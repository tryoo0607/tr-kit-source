#!/usr/bin/env python3
"""codex event adapter. No activation, installation, tool execution or logging."""
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
    response = {'decision': 'block', 'reason': text}
    if result['status'] == 'error':
        response.update({'continue': False, 'stopReason': 'tr-kit: secret inspection failed; stopped.'})
    return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--event', choices=['PreToolUse', 'PostToolUse'], required=True)
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
        if args.event != 'PreToolUse':
            response.update({'decision':'block','reason':'tr-kit: output inspection failed; result blocked.'})
    print(json.dumps(response, ensure_ascii=False))


if __name__ == '__main__':
    main()
