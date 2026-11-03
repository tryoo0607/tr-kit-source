#!/usr/bin/env python3
"""Classify two sanitized file snapshots with Git, without exposing their content."""

import argparse
import json
import os
from pathlib import Path
import stat
import subprocess


def signature(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('not_regular_file')
    # Open both inputs before invoking Git so an unreadable input is unknown.
    with path.open('rb'):
        pass
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, info.st_mode)


def compare(expected, observed):
    try:
        before = (signature(expected), signature(observed))
        if before[0][:2] == before[1][:2]:
            return 'unknown', 'same_input', 2
    except (OSError, ValueError):
        return 'unknown', 'input_unavailable_or_not_regular', 2
    environment = os.environ.copy()
    environment.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                       GIT_ATTR_NOSYSTEM='1', GIT_TERMINAL_PROMPT='0')
    try:
        result = subprocess.run(
            ['git', '--no-pager', 'diff', '--no-index', '--quiet',
             '--no-ext-diff', '--no-textconv', '--no-renames', '--',
             str(expected.absolute()), str(observed.absolute())],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=environment, timeout=10, check=False)
        if before != (signature(expected), signature(observed)):
            return 'unknown', 'inputs_changed', 2
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return 'unknown', 'comparison_unavailable', 2
    if result.returncode == 0:
        return 'match', 'same_snapshot_content', 0
    if result.returncode == 1:
        return 'drift', 'different_snapshot_content', 1
    return 'unknown', 'comparison_failed', 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('expected', type=Path)
    parser.add_argument('observed', type=Path)
    args = parser.parse_args()
    status, reason, code = compare(args.expected, args.observed)
    print(json.dumps({'scope': 'file_snapshot', 'status': status,
                      'reason': reason, 'live_verified': False}))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
