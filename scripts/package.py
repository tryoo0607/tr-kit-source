#!/usr/bin/env python3
"""Build Codex and Claude marketplaces using their existing product identities."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import re
import shutil
import subprocess

from build import assemble


def package(root, output, product='codex', version=None, source_revision=None):
    if product not in {'codex', 'claude'}:
        raise ValueError('unsupported product')
    if output.exists():
        raise ValueError('output already exists; choose a new path')
    output.parent.mkdir(parents=True, exist_ok=True)
    version = version or (root / 'VERSION').read_text().strip()
    source_revision = source_revision or subprocess.check_output(
        ['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if not re.fullmatch(r'[a-f0-9]{40}', source_revision):
        raise ValueError('source revision must be a full commit SHA')
    name = f'tr-{product}'
    plugin_version = f'{version}+{product}.{source_revision[:12]}'
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        stage = Path(temporary) / 'marketplace'
        payload = stage / 'plugins' / name
        assemble(root, product, payload, version=plugin_version)
        metadata = stage / ('.agents/plugins' if product == 'codex' else '.claude-plugin')
        metadata.mkdir(parents=True)
        source = {'source': 'local', 'path': f'./plugins/{name}'} if product == 'codex' else f'./plugins/{name}'
        entry = {'name': name, 'source': source}
        marketplace = {'name': name, 'plugins': [entry]}
        if product == 'codex':
            marketplace['interface'] = {'displayName': name}
            entry.update(policy={'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'},
                         category='Developer Tools')
        else:
            marketplace['owner'] = {'name': 'tryoo0607'}
        (metadata / 'marketplace.json').write_text(json.dumps(marketplace, indent=2) + '\n')
        for filename in ('LICENSE', 'NOTICE', 'SECURITY.md'):
            if (root / filename).is_file():
                shutil.copy2(root / filename, stage / filename)
        (stage / 'README.md').write_text(
            f'# {name}\n\nGenerated from [tr-kit-source](https://github.com/tryoo0607/tr-kit-source) '
            f'commit `{source_revision}`. Do not edit generated files.\n\n'
            f'Marketplace: `tryoo0607/{name}`; plugin: `{name}@{name}`.\n')
        (stage / '.tr-kit-generated').write_text('tr-kit-source\n')
        files = {str(p.relative_to(stage)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(stage.rglob('*')) if p.is_file()}
        (stage / 'release.json').write_text(json.dumps({
            'product': product, 'source_revision': source_revision,
            'version': plugin_version, 'files': files}, indent=2) + '\n')
        stage.rename(output)
    return {'marketplace': name, 'plugin': name,
            'root': str(output), 'version': plugin_version,
            'installed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--product', choices=['codex', 'claude'], default='codex')
    parser.add_argument('--version')
    parser.add_argument('--source-revision')
    args = parser.parse_args()
    try:
        print(json.dumps(package(args.root.resolve(), args.output.resolve(), args.product,
                                 args.version, args.source_revision), indent=2))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'packaging failed: {error}\n')
