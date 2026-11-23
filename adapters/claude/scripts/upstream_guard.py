#!/usr/bin/env python3
"""Claude Pre/Post adapter with explicit scope; no registration side effect."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'common/base/scripts'))
from upstream_guard import (Result, Unavailable, adapter_main, READ_ONLY_TOOLS,
                            STRUCTURED_FILE_TOOLS, structured_file)


def evaluate(guard, payload):
    cwd = Path(payload['cwd']).resolve()
    data = payload.get('tool_input')
    tool = payload.get('tool_name')
    if tool in READ_ONLY_TOOLS:
        return Result('not_applicable', 'read-only contract; other security checks still apply')
    if tool in STRUCTURED_FILE_TOOLS:
        return structured_file(guard, tool, data, cwd)
    if tool not in ('Write', 'Edit', 'Bash'):
        return Result('deferred', 'tool effect not pre-inspected')
    if not isinstance(data, dict):
        if tool == 'Bash':
            return Result('deferred', 'command effect not pre-inspected')
        raise Unavailable('tool input must be an object')
    if tool == 'Bash':
        return guard.shell(data.get('command'), cwd)


if __name__ == '__main__':
    adapter_main(evaluate)
