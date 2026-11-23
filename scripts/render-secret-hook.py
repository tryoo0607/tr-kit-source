#!/usr/bin/env python3
"""Render inactive secret hooks; never write product settings."""
import argparse
import json
import shlex
from pathlib import Path

RESULT_MATCHER = 'Bash|exec_command|write_stdin|Read|read_file|Write|Edit|MultiEdit|Glob|Grep|NotebookEdit|WebFetch|WebSearch|apply_patch|list_mcp_resources|list_mcp_resource_templates|read_mcp_resource|mcp__.*'


def render(product, root, python):
    if product not in ('codex','claude') or not root.is_absolute() or not python.is_absolute():
        raise ValueError('explicit product and absolute paths required')
    events=['PreToolUse','PostToolUse']+(['PostToolUseFailure'] if product=='claude' else [])
    doc=json.loads((root/f'adapters/{product}/hooks/secret-guard.json.in').read_text())
    if sorted(doc)!=['hooks'] or sorted(doc['hooks'])!=sorted(events):
        raise ValueError('invalid event registration')
    for event in events:
        groups=doc['hooks'][event]
        expected='.*' if event=='PreToolUse' else RESULT_MATCHER
        if not isinstance(groups,list) or len(groups)!=1 or sorted(groups[0])!=['hooks','matcher'] or groups[0]['matcher']!=expected:
            raise ValueError('invalid matcher')
        hooks=groups[0]['hooks']
        expected_handler={'type':'command','command':'@@COMMAND@@','timeout':45}
        if product=='claude' and event=='PreToolUse':expected_handler['onFailure']='block'
        if not isinstance(hooks,list) or len(hooks)!=1 or hooks[0]!=expected_handler:
            raise ValueError('invalid handler')
        hooks[0]['command']=shlex.join([str(python),'-B',str(root/f'adapters/{product}/scripts/secret_guard.py'),'--event',event])
    return doc


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--product',choices=['codex','claude'],required=True)
    p.add_argument('--source-root',type=Path,required=True);p.add_argument('--python',type=Path,required=True)
    a=p.parse_args();print(json.dumps(render(a.product,a.source_root,a.python),ensure_ascii=False))
