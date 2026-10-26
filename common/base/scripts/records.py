#!/usr/bin/env python3
"""Run bundled upstream record tools without installing or enabling hooks."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tool', choices=['doctor', 'bmad-setup', 'bmad-render', 'wiki', 'wiki-session', 'mem-mcp', 'mem-worker'])
    raw = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(raw[:1])
    rest = raw[1:]
    if args.tool == 'doctor':
        files = ['skills/bmad/scripts/setup.py', 'skills/bmad-build/SKILL.md',
                 'scripts/llm-wiki', 'scripts/llm-wiki-session',
                 'runtimes/claude-mem/scripts/mcp-server.cjs', 'runtimes/claude-mem/scripts/worker-service.cjs']
        report = {'root': str(ROOT), 'executables': {k: shutil.which(k) for k in ['uv', 'bun', 'node']},
                  'missing_files': [p for p in files if not (ROOT / p).is_file()],
                  'hooks_enabled_by_launcher': False}
        print(json.dumps(report, indent=2))
        return int(bool(report['missing_files']) or any(not v for v in report['executables'].values()))
    if args.tool.startswith('bmad-'):
        uv = shutil.which('uv')
        if not uv:
            parser.error('uv is required by BMAD; install it before running setup/render')
        script = ROOT / 'skills/bmad/scripts' / ('setup.py' if args.tool == 'bmad-setup' else 'render_skill.py')
        command = [uv, 'run', '--no-cache', str(script), *rest]
        if args.tool == 'bmad-setup':
            command += ['--skill', str(ROOT / 'skills/bmad'), '--root', str(ROOT / 'skills')]
    elif args.tool in ['wiki', 'wiki-session']:
        command = [sys.executable, str(ROOT / 'scripts' / ('llm-wiki' if args.tool == 'wiki' else 'llm-wiki-session')), *rest]
    else:
        bun = shutil.which('bun')
        if not bun:
            parser.error('bun is required by the bundled Claude-Mem runtime')
        script = 'mcp-server.cjs' if args.tool == 'mem-mcp' else 'worker-service.cjs'
        command = [bun, str(ROOT / 'runtimes/claude-mem/scripts' / script), *rest]
    # Never start a worker merely by discovering MCP tools. Explicit mem-worker
    # is the only launcher operation that may start the upstream service.
    env = dict(os.environ)
    if args.tool == 'mem-mcp':
        env['CLAUDE_MEM_WORKER_AUTOSTART'] = 'false'
    return subprocess.call(command, env=env)


if __name__ == '__main__':
    raise SystemExit(main())
