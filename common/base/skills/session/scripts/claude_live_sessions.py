#!/usr/bin/env python3
"""Bounded official Claude agents JSON and Linux identity proof. No terminal I/O.

The caller supplies the existing runtime adapter so errors and native transport
have one owner. Nothing here reads transcripts, argv or Claude's private registry.
"""
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import uuid

PRODUCER = '2.1.331'
EXECUTABLE_VERSIONS = frozenset(('2.1.319', '2.1.329', '2.1.331'))
MAX_ROWS = 512
MAX_JSON = 262144


def bounded(path, limit):
    with path.open('rb') as source:
        value = source.read(limit + 1)
    if len(value) > limit:
        raise ValueError('bounded observation exceeded')
    return value


def executable(rr, path, *, home=None, versions=EXECUTABLE_VERSIONS):
    home = Path.home() if home is None else Path(home)
    path = Path(path)
    if path.parent != home / '.local/share/claude/versions' or path.name not in versions:
        raise rr.Deferred('exception-executable-unsupported')
    info = path.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or info.st_mode & 0o022 or not info.st_mode & 0o111 or path.resolve() != path):
        raise rr.Deferred('exception-executable-unverifiable')
    return {'path': str(path), 'device': info.st_dev, 'inode': info.st_ino,
            'uid': info.st_uid, 'mode': info.st_mode, 'size': info.st_size,
            'mtimeNs': info.st_mtime_ns}


def query_executable(rr, *, home=None):
    command = shutil.which('claude')
    if command is None:
        raise rr.Deferred('exception-producer-unverified')
    return executable(rr, Path(command).resolve(strict=True), home=home, versions={PRODUCER})


def query_identity(rr, query):
    """Recheck the proven file itself; PATH never chooses its replacement."""
    if executable(rr, query['path'], versions={PRODUCER}) != query:
        raise rr.Deferred('exception-live-proof-changed')


def query_command(rr, query, args, cwd):
    """Bind each bounded native invocation to the exact proven producer."""
    query_identity(rr, query)
    result = rr.native_command('claude', args, cwd, executable=query['path'])
    query_identity(rr, query)
    return result


def process(rr, pid, *, proc_root=Path('/proc'), home=None):
    """Return only identity fields; environ is bounded and never returned."""
    try:
        if sys.platform != 'linux' or type(pid) is not int or pid <= 0:
            raise ValueError('unsupported process')
        root = Path(proc_root)
        path = root / str(pid)
        raw = bounded(path / 'stat', 8192).decode('utf-8')
        prefix, separator, rest = raw.rpartition(') ')
        fields = rest.split()
        if not separator or prefix.split(' ', 1)[0] != str(pid) or len(fields) < 20:
            raise ValueError('invalid stat')
        start = int(fields[19])
        if start <= 0 or path.stat().st_uid != os.getuid():
            raise ValueError('process owner/start unknown')
        status = bounded(path / 'status', 16384).decode('utf-8')
        uid = re.findall(r'^Uid:\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$', status, re.M)
        nspid = re.findall(r'^NSpid:\s*([^\n]+)$', status, re.M)
        if (len(uid) != 1 or any(int(v) != os.getuid() for v in uid[0])
                or len(nspid) != 1 or nspid[0].split() != [str(pid)]):
            raise ValueError('uid or pid namespace unknown')
        namespace = os.readlink(path / 'ns/pid')
        if (namespace != os.readlink(root / 'self/ns/pid')
                or not re.fullmatch(r'pid:\[\d+\]', namespace)):
            raise ValueError('pid namespace mismatch')
        exe_path = os.readlink(path / 'exe')
        exe = executable(rr, exe_path, home=home)
        info = (path / 'exe').stat()
        if (info.st_dev, info.st_ino) != (exe['device'], exe['inode']):
            raise ValueError('executable identity mismatch')
        cwd = os.readlink(path / 'cwd')
        if not cwd.startswith('/') or '\x00' in cwd or cwd.endswith(' (deleted)'):
            raise ValueError('cwd unknown')
        environment = bounded(path / 'environ', 131072)
        if not environment.endswith(b'\0'):
            raise ValueError('incomplete environment')
        panes = [entry[len(b'ORCA_PANE_KEY='):] for entry in environment.split(b'\0')
                 if entry.startswith(b'ORCA_PANE_KEY=')]
        if len(panes) != 1:
            raise ValueError('pane unknown')
        pane = panes[0].decode('utf-8', errors='strict')
        if not rr.token(pane):
            raise ValueError('pane unknown')
        return {'pid': pid, 'uid': os.getuid(), 'startTicks': start, 'pidNamespace': namespace,
                'executable': exe, 'cwd': cwd, 'paneKey': pane}
    except (OSError, ValueError, UnicodeError, IndexError):
        raise rr.Deferred('exception-process-unverifiable') from None


def parse(rr, text):
    try:
        if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_JSON:
            raise ValueError('invalid JSON size')
        def unique_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('duplicate JSON field')
                result[key] = value
            return result
        rows = json.loads(text, object_pairs_hook=unique_pairs)
        if not isinstance(rows, list) or len(rows) > MAX_ROWS:
            raise ValueError('invalid rows')
        result = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError('invalid row')
            pid, ident, cwd, kind = (row.get(k) for k in ('pid', 'sessionId', 'cwd', 'kind'))
            if (type(pid) is not int or pid <= 0 or not isinstance(ident, str)
                    or str(uuid.UUID(ident)) != ident or not rr.token(cwd) or not cwd.startswith('/')
                    or kind not in ('interactive', 'background')):
                raise ValueError('invalid identity')
            result.append({'pid': pid, 'sessionId': ident, 'cwd': cwd, 'kind': kind})
        if (len({r['pid'] for r in result}) != len(result)
                or len({r['sessionId'] for r in result}) != len(result)):
            raise rr.Deferred('exception-live-identity-ambiguous')
        return result
    except (ValueError, TypeError, AttributeError, RecursionError):
        raise rr.Deferred('exception-native-json-invalid') from None


def observations(rr, cwd, *, absent_uuid=None):
    """A bounded pair of official responses with stable relevant proc identities."""
    try:
        query = query_executable(rr)
        if query_command(rr, query, ['--version'], cwd).strip() != PRODUCER + ' (Claude Code)':
            raise rr.Deferred('exception-producer-unverified')
        rows = parse(rr, query_command(rr, query, ['agents', '--json'], cwd))
        if absent_uuid is not None and any(r['sessionId'] == absent_uuid for r in rows):
            raise rr.Deferred('exception-expected-session-still-live')
        # Cold absence must rule out pane reuse in every active cwd. Live proof
        # remains scoped to its expected cwd, without reading unrelated processes.
        relevant = rows if absent_uuid is not None else [r for r in rows if r['cwd'] == cwd]
        before = {r['pid']: process(rr, r['pid']) for r in relevant}
        if any(before[r['pid']]['cwd'] != r['cwd'] for r in relevant):
            raise rr.Deferred('exception-live-identity-mismatch')
        fresh = parse(rr, query_command(rr, query, ['agents', '--json'], cwd))
        if absent_uuid is not None and any(r['sessionId'] == absent_uuid for r in fresh):
            raise rr.Deferred('exception-expected-session-still-live')
        fresh_relevant = fresh if absent_uuid is not None else [r for r in fresh if r['cwd'] == cwd]
        if (sorted(relevant, key=lambda r: r['pid']) != sorted(fresh_relevant, key=lambda r: r['pid'])
                or any(process(rr, pid) != proof for pid, proof in before.items())
                or query_executable(rr) != query):
            raise rr.Deferred('exception-live-proof-changed')
        query_identity(rr, query)
        return query, relevant, before
    except (OSError, ValueError, UnicodeError):
        raise rr.Deferred('exception-live-proof-unverifiable') from None


def observe(rr, cwd, pane, *, expected=None):
    """Fresh identity, fixed for this operation; old PID/start is never authority."""
    query, relevant, before = observations(rr, cwd)
    matching = [r for r in relevant if before[r['pid']]['paneKey'] == pane]
    if len(matching) != 1:
        raise rr.Deferred('exception-live-identity-ambiguous')
    chosen = matching[0]
    if chosen['kind'] != 'interactive' or (expected is not None and chosen['sessionId'] != expected):
        raise rr.Deferred('exception-live-identity-mismatch')
    return {'producerVersion': PRODUCER, 'queryExecutable': query,
            **chosen, 'paneKey': pane, 'process': before[chosen['pid']]}


def observe_absent(rr, cwd, pane, *, expected):
    """Prove a known excluded UUID absent; unreadable rows are never absence.

    All active processes are validated across this observation, rather than
    becoming authority for an absent identity. Selected process creation must not
    rewrite or invalidate the fixed expectation that this manual UUID is absent.
    """
    query, _, before = observations(rr, cwd, absent_uuid=expected)
    if any(proof['paneKey'] == pane for proof in before.values()):
        raise rr.Deferred('exception-absent-pane-reused')
    return {'producerVersion': PRODUCER, 'queryExecutable': query, 'kind': 'absent',
            'sessionId': expected, 'cwd': cwd, 'paneKey': pane}


def recheck(rr, proof):
    """Only local fixed evidence after the last native query/selected frame."""
    query_identity(rr, proof['queryExecutable'])
    if (proof['kind'] != 'absent' and process(rr, proof['pid']) != proof['process']
            or query_executable(rr) != proof['queryExecutable']):
        raise rr.Deferred('exception-live-proof-changed')


def validate(rr, identity):
    """Validate stored metadata only; historical PID/executable is never reused."""
    try:
        if (set(identity) != {'producerVersion', 'queryExecutable', 'pid', 'sessionId', 'cwd',
                             'kind', 'paneKey', 'process'}
                or identity['producerVersion'] != PRODUCER or identity['kind'] != 'interactive'
                or str(uuid.UUID(identity['sessionId'])) != identity['sessionId']
                or not rr.token(identity['cwd']) or not identity['cwd'].startswith('/')
                or not rr.token(identity['paneKey'])
                or type(identity['pid']) is not int or identity['pid'] <= 0):
            raise ValueError('invalid identity')
        process_proof = identity['process']
        if (set(process_proof) != {'pid', 'uid', 'startTicks', 'pidNamespace', 'executable', 'cwd', 'paneKey'}
                or any(process_proof[k] != identity[k] for k in ('pid', 'cwd', 'paneKey'))
                or type(process_proof['startTicks']) is not int or process_proof['startTicks'] <= 0
                or type(process_proof['uid']) is not int or process_proof['uid'] != os.getuid()
                or not re.fullmatch(r'pid:\[\d+\]', process_proof['pidNamespace'])):
            raise ValueError('invalid process proof')
        for exe, versions in ((identity['queryExecutable'], {PRODUCER}),
                              (process_proof['executable'], EXECUTABLE_VERSIONS)):
            if (set(exe) != {'path', 'device', 'inode', 'uid', 'mode', 'size', 'mtimeNs'}
                    or not isinstance(exe['path'], str) or not exe['path'].startswith('/')
                    or Path(exe['path']).parent != Path.home() / '.local/share/claude/versions'
                    or Path(exe['path']).name not in versions
                    or any(type(exe[k]) is not int or exe[k] < 0 for k in
                           ('device', 'inode', 'uid', 'mode', 'size', 'mtimeNs'))
                    or exe['uid'] != os.getuid() or not stat.S_ISREG(exe['mode'])
                    or exe['mode'] & 0o022 or not exe['mode'] & 0o111):
                raise ValueError('invalid executable proof')
    except (ValueError, TypeError, KeyError, AttributeError):
        raise rr.Deferred('exception-attestation-invalid') from None
    return identity
