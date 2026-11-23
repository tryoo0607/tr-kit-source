#!/usr/bin/env python3
"""Host-local, metadata-only exact session restart batches. No automatic replay."""
import argparse
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import stat
import sys
import time
import uuid

sys.dont_write_bytecode = True

# Import by location so packaged skills need no installation or private dependency.
_spec = importlib.util.spec_from_file_location('session_restart_refresh', Path(__file__).with_name('runtime_refresh.py'))
rr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rr)
Deferred = rr.Deferred


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def uuid_value(value):
    if not isinstance(value, str) or str(uuid.UUID(value)) != value:
        raise Deferred('invalid-uuid')
    return value


def binding():
    """Bind to Linux machine/account/config paths, never to boot/runtime IDs."""
    if sys.platform != 'linux':
        raise Deferred('platform-contract-unverified')
    machine = Path('/etc/machine-id').read_text().strip()
    if not re.fullmatch('[a-f0-9]{32}', machine):
        raise Deferred('machine-identity-unknown')
    profile = {'uid': os.getuid(), 'home': str(Path.home()),
               'codexHome': os.environ.get('CODEX_HOME', str(Path.home() / '.codex')),
               'claudeConfigDir': os.environ.get('CLAUDE_CONFIG_DIR', str(Path.home() / '.claude')),
               'orcaProfile': os.environ.get('ORCA_PROFILE', ''),
               'orcaDevRoot': os.environ.get('ORCA_DEV_REPO_ROOT', '')}
    return {'machine': hashlib.sha256(machine.encode()).hexdigest(),
            'profile': hashlib.sha256(encoded(profile)).hexdigest()}


class Store:
    """Descriptor-anchored 0700 store, signed 0600 records, atomic durable writes.

    flock survives process crashes without a stale-lock deletion procedure. The
    signature catches accidental edits; it is not protection from the account owner.
    """
    def __init__(self, root, read_only=False):
        self.root = Path(root).absolute()
        self.fd = self.lock = None
        self.key = None
        self.read_only = read_only

    def __enter__(self):
        if sys.platform != 'linux' or not all(hasattr(os, x) for x in ('O_NOFOLLOW', 'O_DIRECTORY')):
            raise Deferred('storage-contract-unsupported')
        import fcntl
        try:
            if '..' in self.root.parts:
                raise Deferred('unsafe-state-path')
            self.fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            for part in self.root.parts[1:]:
                if not self.read_only:
                    try:
                        os.mkdir(part, 0o700, dir_fd=self.fd)
                    except FileExistsError:
                        pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.fd)
                os.close(self.fd)
                self.fd = child
            info = os.fstat(self.fd)
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise Deferred('unsafe-state-directory')
            flags = os.O_RDONLY if self.read_only else os.O_RDWR | os.O_CREAT
            self.lock = os.open('batch.lock', flags | os.O_NOFOLLOW | os.O_NONBLOCK,
                                0o600, dir_fd=self.fd)
            self.check_file(self.lock)
            try:
                fcntl.flock(self.lock, (fcntl.LOCK_SH if self.read_only else fcntl.LOCK_EX) | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Deferred('batch-operation-locked') from None
            if not self.read_only:
                try:
                    key_fd = os.open('integrity.key', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                     0o600, dir_fd=self.fd)
                except FileExistsError:
                    pass
                else:
                    with os.fdopen(key_fd, 'wb') as out:
                        out.write(os.urandom(32))
                        out.flush()
                        os.fsync(out.fileno())
                    os.fsync(self.fd)
            self.key = self.read_bytes('integrity.key')
            if len(self.key) != 32:
                raise Deferred('invalid-state-key')
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    @staticmethod
    def check_file(fd):
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 2_000_000):
            raise Deferred('unsafe-state-file')
        return info

    def check_directory(self):
        # Detect pathname replacement before writes/inputs as well as descriptor safety.
        if self.root.resolve() != self.root:
            raise Deferred('state-directory-replaced')
        entry, own = self.root.stat(), os.fstat(self.fd)
        if ((entry.st_dev, entry.st_ino) != (own.st_dev, own.st_ino)
                or own.st_uid != os.getuid() or stat.S_IMODE(own.st_mode) != 0o700):
            raise Deferred('state-directory-replaced')
        lock = os.stat('batch.lock', dir_fd=self.fd, follow_symlinks=False)
        own_lock = self.check_file(self.lock)
        if (lock.st_dev, lock.st_ino) != (own_lock.st_dev, own_lock.st_ino):
            raise Deferred('state-lock-replaced')
        if self.key is not None and self.read_bytes('integrity.key') != self.key:
            raise Deferred('state-key-replaced')

    def read_bytes(self, name):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.fd)
        with os.fdopen(fd, 'rb') as source:
            self.check_file(source.fileno())
            return source.read(2_000_001)

    def load(self, batch_id):
        self.check_directory()
        doc = rr.obj(json.loads(self.read_bytes(uuid_value(batch_id) + '.json')))
        body = rr.obj(doc.get('batch'))
        signature = doc.get('signature')
        if not isinstance(signature, str) or not hmac.compare_digest(signature, self.sign(body)):
            raise Deferred('batch-integrity-mismatch')
        validate_batch(body)
        if body['batchId'] != batch_id:
            raise Deferred('batch-identity-mismatch')
        return body

    def sign(self, body):
        return hmac.new(self.key, encoded(body), hashlib.sha256).hexdigest()

    def save(self, body, new=False):
        if self.read_only:
            raise Deferred('read-only-state')
        self.check_directory()
        validate_batch(body)
        name = uuid_value(body['batchId']) + '.json'
        if new:
            if name in os.listdir(self.fd):
                raise Deferred('batch-already-exists')
        else:
            # Check integrity and file identity before replacing an existing record.
            self.load(body['batchId'])
        data = encoded({'batch': body, 'signature': self.sign(body)})
        if len(data) > 2_000_000:
            raise Deferred('batch-size-limit')
        temporary = '.pending-' + str(uuid.uuid4())
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=self.fd)
            with os.fdopen(fd, 'wb') as out:
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temporary, name, src_dir_fd=self.fd, dst_dir_fd=self.fd)
            os.fsync(self.fd)
        finally:
            try:
                os.unlink(temporary, dir_fd=self.fd)
            except FileNotFoundError:
                pass

    def batches(self):
        return [self.load(name[:-5]) for name in sorted(os.listdir(self.fd))
                if re.fullmatch('[a-f0-9-]{36}\\.json', name)]

    def __exit__(self, *args):
        for attr in ('lock', 'fd'):
            value = getattr(self, attr)
            if value is not None:
                os.close(value)
                setattr(self, attr, None)


def validate_native(native):
    native = rr.obj(native)
    uuid_value(native.get('sessionId'))
    if not rr.token(native.get('cwd')) or not native['cwd'].startswith('/') or not rr.token(native.get('permissions')):
        raise Deferred('invalid-native-identity')
    return native


def validate_batch(batch):
    rr.obj(batch)
    if batch.get('schema') != 1:
        raise Deferred('invalid-batch')
    uuid_value(batch.get('batchId'))
    if set(rr.obj(batch.get('binding'))) != {'machine', 'profile'}:
        raise Deferred('invalid-batch-binding')
    rows = rr.array(batch.get('targets'))
    if not rows or len({row.get('targetId') for row in rows}) != len(rows):
        raise Deferred('duplicate-or-empty-targets')
    native_ids = []
    for row in rows:
        if not rr.token(row.get('targetId')) or row.get('choice') not in ('restart', 'manual'):
            raise Deferred('invalid-batch-target')
        rr.fingerprint(rr.obj(row.get('terminal')))
        if row.get('native') is not None:
            native_ids.append((row.get('provider'), validate_native(row['native'])['sessionId']))
        if row.get('choice') == 'restart' and row.get('state') == 'ready' and row.get('native') is None:
            raise Deferred('native-identity-required')
        if row.get('provider') not in (None, 'codex', 'claude'):
            raise Deferred('invalid-provider')
    if len(native_ids) != len(set(native_ids)):
        raise Deferred('duplicate-native-session')
    rr.array(batch.get('events'))


class Recorder:
    def __init__(self, store, batch, row, operation):
        self.store, self.batch, self.row, self.operation = store, batch, row, operation

    def record(self, phase, **values):
        self.batch['events'].append({'phase': phase, 'targetId': self.row['targetId'],
                                     'operationId': self.operation, 'at': time.time(), **values})
        self.store.save(self.batch)


def local_client(client):
    if getattr(client, 'remote_configured', False) or client.environment:
        raise Deferred('remote-operation-delegate-to-host-session')


def snapshot(client, self_pane):
    local_client(client)
    ts, ps = client.inventory()
    terms = rr.array(ts.get('terminals'))
    for inventory in (ts, ps):
        if inventory.get('truncated') is not False:
            raise Deferred('inventory-incomplete')
        scope = rr.obj(inventory.get('hostScope'))
        if 'local' not in scope.get('hostIds', []):
            raise Deferred('local-host-scope-unknown')
    if len({t.get('handle') for t in terms}) != len(terms):
        raise Deferred('duplicate-target')
    if not self_pane or sum(rr.pane(t) == self_pane for t in terms) != 1:
        raise Deferred('self-unidentified')
    return terms, ps


def target_from(client, item, ps, self_pane):
    if item.get('executionHostId') != 'local':
        raise Deferred('remote-operation-delegate-to-host-session')
    t, frame = client.observe(item['handle'])
    if rr.fingerprint(t) != rr.fingerprint(item):
        raise Deferred('target-changed')
    # First check the entire passive guard before the idle wait. No native input
    # is allowed for an unsafe target, including a freshly busy one.
    provider = t.get('agentIdentity')
    rr.eligible(t, frame, ps, self_pane, True, tui_idle=provider == 'claude')
    rr.wait_idle(client, t)
    rr.eligible(t, frame, ps, self_pane, True, tui_idle=True)
    inventory = rr.plugin_inventory(provider, t['worktreePath'])
    target = {'handle': t['handle'], 'identity': rr.fingerprint(t),
              'provider': provider, 'installation': inventory, 'state': 'idle'}
    rr.installation_guard(target)
    return target


def current_plan(client, self_pane):
    return {'runtimeId': client.runtime, 'selfPane': self_pane}


def prepare(client, store, selected, excluded, self_pane):
    if not selected or len(selected) != len(set(selected)) or len(excluded) != len(set(excluded)):
        raise Deferred('explicit-unique-targets-required')
    check_other_attempts(store)
    terms, ps = snapshot(client, self_pane)
    by_handle = {t['handle']: t for t in terms}
    if any(handle not in by_handle for handle in selected + excluded):
        raise Deferred('unknown-selection')
    own = next(t for t in terms if rr.pane(t) == self_pane)
    try:
        own_provider = rr.agent_for(ps, own).get('agentType')
    except Deferred:
        own_provider = None
    choices = list(dict.fromkeys(selected + excluded + ([own['handle']] if own_provider in ('codex', 'claude') else [])))
    batch = {'schema': 1, 'batchId': str(uuid.uuid4()), 'createdAt': time.time(),
             'binding': binding(), 'hostLabel': socket.gethostname(), 'preparedRuntime': client.runtime, 'prepareState': 'started',
             'targets': [], 'events': []}
    for handle in choices:
        item = by_handle[handle]
        # Providers are metadata hints, never native identity proof.
        try:
            provider = rr.agent_for(ps, item).get('agentType')
        except Deferred:
            provider = None
        if provider not in ('codex', 'claude'):
            provider = None
        manual = handle in excluded or handle == own['handle']
        batch['targets'].append({'targetId': handle, 'terminal': rr.fingerprint(item),
                                 'provider': provider, 'choice': 'manual' if manual else 'restart',
                                 'state': 'manual-restart-required' if manual else 'pending',
                                 'reason': ('requesting-session' if handle == own['handle'] else 'explicit-exception') if manual else None,
                                 'native': None, 'attempt': None})
        if manual and provider is None:
            batch['targets'][-1].update(state='deferred', reason='non-agent-management-shell')
    store.save(batch, new=True)
    stopped = False
    for row in batch['targets']:
        if row['choice'] == 'manual':
            continue
        if stopped:
            row.update(state='deferred', reason='previous-target-failed')
            continue
        log = Recorder(store, batch, row, 'prepare')
        try:
            target = target_from(client, by_handle[row['targetId']], ps, self_pane)
            row['provider'] = target['provider']
            row['installationPrepared'] = target['installation']
            row['native'] = validate_native(rr.native_status(client, current_plan(client, self_pane), target, self_pane, log))
            row.update(state='ready', reason=None)
            store.save(batch)
        except (Deferred, OSError) as error:
            row.update(state='deferred', reason=reason(error))
            if any(e['targetId'] == row['targetId'] and e['phase'] == 'sending' for e in batch['events']):
                batch['prepareState'] = 'uncertain'
            stopped = True
    if batch['prepareState'] != 'uncertain':
        batch['prepareState'] = 'complete'
    batch['events'].append({'phase': 'prepared', 'at': time.time()})
    store.save(batch)
    return report(batch)


def reason(error):
    return str(error) if isinstance(error, Deferred) else 'local-storage-or-io-failed'


def check_other_attempts(store, current=None):
    for batch in store.batches():
        if batch['batchId'] == current:
            continue
        if batch.get('prepareState') != 'complete' or any(
                row.get('attempt') and row['attempt'].get('state') not in ('complete', 'not-submitted')
                for row in batch['targets']):
            raise Deferred('unresolved-batch-inspect-before-new-operation')


def blocked_by_exception(batch, item, runtime):
    for excluded in batch['targets']:
        if excluded['choice'] != 'manual':
            continue
        old = excluded['terminal']
        if rr.pane(item) == rr.pane(old) and item.get('worktreeId') == old['worktreeId']:
            return True
        # After runtime replacement no unknown exception identity may be guessed.
        if runtime != batch['preparedRuntime'] and item.get('worktreeId') == old['worktreeId'] and excluded.get('native') is None:
            return True
    return False


def locate(client, batch, row, self_pane, log=None):
    """Reacquire handles, never use a saved shell/PTY as launch authorization."""
    terms, ps = snapshot(client, self_pane)
    old = row['terminal']
    related = [t for t in terms if t.get('executionHostId') == old['executionHostId']
               and t.get('worktreeId') == old['worktreeId']]
    candidates = []
    for item in related:
        if blocked_by_exception(batch, item, client.runtime) or rr.pane(item) == self_pane:
            # An excluded/own pane can now contain this UUID: absence is uncertain.
            if client.runtime != batch['preparedRuntime']:
                raise Deferred('excluded-identity-unknown-after-runtime-change')
            continue
        t, frame = client.observe(item['handle'])
        if rr.fingerprint(t) != rr.fingerprint(item) or t.get('worktreePath') != old['worktreePath']:
            raise Deferred('workspace-or-target-changed')
        provider = t.get('agentIdentity')
        if provider == row['provider']:
            candidates.append(t)
        elif provider not in ('codex', 'claude'):
            # An empty shell is allowed to remain, but will never receive input.
            text = rr.screen(frame).rstrip().splitlines()
            empty_shell = text and re.fullmatch(r'[^\n]*' + re.escape(old['worktreePath']) + r'[$#]', text[-1])
            if frame.get('draft') not in (None, '') or not empty_shell:
                raise Deferred('unknown-foreground')
    def absent(verified_panes=()):
        # A ps-only agent or an orphan can be the old native session. Never launch
        # a second conversation when inventory cannot prove absence, even if
        # other selected native sessions were verified in this workspace.
        for workspace in rr.array(ps.get('worktrees')):
            if workspace.get('worktreeId') == old['worktreeId']:
                if any(a.get('agentType') == row['provider'] and a.get('paneKey') not in verified_panes
                       for a in rr.array(workspace.get('agents', []))):
                    raise Deferred('unmatched-agent-identity')
        return None
    if not candidates:
        return absent()
    # Only query candidates that the user selected in this batch. Preserve the
    # explicit no-input exceptions even when UUID is not available for them.
    allowed = [r for r in batch['targets'] if r['choice'] == 'restart' and r.get('native') is not None]
    for candidate in candidates:
        if not any(r['provider'] == row['provider'] and r['terminal']['worktreeId'] == candidate['worktreeId']
                   and (rr.pane(r['terminal']) == rr.pane(candidate)
                        or r.get('ownedTerminal') == rr.fingerprint(candidate)) for r in allowed):
            raise Deferred('unselected-or-uncertain-native-candidate')
    targets = [target_from(client, candidate, ps, self_pane) for candidate in candidates]
    if log is None:
        return targets[0], None
    identities = [rr.native_status(client, current_plan(client, self_pane), target, self_pane, log)
                  for target in targets]
    if len({n['sessionId'] for n in identities}) != len(identities):
        raise Deferred('duplicate-native-session')
    for actual in identities:
        expected = [r['native'] for r in allowed if r['provider'] == row['provider']
                    and r['native']['sessionId'] == actual['sessionId']]
        if len(expected) != 1:
            raise Deferred('native-identity-or-permissions-mismatch')
        equal_identity(expected[0], actual)
    matches = [(target, native) for target, native in zip(targets, identities)
               if native['sessionId'] == row['native']['sessionId']]
    if not matches:
        return absent({rr.pane(target['identity']) for target in targets})
    if len(matches) != 1:
        raise Deferred('native-identity-or-permissions-mismatch')
    return matches[0]


def equal_identity(expected, actual, *, resumed=False):
    validate_native(actual)
    if any(expected[k] != actual[k] for k in ('sessionId', 'cwd', 'permissions')):
        raise Deferred('native-identity-or-permissions-mismatch')
    if resumed and expected.get('resumeMode') is not None and expected['resumeMode'] != actual.get('resumeMode'):
        raise Deferred('native-identity-or-permissions-mismatch')


def owned_launch(client, batch, row, self_pane, log, installation):
    # Verify original workspace membership on THIS runtime, with a complete view.
    _, ps = snapshot(client, self_pane)
    old = row['terminal']
    workspaces = [w for w in rr.array(ps.get('worktrees')) if w.get('worktreeId') == old['worktreeId']]
    if (len(workspaces) != 1 or workspaces[0].get('path') != old['worktreePath']
            or workspaces[0].get('hostId') != 'local'):
        raise Deferred('original-workspace-unverified')
    # Close the discovery/launch gap as far as the non-atomic Orca API permits.
    if locate(client, batch, row, self_pane, log) is not None:
        raise Deferred('session-appeared-before-launch')
    current_installation = rr.installation_guard({'provider': row['provider'], 'identity': old,
                                                'installation': installation})
    command = rr.resume_command(row['provider'], row['native'],
                                installed_version=current_installation.get('nativeVersion'))
    log.record('sending', step='owned-restore-terminal')
    result = client.call('terminal', 'create', '--worktree', 'id:' + old['worktreeId'],
                         '--title', 'Session restore', '--command', command)
    # Contract is intentionally strict: a changed/unknown receipt is a partial
    # launch, not permission to create another terminal or fall back to a shell.
    terminal = rr.obj(result.get('terminal'))
    handle = terminal.get('handle')
    if not isinstance(handle, str) or not re.fullmatch(r'term_[A-Za-z0-9_-]+', handle):
        raise Deferred('restore-terminal-receipt-unknown')
    # The creation receipt can be sparse. Prove the returned handle through a
    # fresh show/list; never manufacture missing fingerprint coordinates.
    row['ownedHandle'] = handle
    log.record('accepted', step='owned-restore-terminal', handle=handle)
    terminal, _ = client.observe(handle)
    identity = rr.fingerprint(terminal)
    if (identity['worktreeId'] != old['worktreeId'] or identity['worktreePath'] != old['worktreePath']
            or identity['executionHostId'] != 'local'):
        raise Deferred('restore-terminal-identity-mismatch')
    row['ownedTerminal'] = identity
    log.record('restore-terminal-observed', handle=identity['handle'])
    rr.wait_idle(client, terminal)
    deadline = time.monotonic() + 10
    while True:
        terms, ps = snapshot(client, self_pane)
        matches = [t for t in terms if t.get('handle') == terminal['handle']]
        if len(matches) != 1 or rr.fingerprint(matches[0]) != identity:
            raise Deferred('restore-terminal-changed')
        try:
            target = target_from(client, matches[0], ps, self_pane)
            if target['provider'] != row['provider']:
                raise Deferred('restore-provider-mismatch')
            return target
        except Deferred as error:
            if str(error) not in ('agent-identity-unknown', 'child-state-unknown') or time.monotonic() >= deadline:
                raise
            time.sleep(0.2)


def execute(client, store, batch_id, self_pane, mode):
    if mode not in ('restart', 'restore', 'verify'):
        raise Deferred('invalid-operation')
    batch = store.load(batch_id)
    if batch['binding'] != binding():
        raise Deferred('machine-or-profile-mismatch')
    if batch.get('prepareState') != 'complete':
        raise Deferred('preparation-incomplete-inspect-record')
    check_other_attempts(store, batch_id)
    snapshot(client, self_pane)
    for index, row in enumerate(batch['targets']):
        if row['choice'] == 'manual':
            continue
        if row.get('native') is None:
            # Unsafe targets never get a later implicit preparation/status query.
            continue
        if mode == 'restart' and row['provider'] == 'claude':
            row.update(state='manual-restart-required', reason='claude-clean-exit-contract-unverified')
            store.save(batch)
            continue
        prior = row.get('attempt')
        if prior and prior.get('state') not in ('complete', 'not-submitted', 'verified-running-restart-pending') and mode != 'verify':
            row.update(state='deferred', reason='unresolved-attempt-verify-before-any-recovery')
            defer_later(batch, index)
            store.save(batch)
            break
        operation = str(uuid.uuid4())
        if mode != 'verify':
            row['attempt'] = {'operationId': operation, 'mode': mode, 'state': 'started'}
            store.save(batch)
        log = Recorder(store, batch, row, operation)
        try:
            found = locate(client, batch, row, self_pane, log)
            needs_resume = ((found is None and mode == 'restore') or
                            (found is not None and mode == 'restart' and not (prior and prior.get('state') == 'complete')))
            if needs_resume:
                native = row['native'] if found is None else found[1]
                try:
                    installation = (rr.plugin_inventory(row['provider'], native['cwd']) if found is None
                                    else found[0]['installation'])
                    if installation.get('state') != 'observed':
                        raise Deferred('installed-versions-unverified')
                    command = rr.resume_command(row['provider'], native,
                                                installed_version=installation.get('nativeVersion'))
                except Deferred as error:
                    row.update(state='manual-restart-required', reason=str(error))
                    row['attempt']['state'] = 'not-submitted'
                    log.record('manual-restart-required', reason=row['reason'])
                    continue
            if found is None:
                if mode != 'restore':
                    raise Deferred('session-absent-use-explicit-restore')
                target = owned_launch(client, batch, row, self_pane, log, installation)
                after = rr.native_status(client, current_plan(client, self_pane), target, self_pane, log)
                equal_identity(row['native'], after, resumed=True)
                state = 'restarted'
            else:
                target, before = found
                plan = current_plan(client, self_pane)
                equal_identity(row['native'], before)
                if mode == 'verify' and prior and prior.get('state') != 'complete':
                    # The same live UUID can still be the original, never-exited
                    # process. A status query alone is not restart proof.
                    observed_exit = any(e.get('operationId') == prior['operationId']
                                        and e['phase'] == 'native-exit-observed' for e in batch['events'])
                    observed_owned = row.get('ownedTerminal') == target['identity']
                    if not observed_exit and not observed_owned:
                        row.update(state='deferred', reason='live-identity-confirmed-restart-unproven',
                                   nativeObserved=before, currentTerminal=target['identity'])
                        prior['state'] = 'verified-running-restart-pending'
                        defer_later(batch, index)
                        log.record('verified-running-only')
                        break
                    equal_identity(row['native'], before, resumed=True)
                if mode != 'restart' or (prior and prior.get('state') == 'complete'):
                    after, state = before, 'already-running'
                else:
                    # Claude clean-exit evidence is not established by reload or
                    # by a guessed shell marker. Do not send /exit until proven.
                    _, frame = rr.guard(client, plan, target, self_pane)
                    cursor = frame.get('latestCursor')
                    if not re.fullmatch(r'\d+', str(cursor)):
                        raise Deferred('native-exit-freshness-unknown')
                    evidence = {'sessionId': before['sessionId'], 'cursor': cursor}
                    rr.send(client, log, target, '/exit', 'normal-exit')
                    deadline = time.monotonic() + 10
                    while True:
                        try:
                            rr.shell_guard(client, plan, target, evidence)
                            break
                        except Deferred as error:
                            if str(error) != 'shell-unconfirmed' or time.monotonic() >= deadline:
                                raise
                            time.sleep(0.2)
                    rr.shell_guard(client, plan, target, evidence)
                    log.record('native-exit-observed', sessionId=before['sessionId'])
                    rr.send(client, log, target, command, 'exact-resume')
                    rr.wait_resumed(client, plan, target, self_pane)
                    after = rr.native_status(client, plan, target, self_pane, log)
                    equal_identity(before, after, resumed=True)
                    state = 'restarted'
            row.update(state=state, reason=None, nativeObserved=after,
                       currentTerminal=target['identity'], installationObserved=rr.installation_guard(target),
                       consumption='unverified', consumedVersion=None)
            if row.get('attempt'):
                # Lost receipts require both fresh identity and independent exit
                # or owned-terminal evidence above.
                row['attempt']['state'] = 'complete'
            log.record('verified', result=state)
        except (Deferred, OSError) as error:
            sent = any(e.get('operationId') == operation and e['phase'] == 'sending' for e in batch['events'])
            row.update(state='failed' if sent else 'deferred', reason=reason(error))
            if row.get('attempt') and mode != 'verify':
                row['attempt']['state'] = 'uncertain' if sent else 'not-submitted'
            defer_later(batch, index)
            # If persistence failed, the previous durable sending record remains
            # authoritative. Never perform another action to repair the receipt.
            try:
                log.record('stopped', reason=row['reason'])
            except (Deferred, OSError):
                row['reason'] = 'storage-failed-inspect-existing-record'
            break
    return report(batch)


def defer_later(batch, index):
    for row in batch['targets'][index+1:]:
        if row['choice'] == 'restart' and row.get('native') is not None:
            row.update(state='deferred', reason='previous-target-failed')


def report(batch):
    result = {'batchId': batch['batchId'], 'createdAt': batch['createdAt'], 'targets': []}
    for row in batch['targets']:
        result['targets'].append({'targetId': row['targetId'], 'host': batch['hostLabel'],
                                  'tabId': row['terminal']['tabId'], 'leafId': row['terminal']['leafId'],
                                  'workspace': row['terminal']['worktreePath'], 'provider': row['provider'],
                                  'sessionId': (row.get('native') or {}).get('sessionId'),
                                  'state': row['state'], 'reason': row['reason'],
                                  'nativePrepared': row.get('native'), 'nativeObserved': row.get('nativeObserved'),
                                  'installationPrepared': row.get('installationPrepared'),
                                  'installationObserved': row.get('installationObserved'),
                                  'consumption': row.get('consumption', 'unverified'),
                                  'consumedVersion': None})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'list', 'restart', 'restore', 'verify'))
    parser.add_argument('--target', action='append', default=[])
    parser.add_argument('--exclude', action='append', default=[])
    parser.add_argument('--batch')
    parser.add_argument('--state', type=Path, default=Path.home() / '.local/state/tr-kit/session-restart')
    args = parser.parse_args(argv)
    try:
        if args.mode != 'prepare' and (args.target or args.exclude):
            raise Deferred('choices-are-prepare-only')
        if args.mode == 'prepare' and args.batch:
            raise Deferred('prepare-creates-new-batch')
        if args.mode == 'list' and not os.path.lexists(args.state):
            if args.batch:
                raise Deferred('batch-not-found')
            print('{"batches": []}')
            return 0
        with Store(args.state, read_only=args.mode == 'list') as store:
            if args.mode == 'list':
                # Durable inventory needs no runtime, conversation or host CLI.
                result = report(store.load(args.batch)) if args.batch else {'batches': [report(b) for b in store.batches()]}
            elif args.mode == 'prepare':
                result = prepare(rr.Orca(), store, args.target, args.exclude, os.environ.get('ORCA_PANE_KEY'))
            else:
                if not args.batch:
                    raise Deferred('batch-id-required')
                result = execute(rr.Orca(), store, args.batch, os.environ.get('ORCA_PANE_KEY'), args.mode)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if any(t['state'] in ('failed', 'deferred') for t in result.get('targets', [])) else 0
    except (Deferred, OSError, ValueError, TypeError, KeyError):
        error = sys.exc_info()[1]
        print(json.dumps({'state': 'deferred', 'reason': reason(error) if isinstance(error, (Deferred, OSError)) else 'invalid-input-or-record'}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
