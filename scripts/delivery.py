#!/usr/bin/env python3
"""Fresh local release check only. No commit, remote access or push capability."""
import argparse
import json
from pathlib import Path
from package import verify
from assemble import inspect


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path,required=True)
    p.add_argument('--product',choices=['codex','claude'],required=True);p.add_argument('--expect-sha256',required=True)
    for name in ('root','catalog','scope'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    try:
        value=verify(a.package,a.product)
        check=inspect(a.root,a.catalog,a.scope,'transfer')
        from upstream_guard import Scope
        if a.package not in Scope(a.root,a.scope).artifacts or not check['complete'] or check['status']!='pass':
            raise ValueError('fresh original transfer inspection unavailable')
        if value['package_sha256']!=a.expect_sha256:raise ValueError('release changed since review')
        print(json.dumps({'status':'pass','package_sha256':value['package_sha256'],'pushed':False,'operational_ready':False}));return 0
    except (OSError,ValueError,KeyError,TypeError):print('{"status":"unavailable","pushed":false}');return 2


if __name__=='__main__':raise SystemExit(main())
