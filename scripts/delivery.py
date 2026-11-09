#!/usr/bin/env python3
"""Verify and deliver generated marketplaces in disposable repository clones."""
import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from delivery_scan import strict_json, checksum_lines, scan


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def verify(package, product, revision):
    if package.is_symlink() or any(p.is_symlink() for p in package.parents):
        raise ValueError('release must not contain symlinks')
    if any('.git' in p.relative_to(package).parts and p.relative_to(package).parts[0] != '.git'
           for p in package.rglob('*')):
        raise ValueError('nested Git metadata is not a release payload')
    report = strict_json((package / 'release.json').read_bytes())
    if report['product'] != product or report['source_revision'] != revision:
        raise ValueError('release provenance mismatch')
    if not (package / '.tr-kit-generated').is_file():
        raise ValueError('missing generated-root marker')
    paths = [p for p in package.rglob('*') if '.git' not in p.relative_to(package).parts]
    if any(p.is_symlink() for p in paths):
        raise ValueError('release must not contain symlinks')
    actual = {str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in paths if p.is_file() and p != package / 'release.json'}
    if actual != report['files']:
        raise ValueError('release integrity mismatch')
    name = f'tr-{product}'
    metadata = '.agents/plugins' if product == 'codex' else '.claude-plugin'
    marketplace = strict_json((package / metadata / 'marketplace.json').read_text())
    expected = {'source': 'local', 'path': f'./plugins/{name}'} if product == 'codex' else f'./plugins/{name}'
    if marketplace['name'] != name or len(marketplace['plugins']) != 1:
        raise ValueError('marketplace identity mismatch')
    if marketplace['plugins'][0]['name'] != name or marketplace['plugins'][0]['source'] != expected:
        raise ValueError('marketplace source mismatch')
    manifest_dir = '.codex-plugin' if product == 'codex' else '.claude-plugin'
    payload = package / 'plugins' / name
    manifest = strict_json((payload / manifest_dir / 'plugin.json').read_text())
    if manifest['name'] != name or manifest['version'] != report['version']:
        raise ValueError('plugin identity mismatch')
    assembly = strict_json((payload / 'assembly.json').read_text())
    if assembly['product'] != product or assembly['source_revision'] != revision:
        raise ValueError('assembly provenance mismatch')
    assembled = {str(p.relative_to(payload)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in payload.rglob('*') if p.is_file() and p != payload / 'assembly.json'}
    if assembled != assembly['files']:
        raise ValueError('assembly integrity mismatch')
    for data in (report, assembly):
        if not isinstance(data['files'], dict) or not all(
                isinstance(k, str) and isinstance(v, str) and re.fullmatch(r'[a-f0-9]{64}', v)
                for k, v in data['files'].items()):
            raise ValueError('malformed files map')
    checksum_lines((package / 'release.json').read_bytes())
    checksum_lines((payload / 'assembly.json').read_bytes())
    for relative, digest in assembly['files'].items():
        path = (payload / relative).resolve()
        if not path.is_relative_to(payload.resolve()) or not path.is_file():
            raise ValueError('invalid assembly path')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('assembly integrity mismatch')
    return actual


def replace(package, clone):
    # Only called on a new disposable clone created by prepare().
    if (package / '.git').exists() or (package / '.git').is_symlink():
        raise ValueError('package must not include Git metadata')
    for path in clone.iterdir():
        if path.name == '.git':
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    for path in package.iterdir():
        if path.is_dir():
            shutil.copytree(path, clone / path.name)
        else:
            shutil.copy2(path, clone / path.name)


def stage_changed(clone):
    tracked = subprocess.check_output(['git', '-C', str(clone), 'ls-files', '-z']).split(b'\0')
    present = [os.fsencode(str(p.relative_to(clone))) for p in clone.rglob('*')
               if p.is_file() and '.git' not in p.relative_to(clone).parts]
    changed = subprocess.check_output(['git', '-C', str(clone), 'diff', '--name-only', '-z']).split(b'\0')
    paths = sorted((set(changed) | (set(present) - set(tracked))) - {b''})
    if not paths:
        return
    # Exact NUL-delimited literal paths include removals and ignored upstream assets.
    subprocess.run(['git', '-C', str(clone), '--literal-pathspecs', 'add', '--force', '-A',
                    '--pathspec-from-file=-', '--pathspec-file-nul'],
                   input=b'\0'.join(paths) + b'\0', check=True)


@dataclass(frozen=True)
class Prepared:
    package: Path
    clone: Path
    product: str
    revision: str
    url: str
    parent: str
    tree: str
    package_hashes: tuple
    candidates: tuple
    unchanged: tuple
    changed: str
    ref: str = 'refs/heads/main'


@dataclass(frozen=True)
class Audited:
    prepared: Prepared
    commit: str | None
    counts: dict


def package_hashes(package):
    return tuple(sorted((str(p.relative_to(package)), hashlib.sha256(p.read_bytes()).hexdigest())
                        for p in package.rglob('*') if p.is_file() and '.git' not in p.relative_to(package).parts))


def tree_blobs(repo, tree):
    result = {}
    for entry in subprocess.check_output(['git', '-C', str(repo), 'ls-tree', '-r', '-z', tree]).split(b'\0'):
        if not entry:
            continue
        header, name = entry.split(b'\t', 1)
        mode, kind, oid = header.split()
        if kind != b'blob' or mode not in (b'100644', b'100755'):
            raise ValueError('unsupported delivery tree entry')
        result[os.fsdecode(name)] = oid.decode()
    return result


def remote_parent(state):
    output = git(state.clone, 'ls-remote', '--exit-code', '--', state.url, state.ref).splitlines()
    if output != [state.parent + '\t' + state.ref]:
        raise ValueError('delivery remote parent changed')


def validate(state, commit=None):
    clone = state.clone
    if (git(clone, 'remote', 'get-url', 'origin') != state.url or
            git(clone, 'remote', 'get-url', '--push', 'origin') != state.url or
            git(clone, 'symbolic-ref', 'HEAD') != state.ref or
            git(clone, 'rev-parse', 'refs/remotes/origin/main') != state.parent):
        raise ValueError('delivery remote/ref binding changed')
    expected_head = commit or state.parent
    if git(clone, 'rev-parse', 'HEAD') != expected_head:
        raise ValueError('unknown outgoing commit range')
    if commit is not None and git(clone, 'rev-list', '--parents', '-n', '1', commit).split() != [commit, state.parent]:
        raise ValueError('delivery requires exactly one audited commit')
    if commit is not None and git(clone, 'rev-parse', commit + '^{tree}') != state.tree:
        raise ValueError('audited commit tree changed')
    if commit is not None:
        raw = subprocess.check_output(['git', '-C', str(clone), 'cat-file', 'commit', commit])
        message = raw.split(b'\n\n', 1)[1]
        expected_message = f'chore: deploy tr-kit-source {state.revision[:12]}\n'.encode()
        if message != expected_message:
            raise ValueError('audited commit message changed')
    verify(state.package, state.product, state.revision)
    verify(clone, state.product, state.revision)
    if package_hashes(state.package) != state.package_hashes or package_hashes(clone) != state.package_hashes:
        raise ValueError('prepared package bytes changed')
    if git(clone, 'write-tree') != state.tree:
        raise ValueError('prepared index tree changed')
    blobs = tree_blobs(clone, state.tree)
    algorithm = git(clone, 'rev-parse', '--show-object-format')
    if set(blobs) != dict(state.package_hashes).keys():
        raise ValueError('index package paths mismatch')
    for name, oid in blobs.items():
        blob = (clone / name).read_bytes()
        observed = hashlib.new(algorithm, b'blob ' + str(len(blob)).encode() + b'\0' + blob).hexdigest()
        if oid != observed:
            raise ValueError('delivery index bytes do not match verified bytes')
    parent_blobs = tree_blobs(clone, state.parent)
    unchanged = tuple(sorted((name, oid) for name, oid in blobs.items() if parent_blobs.get(name) == oid))
    candidates = tuple(sorted(set(blobs) - dict(unchanged).keys()))
    if unchanged != state.unchanged or candidates != state.candidates:
        raise ValueError('outgoing candidate binding changed')
    remote_parent(state)


def prepare(package, clone, product, revision, url):
    verify(package, product, revision)
    if clone.exists():
        raise ValueError('delivery clone must not already exist')
    subprocess.run(['git', 'clone', '--quiet', '--branch', 'main', '--single-branch',
                    '--', url, str(clone)], check=True)
    parent = git(clone, 'rev-parse', 'HEAD')
    replace(package, clone)
    verify(clone, product, revision)
    stage_changed(clone)
    first = git(clone, 'write-tree')
    replace(package, clone)
    stage_changed(clone)
    if git(clone, 'write-tree') != first:
        raise ValueError('delivery is not idempotent')
    blobs = tree_blobs(clone, first)
    parent_blobs = tree_blobs(clone, parent)
    unchanged = tuple(sorted((name, oid) for name, oid in blobs.items() if parent_blobs.get(name) == oid))
    candidates = tuple(sorted(set(blobs) - dict(unchanged).keys()))
    state = Prepared(package, clone, product, revision, url, parent, first, package_hashes(package),
                     candidates, unchanged, git(clone, 'diff', '--cached', '--stat'))
    validate(state)
    return state


def audit(state, scanner, *, create_commit=False):
    validate(state)
    counts = scan(state.clone, state.product, state.revision, scanner, candidate_paths=state.candidates)
    validate(state)
    commit = None
    if create_commit and state.tree != git(state.clone, 'rev-parse', state.parent + '^{tree}'):
        git(state.clone, 'config', 'user.name', 'github-actions[bot]')
        git(state.clone, 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
        git(state.clone, 'commit', '-m', f'chore: deploy tr-kit-source {state.revision[:12]}')
        commit = git(state.clone, 'rev-parse', 'HEAD')
        validate(state, commit)
    return Audited(state, commit, counts)


def publish(audited):
    if os.environ.get('TR_KIT_ALLOW_PUSH') != '1':
        raise ValueError('push requires TR_KIT_ALLOW_PUSH=1')
    state = audited.prepared
    validate(state, audited.commit)
    if audited.commit is None:
        if state.tree != git(state.clone, 'rev-parse', state.parent + '^{tree}'):
            raise ValueError('delivery commit has not been audited')
        return 'no-op'
    # Explicit immutable OID, normal non-force fast-forward push. No late scanning.
    git(state.clone, 'push', 'origin', audited.commit + ':' + state.ref)
    return 'pushed'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--built-root', type=Path, required=True)
    parser.add_argument('--clone-root', type=Path, required=True)
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--push', action='store_true')
    parser.add_argument('--gitleaks', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-f0-9]{40}', args.source_revision):
        raise ValueError('source revision must be a full commit SHA')
    if args.push:
        root = Path(__file__).resolve().parents[1]
        if os.environ.get('TR_KIT_ALLOW_PUSH') != '1':
            raise ValueError('push requires TR_KIT_ALLOW_PUSH=1')
        if git(root, 'rev-parse', 'HEAD') != args.source_revision or git(root, 'status', '--porcelain'):
            raise ValueError('push requires a clean checkout of the declared source revision')
    if args.clone_root.exists():
        raise ValueError('clone root must not already exist')
    # Check both packages before even creating a delivery clone.
    for product in ('codex', 'claude'):
        verify(args.built_root / product, product, args.source_revision)
    args.clone_root.mkdir(parents=True)
    audited = []
    for product in ('codex', 'claude'):
        clone = args.clone_root / product
        url = os.environ.get(f'TR_KIT_{product.upper()}_REPOSITORY_URL',
                             f'https://github.com/tryoo0607/tr-{product}.git')
        state = prepare(args.built_root / product, clone, product, args.source_revision, url)
        result = audit(state, args.gitleaks, create_commit=args.push)
        audited.append(result)
        print(f'[{product}] verified scan={json.dumps(result.counts, sort_keys=True)}\n{state.changed or "no changes"}')
    # Both targets are prepared successfully before the first remote write.
    if args.push:
        for result in audited:
            validate(result.prepared, result.commit)
        for result in audited:
            print(f'[{result.prepared.product}] {publish(result)}')
    else:
        print('dry-run: no commits or pushes performed')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        raise SystemExit(f'delivery failed: {error}')
