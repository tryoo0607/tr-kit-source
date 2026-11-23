"""Own plugin context and explicit upstream-guard binding, never a trust manager."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def root_path():return Path(__file__).resolve().parents[3]


def context(root, payload):
    if not isinstance(payload,dict) or payload.get('hook_event_name')!='SessionStart':raise ValueError('SessionStart required')
    path=root/'common/base/instructions.md'
    if path.is_symlink() or not path.is_file():raise ValueError('own instructions unavailable')
    text=path.read_text()
    prefix=f'tr-kit plugin root: {root}\n이 지침의 상대 경로 기준은 위 plugin root다. 작업 흐름: {root}/workflow.md\n'
    return {'hookSpecificOutput':{'hookEventName':'SessionStart','additionalContext':prefix+text}}


def upstream(root, product, event, payload):
    selected=os.environ.get('TR_KIT_UPSTREAM_BINDING')
    if selected is None:
        from runtime_config import load
        _, data=load(product)
        selected=data['upstream_binding']
    binding=Path(selected)
    if not binding.is_absolute() or binding.resolve()!=binding or binding.is_symlink():raise ValueError('explicit local upstream binding required')
    doc=json.loads(binding.read_bytes())
    if not isinstance(doc,dict) or set(doc)!= {'root','catalog','scope'}:raise ValueError('unsupported upstream binding')
    paths=[Path(doc[k]) for k in ('root','catalog','scope')]
    if any(not p.is_absolute() or p.resolve()!=p or p.is_symlink() for p in paths):raise ValueError('canonical guard paths required')
    # Existing wrapper owns timeout, native response validation and guard logic.
    return subprocess.run(['/bin/sh',str(root/'common/base/scripts/run_upstream_guard.sh'),product,
                           *map(str,paths),event],input=payload,capture_output=True,timeout=8)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['context','upstream']);p.add_argument('--product',choices=['codex','claude'],required=True)
    p.add_argument('--event');a=p.parse_args()
    try:
        raw=sys.stdin.buffer.read(1_048_577)
        if len(raw)>1_048_576:raise ValueError('hook input too large')
        payload=json.loads(raw)
        if not isinstance(payload,dict):raise ValueError('native object payload required')
        if a.action=='context':
            from runtime_config import load,note
            selected,data=load(a.product)
            result=context(root_path(),payload)
            result['hookSpecificOutput']['additionalContext']+=note(selected,data)
        else:
            if a.event not in ('PreToolUse','PostToolUse','PostToolUseFailure') or payload.get('hook_event_name')!=a.event:
                raise ValueError('hook event mismatch')
            r=upstream(root_path(),a.product,a.event,raw)
            if r.returncode:raise ValueError('upstream guard unavailable')
            result=json.loads(r.stdout)
        print(json.dumps(result,ensure_ascii=False));return 0
    except (OSError,ValueError,TypeError,KeyError,subprocess.SubprocessError):
        if a.action=='upstream' and a.event=='PreToolUse':
            result={'hookSpecificOutput':{'hookEventName':'PreToolUse','permissionDecision':'deny',
                                         'permissionDecisionReason':'tr-kit upstream guard binding/execution unavailable'}}
        else:result={'continue':False,'stopReason':'tr-kit plugin context/guard unavailable; not ready'}
        print(json.dumps(result));return 0


if __name__=='__main__':raise SystemExit(main())
