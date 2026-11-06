#!/usr/bin/env python3
"""Provision only pinned Gitleaks into a NEW isolated prefix; never activate hooks."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import platform
import subprocess
import tarfile
import tomllib
import urllib.request


def provision(prefix, manifest):
    if platform.system() != 'Linux' or platform.machine() not in {'x86_64', 'amd64'}:
        raise ValueError('only Linux x86_64 is supported')
    if prefix.exists():
        raise ValueError('use a new prefix; existing files are never overwritten')
    config = tomllib.loads(manifest.read_text())['gitleaks']
    version = config['version']
    url = f'https://github.com/gitleaks/gitleaks/releases/download/v{version}/gitleaks_{version}_linux_x64.tar.gz'
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != config['linux_x64_sha256']:
        raise ValueError('Gitleaks checksum mismatch; nothing installed')
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        member = archive.getmember('gitleaks')
        if not member.isfile():
            raise ValueError('expected a regular executable archive member')
        binary = archive.extractfile(member).read()
    prefix.mkdir(parents=True, mode=0o700)
    bindir = prefix / 'bin'
    bindir.mkdir()
    executable = bindir / 'gitleaks'
    executable.write_bytes(binary)
    executable.chmod(0o755)
    observed = subprocess.check_output([str(executable), 'version'], text=True).strip()
    if observed.lstrip('v') != version:
        raise ValueError('installed scanner version mismatch')
    receipt = {'version': observed, 'url': url, 'archive_sha256': hashlib.sha256(data).hexdigest(),
               'binary_sha256': hashlib.sha256(binary).hexdigest(), 'scope': 'Gitleaks only; no enrollment or host activation'}
    (prefix / 'provisioned.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt | {'executable': str(executable)}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prefix', type=Path, required=True)
    p.add_argument('--manifest', type=Path, default=Path(__file__).resolve().parents[1] / 'common/base/scripts/dev-tools.toml')
    args = p.parse_args()
    try:
        print(json.dumps(provision(args.prefix.expanduser().resolve(), args.manifest.resolve()), indent=2))
    except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as error:
        p.exit(2, 'Gitleaks setup failed: ' + str(error) + '\n')
