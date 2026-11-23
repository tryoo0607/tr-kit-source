#!/usr/bin/env python3
"""Render inactive hook JSON to stdout. Never installs, trusts or activates it."""
import argparse
import json
import shlex
import sys
from pathlib import Path


def render(product, source_root, protected_root, catalog, scope):
    if product not in ('codex', 'claude'):
        raise ValueError('unsupported product')
    values = [source_root, protected_root, catalog, scope]
    if any(not isinstance(p, Path) or not p.is_absolute() or '\x00' in str(p) for p in values):
        raise ValueError('absolute paths required')
    source_root, protected_root, catalog, scope = [p.resolve(strict=False) for p in values]
    template = source_root / f'adapters/{product}/hooks/upstream-guard.json.in'
    doc = json.loads(template.read_text())
    events = {'PreToolUse': '@@PRE_COMMAND@@', 'PostToolUse': '@@POST_COMMAND@@'}
    if product == 'claude': events['PostToolUseFailure'] = '@@FAILURE_COMMAND@@'
    if sorted(doc['hooks']) != sorted(events):
        raise ValueError('unexpected extra event')
    for event, placeholder in events.items():
        groups = doc['hooks'][event]
        matcher = ('Bash|exec_command|apply_patch|Write|Edit|MultiEdit|NotebookEdit' if product == 'codex'
                   else 'Bash|Write|Edit|MultiEdit|NotebookEdit') if event == 'PreToolUse' else '.*'
        if len(groups) != 1 or groups[0]['matcher'] != matcher or len(groups[0]['hooks']) != 1:
            raise ValueError('unexpected template scope')
        handler = groups[0]['hooks'][0]
        expected = ['command', 'timeout', 'type'] + (['onFailure'] if product == 'claude' and event == 'PreToolUse' else [])
        if sorted(groups[0]) != ['hooks', 'matcher'] or sorted(handler) != sorted(expected):
            raise ValueError('unexpected template field')
        if handler['type'] != 'command' or handler['timeout'] != 8 or handler['command'] != placeholder:
            raise ValueError('unexpected template handler')
        if product == 'claude' and event == 'PreToolUse' and handler.get('onFailure') != 'block':
            raise ValueError('missing product failure contract')
        handler['command'] = shlex.join(['/bin/sh', str(source_root/'common/base/scripts/run_upstream_guard.sh'),
                                         product, str(protected_root), str(catalog), str(scope), event])
    return doc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--product', choices=['codex', 'claude'], required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--scope', type=Path, required=True)
    args = parser.parse_args()
    try:
        doc = render(args.product, Path(__file__).resolve().parents[1], args.root, args.catalog, args.scope)
    except Exception:
        print('hook rendering failed; nothing installed', file=sys.stderr)
        return 2
    print(json.dumps(doc, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
