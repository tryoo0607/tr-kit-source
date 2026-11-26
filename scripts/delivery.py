#!/usr/bin/env python3
"""Fresh local release check only. No commit, remote access or push capability."""
import argparse
import json
from pathlib import Path
from package import verified_package
from assemble import inspect, output_bytes


def export(package, output, files):
    """Write only the verified marketplace tree to a new directory."""
    if not output.is_absolute() or output.parent.resolve(strict=True) != output.parent:
        raise ValueError('canonical export destination required')
    if output == package or package in output.parents:
        raise ValueError('export must be outside the verification package')
    output.mkdir(mode=0o700)
    for path, data in files.items():
        if path == 'assembly.json':
            continue
        target = output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path,required=True)
    p.add_argument('--product',choices=['codex','claude'],required=True);p.add_argument('--expect-sha256',required=True)
    p.add_argument('--output',type=Path,help='new directory for the installable marketplace tree')
    for name in ('root','catalog','scope'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    try:
        value,files=verified_package(a.package,a.product)
        check=inspect(a.root,a.catalog,a.scope,'transfer')
        from upstream_guard import Scope
        if a.package not in Scope(a.root,a.scope).artifacts or not check['complete'] or check['status']!='pass':
            raise ValueError('fresh original transfer inspection unavailable')
        if value['package_sha256']!=a.expect_sha256:raise ValueError('release changed since review')
        if a.output is not None:
            output_bytes(a.package, files)
            export(a.package, a.output, files)
        print(json.dumps({'status':'pass','package_sha256':value['package_sha256'],'pushed':False,'operational_ready':False}));return 0
    except (OSError,ValueError,KeyError,TypeError):print('{"status":"unavailable","pushed":false}');return 2


if __name__=='__main__':raise SystemExit(main())
