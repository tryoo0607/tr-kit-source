"""Fresh filesystem inspection shared by post hooks and assembly/transfer gates.

No receipt is trusted as a substitute for reading current bytes. No Git ignore
filter, shell execution, rollback, transcript copy, or source mutation is used.
"""
import json
import os
import stat
from pathlib import Path

from upstream_guard import Guard, Scope, Unavailable, bounded_read, digest, exact_content

MAX_NODES = 4096
MAX_TOTAL_BYTES = 16_000_000


def _opaque_container(data):
    return (data.startswith((b'PK\x03\x04', b'PK\x05\x06', b'\x1f\x8b', b'BZh',
                             b'\xfd7zXZ\x00', b'\x28\xb5\x2f\xfd')) or
            data[257:262] == b'ustar')


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _snapshot(root, catalog, scope_path, phase):
    if phase not in ('post', 'assembly', 'transfer'):
        raise Unavailable('invalid inspection phase')
    scope = Scope(root, scope_path)
    guard = Guard(root, catalog)
    guard.load()
    # Bind the identity to the exact bytes Guard parsed, not a later read.
    catalog_before = guard.catalog_fingerprint
    targets = [('component', path) for path in scope.components]
    if phase == 'transfer' and not scope.artifacts:
        raise Unavailable('transfer requires declared expanded artifact directories')
    absent_artifacts = []
    if phase in ('post', 'transfer'):
        for path in scope.artifacts:
            if not path.exists() and not path.is_symlink():
                if phase == 'transfer':
                    raise Unavailable('declared artifact directory missing')
                absent_artifacts.append(str(path))
                continue
            if not path.is_dir():
                raise Unavailable('expanded artifact directory required')
            targets.append(('artifact', path))
    records, findings = {}, []
    total, visited = 0, 0

    def visit(path):
        nonlocal total, visited
        key = str(path)
        if key in records:
            return
        visited += 1
        if visited > MAX_NODES:
            raise Unavailable('declared inventory node limit exceeded')
        before = path.lstat()
        if stat.S_ISLNK(before.st_mode):
            target = path.resolve(strict=True)
            if target.is_dir():
                raise Unavailable('directory reference inventory is not supported')
            if any(target == Path(e['path']) for e in guard.entries):
                kind = 'official-reference'
                # The original's bytes/pin were validated once; avoid rereading
                # the same large official file for every reference node.
                value = next(e['sha256'] for e in guard.entries if target == Path(e['path']))
            elif scope.covers(target):
                kind = 'scoped-reference'
                data = bounded_read(target)
                total += len(data)
                if _opaque_container(data):
                    raise Unavailable('expanded inventory required for container-like content')
                result = exact_content(guard, data)
                if result.status == 'block':
                    findings.append({'path': key, 'observation': result.reason})
                value = digest(data)
            else:
                raise Unavailable('reference points outside declared or registered inventory')
            records[key] = {'kind': kind, 'link': os.readlink(path), 'sha256': value}
        elif stat.S_ISDIR(before.st_mode):
            records[key] = {'kind': 'directory'}
            children = []
            with os.scandir(path) as entries:
                for entry in entries:
                    if visited + len(children) + 1 > MAX_NODES:
                        raise Unavailable('declared inventory node limit exceeded')
                    children.append(Path(entry.path))
            for child in sorted(children):
                visit(child)
        elif stat.S_ISREG(before.st_mode):
            data = bounded_read(path)
            total += len(data)
            if _opaque_container(data):
                raise Unavailable('expanded inventory required for container-like content')
            result = exact_content(guard, data)
            records[key] = {'kind': 'file', 'sha256': digest(data)}
            if result.status == 'block':
                findings.append({'path': key, 'observation': result.reason})
        else:
            raise Unavailable('declared inventory contains unsupported filesystem node')
        if total > MAX_TOTAL_BYTES:
            raise Unavailable('declared inventory byte limit exceeded')
        if _signature(before) != _signature(path.lstat()):
            raise Unavailable('filesystem target changed during inspection')

    for kind, target in targets:
        visit(target)
    # A new Guard re-reads original pins, rather than relying on cached entries.
    Guard(root, catalog).load()
    if catalog_before != digest(bounded_read(catalog)) or scope.fingerprint != digest(bounded_read(scope_path)):
        raise Unavailable('inspection declaration changed during scan')
    state = {'scope': scope.fingerprint, 'catalog': catalog_before, 'phase': phase,
             'targets': [(kind, str(path)) for kind, path in targets],
             'absent_artifacts': absent_artifacts, 'records': records}
    fingerprint = digest(json.dumps(state, sort_keys=True, separators=(',', ':')).encode())
    return {'status': 'block' if findings else 'pass', 'complete': True,
            'phase': phase, 'fingerprint': fingerprint, 'nodes': len(records),
            'files': sum(record['kind'] == 'file' for record in records.values()),
            'references': sum(record['kind'].endswith('reference') for record in records.values()),
            'scope_fingerprint': scope.fingerprint, 'catalog_fingerprint': catalog_before,
            'targets': state['targets'], 'inventory': records,
            'absent_artifacts': absent_artifacts,
            'findings': findings, 'coverage': 'declared current files and registered originals only',
            'limits': 'No authorship, unregistered-source, rewrite or native enforcement certification.'}


def inspect(root: Path, catalog: Path, scope: Path, phase: str) -> dict:
    try:
        first = _snapshot(root, catalog, scope, phase)
        second = _snapshot(root, catalog, scope, phase)
        if first['fingerprint'] != second['fingerprint']:
            raise Unavailable('inventory changed between observations')
        return second
    except Unavailable as error:
        reason = str(error)
    except (OSError, ValueError, TypeError, KeyError, RecursionError, RuntimeError):
        reason = 'filesystem or declaration inspection failed'
    return {'status': 'unavailable', 'complete': False, 'phase': phase,
            'reason': reason, 'coverage': 'inspection incomplete; fresh gate required'}
