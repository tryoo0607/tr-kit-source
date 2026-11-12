#!/usr/bin/env python3
"""Conservative Orca/native runtime refresh. stdout contains metadata only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import time
import uuid


class Deferred(Exception):
    pass


def obj(value):
    if not isinstance(value, dict):
        raise Deferred('invalid-json-shape')
    return value


def array(value):
    if not isinstance(value, list) or any(not isinstance(x, dict) for x in value):
        raise Deferred('invalid-json-shape')
    return value


def token(value):
    return isinstance(value, str) and 0 < len(value) <= 1024 and not any(ord(c) < 32 for c in value)


def pane(t):
    return str(t.get('tabId', '')) + ':' + str(t.get('leafId', ''))


def fingerprint(t):
    if not isinstance(t.get('handle'), str) or not re.fullmatch(r'term_[A-Za-z0-9_-]+', t['handle']):
        raise Deferred('invalid-terminal-handle')
    keys = ('handle', 'ptyId', 'incarnationId', 'worktreeId', 'worktreePath', 'executionHostId', 'tabId', 'leafId')
    if any(not token(t.get(k)) for k in keys):
        raise Deferred('identity-unknown')
    return {k: t[k] for k in keys}


class Orca:
    def __init__(self, environment=None, timeout=15):
        self.environment = environment or os.environ.get('ORCA_ENVIRONMENT')
        self.remote_configured = bool(self.environment or os.environ.get('ORCA_PAIRING_CODE'))
        configured = os.environ.get('ORCA_CLI_COMMAND', '').strip()
        self.executable = configured or ('orca-dev' if os.environ.get('ORCA_DEV_REPO_ROOT') else
                                         'orca-ide' if sys.platform == 'linux' and not os.environ.get('ORCA_PANE_KEY') else 'orca')
        self.timeout = timeout
        self.runtime = None

    def call(self, *args):
        command = [self.executable, *args, '--json']
        if self.environment:
            command += ['--environment', self.environment]
        try:
            p = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout,
                               check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise Deferred('cli-unavailable-or-timeout') from None
        # Never relay CLI stderr, screen text, prompts, or parser exceptions.
        try:
            data = obj(json.loads(p.stdout))
            if p.returncode or data.get('ok') is not True:
                raise Deferred('cli-failed')
            runtime = obj(data.get('_meta')).get('runtimeId')
            if not token(runtime):
                raise Deferred('runtime-unknown')
            if self.runtime is not None and self.runtime != runtime:
                raise Deferred('runtime-changed')
            self.runtime = runtime
            return obj(data.get('result'))
        except (ValueError, TypeError):
            raise Deferred('invalid-json') from None

    def inventory(self):
        ts = self.call('terminal', 'list')
        ps = self.call('worktree', 'ps')
        for data in (ts, ps):
            if data.get('truncated') is not False:
                raise Deferred('inventory-incomplete')
            scope = obj(data.get('hostScope'))
            if not isinstance(scope.get('hostIds'), list):
                raise Deferred('host-scope-unknown')
        return ts, ps

    def observe(self, handle):
        t = obj(self.call('terminal', 'show', '--terminal', handle).get('terminal'))
        r = obj(self.call('terminal', 'read', '--terminal', handle, '--screen').get('terminal'))
        return t, r


def screen(read):
    tail = read.get('tail')
    if read.get('source') != 'screen' or not isinstance(tail, list) or any(not isinstance(x, str) for x in tail):
        raise Deferred('screen-unknown')
    # ANSI sequences must not turn controls or hidden draft text into an empty prompt.
    if any('\x1b' in line for line in tail):
        raise Deferred('screen-controls')
    return '\n'.join(tail)


def idle_screen(provider, read):
    if read.get('draft') not in (None, ''):
        raise Deferred('draft')
    text = screen(read)
    if re.search(r'(?i)(conversation is open in another app|close it there and press|r retry.*f fork)', text):
        raise Deferred('native-session-in-use')
    prompt = '›' if provider == 'codex' else '❯'
    lines = text.splitlines()
    prompts = [line.strip() for line in lines if line.lstrip().startswith(prompt)]
    if not prompts:
        raise Deferred('idle-prompt-unknown')
    placeholder = provider == 'codex' and prompts[-1] == '› Ask Codex to do anything' and 'OpenAI Codex (v0.167.1)' in text
    if prompts[-1] != prompt and not placeholder:
        raise Deferred('draft')
    # A prompt may remain on screen behind a dialog. Refuse known menus and approvals.
    dialog_text = '\n'.join(line for line in lines if not re.match(r'^\s*(?:Permissions|Permission mode)\s*:', line))
    if re.search(r'(?im)((?<![-\w])approve\b|(?<![-\w])approvals?\b|allow once|trust this|select an option|esc to cancel|enter to confirm|yes, proceed)', dialog_text):
        raise Deferred('approval-or-menu')
    return text


def agent_for(ps, t):
    found = []
    for w in array(ps.get('worktrees')):
        if w.get('worktreeId') == t.get('worktreeId'):
            for a in array(w.get('agents', [])):
                if a.get('paneKey') == pane(t):
                    found.append(a)
    if len(found) != 1:
        raise Deferred('agent-identity-unknown')
    return found[0]


def eligible(t, read, ps, self_pane, self_found, tui_idle=False, modal=False):
    fingerprint(t)
    if not self_found:
        raise Deferred('self-unidentified')
    if pane(t) == self_pane:
        raise Deferred('self')
    if t.get('orphaned') is not False or t.get('connected') is not True or t.get('writable') is not True:
        raise Deferred('terminal-unavailable')
    if t.get('agentWait') is not None:
        raise Deferred('approval-or-wait')
    a = agent_for(ps, t)
    provider = t.get('agentIdentity')
    if provider not in ('codex', 'claude') or a.get('agentType') != provider or a.get('structuredHostOwned') is True:
        raise Deferred('provider-or-structured-unsupported')
    if a.get('parentPaneKey') or a.get('children') or a.get('subagents'):
        raise Deferred('child-work')
    main = obj(a.get('mainAgent'))
    missing_claude_program = provider == 'claude' and a.get('programStatus') is None
    program = {} if missing_claude_program else obj(a.get('programStatus'))
    claude_completion = (missing_claude_program and tui_idle and
                         a.get('state') == main.get('state') == 'done')
    observation = a.get('subagentObservation')
    # Native Codex and Claude omit empty rosters; their aggregate state folds tracked work.
    omitted_empty_native = (provider in ('codex', 'claude') and observation is None and
                           'children' not in a and 'subagents' not in a and
                           a.get('state') == main.get('state') == 'done' and
                           (program.get('state') in ('done', 'idle') or claude_completion))
    if observation != 'live' and not omitted_empty_native:
        raise Deferred('child-state-unknown')
    if a.get('state') not in ('idle', 'done') or main.get('state') not in ('idle', 'done') or (program.get('state') not in ('idle', 'done') and not claude_completion):
        raise Deferred('busy-or-state-unknown')
    if not modal:
        idle_screen(provider, read)
    return provider


def native_command(provider, args, cwd):
    if provider not in ('codex', 'claude'):
        raise Deferred('provider-unsupported')
    try:
        p = subprocess.run([provider, *args], cwd=cwd, capture_output=True, text=True,
                           timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Deferred('native-cli-unavailable-or-timeout') from None
    if p.returncode:
        raise Deferred('native-cli-failed')
    return p.stdout


def manifest_metadata(path, plugin_id):
    path = Path(path)
    if not path.is_absolute():
        raise Deferred('manifest-location-unknown')
    fd = os.open(path / '.claude-plugin/plugin.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 1_000_000:
            raise Deferred('manifest-unreadable')
        content = f.read()
    manifest = obj(json.loads(content))
    if manifest.get('name') != plugin_id.split('@')[0]:
        raise Deferred('manifest-identity-mismatch')
    dependencies = manifest.get('dependencies', [])
    if not isinstance(dependencies, list):
        raise Deferred('dependency-shape-unknown')
    normalized = []
    for dep in dependencies:
        if isinstance(dep, str):
            name, version = dep, None
        elif isinstance(dep, dict) and set(dep) <= {'name', 'marketplace', 'version'}:
            name, version = dep.get('name'), dep.get('version')
            if dep.get('marketplace') is not None:
                if not token(dep['marketplace']) or not token(name) or '@' in name:
                    raise Deferred('dependency-shape-unknown')
                name += '@' + dep['marketplace']
        else:
            raise Deferred('dependency-shape-unknown')
        if not token(name) or (version is not None and (not token(version) or not re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][A-Za-z0-9_.-]+)?', version))):
            raise Deferred('dependency-version-or-name-unknown')
        if '@' not in name:
            if '@' not in plugin_id:
                raise Deferred('dependency-marketplace-unknown')
            name += '@' + plugin_id.rsplit('@', 1)[1]
        normalized.append({'id': name, 'version': version})
    return {'manifestSha256': hashlib.sha256(content).hexdigest(),
            'dependencies': sorted(normalized, key=lambda x: (x['id'], x['version'] or ''))}


def plugin_inventory(provider, cwd):
    """Read native installed metadata only, never infer running-session consumption."""
    base = {'provider': provider, 'scope': 'caller-config-at-cwd', 'cwd': cwd,
            'source': 'native-plugin-list', 'consumption': 'unverified'}
    try:
        version = native_command(provider, ['--version'], cwd).strip()
        match = re.fullmatch(r'(?:codex-cli\s+)?(\d+\.\d+\.\d+(?:[-+][A-Za-z0-9_.-]+)?)(?:\s+\(Claude Code\))?', version)
        if not match:
            raise Deferred('native-version-unknown')
        data = json.loads(native_command(provider, ['plugin', 'list', '--json'], cwd))
        entries = array(obj(data).get('installed')) if provider == 'codex' else array(data)
        plugins = []
        dependencies_ready = True
        for entry in entries:
            ident = entry.get('pluginId' if provider == 'codex' else 'id')
            installed_version = entry.get('version')
            enabled = entry.get('enabled')
            scope = 'user' if provider == 'codex' else entry.get('scope')
            if (not token(ident) or not token(installed_version) or type(enabled) is not bool or
                    scope not in ('user', 'project', 'local', 'managed', 'session', 'synced')):
                raise Deferred('plugin-inventory-shape-unknown')
            if provider == 'codex' and entry.get('installed') is not True:
                raise Deferred('plugin-installation-unknown')
            item = {'id': ident, 'version': installed_version, 'enabled': enabled, 'scope': scope}
            if provider == 'claude' and enabled:
                try:
                    item.update(manifest_metadata(entry.get('readFromFolder') or entry.get('installPath'), ident))
                    item['manifestState'] = 'observed'
                except (Deferred, OSError, ValueError, TypeError):
                    item.update(manifestState='unverified', dependencies=[], manifestSha256=None)
                    dependencies_ready = False
                # Native list may report missing package/dependency or load diagnostics.
                # Refuse every diagnostic; never echo its possibly private contents.
                if any(not isinstance(entry.get(k, []), list) or entry.get(k)
                       for k in ('errors', 'notes', 'errorDetails', 'noteDetails')):
                    dependencies_ready = False
                if installed_version == 'unknown':
                    dependencies_ready = False
            plugins.append(item)
        plugins.sort(key=lambda x: (x['id'], x['scope']))
        if len({(p['id'], p['scope']) for p in plugins}) != len(plugins):
            raise Deferred('plugin-installation-ambiguous')
        if provider == 'claude':
            enabled_by_id = {}
            for p in plugins:
                if p['enabled']:
                    enabled_by_id.setdefault(p['id'], []).append(p)
            for p in plugins:
                if not p['enabled']:
                    continue
                for dep in p['dependencies']:
                    matches = enabled_by_id.get(dep['id'], [])
                    if len(matches) != 1 or (dep['version'] is not None and matches[0]['version'] != dep['version']):
                        dependencies_ready = False
        return {**base, 'state': 'observed', 'nativeVersion': match[1], 'plugins': plugins,
                'dependenciesReady': dependencies_ready if provider == 'claude' else None}
    except (Deferred, OSError, ValueError, TypeError):
        error = sys.exc_info()[1]
        return {**base, 'state': 'unverified', 'reason': str(error) if isinstance(error, Deferred) else 'native-inventory-unreadable'}


def installation_guard(target):
    expected = obj(target.get('installation'))
    current = plugin_inventory(target['provider'], target['identity']['worktreePath'])
    if expected.get('state') != 'observed' or current.get('state') != 'observed':
        raise Deferred('installed-versions-unverified')
    if current != expected:
        raise Deferred('installed-versions-drift')
    return current


def installed_versions(inventory):
    return {p['id'] + ':' + p['scope']: p['version'] for p in inventory['plugins']}


def inspect(client, self_pane):
    ts, ps = client.inventory()
    terms = array(ts.get('terminals'))
    handles = [t.get('handle') for t in terms]
    if len(set(handles)) != len(handles):
        raise Deferred('duplicate-target')
    self_found = bool(self_pane) and sum(pane(t) == self_pane for t in terms) == 1
    rows = []
    installations = {}
    for item in terms:
        row = {k: item.get(k) for k in ('handle', 'incarnationId', 'worktreePath', 'executionHostId')}
        try:
            fingerprint(item)
            t, r = client.observe(item['handle'])
            if fingerprint(t) != fingerprint(item):
                raise Deferred('target-changed')
            provider = t.get('agentIdentity')
            if provider in ('codex', 'claude'):
                row['provider'] = provider
                key = (provider, t['worktreePath'])
                if key not in installations:
                    installations[key] = (plugin_inventory(*key) if not getattr(client, 'remote_configured', False) and t['executionHostId'] == 'local' else
                                          {'state': 'unverified', 'reason': 'remote-installation-delegate-to-host-session'})
                row['installation'] = installations[key]
            observed_idle = False
            if provider == 'claude' and pane(t) != self_pane and self_found and agent_for(ps, t).get('programStatus') is None:
                wait_idle(client, {'handle': t['handle']})
                observed_idle = True
            row['provider'] = eligible(t, r, ps, self_pane, self_found, tui_idle=observed_idle)
            row['identity'] = fingerprint(t)
            row['state'] = 'idle'
            row['reason'] = None
        except Deferred as e:
            row['state'] = 'deferred'
            row['reason'] = str(e)
        rows.append(row)
    structured = []
    for w in array(ps.get('worktrees')):
        for a in array(w.get('agents', [])):
            if a.get('structuredHostOwned') is True:
                structured.append({'pane': a.get('paneKey'), 'provider': a.get('agentType'),
                                   'host': w.get('hostId'), 'cwd': w.get('path'),
                                   'state': 'deferred', 'reason': 'structured-unsupported'})
    scope = ts['hostScope']
    return {'schema': 1, 'runtimeId': client.runtime, 'selfPane': self_pane if self_found else None,
            'environment': client.environment, 'remoteConfigured': getattr(client, 'remote_configured', False),
            'hostScope': {k: scope.get(k) for k in ('hostIds', 'omittedHostIds', 'omittedHostSelectors')},
            'targets': rows, 'structured': structured}


def make_plan(report, selected):
    if not selected or len(selected) != len(set(selected)):
        raise Deferred('explicit-unique-targets-required')
    rows = {r['handle']: r for r in report['targets']}
    if any(h not in rows for h in selected):
        raise Deferred('unknown-selection')
    if any(rows[h]['state'] != 'idle' or rows[h].get('installation', {}).get('state') != 'observed' for h in selected):
        raise Deferred('selection-deferred')
    return {'schema': 1, 'operationId': str(uuid.uuid4()), 'createdAt': time.time(),
            'runtimeId': report['runtimeId'], 'selfPane': report['selfPane'],
            'environment': report['environment'], 'remoteConfigured': report.get('remoteConfigured', False), 'targets': [rows[h] for h in selected]}


def status(provider, text):
    # Native status output is used only for these metadata fields; never persisted verbatim.
    def field(names):
        matches = re.findall(r'(?im)^\s*[│|]?\s*(?:' + names + r')\s*:\s*(.*?)\s*[│|]?\s*$', text)
        if not matches:
            raise Deferred('native-identity-unknown')
        return matches[-1].strip()
    ident = field('Session|Session ID')
    try:
        if str(uuid.UUID(ident)) != ident.lower():
            raise ValueError()
    except ValueError:
        raise Deferred('native-identity-unknown') from None
    cwd = field('Directory|cwd|Working directory')
    permission = field('Permissions|Permission mode')
    if not cwd.startswith('/') or not token(cwd) or not token(permission):
        raise Deferred('native-identity-unknown')
    result = {'sessionId': ident, 'cwd': cwd, 'permissions': permission}
    if provider == 'claude':
        result['nativeVersion'] = field('Version')
    return result


class Journal:
    """Descriptor-anchored journal: no symlink traversal, replacement, or replay."""
    def __init__(self, root, operation):
        self.root = Path(root).absolute()
        self.operation = str(uuid.UUID(operation))
        self.name = self.operation + '.json'
        self.path = self.root / self.name
        self.events = []
        self.directory_fd = self.lock_fd = self.record_fd = None

    def __enter__(self):
        if not all(hasattr(os, flag) for flag in ('O_NOFOLLOW', 'O_DIRECTORY')):
            raise Deferred('journal-no-follow-unsupported-on-host')
        if '..' in self.root.parts:
            raise Deferred('unsafe-journal-path')
        try:
            # Open each parent relative to its already-open directory. Checking a
            # resolved path before opening would leave a symlink replacement race.
            directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                for part in self.root.parts[1:]:
                    try:
                        os.mkdir(part, 0o700, dir_fd=directory)
                    except FileExistsError:
                        pass
                    child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                    os.close(directory)
                    directory = child
                self.directory_fd = directory
            except BaseException:
                os.close(directory)
                raise
            info = os.fstat(directory)
            if info.st_uid != os.getuid() or info.st_mode & 0o022:
                raise Deferred('unsafe-journal-directory')
            try:
                self.lock_fd = os.open('apply.lock', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                       0o600, dir_fd=directory)
            except FileExistsError:
                raise Deferred('apply-locked-inspect-journal') from None
            if self.name in os.listdir(directory):
                raise Deferred('operation-already-started-inspect-journal')
            for name in os.listdir(directory):
                if not name.endswith('.json'):
                    continue
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
                with os.fdopen(fd) as f:
                    info = os.fstat(f.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 2_000_000:
                        raise Deferred('unsafe-journal-record')
                    data = obj(json.load(f))
                events = data.get('events')
                if not isinstance(events, list) or not events or obj(events[-1]).get('phase') != 'finished':
                    raise Deferred('unresolved-operation-inspect-journal')
            self.record_fd = os.open(self.name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                     0o600, dir_fd=directory)
            self.record('started')
            return self
        except BaseException as error:
            self.__exit__(None, None, None)
            if isinstance(error, Deferred):
                raise
            if isinstance(error, (OSError, ValueError, TypeError)):
                raise Deferred('unsafe-or-unreadable-journal') from None
            raise

    def record(self, phase, **values):
        info = os.fstat(self.record_fd)
        entry = os.stat(self.name, dir_fd=self.directory_fd, follow_symlinks=False)
        if (not stat.S_ISREG(entry.st_mode) or info.st_nlink != 1 or
                (entry.st_dev, entry.st_ino) != (info.st_dev, info.st_ino)):
            raise Deferred('journal-record-replaced')
        self.events.append({'phase': phase, **values})
        data = json.dumps({'operationId': self.operation, 'events': self.events}).encode()
        os.lseek(self.record_fd, 0, os.SEEK_SET)
        os.ftruncate(self.record_fd, 0)
        while data:
            written = os.write(self.record_fd, data)
            data = data[written:]
        os.fsync(self.record_fd)
        os.fsync(self.directory_fd)

    def __exit__(self, *args):
        if self.record_fd is not None:
            os.close(self.record_fd)
            self.record_fd = None
        if self.lock_fd is not None:
            try:
                actual = os.stat('apply.lock', dir_fd=self.directory_fd, follow_symlinks=False)
                own = os.fstat(self.lock_fd)
                if (actual.st_dev, actual.st_ino) == (own.st_dev, own.st_ino):
                    os.unlink('apply.lock', dir_fd=self.directory_fd)
            except FileNotFoundError:
                pass
            os.close(self.lock_fd)
            self.lock_fd = None
        if self.directory_fd is not None:
            os.close(self.directory_fd)
            self.directory_fd = None


def guard(client, plan, target, self_pane, modal=False):
    installation_guard(target)
    wait_idle(client, target)
    ts, ps = client.inventory()
    if client.runtime != plan['runtimeId']:
        raise Deferred('runtime-changed')
    terms = array(ts.get('terminals'))
    self_found = self_pane == plan['selfPane'] and sum(pane(t) == self_pane for t in terms) == 1
    matches = [t for t in terms if t.get('handle') == target['handle']]
    if len(matches) != 1 or fingerprint(matches[0]) != target['identity']:
        raise Deferred('target-changed')
    t, read = client.observe(target['handle'])
    if fingerprint(t) != target['identity']:
        raise Deferred('target-changed')
    if eligible(t, read, ps, self_pane, self_found, tui_idle=True, modal=modal) != target['provider']:
        raise Deferred('provider-changed')
    return t, read


def send(client, journal, target, text, phase):
    # Persist before calling the transport. Crash/timeout means no automatic resend.
    journal.record('sending', handle=target['handle'], step=phase)
    result = client.call('terminal', 'send', '--terminal', target['handle'], '--text', text, '--enter')
    receipt = obj(result.get('send'))
    mutation = obj(result.get('mutation'))
    request = mutation.get('requestId')
    if receipt.get('accepted') is not True or not token(request):
        raise Deferred('send-receipt-unknown')
    prompt = receipt.get('prompt')
    if prompt is not None and obj(prompt).get('processIncarnation') != target['identity']['incarnationId']:
        raise Deferred('send-incarnation-mismatch')
    journal.record('accepted', handle=target['handle'], step=phase, requestId=request)
    return result


def wait_idle(client, target):
    result = client.call('terminal', 'wait', '--terminal', target['handle'], '--for', 'tui-idle', '--timeout-ms', '10000')
    if obj(result.get('wait')).get('satisfied') is not True:
        raise Deferred('idle-wait-unsatisfied')


def native_status(client, plan, target, self_pane, journal):
    _, fresh = native_query(client, plan, target, self_pane, journal, '/status', 'status')
    identity = status(target['provider'], fresh)
    if identity['cwd'] != target['identity']['worktreePath']:
        raise Deferred('cwd-mismatch')
    return identity


def shell_guard(client, plan, target, normal_exit):
    installation_guard(target)
    ts, ps = client.inventory()
    matches = [t for t in array(ts.get('terminals')) if t.get('handle') == target['handle']]
    if client.runtime != plan['runtimeId'] or len(matches) != 1 or fingerprint(matches[0]) != target['identity']:
        raise Deferred('target-changed')
    if sum(pane(t) == plan['selfPane'] for t in array(ts.get('terminals'))) != 1:
        raise Deferred('self-unidentified')
    t, read = client.observe(target['handle'])
    if fingerprint(t) != target['identity'] or t.get('agentWait') is not None or t.get('connected') is not True or t.get('writable') is not True or t.get('orphaned') is not False:
        raise Deferred('shell-unconfirmed')
    # Require a visible empty shell prompt and no still-tracked live agent/child work.
    text = screen(read).rstrip()
    if read.get('draft') not in (None, ''):
        raise Deferred('draft')
    shell_prompt = r'[^\n]*' + re.escape(target['identity']['worktreePath']) + r'[$#]'
    if not re.fullmatch(shell_prompt, text.splitlines()[-1] if text else ''):
        raise Deferred('shell-unconfirmed')
    for w in array(ps.get('worktrees')):
        for a in array(w.get('agents', [])):
            if a.get('paneKey') != pane(t):
                continue
            if (a.get('state') not in ('done', 'idle') or a.get('children') or a.get('subagents') or
                    a.get('parentPaneKey') or a.get('subagentObservation') == 'unverifiable'):
                raise Deferred('shell-unconfirmed')
            if obj(a.get('mainAgent')).get('state') not in ('done', 'idle'):
                raise Deferred('shell-unconfirmed')
            # The native program's OSC facet may disappear after its clean exit.
            if a.get('programStatus') is not None and obj(a['programStatus']).get('state') not in ('done', 'idle'):
                raise Deferred('shell-unconfirmed')
    if not isinstance(normal_exit, dict) or not re.fullmatch(r'\d+', str(normal_exit.get('cursor', ''))):
        raise Deferred('native-exit-freshness-unknown')
    try:
        session_id = str(uuid.UUID(normal_exit['sessionId']))
    except (KeyError, ValueError, TypeError):
        raise Deferred('native-exit-identity-unknown') from None
    delta = obj(client.call('terminal', 'read', '--terminal', target['handle'], '--cursor', str(normal_exit['cursor'])).get('terminal'))
    lines = delta.get('tail')
    if delta.get('source') != 'stream' or not isinstance(lines, list) or any(not isinstance(line, str) for line in lines):
        raise Deferred('native-exit-stream-unknown')
    # This must be emitted AFTER our guarded /exit. A historical command, a
    # launch/detection identity hint, or a changed PTY is not clean-exit evidence.
    text = '\n'.join(lines)
    exit_marker = (r'To continue this session, run:?\s+codex resume\s+' +
                   re.escape(session_id) + r'(?![A-Za-z0-9-])')
    if not re.search(exit_marker, text):
        raise Deferred('shell-unconfirmed')

    return t


def claude_modal(text, command):
    if re.search(r'(?im)((?<![-\w])approve\b|allow once|trust this|select an option|enter to confirm|yes, proceed)', text):
        return False
    if command == '/status':
        return bool(re.search(r'(?m)^\s*Settings\s+Status\s+Config\s+Usage\s+Stats\s*$', text) and
                    'Esc to cancel' in text)
    if command == '/help':
        return bool(re.search(r'(?m)^\s*Help\s+General\s+Commands\s+Custom commands\s*$', text) and
                    'Esc to cancel' in text)
    return False


def modal_key(client, plan, target, self_pane, journal, command, key):
    _, read = guard(client, plan, target, self_pane, modal=True)
    if not claude_modal(screen(read), command):
        raise Deferred('claude-modal-boundary-unknown')
    journal.record('sending', handle=target['handle'], step='modal-navigation')
    result = client.call('terminal', 'send', '--terminal', target['handle'], '--text', key)
    receipt = obj(result.get('send'))
    if (receipt.get('handle') != target['handle'] or receipt.get('accepted') is not True or
            type(receipt.get('bytesWritten')) is not int or receipt['bytesWritten'] != len(key.encode('utf-8'))):
        raise Deferred('send-receipt-unknown')
    metadata = {'handle': receipt['handle'], 'accepted': True, 'bytesWritten': receipt['bytesWritten']}
    if 'prompt' in receipt:
        incarnation = obj(receipt['prompt']).get('processIncarnation')
        if incarnation != target['identity']['incarnationId']:
            raise Deferred('send-incarnation-mismatch')
        metadata['processIncarnation'] = incarnation
    if 'mutation' in result:
        request = obj(result['mutation']).get('requestId')
        if not token(request):
            raise Deferred('send-receipt-unknown')
        metadata['requestId'] = request
    journal.record('accepted', step='modal-navigation', receiptKind='raw-key', **metadata)
    wait_idle(client, target)
    return guard(client, plan, target, self_pane, modal=True)[1]


def claude_permission(text):
    fields = re.findall(r'(?im)^\s*(?:Permission mode|Permissions)\s*:\s*(.+)$', text)
    if fields:
        return fields[-1].strip()
    if re.search(r'(?m)^\s*⏵⏵ bypass permissions on \(shift\+tab to cycle\)\s*$', text):
        return 'bypass permissions'
    raise Deferred('claude-permissions-unknown')


def native_query(client, plan, target, self_pane, journal, command, phase, completion=None):
    _, previous = guard(client, plan, target, self_pane)
    cursor = previous.get('latestCursor')
    if cursor is None:
        raise Deferred('native-response-freshness-unknown')
    previous_text = screen(previous)
    send(client, journal, target, command, phase)
    wait_idle(client, target)
    if target['provider'] == 'claude':
        marker = '❯ ' + command
        old_count = sum(line.strip() == marker for line in previous_text.splitlines())
        deadline = time.monotonic() + 3
        pending = None
        for attempt in range(12):
            _, current = guard(client, plan, target, self_pane, modal=True)
            text = screen(current)
            if claude_modal(text, command):
                break
            idle_screen('claude', current)
            echoes = [line.strip() for line in text.splitlines()
                      if line.lstrip().startswith('❯') and line.strip() != '❯']
            if sum(line == marker for line in echoes) > old_count:
                if echoes[-1] != marker:
                    raise Deferred('native-response-boundary-changed')
                break
            if current.get('latestCursor') not in (None, cursor):
                delta = obj(client.call('terminal', 'read', '--terminal', target['handle'], '--cursor', str(cursor)).get('terminal'))
                tail = delta.get('tail')
                if delta.get('source') != 'stream' or not isinstance(tail, list) or any(not isinstance(x, str) for x in tail):
                    raise Deferred('native-response-output-unknown')
                fresh = '\n'.join(tail)
                try:
                    if completion is not None:
                        completion[0](fresh)
                    elif command == '/status':
                        status('claude', fresh)
                    elif command == '/help':
                        if not re.search(r'(?m)^\s*/reload-plugins(?:\s|$)', fresh):
                            raise Deferred('claude-reload-command-unsupported')
                    elif not fresh.strip():
                        raise Deferred('native-response-output-unknown')
                except Deferred as error:
                    if completion is not None and str(error) != completion[1]:
                        raise
                    pending = error
                else:
                    return text, fresh
            if attempt == 11 or time.monotonic() >= deadline:
                raise pending or Deferred('native-response-freshness-unknown')
            journal.record('awaiting-native-response', handle=target['handle'], step=phase,
                           expectedEchoAdded=False, streamComplete=False)
            time.sleep(0.05)
        text = screen(current)
        if claude_modal(text, command):
            if claude_modal(previous_text, command) or text == previous_text:
                raise Deferred('native-response-freshness-unknown')
            if command == '/status':
                output = text + '\nPermission mode: ' + claude_permission(previous_text)
            else:
                # The Commands tab and list are bounded native UI navigation.
                current = modal_key(client, plan, target, self_pane, journal, command, '\x1b[C')
                output = ''
                for _ in range(16):
                    frame = screen(current)
                    if not claude_modal(frame, command):
                        raise Deferred('claude-modal-boundary-unknown')
                    if 'Browse default commands' in frame:
                        output += '\n' + frame
                        if re.search(r'(?m)^\s*(?:❯\s*)?/reload-plugins(?:\s|$)', frame):
                            break
                    current = modal_key(client, plan, target, self_pane, journal, command, '\x1b[B' * 10)
                else:
                    raise Deferred('claude-reload-command-unsupported')
            modal_key(client, plan, target, self_pane, journal, command, '\x1b')
            _, closed = guard(client, plan, target, self_pane)
            if claude_modal(screen(closed), command):
                raise Deferred('claude-modal-close-unconfirmed')
            return screen(closed), output
        idle_screen('claude', current)
        # For screen-only responses require a new latest command echo, then use
        # only the response bounded by that echo and the next empty prompt.
        marker = '❯ ' + command
        lines = text.splitlines()
        indices = [i for i, line in enumerate(lines) if line.strip() == marker]
        if indices:
            index = indices[-1]
            old_count = sum(line.strip() == marker for line in previous_text.splitlines())
            if len(indices) <= old_count and current.get('latestCursor') == cursor:
                raise Deferred('native-response-freshness-unknown')
            response = []
            for line in lines[index + 1:]:
                if line.strip() == '❯':
                    break
                response.append(line)
            fresh = '\n'.join(response)
            if completion is not None and len(indices) > old_count:
                return claude_complete_response(client, plan, target, self_pane,
                                                command, current, fresh, *completion)
            if fresh.strip() and (len(indices) > old_count or fresh not in previous_text):
                return text, fresh
    else:
        _, current = guard(client, plan, target, self_pane)
    if current.get('latestCursor') in (None, cursor):
        raise Deferred('native-response-freshness-unknown')
    delta = obj(client.call('terminal', 'read', '--terminal', target['handle'], '--cursor', str(cursor)).get('terminal'))
    tail = delta.get('tail')
    if delta.get('source') != 'stream' or not isinstance(tail, list) or any(not isinstance(x, str) for x in tail):
        raise Deferred('native-response-output-unknown')
    fresh = '\n'.join(tail)
    if completion is not None:
        # Stream freshness cannot bind a later screen echo: validate this delta only.
        completion[0](fresh)
    return idle_screen(target['provider'], current), fresh


def claude_plugin_listing(text, inventory):
    enabled = [p for p in inventory['plugins'] if p['enabled']]
    expected = {p['id']: p for p in enabled}
    if len(expected) != len(enabled):
        raise Deferred('claude-runtime-plugin-list-ambiguous')
    found = {}
    number = r'(?:0|[1-9][0-9]*)'
    prerelease = rf'(?:{number}|[0-9]*[A-Za-z-][0-9A-Za-z-]*)'
    build = r'[0-9A-Za-z-]+'
    version = rf'{number}\.{number}\.{number}(?:-{prerelease}(?:\.{prerelease})*)?(?:\+{build}(?:\.{build})*)?'
    scope = r'user|project|local|managed|session|synced'
    lines = text.splitlines()
    footer_seen = False
    for index, line in enumerate(lines):
        ids = re.findall(r'(?<![\w.-])[A-Za-z0-9][A-Za-z0-9_.-]*@[A-Za-z0-9_.-]+', line)
        if not ids:
            stripped = line.strip()
            if re.fullmatch(r'[─━╌═-]+', stripped):
                continue
            # Observed Claude2.1.322 chrome: complete list, one known hint, divider.
            following = next((s.strip() for s in lines[index + 1:] if s.strip()), '')
            if (not footer_seen and set(found) == set(expected) and
                    re.fullmatch(r'\s{2,}(?:◐ medium · /effort|'
                                 r'Scroll wheel is sending arrow keys · use PgUp/PgDn to scroll)\s*', line) and
                    re.fullmatch(r'[─━╌═-]+', following)):
                footer_seen = True
                continue
            if (not stripped or re.fullmatch(r'(?:⎿\s*)?Installed plugins:', stripped) or
                    (not expected and stripped == 'No plugins installed.')):
                continue
            raise Deferred('claude-runtime-plugin-list-unknown')
        if len(ids) != 1 or ids[0] not in expected or ids[0] in found:
            raise Deferred('claude-runtime-plugin-list-mismatch')
        ident = ids[0]
        prefix = r'^\s*(?:[•*-]\s*)?' + re.escape(ident) + r'\s+'
        match = (re.fullmatch(prefix + rf'\(v({version}),\s*({scope})\)\s*✔\s*enabled\s*', line) or
                 re.fullmatch(prefix + rf'v?({version})\s+({scope})\s+enabled\s*', line))
        if match is None or match[2] != expected[ident]['scope']:
            raise Deferred('claude-runtime-plugin-list-mismatch')
        found[ident] = match[1]
    if set(found) != set(expected) or (not expected and 'No plugins installed.' not in text):
        raise Deferred('claude-runtime-plugin-list-unknown')
    return {ident + ':' + expected[ident]['scope']: value for ident, value in found.items()}


def claude_reload_summary(text, inventory):
    if re.search(r'(?i)(errors? during load|dependencies|--force|not available|isn.t available|failed|refused)', text):
        raise Deferred('claude-reload-refused-or-partial')
    pattern = (r'Reloaded:\s*(\d+) plugins?\s*[·|]\s*(\d+) skills?\s*[·|]\s*'
               r'(\d+) agents?\s*[·|]\s*(\d+) hooks?\s*[·|]\s*'
               r'(\d+) plugin MCP servers?\s*[·|]\s*(\d+) plugin LSP servers?')
    matches = re.findall(pattern, text)
    if not matches:
        raise Deferred('claude-reload-completion-unknown')
    counts = [int(value) for value in matches[-1]]
    if counts[0] != sum(p['enabled'] for p in inventory['plugins']):
        raise Deferred('claude-reloaded-plugin-count-mismatch')
    return dict(zip(('plugins', 'skills', 'agents', 'hooks', 'mcpServers', 'lspServers'), counts))


def claude_complete_response(client, plan, target, self_pane, command, initial_frame, text, validate, pending_reason):
    # Only called for a proved fresh screen echo; retain its prefix/cursor.
    initial = screen(initial_frame).splitlines()
    marker = '❯ ' + command
    indices = [i for i, line in enumerate(initial) if line.strip() == marker]
    if not indices:
        raise Deferred('claude-response-boundary-unknown')
    prefix = initial[:indices[-1] + 1]
    cursor = initial_frame.get('latestCursor')
    if cursor is None:
        raise Deferred('native-response-freshness-unknown')
    frame = initial_frame
    deadline = time.monotonic() + 3
    for attempt in range(12):
        try:
            validate(text)
            return screen(frame), text
        except Deferred as error:
            if str(error) != pending_reason or attempt == 11 or time.monotonic() >= deadline:
                raise
        time.sleep(0.05)
        _, frame = guard(client, plan, target, self_pane)
        lines = screen(frame).splitlines()
        commands = [i for i, line in enumerate(lines) if line.lstrip().startswith('❯') and line.strip() != '❯']
        current_prefix = lines[:commands[-1] + 1] if commands else []
        count = sum(line.strip() == marker for line in lines)
        if (not commands or lines[commands[-1]].strip() != marker or frame.get('latestCursor') != cursor or
                count > len(indices) or len(current_prefix) > len(prefix) or
                current_prefix != prefix[-len(current_prefix):]):
            raise Deferred('claude-response-boundary-changed')
        response = []
        for line in lines[commands[-1] + 1:]:
            if line.strip() == '❯':
                break
            response.append(line)
        text = '\n'.join(response)


def refresh_claude(client, plan, target, self_pane, journal):
    installation_before = installation_guard(target)
    version = installation_before.get('nativeVersion', '')
    parts = re.fullmatch(r'2\.1\.(\d+)', version)
    if parts is None or int(parts[1]) < 260 or installation_before.get('dependenciesReady') is not True:
        raise Deferred('claude-reload-support-and-dependencies-unverified')
    journal.record('installation-before', handle=target['handle'], installation=installation_before)
    before = native_status(client, plan, target, self_pane, journal)
    if before.get('nativeVersion') != version:
        raise Deferred('claude-native-version-mismatch')
    journal.record('identity-before', handle=target['handle'], **before)
    _, help_output = native_query(client, plan, target, self_pane, journal, '/help', 'reload-support')
    if not re.search(r'(?m)^\s*(?:❯\s*)?/reload-plugins(?:\s|$)', help_output):
        raise Deferred('claude-reload-command-unsupported')
    _, listing = native_query(client, plan, target, self_pane, journal, '/plugin list --enabled', 'plugin-preflight',
                              completion=(lambda text: claude_plugin_listing(text, installation_before),
                                          'claude-runtime-plugin-list-unknown'))
    listed_before = claude_plugin_listing(listing, installation_before)
    listing_matches = listed_before == {p['id'] + ':' + p['scope']: p['version']
                                       for p in installation_before['plugins'] if p['enabled']}
    journal.record('runtime-listing-before', handle=target['handle'],
                   versions=listed_before, matchesInstalled=listing_matches)
    _, output = native_query(client, plan, target, self_pane, journal, '/reload-plugins', 'native-reload',
                             completion=(lambda text: claude_reload_summary(text, installation_before),
                                         'claude-reload-completion-unknown'))
    summary = claude_reload_summary(output, installation_before)
    journal.record('reload-completed', handle=target['handle'], counts=summary)
    after = native_status(client, plan, target, self_pane, journal)
    journal.record('identity-after', handle=target['handle'], **after)
    if before != after:
        raise Deferred('native-identity-or-permissions-mismatch')
    installation_after = installation_guard(target)
    journal.record('installation-after', handle=target['handle'], installation=installation_after)
    return {'handle': target['handle'], 'before': before, 'after': after,
            'refresh': 'native-reload-observed', 'reloadSummary': summary, 'consumption': 'unverified',
            'runtimeListedVersionsBefore': listed_before, 'runtimeListingMatchesInstalledBefore': listing_matches,
            'installedVersion': installed_versions(installation_after), 'consumedVersion': None,
            'installationBefore': installation_before, 'installationAfter': installation_after}


def refresh(client, plan, target, self_pane, journal):
    if target['provider'] == 'claude':
        return refresh_claude(client, plan, target, self_pane, journal)
    installation_before = installation_guard(target)
    journal.record('installation-before', handle=target['handle'], installation=installation_before)
    before = native_status(client, plan, target, self_pane, journal)
    journal.record('identity-before', handle=target['handle'], **before)
    _, exit_frame = guard(client, plan, target, self_pane)
    normal_exit = {'sessionId': before['sessionId'], 'cursor': exit_frame.get('latestCursor')}
    if not re.fullmatch(r'\d+', str(normal_exit['cursor'])):
        raise Deferred('native-exit-freshness-unknown')
    journal.record('native-exit-planned', handle=target['handle'], **normal_exit)
    send(client, journal, target, '/exit', 'normal-exit')
    # Do not send into an uncertain foreground process. No close, kill, Ctrl-C or retry.
    deadline = time.monotonic() + 10
    while True:
        try:
            shell_guard(client, plan, target, normal_exit)
            break
        except Deferred as e:
            if str(e) != 'shell-unconfirmed' or time.monotonic() >= deadline:
                raise
            time.sleep(0.2)
    shell_guard(client, plan, target, normal_exit)
    journal.record('native-exit-observed', handle=target['handle'], sessionId=before['sessionId'], shellCwd=before['cwd'])
    command = 'codex resume ' + shlex.quote(before['sessionId'])
    send(client, journal, target, command, 'exact-resume')
    wait_idle(client, target)
    # Native UI readiness can precede publication of its resumed hook row. Read only
    # during this bounded handshake; never retry a send or tolerate changed identity.
    deadline = time.monotonic() + 10
    while True:
        try:
            guard(client, plan, target, self_pane)
            break
        except Deferred as e:
            if str(e) != 'agent-identity-unknown' or time.monotonic() >= deadline:
                raise
            time.sleep(0.2)
    after = native_status(client, plan, target, self_pane, journal)
    journal.record('identity-after', handle=target['handle'], **after)
    if before != after:
        raise Deferred('native-identity-or-permissions-mismatch')
    installation_after = installation_guard(target)
    journal.record('installation-after', handle=target['handle'], installation=installation_after)
    return {'handle': target['handle'], 'before': before, 'after': after,
            'refresh': 'native-resume-observed', 'consumption': 'unverified',
            'installedVersion': installed_versions(installation_after), 'consumedVersion': None,
            'installationBefore': installation_before, 'installationAfter': installation_after}


def validate_plan(plan):
    obj(plan)
    if plan.get('schema') != 1 or not token(plan.get('runtimeId')) or not token(plan.get('selfPane')):
        raise Deferred('invalid-plan')
    try:
        if not isinstance(plan.get('operationId'), str):
            raise Deferred('invalid-plan')
        uuid.UUID(plan['operationId'])
    except (KeyError, ValueError, TypeError):
        raise Deferred('invalid-plan') from None
    if not isinstance(plan.get('createdAt'), (float, int)) or not 0 <= time.time() - plan['createdAt'] <= 300:
        raise Deferred('plan-expired')
    targets = array(plan.get('targets'))
    if not targets or len({t.get('handle') for t in targets}) != len(targets):
        raise Deferred('duplicate-or-empty-targets')
    for t in targets:
        if t.get('provider') not in ('codex', 'claude') or t.get('state') != 'idle':
            raise Deferred('invalid-plan')
        if obj(t.get('installation')).get('state') != 'observed':
            raise Deferred('installed-versions-unverified')
        identity = fingerprint(obj(t.get('identity')))
        if identity['handle'] != t.get('handle') or pane(identity) == plan['selfPane']:
            raise Deferred('invalid-plan')


def apply(client, plan, self_pane, journal_root):
    validate_plan(plan)
    if getattr(client, 'remote_configured', False) or client.environment or plan.get('environment') or plan.get('remoteConfigured') or any(t['identity']['executionHostId'] != 'local' for t in plan['targets']):
        raise Deferred('remote-apply-delegate-to-host-session')
    if not self_pane or self_pane != plan['selfPane']:
        raise Deferred('self-unidentified')
    result = {'operationId': plan['operationId'], 'results': [], 'remaining': [t['handle'] for t in plan['targets']]}
    with Journal(journal_root, plan['operationId']) as journal:
        for target in plan['targets']:
            try:
                result['results'].append(refresh(client, plan, target, self_pane, journal))
                result['remaining'].pop(0)
            except (Deferred, OSError) as e:
                reason = str(e) if isinstance(e, Deferred) else 'journal-or-local-io-failed'
                result['stopped'] = reason
                result['recovery'] = {'journal': str(journal.path), 'handle': target['handle'],
                                      'identity': target['identity'], 'action': 'inspect-before-any-resend'}
                try:
                    journal.record('stopped', handle=target['handle'], reason=reason)
                except (Deferred, OSError):
                    result['recovery']['journalRecording'] = 'failed-inspect-existing-record'
                return result
        try:
            journal.record('finished')
        except (Deferred, OSError) as error:
            result['stopped'] = str(error) if isinstance(error, Deferred) else 'journal-or-local-io-failed'
            result['recovery'] = {'journal': str(journal.path), 'handle': target['handle'],
                                  'identity': target['identity'], 'phase': 'final-journal-record',
                                  'journalRecording': 'failed-inspect-existing-record',
                                  'action': 'inspect-completed-results-before-any-resend'}
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('inspect', 'plan', 'apply'), nargs='?', default='inspect')
    p.add_argument('--environment')
    p.add_argument('--target', action='append', default=[])
    p.add_argument('--plan', type=Path)
    p.add_argument('--journal', type=Path, default=Path.home() / '.local/state/tr-kit/runtime-refresh')
    args = p.parse_args(argv)
    client = Orca(args.environment)
    try:
        self_pane = os.environ.get('ORCA_PANE_KEY')
        if args.mode == 'apply':
            if not args.plan or args.target:
                raise Deferred('apply-requires-plan-only')
            result = apply(client, json.loads(args.plan.read_text()), self_pane, args.journal)
        else:
            report = inspect(client, self_pane)
            result = make_plan(report, args.target) if args.mode == 'plan' else report
            if args.mode == 'plan':
                if not args.plan:
                    raise Deferred('plan-path-required')
                with args.plan.open('x') as f:
                    os.chmod(args.plan, 0o600)
                    json.dump(result, f, ensure_ascii=False, indent=2)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get('stopped') else 0
    except (Deferred, OSError, ValueError, TypeError, KeyError):
        # Do not echo hostile file/CLI contents, even in an exception message.
        error = sys.exc_info()[1]
        print(json.dumps({'state': 'deferred', 'reason': str(error) if isinstance(error, Deferred) else 'invalid-input-or-local-io'}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
