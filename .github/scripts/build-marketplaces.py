"""Create both marketplace exports from one verified CI checkout."""

import concurrent.futures
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'scripts'))
import assemble
from package import verified_package


def prepare_source(item, originals):
    url, expected = item['url'], item['sha256']
    if not re.fullmatch(r'https://raw\.githubusercontent\.com/[\w.-]+/[\w.-]+/[0-9a-f]{40}/[\w./-]+', url):
        raise ValueError('expected a pinned GitHub source URL')
    with urllib.request.urlopen(url, timeout=30) as response:
        if response.geturl() != url:
            raise ValueError('unexpected upstream redirect')
        data = response.read(2_000_001)
    if len(data) > 2_000_000 or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f'upstream file differs from lock: {url}')
    destination = originals / expected
    destination.write_bytes(data)
    return destination


def main(workspace, version):
    workspace.mkdir(mode=0o700)
    originals = workspace / 'originals'
    originals.mkdir()
    locked = json.loads((ROOT / '.github/delivery-upstream.json').read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        paths = list(executor.map(lambda item: prepare_source(item, originals), locked))
    from upstream_guard import make_catalog

    catalog = workspace / 'catalog.json'
    catalog.write_text(json.dumps(make_catalog(paths)))
    providers = workspace / 'providers.json'
    providers.write_text('{"version":1,"providers":[]}')
    for product in ('codex', 'claude'):
        package = workspace / f'{product}-package'
        scope = workspace / f'{product}-scope.json'
        scope.write_text(json.dumps({
            'version': 1,
            'components': ['common/base', 'adapters', 'scripts', 'LICENSE', 'NOTICE', 'SECURITY.md', 'INSTALL.md'],
            'artifacts': [str(package)],
        }))
        assemble.build(ROOT, product, package, catalog, scope, providers,
                       native={'version': version, 'profile': 'guarded'})
        report, _ = verified_package(package, product)
        subprocess.run([
            sys.executable, '-B', str(ROOT / 'scripts/delivery.py'),
            '--root', str(ROOT), '--catalog', str(catalog), '--scope', str(scope),
            '--package', str(package), '--product', product,
            '--expect-sha256', report['package_sha256'], '--output', str(workspace / product),
        ], check=True)


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve(), sys.argv[2])
