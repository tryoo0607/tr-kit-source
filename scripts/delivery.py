#!/usr/bin/env python3
"""Verify and deliver generated marketplaces in disposable repository clones."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def verify(package, product, revision):
    report = json.loads((package / 'release.json').read_text())
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
    marketplace = json.loads((package / metadata / 'marketplace.json').read_text())
    expected = {'source': 'local', 'path': f'./plugins/{name}'} if product == 'codex' else f'./plugins/{name}'
    if marketplace['name'] != name or len(marketplace['plugins']) != 1:
        raise ValueError('marketplace identity mismatch')
    if marketplace['plugins'][0]['name'] != name or marketplace['plugins'][0]['source'] != expected:
        raise ValueError('marketplace source mismatch')
    manifest_dir = '.codex-plugin' if product == 'codex' else '.claude-plugin'
    payload = package / 'plugins' / name
    manifest = json.loads((payload / manifest_dir / 'plugin.json').read_text())
    if manifest['name'] != name or manifest['version'] != report['version']:
        raise ValueError('plugin identity mismatch')
    assembly = json.loads((payload / 'assembly.json').read_text())
    if assembly['product'] != product:
        raise ValueError('assembly product mismatch')
    for relative, digest in assembly['files'].items():
        path = (payload / relative).resolve()
        if not path.is_relative_to(payload.resolve()) or not path.is_file():
            raise ValueError('invalid assembly path')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('assembly integrity mismatch')
    return actual


def replace(package, clone):
    # Only called on a new disposable clone created by prepare().
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


def prepare(package, clone, product, revision, url):
    verify(package, product, revision)
    if clone.exists():
        raise ValueError('delivery clone must not already exist')
    subprocess.run(['git', 'clone', '--quiet', '--branch', 'main', '--single-branch',
                    '--', url, str(clone)], check=True)
    replace(package, clone)
    verify(clone, product, revision)
    git(clone, 'add', '--force', '-A')
    first = git(clone, 'write-tree')
    replace(package, clone)
    git(clone, 'add', '--force', '-A')
    if git(clone, 'write-tree') != first:
        raise ValueError('delivery is not idempotent')
    # Preserve pinned upstream bytes, including their whitespace conventions.
    return git(clone, 'diff', '--cached', '--stat')


def publish(clone, revision):
    if os.environ.get('TR_KIT_ALLOW_PUSH') != '1':
        raise ValueError('push requires TR_KIT_ALLOW_PUSH=1')
    if not git(clone, 'diff', '--cached', '--name-only'):
        return 'no-op'
    git(clone, 'config', 'user.name', 'github-actions[bot]')
    git(clone, 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
    git(clone, 'commit', '-m', f'chore: deploy tr-kit-source {revision[:12]}')
    git(clone, 'push', 'origin', 'HEAD:main')
    return 'pushed'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--built-root', type=Path, required=True)
    parser.add_argument('--clone-root', type=Path, required=True)
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--push', action='store_true')
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
    for product in ('codex', 'claude'):
        clone = args.clone_root / product
        url = os.environ.get(f'TR_KIT_{product.upper()}_REPOSITORY_URL',
                             f'https://github.com/tryoo0607/tr-{product}.git')
        changed = prepare(args.built_root / product, clone, product, args.source_revision, url)
        print(f'[{product}] verified\n{changed or "no changes"}')
    # Both targets are prepared successfully before the first remote write.
    if args.push:
        for product in ('codex', 'claude'):
            print(f'[{product}] {publish(args.clone_root / product, args.source_revision)}')
    else:
        print('dry-run: no commits or pushes performed')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        raise SystemExit(f'delivery failed: {error}')
