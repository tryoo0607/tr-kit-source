#!/usr/bin/env python3
"""Inspect one explicit expanded payload with the existing pinned secret scanner."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'common/base/scripts'))
import secret_guard as secrets
from upstream_artifacts import _opaque_container

MAX_NODES=4096
MAX_BYTES=16*1024*1024


def signature(info):
    return (info.st_dev,info.st_ino,info.st_mode,info.st_size,info.st_mtime_ns,info.st_ctime_ns)


def snapshot(root):
    root=Path(root).absolute()
    if any(p.is_symlink() for p in (root,*root.parents)) or not root.is_dir():
        raise ValueError('explicit non-reference directory required')
    records={};blobs=[];total=0
    def visit(path):
        nonlocal total
        if len(records)>=MAX_NODES:raise ValueError('payload node limit exceeded')
        before=path.lstat();mode=before.st_mode
        name=str(path.relative_to(root))
        if stat.S_ISDIR(mode):
            records[name]=('directory',signature(before))
            children=[]
            with os.scandir(path) as entries:
                for entry in entries:
                    if len(records)+len(children)>=MAX_NODES:raise ValueError('payload node limit exceeded')
                    children.append(Path(entry.path))
            for child in sorted(children):visit(child)
        elif stat.S_ISREG(mode):
            if before.st_size>MAX_BYTES:raise ValueError('payload byte limit exceeded')
            flags=os.O_RDONLY|os.O_NONBLOCK|getattr(os,'O_NOFOLLOW',0)
            fd=os.open(path,flags)
            with os.fdopen(fd,'rb') as stream:
                opened=os.fstat(stream.fileno())
                if not stat.S_ISREG(opened.st_mode) or signature(opened)!=signature(before):
                    raise ValueError('payload identity changed')
                data=stream.read(MAX_BYTES+1)
                if signature(os.fstat(stream.fileno()))!=signature(before):raise ValueError('payload changed')
            total+=len(data)
            if total>MAX_BYTES:raise ValueError('payload byte limit exceeded')
            if _opaque_container(data):raise ValueError('expanded payload required')
            records[name]=('file',signature(before),hashlib.sha256(data).hexdigest())
            blobs.append((name,data))
        else:raise ValueError('payload reference or special node refused')
        if signature(path.lstat())!=signature(before):raise ValueError('payload changed')
    visit(root)
    if not blobs:raise ValueError('empty payload not certified')
    # File names are part of the transmitted payload, too. Do not exempt names
    # that contain secrets, and never print them in a finding report.
    names=json.dumps([name for name,_ in blobs],ensure_ascii=False).encode()
    if len(names)>MAX_BYTES:raise ValueError('payload name limit exceeded')
    return records,blobs+[('payload-paths',names)]


class InspectionUnavailable(ValueError):
    def __init__(self,stage,error):
        import subprocess
        self.stage=stage
        self.kind=('permission' if isinstance(error,PermissionError) else
                   'missing-file' if isinstance(error,FileNotFoundError) else
                   'timeout' if isinstance(error,subprocess.TimeoutExpired) else
                   'io' if isinstance(error,OSError) else
                   'scanner' if isinstance(error,secrets.GuardError) else
                   'changed-or-unsupported')
        super().__init__('artifact inspection unavailable')


def check(root):
    stage='inventory'
    try:
        before,blobs=snapshot(root)
        stage='scanner-identity'
        scanner=secrets.trusted_scanner()
        stage='scanner'
        secrets.scan(blobs,scanner)
        stage='recheck'
        after,_=snapshot(root)
        if after!=before:raise ValueError('payload changed while scanning')
    except Exception as error:
        if isinstance(error,secrets.GuardError) and str(error).startswith('secret detected'):raise
        raise InspectionUnavailable(stage,error) from None
    fingerprint=hashlib.sha256(json.dumps({name:record[2] for name,record in before.items()
                        if record[0]=='file'},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {'status':'pass','files':len(blobs)-1,'fingerprint':fingerprint,
            'limits':'Observed expanded files only; not approval to publish, an atomic lock, or complete binary/encoded-secret detection.'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args(argv)
    try:result=check(args.root)
    except Exception as error:
        finding=isinstance(error,secrets.GuardError) and str(error).startswith('secret detected')
        result={'status':'finding' if finding else 'unavailable',
                'diagnostic':getattr(error,'diagnostic',{}) if finding else
                    {'stage':error.stage,'kind':error.kind} if isinstance(error,InspectionUnavailable) else {}}
        print(json.dumps(result));return 2
    print(json.dumps(result));return 0


if __name__=='__main__':raise SystemExit(main())
