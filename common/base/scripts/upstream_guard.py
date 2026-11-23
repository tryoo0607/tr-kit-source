"""Project-scoped upstream-content checks. No tool execution or file mutation.

The catalog holds fingerprints of explicitly selected official files, not their
contents. Passing means only 'no match in that catalog', not proof of authorship.
"""
from __future__ import annotations

import hashlib
import json
import os
import shlex
import stat
from dataclasses import dataclass
from pathlib import Path

MAX_BYTES = 1_000_000
MAX_SOURCES = 256


class Unavailable(ValueError):
    pass


@dataclass(frozen=True)
class Result:
    status: str  # pass, block, unavailable, not_applicable, deferred
    reason: str


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bounded_read(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise Unavailable('only regular files can be inspected')
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise Unavailable('inspection size limit exceeded')
    return data


def absolute(value: str, cwd: Path) -> Path:
    if not isinstance(value, str) or not value or '\x00' in value:
        raise Unavailable('missing or invalid target path')
    p = Path(value)
    return (p if p.is_absolute() else cwd / p).resolve(strict=False)


def unlink_target(value: str, cwd: Path) -> Path:
    """Unlink resolves parents, not the final symlink's referent."""
    if not isinstance(value, str) or not value or '\x00' in value:
        raise Unavailable('missing or invalid deletion path')
    p = Path(value)
    p = p if p.is_absolute() else cwd / p
    return p.parent.resolve(strict=False) / p.name


def within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


class Scope:
    """Explicit component roots and complete, expanded artifact directories."""
    def __init__(self, root: Path, path: Path):
        self.root = root.resolve(strict=True)
        raw = bounded_read(path)
        doc = json.loads(raw)
        if (not isinstance(doc, dict) or sorted(doc) != ['artifacts', 'components', 'version'] or
                type(doc['version']) is not int or doc['version'] != 1):
            raise Unavailable('invalid scope declaration')
        if (not isinstance(doc['components'], list) or not 1 <= len(doc['components']) <= 64 or
                not isinstance(doc['artifacts'], list) or len(doc['artifacts']) > 64):
            raise Unavailable('invalid scope target lists')
        self.components = []
        for value in doc['components']:
            if not isinstance(value, str) or not value or Path(value).is_absolute():
                raise Unavailable('components require project-relative paths')
            if '..' in Path(value).parts:
                raise Unavailable('component declaration contains parent traversal')
            target = self.root if Path(value) == Path('.') else unlink_target(value, self.root)
            if not within(target, self.root):
                raise Unavailable('component root escapes project')
            self.components.append(target)
        self.artifacts = []
        for value in doc['artifacts']:
            if not isinstance(value, str) or not Path(value).is_absolute():
                raise Unavailable('artifact directories require absolute paths')
            # Preserve the declared leaf so a directory symlink cannot vanish
            # before the inventory's lstat/type check. Ancestors are canonical.
            self.artifacts.append(unlink_target(value, self.root))
        self.fingerprint = digest(raw)

    def covers(self, path: Path) -> bool:
        # Physical inventory membership: an outside reference is not thereby
        # promoted to a declared, traversable source tree.
        return any(within(path, target) for target in self.components + self.artifacts)

    def mutation_covers(self, path: Path) -> bool:
        # Mutation targets resolve file references to their actual referents.
        return (self.covers(path) or any(within(path, target.resolve())
                for target in self.components + self.artifacts))


def exact_content(guard, data: bytes) -> Result:
    """Exact observations only; no similarity or authorship inference."""
    guard.load()
    if len(data) > MAX_BYTES:
        raise Unavailable('inspection size limit exceeded')
    candidate_digest = digest(data)
    for entry in guard.entries:
        raw = guard.raws[entry['path']]
        if candidate_digest == entry['sha256']:
            return Result('block', 'candidate bytes equal a registered original')
        if raw in data:
            return Result('block', 'candidate contains an entire registered original')
    return Result('pass', 'no registered exact match; unregistered sources and rewrites not certified')


def make_catalog(paths: list[Path]) -> dict:
    """Read explicit files only. Callers own output storage and registration."""
    if not paths or len(paths) > MAX_SOURCES:
        raise Unavailable('catalog requires 1..256 explicit source files')
    entries, total = [], 0
    for path in paths:
        p = path.resolve(strict=True)
        data = bounded_read(p)
        total += len(data)
        if total > MAX_BYTES:
            raise Unavailable('combined source byte limit exceeded')
        if not data:
            raise Unavailable('empty source cannot identify external content')
        entries.append({'path': str(p), 'sha256': digest(data), 'size': len(data)})
    return {'version': 2, 'sources': entries}


class Guard:
    def __init__(self, root: Path, catalog: Path, scope: Path | None = None):
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise Unavailable('protected root is not a directory')
        self.catalog_path = catalog
        self.entries = None
        self.raws = {}
        self.scope_path = scope

    def covers(self, target: Path) -> bool:
        if self.scope_path is None:
            raise Unavailable('explicit component scope required for mutation inspection')
        return Scope(self.root, self.scope_path).mutation_covers(target)

    def load(self) -> list[dict]:
        if self.entries is not None:
            return self.entries
        catalog_raw = bounded_read(self.catalog_path)
        doc = json.loads(catalog_raw)
        entries = doc.get('sources') if isinstance(doc, dict) else None
        if (not isinstance(doc, dict) or sorted(doc) != ['sources', 'version'] or
                type(doc.get('version')) is not int or doc.get('version') != 2 or
                not isinstance(entries, list) or not 1 <= len(entries) <= MAX_SOURCES):
            raise Unavailable('invalid or empty source catalog')
        total = 0
        for entry in entries:
            if not isinstance(entry, dict):
                raise Unavailable('invalid source entry')
            p = Path(entry['path'])
            if not p.is_absolute() or within(p.resolve(), self.root):
                raise Unavailable('official source must remain outside protected kit')
            raw = bounded_read(p)
            total += len(raw)
            if total > MAX_BYTES:
                raise Unavailable('combined source byte limit exceeded')
            if digest(raw) != entry['sha256'] or len(raw) != entry['size']:
                raise Unavailable('source changed; review and rebuild catalog')
            # Validate derived metadata rather than trusting caller-supplied hashes.
            if (json.dumps(make_catalog([p])['sources'][0], sort_keys=True, allow_nan=False) !=
                    json.dumps(entry, sort_keys=True, allow_nan=False)):
                raise Unavailable('catalog metadata does not match selected source')
            self.raws[entry['path']] = raw
        self.entries = entries
        self.catalog_fingerprint = digest(catalog_raw)
        return entries

    def content(self, data: bytes) -> Result:
        return exact_content(self, data)

    def original_target(self, target: Path) -> bool:
        for entry in self.load():
            source = Path(entry['path'])
            if target == source or (target.exists() and target.samefile(source)):
                return True
        return False

    def outside_result(self, target: Path) -> Result:
        if target.exists() and target.stat().st_nlink > 1:
            return Result('deferred', 'outside hard-link effect requires actual-file inspection')
        return Result('not_applicable', 'target outside protected project')

    def write(self, path: str, data: bytes, cwd: Path) -> Result:
        target = absolute(path, cwd)
        if self.original_target(target):
            return Result('block', 'registered official source modification forbidden')
        if not self.covers(target):
            return self.outside_result(target)
        return self.content(data)

    def edit(self, path: str, old: str, new: str, replace_all: bool, cwd: Path) -> Result:
        target = absolute(path, cwd)
        if self.original_target(target):
            return Result('block', 'registered official source modification forbidden')
        if not self.covers(target):
            return self.outside_result(target)
        if not isinstance(old, str) or not old or not isinstance(new, str):
            raise Unavailable('invalid edit')
        text = bounded_read(target).decode('utf-8')
        n = text.count(old)
        if n == 0 or (not replace_all and n != 1):
            raise Unavailable('edit does not identify a unique existing span')
        return self.content(text.replace(old, new, -1 if replace_all else 1).encode())

    def shell(self, command: str, cwd: Path) -> Result:
        """Limited explicit command contract, not a general shell interpreter.

        Only direct cp operands can be predicted. Other shell work is unresolved
        in the protected project. Outside-cwd calls are unresolved as well: an
        opaque command may address the project with an absolute or hidden path.
        """
        if not isinstance(command, str) or not command.strip():
            return Result('deferred', 'command effect not pre-inspected')
        # Shell constructs, expansions, options and interpreters are not simulated.
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in command):
            return Result('deferred', 'command effect not pre-inspected')
        if any(ch in command for ch in '\n;&|<>$`*?(){}~[]'):
            return Result('deferred', 'command effect not pre-inspected')
        try:
            args = shlex.split(command)
        except ValueError:
            return Result('deferred', 'command effect not pre-inspected')
        if args == ['pwd']:
            return Result('not_applicable', 'pwd has no source mutation')
        if len(args) == 3 and args[0] in ('cp', '/bin/cp', '/usr/bin/cp'):
            if any(a.startswith('-') for a in args[1:]):
                return Result('deferred', 'copy effect not pre-inspected')
            source, target = absolute(args[1], cwd), absolute(args[2], cwd)
            if target.is_dir():
                # cp uses the operand's basename, not the resolved symlink target's.
                target = (target / Path(args[1]).name).resolve(strict=False)
            if self.original_target(target):
                return Result('block', 'registered official source modification forbidden')
            if not self.covers(target):
                return self.outside_result(target)
            entries = self.load()
            if any(source == Path(e['path']) for e in entries):
                return Result('block', 'registered external source copy into protected project')
            return self.content(bounded_read(source))
        return Result('deferred', 'command effect not pre-inspected')


def combine(results: list[Result]) -> Result:
    for status in ('block', 'unavailable', 'deferred', 'pass', 'not_applicable'):
        for result in results:
            if result.status == status:
                return result
    raise Unavailable('no inspectable operation')


def protocol(result: Result) -> dict:
    # No 'allow': this check must not override product permission or other guards.
    if result.status not in ('pass', 'block', 'unavailable', 'not_applicable', 'deferred'):
        result = Result('unavailable', 'invalid inspection result')
    if result.status in ('block', 'unavailable'):
        return {'hookSpecificOutput': {'hookEventName': 'PreToolUse',
                'permissionDecision': 'deny',
                'permissionDecisionReason': f'upstream-guard {result.status}: {result.reason}'}}
    if result.status == 'deferred':
        return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'additionalContext':
            'upstream-guard: not pre-inspected; fresh current-file checks are required before assembly/transfer.'}}
    return {}


def read_payload(stream, expected_event='PreToolUse') -> dict:
    data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise Unavailable('hook input limit exceeded')
    payload = json.loads(data)
    if not isinstance(payload, dict) or payload.get('hook_event_name') != expected_event:
        raise Unavailable('unexpected hook event payload')
    if not isinstance(payload.get('cwd'), str) or not Path(payload['cwd']).is_absolute():
        raise Unavailable('absolute event cwd required')
    return payload


READ_ONLY_TOOLS = ('Read', 'Glob', 'Grep', 'WebSearch', 'WebFetch')
STRUCTURED_FILE_TOOLS = ('Write', 'Edit', 'MultiEdit', 'NotebookEdit')


def structured_file(guard, tool, data, cwd):
    """Known file-mutation names: applicability before candidate reconstruction.

    MultiEdit/NotebookEdit candidates are not reconstructed here. Known target
    mutations require an inspection, rather than taking the opaque-shell path.
    Actual product payload availability remains a separate native test.
    """
    if not isinstance(data, dict):
        raise Unavailable('structured mutation input must be an object')
    field = 'notebook_path' if tool == 'NotebookEdit' else 'file_path'
    path = data.get(field)
    target = absolute(path, cwd)
    if guard.original_target(target):
        return Result('block', 'registered official source modification forbidden')
    if not guard.covers(target):
        return guard.outside_result(target)
    if tool == 'Write':
        if not isinstance(data.get('content'), str):
            raise Unavailable('Write content missing')
        return guard.content(data['content'].encode())
    if tool == 'Edit':
        if type(data.get('replace_all', False)) is not bool:
            raise Unavailable('invalid replace_all')
        return guard.edit(path, data.get('old_string'), data.get('new_string'),
                          data.get('replace_all', False), cwd)
    raise Unavailable('targeted structured mutation candidate reconstruction unsupported')


def post_protocol(report: dict, event: str) -> dict:
    if report['status'] == 'pass' and report.get('complete'):
        return {}
    status = report['status'] if report['status'] in ('block', 'unavailable') else 'unavailable'
    return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext':
        f'upstream-guard current-file inspection: {status}; effects were not undone. '
        'Related assembly/transfer requires a fresh complete gate.'}}


def adapter_main(evaluate):
    import argparse
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--catalog', required=True, type=Path)
    parser.add_argument('--scope', required=True, type=Path)
    parser.add_argument('--event', choices=['PreToolUse', 'PostToolUse', 'PostToolUseFailure'], default='PreToolUse')
    args = parser.parse_args()
    try:
        payload = read_payload(sys.stdin.buffer, args.event)
        if args.event == 'PreToolUse':
            response = protocol(evaluate(Guard(args.root, args.catalog, args.scope), payload))
        elif payload.get('tool_name') in READ_ONLY_TOOLS:
            response = {}
        else:
            from upstream_artifacts import inspect
            response = post_protocol(inspect(args.root, args.catalog, args.scope, 'post'), args.event)
    except Exception:
        response = (protocol(Result('unavailable', 'input, policy or inspection failed'))
                    if args.event == 'PreToolUse' else
                    post_protocol({'status': 'unavailable'}, args.event))
    print(json.dumps(response, ensure_ascii=False))
