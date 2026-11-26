#!/usr/bin/env python3
"""Private one-use Claude exact-resume exec gate. No general command/environment replay."""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import uuid


class Refused(Exception):
    pass


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def file_identity(path, *, executable=False):
    path = Path(path)
    if not path.is_absolute() or path.resolve() != path:
        raise Refused()
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid not in (0, os.getuid())
            or info.st_mode & 0o022 or executable and not info.st_mode & 0o111):
        raise Refused()
    return dict(path=str(path), device=info.st_dev, inode=info.st_ino, uid=info.st_uid,
                mode=info.st_mode, size=info.st_size, mtimeNs=info.st_mtime_ns)


# Observed native319/329/332 bookkeeping ONLY. Unknown fields stay authoritative.
_RUNTIME_TOP = frozenset(('cachedFeatureFlags', 'cachedGrowthBookFeatures',
    'cachedGrowthBookFeaturesAt', 'pluginUsage', 'additionalModelOptionsAnsweredAt',
    'cachedExperimentData', 'tipsHistory', 'tipLifetimeShownCounts', 'clientDataCacheSlots',
    'cachedExperimentFeatures', 'numStartups', 'tipsHistoryByCommand', 'cachedFeatureFlagsAt'))
_RUNTIME_PROJECT = frozenset(('lastGracefulShutdown', 'lastVersionBase', 'lastCost',
    'lastAPIDuration', 'lastAPIDurationWithoutRetries', 'lastToolDuration', 'lastDuration',
    'lastStartTime', 'lastLinesAdded', 'lastLinesRemoved', 'lastTotalInputTokens',
    'lastTotalOutputTokens', 'lastTotalCacheCreationInputTokens', 'lastTotalCacheReadInputTokens',
    'lastTotalWebSearchRequests', 'lastFpsAverage', 'lastFpsLow1Pct', 'lastModelUsage', 'lastSessionId'))
RUNTIME_KEYS = {version: (_RUNTIME_TOP, _RUNTIME_PROJECT)
                for version in ('2.1.319', '2.1.329', '2.1.332')}
MAX_PROFILE_BYTES = 2_000_000


def strict_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise Refused()
            result[key] = value
        return result
    def invalid_constant(value):
        raise Refused()
    try:
        value = json.loads(data, object_pairs_hook=unique, parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise Refused() from None
    if not isinstance(value, dict):
        raise Refused()
    return value


def state_projection(value, version):
    if version not in RUNTIME_KEYS:
        raise Refused()
    top_keys, project_keys = RUNTIME_KEYS[version]
    result = {key: item for key, item in value.items() if key not in top_keys}
    if 'projects' in result:
        if not isinstance(result['projects'], dict):
            raise Refused()
        projects = {}
        for path, project in result['projects'].items():
            if not isinstance(project, dict):
                raise Refused()
            kept = {key: item for key, item in project.items() if key not in project_keys}
            if kept:
                projects[path] = kept
        # An absent/empty project with only known runtime fields adds no policy.
        if projects:
            result['projects'] = projects
        else:
            del result['projects']
    return result


def stable_data(path, *, state_version=None):
    """Stable bounded content; inode/timestamps detect races, not semantics."""
    path = Path(path)
    if not path.is_absolute() or path.resolve() != path:
        raise Refused()
    try:
        before = path.lstat()
    except FileNotFoundError:
        try:
            path.lstat()
        except FileNotFoundError:
            return None
        raise Refused()
    def signature(info):
        return (info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode,
                info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
            or before.st_mode & 0o002 or before.st_nlink != 1 or before.st_size > MAX_PROFILE_BYTES):
        raise Refused()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as source:
        if signature(os.fstat(source.fileno())) != signature(before):
            raise Refused()
        data = source.read(MAX_PROFILE_BYTES + 1)
        if (len(data) > MAX_PROFILE_BYTES or signature(os.fstat(source.fileno())) != signature(before)
                or signature(path.lstat()) != signature(before) or path.resolve() != path):
            raise Refused()
    value = strict_json(data)  # Reject duplicate keys even in opaque credential/settings data.
    try:
        content = encoded(state_projection(value, state_version)) if state_version is not None else data
    except (ValueError, UnicodeError, RecursionError):
        raise Refused() from None
    return {'uid': before.st_uid, 'gid': before.st_gid, 'mode': stat.S_IMODE(before.st_mode),
            'contentSha256': hashlib.sha256(content).hexdigest()}


def owned_entry(path, *, directory=True, missing=False):
    path = Path(path)
    if path.resolve() != path:
        raise Refused()
    try:
        info = path.lstat()
    except FileNotFoundError:
        if missing:
            return
        raise Refused() from None
    if (info.st_uid != os.getuid() or info.st_mode & 0o002
            or (not stat.S_ISDIR(info.st_mode) if directory else
                not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)))):
        raise Refused()


def git_discovery_environment(values):
    """Only documented prompting-only Git/GCM inputs; never forward them to Git."""
    if any(not isinstance(key, bytes) or not isinstance(value, bytes) for key, value in values.items()):
        raise Refused()
    booleans = frozenset((b'0', b'1', b'false', b'true', b'no', b'yes', b'off', b'on'))
    prompt_values = {b'credential.interactive': booleans | {b'auto', b'never', b'always', b'force'},
                     b'credential.guiprompt': booleans}
    count_value = values.get(b'GIT_CONFIG_COUNT')
    if count_value is None:
        count = 0
    elif count_value in (b'', b'0', b'1', b'2'):
        count = int(count_value or b'0')
    else:
        raise Refused()
    indexed = {prefix + str(index).encode('ascii')
               for prefix in (b'GIT_CONFIG_KEY_', b'GIT_CONFIG_VALUE_') for index in range(count)}
    allowed = indexed | {b'GIT_CONFIG_COUNT', b'GIT_ASKPASS', b'GIT_TERMINAL_PROMPT'}
    if (any(key.startswith(b'GIT_') and key not in allowed for key in values)
            or any(key not in values for key in indexed)):
        raise Refused()
    seen = set()
    for index in range(count):
        raw_key = values[b'GIT_CONFIG_KEY_' + str(index).encode('ascii')]
        raw_value = values[b'GIT_CONFIG_VALUE_' + str(index).encode('ascii')]
        if len(raw_key) > 64 or len(raw_value) > 32:
            raise Refused()
        key, value = raw_key.lower(), raw_value.lower()
        if key not in prompt_values or key in seen or value not in prompt_values[key]:
            raise Refused()
        seen.add(key)
    if (b'GIT_TERMINAL_PROMPT' in values
            and values[b'GIT_TERMINAL_PROMPT'].lower() not in booleans):
        raise Refused()
    askpass = values.get(b'GIT_ASKPASS', b'')
    if len(askpass) > 4096 or any(char in askpass for char in (b'\0', b'\r', b'\n')):
        raise Refused()
    # This derived environment is only for fixed read-only root discovery.
    # Native exec and environmentSha256 still use every original inherited byte.
    return {key: value for key, value in values.items() if not key.startswith(b'GIT_')}


def project_roots(cwd, values):
    """Official read-only Git discovery, retaining cwd legacy settings as well."""
    cwd = Path(cwd)
    owned_entry(cwd)
    roots = [cwd]
    # Validate before the no-repository return: alternate contexts stay unsupported.
    discovery_environment = git_discovery_environment(values)
    ancestor = next((p for p in (cwd, *cwd.parents) if (p / '.git').exists() or (p / '.git').is_symlink()), None)
    if ancestor is None:
        return roots
    owned_entry(ancestor)
    owned_entry(ancestor / '.git', directory=False)
    git = Path('/usr/bin/git').resolve()
    identity = file_identity(git, executable=True)
    if identity['uid'] != 0:
        raise Refused()
    result = subprocess.run([str(git), '-C', str(cwd), 'rev-parse', '--path-format=absolute',
                             '--show-toplevel', '--git-common-dir', '--is-bare-repository'],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            timeout=5, check=False, env=discovery_environment)
    if (result.returncode or len(result.stdout) > 16384 or file_identity(git, executable=True) != identity):
        raise Refused()
    lines = result.stdout.decode('utf-8').splitlines()
    if len(lines) != 3 or lines[2] != 'false' or Path(lines[0]) != ancestor:
        raise Refused()
    common = Path(lines[1])
    main = common.parent
    if common.name != '.git' or not common.is_absolute():
        raise Refused()
    owned_entry(common)
    owned_entry(main)
    for root in (ancestor, main):
        owned_entry(root / '.claude', missing=True)
        if root != Path.home() and root not in roots:
            roots.append(root)
    return roots


def environment_proof(values, cwd, *, version='2.1.332'):
    """Hash selected/actual inherited environment and logical data profile."""
    if version not in RUNTIME_KEYS:
        raise Refused()
    if any(not isinstance(k, bytes) or not isinstance(v, bytes) or not k or b'=' in k
           or b'\0' in k or b'\0' in v for k, v in values.items()):
        raise Refused()
    inherited = sorted(k + b'=' + v for k, v in values.items() if k not in (b'_', b'SHLVL'))
    if sum(map(len, inherited)) > 131072:
        raise Refused()
    home = Path(values[b'HOME'].decode('utf-8'))
    config = Path(values.get(b'CLAUDE_CONFIG_DIR', os.fsencode(home / '.claude')).decode('utf-8'))
    if home != Path.home() or config != home / '.claude' or config.resolve() != config:
        raise Refused()  # Only the observed default profile layout is supported.
    owned_entry(config, missing=True)
    files = [home / '.claude.json', config / '.credentials.json', config / 'settings.json']
    for root in project_roots(cwd, values):
        owned_entry(root / '.claude', missing=True)
        files.extend((root / '.claude/settings.json', root / '.claude/settings.local.json', root / '.mcp.json'))
    metadata = []
    for path in dict.fromkeys(files):
        metadata.append([str(path), stable_data(path, state_version=version if path == home / '.claude.json' else None)])
    return {'environmentSha256': hashlib.sha256(b'\0'.join(inherited)).hexdigest(),
            'profileSha256': hashlib.sha256(encoded(metadata)).hexdigest()}


def source_proof():
    root = Path(__file__).absolute().parent
    result = []
    for name in ('claude_checked_resume.py', 'claude_live_sessions.py', 'runtime_refresh.py', 'session_restart.py'):
        path = root / name
        before = file_identity(path)
        data = path.read_bytes()
        if len(data) > 1048576 or file_identity(path) != before:
            raise Refused()
        result.append(dict(identity=before, sha256=hashlib.sha256(data).hexdigest()))
    return result


def write_proof(directory, *, batch_id, attempt_id, native, launch):
    """Create once; no stored arbitrary argv/env and no child Store lock."""
    for ident in (batch_id, attempt_id, native['sessionId']):
        if str(uuid.UUID(ident)) != ident:
            raise Refused()
    directory = Path(directory)
    info = directory.lstat()
    if (directory.resolve() != directory or not stat.S_ISDIR(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.getuid()):
        raise Refused()
    executable = native['queryExecutable']
    if (file_identity(executable['path'], executable=True) != executable
            or Path(executable['path']) != Path.home() / '.local/share/claude/versions/2.1.332'):
        raise Refused()
    path = directory / ('claude-resume-' + attempt_id + '.proof')
    body = dict(schema=1, proofPath=str(path), batchId=batch_id, attemptId=attempt_id, sessionId=native['sessionId'],
                cwd=native['cwd'], paneKey=native['paneKey'], environment=launch['environment'],
                sourceVersion=Path(native['process']['executable']['path']).name,
                shell=launch['shell'], shellExecutable=launch['shellExecutable'],
                native=executable, sources=source_proof(),
                python=file_identity(Path('/usr/bin/python3').resolve(), executable=True))
    data = encoded(body)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())
    dfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)
    return dict(path=str(path), sha256=hashlib.sha256(data).hexdigest())


def command(proof):
    return shlex.join([str(Path('/usr/bin/python3').resolve()), '-I', '-S', str(Path(__file__).absolute()),
                       '--proof', proof['path'], '--sha256', proof['sha256']])


def inspect_proof(proof):
    """Recheck immutable launch intent before either original terminal input."""
    path = Path(proof['path'])
    if (path.resolve() != path or path.parent.stat().st_uid != os.getuid()
            or stat.S_IMODE(path.parent.stat().st_mode) != 0o700
            or path.with_name(path.name + '.used').exists()):
        raise Refused()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as source:
        info = os.fstat(source.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o400 or info.st_nlink != 1 or info.st_size > 32768):
            raise Refused()
        data = source.read(32769)
    body = json.loads(data)
    if (body['proofPath'] != str(path) or hashlib.sha256(data).hexdigest() != proof['sha256']
            or body['sources'] != source_proof()
            or body['native'] != file_identity(body['native']['path'], executable=True)
            or body['python'] != file_identity(Path('/usr/bin/python3').resolve(), executable=True)):
        raise Refused()
    return body


def parent_identity():
    path = Path('/proc') / str(os.getppid())
    fields = (path / 'stat').read_text().rpartition(') ')[2].split()
    return dict(pid=os.getppid(), starttime=int(fields[19]), uid=path.stat().st_uid,
                sid=int(fields[3]), pgrp=int(fields[2]), tty=int(fields[4]))


def parent_executable():
    path = Path('/proc') / str(os.getppid()) / 'exe'
    info = path.stat()
    return dict(path=os.readlink(path), device=info.st_dev, inode=info.st_ino,
                uid=info.st_uid, mode=info.st_mode, mtime=info.st_mtime_ns)


def run(path, digest):
    """Claim durably BEFORE validation/exec. Every failure consumes this attempt."""
    path = Path(path)
    if (not re.fullmatch('[a-f0-9]{64}', digest) or path.resolve() != path
            or not re.fullmatch(r'claude-resume-[a-f0-9-]{36}\.proof', path.name)):
        raise Refused()
    directory = path.parent
    info = directory.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise Refused()
    dfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    claimed = False
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dfd)
        with os.fdopen(fd, 'rb') as source:
            info = os.fstat(source.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
                    or stat.S_IMODE(info.st_mode) != 0o400 or info.st_size > 32768):
                raise Refused()
            data = source.read(32769)
        if hashlib.sha256(data).hexdigest() != digest:
            raise Refused()
        claim = os.open(path.name + '.used', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o400, dir_fd=dfd)
        claimed = True
        try:
            os.write(claim, digest.encode())
            os.fsync(claim)
        finally:
            os.close(claim)
        os.fsync(dfd)
        body = json.loads(data)
        if (body['schema'] != 1 or body['proofPath'] != str(path)
                or path.name != 'claude-resume-' + body['attemptId'] + '.proof'
                or any(str(uuid.UUID(body[k])) != body[k] for k in ('attemptId', 'batchId', 'sessionId'))
                or body['sources'] != source_proof()
                or body['python'] != file_identity(Path('/usr/bin/python3').resolve(), executable=True)
                or os.getcwd() != body['cwd'] or os.environ.get('ORCA_PANE_KEY') != body['paneKey']
                or any(body['shell'][k] != v for k, v in parent_identity().items())
                or body['shellExecutable'] != parent_executable()
                or environment_proof(dict(os.environb), body['cwd'], version=body['sourceVersion']) != body['environment']):
            raise Refused()
        native = body['native']
        if (Path(native['path']) != Path.home() / '.local/share/claude/versions/2.1.332'
                or file_identity(native['path'], executable=True) != native):
            raise Refused()
        native_fd = os.open(native['path'], os.O_RDONLY | os.O_NOFOLLOW)
        try:
            info = os.fstat(native_fd)
            if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) != tuple(
                    native[k] for k in ('device', 'inode', 'size', 'mtimeNs')):
                raise Refused()
            # The env is current, validated inherited state, never stored values.
            os.execve(native_fd, [native['path'], '--dangerously-skip-permissions',
                                 '--resume', body['sessionId']], dict(os.environ))
        finally:
            os.close(native_fd)
    except (Refused, OSError, ValueError, KeyError, TypeError, UnicodeError, subprocess.SubprocessError):
        if not claimed:
            raise
        try:
            result = os.open(path.name + '.refused', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o400, dir_fd=dfd)
            try:
                os.write(result, digest.encode())
                os.fsync(result)
            finally:
                os.close(result)
            os.fsync(dfd)
        except OSError:
            pass
        raise
    finally:
        os.close(dfd)


def main():
    try:
        if len(sys.argv) != 5 or sys.argv[1] != '--proof' or sys.argv[3] != '--sha256':
            raise Refused()
        run(sys.argv[2], sys.argv[4])
    except (Refused, OSError, ValueError, KeyError, TypeError, UnicodeError, subprocess.SubprocessError):
        # Never print exceptions, raw environment, arguments or profile contents.
        print('claude-checked-resume-refused', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
