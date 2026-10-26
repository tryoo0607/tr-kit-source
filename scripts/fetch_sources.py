#!/usr/bin/env python3
"""Fetch declared public upstreams without resetting existing checkouts."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tomllib

from build import declarations


def fetch(root, cache):
    registry = tomllib.loads((root / 'sources.toml').read_text())
    if registry.get('schema_version') != 1 or set(registry) != {'schema_version', 'sources'}:
        raise ValueError('unsupported source registry')
    revisions = {}
    for path in [root / 'common/base/dependencies.toml',
                 *sorted((root / 'adapters').glob('*/dependencies.toml'))]:
        for entry in declarations(path):
            alias, revision = entry['source'], entry['revision']
            if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', alias):
                raise ValueError('fetch requires a repository alias')
            if not re.fullmatch(r'[a-f0-9]{40}', revision):
                raise ValueError('fetch requires an exact revision')
            if alias in revisions and revisions[alias] != revision:
                raise ValueError(f'conflicting revisions: {alias}')
            revisions[alias] = revision
    cache.mkdir(parents=True, exist_ok=True)
    report = []
    for alias, revision in sorted(revisions.items()):
        url = registry['sources'].get(alias, '')
        if not re.fullmatch(r'https://github.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git', url):
            raise ValueError(f'invalid public source URL: {alias}')
        destination = cache / alias
        if destination.is_symlink():
            raise ValueError(f'checkout must not be a symlink: {alias}')
        if not destination.exists():
            subprocess.run(['git', 'clone', '--no-checkout', url, str(destination)], check=True)
            subprocess.run(['git', '-C', str(destination), 'checkout', '--detach', revision], check=True)
        def git(*args):
            return subprocess.check_output(['git', '-C', str(destination), *args], text=True).strip()
        if git('status', '--porcelain') or git('rev-parse', 'HEAD') != revision:
            raise ValueError(f'existing checkout is dirty or has another revision: {alias}')
        if git('config', '--get', 'remote.origin.url').removesuffix('.git') != url.removesuffix('.git'):
            raise ValueError(f'upstream origin mismatch: {alias}')
        report.append({'source': alias, 'revision': revision, 'path': str(destination)})
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--cache', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    cache = args.cache or Path(os.environ.get('TR_KIT_SOURCE_CACHE') or root / '.cache/upstreams')
    try:
        print(json.dumps(fetch(root, cache.expanduser().resolve()), indent=2))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'source fetch failed; existing checkouts were not reset: {error}\n')
