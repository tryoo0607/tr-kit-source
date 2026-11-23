#!/usr/bin/env python3
"""Codex adapter; Pre predicts supported patches, Post inspects current files."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'common/base/scripts'))
from upstream_guard import (Result, Unavailable, absolute, bounded_read,
                            combine, within, adapter_main, READ_ONLY_TOOLS, unlink_target)


def inspect_patch(guard, command, cwd):
    if not isinstance(command, str):
        raise Unavailable('patch text missing')
    separators = '\r\v\f\x1c\x1d\x1e\x85\u2028\u2029'
    if any(ch in command for ch in separators):
        raise Unavailable('patch line separator is not supported')
    lines = command.splitlines()
    if not lines or lines[0] != '*** Begin Patch' or lines[-1] != '*** End Patch':
        raise Unavailable('unsupported patch envelope')
    results, i = [], 1
    seen_paths, seen_inodes = {}, {}

    def claim(path):
        target = absolute(path, cwd)
        if target in seen_paths:
            raise Unavailable('repeated or conflicting patch path')
        seen_paths[target] = True
        if target.exists():
            info = target.stat()
            inode = (info.st_dev, info.st_ino)
            if inode in seen_inodes:
                raise Unavailable('patch paths alias the same inode')
            seen_inodes[inode] = True
        return target
    while i < len(lines) - 1:
        header = lines[i]
        if header.startswith('*** Add File: '):
            path = header[len('*** Add File: '):]
            claim(path)
            i += 1
            body = []
            while i < len(lines) - 1 and not lines[i].startswith('*** '):
                if not lines[i].startswith('+'):
                    raise Unavailable('invalid add-file patch')
                body.append(lines[i][1:]); i += 1
            results.append(guard.write(path, ('\n'.join(body) + '\n').encode(), cwd))
        elif header.startswith('*** Delete File: '):
            path = header[len('*** Delete File: '):]
            claim(path)
            target = unlink_target(path, cwd)
            if not within(target, guard.root) and any(target == Path(e['path']) for e in guard.load()):
                results.append(Result('block', 'registered official source deletion forbidden'))
                i += 1
                continue
            # Removing a file cannot bundle it. Deletion authorization is a separate guard.
            results.append(Result('not_applicable', 'deletion is not a content inclusion'))
            i += 1
        elif header.startswith('*** Update File: '):
            path = header[len('*** Update File: '):]
            target = claim(path)
            if guard.original_target(target):
                return Result('block', 'registered official source modification forbidden')
            i += 1
            move = None
            if i < len(lines) and lines[i].startswith('*** Move to: '):
                move = lines[i][len('*** Move to: '):]; i += 1
                move_target = claim(move)
                if guard.original_target(move_target):
                    return Result('block', 'registered official source move destination forbidden')
            relevant = guard.covers(target) or (move and guard.covers(absolute(move, cwd)))
            if not relevant:
                while i < len(lines) - 1 and not lines[i].startswith('*** '):
                    i += 1
                outside = [guard.outside_result(target)]
                if move:
                    outside.append(guard.outside_result(move_target))
                results.append(combine(outside))
                continue
            old_text = bounded_read(target).decode('utf-8')
            if any(ch in old_text for ch in separators) or (old_text and not old_text.endswith('\n')):
                raise Unavailable('existing patch target byte endings are not supported')
            old_lines = old_text.splitlines()
            cursor, output = 0, []
            while i < len(lines) - 1 and not lines[i].startswith('*** '):
                if not lines[i].startswith('@@'):
                    raise Unavailable('expected patch hunk')
                # Context labels may aid the native patcher but must not silently
                # select a different match in this predictor.
                if lines[i] != '@@':
                    raise Unavailable('labelled patch hunks need review')
                i += 1
                old, new = [], []
                while i < len(lines) - 1 and not lines[i].startswith(('@@', '*** ')):
                    line = lines[i]
                    if not line or line[0] not in ' +-':
                        raise Unavailable('unsupported patch hunk line')
                    if line[0] in ' -': old.append(line[1:])
                    if line[0] in ' +': new.append(line[1:])
                    i += 1
                if not old:
                    raise Unavailable('unanchored insertion is not predicted')
                matches = [j for j in range(cursor, len(old_lines) - len(old) + 1)
                           if old_lines[j:j + len(old)] == old]
                if len(matches) != 1:
                    raise Unavailable('patch hunk is absent or ambiguous')
                j = matches[0]
                output += old_lines[cursor:j] + new
                cursor = j + len(old)
            output += old_lines[cursor:]
            results.append(guard.write(move or path, ('\n'.join(output) + '\n').encode(), cwd))
        else:
            raise Unavailable('unsupported patch operation')
    return combine(results)


def evaluate(guard, payload):
    from upstream_guard import STRUCTURED_FILE_TOOLS, structured_file
    data = payload.get('tool_input')
    tool = payload.get('tool_name')
    if tool in READ_ONLY_TOOLS:
        return Result('not_applicable', 'read-only contract; other security checks still apply')
    if tool not in ('apply_patch', 'Bash', 'exec_command') + STRUCTURED_FILE_TOOLS:
        return Result('deferred', 'tool effect not pre-inspected')
    if not isinstance(data, dict):
        if tool in ('Bash', 'exec_command'):
            return Result('deferred', 'command effect not pre-inspected')
        raise Unavailable('tool input must be an object')
    cwd_value = payload.get('tool_cwd') or data.get('workdir') or payload['cwd']
    if not isinstance(cwd_value, str) or not Path(cwd_value).is_absolute():
        raise Unavailable('absolute tool cwd required')
    cwd = Path(cwd_value).resolve()
    if tool in STRUCTURED_FILE_TOOLS:
        return structured_file(guard, tool, data, cwd)
    if tool == 'apply_patch':
        return inspect_patch(guard, data.get('command'), cwd)
    if tool in ('Bash', 'exec_command'):
        return guard.shell(data.get('command', data.get('cmd')), cwd)


if __name__ == '__main__':
    adapter_main(evaluate)
