#!/usr/bin/env python3
"""Exercise packaged upstream tools in an isolated project without model calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plugin', type=Path, required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    args = parser.parse_args()
    plugin = args.plugin.resolve()
    root = Path(tempfile.mkdtemp(prefix='tr-records-proof-'))
    project = root / 'project'
    project.mkdir()
    toolchain = args.toolchain.resolve()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = dict(os.environ)
    env.update(PATH=str(toolchain / 'uv-x86_64-unknown-linux-gnu') + os.pathsep +
               str(toolchain / 'node_modules/@oven/bun-linux-x64/bin') + os.pathsep + env['PATH'],
               UV_CACHE_DIR=str(root / 'uv-cache'), UV_PYTHON_DOWNLOADS='never',
               CLAUDE_MEM_DATA_DIR=str(root / 'memory'), CLAUDE_CONFIG_DIR=str(root / 'claude-config'),
               CLAUDE_MEM_WORKER_PORT=str(port), CLAUDE_MEM_WORKER_HOST='127.0.0.1',
               CLAUDE_MEM_CHROMA_ENABLED='false', CLAUDE_MEM_ONLINE_OPTIN='false',
               CLAUDE_MEM_CLOUD_SYNC_HUB_URL='', CLAUDE_MEM_CLOUD_SYNC_TOKEN='')
    launcher = [sys.executable, str(plugin / 'scripts/records.py')]
    checks = []

    def run(*parts):
        result = subprocess.run([*launcher, *parts], env=env, cwd=project,
                                capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise RuntimeError(f'{parts[0]} failed: {result.stderr[-1500:]}')
        return result.stdout.strip()

    worker = mcp = None
    worker_log = (root / 'worker.log').open('w')
    mcp_log = (root / 'mcp.log').open('w')
    try:
        run('doctor')
        checks.append('bundled files and runtime prerequisites')
        setup = json.loads(run('bmad-setup', '--project-root', str(project)))
        assert setup['status'] == 'created', setup
        workflow = run('bmad-render', '--project-root', str(project), '--skill', str(plugin / 'skills/bmad-build'))
        assert 'READY FOR DEVELOPMENT' in workflow
        checks.append('BMAD upstream setup and immutable workflow rendering')

        worker = subprocess.Popen([*launcher, 'mem-worker', '--daemon'], env=env, cwd=project,
                                  stdout=worker_log, stderr=worker_log, start_new_session=True)
        deadline = time.monotonic() + 30
        health = None
        while time.monotonic() < deadline:
            if worker.poll() is not None:
                raise RuntimeError('worker exited; see worker.log')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health', timeout=1) as response:
                    health = json.load(response)
                if health.get('initialized'):
                    break
            except (OSError, ValueError):
                pass
            time.sleep(.2)
        else:
            raise RuntimeError('worker readiness timed out; see worker.log')
        checks.append('isolated Claude-Mem worker and SQLite initialization')
        connection = json.loads((plugin / '.mcp.json').read_text())['mcpServers']['claude-mem']
        arguments = [part.replace('${PLUGIN_ROOT}', str(plugin)).replace('${CLAUDE_PLUGIN_ROOT}', str(plugin))
                     for part in connection['args']]
        assert not any('${' in part for part in arguments)
        mcp_env = dict(env, **connection.get('env', {}))
        mcp = subprocess.Popen([connection['command'], *arguments], env=mcp_env, cwd=project, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=mcp_log, text=True, start_new_session=True)
        messages = queue.Queue()

        def read_messages():
            for line in mcp.stdout:
                try:
                    messages.put(json.loads(line))
                except ValueError:
                    pass
        threading.Thread(target=read_messages, daemon=True).start()
        request_id = 0

        def rpc(method, params):
            nonlocal request_id
            request_id += 1
            mcp.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params}) + '\n')
            mcp.stdin.flush()
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                try:
                    reply = messages.get(timeout=max(.1, deadline - time.monotonic()))
                except queue.Empty:
                    break
                if reply.get('id') == request_id:
                    if 'error' in reply:
                        raise RuntimeError(str(reply['error']))
                    return reply['result']
            raise RuntimeError(f'MCP {method} timeout; see mcp.log')

        rpc('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {}, 'clientInfo': {'name': 'records-proof', 'version': '1'}})
        names = {tool['name'] for tool in rpc('tools/list', {})['tools']}
        assert {'save_memory', 'search', 'get_observations'} <= names, names

        def call(name, arguments):
            result = rpc('tools/call', {'name': name, 'arguments': arguments})
            if result.get('isError'):
                raise RuntimeError(json.dumps(result))
            return '\n'.join(c.get('text', '') for c in result.get('content', []))

        note = 'Synthetic proof: requirements preserved; concurrency verification is still pending.'
        fingerprint = hashlib.sha256(note.encode()).hexdigest()
        payload = {'text': note, 'title': 'Synthetic continuity proof', 'project': 'records-proof',
                   'metadata': {'sourceFingerprint': fingerprint, 'source': 'synthetic BMAD evidence'}}
        saved = call('save_memory', payload)
        repeated = call('save_memory', payload)
        match = re.search(r'#(\d+)', saved)
        assert match, saved
        observation_id = int(match[1])
        assert f'#{observation_id}' in repeated and 'already saved' in repeated, repeated
        index = call('search', {'query': 'Synthetic', 'project': 'records-proof', 'limit': 5})
        assert str(observation_id) in index, index
        timeline = call('timeline', {'anchor': observation_id, 'project': 'records-proof', 'depth_before': 1, 'depth_after': 1})
        assert str(observation_id) in timeline, timeline
        detail = call('get_observations', {'ids': [observation_id], 'project': 'records-proof'})
        assert 'concurrency verification' in detail, detail
        other = call('search', {'query': 'Synthetic', 'project': 'unrelated-project', 'limit': 5})
        assert 'Synthetic continuity proof' not in other, other
        checks.append('real MCP initialize/list/save/search/timeline/read, replay deduplication and project filtering')

        hub = root / 'wiki'
        topic = hub / 'topics/demo'
        (topic / 'raw/notes').mkdir(parents=True)
        (topic / 'log.md').write_text('# Log\n')
        (hub / 'wikis.json').write_text(json.dumps({'wikis': {'demo': {'path': 'topics/demo'}}}))
        digest = Path(run('wiki-session', '--hub', str(hub), 'capture', '--harness', 'manual',
                          '--session-id', 'records-proof', '--cwd', str(project), '--summary', detail))
        assert digest.is_file()
        rehydrated = run('wiki-session', '--hub', str(hub), 'rehydrate', '--session-id', 'manual:records-proof')
        assert str(digest) in rehydrated, rehydrated
        promoted = Path(run('wiki-session', '--hub', str(hub), 'promote', 'manual:records-proof', '--topic', 'demo'))
        assert promoted.is_file() and 'concurrency verification' in promoted.read_text()
        checks.append('memory evidence to Wiki digest, fresh-process rehydrate and raw-note promotion')
        report = {'passed': True, 'checks': checks, 'evidence_root': str(root),
                  'worker_degraded_dependencies': health.get('dependencies'),
                  'unverified': ['model-authored BMAD plan quality', 'LLM Wiki knowledge compilation',
                                 'automatic capture hooks', 'real host discovery and cross-host transfer']}
    except Exception as error:
        report = {'passed': False, 'checks': checks, 'error': str(error), 'evidence_root': str(root)}
    finally:
        for process in [mcp, worker]:
            if process is not None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        worker_log.close()
        mcp_log.close()
    (root / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
