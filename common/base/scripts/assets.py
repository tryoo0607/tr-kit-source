#!/usr/bin/env python3
"""Deterministic scoped originals and thin local Docling/QMD connections."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def owned(root, relative):
    root = Path(root)
    if root.is_symlink():
        raise ValueError('fixed directory must not be a symlink')
    root = root.resolve()
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('expected a safe relative path')
    path = root / relative
    if not path.resolve().is_relative_to(root):
        raise ValueError('path escapes scope')
    return path


def scope_path(root, ownership, group=None, project=None):
    root = Path(root).expanduser().resolve()
    if ownership == 'environment':
        return root / 'environment'
    if not group or Path(group).name != group or group in ('.', '..'):
        raise ValueError('group must be one path component')
    base = root / 'groups' / group
    if ownership == 'group':
        return base / 'common'
    if not project or Path(project).name != project or project in ('.', '..'):
        raise ValueError('project must be one stable identifier (shared by worktrees)')
    return base / 'projects' / project


def prepare(scope, apply=False):
    scope = Path(scope).resolve()
    paths = [scope / 'originals', scope / 'extracted']
    if apply:
        for path in paths:
            if path.is_symlink():
                raise ValueError('fixed directories must not be symlinks')
            path.mkdir(parents=True, exist_ok=True)
    return {'status': 'prepared' if apply else 'planned', 'directories': list(map(str, paths))}


def output_paths(scope, relative):
    return (owned(Path(scope) / 'originals', relative),
            owned(Path(scope) / 'extracted', str(relative) + '/content.md'),
            owned(Path(scope) / 'extracted', str(relative) + '/provenance.json'))


def freshness(scope, relative):
    source, output, meta = output_paths(scope, relative)
    if not source.exists():
        return 'missing'
    if not output.is_file() or not meta.is_file():
        return 'unindexed'
    try:
        data = json.loads(meta.read_text())
        return 'fresh' if (not data.get('stale') and data['original'] == str(source.resolve())
                           and data['sha256'] == digest(source)
                           and data['output_sha256'] == digest(output)) else 'stale'
    except (OSError, ValueError, KeyError):
        return 'stale'


def extract(scope, relative, command, options=None):
    source, output, meta = output_paths(scope, relative)
    try:
        if not (Path(scope) / 'originals').is_dir():
            return {'status': 'unavailable', 'original': str(source)}
        source.stat()
        if not source.is_file():
            return {'status': 'missing', 'original': str(source)}
    except FileNotFoundError:
        return {'status': 'missing', 'original': str(source)}
    except OSError as exc:
        return {'status': 'unavailable', 'original': str(source), 'error': str(exc)}
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        before = digest(source)
        version = subprocess.run([*command, '--version'], capture_output=True, text=True, check=True).stdout.strip()
        with tempfile.TemporaryDirectory(prefix='.convert-', dir=output.parent) as work:
            offline = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
            result = subprocess.run([*command, 'convert', str(source), '--to', 'md', '--output', work, *(options or [])],
                                    capture_output=True, text=True, env=offline)
            candidates = list(Path(work).rglob('*.md'))
            if result.returncode or len(candidates) != 1 or not candidates[0].stat().st_size:
                raise RuntimeError('conversion failed or did not produce exactly one nonempty Markdown output')
            if digest(source) != before:
                raise RuntimeError('original changed during conversion')
            payload = candidates[0].read_bytes()
            provenance = {'original': str(source.resolve()), 'relative': str(relative), 'sha256': before,
                          'tool': command, 'tool_version': version, 'stale': False,
                          'output_sha256': hashlib.sha256(payload).hexdigest()}
            staged = Path(work) / 'provenance.json'
            staged.write_text(json.dumps(provenance, indent=2) + '\n')
            backups = {}
            for target in [output, meta]:
                backup = Path(work) / (target.name + '.previous')
                if target.exists():
                    shutil.copyfile(target, backup)
                    backups[target] = backup
                else:
                    backups[target] = None
            try:
                os.replace(candidates[0], output)
                os.replace(staged, meta)
            except OSError:
                for target, backup in backups.items():
                    if backup is None:
                        target.unlink(missing_ok=True)
                    else:
                        # Restore before leaving the temporary directory, even if rename failed.
                        try:
                            os.replace(backup, target)
                        except OSError:
                            shutil.copyfile(backup, target)
                raise
        return {'status': 'fresh', **provenance, 'extracted': str(output)}
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        # Never replace a previously usable conversion on failure.
        if meta.is_file():
            try:
                old = json.loads(meta.read_text())
                old.update(stale=True, error=str(exc))
                temporary = meta.with_suffix('.tmp')
                temporary.write_text(json.dumps(old, indent=2) + '\n')
                os.replace(temporary, meta)
            except (OSError, ValueError):
                pass
        return {'status': 'stale' if output.exists() else 'unindexed', 'original': str(source), 'error': str(exc)}


def state_path(scope):
    scope = Path(scope).resolve()
    key = hashlib.sha256(str(scope).encode()).hexdigest()[:16]
    base = Path(os.environ.get('TR_ASSETS_STATE_ROOT', str(Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'tr-kit/assets'))).expanduser().resolve()
    if base == scope or base.is_relative_to(scope):
        raise ValueError('state root must be outside the original scope')
    return base / key


def qmd_connection(scope):
    scope = Path(scope).resolve()
    key = hashlib.sha256(str(scope).encode()).hexdigest()[:16]
    # A dedicated config AND dedicated named index isolate qmd update from all other collections.
    for child in ['config','cache','corpus']:
        if (state_path(scope) / child).is_symlink():
            raise ValueError('QMD state directories must not be symlinks')
    env = dict(os.environ, QMD_CONFIG_DIR=str(state_path(scope) / 'config'),
               XDG_CACHE_HOME=str(state_path(scope) / 'cache'))
    return ['qmd', '--index', 'tr-assets-' + key], env


def index(scope):
    scope = Path(scope).resolve()
    if not (scope / 'originals').is_dir() or not (scope / 'extracted').is_dir():
        return {'status': 'unavailable'}
    if not shutil.which('qmd'):
        return {'status': 'not_configured', 'fallback': 'original paths'}
    command, env = qmd_connection(scope)
    # Publish verified fresh output; retain older corpus entries until deletion is confirmed.
    stage = state_path(scope) / 'corpus'
    stage.mkdir(parents=True, exist_ok=True)
    wanted = set()
    for meta in (scope / 'extracted').rglob('provenance.json'):
        relative = meta.parent.relative_to(scope / 'extracted').as_posix()
        if freshness(scope, relative) == 'fresh':
            target = owned(stage, relative + '.md')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(output_paths(scope, relative)[1], target)
            wanted.add(target)
    # Missing or inaccessible originals are not confirmed deletions. Search validates
    # current originals and freshness before presenting retained indexed candidates.
    for args in (['collection', 'add', str(stage), '--name', 'assets', '--mask', '**/*.md'], ['update']):
        result = subprocess.run(command + args, env=env, capture_output=True, text=True)
        if result.returncode and not ('already exists' in result.stdout + result.stderr and args[0] == 'collection'):
            return {'status': 'unindexed', 'error': result.stderr or result.stdout}
    corpus_files = sorted(str(p.relative_to(stage)) for p in stage.rglob('*.md'))
    (state_path(scope) / 'indexed.json').write_text(json.dumps({'files': corpus_files}))
    return {'status': 'indexed' if wanted else ('stale' if corpus_files else 'empty'), 'count': len(wanted)}


def search(scopes, query, limit=5):
    reports, results, seen = [], [], set()
    for name in scopes:  # caller supplies explicit authorized order; no recursive discovery
        scope = Path(name).resolve()
        try:
            originals = scope / 'originals'
            if not originals.is_dir():
                reports.append({'scope': str(scope), 'status': 'unavailable'})
                continue
            paths = list(originals.rglob('*'))
            paths = [p for p in paths if p.is_file() and p.resolve().is_relative_to(originals.resolve())]
            statuses = {str(p.relative_to(originals)): freshness(scope, p.relative_to(originals)) for p in paths}
            matches = set()
            indexed = (state_path(scope) / 'indexed.json').is_file()
            search_error = None
            indexed_files = set()
            if indexed:
                try:
                    indexed_files = set(json.loads((state_path(scope) / 'indexed.json').read_text()).get('files', []))
                except (OSError, ValueError, TypeError, AttributeError) as exc:
                    indexed = False
                    search_error = str(exc)
            if indexed and shutil.which('qmd'):
                command, env = qmd_connection(scope)
                try:
                    proc = subprocess.run(command + ['search', query, '-c', 'assets', '--format', 'json', '--full-path'],
                                          env=env, capture_output=True, text=True)
                    if proc.returncode:
                        raise ValueError(proc.stderr or 'QMD search failed')
                    hits = json.loads(proc.stdout or '[]')
                    if not isinstance(hits,list) or any(not isinstance(hit,dict) for hit in hits):
                        raise ValueError('invalid QMD JSON response')
                    for hit in hits:
                        hitpath = Path(hit.get('file', hit.get('path', '')))
                        try:
                            relative = hitpath.resolve().relative_to(state_path(scope) / 'corpus').as_posix().removesuffix('.md')
                        except ValueError:
                            continue
                        if (statuses.get(relative) == 'fresh' and relative + '.md' in indexed_files
                                and digest(hitpath) == digest(output_paths(scope, relative)[1])):
                            matches.add(relative)
                except (OSError, ValueError) as exc:
                    indexed = False
                    search_error = str(exc)
            elif indexed:
                indexed = False
                search_error = 'QMD is unavailable; filename/path fallback only'
            for relative, state in statuses.items():
                if query.casefold() in relative.casefold():
                    matches.add(relative)
                if relative not in matches:
                    continue
                source = owned(originals, relative)
                identity = (str(source.resolve()), digest(source))
                if identity in seen:
                    continue
                seen.add(identity)
                results.append({'original': str(source), 'freshness': state, 'scope': str(scope)})
            incomplete = not indexed or 'unindexed' in statuses.values() or any(
                state == 'fresh' and (relative + '.md' not in indexed_files
                    or not owned(state_path(scope) / 'corpus', relative + '.md').is_file()
                    or digest(owned(state_path(scope) / 'corpus', relative + '.md')) != digest(output_paths(scope, relative)[1]))
                for relative, state in statuses.items())
            status = 'empty' if not paths else ('unindexed' if incomplete else ('stale' if 'stale' in statuses.values() else 'searched'))
            reports.append({'scope': str(scope), 'status': status, **({'error':search_error} if search_error else {})})
            if len(results) >= limit:
                break
        except (OSError, ValueError) as exc:
            reports.append({'scope': str(scope), 'status': 'unavailable', 'error': str(exc)})
    return {'scopes': reports, 'results': results[:limit], 'remaining_scopes': [str(p) for p in scopes[len(reports):]]}


def configured_scope(config, ownership, group, project, root=None):
    data = {}
    if config and Path(config).expanduser().exists():
        data = tomllib.loads(Path(config).expanduser().read_text())
        if type(data.get('schema_version')) is not int or data['schema_version'] != 1:
            raise ValueError('unsupported common config')
    if ownership == 'project':
        override = data.get('projects', {}).get(project, {}).get('assets')
    elif ownership == 'group':
        override = data.get('groups', {}).get(group, {}).get('assets')
    else:
        override = data.get('common', {}).get('assets')
    if override:
        override = Path(override).expanduser()
        if not override.is_absolute() or '..' in override.parts:
            raise ValueError('absolute safe scope override required')
        return override
    base = root or data.get('roots', {}).get('assets', str(Path.home() / 'projects/_tr-assets'))
    return scope_path(base, ownership, group, project)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['scope', 'prepare', 'extract', 'index', 'search'])
    p.add_argument('--scope', action='append', default=[])
    p.add_argument('--root')
    p.add_argument('--config', default=str(Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'tr-kit/config.toml'))
    p.add_argument('--ownership', choices=['environment', 'group', 'project'], default='project')
    p.add_argument('--group'); p.add_argument('--project')
    p.add_argument('--apply', action='store_true')
    p.add_argument('--relative'); p.add_argument('--query'); p.add_argument('--limit', type=int, default=5)
    p.add_argument('--docling-command', nargs='+', default=['docling'])
    p.add_argument('--docling-args', default='[]', help='JSON array of explicit Docling convert options; no automatic model downloads')
    a = p.parse_args()
    scopes = a.scope or [str(configured_scope(a.config, a.ownership, a.group, a.project, a.root))]
    if len(scopes) > 1 and a.action != 'search':
        p.error('multiple scopes are supported only for sequential search')
    if a.action == 'scope': result = {'scope': scopes[0]}
    elif a.action == 'prepare': result = prepare(scopes[0], a.apply)
    elif a.action == 'extract':
        if not a.relative: p.error('--relative required')
        options = json.loads(a.docling_args)
        if not isinstance(options, list) or any(not isinstance(x, str) for x in options): p.error('--docling-args must be a JSON string array')
        if any(x in {'--output','--to'} or x.startswith(('--output=','--to=')) for x in options): p.error('output and format are owned by the helper')
        result = extract(scopes[0], a.relative, a.docling_command, options)
    elif a.action == 'index': result = index(scopes[0])
    else:
        if not a.query: p.error('--query required')
        if a.limit < 1: p.error('--limit must be positive')
        result = search(scopes, a.query, a.limit)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
