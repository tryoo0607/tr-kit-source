#!/usr/bin/env python3
"""Provision the selected development tools in an explicit, isolated prefix."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tarfile
import tomllib
import urllib.request


def write_environment(prefix):
    state = prefix / 'state'
    state.mkdir(exist_ok=True)
    exports = {
        'TR_DEVTOOLS_ROOT': str(prefix),
        'PLAYWRIGHT_BROWSERS_PATH': str(prefix / 'browsers'),
        'SEMGREP_SETTINGS_FILE': str(state / 'semgrep-settings.yml'),
        'SEMGREP_LOG_FILE': str(state / 'semgrep.log'),
        'SEMGREP_ENABLE_VERSION_CHECK': '0',
        'SEMGREP_SEND_METRICS': 'off',
    }
    (prefix / 'env.sh').write_text(
        '# Source explicitly in the selected shell; no host settings are changed.\n'
        + ''.join(f'export {key}={shlex.quote(value)}\n' for key, value in exports.items())
        + f'export PATH={shlex.quote(str(prefix / "bin"))}:"$PATH"\n')


def provision(prefix, manifest, uv):
    config = tomllib.loads(manifest.read_text())
    if config['schema_version'] != 1:
        raise ValueError('unsupported manifest')
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64'):
        raise ValueError('this provisioner currently supports Linux x86_64 only')
    if prefix.exists():
        raise ValueError('use a new prefix; existing toolchains are never overwritten')
    node = shutil.which('node')
    npm = shutil.which('npm')
    if not node or not npm or not uv:
        raise ValueError('node, npm and uv are required before provisioning')
    version = subprocess.check_output([node, '--version'], text=True).strip().lstrip('v')
    if tuple(map(int, version.split('.'))) < tuple(map(int, config['node']['minimum'].split('.'))):
        raise ValueError('Node version is below the manifest minimum')
    prefix.mkdir(parents=True)
    env = dict(os.environ, UV_CACHE_DIR=str(prefix / 'uv-cache'),
               PLAYWRIGHT_BROWSERS_PATH=str(prefix / 'browsers'),
               npm_config_cache=str(prefix / 'npm-cache'))

    def run(*args):
        subprocess.run(list(map(str, args)), env=env, check=True, cwd=prefix)

    node_root = prefix / 'node'
    node_root.mkdir()
    (node_root / 'package.json').write_text(json.dumps({
        'name': 'tr-development-tools', 'version': '0.0.0', 'private': True,
        'dependencies': {'ctx7': config['node']['ctx7'],
                         '@playwright/cli': config['node']['playwright_cli']},
    }, indent=2) + '\n')
    run(npm, 'install', '--prefix', node_root, '--ignore-scripts', '--no-audit', '--no-fund')
    engine = json.loads((node_root / 'node_modules/playwright/package.json').read_text())['version']
    if engine != config['node']['playwright_engine']:
        raise ValueError(f'Playwright engine drift: {engine}')
    python_root = prefix / 'python'
    run(uv, 'venv', '--python', sys.executable, python_root)
    python = python_root / 'bin/python'
    run(uv, 'pip', 'install', '--python', python,
        f"semgrep=={config['python']['semgrep']}", f"playwright=={config['python']['playwright']}")
    frozen = subprocess.check_output([str(uv), 'pip', 'freeze', '--python', str(python)],
                                     env=env, text=True)
    (prefix / 'python-freeze.txt').write_text(frozen)
    run(python, '-m', 'playwright', 'install', 'chromium')
    browser = subprocess.check_output([str(python), '-c',
        'from playwright.sync_api import sync_playwright; '
        'p=sync_playwright().start(); print(p.chromium.executable_path); p.stop()'],
        env=env, text=True).strip()
    # Both engines use the explicitly provisioned Chromium, not user profiles.
    (prefix / 'playwright.json').write_text(json.dumps({'browser': {
        'browserName': 'chromium', 'launchOptions': {'executablePath': browser, 'headless': True},
    }}, indent=2) + '\n')
    trivy_version = config['trivy']['version']
    url = (f'https://github.com/aquasecurity/trivy/releases/download/v{trivy_version}/'
           f'trivy_{trivy_version}_Linux-64bit.tar.gz')
    with urllib.request.urlopen(url, timeout=120) as response:
        archive = response.read()
    if hashlib.sha256(archive).hexdigest() != config['trivy']['linux_x86_64_sha256']:
        raise ValueError('Trivy checksum mismatch')
    bindir = prefix / 'bin'
    bindir.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
        member = tar.getmember('trivy')
        if not member.isfile():
            raise ValueError('Trivy archive entry must be a regular file')
        with tar.extractfile(member) as source:
            (bindir / 'trivy').write_bytes(source.read())
    (bindir / 'trivy').chmod(0o755)
    for name, source in {'ctx7': node_root / 'node_modules/.bin/ctx7',
                         'playwright-cli': node_root / 'node_modules/.bin/playwright-cli',
                         'semgrep': python_root / 'bin/semgrep'}.items():
        (bindir / name).symlink_to(source)
    shutil.copy2(manifest, prefix / 'dev-tools.toml')
    write_environment(prefix)
    (prefix / 'provisioned.json').write_text(json.dumps({
        'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
        'node': version, 'browser': browser, 'playwright_engine': engine,
        'scope': 'isolated toolchain; no host registration, authentication or scan',
    }, indent=2) + '\n')
    print(json.dumps({'prefix': str(prefix), 'bin': str(bindir),
                      'browser_config': str(prefix / 'playwright.json')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', type=Path, required=True)
    parser.add_argument('--manifest', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'common/base/scripts/dev-tools.toml')
    parser.add_argument('--uv', default=shutil.which('uv'))
    args = parser.parse_args()
    try:
        provision(args.prefix.expanduser().resolve(), args.manifest.resolve(), args.uv)
    except (OSError, ValueError, subprocess.CalledProcessError, tarfile.TarError) as error:
        parser.exit(1, f'provision failed (partial prefix retained for diagnosis): {error}\n')
