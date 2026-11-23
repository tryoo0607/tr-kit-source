#!/usr/bin/env python3
"""Local CI equivalent: tests with explicit pinned scanner, never delivery/push."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'common/base/scripts'))
from secret_guard import verify_scanner


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--gitleaks',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:
        scanner=verify_scanner(a.gitleaks)
        if not a.output.is_absolute() or a.output.exists() or a.output.resolve()!=a.output or not a.output.parent.is_dir():
            raise ValueError('new explicit CI evidence directory required')
        a.output.mkdir(mode=0o700)
        env=dict(os.environ);env['TR_GITLEAKS_TEST_BINARY']=str(scanner);env['TR_KIT_TEST_GITLEAKS']=str(scanner)
        with (a.output/'tests.log').open('xb') as stream:
            result=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_*.py','-v'],
                cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=stream,timeout=600)
        report={'status':'pass' if result.returncode==0 else 'failed','tests_exit_code':result.returncode,
                'scanner_identity':'verified','pushed':False,'native_registered':False,
                'limits':'Local test suite only. Inspect log for skips; no remote CI or product readiness certification.'}
        (a.output/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));return result.returncode
    except (OSError,ValueError,subprocess.SubprocessError):print('{"status":"unavailable","pushed":false}');return 2


if __name__=='__main__':raise SystemExit(main())
