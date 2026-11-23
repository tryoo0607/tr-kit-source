#!/usr/bin/env python3
"""Print an inactive Git hook. Existing hook ownership/chaining is not changed."""
import argparse
import shlex
from pathlib import Path


def render(mode, source_root, repo, policy, python):
    if mode not in ('index','push') or any(not p.is_absolute() for p in (source_root,repo,policy,python)):
        raise ValueError('explicit mode and absolute paths required')
    command=[str(python),'-B',str(source_root/'scripts/check-git-secrets.py'),mode,
             '--repo',str(repo),'--policy',str(policy)]
    return '#!/bin/sh\nexec '+shlex.join(command)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--mode',choices=['index','push'],required=True)
    for key in ('source-root','repo','policy','python'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();print(render(a.mode,a.source_root,a.repo,a.policy,a.python),end='')
