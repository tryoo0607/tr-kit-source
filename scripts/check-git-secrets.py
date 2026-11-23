#!/usr/bin/env python3
"""Explicit Git checks, no installation or transmission."""
import argparse
import json
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'common/base/scripts'))
import secret_guard as core


def main():
    p=argparse.ArgumentParser()
    p.add_argument('mode', choices=['index','push'])
    p.add_argument('--repo', required=True, type=Path)
    p.add_argument('--policy', required=True, type=Path)
    args=p.parse_args()
    try:
        if args.mode=='index':core.check_index(args.repo,args.policy)
        else:core.check_push(args.repo,args.policy,sys.stdin.read())
    except Exception as error:
        finding=isinstance(error,core.GuardError) and str(error).startswith('secret detected')
        print(json.dumps({'status':('finding' if finding else 'policy_violation'
                          if isinstance(error,core.PolicyViolation) else 'unavailable'),
                          'diagnostic':error.diagnostic if finding else {}}))
        return 2
    print(json.dumps({'status':'pass'}));return 0


if __name__=='__main__':raise SystemExit(main())
