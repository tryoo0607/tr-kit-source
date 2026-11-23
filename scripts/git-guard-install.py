#!/usr/bin/env python3
"""Plan/apply explicit Git enrollment, inspect status or restore owned changes."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'common/base/scripts'))
import git_guard_install as installer


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['plan','apply','status','rollback'])
    p.add_argument('--state',type=Path,required=True)
    p.add_argument('--repo',type=Path)
    p.add_argument('--gitleaks',type=Path)
    p.add_argument('--local-only',action='append',default=[])
    p.add_argument('--allow-artifact',action='append',default=[])
    p.add_argument('--expect-plan')
    a=p.parse_args()
    try:
        if a.action in ('status','rollback'):
            if any((a.repo,a.gitleaks,a.local_only,a.allow_artifact,a.expect_plan)):
                p.error('status/rollback accepts only --state')
            result=installer.status(a.state,a.action=='rollback')
        else:
            if not a.repo or not a.gitleaks:p.error('--repo and --gitleaks required')
            if a.action=='apply' and not a.expect_plan:p.error('apply requires the reviewed --expect-plan')
            report=installer.plan(a.repo,a.state,a.gitleaks,a.local_only,a.allow_artifact)
            result=installer.apply(report,a.expect_plan) if a.action=='apply' else installer.public(report)
        print(json.dumps(result,indent=2));return 0
    except (installer.InstallError,installer.guard.GuardError) as error:
        # Own messages contain fixed diagnoses, never raw scanner/Git output.
        print(json.dumps({'status':'unavailable','reason':str(error)}))
        return 2
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
        print(json.dumps({'status':'unavailable','reason':'enrollment inspection or conflict; no forced overwrite'}))
        return 2


if __name__=='__main__':raise SystemExit(main())
