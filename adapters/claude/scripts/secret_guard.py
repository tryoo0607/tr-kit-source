#!/usr/bin/env python3
"""claude event adapter. No activation, installation, tool execution or logging."""
import argparse
import json
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'common/base/scripts'))
import secret_guard as core


def input_response(payload):
    reason = core.inspect_input(payload)
    return {} if reason is None else {'hookSpecificOutput': {'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny', 'permissionDecisionReason': reason}}


def output_response(payload):
    result = core.inspect_output(payload)
    if result['status'] == 'clean':
        return {}
    if result['status'] == 'unsupported':
        return {'continue': False, 'stopReason': 'tr-kit: tool output protection unsupported; stopped.'}
    text = core.notice(result)
    if payload.get('hook_event_name') == 'PostToolUseFailure':
        return {'continue': False, 'stopReason': text + ' Failure replacement unsupported; effects were not undone.'}
    tool = payload.get('tool_name')
    original = payload.get('tool_response')
    if tool == 'Bash':
        replacement = {'stdout': text, 'stderr': '', 'interrupted': False, 'isImage': False}
    elif tool == 'Read' and isinstance(original, dict) and original.get('type') == 'text' and isinstance(original.get('file'), dict):
        replacement = {'type':'text','file':{'filePath':'[withheld]','content':text,'numLines':1,'startLine':1,'totalLines':1}}
    elif isinstance(tool, str) and tool.startswith('mcp__'):
        replacement = text
    else:
        return {'continue':False,'stopReason':'tr-kit: result replacement unsupported; stopped.'}
    response = {'hookSpecificOutput': {'hookEventName':'PostToolUse','updatedToolOutput':replacement}}
    if result['status'] == 'error':
        response.update({'continue': False, 'stopReason': 'tr-kit: secret inspection failed; stopped.'})
    return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--event', choices=['PreToolUse', 'PostToolUse', 'PostToolUseFailure'], required=True)
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(core.MAX_NATIVE_BYTES + 1)
        if len(raw) > core.MAX_NATIVE_BYTES:
            raise ValueError('input too large')
        payload = json.loads(raw)
        if not isinstance(payload, dict) or payload.get('hook_event_name') != args.event:
            raise ValueError('event mismatch')
        response = input_response(payload) if args.event == 'PreToolUse' else output_response(payload)
    except Exception:
        response = ({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision':'deny',
            'permissionDecisionReason':'tr-kit: input inspection failed; operation blocked'}}
            if args.event == 'PreToolUse' else
            {'continue':False,'stopReason':'tr-kit: output inspection failed; stopped.'})
        pass
    print(json.dumps(response, ensure_ascii=False))


if __name__ == '__main__':
    main()
