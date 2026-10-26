#!/usr/bin/env python3
"""Assemble selected skills from verified local Git checkouts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import tomllib


class BuildError(ValueError):
    pass


def inside(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise BuildError(f"path escapes source: {value}")
    return path


def copy_tree(source, destination, omit_bindings=False):
    if not source.is_dir():
        raise BuildError(f"missing directory: {source}")
    for item in sorted(source.rglob('*')):
        if '__pycache__' in item.relative_to(source).parts or item.suffix in {'.pyc', '.pyo'}:
            continue
        if item.is_symlink():
            raise BuildError(f"symlink requires explicit mapping: {item}")
        if item.is_file():
            if omit_bindings and item.name == 'bindings.toml':
                continue
            target = destination / item.relative_to(source)
            if target.exists():
                raise BuildError(f"output collision: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def declarations(path):
    if not path.exists():
        return []
    data = tomllib.loads(path.read_text())
    if data.get('schema_version') != 1 or set(data) - {'schema_version', 'skills'}:
        raise BuildError(f"invalid declaration: {path}")
    entries = data.get('skills', [])
    if not isinstance(entries, list):
        raise BuildError('skills must be an array')
    return entries


def bind_skill(stage, skill, binding_file):
    data = tomllib.loads(binding_file.read_text())
    if data.get('schema_version') != 1 or set(data) - {'schema_version', 'replacements', 'runtime_note'}:
        raise BuildError(f'invalid binding: {binding_file}')
    folder = stage / 'skills' / skill
    if not folder.is_dir():
        raise BuildError(f'binding skill is not included: {skill}')
    changes = []
    replacements = data.get('replacements', [])
    if not isinstance(replacements, list):
        raise BuildError('replacements must be an array')
    for item in replacements:
        required = {'file', 'old', 'new', 'count'}
        if not isinstance(item, dict) or not required.issubset(item) or set(item) - required - {'target_skill', 'target_file'}:
            raise BuildError('invalid replacement fields')
        if not all(isinstance(item[k], str) and item[k] for k in ['file', 'old', 'new']):
            raise BuildError('replacement fields must be non-empty strings')
        if type(item['count']) is not int or item['count'] <= 0:
            raise BuildError('replacement count must be positive')
        if 'target_skill' in item:
            target = item['target_skill']
            if not isinstance(target, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]*', target):
                raise BuildError('invalid target skill')
            if not (stage / 'skills' / target / 'SKILL.md').is_file():
                raise BuildError(f'missing linked skill: {target}')
        if 'target_file' in item:
            if not isinstance(item['target_file'], str) or not item['target_file']:
                raise BuildError('invalid target file')
            if not inside(folder, item['target_file']).is_file():
                raise BuildError(f'missing linked file: {item["target_file"]}')
        path = inside(folder, item['file'])
        if path.suffix != '.md':
            raise BuildError('bindings only modify Markdown instructions')
        content = path.read_text()
        if content.count(item['old']) != item['count']:
            raise BuildError(f'binding source drift: {skill}/{item["file"]}')
        path.write_text(content.replace(item['old'], item['new']))
        changes.append({'file': item['file'], 'count': item['count'],
                        'target_skill': item.get('target_skill'), 'target_file': item.get('target_file')})
    note = data.get('runtime_note')
    if note is not None:
        if not isinstance(note, str) or not note.strip():
            raise BuildError('runtime note must be non-empty text')
        path = folder / 'SKILL.md'
        content = path.read_text()
        if not content.startswith('---\n') or '\n---\n' not in content[4:]:
            raise BuildError('binding requires YAML frontmatter')
        end = content.index('\n---\n', 4) + 5
        path.write_text(content[:end] + '\n' + note + '\n' + content[end:])
    return {'skill': skill, 'changes': changes, 'runtime_note': note is not None}


def assemble(root, product, output, *, version='0.0.0', source_cache=None):
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?', version):
        raise BuildError('invalid plugin version')
    base = root / 'common/base'
    adapter = root / 'adapters' / product
    ids = set()
    records = []
    resolved_sources = {}
    cache = Path(source_cache or os.environ.get('TR_KIT_SOURCE_CACHE') or root / '.cache/upstreams').expanduser().resolve()
    for entry in declarations(base / 'dependencies.toml') + declarations(adapter / 'dependencies.toml'):
        if not {'id', 'source', 'revision', 'path'}.issubset(entry) or set(entry) - {'id', 'source', 'revision', 'path', 'requires', 'license_files', 'wrapped', 'resources'}:
            raise BuildError('dependency fields must be id, source, revision, path')
        if type(entry.get('wrapped', False)) is not bool:
            raise BuildError('wrapped must be a boolean')
        if not all(isinstance(entry[k], str) and entry[k] for k in ['id', 'source', 'revision', 'path']):
            raise BuildError('dependency fields must be non-empty strings')
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', entry['id']):
            raise BuildError('invalid dependency id')
        if entry['id'] in ids:
            raise BuildError(f"duplicate dependency: {entry['id']}")
        ids.add(entry['id'])
        declared = Path(entry['source']).expanduser()
        if declared.is_absolute():
            source = declared.resolve()
        else:
            if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', entry['source']):
                raise BuildError('relative source must be a repository alias')
            source = cache / entry['source']
        resolved_sources[entry['id']] = source
        commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
        if not re.fullmatch(r'[0-9a-f]{40}', entry['revision']) or commit != entry['revision']:
            raise BuildError(f"revision mismatch: {entry['id']}")
        if subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True).strip():
            raise BuildError(f"dirty source: {entry['id']}")
        selected = inside(source, entry['path'])
        if not (selected / 'SKILL.md').is_file():
            raise BuildError(f"missing SKILL.md: {entry['id']}")
        content = (selected / 'SKILL.md').read_text()
        name = re.search(r'^name:\s*(.+)$', content, re.M)
        if not name or name.group(1).strip().strip('\"\'') != entry['id']:
            raise BuildError(f"skill id must match frontmatter name: {entry['id']}")
        for item in selected.rglob('*'):
            if item.is_file() and not item.is_symlink():
                text = item.read_bytes()
                if b'${CLAUDE_PLUGIN_ROOT}' in text or b'${PLUGIN_ROOT}' in text:
                    raise BuildError(f"plugin root dependency requires mapping: {entry['id']}")
        if product == 'codex' and re.search(r'^hooks\s*:', content, re.M):
            raise BuildError(f"Codex skill hook adapter required: {entry['id']}")
        licenses = entry.get('license_files', [])
        if not isinstance(licenses, list) or not all(isinstance(v, str) and v for v in licenses):
            raise BuildError(f'invalid license_files: {entry["id"]}')
        if len(set(licenses)) != len(licenses):
            raise BuildError(f'duplicate license file: {entry["id"]}')
        for value in licenses:
            if Path(value).is_absolute() or '..' in Path(value).parts:
                raise BuildError(f'invalid license path: {value}')
            license_path = inside(source, value)
            if not license_path.is_file() or (source / value).is_symlink():
                raise BuildError(f'missing or unsupported license file: {value}')
        resources = entry.get('resources', [])
        if not isinstance(resources, list):
            raise BuildError(f'invalid resources: {entry["id"]}')
        for resource in resources:
            if not isinstance(resource, dict) or set(resource) != {'source', 'target'}:
                raise BuildError('resource requires source and target')
            for value in resource.values():
                if not isinstance(value, str) or not value or Path(value).is_absolute() or '..' in Path(value).parts or value == '.':
                    raise BuildError('invalid resource path')
            candidate = inside(source, resource['source'])
            if not candidate.exists() or (source / resource['source']).is_symlink():
                raise BuildError('missing or unsupported resource')
        records.append((entry, selected, commit))
    for entry, _, _ in records:
        requires = entry.get('requires', [])
        if not isinstance(requires, list) or not all(isinstance(v, str) and v in ids for v in requires):
            raise BuildError(f'missing or invalid required skill: {entry["id"]}')
    if output.exists():
        raise BuildError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        stage = Path(temporary) / 'payload'
        stage.mkdir()
        for folder in (base / 'skills', adapter / 'skills'):
            if folder.exists():
                copy_tree(folder, stage / 'skills', omit_bindings=True)
        for folder in (base / 'scripts', adapter / 'scripts'):
            if folder.exists():
                copy_tree(folder, stage / 'scripts')
        report = []
        for entry, selected, commit in records:
            destination = stage / 'skills' / entry['id']
            wrapped = entry.get('wrapped', False)
            if wrapped and not (destination / 'SKILL.md').is_file():
                raise BuildError(f'missing wrapper SKILL.md: {entry["id"]}')
            if not wrapped and destination.exists():
                raise BuildError(f"skill collision: {entry['id']}")
            payload = destination / 'upstream' if wrapped else destination
            copy_tree(selected, payload)
            if wrapped:
                if (payload / 'GUIDE.md').exists():
                    raise BuildError(f'upstream guide name collision: {entry["id"]}')
                (payload / 'SKILL.md').rename(payload / 'GUIDE.md')
                if list(payload.rglob('SKILL.md')):
                    raise BuildError(f'nested upstream skill requires mapping: {entry["id"]}')
            for value in entry.get('license_files', []):
                target = inside(payload, value)
                if target.exists():
                    raise BuildError(f'output collision: {target}')
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(inside(resolved_sources[entry['id']], value), target)
            for resource in entry.get('resources', []):
                origin = inside(resolved_sources[entry['id']], resource['source'])
                target = inside(stage, resource['target'])
                if target.exists():
                    raise BuildError(f'output collision: {target}')
                if origin.is_dir():
                    copy_tree(origin, target)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(origin, target)
            report.append({'id': entry['id'], 'revision': commit, 'path': entry['path'],
                           'requires': entry.get('requires', []),
                           'wrapped': wrapped,
                           'license_files': entry.get('license_files', []),
                           'resources': entry.get('resources', []),
                           'skill_hook_declared': bool(re.search(r'^hooks\s*:', (selected / 'SKILL.md').read_text(), re.M))})
        bindings = []
        for scope, folder in [('common', base / 'skills'), (product, adapter / 'skills')]:
            for path in sorted(folder.glob('*/bindings.toml')):
                record = bind_skill(stage, path.parent.name, path)
                record['scope'] = scope
                bindings.append(record)
        filename = 'AGENTS.md' if product == 'codex' else 'CLAUDE.md'
        template = (adapter / (filename + '.template')).read_text()
        if template.count('{{COMMON_INSTRUCTIONS}}') != 1:
            raise BuildError('template must contain exactly one common marker')
        result = template.replace('{{COMMON_INSTRUCTIONS}}', (base / 'instructions.md').read_text())
        if '{{' in result or '}}' in result:
            raise BuildError('unresolved template marker')
        (stage / filename).write_text(result)
        workflow = base / 'workflow.md'
        if workflow.is_file():
            workflow_target = stage / 'workflow.md'
            if workflow_target.exists():
                raise BuildError('output collision: workflow.md')
            shutil.copy2(workflow, workflow_target)
        elif '](workflow.md)' in result:
            raise BuildError('missing referenced workflow.md')
        manifest_dir = stage / ('.codex-plugin' if product == 'codex' else '.claude-plugin')
        manifest_dir.mkdir()
        manifest = {'name': f'tr-{product}', 'version': version}
        if product == 'codex':
            manifest['skills'] = './skills/'
        mcp = adapter / 'mcp.json'
        if mcp.is_file():
            config = json.loads(mcp.read_text())
            if not isinstance(config.get('mcpServers'), dict):
                raise BuildError('mcp.json requires mcpServers')
            shutil.copy2(mcp, stage / '.mcp.json')
            if product == 'codex':
                manifest['mcpServers'] = './.mcp.json'
        (manifest_dir / 'plugin.json').write_text(json.dumps(manifest, indent=2) + '\n')
        files = {str(p.relative_to(stage)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(stage.rglob('*')) if p.is_file()}
        (stage / 'assembly.json').write_text(json.dumps({'product': product, 'dependencies': report, 'bindings': bindings, 'files': files,
                                                      'plugin_hooks': []}, indent=2) + '\n')
        stage.rename(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('product', choices=['codex', 'claude'])
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-cache', type=Path)
    args = parser.parse_args()
    try:
        assemble(args.root.resolve(), args.product, args.output.resolve(), source_cache=args.source_cache)
    except (BuildError, OSError, subprocess.CalledProcessError, tomllib.TOMLDecodeError) as error:
        parser.exit(1, f'build failed: {error}\n')
