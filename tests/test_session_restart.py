"""Owned transport doubles only; no user terminal or native account is touched."""
import copy
from contextlib import redirect_stdout
import importlib.util
import json
import io
import os
import shlex
from pathlib import Path
import tempfile
import stat
import subprocess
import sys
import unittest
from unittest.mock import patch
import uuid

SCRIPT = Path(__file__).resolve().parents[1] / 'common/base/skills/session/scripts/session_restart.py'
spec = importlib.util.spec_from_file_location('restart', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SESSION = '01a1c848-8ff2-7e90-bcec-44a3ca07a21b'
CODEX_RESUME = 'codex resume '
CODEX_OPTION = ' --dangerously-bypass-approvals-and-sandbox'
READINESS_PROMPT = 'Reply only TR_KIT_RESTART_READY. Do not use tools or perform any other action.'
CLAUDE_RESUME = 'claude --dangerously-skip-permissions --resume '
INSTALL = {'state': 'observed', 'plugins': [{'id': 'owned@test', 'scope': 'user', 'version': '1.0'}]}


class Fake:
    environment = None
    remote_configured = False

    def __init__(self, provider='codex'):
        self.runtime = 'runtime-1'
        self.terms = {}
        self.agents = {}
        self.frames = {}
        self.identities = {}
        self.sent = []
        self.created = []
        self.fail = None
        self.change_after_resume = None
        self.claude_version = '2.1.330'
        self.codex_version = '0.171.0'
        self.installed_codex_version = '0.171.0'
        self.installed_claude_version = '2.1.330'
        self.add('self', '/caller')
        self.add('target', '/work', provider)

    def add(self, name, cwd, provider='codex'):
        handle = 'term_' + name
        item = dict(handle=handle, ptyId='pty-'+name, incarnationId='inc-'+name,
                    worktreeId='repo::'+cwd, worktreePath=cwd, executionHostId='local',
                    tabId='tab', leafId=name, agentIdentity=provider, agentWait=None,
                    orphaned=False, connected=True, writable=True)
        self.terms[handle] = item
        self.agents[handle] = dict(paneKey=m.rr.pane(item), agentType=provider, state='idle',
                                   mainAgent={'state': 'idle'}, programStatus={'state': 'idle'},
                                   subagentObservation='live', children=[])
        self.frames[handle] = {'source': 'screen', 'tail': ['›' if provider == 'codex' else '❯'],
                               'latestCursor': '10'}
        if provider == 'claude':
            self.frames[handle]['tail'].append('  ⏵⏵ bypass permissions on (shift+tab to cycle)')
        self.identities[handle] = {'sessionId': SESSION if name == 'target' else str(uuid.uuid4()),
                                   'cwd': cwd, 'permissions': 'Full Access' if provider == 'codex' else 'bypass permissions'}
        return handle

    def inventory(self):
        workspaces = {t['worktreeId']: dict(worktreeId=t['worktreeId'], path=t['worktreePath'],
                                            hostId='local', agents=[]) for t in self.terms.values()}
        # /work persists across removal of the last terminal, just like Orca.
        workspaces.setdefault('repo::/work', dict(worktreeId='repo::/work', path='/work', hostId='local', agents=[]))
        for handle, agent in self.agents.items():
            if handle in self.terms:
                workspaces[self.terms[handle]['worktreeId']]['agents'].append(copy.deepcopy(agent))
        scope = {'hostIds': ['local'], 'omittedHostIds': []}
        return ({'terminals': copy.deepcopy(list(self.terms.values())), 'truncated': False, 'hostScope': scope},
                {'worktrees': list(workspaces.values()), 'truncated': False, 'hostScope': scope})

    def observe(self, handle):
        return copy.deepcopy(self.terms[handle]), copy.deepcopy(self.frames[handle])

    def call(self, *args):
        if args[:2] == ('terminal', 'wait'):
            return {'wait': {'satisfied': True}}
        if args[:2] == ('terminal', 'read'):
            handle = args[args.index('--terminal')+1]
            frame = self.frames[handle]
            return {'terminal': {'source': 'stream', 'tail': frame.get('delta', [])}}
        if args[:2] == ('terminal', 'create'):
            self.created.append(args)
            if self.fail:
                raise m.Deferred(self.fail)
            command = args[args.index('--command')+1]
            provider = command.split()[0]
            h = self.add('restored', '/work', provider)
            args = command.split()
            self.identities[h]['sessionId'] = args[2] if provider == 'codex' else args[args.index('--resume')+1]
            return {'terminal': copy.deepcopy(self.terms[h])}
        if args[:2] == ('terminal', 'send'):
            self.sent.append(args)
            if self.fail:
                raise m.Deferred(self.fail)
            h = args[args.index('--terminal')+1]
            command = args[args.index('--text')+1]
            if self.terms[h].get('agentIdentity') == 'codex' and self.codex_version == '0.172.0':
                # Native composer trims submissions; self.sent retains wire bytes.
                command = command.strip()
            frame = self.frames[h]
            frame['latestCursor'] = str(int(frame['latestCursor']) + 1)
            if command == '/status':
                identity = self.identities[h]
                frame['delta'] = ['Session ID: '+identity['sessionId'], 'cwd: '+identity['cwd'],
                                  'Permissions: '+identity['permissions']]
                if self.terms[h].get('agentIdentity') == 'claude':
                    frame['delta'].append('Version: '+self.claude_version)
                else:
                    frame['delta'].insert(0, 'OpenAI Codex (v'+self.codex_version+')')
                frame['tail'] = frame['delta'] + ['›' if self.terms[h].get('agentIdentity') == 'codex' else '❯']
            elif command == '/exit':
                frame['delta'] = ['To continue this session, run: codex resume '+self.identities[h]['sessionId']]
                frame['tail'] = ['owned@host:'+self.terms[h]['worktreePath']+'$']
            elif command.startswith('codex resume '):
                frame['tail'] = ['›']
                if self.change_after_resume:
                    self.identities[h].update(self.change_after_resume)
            else:
                raise AssertionError(command)
            return {'send': {'accepted': True}, 'mutation': {'requestId': str(uuid.uuid4())}}
        raise AssertionError(args)

    def remove(self, handle):
        for values in (self.terms, self.frames, self.agents, self.identities):
            values.pop(handle, None)

    def replace_handle(self):
        for values in (self.terms, self.frames, self.agents, self.identities):
            values['term_replacement'] = values.pop('term_target')
        self.terms['term_replacement']['handle'] = 'term_replacement'
        self.terms['term_replacement']['ptyId'] = 'fresh-pty'
        self.terms['term_replacement']['incarnationId'] = 'fresh-incarnation'
        self.runtime = 'runtime-2'


class ModalFake(Fake):
    """Owned Claude status modals; closing discards the identity-bearing frame."""
    def __init__(self):
        super().__init__('claude')
        self.modals = set()

    def call(self, *args):
        if args[:2] == ('terminal', 'send'):
            handle = args[args.index('--terminal')+1]
            text = args[args.index('--text')+1]
            if text == '\x1b':
                self.sent.append(args)
                self.modals.discard(handle)
                frame = self.frames[handle]
                frame.update(tail=['❯', '  ⏵⏵ bypass permissions on (shift+tab to cycle)'],
                             latestCursor=str(int(frame['latestCursor'])+1))
                return {'send': {'handle': handle, 'accepted': True, 'bytesWritten': 1}}
            result = super().call(*args)
            if text == '/status' and self.terms[handle]['agentIdentity'] == 'claude':
                self.modals.add(handle)
                identity = self.identities[handle]
                self.frames[handle]['tail'] = [
                    ' Settings  Status  Config  Usage  Stats', ' Version: 2.1.330',
                    ' Session ID: '+identity['sessionId'], ' cwd: '+identity['cwd'],
                    ' ←/→ to switch · Esc to close']
            return result
        return super().call(*args)


class ScreenStatusFake(Fake):
    """Status cards repaint without completed stream records; no native evidence."""
    def __init__(self):
        super().__init__()
        self.stale_status = False
        self.conflict = False
        # The first status preserves real task history, rather than empty UI.
        self.frames['term_target']['tail'] = ['› earlier fixture instruction',
                                              'fixture completed work', '›']

    def call(self, *args):
        if args[:2] == ('terminal', 'send') and args[args.index('--text')+1] == '/status':
            handle = args[args.index('--terminal')+1]
            before = copy.deepcopy(self.frames[handle])
            result = super().call(*args)
            frame = self.frames[handle]
            body = ['  >_ '+frame['delta'][0], *frame['delta'][1:]]
            old = before['tail'][:-1]
            # A cropped old card retains its unique Session/cwd/permission suffix.
            retained = old[-3:] if len(old) >= 4 else old
            frame.update(latestCursor=before['latestCursor'], delta=[],
                         tail=before['tail'] if self.stale_status else
                         [*retained, '/status', *body, '›'])
            if self.conflict:
                frame['delta'] = ['Permissions: default']
            return result
        return super().call(*args)


class Restart(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'state'
        self.client = Fake()
        self.self_pane = 'tab:self'
        self.inventory = patch.object(m.rr, 'plugin_inventory', side_effect=lambda provider, cwd: {
            **copy.deepcopy(INSTALL), 'nativeVersion': (self.client.installed_codex_version if provider == 'codex'
                                                       else self.client.installed_claude_version)})
        self.inventory.start()
        self.addCleanup(self.inventory.stop)
        self.host = patch.object(m, 'binding', return_value={'machine': 'owned-machine', 'profile': 'owned-profile'})
        self.host.start()
        self.addCleanup(self.host.stop)

    def prepare(self, selected=None, excluded=None):
        with m.Store(self.root) as store:
            return m.prepare(self.client, store, selected or ['term_target'], excluded or [], self.self_pane)['batchId']

    def execute(self, ident, mode='restart'):
        with m.Store(self.root) as store:
            return m.execute(self.client, store, ident, self.self_pane, mode)

    def load(self, ident):
        with m.Store(self.root) as store:
            return store.load(ident)

    def texts(self):
        return [a[a.index('--text')+1] for a in self.client.sent]

    def glyph_exit(self):
        original = self.client.call
        def call(*args):
            result = original(*args)
            if args[:2] == ('terminal', 'send') and args[args.index('--text')+1] == '/exit':
                self.client.frames['term_target']['tail'] = ['NAS prompt context', '❯']
            return result
        self.client.call = call

    def test_glyph_restart_preserves_exact_identity_once_and_clears_ephemeral_proof(self):
        ident = self.prepare()
        self.client.sent.clear()
        self.glyph_exit()
        self.client.target_shell_proof = {'stale': 'previous invocation'}
        with patch.object(m.rr, 'target_shell_process_proof', return_value={'owned-zsh': 'fixed'}):
            row = self.execute(ident)['targets'][0]
            self.assertEqual('restarted', row['state'])
            self.assertEqual(['/status', '/exit', CODEX_RESUME+SESSION+CODEX_OPTION, '/status'], self.texts())
            self.assertIsNone(self.client.target_shell_proof)
            self.assertEqual('already-running', self.execute(ident)['targets'][0]['state'])
        batch = self.load(ident)
        row = batch['targets'][0]
        self.assertEqual(SESSION, row['nativeObserved']['sessionId'])
        self.assertEqual('/work', row['nativeObserved']['cwd'])
        self.assertEqual('Full Access', row['nativeObserved']['permissions'])
        self.assertEqual('codex-full-access', row['nativeObserved']['resumeMode'])
        self.assertEqual(1, self.texts().count('/exit'))
        self.assertEqual(1, self.texts().count(CODEX_RESUME+SESSION+CODEX_OPTION))
        self.assertEqual([], self.client.created)
        self.assertNotIn('owned-zsh', json.dumps(batch))
        self.assertNotIn('target_shell_proof', json.dumps(batch))

    def test_glyph_process_refusal_retains_failed_attempt_and_never_resumes_or_creates(self):
        ident = self.prepare()
        self.client.sent.clear()
        self.glyph_exit()
        with patch.object(m.rr, 'target_shell_process_proof', side_effect=m.Deferred('target-shell-process-unverifiable')):
            row = self.execute(ident)['targets'][0]
        self.assertEqual('failed', row['state'])
        self.assertEqual('target-shell-process-unverifiable', row['reason'])
        self.assertEqual(['/status', '/exit'], self.texts())
        batch = self.load(ident)
        self.assertEqual('uncertain', batch['targets'][0]['attempt']['state'])
        self.assertTrue(any(e['phase'] == 'stopped' and e['reason'] == row['reason'] for e in batch['events']))
        self.assertFalse(any(e['phase'] == 'sending' and e.get('step') == 'exact-resume' for e in batch['events']))
        self.assertEqual([], self.client.created)

    def test_glyph_drift_across_exit_record_and_durable_resume_refuses_single_transport(self):
        for boundary in ('native-exit-observed', 'sending'):
            for drift in ('process', 'pane', 'draft', 'runtime', 'installation'):
                with self.subTest(boundary=boundary, drift=drift), tempfile.TemporaryDirectory() as folder:
                    self.root = Path(folder) / 'state'
                    self.client = Fake()
                    ident = self.prepare()
                    self.client.sent.clear()
                    self.glyph_exit()
                    process = {'generation': 1}
                    record = m.Recorder.record
                    def durable(recorder, event, **values):
                        result = record(recorder, event, **values)
                        if event == boundary and (boundary != 'sending' or values.get('step') == 'exact-resume'):
                            if drift == 'process': process['generation'] = 2
                            elif drift == 'pane': self.client.terms['term_target']['leafId'] = 'other'
                            elif drift == 'draft': self.client.frames['term_target']['draft'] = 'typed'
                            elif drift == 'runtime': self.client.runtime = 'changed'
                            else: self.client.installed_codex_version = '0.172.0'
                        return result
                    with patch.object(m.rr, 'target_shell_process_proof', side_effect=lambda identity: copy.deepcopy(process)), \
                         patch.object(m.Recorder, 'record', new=durable):
                        row = self.execute(ident)['targets'][0]
                    self.assertEqual('failed', row['state'])
                    self.assertEqual(['/status', '/exit'], self.texts())
                    self.assertEqual([], self.client.created)
                    batch = self.load(ident)
                    sends = [e for e in batch['events'] if e['phase'] == 'sending' and e.get('step') == 'exact-resume']
                    self.assertEqual(1 if boundary == 'sending' else 0, len(sends))
                    self.assertEqual('uncertain', batch['targets'][0]['attempt']['state'])
                    self.assertEqual('stopped', batch['events'][-1]['phase'])

    def management_batch(self):
        own = self.client.terms['term_self']
        own.update(worktreeId='repo::/work', worktreePath='/work', agentIdentity=None)
        self.client.agents.pop('term_self')
        self.client.frames['term_self'] = {'source': 'screen', 'tail': ['Python management helper running'],
                                           'latestCursor': '10'}
        ident = self.prepare()
        self.client.replace_handle()
        self.client.sent.clear()
        return ident

    def test_management_helper_restarts_same_batch_without_self_input_in_either_order(self):
        for target_first in (False, True):
            with self.subTest(target_first=target_first), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder) / 'state'
                self.client = Fake()
                ident = self.management_batch()
                if target_first:
                    self.client.terms['term_self'] = self.client.terms.pop('term_self')
                with m.Store(self.root) as store:
                    before = store.load(ident)
                    before['events'].append({'phase': 'stopped', 'reason': 'original-failure-receipt'})
                    store.save(before)
                files = {p.name for p in self.root.iterdir()}
                key = (self.root / 'integrity.key').read_bytes()
                with patch.object(m.rr, 'management_process_proof', return_value={'owned': 'fixed-process'}):
                    result = self.execute(ident)
                self.assertEqual('restarted', result['targets'][0]['state'])
                self.assertEqual(['/status', '/exit', CODEX_RESUME+SESSION+CODEX_OPTION, '/status'], self.texts())
                self.assertEqual({'term_replacement'}, {a[a.index('--terminal')+1] for a in self.client.sent})
                after = self.load(ident)
                for field in ('batchId', 'createdAt', 'binding', 'preparedRuntime'):
                    self.assertEqual(before[field], after[field])
                for field in ('terminal', 'native', 'choice', 'targetId'):
                    self.assertEqual(before['targets'][0][field], after['targets'][0][field])
                self.assertEqual(before['events'], after['events'][:len(before['events'])])
                self.assertEqual(files, {p.name for p in self.root.iterdir()})
                self.assertEqual(key, (self.root / 'integrity.key').read_bytes())
                self.assertNotIn('management_self', json.dumps(after))

    def test_management_helper_requires_os_proof_before_any_candidate_query(self):
        ident = self.management_batch()
        self.client.terms['term_self'] = self.client.terms.pop('term_self')
        with patch.object(m.rr, 'management_process_proof', side_effect=m.Deferred('management-process-unverifiable')):
            self.assertEqual('management-process-unverifiable', self.execute(ident)['targets'][0]['reason'])
        self.assertEqual([], self.client.sent)
        self.assertEqual([], self.client.created)

    def test_management_helper_rejects_agent_child_draft_wait_and_access(self):
        for unsafe in ('agent', 'child', 'draft', 'wait', 'writable', 'fingerprint', 'native-hint'):
            with self.subTest(unsafe=unsafe), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder) / 'state'
                self.client = Fake()
                ident = self.management_batch()
                if unsafe == 'agent':
                    self.client.agents['term_self'] = {'paneKey': self.self_pane, 'agentType': 'codex'}
                elif unsafe == 'child':
                    self.client.agents['term_replacement']['parentPaneKey'] = self.self_pane
                elif unsafe == 'draft':
                    self.client.frames['term_self']['draft'] = 'typed work'
                elif unsafe == 'wait':
                    self.client.terms['term_self']['agentWait'] = {'kind': 'approval'}
                elif unsafe == 'native-hint':
                    self.client.terms['term_self']['agentIdentity'] = 'codex'
                elif unsafe == 'fingerprint':
                    self.client.terms['term_self']['ptyId'] = None
                else:
                    self.client.terms['term_self']['writable'] = False
                with patch.object(m.rr, 'management_process_proof', return_value={'owned': True}):
                    self.assertIn(self.execute(ident)['targets'][0]['state'], ('deferred', 'failed'))
                self.assertEqual([], self.client.sent)
                self.assertEqual([], self.client.created)

    def test_explicit_unknown_exception_cannot_be_overridden_by_management_proof(self):
        ident = self.management_batch()
        with m.Store(self.root) as store:
            batch = store.load(ident)
            batch['targets'].append({'targetId': 'term_old_exception',
                'terminal': {**copy.deepcopy(batch['targets'][0]['terminal']),
                             'handle': 'term_old_exception', 'leafId': 'excluded'},
                'provider': 'codex', 'choice': 'manual', 'native': None,
                'state': 'manual-restart-required', 'reason': 'explicit-exception', 'attempt': None})
            store.save(batch)
        with patch.object(m.rr, 'management_process_proof', side_effect=AssertionError('must not classify')):
            self.assertEqual('excluded-identity-unknown-after-runtime-change', self.execute(ident)['targets'][0]['reason'])
        self.assertEqual([], self.client.sent)

    def test_management_proof_stays_fixed_and_stops_after_slow_target_observation(self):
        for drift in ('runtime', 'fingerprint', 'process', 'draft', 'agent', 'child', 'wait'):
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder) / 'state'
                self.client = Fake()
                ident = self.management_batch()
                evidence = {'generation': 1}
                lookup = m.rr.plugin_inventory
                changed = []
                def slow_lookup(*args):
                    result = lookup(*args)
                    if getattr(self.client, 'management_self', None) and not changed:
                        changed.append(True)
                        if drift == 'runtime':
                            self.client.runtime = 'runtime-3'
                        elif drift == 'fingerprint':
                            self.client.terms['term_self']['incarnationId'] = 'changed'
                        elif drift == 'process':
                            evidence['generation'] = 2
                        elif drift == 'draft':
                            self.client.frames['term_self']['draft'] = 'work'
                        elif drift == 'agent':
                            self.client.agents['term_self'] = {'paneKey': self.self_pane}
                        elif drift == 'child':
                            self.client.agents['term_replacement']['parentPaneKey'] = self.self_pane
                        else:
                            self.client.terms['term_self']['agentWait'] = {'kind': 'approval'}
                    return result
                with patch.object(m.rr, 'management_process_proof', side_effect=lambda: copy.deepcopy(evidence)), \
                     patch.object(m.rr, 'plugin_inventory', side_effect=slow_lookup):
                    self.assertEqual('deferred', self.execute(ident)['targets'][0]['state'])
                self.assertEqual([True], changed)
                self.assertEqual([], self.client.sent)
                self.assertEqual([], self.client.created)

    def test_management_drift_during_durable_send_stops_exit_and_resume(self):
        for phase in ('status', 'normal-exit', 'exact-resume'):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder) / 'state'
                self.client = Fake()
                ident = self.management_batch()
                record = m.Recorder.record
                process = {'generation': 1}
                def interleave(recorder, event, **values):
                    result = record(recorder, event, **values)
                    if event == 'sending' and values.get('step') == phase:
                        process['generation'] = 2
                    return result
                with patch.object(m.rr, 'management_process_proof', side_effect=lambda: copy.deepcopy(process)), \
                     patch.object(m.Recorder, 'record', new=interleave):
                    self.assertEqual('failed', self.execute(ident)['targets'][0]['state'])
                expected = {'status': [], 'normal-exit': ['/status'], 'exact-resume': ['/status', '/exit']}[phase]
                self.assertEqual(expected, self.texts())
                self.assertEqual([], self.client.created)

    def test_management_restore_rechecks_after_final_installation_and_record(self):
        for drift in ('installation', 'record'):
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder) / 'state'
                self.client = Fake()
                ident = self.management_batch()
                self.client.remove('term_replacement')
                guard, record = m.rr.installation_guard, m.Recorder.record
                changed = []
                process = {'generation': 1}
                def final_installation(target):
                    result = guard(target)
                    if drift == 'installation' and 'handle' not in target:
                        changed.append(True)
                        self.client.frames['term_self']['draft'] = 'work arrived'
                    return result
                def final_record(recorder, event, **values):
                    result = record(recorder, event, **values)
                    if drift == 'record' and event == 'sending' and values.get('step') == 'owned-restore-terminal':
                        changed.append(True)
                        process['generation'] = 2
                    return result
                with patch.object(m.rr, 'management_process_proof', side_effect=lambda: copy.deepcopy(process)), \
                     patch.object(m.rr, 'installation_guard', side_effect=final_installation), \
                     patch.object(m.Recorder, 'record', new=final_record):
                    self.assertIn(self.execute(ident, 'restore')['targets'][0]['state'], ('deferred', 'failed'))
                self.assertEqual([True], changed)
                self.assertEqual([], self.client.sent)
                self.assertEqual([], self.client.created)

    def test_management_helper_can_restore_absent_uuid_without_self_input(self):
        ident = self.management_batch()
        self.client.remove('term_replacement')
        with patch.object(m.rr, 'management_process_proof', return_value={'owned': True}):
            self.assertEqual('restarted', self.execute(ident, 'restore')['targets'][0]['state'])
        self.assertEqual(1, len(self.client.created))
        self.assertEqual({'term_restored'}, {a[a.index('--terminal')+1] for a in self.client.sent})

    def test_execute_clears_previous_management_authority(self):
        ident = self.prepare()
        self.client.management_self = {'stale': True}
        self.assertEqual('restarted', self.execute(ident)['targets'][0]['state'])
        self.assertIsNone(self.client.management_self)

    def test_management_exception_is_not_activated_for_same_runtime_or_other_workspace(self):
        for same_runtime in (True, False):
            with self.subTest(same_runtime=same_runtime), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder) / 'state'
                self.client = Fake()
                ident = self.management_batch()
                if same_runtime:
                    self.client.runtime = 'runtime-1'
                else:
                    self.client.terms['term_self'].update(worktreeId='repo::/caller', worktreePath='/caller')
                with patch.object(m.rr, 'management_process_proof', side_effect=AssertionError('not applicable')):
                    self.assertEqual('restarted', self.execute(ident)['targets'][0]['state'])
                self.assertIsNone(self.client.management_self)

    def test_prepare_survives_new_process_boundary_and_never_exits(self):
        ident = self.prepare()
        self.assertEqual(['/status'], self.texts())
        batch = self.load(ident)
        self.assertEqual(SESSION, batch['targets'][0]['native']['sessionId'])
        self.assertEqual('ready', batch['targets'][0]['state'])
        self.assertEqual('manual-restart-required', batch['targets'][1]['state'])
        self.assertEqual('requesting-session', batch['targets'][1]['reason'])
        self.assertEqual(0o700, self.root.stat().st_mode & 0o777)
        self.assertEqual(0o600, (self.root/(ident+'.json')).stat().st_mode & 0o777)

    def test_list_needs_no_orca_or_conversation_loading(self):
        ident = self.prepare()
        with patch.object(m.rr, 'Orca', side_effect=AssertionError('runtime access')):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, m.main(['list', '--batch', ident, '--state', str(self.root)]))

    def test_explicit_exception_and_self_receive_zero_input(self):
        self.client.add('excluded', '/excluded')
        ident = self.prepare(['term_target', 'term_excluded', 'term_self'], ['term_excluded'])
        self.execute(ident)
        handles = [a[a.index('--terminal')+1] for a in self.client.sent]
        self.assertEqual({'term_target'}, set(handles))
        manual = [r for r in m.report(self.load(ident))['targets'] if r['state'] == 'manual-restart-required']
        self.assertEqual({'requesting-session', 'explicit-exception'}, {r['reason'] for r in manual})
        self.assertTrue(all({'host', 'workspace', 'provider', 'sessionId', 'reason'} <= set(r) for r in manual))

    def test_restart_preserves_uuid_cwd_permissions_and_separates_consumption(self):
        ident = self.prepare()
        self.client.sent.clear()
        report = self.execute(ident)
        self.assertEqual(['/status', '/exit', CODEX_RESUME+SESSION+CODEX_OPTION, '/status'], self.texts())
        self.assertEqual('restarted', report['targets'][0]['state'])
        self.assertEqual('unverified', report['targets'][0]['consumption'])
        self.assertIsNone(report['targets'][0]['consumedVersion'])
        batch = self.load(ident)
        phases = [e['phase'] for e in batch['events']]
        self.assertIn('sending', phases)
        self.assertEqual('complete', batch['targets'][0]['attempt']['state'])

    def test_repeated_restart_verifies_without_second_exit_or_resume(self):
        ident = self.prepare()
        self.execute(ident)
        self.client.sent.clear()
        report = self.execute(ident)
        self.assertEqual(['/status'], self.texts())
        self.assertEqual('already-running', report['targets'][0]['state'])

    def test_changed_runtime_and_handles_are_reacquired_by_live_identity(self):
        ident = self.prepare()
        self.client.replace_handle()
        self.client.sent.clear()
        report = self.execute(ident, 'restore')
        self.assertEqual('already-running', report['targets'][0]['state'])
        self.assertEqual([], self.client.created)
        self.assertEqual('term_replacement', self.client.sent[0][self.client.sent[0].index('--terminal')+1])

    def test_both_products_restore_absent_uuid_only_in_new_owned_terminal(self):
        for provider in ('codex', 'claude'):
            with self.subTest(provider=provider):
                self.root = Path(self.tmp.name)/provider
                self.client = Fake(provider)
                ident = self.prepare()
                self.client.remove('term_target')
                self.client.runtime = 'new-runtime'
                self.client.sent.clear()
                report = self.execute(ident, 'restore')
                self.assertEqual('restarted', report['targets'][0]['state'])
                self.assertEqual(1, len(self.client.created))
                launch = self.client.created[0]
                expected = CODEX_RESUME+SESSION+CODEX_OPTION if provider == 'codex' else CLAUDE_RESUME+SESSION
                self.assertEqual(expected, launch[launch.index('--command')+1])
                self.assertEqual('id:repo::/work', launch[launch.index('--worktree')+1])
                self.assertFalse(any(flag in launch for flag in ('--focus', '--last', '--prompt')))
                self.assertEqual({'term_restored'}, {a[a.index('--terminal')+1] for a in self.client.sent})

    def test_claude_unproven_clean_exit_is_manual_without_input(self):
        self.client = Fake('claude')
        ident = self.prepare()
        self.client.sent.clear()
        row = self.execute(ident)['targets'][0]
        self.assertEqual('manual-restart-required', row['state'])
        self.assertIn('clean-exit', row['reason'])
        self.assertEqual([], self.client.sent)

    def test_unverified_modes_are_manual_before_exit_or_create_without_bypass_flags(self):
        for provider, permissions in [('codex', 'default'), ('codex', 'Custom (workspace, Ask for approval)'),
                                      ('codex', 'Full Access --fake-flag'), ('claude', 'default')]:
            for absent in (False, True):
                with self.subTest(provider=provider, permissions=permissions, absent=absent):
                    self.root = Path(self.tmp.name)/str(uuid.uuid4())
                    self.client = Fake(provider)
                    self.client.identities['term_target']['permissions'] = permissions
                    ident = self.prepare()
                    self.client.sent.clear()
                    if absent:
                        self.client.remove('term_target')
                    row = self.execute(ident, 'restore' if absent else 'restart')['targets'][0]
                    self.assertEqual('manual-restart-required', row['state'])
                    self.assertTrue(all(text == '/status' for text in self.texts()))
                    self.assertEqual([], self.client.created)

    def test_legacy_batch_needs_fresh_live_mode_and_never_guesses_absent_mode(self):
        for absent in (False, True):
            with self.subTest(absent=absent):
                self.root = Path(self.tmp.name)/str(uuid.uuid4())
                self.client = Fake()
                ident = self.prepare()
                with m.Store(self.root) as store:
                    batch = store.load(ident)
                    batch['targets'][0]['native'].pop('resumeMode')
                    store.save(batch)
                self.client.sent.clear()
                if absent:
                    self.client.remove('term_target')
                row = self.execute(ident, 'restore' if absent else 'restart')['targets'][0]
                if absent:
                    self.assertEqual('manual-restart-required', row['state'])
                    self.assertEqual('native-resume-permissions-unverified', row['reason'])
                    self.assertEqual([], self.client.created)
                else:
                    self.assertEqual('restarted', row['state'])
                    self.assertIn(CODEX_RESUME+SESSION+CODEX_OPTION, self.texts())

    def test_unknown_mode_manual_does_not_replace_uncertain_attempt(self):
        ident = self.prepare()
        self.client.remove('term_target')
        self.client.fail = 'lost-create-receipt'
        self.execute(ident, 'restore')
        with m.Store(self.root) as store:
            batch = store.load(ident)
            prior = copy.deepcopy(batch['targets'][0]['attempt'])
            batch['targets'][0]['native'].pop('resumeMode')
            store.save(batch)
        self.client.fail = None
        self.execute(ident, 'restore')
        self.assertEqual(prior, self.load(ident)['targets'][0]['attempt'])
        self.assertEqual(1, len(self.client.created))

    def test_headerless_status_without_current_identity_is_unverified_without_exit(self):
        ident = self.prepare()
        self.client.sent.clear()
        self.client.codex_version = '0.172.0'
        self.client.frames['term_target']['tail'] = ['› Ask Codex to do anything']
        original = self.client.call
        def headerless_screen(*args):
            result = original(*args)
            if args[:2] == ('terminal', 'send'):
                self.client.frames['term_target']['tail'] = ['› Ask Codex to do anything']
            return result
        with patch.object(self.client, 'call', side_effect=headerless_screen):
            row = self.execute(ident, 'restart')['targets'][0]
        self.assertEqual('failed', row['state'])
        self.assertEqual('native-identity-unknown', row['reason'])
        self.assertEqual(['/status'], self.texts())
        self.assertEqual([], self.client.created)

    def test_absent_restore_unknown_current_cli_version_never_creates(self):
        ident = self.prepare()
        self.client.remove('term_target')
        self.client.installed_codex_version = '0.172.1'
        self.client.sent.clear()
        row = self.execute(ident, 'restore')['targets'][0]
        self.assertEqual('manual-restart-required', row['state'])
        self.assertEqual('native-resume-version-unverified', row['reason'])
        self.assertEqual([], self.client.created)
        self.assertEqual([], self.client.sent)

    def test_codex_01720_upgrade_restart_and_restore_preserve_identity_and_permissions(self):
        for before in ('0.167.1', '0.167.2', '0.171.0', '0.172.0'):
            for mode in ('restart', 'restore'):
                with self.subTest(before=before, mode=mode):
                    self.root = Path(self.tmp.name)/(before+'-'+mode)
                    self.client = Fake()
                    self.client.codex_version = before
                    ident = self.prepare()
                    original_native = copy.deepcopy(self.load(ident)['targets'][0]['native'])
                    self.client.installed_codex_version = '0.172.0'
                    if mode == 'restore':
                        self.client.remove('term_target')
                    original = self.client.call
                    def upgraded_call(*args):
                        result = original(*args)
                        if (args[:2] == ('terminal', 'create') or
                                args[:2] == ('terminal', 'send') and
                                args[args.index('--text')+1].startswith(CODEX_RESUME)):
                            self.client.codex_version = '0.172.0'
                        return result
                    with patch.object(self.client, 'call', side_effect=upgraded_call):
                        row = self.execute(ident, mode)['targets'][0]
                    self.assertEqual('restarted', row['state'])
                    observed = row['nativeObserved']
                    self.assertEqual('0.172.0', observed['nativeVersion'])
                    for field in ('sessionId', 'cwd', 'permissions', 'resumeMode'):
                        self.assertEqual(original_native[field], observed[field])
                    self.assertEqual(original_native, self.load(ident)['targets'][0]['native'])
                    self.assertEqual(1 if mode == 'restore' else 0, len(self.client.created))
                    def launches():
                        return ([args[args.index('--command')+1] for args in self.client.created]
                                + [text for text in self.texts() if text.startswith(CODEX_RESUME)])
                    self.assertEqual([['codex', 'resume', SESSION,
                        '--dangerously-bypass-approvals-and-sandbox', '--no-alt-screen',
                        READINESS_PROMPT]], [shlex.split(command) for command in launches()])
                    self.assertEqual('already-running', self.execute(ident, 'verify')['targets'][0]['state'])
                    self.assertEqual('/status ', self.texts()[-1])
                    self.assertEqual(1 if mode == 'restore' else 0, len(self.client.created))
                    self.assertEqual(1, len(launches()))
                    self.assertNotIn(READINESS_PROMPT, self.texts())

    def test_owned_restore_can_verify_and_repeat_without_duplicate_or_reusing_changed_identity(self):
        for provider in ('codex', 'claude'):
            with self.subTest(provider=provider):
                self.root = Path(self.tmp.name)/provider
                self.client = Fake(provider)
                ident = self.prepare()
                self.client.remove('term_target')
                self.assertEqual('restarted', self.execute(ident, 'restore')['targets'][0]['state'])
                for mode in ('verify', 'restore'):
                    self.assertEqual('already-running', self.execute(ident, mode)['targets'][0]['state'])
                    self.assertEqual(1, len(self.client.created))
                self.client.sent.clear()
                self.client.terms['term_restored']['incarnationId'] = 'different-incarnation'
                row = self.execute(ident, 'verify')['targets'][0]
                self.assertEqual('unselected-or-uncertain-native-candidate', row['reason'])
                self.assertEqual([], self.client.sent)
                self.assertEqual(1, len(self.client.created))

    def test_owned_restore_readiness_rechecks_transient_child_state_before_status(self):
        ident = self.prepare()
        self.client.remove('term_target')
        self.client.sent.clear()
        original = m.target_from
        calls = []
        def ready(*args, **kwargs):
            self.assertEqual([], self.client.sent)
            calls.append(True)
            if len(calls) == 1:
                raise m.Deferred('child-state-unknown')
            return original(*args, **kwargs)
        with patch.object(m, 'target_from', side_effect=ready), patch.object(m.time, 'sleep') as sleep:
            row = self.execute(ident, 'restore')['targets'][0]
        self.assertEqual('restarted', row['state'])
        self.assertEqual(2, len(calls))
        sleep.assert_called_once_with(0.2)
        self.assertEqual(['/status'], self.texts())
        self.assertEqual(1, len(self.client.created))

    def test_owned_restore_persistent_child_unknown_stops_without_status_or_second_create(self):
        self.client.installed_codex_version = '0.172.0'
        ident = self.prepare()
        self.client.remove('term_target')
        self.client.sent.clear()
        with patch.object(m, 'target_from', side_effect=m.Deferred('child-state-unknown')) as target, \
             patch.object(m.time, 'monotonic', side_effect=[0, 0, 10]), patch.object(m.time, 'sleep') as sleep:
            row = self.execute(ident, 'restore')['targets'][0]
        self.assertEqual('failed', row['state'])
        self.assertEqual('child-state-unknown', row['reason'])
        self.assertEqual(2, target.call_count)
        sleep.assert_called_once_with(0.2)
        self.assertEqual([], self.client.sent)
        self.assertEqual(1, len(self.client.created))
        self.assertEqual(['codex', 'resume', SESSION,
            '--dangerously-bypass-approvals-and-sandbox', '--no-alt-screen', READINESS_PROMPT],
            shlex.split(self.client.created[0][self.client.created[0].index('--command')+1]))
        failed = self.load(ident)
        repeated = self.execute(ident, 'restore')['targets'][0]
        self.assertEqual('unresolved-attempt-verify-before-any-recovery', repeated['reason'])
        self.assertEqual(1, len(self.client.created))
        self.assertEqual([], self.client.sent)
        self.assertEqual(failed['targets'][0]['attempt'], self.load(ident)['targets'][0]['attempt'])

    def test_owned_restore_readiness_never_retries_other_safety_guards(self):
        for reason in ('child-work', 'busy-or-state-unknown', 'approval-or-wait', 'approval-or-menu', 'draft'):
            with self.subTest(reason=reason):
                self.root = Path(self.tmp.name)/str(uuid.uuid4())
                self.client = Fake()
                ident = self.prepare()
                self.client.remove('term_target')
                self.client.sent.clear()
                with patch.object(m, 'target_from', side_effect=m.Deferred(reason)) as target, \
                     patch.object(m.time, 'sleep') as sleep:
                    row = self.execute(ident, 'restore')['targets'][0]
                self.assertEqual(reason, row['reason'])
                target.assert_called_once()
                sleep.assert_not_called()
                self.assertEqual([], self.client.sent)
                self.assertEqual(1, len(self.client.created))

    def test_fresh_unsafe_matrix_receives_no_status_exit_resume(self):
        changes = [lambda c: c.agents['term_target'].update(state='working'),
                   lambda c: c.frames['term_target'].update(draft='pending'),
                   lambda c: c.frames['term_target'].update(tail=['› draft']),
                   lambda c: c.terms['term_target'].update(agentWait={'state': 'waiting'}),
                   lambda c: c.agents['term_target'].update(children=[{'state': 'working'}]),
                   lambda c: c.agents['term_target'].pop('subagentObservation'),
                   lambda c: c.frames['term_target'].update(tail=['›', 'Enter to confirm']),
                   lambda c: c.frames['term_target'].update(tail=['Conversation is open in another app', '›']),
                   lambda c: c.terms['term_target'].update(writable=False)]
        for i, change in enumerate(changes):
            with self.subTest(i=i):
                self.root = Path(self.tmp.name)/str(i)
                self.client = Fake()
                ident = self.prepare()
                self.client.sent.clear()
                change(self.client)
                self.assertEqual('deferred', self.execute(ident)['targets'][0]['state'])
                self.assertEqual([], self.client.sent)

    def test_prepare_unsafe_target_is_not_recaptured_on_execution(self):
        self.client.agents['term_target']['state'] = 'working'
        ident = self.prepare()
        self.client.agents['term_target']['state'] = 'idle'
        self.execute(ident)
        self.assertEqual([], self.client.sent)

    def test_first_failure_stops_later_targets_and_uncertain_attempt_cannot_replay(self):
        self.client.add('other', '/other')
        ident = self.prepare(['term_target', 'term_other'])
        self.client.sent.clear()
        self.client.fail = 'cli-unavailable-or-timeout'
        report = self.execute(ident)
        self.assertEqual('failed', report['targets'][0]['state'])
        self.assertEqual('deferred', report['targets'][1]['state'])
        self.assertEqual('previous-target-failed', report['targets'][1]['reason'])
        self.assertEqual(1, len(self.client.sent))
        self.client.fail = None
        self.execute(ident, 'restore')
        self.assertEqual(1, len(self.client.sent))
        with self.assertRaisesRegex(m.Deferred, 'unresolved-batch'):
            self.prepare()

    def test_verify_running_uuid_does_not_claim_restart_or_skip_later_explicit_restart(self):
        ident = self.prepare()
        self.client.fail = 'timeout'
        self.execute(ident)
        self.client.fail = None
        self.client.sent.clear()
        self.assertEqual('live-identity-confirmed-restart-unproven', self.execute(ident, 'verify')['targets'][0]['reason'])
        self.assertEqual(['/status'], self.texts())
        self.assertEqual([], self.client.created)
        self.assertNotEqual('complete', self.load(ident)['targets'][0]['attempt']['state'])
        self.client.sent.clear()
        self.assertEqual('restarted', self.execute(ident)['targets'][0]['state'])
        self.assertEqual(['/status', '/exit', CODEX_RESUME+SESSION+CODEX_OPTION, '/status'], self.texts())

    def test_resume_permission_drift_stops_later_targets(self):
        self.client.add('other', '/other')
        ident = self.prepare(['term_target', 'term_other'])
        self.client.sent.clear()
        self.client.change_after_resume = {'permissions': 'changed'}
        report = self.execute(ident)
        self.assertEqual('native-identity-or-permissions-mismatch', report['targets'][0]['reason'])
        self.assertEqual({'term_target'}, {a[a.index('--terminal')+1] for a in self.client.sent})

    def test_unselected_live_candidate_stops_before_input_or_creation(self):
        ident = self.prepare()
        self.client.add('duplicate', '/work')
        self.client.identities['term_duplicate']['sessionId'] = SESSION
        self.client.sent.clear()
        self.assertIn('uncertain', self.execute(ident, 'restore')['targets'][0]['reason'])
        self.assertEqual([], self.client.sent)
        self.assertEqual([], self.client.created)

    def test_multiple_selected_sessions_in_one_workspace_are_matched_by_uuid(self):
        self.client.add('other', '/work')
        ident = self.prepare(['term_target', 'term_other'])
        self.client.sent.clear()
        rows = self.execute(ident)['targets'][:2]
        self.assertEqual(['restarted', 'restarted'], [r['state'] for r in rows])
        self.assertEqual(2, self.texts().count('/exit'))
        self.assertEqual([], self.client.created)

    def test_partial_same_workspace_restore_then_verify_keeps_other_selected_session(self):
        self.client.add('other', '/work')
        other_before = copy.deepcopy(self.client.identities['term_other'])
        ident = self.prepare(['term_target', 'term_other'])
        self.client.remove('term_target')
        self.client.sent.clear()
        rows = self.execute(ident, 'restore')['targets'][:2]
        self.assertEqual(['restarted', 'already-running'], [r['state'] for r in rows])
        rows = self.execute(ident, 'verify')['targets'][:2]
        self.assertEqual(['already-running', 'already-running'], [r['state'] for r in rows])
        self.assertEqual(other_before, self.client.identities['term_other'])
        self.assertEqual(1, len(self.client.created))
        self.assertTrue(all(text == '/status' for text in self.texts()))

    def test_ps_only_or_unknown_pane_blocks_absence_with_or_without_other_selected_candidate(self):
        for other_live in (False, True):
            for unknown_pane in (False, True):
                with self.subTest(other_live=other_live, unknown_pane=unknown_pane):
                    self.root = Path(self.tmp.name)/str(uuid.uuid4())
                    self.client = Fake()
                    selected = ['term_target']
                    if other_live:
                        self.client.add('other', '/work')
                        selected.append('term_other')
                    ident = self.prepare(selected)
                    orphan = copy.deepcopy(self.client.agents['term_target'])
                    if unknown_pane:
                        orphan['paneKey'] = None
                    self.client.remove('term_target')
                    self.client.sent.clear()
                    original = self.client.inventory
                    def with_orphan():
                        ts, ps = original()
                        next(w for w in ps['worktrees'] if w['worktreeId'] == 'repo::/work')['agents'].append(copy.deepcopy(orphan))
                        return ts, ps
                    with patch.object(self.client, 'inventory', side_effect=with_orphan):
                        row = self.execute(ident, 'restore')['targets'][0]
                    self.assertEqual('unmatched-agent-identity', row['reason'])
                    self.assertEqual([], self.client.created)
                    self.assertTrue(all(a[a.index('--terminal')+1] == 'term_other' for a in self.client.sent))

    def test_ps_only_agent_appearing_before_owned_launch_is_rechecked_without_create(self):
        self.client.add('other', '/work')
        ident = self.prepare(['term_target', 'term_other'])
        orphan = copy.deepcopy(self.client.agents['term_target'])
        self.client.remove('term_target')
        self.client.sent.clear()
        inventory = self.client.inventory
        launch = m.owned_launch
        appeared = []
        def with_orphan():
            ts, ps = inventory()
            if appeared:
                next(w for w in ps['worktrees'] if w['worktreeId'] == 'repo::/work')['agents'].append(copy.deepcopy(orphan))
            return ts, ps
        def before_launch(*args, **kwargs):
            appeared.append(True)
            return launch(*args, **kwargs)
        with patch.object(self.client, 'inventory', side_effect=with_orphan), \
             patch.object(m, 'owned_launch', side_effect=before_launch):
            row = self.execute(ident, 'restore')['targets'][0]
        self.assertEqual([True], appeared)
        self.assertEqual('unmatched-agent-identity', row['reason'])
        self.assertEqual([], self.client.created)
        self.assertTrue(all(text == '/status' for text in self.texts()))

    def test_unknown_exception_identity_with_other_selected_live_never_proves_absence(self):
        self.client.add('other', '/work')
        self.client.add('excluded', '/work')
        ident = self.prepare(['term_target', 'term_other'], ['term_excluded'])
        self.client.remove('term_target')
        self.client.sent.clear()
        row = self.execute(ident, 'restore')['targets'][0]
        self.assertEqual('unmatched-agent-identity', row['reason'])
        self.assertEqual([], self.client.created)
        self.assertTrue(all(a[a.index('--terminal')+1] == 'term_other' for a in self.client.sent))

    def test_duplicate_uuid_among_selected_candidates_never_exits_or_launches(self):
        self.client.add('other', '/work')
        ident = self.prepare(['term_target', 'term_other'])
        self.client.identities['term_other']['sessionId'] = SESSION
        self.client.sent.clear()
        row = self.execute(ident)['targets'][0]
        self.assertEqual('duplicate-native-session', row['reason'])
        self.assertEqual(['/status', '/status'], self.texts())
        self.assertEqual([], self.client.created)

    def test_sparse_create_receipt_is_validated_with_fresh_terminal_show(self):
        ident = self.prepare()
        self.client.remove('term_target')
        original = self.client.call
        def sparse(*args):
            result = original(*args)
            return {'terminal': {'handle': result['terminal']['handle']}} if args[:2] == ('terminal', 'create') else result
        with patch.object(self.client, 'call', side_effect=sparse):
            self.assertEqual('restarted', self.execute(ident, 'restore')['targets'][0]['state'])

    def test_restore_wrong_provider_is_rejected_before_status_input(self):
        ident = self.prepare()
        self.client.remove('term_target')
        self.client.sent.clear()
        original = self.client.call
        def wrong_provider(*args):
            result = original(*args)
            if args[:2] == ('terminal','create'):
                self.client.terms['term_restored']['agentIdentity'] = 'claude'
                self.client.agents['term_restored']['agentType'] = 'claude'
                self.client.frames['term_restored']['tail'] = ['❯']
            return result
        with patch.object(self.client,'call',side_effect=wrong_provider):
            row = self.execute(ident,'restore')['targets'][0]
        self.assertEqual('restore-provider-mismatch',row['reason'])
        self.assertEqual([],self.client.sent)

    def test_list_absent_state_and_existing_state_are_read_only(self):
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(0, m.main(['list', '--state', str(self.root)]))
        self.assertEqual({'batches': []}, json.loads(out.getvalue()))
        self.assertFalse(self.root.exists())
        ident = self.prepare()
        before = {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in self.root.iterdir()}
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(0, m.main(['list', '--state', str(self.root)]))
        self.assertEqual([ident], [b['batchId'] for b in json.loads(out.getvalue())['batches']])
        self.assertEqual(before, {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in self.root.iterdir()})

    def test_requesting_management_shell_is_not_reported_as_native_manual_restart(self):
        self.client.agents.pop('term_self')
        self.client.terms['term_self']['agentIdentity'] = None
        ident = self.prepare()
        self.assertEqual(['term_target'], [r['targetId'] for r in m.report(self.load(ident))['targets']])

    def zero_input_batch(self, management=False):
        self.client = Fake('claude')
        self.client.frames['term_target']['tail'] = ['❯', '  auto mode']
        self.client.add('tail', '/tail')
        self.client.add('last', '/last', 'claude')
        self.client.add('manual', '/manual')
        if management:
            self.client.agents.pop('term_self')
            self.client.terms['term_self']['agentIdentity'] = None
        ident = self.screen_execute(lambda: self.prepare(
            ['term_target', 'term_tail', 'term_last'], ['term_manual']))
        self.assertEqual([], self.client.sent)
        self.assertEqual(['preparation-failed', 'prepared'], [e['phase'] for e in self.load(ident)['events']])
        self.assertEqual('claude-permissions-unknown', self.load(ident)['targets'][0]['reason'])
        return ident

    def continue_preparation(self, ident, excluded=None, self_pane=None):
        with m.Store(self.root, existing_only=True) as store:
            return m.continue_prepare(self.client, store, ident,
                                      ['term_target'] if excluded is None else excluded,
                                      self.self_pane if self_pane is None else self_pane)

    def test_continue_preparation_preserves_signed_batch_and_queries_only_original_tail_in_order(self):
        for management in (False, True):
            with self.subTest(management=management), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                ident = self.zero_input_batch(management)
                before = self.load(ident)
                key = (self.root/'integrity.key').read_bytes()
                files = {p.name for p in self.root.iterdir()}
                observe = self.client.observe
                def tail_only(handle):
                    self.assertIn(handle, ('term_tail', 'term_last'))
                    return observe(handle)
                with patch.object(self.client, 'observe', side_effect=tail_only):
                    result = self.continue_preparation(ident)
                after = self.load(ident)
                for field in ('batchId', 'createdAt', 'binding', 'preparedRuntime', 'hostLabel'):
                    self.assertEqual(before[field], after[field])
                self.assertEqual(before['events'], after['events'][:2])
                self.assertEqual(before['targets'][3:], after['targets'][3:])
                for old, new in zip(before['targets'], after['targets']):
                    self.assertEqual(old['terminal'], new['terminal'])
                    self.assertEqual(old['targetId'], new['targetId'])
                    self.assertIsNone(new['attempt'])
                self.assertEqual('manual', after['targets'][0]['choice'])
                self.assertEqual('manual-restart-required', after['targets'][0]['state'])
                self.assertIsNone(after['targets'][0]['native'])
                self.assertEqual('preparation-manual-exclusion', after['events'][2]['phase'])
                for row in after['targets'][1:3]:
                    self.assertEqual(self.client.identities[row['targetId']]['sessionId'], row['native']['sessionId'])
                    self.assertEqual(self.client.identities[row['targetId']]['cwd'], row['native']['cwd'])
                    self.assertEqual(self.client.identities[row['targetId']]['permissions'], row['native']['permissions'])
                    self.assertEqual('ready', row['state'])
                self.assertEqual(['term_tail', 'term_last'], [a[a.index('--terminal')+1] for a in self.client.sent])
                self.assertEqual(['/status', '/status'], self.texts())
                self.assertEqual([], self.client.created)
                self.assertEqual('complete', result['prepareState'])
                self.assertTrue(all(r['consumption'] == 'unverified' and r['consumedVersion'] is None for r in result['targets']))
                self.assertEqual(key, (self.root/'integrity.key').read_bytes())
                self.assertEqual(files, {p.name for p in self.root.iterdir()})
                before_repeat = copy.deepcopy(after)
                with self.assertRaisesRegex(m.Deferred, 'continuation-not-admissible'):
                    self.continue_preparation(ident)
                self.assertEqual(before_repeat, self.load(ident))
                self.assertEqual(2, len(self.client.sent))

    def test_continue_preparation_rejects_wrong_exclusions_without_changes_or_input(self):
        ident = self.zero_input_batch()
        before = self.load(ident)
        for excluded in ([], ['term_tail'], ['term_new'], ['term_target', 'term_tail'], ['term_target']*2):
            with self.subTest(excluded=excluded), self.assertRaisesRegex(m.Deferred, 'continuation-not-admissible'):
                self.continue_preparation(ident, excluded)
            self.assertEqual(before, self.load(ident))
        self.assertEqual([], self.client.sent)

    def test_continue_preparation_rejects_receipts_attempts_states_and_nonexact_history(self):
        changes = ('sending', 'accepted', 'modal', 'exit', 'create', 'resume', 'attempt', 'native',
                   'incomplete', 'failed-reason', 'failure-target', 'failure-handle', 'failure-operation',
                   'extra-event', 'missing-event', 'tail-ready', 'tail-installation', 'duplicate-target')
        for change in changes:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                ident = self.zero_input_batch()
                with m.Store(self.root) as store:
                    body = store.load(ident)
                    if change in ('sending', 'accepted', 'modal', 'exit', 'create', 'resume'):
                        body['events'].insert(0, {'phase': change})
                    elif change == 'attempt':
                        body['targets'][1]['attempt'] = {'state': 'not-submitted'}
                    elif change == 'native':
                        body['targets'][1]['native'] = copy.deepcopy(self.client.identities['term_tail'])
                    elif change == 'incomplete':
                        body['prepareState'] = 'uncertain'
                    elif change == 'failed-reason':
                        body['targets'][0]['reason'] = 'unknown'
                    elif change == 'failure-target':
                        body['events'][0]['targetId'] = 'term_tail'
                    elif change == 'failure-handle':
                        body['targets'][0]['targetId'] = 'term_other'
                        body['events'][0]['targetId'] = 'term_other'
                    elif change == 'failure-operation':
                        body['events'][0]['operationId'] = 'other'
                    elif change == 'extra-event':
                        body['events'].append({'phase': 'prepared'})
                    elif change == 'missing-event':
                        body['events'].pop()
                    elif change == 'tail-ready':
                        body['targets'][1]['state'] = 'pending'
                    elif change == 'tail-installation':
                        body['targets'][1]['installationPrepared'] = INSTALL
                    else:
                        # Duplicate selection must be rejected by signed record validation.
                        body['targets'].append(copy.deepcopy(body['targets'][1]))
                    if change == 'duplicate-target':
                        with self.assertRaisesRegex(m.Deferred, 'duplicate-or-empty-targets'):
                            store.save(body)
                        continue
                    store.save(body)
                before = self.load(ident)
                with self.assertRaisesRegex(m.Deferred, 'continuation-not-admissible'):
                    self.continue_preparation(ident)
                self.assertEqual(before, self.load(ident))
                self.assertEqual([], self.client.sent)

    def test_continue_preparation_rejects_binding_runtime_all_fingerprints_and_stored_self_changes(self):
        for drift in ('binding', 'runtime', 'failed', 'tail', 'last', 'manual', 'self', 'caller'):
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                ident = self.zero_input_batch()
                before = self.load(ident)
                if drift == 'binding':
                    m.binding.return_value = {'machine': 'different', 'profile': 'owned-profile'}
                elif drift == 'runtime':
                    self.client.runtime = 'changed'
                elif drift != 'caller':
                    self.client.terms['term_'+drift if drift != 'failed' else 'term_target']['incarnationId'] = 'changed'
                try:
                    with self.assertRaises(m.Deferred):
                        self.continue_preparation(ident, self_pane='tab:tail' if drift == 'caller' else None)
                    self.assertEqual(before, self.load(ident))
                    self.assertEqual([], self.client.sent)
                finally:
                    m.binding.return_value = {'machine': 'owned-machine', 'profile': 'owned-profile'}

    def test_continue_preparation_tamper_and_other_unresolved_batch_never_query(self):
        ident = self.zero_input_batch()
        path = self.root/(ident+'.json')
        original = path.read_bytes()
        path.write_bytes(original.replace(b'claude-permissions-unknown', b'claude-permissions-tamper'))
        with self.assertRaisesRegex(m.Deferred, 'batch-integrity-mismatch'):
            self.continue_preparation(ident)
        path.write_bytes(original)
        with m.Store(self.root) as store:
            other = copy.deepcopy(store.load(ident))
            other.update(batchId=str(uuid.uuid4()), prepareState='started')
            store.save(other, new=True)
        with self.assertRaisesRegex(m.Deferred, 'unresolved-batch'):
            self.continue_preparation(ident)
        self.assertEqual([], self.client.sent)

    def test_continue_preparation_unsafe_tail_keeps_first_stop_and_durable_manual_decision(self):
        for unsafe in ('working', 'draft', 'approval', 'child', 'unknown', 'installation', 'provider', 'self'):
            with self.subTest(unsafe=unsafe), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                ident = self.zero_input_batch(management=unsafe == 'self')
                if unsafe == 'working':
                    self.client.agents['term_tail']['state'] = 'working'
                elif unsafe == 'draft':
                    self.client.frames['term_tail']['draft'] = 'owned draft'
                elif unsafe == 'approval':
                    self.client.terms['term_tail']['agentWait'] = {'kind': 'approval'}
                elif unsafe == 'child':
                    self.client.agents['term_tail']['children'] = [{'state': 'working'}]
                elif unsafe == 'unknown':
                    self.client.terms['term_tail']['agentIdentity'] = None
                elif unsafe == 'installation':
                    m.rr.plugin_inventory.side_effect = m.Deferred('installed-versions-unverified')
                elif unsafe == 'provider':
                    self.client.terms['term_tail']['agentIdentity'] = 'claude'
                    self.client.agents['term_tail']['agentType'] = 'claude'
                    self.client.frames['term_tail']['tail'] = ['❯', 'Permission mode: bypass permissions']
                result = self.continue_preparation(ident, self_pane='tab:tail' if unsafe == 'self' else None)
                after = self.load(ident)
                self.assertEqual('manual', after['targets'][0]['choice'])
                self.assertEqual('deferred', result['targets'][1]['state'])
                self.assertEqual('previous-target-failed', result['targets'][2]['reason'])
                self.assertEqual('preparation-manual-exclusion', after['events'][2]['phase'])
                self.assertEqual([], self.client.sent)
                self.assertEqual([], self.client.created)
                m.rr.plugin_inventory.side_effect = lambda provider, cwd: {**copy.deepcopy(INSTALL), 'nativeVersion': (
                    self.client.installed_codex_version if provider == 'codex' else self.client.installed_claude_version)}

    def test_continue_preparation_rechecks_runtime_installation_and_fingerprint_after_admission(self):
        for drift in ('runtime', 'installation', 'fingerprint'):
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                ident = self.zero_input_batch()
                inventory = m.rr.plugin_inventory.side_effect
                changed = []
                def interleave(provider, cwd):
                    result = inventory(provider, cwd)
                    if cwd == '/tail' and not changed:
                        changed.append(True)
                        if drift == 'runtime':
                            self.client.runtime = 'changed'
                        elif drift == 'installation':
                            self.client.installed_codex_version = 'changed'
                        else:
                            self.client.terms['term_tail']['incarnationId'] = 'changed'
                    return result
                with patch.object(m.rr, 'plugin_inventory', side_effect=interleave):
                    result = self.continue_preparation(ident)
                self.assertEqual([True], changed)
                self.assertEqual('deferred', result['targets'][1]['state'])
                self.assertEqual('previous-target-failed', result['targets'][2]['reason'])
                self.assertEqual([], self.client.sent)
                self.assertEqual([], self.client.created)

    def test_continue_preparation_decision_storage_failure_has_no_native_input(self):
        ident = self.zero_input_batch()
        before = self.load(ident)
        with patch.object(m.Store, 'save', side_effect=OSError('owned write failure')), self.assertRaises(OSError):
            self.continue_preparation(ident)
        self.assertEqual(before, self.load(ident))
        self.assertEqual([], self.client.sent)

    def test_continue_preparation_crash_after_decision_stays_started_and_cannot_repeat_or_discover(self):
        ident = self.zero_input_batch()
        with patch.object(m, 'prepare_rows', side_effect=OSError('owned crash')), self.assertRaises(OSError):
            self.continue_preparation(ident)
        after = self.load(ident)
        self.assertEqual('started', after['prepareState'])
        self.assertEqual('manual', after['targets'][0]['choice'])
        with self.assertRaisesRegex(m.Deferred, 'continuation-not-admissible'):
            self.continue_preparation(ident)
        with self.assertRaisesRegex(m.Deferred, 'receipt-unmatched'):
            self.execute(ident, 'verify')
        self.assertEqual(after, self.load(ident))
        self.assertEqual([], self.client.sent)

    def test_continue_preparation_acknowledged_failure_verify_only_queries_acknowledged_tail(self):
        ident = self.zero_input_batch()
        status = m.rr.native_status
        def incomplete(*args, **kwargs):
            status(*args, **kwargs)
            raise m.Deferred('native-identity-unknown')
        with patch.object(m.rr, 'native_status', side_effect=incomplete):
            result = self.continue_preparation(ident)
        before = self.load(ident)
        self.assertEqual('uncertain', result['prepareState'])
        self.assertEqual(['term_tail'], [a[a.index('--terminal')+1] for a in self.client.sent])
        self.client.sent.clear()
        result = self.execute(ident, 'verify')
        after = self.load(ident)
        self.assertEqual('complete', result['prepareState'])
        self.assertEqual(before['events'], after['events'][:len(before['events'])])
        self.assertEqual(before['targets'][0], after['targets'][0])
        self.assertEqual(before['targets'][2:], after['targets'][2:])
        self.assertEqual('ready', after['targets'][1]['state'])
        self.assertEqual(['term_tail'], [a[a.index('--terminal')+1] for a in self.client.sent])
        self.assertEqual([], self.client.created)

    def test_continue_preparation_verify_rejects_forged_or_duplicate_manual_decision(self):
        for mutation in ('handle', 'reason', 'duplicate'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                ident = self.zero_input_batch()
                status = m.rr.native_status
                def incomplete(*args, **kwargs):
                    status(*args, **kwargs)
                    raise m.Deferred('native-identity-unknown')
                with patch.object(m.rr, 'native_status', side_effect=incomplete):
                    self.continue_preparation(ident)
                with m.Store(self.root) as store:
                    body = store.load(ident)
                    if mutation == 'duplicate':
                        body['events'].append(copy.deepcopy(body['events'][2]))
                    else:
                        body['events'][2][mutation] = 'changed'
                    store.save(body)
                self.client.sent.clear()
                with self.assertRaisesRegex(m.Deferred, 'status-only-required'):
                    self.execute(ident, 'verify')
                self.assertEqual([], self.client.sent)

    def test_continue_preparation_unacknowledged_send_and_storage_failure_never_replay(self):
        for failure in ('send', 'identity-save'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                ident = self.zero_input_batch()
                save = m.Store.save
                def fail_identity(store, body, *args, **kwargs):
                    if body['targets'][1].get('native') is not None:
                        raise OSError('owned durable identity failure')
                    return save(store, body, *args, **kwargs)
                if failure == 'send':
                    self.client.fail = 'lost-status-receipt'
                    self.continue_preparation(ident)
                else:
                    with patch.object(m.Store, 'save', new=fail_identity), self.assertRaises(OSError):
                        self.continue_preparation(ident)
                before = self.load(ident)
                self.assertEqual(1, len(self.client.sent))
                self.assertEqual('manual', before['targets'][0]['choice'])
                self.client.fail = None
                with self.assertRaisesRegex(m.Deferred, 'continuation-not-admissible'):
                    self.continue_preparation(ident)
                if failure == 'send':
                    with self.assertRaisesRegex(m.Deferred, 'receipt-unmatched'):
                        self.execute(ident, 'verify')
                else:
                    self.execute(ident, 'verify')
                    self.assertEqual('ready', self.load(ident)['targets'][1]['state'])
                    self.assertEqual('previous-target-failed', self.load(ident)['targets'][2]['reason'])
                self.assertEqual([], self.client.created)

    def test_continue_preparation_cli_requires_existing_state_key_batch_and_exact_arguments(self):
        missing = self.root/'missing'
        for args in ([], ['--batch', str(uuid.uuid4())],
                     ['--batch', str(uuid.uuid4()), '--exclude', 'term_target'],
                     ['--batch', str(uuid.uuid4()), '--exclude', 'term_target', '--target', 'term_tail']):
            with redirect_stdout(io.StringIO()), patch.object(m.rr, 'Orca', side_effect=AssertionError('runtime')):
                self.assertEqual(2, m.main(['continue-prepare', '--state', str(missing), *args]))
            self.assertFalse(self.root.exists())
        ident = self.zero_input_batch()
        key = self.root/'integrity.key'
        saved_key = key.read_bytes()
        key.unlink()
        with redirect_stdout(io.StringIO()), patch.object(m.rr, 'Orca', side_effect=AssertionError('runtime')):
            self.assertEqual(2, m.main(['continue-prepare', '--state', str(self.root), '--batch', ident, '--exclude', 'term_target']))
        self.assertFalse(key.exists())
        key.write_bytes(saved_key)
        key.chmod(0o600)
        with redirect_stdout(io.StringIO()), patch.object(m.rr, 'Orca', side_effect=AssertionError('runtime')):
            self.assertEqual(2, m.main(['continue-prepare', '--state', str(self.root), '--batch', str(uuid.uuid4()), '--exclude', 'term_target']))
        with redirect_stdout(io.StringIO()) as output, patch.object(m.rr, 'Orca', return_value=self.client), \
             patch.dict(os.environ, {'ORCA_PANE_KEY': self.self_pane}):
            self.assertEqual(0, m.main(['continue-prepare', '--state', str(self.root), '--batch', ident, '--exclude', 'term_target']))
        self.assertEqual(ident, json.loads(output.getvalue())['batchId'])
        (self.root/'batch.lock').unlink()
        with redirect_stdout(io.StringIO()), patch.object(m.rr, 'Orca', side_effect=AssertionError('runtime')):
            self.assertEqual(2, m.main(['continue-prepare', '--state', str(self.root), '--batch', ident, '--exclude', 'term_target']))
        self.assertFalse((self.root/'batch.lock').exists())

    def test_prepare_timeout_is_durable_and_prevents_new_status_submission(self):
        self.client.fail = 'timeout'
        ident = self.prepare()
        self.assertEqual('uncertain', self.load(ident)['prepareState'])
        self.client.fail = None
        with self.assertRaisesRegex(m.Deferred, 'unresolved-batch'):
            self.prepare()
        self.assertEqual(1, len(self.client.sent))

    def interrupted_preparation(self, selected=None, excluded=None):
        original = m.rr.native_status
        def acknowledged_then_incomplete(*args, **kwargs):
            original(*args, **kwargs)
            raise m.Deferred('native-identity-unknown')
        with patch.object(m.rr, 'native_status', side_effect=acknowledged_then_incomplete):
            return self.prepare(selected, excluded)

    def test_verify_acknowledged_preparation_preserves_failure_tail_exclusions_and_signed_store(self):
        self.client.add('tail', '/tail')
        self.client.add('manual', '/manual')
        ident = self.interrupted_preparation(['term_target', 'term_tail'], ['term_manual'])
        before = self.load(ident)
        self.assertEqual('uncertain', before['prepareState'])
        self.assertEqual(['sending', 'accepted', 'preparation-failed', 'prepared'],
                         [e['phase'] for e in before['events']])
        self.client.sent.clear()
        with patch.object(m, 'locate', side_effect=AssertionError('ordinary discovery')):
            result = self.execute(ident, 'verify')
        after = self.load(ident)
        self.assertEqual('complete', after['prepareState'])
        self.assertEqual(before['events'], after['events'][:len(before['events'])])
        self.assertEqual(before['targets'][1:], after['targets'][1:])
        self.assertEqual(['/status'], self.texts())
        self.assertEqual([], self.client.created)
        row = after['targets'][0]
        self.assertEqual(SESSION, row['native']['sessionId'])
        self.assertEqual('/work', row['native']['cwd'])
        self.assertEqual('Full Access', row['native']['permissions'])
        self.assertEqual('ready', row['state'])
        self.assertIsNone(row['attempt'])
        self.assertEqual('unverified', result['targets'][0]['consumption'])
        self.assertIsNone(result['targets'][0]['consumedVersion'])
        self.assertIn('preparation-verified', [e['phase'] for e in after['events']])
        verified = next(e for e in after['events'] if e['phase'] == 'preparation-verified')
        self.assertIn('screenSha256', verified['nativeProof'])
        self.assertEqual('complete', result['prepareState'])

    def screen_execute(self, operation):
        clock = [0.0]
        with patch.object(m.rr.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(m.rr.time, 'sleep', side_effect=lambda duration: clock.__setitem__(0, clock[0]+duration)):
            return operation()

    def test_complete_batch_screen_status_prepare_and_verify_never_launch_or_lose_history(self):
        self.client = ScreenStatusFake()
        ident = self.prepare()
        before = self.load(ident)
        self.assertEqual('complete', before['prepareState'])
        self.assertEqual(SESSION, before['targets'][0]['native']['sessionId'])
        self.client.sent.clear()
        result = self.execute(ident, 'verify')
        after = self.load(ident)
        self.assertEqual(before['events'], after['events'][:len(before['events'])])
        self.assertEqual(SESSION, after['targets'][0]['native']['sessionId'])
        self.assertEqual(['/status'], self.texts())
        self.assertEqual([], self.client.created)
        self.assertEqual('unverified', result['targets'][0]['consumption'])
        self.assertIsNone(result['targets'][0]['consumedVersion'])

    def test_incomplete_batch_screen_status_verify_preserves_signed_failure_tail_exclusions_and_proof(self):
        self.client = ScreenStatusFake()
        self.client.add('tail', '/tail')
        self.client.add('manual', '/manual')
        self.client.stale_status = True
        ident = self.screen_execute(lambda: self.prepare(['term_target', 'term_tail'], ['term_manual']))
        before = self.load(ident)
        self.assertEqual('uncertain', before['prepareState'])
        self.assertIsNone(before['targets'][0]['native'])
        self.client.stale_status = False
        self.client.sent.clear()
        with patch.object(m, 'locate', side_effect=AssertionError('ordinary discovery')):
            result = self.execute(ident, 'verify')
        after = self.load(ident)
        self.assertEqual('complete', after['prepareState'])
        self.assertEqual(before['events'], after['events'][:len(before['events'])])
        self.assertEqual(before['targets'][1:], after['targets'][1:])
        self.assertEqual('ready', after['targets'][0]['state'])
        self.assertEqual(SESSION, after['targets'][0]['native']['sessionId'])
        verified = next(e for e in after['events'] if e['phase'] == 'preparation-verified')
        self.assertEqual(m.rr.output_proof(self.client.frames['term_target']), verified['nativeProof'])
        self.assertEqual({'cursor', 'screenSha256'}, set(verified['nativeProof']))
        self.assertEqual(['/status'], self.texts())
        self.assertEqual([], self.client.created)
        self.assertIsNone(after['targets'][0]['attempt'])
        self.assertEqual('unverified', result['targets'][0]['consumption'])
        self.assertIsNone(result['targets'][0]['consumedVersion'])

    def test_incomplete_batch_screen_conflict_keeps_failure_and_first_failure_stop(self):
        self.client = ScreenStatusFake()
        self.client.add('tail', '/tail')
        self.client.stale_status = True
        ident = self.screen_execute(lambda: self.prepare(['term_target', 'term_tail']))
        before = self.load(ident)
        self.client.stale_status = False
        self.client.conflict = True
        self.client.sent.clear()
        result = self.execute(ident, 'verify')
        after = self.load(ident)
        self.assertEqual('uncertain', result['prepareState'])
        self.assertEqual('native-response-identity-changed', result['targets'][0]['reason'])
        self.assertEqual(before['events'], after['events'][:len(before['events'])])
        self.assertEqual(before['targets'][1:], after['targets'][1:])
        self.assertIsNone(after['targets'][0]['native'])
        self.assertEqual(['/status'], self.texts())
        self.assertEqual([], self.client.created)

    def test_verify_preparation_legacy_row_failure_is_retained_as_event(self):
        ident = self.interrupted_preparation()
        with m.Store(self.root) as store:
            batch = store.load(ident)
            batch['events'] = [e for e in batch['events'] if e['phase'] != 'preparation-failed']
            store.save(batch)
        self.execute(ident, 'verify')
        failures = [e for e in self.load(ident)['events'] if e['phase'] == 'preparation-failed']
        self.assertEqual('native-identity-unknown', failures[0]['reason'])

    def test_verify_legacy_management_shell_preparation_needs_no_invented_past_self(self):
        self.client.agents.pop('term_self')
        self.client.terms['term_self']['agentIdentity'] = None
        self.client.frames['term_self']['tail'] = ['owner@host:/caller$']
        ident = self.interrupted_preparation()
        before = self.load(ident)
        self.assertEqual(['term_target'], [row['targetId'] for row in before['targets']])
        self.client.sent.clear()
        result = self.execute(ident, 'verify')
        self.assertEqual('complete', result['prepareState'])
        self.assertEqual(['/status'], self.texts())
        self.assertEqual(['term_target'], [row['targetId'] for row in self.load(ident)['targets']])

    def test_verify_preparation_never_sends_to_current_self(self):
        ident = self.interrupted_preparation()
        self.client.sent.clear()
        with m.Store(self.root) as store:
            result = m.execute(self.client, store, ident, 'tab:target', 'verify')
        self.assertEqual('self', result['targets'][0]['reason'])
        self.assertEqual('uncertain', result['prepareState'])
        self.assertEqual([], self.texts())

    def test_verify_preparation_crash_after_identity_save_requires_fresh_same_identity(self):
        ident = self.interrupted_preparation()
        original_save = m.Store.save
        def crash_before_outcome(store, body, *args, **kwargs):
            if body.get('prepareState') == 'complete':
                raise OSError('owned outcome write failed')
            return original_save(store, body, *args, **kwargs)
        with patch.object(m.Store, 'save', new=crash_before_outcome), self.assertRaises(OSError):
            self.execute(ident, 'verify')
        persisted = self.load(ident)
        self.assertEqual('uncertain', persisted['prepareState'])
        self.assertEqual(SESSION, persisted['targets'][0]['native']['sessionId'])
        self.client.sent.clear()
        result = self.execute(ident, 'verify')
        self.assertEqual('complete', result['prepareState'])
        self.assertEqual(['/status'], self.texts())

    def test_verify_preparation_with_saved_identity_rejects_new_uuid(self):
        ident = self.prepare()
        with m.Store(self.root) as store:
            batch = store.load(ident)
            batch['prepareState'] = 'started'
            store.save(batch)
        self.client.identities['term_target']['sessionId'] = str(uuid.uuid4())
        self.client.sent.clear()
        result = self.execute(ident, 'verify')
        self.assertIn('identity-or-permissions-mismatch', result['targets'][0]['reason'])
        self.assertEqual('started', result['prepareState'])
        self.assertEqual(SESSION, self.load(ident)['targets'][0]['native']['sessionId'])
        self.assertEqual(['/status'], self.texts())

    def test_verify_unacknowledged_preparation_remains_blocked_without_input(self):
        self.client.fail = 'timeout'
        ident = self.prepare()
        self.client.fail = None
        self.client.sent.clear()
        before = self.load(ident)
        with self.assertRaisesRegex(m.Deferred, 'receipt-unmatched'):
            self.execute(ident, 'verify')
        self.assertEqual(before, self.load(ident))
        self.assertEqual([], self.texts())
        with self.assertRaisesRegex(m.Deferred, 'unresolved-batch'):
            self.prepare()

    def test_verify_preparation_rejects_mismatched_receipts_mutation_navigation_and_attempts(self):
        for label in ('request', 'operation', 'handle', 'duplicate', 'mutation', 'navigation', 'attempt'):
            with self.subTest(label=label):
                self.root = Path(self.tmp.name)/label
                self.client = Fake()
                ident = self.interrupted_preparation()
                with m.Store(self.root) as store:
                    batch = store.load(ident)
                    accepted = next(e for e in batch['events'] if e['phase'] == 'accepted')
                    if label == 'request':
                        accepted['requestId'] = None
                    elif label in ('operation', 'handle'):
                        accepted['operationId' if label == 'operation' else 'handle'] = 'different'
                    elif label == 'attempt':
                        batch['targets'][0]['attempt'] = {'state': 'complete'}
                    elif label == 'duplicate':
                        batch['events'].extend(copy.deepcopy(batch['events'][:2]))
                    else:
                        batch['events'].append({'phase': 'sending', 'targetId': 'term_target',
                                                'handle': 'term_target', 'operationId': 'other',
                                                'step': 'normal-exit' if label == 'mutation' else 'modal-key'})
                    store.save(batch)
                self.client.sent.clear()
                with self.assertRaises(m.Deferred):
                    self.execute(ident, 'verify')
                self.assertEqual([], self.texts())
                self.assertEqual('uncertain', self.load(ident)['prepareState'])

    def test_verify_preparation_preserves_unresolved_on_binding_runtime_terminal_and_unsafe_state(self):
        for label in ('binding', 'runtime', 'terminal', 'busy', 'draft', 'child', 'provider', 'self'):
            with self.subTest(label=label):
                self.root = Path(self.tmp.name)/label
                self.client = Fake()
                ident = self.interrupted_preparation()
                if label == 'binding':
                    with m.Store(self.root) as store:
                        batch = store.load(ident)
                        batch['binding']['profile'] = 'other'
                        store.save(batch)
                elif label == 'runtime':
                    self.client.runtime = 'other'
                elif label == 'terminal':
                    self.client.terms['term_target']['incarnationId'] = 'other'
                elif label == 'busy':
                    self.client.agents['term_target']['state'] = 'working'
                elif label == 'draft':
                    self.client.frames['term_target']['draft'] = 'typed'
                elif label == 'child':
                    self.client.agents['term_target']['children'] = [{'state': 'working'}]
                elif label == 'provider':
                    self.client.terms['term_target']['agentIdentity'] = 'claude'
                else:
                    self.client.terms['term_self']['leafId'] = 'moved'
                self.client.sent.clear()
                try:
                    self.execute(ident, 'verify')
                except m.Deferred:
                    pass
                self.assertEqual([], self.texts())
                self.assertEqual([], self.client.created)
                self.assertEqual('uncertain', self.load(ident)['prepareState'])

    def test_verify_preparation_cannot_restart_restore_or_bypass_other_unresolved_batch(self):
        ident = self.interrupted_preparation()
        self.client.sent.clear()
        for mode in ('restart', 'restore'):
            with self.assertRaisesRegex(m.Deferred, 'preparation-incomplete'):
                self.execute(ident, mode)
        with m.Store(self.root) as store:
            other = copy.deepcopy(store.load(ident))
            other['batchId'] = str(uuid.uuid4())
            store.save(other, new=True)
        with self.assertRaisesRegex(m.Deferred, 'unresolved-batch'):
            self.execute(ident, 'verify')
        self.assertEqual([], self.texts())

    def test_verify_preparation_failed_fresh_query_retains_uncertainty_and_never_retries(self):
        ident = self.interrupted_preparation()
        self.client.sent.clear()
        self.client.fail = 'timeout'
        result = self.execute(ident, 'verify')
        self.assertEqual('timeout', result['targets'][0]['reason'])
        self.assertEqual(['/status'], self.texts())
        self.assertEqual('uncertain', self.load(ident)['prepareState'])
        self.client.fail = None
        self.client.sent.clear()
        with self.assertRaisesRegex(m.Deferred, 'receipt-unmatched'):
            self.execute(ident, 'verify')
        self.assertEqual([], self.texts())

    def test_verify_preparation_rechecks_installation_before_native_input(self):
        ident = self.interrupted_preparation()
        self.client.sent.clear()
        current = m.rr.plugin_inventory('codex', '/work')
        changed = {**current, 'nativeVersion': 'different'}
        with patch.object(m.rr, 'plugin_inventory', side_effect=[current, current, changed]):
            report = self.execute(ident, 'verify')
        self.assertEqual('installed-versions-drift', report['targets'][0]['reason'])
        self.assertEqual([], self.texts())
        self.assertEqual('uncertain', self.load(ident)['prepareState'])

    def test_exception_identity_unknown_after_runtime_change_defers(self):
        self.client.add('excluded', '/work')
        ident = self.prepare(excluded=['term_excluded'])
        self.client.replace_handle()
        self.client.sent.clear()
        self.assertIn('excluded-identity-unknown', self.execute(ident, 'restore')['targets'][0]['reason'])
        self.assertEqual([], self.client.sent)

    def test_wrong_native_identity_does_not_exit_or_launch(self):
        ident = self.prepare()
        self.client.identities['term_target']['sessionId'] = str(uuid.uuid4())
        self.client.sent.clear()
        row = self.execute(ident, 'restore')['targets'][0]
        self.assertEqual('native-identity-or-permissions-mismatch', row['reason'])
        self.assertEqual(['/status'], self.texts())
        self.assertEqual([], self.client.created)

    def test_host_profile_drift_no_input(self):
        ident = self.prepare()
        self.client.sent.clear()
        with patch.object(m, 'binding', return_value={'machine': 'another', 'profile': 'owned-profile'}):
            with self.assertRaisesRegex(m.Deferred, 'machine-or-profile'):
                self.execute(ident)
        self.assertEqual([], self.client.sent)

    def test_remote_and_unidentified_requester_refused(self):
        for remote in (True, False):
            self.client.remote_configured = remote
            with m.Store(self.root) as store:
                with self.assertRaises(m.Deferred):
                    m.prepare(self.client, store, ['term_target'], [], None if not remote else self.self_pane)
        self.assertEqual([], self.client.sent)

    def test_storage_failure_before_submission_sends_nothing(self):
        ident = self.prepare()
        self.client.sent.clear()
        with m.Store(self.root) as store:
            with patch.object(store, 'save', side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):
                    m.execute(self.client, store, ident, self.self_pane, 'restart')
        self.assertEqual([], self.client.sent)

    def test_storage_failure_after_exit_preserves_durable_sending_and_blocks_replay(self):
        ident = self.prepare()
        self.client.sent.clear()
        with m.Store(self.root) as store:
            original = store.save
            def fail_on_exit_receipt(body, **kw):
                if any(e.get('step') == 'normal-exit' and e['phase'] == 'accepted' for e in body['events']):
                    raise OSError('disk failure')
                return original(body, **kw)
            with patch.object(store, 'save', side_effect=fail_on_exit_receipt):
                row = m.execute(self.client, store, ident, self.self_pane, 'restart')['targets'][0]
                self.assertEqual('failed', row['state'])
        self.assertEqual(['/status', '/exit'], self.texts())
        self.execute(ident)
        self.assertEqual(['/status', '/exit'], self.texts())

    def test_tamper_symlink_hardlink_and_open_permissions_fail_closed(self):
        ident = self.prepare()
        path = self.root/(ident+'.json')
        original = path.read_bytes()
        data = json.loads(original)
        data['batch']['targets'][0]['native']['permissions'] = 'changed'
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(m.Deferred, 'integrity'):
            self.load(ident)
        path.write_bytes(original)
        path.chmod(0o644)
        with self.assertRaisesRegex(m.Deferred, 'unsafe-state-file'):
            self.load(ident)
        path.chmod(0o600)
        os.link(path, self.root/'hardlink')
        with self.assertRaisesRegex(m.Deferred, 'unsafe-state-file'):
            self.load(ident)
        (self.root/'hardlink').unlink()
        path.rename(self.root/'original')
        path.symlink_to(self.root/'original')
        with self.assertRaises(OSError):
            self.load(ident)

    def test_parent_symlink_and_directory_replacement_refused(self):
        self.root.mkdir(mode=0o700)
        link = Path(self.tmp.name)/'link'
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            with m.Store(link):
                pass
        ident = self.prepare()
        with m.Store(self.root) as store:
            self.root.rename(self.root.with_name('moved'))
            self.root.mkdir(mode=0o700)
            with self.assertRaisesRegex(m.Deferred, 'directory-replaced'):
                store.load(ident)

    def test_concurrent_operations_refused_and_crash_lock_file_is_reusable(self):
        ident = self.prepare()
        with m.Store(self.root):
            with self.assertRaisesRegex(m.Deferred, 'locked'):
                with m.Store(self.root):
                    pass
        self.assertEqual(ident, self.load(ident)['batchId'])

    def test_restore_rechecks_last_lookup_before_create_for_appeared_candidates(self):
        for kind in ('selected', 'native', 'unknown', 'other-provider', 'ps-only'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                self.client = Fake()
                ident = self.prepare()
                orphan = copy.deepcopy(self.client.agents['term_target'])
                self.client.remove('term_target')
                self.client.sent.clear()
                lookup, inventory = m.rr.installation_guard, self.client.inventory
                injected = []
                observed = []
                observe = self.client.observe
                def guarded(target):
                    result = lookup(target)
                    if target['identity']['handle'] == 'term_target':
                        if not injected:
                            injected.append(True)
                            if kind != 'ps-only':
                                name = 'target' if kind == 'selected' else 'new'
                                h = self.client.add(name, '/work', None if kind == 'unknown' else 'claude' if kind == 'other-provider' else 'codex')
                                self.client.identities[h]['sessionId'] = SESSION
                    return result
                def fresh():
                    ts, ps = inventory()
                    if injected and kind == 'ps-only':
                        next(w for w in ps['worktrees'] if w['worktreeId'] == 'repo::/work')['agents'].append(orphan)
                    return ts, ps
                def read(handle):
                    if injected:
                        observed.append(handle)
                    return observe(handle)
                with patch.object(m.rr, 'installation_guard', side_effect=guarded), \
                     patch.object(self.client, 'inventory', side_effect=fresh), patch.object(self.client, 'observe', side_effect=read):
                    row = self.execute(ident, 'restore')['targets'][0]
                self.assertEqual([True], injected)
                self.assertEqual('restore-safety-state-changed', row['reason'])
                self.assertEqual([], self.client.created)
                self.assertEqual([], self.client.sent)
                self.assertEqual([], observed)
                self.assertEqual('not-submitted', self.load(ident)['targets'][0]['attempt']['state'])

    def test_restore_rechecks_runtime_workspace_self_and_selected_state_after_last_lookup(self):
        for change in ('runtime', 'self', 'workspace-path', 'workspace-host', 'busy', 'draft', 'fingerprint', 'permissions'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                self.client = Fake()
                self.client.add('other', '/work')
                ident = self.prepare(['term_target', 'term_other'])
                self.client.remove('term_target')
                self.client.sent.clear()
                lookup, inventory = m.rr.installation_guard, self.client.inventory
                injected = []
                def guarded(target):
                    result = lookup(target)
                    if target['identity']['handle'] == 'term_target' and not injected:
                        injected.append(True)
                        if change == 'runtime':
                            self.client.runtime = 'new'
                        elif change == 'self':
                            self.client.terms['term_self']['leafId'] = 'new'
                        elif change == 'busy':
                            self.client.agents['term_other']['state'] = 'working'
                        elif change == 'draft':
                            self.client.frames['term_other'].update(draft='SECRET pending', tail=['› pending'])
                        elif change == 'fingerprint':
                            self.client.terms['term_other']['incarnationId'] = 'new'
                        elif change == 'permissions':
                            frame = self.client.frames['term_other']
                            frame['latestCursor'] = str(int(frame['latestCursor']) + 1)
                            frame['tail'] = ['Permissions: Custom', '›']
                    return result
                def fresh():
                    ts, ps = inventory()
                    if injected and change in ('workspace-path', 'workspace-host'):
                        w = next(w for w in ps['worktrees'] if w['worktreeId'] == 'repo::/work')
                        w['path' if change == 'workspace-path' else 'hostId'] = 'changed'
                    return ts, ps
                with patch.object(m.rr, 'installation_guard', side_effect=guarded), patch.object(self.client, 'inventory', side_effect=fresh):
                    row = self.execute(ident, 'restore')['targets'][0]
                self.assertEqual([True], injected)
                self.assertEqual('failed', row['state'])  # Earlier status already has a durable sending receipt.
                self.assertEqual([], self.client.created)
                self.assertTrue(all(a[a.index('--terminal')+1] == 'term_other' for a in self.client.sent))
                self.assertTrue(all(text == '/status' for text in self.texts()))
                self.assertNotIn('SECRET', json.dumps(row))

    def test_selected_same_pane_uuid_change_during_last_lookup_uses_bound_response_proof(self):
        for changed in ('cursor-and-output', 'cursor-only', 'output-only', 'missing-cursor'):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                self.client = Fake()
                self.client.add('other', '/work')
                ident = self.prepare(['term_target', 'term_other'])
                self.client.remove('term_target')
                self.client.sent.clear()
                before_term = copy.deepcopy(self.client.terms['term_other'])
                before_agent = copy.deepcopy(self.client.agents['term_other'])
                lookup = m.rr.installation_guard
                injected = []
                def guarded(target):
                    result = lookup(target)
                    if target['identity']['handle'] == 'term_target' and not injected:
                        injected.append(True)
                        self.client.identities['term_other']['sessionId'] = SESSION
                        frame = self.client.frames['term_other']
                        if changed != 'output-only':
                            frame['latestCursor'] = None if changed == 'missing-cursor' else str(int(frame['latestCursor']) + 1)
                        if changed != 'cursor-only':
                            frame['tail'] = ['Session ID: '+SESSION, 'cwd: /work', 'Permissions: Full Access', '›']
                    return result
                send = self.client.call
                def no_new_input(*args):
                    if injected and args[:2] == ('terminal', 'send'):
                        self.fail('status input after final lookup')
                    return send(*args)
                with patch.object(m.rr, 'installation_guard', side_effect=guarded), patch.object(self.client, 'call', side_effect=no_new_input):
                    row = self.execute(ident, 'restore')['targets'][0]
                self.assertEqual([True], injected)
                self.assertIn(row['reason'], ('native-response-proof-changed', 'native-response-proof-unknown'))
                self.assertEqual(before_term, self.client.terms['term_other'])
                self.assertEqual(before_agent, self.client.agents['term_other'])
                self.assertEqual([], self.client.created)
                self.assertEqual(1, sum(i['sessionId'] == SESSION for i in self.client.identities.values()))
                self.assertTrue(all(text == '/status' for text in self.texts()))

    def test_selected_empty_shell_output_change_during_lookup_never_creates_duplicate(self):
        ident = self.prepare()
        self.client.terms['term_target']['agentIdentity'] = None
        self.client.agents['term_target']['agentType'] = None
        self.client.frames['term_target']['tail'] = ['owned@host:/work$']
        self.client.sent.clear()
        guard = m.rr.installation_guard
        injected = []
        def changed(target):
            result = guard(target)
            if not injected:
                injected.append(True)
                self.client.frames['term_target'].update(latestCursor='11', tail=['Session ID: '+SESSION, '›'])
            return result
        with patch.object(m.rr, 'installation_guard', side_effect=changed):
            row = self.execute(ident, 'restore')['targets'][0]
        self.assertEqual('native-response-proof-changed', row['reason'])
        self.assertEqual([], self.client.created)
        self.assertEqual([], self.client.sent)

    def test_missing_response_bound_proof_is_not_replaced_by_new_cursor_baseline(self):
        self.client.add('other', '/work')
        ident = self.prepare(['term_target', 'term_other'])
        self.client.remove('term_target')
        self.client.sent.clear()
        status = m.rr.native_status
        def without_proof(client, plan, target, *args, **kwargs):
            result = status(client, plan, target, *args, **kwargs)
            target.pop('nativeProof', None)
            return result
        with patch.object(m.rr, 'native_status', side_effect=without_proof):
            row = self.execute(ident, 'restore')['targets'][0]
        self.assertEqual('native-response-proof-unknown', row['reason'])
        self.assertEqual([], self.client.created)

    def test_unselected_native_unknown_panes_never_receive_observe_or_input(self):
        for provider in (None, 'codex'):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                self.client = Fake()
                ident = self.prepare()
                self.client.remove('term_target')
                self.client.add('unselected', '/work', provider)
                self.client.sent.clear()
                with patch.object(self.client, 'observe', side_effect=AssertionError('unselected screen')):
                    row = self.execute(ident, 'restore')['targets'][0]
                self.assertEqual('unselected-or-uncertain-native-candidate', row['reason'])
                self.assertEqual([], self.client.created)
                self.assertEqual([], self.client.sent)

    def test_post_status_wait_uuid_switch_and_stale_startup_never_create(self):
        for changed in ('uuid', 'startup', 'another-command', 'missing-identity', 'during-stream'):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                self.client = Fake()
                self.client.add('other', '/work')
                ident = self.prepare(['term_target', 'term_other'])
                self.client.remove('term_target')
                self.client.sent.clear()
                call = self.client.call
                switched = []
                def switch():
                    switched.append(True)
                    self.client.identities['term_other']['sessionId'] = SESSION
                    frame = self.client.frames['term_other']
                    frame['latestCursor'] = str(int(frame['latestCursor'])+1)
                    if changed in ('uuid', 'during-stream'):
                        frame['tail'] = ['OpenAI Codex (v0.171.0)', 'Session ID: '+SESSION,
                                         'cwd: /work', 'Permissions: Full Access', '›']
                    elif changed == 'startup':
                        frame['tail'] += ['OpenAI Codex (v0.171.0)', '› Ask Codex to do anything']
                    elif changed == 'another-command':
                        frame['tail'] += ['› /help', 'Native help', '›']
                    else:
                        frame['tail'] = ['OpenAI Codex (v0.171.0)', '›']
                def interleave(*args):
                    result = call(*args)
                    status_sent = self.texts() == ['/status']
                    trigger = ('terminal', 'read') if changed == 'during-stream' else ('terminal', 'wait')
                    if status_sent and args[:2] == trigger and not switched:
                        switch()
                    return result
                with patch.object(self.client, 'call', side_effect=interleave):
                    row = self.execute(ident, 'restore')['targets'][0]
                self.assertEqual([True], switched)
                self.assertIn(row['reason'], ('native-response-identity-changed', 'native-identity-unknown',
                                              'native-response-boundary-changed', 'native-response-proof-changed'))
                self.assertEqual([], self.client.created)
                self.assertEqual(['/status'], self.texts())
                self.assertEqual(1, sum(i['sessionId'] == SESSION for i in self.client.identities.values()))

    def test_positive_multi_selected_restore_for_codex_and_claude_modal(self):
        for provider in ('codex', 'claude'):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                self.client = Fake() if provider == 'codex' else ModalFake()
                self.client.add('other', '/work', provider)
                ident = self.prepare(['term_target', 'term_other'])
                self.client.remove('term_target')
                self.client.sent.clear()
                call = self.client.call
                decision = []
                def at_create(*args):
                    if args[:2] == ('terminal', 'create'):
                        decision.append(True)
                        if provider == 'claude':
                            self.assertEqual({'term_other'}, self.client.modals)
                    return call(*args)
                with patch.object(self.client, 'call', side_effect=at_create):
                    report = self.execute(ident, 'restore')
                self.assertEqual(['restarted', 'already-running'], [r['state'] for r in report['targets'][:2]])
                self.assertEqual([True], decision)
                self.assertEqual(1, len(self.client.created))
                self.assertEqual(1, sum(i['sessionId'] == SESSION for i in self.client.identities.values()))
                if provider == 'claude':
                    self.assertFalse(self.client.modals)
                    self.assertEqual(self.texts().count('/status'), self.texts().count('\x1b'))
                    self.assertTrue(any(e['phase'] == 'owned-status-modal-closed' for e in self.load(ident)['events']))

    def test_claude_modal_retained_lookup_switch_defers_without_escape_or_create(self):
        for changed in ('uuid', 'closed', 'busy', 'draft', 'installation'):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                self.client = ModalFake()
                self.client.add('other', '/work', 'claude')
                ident = self.prepare(['term_target', 'term_other'])
                self.client.remove('term_target')
                self.client.sent.clear()
                original_uuid = self.client.identities['term_other']['sessionId']
                lookup = m.rr.installation_guard
                switched = []
                def interleave(target):
                    result = lookup(target)
                    if target['identity']['handle'] == 'term_target' and not switched:
                        self.assertEqual({'term_other'}, self.client.modals)
                        switched.append(True)
                        frame = self.client.frames['term_other']
                        if changed == 'uuid':
                            self.client.identities['term_other']['sessionId'] = SESSION
                            frame['tail'] = [line.replace(original_uuid, SESSION)
                                             for line in frame['tail']]
                        elif changed == 'closed':
                            self.client.modals.clear()
                            frame['tail'] = ['❯', 'Permission mode: bypass permissions']
                        elif changed == 'busy':
                            self.client.agents['term_other']['state'] = 'working'
                        elif changed == 'draft':
                            frame['draft'] = 'SECRET draft'
                        else:
                            self.client.installed_claude_version = 'changed'
                            raise m.Deferred('installation-changed')
                    return result
                with patch.object(m.rr, 'installation_guard', side_effect=interleave):
                    row = self.execute(ident, 'restore')['targets'][0]
                self.assertEqual([True], switched)
                self.assertEqual([], self.client.created)
                # Initial locate closed its own modal; the retained modal never gets an Esc.
                self.assertEqual(['/status', '\x1b', '/status'], self.texts())
                self.assertEqual('failed', row['state'])
                events = self.load(ident)['events']
                self.assertTrue(any(e['phase'] == 'manual-status-modal-cleanup-required' for e in events))
                self.assertNotIn('SECRET', json.dumps(row))

    def test_claude_owned_modal_partial_failure_cleanup_and_lost_escape_never_replay(self):
        for failure in ('create', 'identity', 'lost-escape', 'changed-after-create'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                self.client = ModalFake()
                self.client.add('other', '/work', 'claude')
                ident = self.prepare(['term_target', 'term_other'])
                self.client.remove('term_target')
                self.client.sent.clear()
                call, lookup = self.client.call, m.rr.installation_guard
                pending = []
                def interleave(*args):
                    if args[:2] == ('terminal', 'create'):
                        pending.append(True)
                        if failure == 'create':
                            self.client.created.append(args)
                            raise m.Deferred('cli-unavailable-or-timeout')
                    result = call(*args)
                    if pending and args[:2] == ('terminal', 'create') and failure == 'changed-after-create':
                        self.client.frames['term_other']['tail'] = ['SECRET changed UI']
                    if (pending and failure == 'lost-escape' and args[:2] == ('terminal', 'send')
                            and args[args.index('--text')+1] == '\x1b'):
                        raise m.Deferred('cli-unavailable-or-timeout')
                    return result
                def identity_change(target):
                    result = lookup(target)
                    # The first closed modal belongs to initial locate. Switch the
                    # second response itself, then let finally close its exact frame.
                    if (failure == 'identity' and self.texts() == ['/status', '\x1b']
                            and target['identity']['handle'] == 'term_other'):
                        self.client.identities['term_other']['sessionId'] = str(uuid.uuid4())
                    return result
                with patch.object(self.client, 'call', side_effect=interleave), \
                     patch.object(m.rr, 'installation_guard', side_effect=identity_change):
                    row = self.execute(ident, 'restore')['targets'][0]
                self.assertEqual('failed', row['state'])
                events = self.load(ident)['events']
                if failure in ('create', 'identity'):
                    self.assertFalse(self.client.modals)
                    self.assertTrue(any(e['phase'] == 'owned-status-modal-closed' for e in events))
                else:
                    self.assertEqual('owned-status-modal-cleanup-unverified', row['reason'])
                    self.assertTrue(any(e['phase'] == 'manual-status-modal-cleanup-required' for e in events))
                    self.assertEqual('term_restored', self.load(ident)['targets'][0]['ownedHandle'])
                before = (len(self.client.created), len(self.client.sent))
                self.execute(ident, 'restore')
                self.assertEqual(before, (len(self.client.created), len(self.client.sent)))
                if failure == 'changed-after-create':
                    self.assertEqual(['/status', '\x1b', '/status'], self.texts())
                self.assertNotIn('SECRET', json.dumps(row))

    def test_claude_pre_escape_uuid_switch_and_post_escape_switch_never_duplicate(self):
        for when in ('pre', 'post'):
            with self.subTest(when=when), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                self.client = ModalFake()
                self.client.add('other', '/work', 'claude')
                ident = self.prepare(['term_target', 'term_other'])
                self.client.remove('term_target')
                self.client.sent.clear()
                lookup, call = m.rr.installation_guard, self.client.call
                switched = []
                def switch():
                    switched.append(True)
                    old = self.client.identities['term_other']['sessionId']
                    self.client.identities['term_other']['sessionId'] = SESSION
                    frame = self.client.frames['term_other']
                    frame['tail'] = [line.replace(old, SESSION) for line in frame['tail']]
                    frame['latestCursor'] = str(int(frame['latestCursor'])+1)
                def pre(target):
                    result = lookup(target)
                    if when == 'pre' and self.client.modals and not switched:
                        switch()
                    return result
                def post(*args):
                    result = call(*args)
                    if (when == 'post' and args[:2] == ('terminal', 'send')
                            and args[args.index('--text')+1] == '\x1b' and not switched):
                        switch()
                    return result
                with patch.object(m.rr, 'installation_guard', side_effect=pre), patch.object(self.client, 'call', side_effect=post):
                    row = self.execute(ident, 'restore')['targets'][0]
                self.assertEqual([True], switched)
                self.assertEqual([], self.client.created)
                self.assertEqual(1, sum(i['sessionId'] == SESSION for i in self.client.identities.values()))
                if when == 'pre':
                    self.assertEqual(['/status'], self.texts())
                    self.assertEqual('native-response-proof-changed', row['reason'])
                else:
                    self.assertIn(row['reason'], ('native-identity-or-permissions-mismatch', 'session-appeared-before-launch'))

    def test_unknown_foreground_and_unverified_workspace_never_launch(self):
        ident = self.prepare()
        self.client.terms['term_target']['agentIdentity'] = None
        self.client.frames['term_target']['tail'] = ['an unknown foreground program']
        self.client.sent.clear()
        self.assertEqual('unknown-foreground', self.execute(ident, 'restore')['targets'][0]['reason'])
        self.assertEqual([], self.client.created)
        self.assertEqual([], self.client.sent)

    def test_unknown_create_receipt_is_not_retried(self):
        ident = self.prepare()
        self.client.remove('term_target')
        self.client.fail = 'lost-create-receipt'
        self.execute(ident, 'restore')
        self.client.fail = None
        self.execute(ident, 'restore')
        self.assertEqual(1, len(self.client.created))

    def test_lost_create_then_absent_verify_preserves_uncertain_attempt_without_resend(self):
        ident = self.prepare()
        self.client.remove('term_target')
        self.client.sent.clear()
        self.client.fail = 'lost-create-receipt'
        self.assertEqual('failed', self.execute(ident, 'restore')['targets'][0]['state'])
        attempt = copy.deepcopy(self.load(ident)['targets'][0]['attempt'])
        self.assertEqual('uncertain', attempt['state'])
        self.client.fail = None
        self.assertEqual('session-absent-use-explicit-restore', self.execute(ident, 'verify')['targets'][0]['reason'])
        self.assertEqual(attempt, self.load(ident)['targets'][0]['attempt'])
        row = self.execute(ident, 'restore')['targets'][0]
        self.assertEqual('unresolved-attempt-verify-before-any-recovery', row['reason'])
        self.assertEqual(attempt, self.load(ident)['targets'][0]['attempt'])
        self.assertEqual(1, len(self.client.created))
        self.assertEqual([], self.client.sent)

    def test_absent_restart_defers_then_explicit_restore_can_run_without_replay(self):
        ident = self.prepare()
        self.client.remove('term_target')
        self.client.sent.clear()
        row = self.execute(ident)['targets'][0]
        self.assertEqual('session-absent-use-explicit-restore', row['reason'])
        self.assertEqual('not-submitted', self.load(ident)['targets'][0]['attempt']['state'])
        self.assertEqual([], self.client.created)
        self.assertEqual('restarted', self.execute(ident,'restore')['targets'][0]['state'])
        self.assertEqual(1, len(self.client.created))

    def test_durable_list_in_separate_process_preserves_original_choices_and_identity(self):
        ident = self.prepare()
        result = subprocess.run([sys.executable, str(SCRIPT), 'list', '--batch', ident, '--state', str(self.root)],
                                text=True, capture_output=True)
        self.assertEqual(0, result.returncode, result.stderr)
        rows = json.loads(result.stdout)['targets']
        self.assertEqual(SESSION,rows[0]['nativePrepared']['sessionId'])
        self.assertEqual('manual-restart-required',rows[1]['state'])

    def test_complete_inventory_required(self):
        original = self.client.inventory
        def truncated():
            ts, ps = original()
            ps['truncated'] = True
            return ts, ps
        with patch.object(self.client, 'inventory', side_effect=truncated):
            with self.assertRaisesRegex(m.Deferred, 'inventory-incomplete'):
                self.prepare()
        self.assertEqual([], self.client.sent)

    def test_plain_python_query_preserves_source_bytes_and_does_not_create_cache(self):
        before = {str(p): p.read_bytes() for p in SCRIPT.parent.rglob('*') if p.is_file()}
        env = dict(os.environ)
        env.pop('PYTHONDONTWRITEBYTECODE', None)
        result = subprocess.run([sys.executable, str(SCRIPT), 'list', '--state', str(self.root)],
                                text=True, capture_output=True, env=env)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({'batches': []}, json.loads(result.stdout))
        self.assertEqual(before, {str(p): p.read_bytes() for p in SCRIPT.parent.rglob('*') if p.is_file()})

    def mixed_recovery_batch(self):
        class Mixed(ModalFake):
            def __init__(self):
                super().__init__()
                self.versions = {'term_target': '2.1.319', 'term_other': '2.1.329'}
                self.installed_claude_version = '2.1.331'
            def call(inner, *args):
                result = super(Mixed, inner).call(*args)
                if args[:2] == ('terminal', 'send') and args[args.index('--text')+1] == '/status':
                    handle = args[args.index('--terminal')+1]
                    version = inner.versions.get(handle, '2.1.331')
                    inner.frames[handle]['tail'][1] = ' Version: '+version
                    if version == '2.1.319':
                        inner.frames[handle]['tail'][-1] = ' Esc to cancel'
                return result
        self.client = Mixed()
        self.client.add('other', '/other', 'claude')
        self.client.add('tail', '/tail', 'claude')
        self.client.add('manual', '/manual', 'claude')
        original = m.rr.native_status
        def interrupted(client, plan, target, self_pane, log, **kwargs):
            if target['handle'] == 'term_other':
                original(client, plan, target, self_pane, log, keep_modal=True)
                raise m.Deferred('idle-prompt-unknown')
            native = original(client, plan, target, self_pane, log, **kwargs)
            if target['handle'] == 'term_target':
                native['resumeMode'] = None  # historical pre-fix observation
            return native
        with patch.object(m.rr, 'native_status', side_effect=interrupted):
            ident = self.prepare(['term_target', 'term_other', 'term_tail'], ['term_manual'])
        self.client.sent.clear()
        return ident

    def recover_preparation(self, ident):
        with m.Store(self.root, existing_only=True) as store:
            return m.recover_prepare(self.client, store, ident, self.self_pane)

    def test_recover_mixed_native_legacy_ready_and_pending_card_preserves_signed_history(self):
        ident = self.mixed_recovery_batch()
        before = self.load(ident)
        key = (self.root/'integrity.key').read_bytes()
        with self.assertRaisesRegex(m.Deferred, 'status-only-required'):
            self.execute(ident, 'verify')
        result = self.recover_preparation(ident)
        after = self.load(ident)
        self.assertEqual('complete', result['prepareState'])
        self.assertEqual(before['events'], after['events'][:len(before['events'])])
        self.assertEqual(key, (self.root/'integrity.key').read_bytes())
        for key in ('batchId', 'binding', 'createdAt', 'preparedRuntime'):
            self.assertEqual(before[key], after[key])
        self.assertEqual(before['targets'][0]['native'], after['targets'][0]['native'])
        self.assertIsNone(after['targets'][0]['native']['resumeMode'])
        self.assertEqual(before['targets'][2:], after['targets'][2:])
        self.assertEqual(['/status', '\x1b', '\x1b', '/status', '\x1b'], self.texts())
        self.assertFalse(self.client.created)
        self.assertFalse(self.client.modals)
        for row in after['targets'][:2]:
            self.assertEqual('claude-bypass-permissions', m.resume_basis(after, row)['resumeMode'])
            self.assertIsNone(row['attempt'])
        # Later explicit restore uses fresh mode while keeping native319 null history.
        self.client.remove('term_target')
        self.client.sent.clear()
        restored = self.execute(ident, 'restore')
        self.assertEqual('restarted', restored['targets'][0]['state'])
        self.assertEqual(CLAUDE_RESUME+SESSION, self.client.created[0][-1])
        self.assertEqual(before['targets'][0]['native'], self.load(ident)['targets'][0]['native'])

    def test_recover_cleanup_card_identity_must_continue_into_fresh_status_before_adoption(self):
        for field in ('sessionId', 'cwd'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                ident = self.mixed_recovery_batch()
                before = self.load(ident)
                cleanup_session = self.client.identities['term_other']['sessionId']
                original = self.client.call
                def switched_status(*args):
                    if (args[:2] == ('terminal', 'send')
                            and args[args.index('--terminal')+1] == 'term_other'
                            and args[args.index('--text')+1] == '/status'):
                        self.client.identities['term_other'][field] = str(uuid.uuid4()) if field == 'sessionId' else '/different'
                    return original(*args)
                with patch.object(self.client, 'call', side_effect=switched_status):
                    result = self.recover_preparation(ident)
                after = self.load(ident)
                self.assertEqual('uncertain', result['prepareState'])
                row = after['targets'][1]
                self.assertIsNone(row['native'])
                self.assertNotIn('resumeAttestation', row)
                self.assertEqual('claude-cleanup-identity-changed' if field == 'sessionId' else 'cwd-mismatch', row['reason'])
                self.assertEqual(before['events'], after['events'][:len(before['events'])])
                self.assertEqual(['/status', '\x1b', '\x1b', '/status', '\x1b'], self.texts())
                self.assertFalse(self.client.created)
                if field == 'sessionId':
                    self.assertNotEqual(cleanup_session, self.client.identities['term_other']['sessionId'])

    def test_recover_unknown_status_card_with_background_prompt_never_receives_input(self):
        for change in ('version', 'footer', 'orphan-footer'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                ident = self.mixed_recovery_batch()
                frame = self.client.frames['term_target']
                frame['tail'] = ['Settings  Status  Config  Usage  Stats',
                                 'Version: 2.1.329', 'Session ID: '+SESSION, 'cwd: /work',
                                 '←/→ to switch · Esc to close', '❯',
                                 '  ⏵⏵ bypass permissions on (shift+tab to cycle)']
                if change == 'version': frame['tail'][1] = 'Version: 2.1.333'
                elif change == 'footer': frame['tail'][4] = '←/→ to switch · Esc to quit'
                else:
                    frame['tail'].pop(0)
                    frame['tail'][0] = 'Version: 2.1.333'
                self.assertFalse(m.rr.claude_modal(m.rr.screen(frame), '/status'))
                result = self.recover_preparation(ident)
                self.assertEqual('uncertain', result['prepareState'])
                self.assertEqual('approval-or-menu', result['targets'][0]['reason'])
                self.assertFalse(self.texts())
                self.assertFalse(self.client.created)

    def test_recover_unknown_status_card_drift_before_native_status_never_receives_input(self):
        ident = self.mixed_recovery_batch()
        original = self.client.observe
        count = [0]
        def drift(handle):
            if handle == 'term_target':
                count[0] += 1
                if count[0] == 2:  # native_status full guard after initial recovery observation
                    self.client.frames[handle]['tail'] = [
                        'Settings  Status  Config  Usage  Stats', 'Version: 2.1.333',
                        'Session ID: '+SESSION, 'cwd: /work', '←/→ to switch · Esc to close',
                        '❯', '  ⏵⏵ bypass permissions on (shift+tab to cycle)']
            return original(handle)
        with patch.object(self.client, 'observe', side_effect=drift):
            result = self.recover_preparation(ident)
        self.assertEqual(2, count[0])
        self.assertEqual('uncertain', result['prepareState'])
        self.assertEqual('approval-or-menu', result['targets'][0]['reason'])
        self.assertFalse(self.texts())
        self.assertFalse(self.client.created)

    def test_recover_rejects_unknown_receipts_attempts_and_unqueried_authority_without_input(self):
        mutations = ('unmatched', 'lost', 'extra', 'manual', 'self', 'unqueried', 'attempt',
                     'raw-size', 'raw-accepted', 'raw-incarnation', 'raw-unresolved')
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                ident = self.mixed_recovery_batch()
                with m.Store(self.root) as store:
                    batch = store.load(ident)
                    status = next(e for e in batch['events'] if e['phase'] == 'accepted' and e.get('step') == 'status')
                    raw = next(e for e in batch['events'] if e['phase'] == 'accepted' and e.get('step') == 'modal-navigation')
                    if mutation == 'unmatched': status['operationId'] = 'other'
                    elif mutation == 'lost': batch['events'].remove(status)
                    elif mutation == 'extra': batch['events'].append({'phase': 'exit'})
                    elif mutation == 'manual': batch['targets'][0]['choice'] = 'manual'
                    elif mutation == 'self':
                        batch['targets'][0]['terminal'] = copy.deepcopy(batch['targets'][-1]['terminal'])
                    elif mutation == 'unqueried':
                        for e in batch['events']:
                            if e.get('targetId') == 'term_other': e.update(targetId='term_tail', handle='term_tail')
                    elif mutation == 'attempt': batch['targets'][0]['attempt'] = {'state': 'started'}
                    elif mutation == 'raw-size': raw['bytesWritten'] = 3
                    elif mutation == 'raw-accepted': raw['accepted'] = False
                    elif mutation == 'raw-incarnation': raw['processIncarnation'] = 'other'
                    elif mutation == 'raw-unresolved': batch['targets'][0].update(native=None, state='deferred')
                    store.save(batch)
                with self.assertRaises(m.Deferred): self.recover_preparation(ident)
                self.assertFalse(self.texts())
                self.assertFalse(self.client.created)

    def test_recover_pending_card_metadata_and_all_current_guards_stop_without_cleanup(self):
        changes = ('uuid-missing', 'uuid-duplicate', 'cwd', 'version', 'approval', 'draft', 'working',
                   'child', 'wait', 'runtime', 'fingerprint', 'installation')
        for change in changes:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                ident = self.mixed_recovery_batch()
                # First row remains valid; stop second without sending its cleanup/status.
                frame = self.client.frames['term_other']
                if change == 'uuid-missing': frame['tail'] = [x for x in frame['tail'] if 'Session ID:' not in x]
                elif change == 'uuid-duplicate': frame['tail'].append('Session ID: '+str(uuid.uuid4()))
                elif change == 'cwd': frame['tail'][3] = 'cwd: /wrong'
                elif change == 'version': frame['tail'][1] = 'Version: 2.1.333'
                elif change == 'approval': frame['tail'].append('Allow once')
                elif change == 'draft': frame['draft'] = 'typed'
                elif change == 'working': self.client.agents['term_other']['state'] = 'working'
                elif change == 'child': self.client.agents['term_other']['children'] = ['child']
                elif change == 'wait': self.client.terms['term_other']['agentWait'] = 'approval'
                elif change == 'runtime': self.client.runtime = 'changed'
                elif change == 'fingerprint': self.client.terms['term_other']['incarnationId'] = 'changed'
                elif change == 'installation': self.client.installed_claude_version = '2.1.332'
                if change in ('runtime', 'fingerprint'):
                    with self.assertRaises(m.Deferred): self.recover_preparation(ident)
                    self.assertFalse(self.texts())
                elif change == 'installation':
                    # Installed-version support gates launch separately; drift gates actions.
                    original = m.rr.plugin_inventory
                    calls = [0]
                    def drift(*args):
                        calls[0] += 1
                        value = original(*args)
                        if calls[0] > 1: value['nativeVersion'] = 'changed'
                        return value
                    with patch.object(m.rr, 'plugin_inventory', side_effect=drift):
                        result = self.recover_preparation(ident)
                    self.assertEqual('uncertain', result['prepareState'])
                else:
                    result = self.recover_preparation(ident)
                    self.assertEqual('uncertain', result['prepareState'])
                    self.assertEqual(['/status', '\x1b'], self.texts())
                self.assertFalse(self.client.created)

    def test_recover_storage_transport_identity_proof_failures_are_one_shot_and_first_stop(self):
        for failure in ('start-storage', 'cleanup-lost', 'status-lost', 'proof', 'identity', 'attest-storage'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                ident = self.mixed_recovery_batch()
                before = self.load(ident)
                original_call = self.client.call
                original_save = m.Store.save
                original_observe = self.client.observe
                def call(*args):
                    if args[:2] == ('terminal', 'send'):
                        h = args[args.index('--terminal')+1]
                        text = args[args.index('--text')+1]
                        if failure == 'cleanup-lost' and h == 'term_other' and text == '\x1b':
                            original_call(*args)
                            raise m.Deferred('lost-cleanup-receipt')
                        if failure == 'status-lost' and text == '/status':
                            original_call(*args)
                            raise m.Deferred('lost-status-receipt')
                    return original_call(*args)
                def save(store, batch, *args, **kwargs):
                    if ((failure == 'start-storage' and batch.get('preparationRecovery')) or
                        (failure == 'attest-storage' and batch['events'][-1]['phase'] == 'preparation-mode-attested')):
                        raise OSError('owned storage failure')
                    return original_save(store, batch, *args, **kwargs)
                counts = [0]
                def observe(handle):
                    t, frame = original_observe(handle)
                    if failure == 'proof' and handle == 'term_other':
                        counts[0] += 1
                        if counts[0] >= 2: frame['tail'].append('drift')
                    return t, frame
                if failure == 'identity': self.client.identities['term_target']['sessionId'] = str(uuid.uuid4())
                with patch.object(self.client, 'call', side_effect=call), patch.object(m.Store, 'save', save), patch.object(self.client, 'observe', side_effect=observe):
                    if failure == 'start-storage':
                        with self.assertRaises(OSError): self.recover_preparation(ident)
                    else:
                        result = self.recover_preparation(ident)
                        self.assertEqual('uncertain', result['prepareState'])
                after = self.load(ident)
                self.assertEqual(before['events'], after['events'][:len(before['events'])])
                if failure == 'start-storage': self.assertFalse(self.texts())
                else:
                    count = len(self.texts())
                    with self.assertRaisesRegex(m.Deferred, 'not-admissible'): self.recover_preparation(ident)
                    self.assertEqual(count, len(self.texts()))
                self.assertFalse(self.client.created)

    def test_legacy_resume_basis_requires_exact_signed_attestation_and_supported_fresh_mode(self):
        ident = self.mixed_recovery_batch()
        before = self.load(ident)
        legacy = before['targets'][0]
        with self.assertRaisesRegex(m.Deferred, 'permissions-unverified'):
            m.rr.resume_command('claude', m.resume_basis(before, legacy), installed_version='2.1.331')
        self.recover_preparation(ident)
        batch = self.load(ident)
        for change in ('uuid', 'cwd', 'permission', 'mode', 'proof', 'event', 'duplicate-event'):
            with self.subTest(change=change):
                bad = copy.deepcopy(batch)
                row = bad['targets'][0]
                attestation = row['resumeAttestation']
                if change == 'uuid': attestation['native']['sessionId'] = str(uuid.uuid4())
                elif change == 'cwd': attestation['native']['cwd'] = '/wrong'
                elif change == 'permission': attestation['native']['permissions'] = 'default'
                elif change == 'mode': attestation['native']['resumeMode'] = None
                elif change == 'proof': attestation['nativeProof']['screenSha256'] = 'invalid'
                elif change == 'event': bad['events'] = [e for e in bad['events'] if e['phase'] != 'preparation-mode-attested']
                elif change == 'duplicate-event': bad['events'].append(copy.deepcopy(next(e for e in bad['events'] if e['phase'] == 'preparation-mode-attested')))
                with self.assertRaises(m.Deferred): m.resume_basis(bad, row)

    def test_recover_cli_requires_existing_state_batch_and_no_new_choices(self):
        missing = Path(self.tmp.name)/'missing'
        with patch.object(m.rr, 'Orca', side_effect=AssertionError('runtime must not open')), redirect_stdout(io.StringIO()):
            for args in ([], ['--batch', str(uuid.uuid4())], ['--batch', str(uuid.uuid4()), '--target', 'term_x'], ['--batch', str(uuid.uuid4()), '--exclude', 'term_x']):
                self.assertEqual(2, m.main(['recover-prepare', '--state', str(missing), *args]))
        self.assertFalse(missing.exists())


    def manual_proof(self, session_id='01a1c848-8ff2-7e90-bcec-44a3ca07a21c', pid=123, start=100):
        exe = {'path': str(Path.home() / '.local/share/claude/versions/2.1.331'),
               'device': 1, 'inode': 42, 'uid': os.getuid(), 'mode': stat.S_IFREG | 0o700,
               'size': 100, 'mtimeNs': 1}
        process = {'pid': pid, 'uid': os.getuid(), 'startTicks': start, 'pidNamespace': 'pid:[42]',
                   'executable': exe, 'cwd': '/work', 'paneKey': 'tab:excluded'}
        return {'producerVersion': '2.1.331', 'queryExecutable': exe, 'pid': pid,
                'sessionId': session_id, 'cwd': '/work', 'kind': 'interactive',
                'paneKey': 'tab:excluded', 'process': process}

    def identified_manual_batch(self, *, absent=False, change_runtime=False):
        self.client = Fake('claude')
        self.client.add('excluded', '/work', 'claude')
        ident = self.prepare(excluded=['term_excluded'])
        self.live_proof = self.manual_proof()
        def observe(adapter, cwd, pane, *, expected=None):
            self.assertEqual(('/work', 'tab:excluded'), (cwd, pane))
            if expected is not None and self.live_proof['sessionId'] != expected:
                raise m.Deferred('exception-live-identity-mismatch')
            return copy.deepcopy(self.live_proof)
        self.live_observe = patch.object(m.live, 'observe', side_effect=observe)
        self.live_observe.start(); self.addCleanup(self.live_observe.stop)
        def recheck(adapter, proof):
            if proof != self.live_proof:
                raise m.Deferred('exception-live-proof-changed')
        self.live_recheck = patch.object(m.live, 'recheck', side_effect=recheck)
        self.live_recheck.start(); self.addCleanup(self.live_recheck.stop)
        with m.Store(self.root) as store:
            original = copy.deepcopy(store.load(ident))
            m.identify_exception(self.client, store, ident, 'term_excluded', self.self_pane)
        after = self.load(ident)
        for before, row in zip(original['targets'], after['targets']):
            self.assertEqual(before, {k: v for k, v in row.items() if k != 'exceptionAttestation'})
        self.assertEqual(original['events'], after['events'][:-1])
        real_observe = self.client.observe
        def selected_only(handle):
            self.assertNotEqual('term_excluded', handle, 'manual pane must never be observed')
            return real_observe(handle)
        guard = patch.object(self.client, 'observe', side_effect=selected_only)
        guard.start(); self.addCleanup(guard.stop)
        if change_runtime:
            self.client.replace_handle()
        if absent:
            self.client.remove('term_replacement' if change_runtime else 'term_target')
        self.client.sent.clear()
        return ident

    def test_known_manual_same_workspace_live_selected_after_runtime_and_pid_change(self):
        ident = self.identified_manual_batch(change_runtime=True)
        old = copy.deepcopy(self.load(ident)['targets'][1]['exceptionAttestation'])
        self.live_proof.update(pid=456)
        self.live_proof['process'].update(pid=456, startTicks=200, pidNamespace='pid:[99]')
        result = self.execute(ident, 'verify')
        self.assertEqual('already-running', result['targets'][0]['state'])
        self.assertEqual(old, self.load(ident)['targets'][1]['exceptionAttestation'])
        self.assertTrue(self.client.sent)
        self.assertTrue(all(a[a.index('--terminal')+1] == 'term_replacement' for a in self.client.sent))
        self.assertEqual([], self.client.created)

    def test_known_manual_absent_selected_restores_exact_uuid_once(self):
        ident = self.identified_manual_batch(absent=True, change_runtime=True)
        old = copy.deepcopy(self.load(ident)['targets'][1])
        result = self.execute(ident, 'restore')
        self.assertEqual('restarted', result['targets'][0]['state'], result)
        self.assertEqual(1, len(self.client.created))
        self.assertIn('--resume ' + SESSION, self.client.created[0][-1])
        self.assertEqual(old, self.load(ident)['targets'][1])
        result = self.execute(ident, 'restore')
        self.assertEqual('already-running', result['targets'][0]['state'], result)
        self.assertEqual(1, len(self.client.created))
        self.assertTrue(all(a[a.index('--terminal')+1] == 'term_restored' for a in self.client.sent))

    def test_known_manual_does_not_cover_ps_only_agent(self):
        ident = self.identified_manual_batch(absent=True, change_runtime=True)
        inventory = self.client.inventory
        def orphan():
            ts, ps = inventory()
            next(w for w in ps['worktrees'] if w['worktreeId'] == 'repo::/work')['agents'].append(
                {'paneKey': 'tab:unknown', 'agentType': 'claude'})
            return ts, ps
        with patch.object(self.client, 'inventory', side_effect=orphan):
            result = self.execute(ident, 'restore')
        self.assertEqual('unmatched-agent-identity', result['targets'][0]['reason'])
        self.assertEqual([], self.client.created)
        self.assertEqual([], self.client.sent)

    def test_identify_exception_rejects_wrong_target_and_existing_attestation_before_native(self):
        ident = self.identified_manual_batch()
        with m.Store(self.root) as store, patch.object(m.live, 'observe', side_effect=AssertionError('no native query')):
            for target in ('term_target', 'term_self', 'term_unknown'):
                with self.subTest(target=target), self.assertRaisesRegex(m.Deferred, 'exception-target-invalid'):
                    m.identify_exception(self.client, store, ident, target, self.self_pane)
            with self.assertRaisesRegex(m.Deferred, 'exception-already-identified'):
                m.identify_exception(self.client, store, ident, 'term_excluded', self.self_pane)
        self.assertEqual([], self.client.sent)

    def test_identify_missing_store_invalid_record_and_missing_target_never_lookup_native(self):
        for mode in ('missing', 'invalid', 'target'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)/'state'
                ident = str(uuid.uuid4())
                if mode != 'missing':
                    with m.Store(root) as store:
                        if mode == 'invalid':
                            bad = root/(ident+'.json'); bad.write_text('{}'); bad.chmod(0o600)
                        else:
                            ident = m.prepare(self.client, store, ['term_target'], [], self.self_pane)['batchId']
                with patch.object(m.rr, 'Orca', side_effect=AssertionError('no runtime')), \
                     patch.object(m.live, 'observe', side_effect=AssertionError('no native')), redirect_stdout(io.StringIO()):
                    self.assertEqual(2, m.main(['identify-exception', '--state', str(root), '--batch', ident,
                                              '--target', 'term_missing']))
                if mode == 'missing': self.assertFalse(root.exists())

    def test_attestation_binding_event_collisions_and_partial_storage_fail_closed(self):
        ident = self.identified_manual_batch()
        original = self.load(ident)
        for case in ('event', 'operation', 'terminal', 'binding', 'uuid-collision', 'producer', 'process'):
            with self.subTest(case=case):
                batch = copy.deepcopy(original)
                row = batch['targets'][1]
                value = row['exceptionAttestation']
                if case == 'event': batch['events'].pop()
                elif case == 'operation': value['operationId'] = str(uuid.uuid4())
                elif case == 'terminal': value['terminal'] = {**value['terminal'], 'leafId': 'other'}
                elif case == 'binding': value['binding'] = {'machine': 'other', 'profile': 'other'}
                elif case == 'uuid-collision': value['identity']['sessionId'] = SESSION
                elif case == 'producer': value['identity']['producerVersion'] = '2.1.329'
                else: value['identity']['process']['startTicks'] = 0
                with self.assertRaises(m.Deferred): m.validate_batch(batch)
        with m.Store(self.root) as store:
            body = store.load(ident)
            body['targets'][1].pop('exceptionAttestation')
            body['events'] = body['events'][:-1]
            store.save(body)
            with patch.object(store, 'save', side_effect=OSError('owned storage failure')), self.assertRaises(OSError):
                m.identify_exception(self.client, store, ident, 'term_excluded', self.self_pane)
            self.assertEqual(body['events'], store.load(ident)['events'])
            self.assertNotIn('exceptionAttestation', store.load(ident)['targets'][1])
        self.assertEqual([], self.client.sent)
        self.assertEqual([], self.client.created)

    def test_attested_manual_mismatch_pane_duplicate_and_unsupported_producer_stop_before_selected_input(self):
        ident = self.identified_manual_batch(change_runtime=True)
        base = copy.deepcopy(self.live_proof)
        for case in ('uuid', 'pane', 'process', 'producer', 'duplicate'):
            with self.subTest(case=case):
                self.live_proof = copy.deepcopy(base)
                if case == 'uuid': self.live_proof['sessionId'] = str(uuid.uuid4())
                elif case == 'pane': self.client.terms['term_excluded']['leafId'] = 'other'
                elif case == 'process': self.live_proof['process']['cwd'] = '/elsewhere'
                elif case == 'producer': self.live_proof['producerVersion'] = '2.1.329'
                else:
                    self.client.add('duplicate', '/work', 'claude')
                    self.client.terms['term_duplicate']['leafId'] = 'excluded'
                if case in ('process', 'producer'):
                    # The real helper refuses these observations, before returning a proof.
                    with patch.object(m.live, 'observe', side_effect=m.Deferred('exception-process-unverifiable')):
                        result = self.execute(ident, 'verify')
                else:
                    result = self.execute(ident, 'verify')
                self.assertIn(result['targets'][0]['state'], ('deferred', 'failed'))
                self.assertEqual([], self.client.sent)
                self.assertEqual([], self.client.created)
                self.client.terms['term_excluded']['leafId'] = 'excluded'
                self.client.remove('term_duplicate')

    def test_exception_proof_is_frozen_over_inventory_wait_and_final_create_receipt(self):
        for boundary in ('inventory', 'durable-sending', 'durable-uuid', 'selected-status'):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                ident = self.identified_manual_batch(absent=boundary != 'selected-status', change_runtime=True)
                changed = []
                def drift():
                    if boundary == 'durable-uuid':
                        self.live_proof['sessionId'] = str(uuid.uuid4())
                    else:
                        self.live_proof['process']['startTicks'] += 1
                    changed.append(True)
                inventory = m.rr.plugin_inventory
                record = m.Recorder.record
                call = self.client.call
                def slow(*args):
                    value = inventory(*args)
                    if getattr(self.client, 'exception_proofs', {}) and boundary == 'inventory' and not changed:
                        drift()
                    return value
                def sending(recorder, phase, **values):
                    value = record(recorder, phase, **values)
                    if boundary in ('durable-sending', 'durable-uuid') and values.get('step') == 'owned-restore-terminal': drift()
                    return value
                def status(*args):
                    value = call(*args)
                    if boundary == 'selected-status' and args[:2] == ('terminal', 'wait') and not changed:
                        drift()
                    return value
                with patch.object(m.rr, 'plugin_inventory', side_effect=slow), \
                     patch.object(m.Recorder, 'record', new=sending), patch.object(self.client, 'call', side_effect=status):
                    result = self.execute(ident, 'verify' if boundary == 'selected-status' else 'restore')
                self.assertEqual([True], changed)
                self.assertEqual('exception-live-identity-mismatch' if boundary == 'durable-uuid' else
                                 'exception-live-proof-changed', result['targets'][0]['reason'])
                self.assertEqual([], self.client.created)
                self.assertEqual([], self.client.sent)
                if boundary in ('durable-sending', 'durable-uuid'):
                    self.assertTrue(any(e.get('step') == 'owned-restore-terminal' and e['phase'] == 'sending'
                                        for e in self.load(ident)['events']))


    def cold_manual_batch(self):
        ident = self.identified_manual_batch(absent=True, change_runtime=True)
        self.client.remove('term_excluded')
        self.cold_state = 'absent'
        self.absent_proof = {k: copy.deepcopy(self.live_proof[k]) for k in
                             ('producerVersion', 'queryExecutable', 'sessionId', 'cwd', 'paneKey')}
        self.absent_proof['kind'] = 'absent'
        def observe_absent(adapter, cwd, pane, *, expected):
            self.assertEqual(('/work', 'tab:excluded', self.live_proof['sessionId']), (cwd, pane, expected))
            if self.cold_state != 'absent':
                raise m.Deferred(self.cold_state)
            return copy.deepcopy(self.absent_proof)
        lookup = patch.object(m.live, 'observe_absent', side_effect=observe_absent)
        lookup.start(); self.addCleanup(lookup.stop)
        original_recheck = m.live.recheck
        def recheck(adapter, proof):
            if proof['kind'] == 'absent':
                self.assertEqual(self.absent_proof, proof)
                return
            return original_recheck(adapter, proof)
        check = patch.object(m.live, 'recheck', side_effect=recheck)
        check.start(); self.addCleanup(check.stop)
        return ident

    def test_cold_both_absent_restores_selected_exactly_once_and_preserves_manual_history(self):
        ident = self.cold_manual_batch()
        before = copy.deepcopy(self.load(ident))
        result = self.execute(ident, 'restore')
        self.assertEqual('restarted', result['targets'][0]['state'], result)
        self.assertEqual(1, len(self.client.created))
        self.assertIn('--resume '+SESSION, self.client.created[0][-1])
        after = self.load(ident)
        self.assertEqual(before['targets'][1], after['targets'][1])
        self.assertEqual(before['events'], after['events'][:len(before['events'])])
        self.assertEqual('absent', self.client.exception_proofs['term_excluded']['live']['kind'])
        self.assertEqual('already-running', self.execute(ident, 'restore')['targets'][0]['state'])
        self.assertEqual(1, len(self.client.created))
        self.assertTrue(all(a[a.index('--terminal')+1] == 'term_restored' for a in self.client.sent))

    def test_cold_original_manual_pane_nonagent_unknown_or_reused_identity_never_falls_back_to_absence(self):
        for provider in (None, 'unknown', 'claude'):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                ident = self.cold_manual_batch()
                self.client.add('excluded', '/work', provider)
                self.live_proof['sessionId'] = str(uuid.uuid4())
                # A live wrong UUID on the original pane is rejected by the official helper.
                with patch.object(m.live, 'observe', side_effect=m.Deferred('exception-live-identity-mismatch')), \
                     patch.object(m.live, 'observe_absent', side_effect=AssertionError('no absence fallback')):
                    result = self.execute(ident, 'restore')
                self.assertIn(result['targets'][0]['state'], ('failed', 'deferred'))
                self.assertEqual([], self.client.sent)
                self.assertEqual([], self.client.created)

    def test_cold_missing_truncated_ps_only_associated_child_and_workspace_views_refuse(self):
        for kind in ('truncated-terms', 'truncated-ps', 'missing-scope', 'missing-workspace', 'wrong-path',
                     'missing-agents', 'manual-agent', 'ps-only', 'parent', 'children', 'subagents'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                ident = self.cold_manual_batch()
                inventory = self.client.inventory
                def broken():
                    ts, ps = inventory()
                    workspace = next(w for w in ps['worktrees'] if w['worktreeId'] == 'repo::/work')
                    if kind == 'truncated-terms': ts['truncated'] = True
                    elif kind == 'truncated-ps': ps['truncated'] = True
                    elif kind == 'missing-scope': ts['hostScope']['hostIds'] = []
                    elif kind == 'missing-workspace': ps['worktrees'].remove(workspace)
                    elif kind == 'wrong-path': workspace['path'] = '/other'
                    elif kind == 'missing-agents': workspace.pop('agents')
                    else:
                        agent = {'paneKey': 'tab:unknown', 'agentType': 'claude'}
                        if kind == 'manual-agent': agent['paneKey'] = 'tab:excluded'
                        elif kind == 'parent': agent['parentPaneKey'] = 'tab:excluded'
                        elif kind == 'children': agent['children'] = [{'paneKey': 'tab:excluded'}]
                        elif kind == 'subagents': agent['subagents'] = ['tab:excluded']
                        workspace['agents'].append(agent)
                    return ts, ps
                try:
                    with patch.object(self.client, 'inventory', side_effect=broken):
                        result = self.execute(ident, 'restore')
                except m.Deferred:
                    pass  # Top-level complete inventory checks stop before row execution.
                else:
                    self.assertIn(result['targets'][0]['state'], ('deferred', 'failed'), result)
                self.assertEqual([], self.client.sent)
                self.assertEqual([], self.client.created)

    def test_cold_native_alive_elsewhere_unreadable_or_reused_pane_never_proves_absence(self):
        ident = self.cold_manual_batch()
        for failure in ('exception-expected-session-still-live', 'exception-process-unverifiable',
                        'exception-absent-pane-reused', 'exception-native-json-invalid',
                        'native-cli-unavailable-or-timeout', 'exception-live-identity-ambiguous'):
            with self.subTest(failure=failure):
                self.cold_state = failure
                result = self.execute(ident, 'restore')
                self.assertEqual(failure, result['targets'][0]['reason'])
                self.assertEqual([], self.client.sent)
                self.assertEqual([], self.client.created)

    def test_cold_absence_is_fixed_over_inventory_durable_and_final_official_lookup(self):
        for boundary in ('inventory', 'durable', 'final-native-query', 'final-orca'):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)/'state'
                ident = self.cold_manual_batch()
                changed = []
                real_inventory = m.rr.plugin_inventory
                real_record = m.Recorder.record
                real_absent = m.live.observe_absent
                sending = []
                def change():
                    self.cold_state = 'exception-expected-session-still-live'
                    changed.append(True)
                def inventory(*args):
                    value = real_inventory(*args)
                    if boundary == 'inventory' and self.client.exception_proofs and not changed: change()
                    return value
                def record(recorder, phase, **values):
                    value = real_record(recorder, phase, **values)
                    if phase == 'sending' and values.get('step') == 'owned-restore-terminal':
                        sending.append(True)
                    if boundary == 'durable' and values.get('step') == 'owned-restore-terminal': change()
                    return value
                def native(*args, **kwargs):
                    value = real_absent(*args, **kwargs)
                    if sending and boundary == 'final-native-query' and not changed:
                        # The second official response detects this in the real helper.
                        change()
                        raise m.Deferred(self.cold_state)
                    if sending and boundary == 'final-orca' and not changed:
                        changed.append(True)
                        self.client.add('excluded', '/work', None)
                    return value
                with patch.object(m.rr, 'plugin_inventory', side_effect=inventory), \
                     patch.object(m.Recorder, 'record', new=record), patch.object(m.live, 'observe_absent', side_effect=native):
                    result = self.execute(ident, 'restore')
                self.assertEqual([True], changed)
                self.assertIn(result['targets'][0]['reason'],
                              ('exception-expected-session-still-live', 'exception-pane-mismatch',
                               'exception-absence-unverified', 'restore-safety-state-changed'))
                self.assertEqual([], self.client.sent)
                self.assertEqual([], self.client.created)

    def test_exception_native_lookup_cannot_hide_new_selected_or_ps_candidate_before_create(self):
        ident = self.cold_manual_batch()
        real_absent = m.live.observe_absent
        changed, sending = [], []
        real_record = m.Recorder.record
        def record(recorder, phase, **values):
            value = real_record(recorder, phase, **values)
            if phase == 'sending' and values.get('step') == 'owned-restore-terminal': sending.append(True)
            return value
        def appeared(*args, **kwargs):
            value = real_absent(*args, **kwargs)
            if sending and not changed:
                changed.append(True)
                self.client.add('unexpected', '/work', 'claude')
            return value
        with patch.object(m.live, 'observe_absent', side_effect=appeared), patch.object(m.Recorder, 'record', new=record):
            result = self.execute(ident, 'restore')
        self.assertEqual('restore-safety-state-changed', result['targets'][0]['reason'])
        self.assertEqual([], self.client.sent)
        self.assertEqual([], self.client.created)


class Claude332Fake(ModalFake):
    def __init__(self):
        super().__init__()
        self.claude_version = self.installed_claude_version = '2.1.332'
        self.resumed = False
        self.account = 'owned@example.test'
        self.bad_marker = False
        self.exit_marker_bypass = False

    def call(self, *args):
        if args[:2] == ('terminal', 'send'):
            command = args[args.index('--text')+1]
            handle = args[args.index('--terminal')+1]
            if ' --proof ' in command:
                self.sent.append(args)
                self.resumed = True
                self.claude_version = self.installed_claude_version
                self.frames[handle].update(tail=['❯', '  ⏵⏵ bypass permissions on (shift+tab to cycle)'],
                                          latestCursor=str(int(self.frames[handle]['latestCursor'])+1))
                return {'send': {'accepted': True}, 'mutation': {'requestId': str(uuid.uuid4())}}
            result = super().call(*args)
            if command == '/status':
                lines = self.frames[handle]['tail']
                lines[1] = ' Version: ' + self.claude_version
                if self.claude_version == '2.1.319':
                    lines[:] = [line.replace('←/→ to switch · Esc to close', 'Esc to cancel') for line in lines]
                lines[-1:-1] = [' Login method: Claude Account', ' Organization: Owned fixture',
                                ' Email: '+self.account]
            elif command == '/exit':
                flag = '--dangerously-skip-permissions ' if self.exit_marker_bypass else ''
                marker = ['Resume this session with:', 'claude ' + flag + '--resume '+self.identities[handle]['sessionId']]
                self.frames[handle]['delta'] = ['stale marker'] if self.bad_marker else marker
            return result
        return super().call(*args)


class Claude332Restart(unittest.TestCase):
    prepare = Restart.prepare
    execute = Restart.execute
    load = Restart.load
    texts = Restart.texts

    def setUp(self):
        Restart.setUp(self)
        self.client = Claude332Fake()
        self.clock = 0.0
        def sleep(seconds):
            self.clock += seconds
        patch.object(m.time, 'monotonic', side_effect=lambda: self.clock).start()
        patch.object(m.time, 'sleep', side_effect=sleep).start()
        self.shell = {'shell': {'pid': 42, 'starttime': 10, 'uid': os.getuid(),
                               'sid': 42, 'pgrp': 42, 'tty': 5},
                      'executable': {'path': '/usr/bin/zsh'}, 'cwd': '/work', 'pane': 'tab:target'}
        self.launch = {'environment': {'environmentSha256': 'a'*64, 'profileSha256': 'b'*64},
                       'shell': self.shell['shell'], 'shellExecutable': self.shell['executable'],
                       'argumentClass': 'fixed-bypass'}
        self.native = {'sessionId': SESSION, 'cwd': '/work', 'paneKey': 'tab:target',
                       'producerVersion': '2.1.332', 'queryExecutable': {
                           'path': str(Path.home() / '.local/share/claude/versions/2.1.332')},
                       'kind': 'interactive', 'process': {'startTicks': 100, 'pidNamespace': 'pid:[42]',
                           'executable': {'path': str(Path.home() / '.local/share/claude/versions/2.1.332')}}}
        def observe(*args, **kwargs):
            return {**copy.deepcopy(self.native), 'pid': 200 if self.client.resumed else 100,
                    'process': {**self.native['process'], 'startTicks': 200 if self.client.resumed else 100,
                                'executable': {'path': str(Path.home() / '.local/share/claude/versions' / self.client.claude_version)}}}
        self.intent_patch = patch.object(m.live.checked, 'write_proof', return_value={'path': '/tmp/owned.proof', 'sha256': 'd'*64}).start()
        self.inspect_patch = patch.object(m.live.checked, 'inspect_proof').start()
        self.observe_patch = patch.object(m.live, 'observe', side_effect=observe).start()
        self.launch_patch = patch.object(m.live, 'selected_launch', side_effect=lambda *args: copy.deepcopy(self.launch)).start()
        self.exited_patch = patch.object(m.live, 'exited').start()
        self.shell_patch = patch.object(m.rr, 'target_shell_process_proof', return_value=self.shell).start()
        self.addCleanup(patch.stopall)

    def settling_target(self):
        ident = self.prepare()
        before = self.load(ident)['targets'][0]['native']
        _, ps = self.client.inventory()
        target = m.target_from(self.client, self.client.terms['term_target'], ps, self.self_pane)
        self.observe_patch.reset_mock()
        self.client.sent.clear()
        return target, before, m.current_plan(self.client, self.self_pane)

    def test_ui_settles_exact_transient_hint_layout_and_cursor_before_native_proof(self):
        target, before, plan = self.settling_target()
        original_guard = m.rr.guard
        observed = self.observe_patch.side_effect
        frames = []
        def guard(*args, **kwargs):
            frame = self.client.frames['term_target']
            if self.clock < 0.5:
                frame['tail'] = ['◐ medium · /effort ·', '❯',
                                 '  ⏵⏵ bypass permissions on (shift+tab to cycle)']
            elif self.clock < 1.0:
                frame['tail'][0] = '                       '
            else:
                frame['tail'][0] = '   settled layout'
                frame['latestCursor'] = '13'
            result = original_guard(*args, **kwargs)
            frames.append((self.clock, copy.deepcopy(result[1])))
            self.assertEqual(0, self.observe_patch.call_count)
            return result
        def observe(*args, **kwargs):
            self.assertGreaterEqual(self.clock, 3.0)
            stable = [(at, frame) for at, frame in frames if at >= 1.0]
            self.assertGreaterEqual(len(stable), 3)
            self.assertGreaterEqual(stable[-1][0] - stable[0][0], 2.0)
            self.assertTrue(all(frame == stable[0][1] for _, frame in stable))
            return observed(*args, **kwargs)
        self.observe_patch.side_effect = observe
        with patch.object(m.rr, 'guard', side_effect=guard):
            m.claude_restart_proof(self.client, target, before, plan, self.self_pane)
        self.assertEqual(1, self.observe_patch.call_count)
        self.assertEqual([], self.texts())

    def test_ui_stable_versions_need_two_seconds_and_three_full_observations(self):
        original_guard = m.rr.guard
        for version in ('2.1.319', '2.1.329', '2.1.332'):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory) / 'state'
                self.client = Claude332Fake()
                self.client.claude_version = version
                self.clock = 0.0
                target, before, plan = self.settling_target()
                with patch.object(m.rr, 'guard', wraps=original_guard) as guarded:
                    m.claude_restart_proof(self.client, target, before, plan, self.self_pane)
                self.assertGreaterEqual(guarded.call_count, 3)
                self.assertGreaterEqual(self.clock, 2.0)
                self.assertEqual(1, self.observe_patch.call_count)
                self.assertEqual([], self.texts())

    def test_ui_persistent_screen_or_cursor_changes_stop_bounded_without_proof_or_exit(self):
        target, before, plan = self.settling_target()
        original_guard = m.rr.guard
        for change in ('screen', 'cursor'):
            with self.subTest(change=change):
                self.clock = 0.0
                self.observe_patch.reset_mock()
                def guard(*args, **kwargs):
                    frame = self.client.frames['term_target']
                    if change == 'screen': frame['tail'] = [str(self.clock), '❯',
                        '  ⏵⏵ bypass permissions on (shift+tab to cycle)']
                    else: frame['latestCursor'] = str(int(self.clock * 10))
                    return original_guard(*args, **kwargs)
                with patch.object(m.rr, 'guard', side_effect=guard) as guarded:
                    with self.assertRaisesRegex(m.Deferred, 'claude-ui-settling-timeout'):
                        m.claude_restart_proof(self.client, target, before, plan, self.self_pane)
                self.assertEqual(15.0, self.clock)
                self.assertLessEqual(guarded.call_count, 30)
                self.assertEqual(0, self.observe_patch.call_count)
                self.assertEqual([], self.texts())

    def test_ui_unsafe_full_guard_or_mode_failure_is_immediate_without_retry(self):
        target, before, plan = self.settling_target()
        original_guard = m.rr.guard
        for failure in ('target-changed', 'draft', 'busy', 'approval', 'children', 'mode'):
            with self.subTest(failure=failure):
                self.clock = 0.0
                self.observe_patch.reset_mock()
                def guard(*args, **kwargs):
                    if failure != 'mode': raise m.Deferred(failure)
                    result = original_guard(*args, **kwargs)
                    result[1]['tail'][-1] = '⏵⏵ auto mode on (shift+tab to cycle)'
                    return result
                with patch.object(m.rr, 'guard', side_effect=guard) as guarded:
                    with self.assertRaises(m.Deferred):
                        m.claude_restart_proof(self.client, target, before, plan, self.self_pane)
                self.assertEqual(1, guarded.call_count)
                self.assertEqual(0.0, self.clock)
                self.assertEqual(0, self.observe_patch.call_count)
                self.assertEqual([], self.texts())

    def test_332_restart_and_repeat_verify_have_one_exit_resume_and_new_process(self):
        for bypass_marker in (False, True):
            with self.subTest(bypass_marker=bypass_marker), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory) / 'state'
                self.client = Claude332Fake()
                self.client.exit_marker_bypass = bypass_marker
                ident = self.prepare()
                self.client.sent.clear()
                row = self.execute(ident)['targets'][0]
                self.assertEqual('restarted', row['state'], row)
                command = m.live.checked.command({'path': '/tmp/owned.proof', 'sha256': 'd'*64})
                self.assertEqual(['/status', '\x1b', '/exit', command, '/status', '\x1b'], self.texts())
                stored = self.load(ident)['targets'][0]
                self.assertEqual(100, stored['restartProof']['native']['pid'])
                self.assertEqual(200, stored['processObserved']['pid'])
                self.assertNotIn('owned@example.test', json.dumps(stored))
                self.client.sent.clear()
                for unused in range(2):
                    self.assertEqual('already-running', self.execute(ident, 'verify')['targets'][0]['state'])
                self.assertEqual(['/status', '\x1b', '/status', '\x1b'], self.texts())

    def test_observed_319_329_sources_restart_to_installed_332_with_same_account(self):
        for version in ('2.1.319', '2.1.329'):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory) / 'state'
                self.client = Claude332Fake()
                self.client.claude_version = version
                ident = self.prepare()
                self.client.sent.clear()
                self.assertEqual(version, self.load(ident)['targets'][0]['native']['nativeVersion'])
                row = self.execute(ident)['targets'][0]
                self.assertEqual('restarted', row['state'], row)
                stored = self.load(ident)['targets'][0]
                self.assertEqual(version, Path(stored['restartProof']['native']['process']['executable']['path']).name)
                self.assertEqual('2.1.332', stored['nativeObserved']['nativeVersion'])
                self.assertEqual(stored['native']['accountProof'], stored['nativeObserved']['accountProof'])
                self.assertEqual(1, self.texts().count('/exit'))
                self.assertEqual(1, sum(' --proof ' in text for text in self.texts()))
                self.client.sent.clear()
                self.assertEqual('already-running', self.execute(ident, 'verify')['targets'][0]['state'])
                self.assertEqual(['/status', '\x1b'], self.texts())

    def test_resumed_legacy_or_changed_query_executable_never_gets_status(self):
        observed = self.observe_patch.side_effect
        for change in ('2.1.319', '2.1.329', 'query'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory) / 'state'
                self.client = Claude332Fake()
                self.client.claude_version = '2.1.319'
                ident = self.prepare()
                self.client.sent.clear()
                def replaced(*args, **kwargs):
                    proof = observed(*args, **kwargs)
                    if self.client.resumed:
                        path = str(Path.home() / '.local/share/claude/versions' /
                                   ('2.1.329' if change == 'query' else change))
                        if change == 'query': proof['queryExecutable']['path'] = path
                        else: proof['process']['executable']['path'] = path
                    return proof
                self.observe_patch.side_effect = replaced
                row = self.execute(ident)['targets'][0]
                self.assertEqual('claude-resumed-launch-mismatch', row['reason'])
                self.assertEqual(1, self.texts().count('/status'))
                self.assertEqual(1, self.texts().count('/exit'))
                self.assertEqual(1, sum(' --proof ' in text for text in self.texts()))
                sent = list(self.texts())
                attempt = copy.deepcopy(self.load(ident)['targets'][0]['attempt'])
                self.assertEqual('uncertain', attempt['state'])
                self.execute(ident)
                self.assertEqual(sent, self.texts())
                self.assertEqual(attempt, self.load(ident)['targets'][0]['attempt'])
                self.observe_patch.side_effect = observed

    def test_legacy_source_status_executable_mismatch_never_exits(self):
        self.client.claude_version = '2.1.319'
        ident = self.prepare()
        self.client.sent.clear()
        observed = self.observe_patch.side_effect
        def mismatch(*args, **kwargs):
            proof = observed(*args, **kwargs)
            proof['process']['executable']['path'] = str(Path.home() / '.local/share/claude/versions/2.1.329')
            return proof
        self.observe_patch.side_effect = mismatch
        row = self.execute(ident)['targets'][0]
        self.assertEqual('claude-restart-source-version-mismatch', row['reason'])
        self.assertEqual(['/status', '\x1b'], self.texts())

    def test_legacy_restart_without_account_proof_stays_manual(self):
        self.client.claude_version = '2.1.319'
        original = self.client.call
        def call(*args):
            result = original(*args)
            if args[:2] == ('terminal', 'send') and args[args.index('--text') + 1] == '/status':
                frame = self.client.frames['term_target']
                frame['tail'] = [line for line in frame['tail']
                                 if not any(label in line for label in ('Login method:', 'Organization:', 'Email:'))]
            return result
        with patch.object(self.client, 'call', side_effect=call):
            ident = self.prepare()
            self.client.sent.clear()
            row = self.execute(ident)['targets'][0]
        self.assertEqual('claude-account-unverified', row['reason'])
        self.assertNotIn('/exit', self.texts())

    def test_332_unverified_launch_or_source_has_no_exit(self):
        for failure in ('claude-launch-options-unverified', 'claude-launch-environment-mismatch',
                        'claude-restart-source-version-mismatch'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory)/'state'
                self.client = Claude332Fake()
                ident = self.prepare()
                self.client.sent.clear()
                self.launch_patch.side_effect = m.Deferred(failure)
                row = self.execute(ident)['targets'][0]
                self.assertEqual('manual-restart-required', row['state'])
                self.assertEqual(failure, row['reason'])
                self.assertEqual(['/status', '\x1b'], self.texts())

    def test_332_changed_account_never_exits(self):
        ident = self.prepare()
        self.client.sent.clear()
        self.client.account = 'different@example.test'
        row = self.execute(ident)['targets'][0]
        self.assertEqual('claude-account-mismatch', row['reason'])
        self.assertEqual(['/status', '\x1b'], self.texts())

    def test_332_drift_after_durable_exit_intent_stops_before_transport(self):
        ident = self.prepare()
        self.client.sent.clear()
        original = m.Recorder.record
        def record(recorder, phase, **values):
            result = original(recorder, phase, **values)
            if phase == 'sending' and values.get('step') == 'normal-exit':
                self.launch['environment']['environmentSha256'] = 'c'*64
            return result
        with patch.object(m.Recorder, 'record', new=record):
            row = self.execute(ident)['targets'][0]
        self.assertEqual('claude-launch-proof-changed', row['reason'])
        self.assertEqual(['/status', '\x1b'], self.texts())
        self.execute(ident)
        self.assertEqual(['/status', '\x1b'], self.texts())

    def test_332_final_mode_is_checked_before_and_after_durable_exit_intent(self):
        for phase in ('claude-restart-preflight', 'sending'):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory) / 'state'
                self.client = Claude332Fake()
                ident = self.prepare()
                self.client.sent.clear()
                original = m.Recorder.record
                def record(recorder, current, **values):
                    result = original(recorder, current, **values)
                    if current == phase and (phase != 'sending' or values.get('step') == 'normal-exit'):
                        self.client.frames['term_target']['tail'][-1] = '  ⏵⏵ auto mode on (shift+tab to cycle)'
                    return result
                with patch.object(m.Recorder, 'record', new=record):
                    row = self.execute(ident)['targets'][0]
                self.assertEqual('claude-permissions-unknown', row['reason'])
                self.assertEqual(['/status', '\x1b'], self.texts())
                stored = self.load(ident)
                exit_sending = [e for e in stored['events'] if e['phase'] == 'sending'
                                and e.get('step') == 'normal-exit']
                self.assertEqual(1 if phase == 'sending' else 0, len(exit_sending))
                self.execute(ident)
                self.assertNotIn('/exit', self.texts())

    def test_332_exit_cursor_uuid_and_fresh_proof_are_durable_before_exit(self):
        ident = self.prepare()
        original = self.client.call
        checked = []
        def call(*args):
            if args[:2] == ('terminal', 'send') and args[args.index('--text') + 1] == '/exit':
                stored = json.loads((self.root / (ident + '.json')).read_text())['batch']
                planned = [e for e in stored['events'] if e['phase'] == 'native-exit-planned']
                self.assertEqual(1, len(planned))
                evidence = planned[0]
                self.assertEqual(SESSION, evidence['sessionId'])
                self.assertEqual('2.1.332', evidence['nativeVersion'])
                self.assertEqual(self.client.frames['term_target']['latestCursor'], evidence['cursor'])
                self.assertEqual(64, len(evidence['frameSha256']))
                self.assertIn('nativeProof', evidence)
                checked.append(True)
            return original(*args)
        with patch.object(self.client, 'call', side_effect=call):
            self.assertEqual('restarted', self.execute(ident)['targets'][0]['state'])
        self.assertEqual([True], checked)

    def test_332_durable_exit_cursor_or_checked_intent_drift_never_exits(self):
        for failure in ('cursor', 'intent'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory) / 'state'
                self.client = Claude332Fake()
                ident = self.prepare()
                self.client.sent.clear()
                self.inspect_patch.side_effect = None
                original = m.Recorder.record
                def record(recorder, phase, **values):
                    result = original(recorder, phase, **values)
                    if phase == 'sending' and values.get('step') == 'normal-exit':
                        if failure == 'cursor': self.client.frames['term_target']['latestCursor'] = '99999'
                        else: self.inspect_patch.side_effect = m.live.checked.Refused()
                    return result
                with patch.object(m.Recorder, 'record', new=record):
                    row = self.execute(ident)['targets'][0]
                expected = 'native-exit-proof-changed' if failure == 'cursor' else 'claude-checked-resume-proof-changed'
                self.assertEqual(expected, row['reason'])
                self.assertEqual(['/status', '\x1b'], self.texts())
                self.execute(ident)
                self.assertEqual(['/status', '\x1b'], self.texts())

    def test_332_same_process_or_changed_resumed_process_is_not_restart_proof(self):
        ident = self.prepare()
        self.client.sent.clear()
        real_observe = self.observe_patch.side_effect
        def original_process(*args, **kwargs):
            proof = real_observe(*args, **kwargs)
            if self.client.resumed:
                proof['pid'] = 100
            return proof
        self.observe_patch.side_effect = original_process
        row = self.execute(ident)['targets'][0]
        self.assertEqual('claude-new-process-unproven', row['reason'])
        self.assertEqual(1, self.texts().count('/exit'))
        self.assertEqual(1, sum(' --proof ' in text for text in self.texts()))

    def test_332_post_resume_status_requires_fresh_exact_new_process_launch_proof(self):
        ident = self.prepare()
        self.client.sent.clear()
        original = self.client.call
        launched = self.launch_patch.side_effect
        proven = []
        def selected_launch(adapter, proof):
            result = launched(adapter, proof)
            if self.client.resumed:
                self.assertEqual(SESSION, proof['sessionId'])
                self.assertEqual(200, proof['pid'])
                self.assertEqual(200, proof['process']['startTicks'])
                proven.append(copy.deepcopy(proof))
            return result
        def call(*args):
            if (self.client.resumed and args[:2] == ('terminal', 'send')
                    and args[args.index('--text') + 1] == '/status'):
                self.assertEqual(1, len(proven))
                self.assertEqual(SESSION, self.observe_patch.call_args.kwargs['expected'])
            return original(*args)
        self.launch_patch.side_effect = selected_launch
        with patch.object(self.client, 'call', side_effect=call):
            self.assertEqual('restarted', self.execute(ident)['targets'][0]['state'])
        self.assertEqual(2, len(proven))  # Before input and after native/account status.

    def test_332_stale_done_shell_or_failed_launcher_never_gets_status_or_resend(self):
        observed = self.observe_patch.side_effect
        for failure in ('stale-done', 'refused', 'crashed'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory) / 'state'
                self.client = Claude332Fake()
                intent = {'path': str(Path(directory) / 'owned.proof'), 'sha256': 'd' * 64}
                self.intent_patch.return_value = intent
                ident = self.prepare()
                self.client.sent.clear()
                original = self.client.call
                def observe(*args, **kwargs):
                    if self.client.resumed:
                        if failure == 'stale-done':
                            proof = copy.deepcopy(self.native)
                            proof['pid'] = 100
                            return proof
                        raise m.Deferred('exception-live-identity-ambiguous')
                    return observed(*args, **kwargs)
                self.observe_patch.side_effect = observe
                def call(*args):
                    result = original(*args)
                    if args[:2] == ('terminal', 'send') and ' --proof ' in args[args.index('--text') + 1]:
                        self.client.frames['term_target']['tail'] = [
                            '  ⏵⏵ bypass permissions on (shift+tab to cycle)',
                            'Resume this session with:', 'claude --resume ' + SESSION, '❯']
                        self.client.agents['term_target']['state'] = 'done'
                        self.client.agents['term_target']['mainAgent']['state'] = 'done'
                        self.client.agents['term_target']['programStatus']['state'] = 'done'
                        if failure == 'refused':
                            receipt = Path(intent['path'] + '.refused')
                            receipt.write_text(intent['sha256'])
                            receipt.chmod(0o400)
                    return result
                with patch.object(self.client, 'call', side_effect=call):
                    row = self.execute(ident)['targets'][0]
                expected = {'stale-done': 'claude-new-process-unproven',
                            'refused': 'claude-checked-resume-stopped-before-native-launch',
                            'crashed': 'exception-live-identity-ambiguous'}[failure]
                self.assertEqual('failed', row['state'], row)
                self.assertEqual(expected, row['reason'])
                command = m.live.checked.command(intent)
                self.assertEqual(['/status', '\x1b', '/exit', command], self.texts())
                stored = self.load(ident)
                attempt = copy.deepcopy(stored['targets'][0]['attempt'])
                self.assertEqual('uncertain', attempt['state'])
                events = copy.deepcopy(stored['events'])
                self.assertTrue(any(e.get('operationId') == attempt['operationId']
                                    and e['phase'] == 'accepted' and e.get('step') == 'exact-resume'
                                    for e in events))
                self.execute(ident)
                self.assertEqual(['/status', '\x1b', '/exit', command], self.texts())
                final = self.load(ident)
                self.assertEqual(attempt, final['targets'][0]['attempt'])
                self.assertEqual(events, final['events'])
                verification = self.execute(ident, 'verify')['targets'][0]
                self.assertEqual('deferred', verification['state'])
                self.assertEqual(['/status', '\x1b', '/exit', command], self.texts())
                verified = self.load(ident)
                self.assertEqual(attempt, verified['targets'][0]['attempt'])
                self.assertEqual(events, verified['events'][:len(events)])
                self.assertTrue(all(e['phase'] == 'stopped' for e in verified['events'][len(events):]))
                self.observe_patch.side_effect = observed

    def test_verify_missing_exit_receipt_or_observation_never_inputs_into_shell(self):
        observed = self.observe_patch.side_effect
        for failure in ('receipt', 'observation'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory) / 'state'
                self.client = Claude332Fake()
                ident = self.prepare()
                self.client.sent.clear()
                exited = [False]
                original = self.client.call
                record = m.Recorder.record
                def call(*args):
                    result = original(*args)
                    if args[:2] == ('terminal', 'send') and args[args.index('--text') + 1] == '/exit':
                        exited[0] = True
                        self.client.frames['term_target']['tail'] = [
                            '  ⏵⏵ bypass permissions on (shift+tab to cycle)',
                            'Resume this session with:', 'claude --resume ' + SESSION, '❯']
                        for key in ('mainAgent', 'programStatus'):
                            self.client.agents['term_target'][key]['state'] = 'done'
                        self.client.agents['term_target']['state'] = 'done'
                        if failure == 'receipt': return {'send': {'accepted': False}}
                    return result
                def recorder(recorder, phase, **values):
                    if failure == 'observation' and phase == 'native-exit-observed':
                        raise m.Deferred('owned-exit-observation-lost')
                    return record(recorder, phase, **values)
                def absent(*args, **kwargs):
                    if exited[0]: raise m.Deferred('exception-live-identity-ambiguous')
                    return observed(*args, **kwargs)
                self.observe_patch.side_effect = absent
                with patch.object(self.client, 'call', side_effect=call), patch.object(m.Recorder, 'record', new=recorder):
                    result = self.execute(ident)['targets'][0]
                self.assertEqual('failed', result['state'])
                stored = self.load(ident)
                attempt = copy.deepcopy(stored['targets'][0]['attempt'])
                self.assertEqual('uncertain', attempt['state'])
                self.assertFalse(any(e['phase'] == 'native-exit-observed' for e in stored['events']))
                sent = list(self.texts())
                self.assertEqual(['/status', '\x1b', '/exit'], sent)
                result = self.execute(ident, 'verify')['targets'][0]
                self.assertEqual('exception-live-identity-ambiguous', result['reason'])
                self.assertEqual(sent, self.texts())
                self.assertEqual(attempt, self.load(ident)['targets'][0]['attempt'])
                self.execute(ident)
                self.assertEqual(sent, self.texts())
                self.observe_patch.side_effect = observed

    def test_verify_proven_original_without_observed_exit_keeps_restart_pending(self):
        self.client.claude_version = '2.1.319'
        ident = self.prepare()
        self.client.sent.clear()
        original = m.Recorder.record
        def record(recorder, phase, **values):
            if phase == 'native-exit-planned': raise m.Deferred('owned-stopped-before-exit')
            return original(recorder, phase, **values)
        with patch.object(m.Recorder, 'record', new=record):
            self.assertEqual('failed', self.execute(ident)['targets'][0]['state'])
        stored = self.load(ident)
        operation = stored['targets'][0]['attempt']['operationId']
        self.assertIsNotNone(stored['targets'][0]['restartProof'])
        self.assertFalse(any(e['phase'] == 'native-exit-observed' for e in stored['events']))
        self.client.sent.clear()
        row = self.execute(ident, 'verify')['targets'][0]
        self.assertEqual('live-identity-confirmed-restart-unproven', row['reason'])
        self.assertEqual(['/status', '\x1b'], self.texts())
        attempt = self.load(ident)['targets'][0]['attempt']
        self.assertEqual(operation, attempt['operationId'])
        self.assertEqual('verified-running-restart-pending', attempt['state'])

    def test_332_resume_receipt_loss_or_timeout_keeps_attempt_and_never_resends(self):
        for failure in ('receipt', 'timeout'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory) / 'state'
                self.client = Claude332Fake()
                ident = self.prepare()
                self.client.sent.clear()
                original = self.client.call
                def call(*args):
                    result = original(*args)
                    if args[:2] == ('terminal', 'send') and ' --proof ' in args[args.index('--text') + 1]:
                        if failure == 'receipt': return {'send': {'accepted': False}}
                        raise m.Deferred('owned-resume-timeout')
                    return result
                with patch.object(self.client, 'call', side_effect=call):
                    row = self.execute(ident)['targets'][0]
                self.assertEqual('failed', row['state'])
                stored = self.load(ident)['targets'][0]
                self.assertEqual('uncertain', stored['attempt']['state'])
                self.assertIn('launchIntent', stored['restartProof'])
                self.assertEqual(1, self.texts().count('/exit'))
                self.assertEqual(1, sum(' --proof ' in text for text in self.texts()))
                before = list(self.texts())
                self.execute(ident)
                self.assertEqual(before, self.texts())

    def test_resumed_launch_mismatch_records_only_fixed_boolean_comparisons(self):
        selected = self.launch_patch.side_effect
        observed = self.observe_patch.side_effect
        for failure in ('environment', 'profile', 'shell', 'shell-executable', 'native-executable', 'query'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory) / 'state'
                self.client = Claude332Fake()
                ident = self.prepare()
                self.client.sent.clear()
                def launch(*args, **kwargs):
                    result = selected(*args, **kwargs)
                    if self.client.resumed:
                        if failure == 'environment': result['environment']['environmentSha256'] = 'private-raw-fixture'
                        elif failure == 'profile': result['environment']['profileSha256'] = 'private-raw-fixture'
                        elif failure == 'shell': result['shell']['tty'] += 1
                        elif failure == 'shell-executable': result['shellExecutable']['path'] = '/private-raw-fixture'
                    return result
                def process(*args, **kwargs):
                    result = observed(*args, **kwargs)
                    if self.client.resumed:
                        if failure == 'native-executable': result['process']['executable']['path'] = '/private-raw-fixture'
                        elif failure == 'query': result['queryExecutable']['path'] = '/private-raw-fixture'
                    return result
                self.launch_patch.side_effect = launch
                self.observe_patch.side_effect = process
                result = self.execute(ident)['targets'][0]
                self.assertEqual('claude-resumed-launch-mismatch', result['reason'])
                stored = self.load(ident)
                events = [e for e in stored['events'] if e['phase'] == 'claude-launch-comparison']
                self.assertEqual(1, len(events))
                fields = {key: value for key, value in events[0].items()
                          if key not in ('phase', 'targetId', 'operationId', 'at')}
                self.assertTrue(fields)
                self.assertTrue(all(type(value) is bool for value in fields.values()))
                expected = {'environment': 'environmentEqual', 'profile': 'profileEqual',
                            'shell': 'shellFieldsEqual', 'shell-executable': 'shellExecutableEqual',
                            'native-executable': 'nativeExecutableEqual', 'query': 'queryExecutableEqual'}[failure]
                self.assertFalse(fields[expected])
                self.assertNotIn('private-raw-fixture', json.dumps(stored['events']))
                self.assertEqual(1, self.texts().count('/status'))  # No unsafe post-resume query.
                self.assertEqual('uncertain', stored['targets'][0]['attempt']['state'])
                self.launch_patch.side_effect = selected
                self.observe_patch.side_effect = observed

    def test_332_changed_account_after_resume_is_not_success(self):
        ident = self.prepare()
        self.client.sent.clear()
        original = self.client.call
        def call(*args):
            result = original(*args)
            if args[:2] == ('terminal', 'send') and ' --proof ' in args[args.index('--text') + 1]:
                self.client.account = 'changed-after-exec@example.test'
            return result
        with patch.object(self.client, 'call', side_effect=call):
            row = self.execute(ident)['targets'][0]
        self.assertEqual('claude-account-mismatch', row['reason'])
        self.assertEqual(1, sum(' --proof ' in text for text in self.texts()))
        self.execute(ident)
        self.assertEqual(1, sum(' --proof ' in text for text in self.texts()))

    def test_332_missing_marker_or_receipt_never_resends(self):
        for failure in ('marker', 'receipt'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory)/'state'
                self.client = Claude332Fake()
                ident = self.prepare()
                self.client.sent.clear()
                self.client.bad_marker = failure == 'marker'
                original = self.client.call
                def call(*args):
                    result = original(*args)
                    if failure == 'receipt' and args[:2] == ('terminal', 'send') and args[args.index('--text')+1] == '/exit':
                        return {'send': {'accepted': False}}
                    return result
                with patch.object(self.client, 'call', side_effect=call), patch.object(m.time, 'monotonic', side_effect=range(1000)):
                    row = self.execute(ident)['targets'][0]
                self.assertEqual('failed', row['state'], row)
                self.assertEqual(['/status', '\x1b', '/exit'], self.texts())
                self.execute(ident)
                self.assertEqual(['/status', '\x1b', '/exit'], self.texts())



class MissingHintClaudeFake(Claude332Fake):
    """Physical Claude responses remain separate from a missing Orca hint."""
    def __init__(self):
        super().__init__()
        self.terms['term_target']['agentIdentity'] = None
        self.claude_version = '2.1.329'

    def call(self, *args):
        if (args[:2] == ('terminal', 'send') and args[args.index('--text') + 1] == '/status'
                and self.terms[args[args.index('--terminal') + 1]].get('agentIdentity') is None):
            self.sent.append(args)
            handle = args[args.index('--terminal') + 1]
            native = self.identities[handle]
            frame = self.frames[handle]
            frame['latestCursor'] = str(int(frame['latestCursor']) + 1)
            frame['tail'] = ['Settings  Status  Config  Usage  Stats', 'Version: ' + self.claude_version,
                             'Session ID: ' + native['sessionId'], 'cwd: ' + native['cwd'],
                             'Login method: Claude Account', 'Organization: Owned fixture',
                             'Email: ' + self.account, '←/→ to switch · Esc to close']
            self.modals.add(handle)
            return {'send': {'accepted': True}, 'mutation': {'requestId': str(uuid.uuid4())}}
        return super().call(*args)


class MissingClaudeProvider(unittest.TestCase):
    prepare = Restart.prepare
    execute = Restart.execute
    load = Restart.load
    texts = Restart.texts

    def setUp(self):
        Claude332Restart.setUp(self)
        self.client = MissingHintClaudeFake()
        observed = self.observe_patch.side_effect
        def rich(*args, **kwargs):
            proof = observed(*args, **kwargs)
            proof['process'].update(pid=proof['pid'], cwd=proof['cwd'], paneKey=proof['paneKey'])
            return proof
        self.observe_patch.side_effect = rich
        self.recheck = patch.object(m.live, 'recheck').start()

    def context(self):
        item = self.client.terms['term_target']
        row = dict(targetId=item['handle'], terminal=m.rr.fingerprint(item), choice='restart',
                   provider='claude', native=None)
        return row, item, self.client.inventory()[1]

    def test_missing_hint_prepare_uses_unique_api_without_rewriting_observations(self):
        terms, agents = copy.deepcopy(self.client.terms), copy.deepcopy(self.client.agents)
        ident = self.prepare()
        row = self.load(ident)['targets'][0]
        self.assertEqual('ready', row['state'], row)
        self.assertEqual(SESSION, row['native']['sessionId'])
        self.assertEqual('2.1.329', row['native']['nativeVersion'])
        self.assertEqual(['/status', '\x1b'], self.texts())
        self.assertEqual(terms, self.client.terms)
        self.assertEqual(agents, self.client.agents)
        self.assertIsNone(self.observe_patch.call_args.kwargs['expected'])
        self.assertGreater(self.recheck.call_count, 2)
        self.assertNotIn('nativeProvider', json.dumps(self.load(ident)))

    def test_omitted_hint_initial_prepare_locate_verify_and_post_resume_keep_proofs(self):
        self.client.terms['term_target'].pop('agentIdentity')
        before = copy.deepcopy(self.client.terms)
        ident = self.prepare()
        self.assertEqual('ready', self.load(ident)['targets'][0]['state'])
        self.assertEqual(before, self.client.terms)
        self.assertNotIn('agentIdentity', self.client.observe('term_target')[0])
        self.assertNotIn('agentIdentity', self.client.inventory()[0]['terminals'][1])
        self.client.sent.clear()
        self.assertEqual('already-running', self.execute(ident, 'verify')['targets'][0]['state'])
        self.assertEqual(['/status', '\x1b'], self.texts())
        self.client.sent.clear()
        self.assertEqual('restarted', self.execute(ident)['targets'][0]['state'])
        self.assertEqual(1, self.texts().count('/exit'))
        self.assertEqual(1, sum(' --proof ' in text for text in self.texts()))
        self.assertNotIn('agentIdentity', self.client.terms['term_target'])
        self.client.sent.clear()
        self.assertEqual('already-running', self.execute(ident, 'verify')['targets'][0]['state'])
        self.assertEqual(['/status', '\x1b'], self.texts())
        self.assertNotIn('agentIdentity', self.client.terms['term_target'])

    def test_missing_hint_api_uuid_and_source_must_match_native_status_before_storage(self):
        for failure in ('uuid', 'source'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory) / 'state'
                self.client = MissingHintClaudeFake()
                self.observe_patch.reset_mock()
                original = self.client.call
                def call(*args):
                    result = original(*args)
                    if args[:2] == ('terminal', 'send') and args[args.index('--text') + 1] == '/status':
                        frame = self.client.frames['term_target']
                        if failure == 'uuid':
                            frame['tail'] = [line.replace(SESSION, '11111111-1111-4111-8111-111111111111')
                                             for line in frame['tail']]
                        else: frame['tail'][1] = 'Version: 2.1.332'
                    return result
                with patch.object(self.client, 'call', side_effect=call):
                    ident = self.prepare()
                row = self.load(ident)['targets'][0]
                expected = 'native-provider-session-mismatch' if failure == 'uuid' else 'native-provider-source-mismatch'
                self.assertEqual(expected, row['reason'])
                self.assertIsNone(row['native'])
                self.assertEqual('uncertain', self.load(ident)['prepareState'])
                self.assertEqual(['/status', '\x1b'], self.texts())
                self.assertEqual(1, self.observe_patch.call_count)
                self.assertIsNone(self.observe_patch.call_args.kwargs['expected'])

    def test_missing_hint_locate_verify_and_hint_restored_keep_fixed_authority(self):
        ident = self.prepare()
        self.client.sent.clear()
        self.observe_patch.reset_mock()
        self.assertEqual('already-running', self.execute(ident, 'verify')['targets'][0]['state'])
        self.assertEqual(['/status', '\x1b'], self.texts())
        self.assertEqual(1, self.observe_patch.call_count)  # Reuse target; local checks do not rediscover.
        self.assertEqual(SESSION, self.observe_patch.call_args.kwargs['expected'])
        row, item, ps = self.context()
        target = m.target_from(self.client, item, ps, self.self_pane, selected_row=row)
        self.client.terms['term_target']['agentIdentity'] = 'claude'
        self.client.sent.clear()
        self.recheck.reset_mock()
        m.rr.guard(self.client, m.current_plan(self.client, self.self_pane), target, self.self_pane)
        self.assertGreater(self.recheck.call_count, 0)
        self.assertEqual([], self.texts())

    def test_missing_hint_restart_renews_only_from_new_pinned_process_proof(self):
        ident = self.prepare()
        self.client.sent.clear()
        row = self.execute(ident)['targets'][0]
        self.assertEqual('restarted', row['state'], row)
        self.assertIsNone(self.client.terms['term_target']['agentIdentity'])
        self.assertEqual(1, self.texts().count('/exit'))
        self.assertEqual(1, sum(' --proof ' in text for text in self.texts()))
        self.client.sent.clear()
        self.assertEqual('already-running', self.execute(ident, 'verify')['targets'][0]['state'])
        self.assertEqual(['/status', '\x1b'], self.texts())

    def test_missing_hint_selection_provider_and_ps_negatives_never_input(self):
        for failure in ('manual', 'unselected', 'codex-row', 'explicit-codex', 'empty-hint', 'absent-unselected', 'absent-ps-codex',
                        'ps-missing', 'ps-codex', 'self'):
            with self.subTest(failure=failure):
                self.client = MissingHintClaudeFake()
                row, item, ps = self.context()
                self.observe_patch.reset_mock()
                if failure == 'manual': row['choice'] = 'manual'
                elif failure == 'unselected': row = None
                elif failure == 'codex-row': row['provider'] = 'codex'
                elif failure == 'explicit-codex': item['agentIdentity'] = 'codex'
                elif failure == 'empty-hint': item['agentIdentity'] = ''
                elif failure == 'absent-unselected':
                    item.pop('agentIdentity')
                    row = None
                elif failure == 'absent-ps-codex':
                    item.pop('agentIdentity')
                    m.rr.agent_for(ps, item)['agentType'] = 'codex'
                elif failure == 'ps-missing':
                    for workspace in ps['worktrees']:
                        workspace['agents'] = [a for a in workspace['agents'] if a.get('paneKey') != 'tab:target']
                elif failure == 'ps-codex':
                    m.rr.agent_for(ps, item)['agentType'] = 'codex'
                else:
                    item = self.client.terms['term_self']
                    item['agentIdentity'] = None
                    m.rr.agent_for(ps, item)['agentType'] = 'claude'
                    row['terminal'] = m.rr.fingerprint(item)
                with self.assertRaises(m.Deferred):
                    m.target_from(self.client, item, ps, self.self_pane, selected_row=row)
                self.assertEqual([], self.texts())
                self.assertEqual(0, self.observe_patch.call_count)

    def test_missing_hint_busy_draft_approval_child_and_wait_guards_are_not_bypassed(self):
        for omitted in (False, True):
            for failure in ('busy', 'draft', 'approval', 'child', 'wait', 'unknown-child'):
                with self.subTest(failure=failure):
                    self.client = MissingHintClaudeFake()
                    row, item, ps = self.context()
                    if omitted: item.pop('agentIdentity')
                    if failure == 'busy': m.rr.agent_for(ps, item)['programStatus']['state'] = 'working'
                    elif failure == 'draft': self.client.frames['term_target']['draft'] = 'owned typed draft'
                    elif failure == 'approval': self.client.frames['term_target']['tail'].append('Allow once')
                    elif failure == 'child': m.rr.agent_for(ps, item)['children'] = [{'state': 'working'}]
                    elif failure == 'wait': item['agentWait'] = {'kind': 'approval'}
                    else: m.rr.agent_for(ps, item)['subagentObservation'] = 'unverifiable'
                    with self.assertRaises(m.Deferred):
                        m.target_from(self.client, item, ps, self.self_pane, selected_row=row)
                    self.assertEqual([], self.texts())

    def test_missing_hint_wrong_uuid_executable_pane_cwd_or_runtime_never_inputs(self):
        observed = self.observe_patch.side_effect
        for failure in ('uuid', 'executable', 'query', 'pane', 'cwd', 'process-pane', 'pid', 'runtime'):
            with self.subTest(failure=failure):
                self.client = MissingHintClaudeFake()
                row, item, ps = self.context()
                row['native'] = {'sessionId': SESSION}
                def wrong(*args, **kwargs):
                    proof = observed(*args, **kwargs)
                    if failure == 'uuid': proof['sessionId'] = str(uuid.uuid4())
                    elif failure == 'executable': proof['process']['executable']['path'] = '/unsupported/native'
                    elif failure == 'query': proof['queryExecutable']['path'] = '/unsupported/query'
                    elif failure == 'pane': proof['paneKey'] = 'tab:other'
                    elif failure == 'cwd': proof['cwd'] = '/other'
                    elif failure == 'process-pane': proof['process']['paneKey'] = 'tab:other'
                    elif failure == 'pid': proof['process']['pid'] += 1
                    else: self.client.runtime = 'changed-runtime'
                    return proof
                self.observe_patch.side_effect = wrong
                with self.assertRaises(m.Deferred):
                    m.target_from(self.client, item, ps, self.self_pane, selected_row=row)
                self.assertEqual([], self.texts())
                self.observe_patch.side_effect = observed

    def test_missing_hint_fixed_callback_rejects_identity_runtime_process_and_other_provider_drift(self):
        for failure in ('identity', 'runtime', 'process', 'other-provider', 'proof-edit'):
            with self.subTest(failure=failure):
                self.client = MissingHintClaudeFake()
                self.recheck.side_effect = None
                row, item, ps = self.context()
                target = m.target_from(self.client, item, ps, self.self_pane, selected_row=row)
                if failure == 'identity': target['identity']['ptyId'] = 'changed-in-place'
                elif failure == 'runtime': self.client.runtime = 'changed-runtime'
                elif failure == 'process': self.recheck.side_effect = m.Deferred('exception-live-proof-changed')
                elif failure == 'other-provider': self.client.terms['term_target']['agentIdentity'] = 'codex'
                else: target['nativeProviderProof']['process']['startTicks'] += 1
                with self.assertRaises(m.Deferred):
                    if failure == 'other-provider':
                        m.rr.passive_guard(self.client, m.current_plan(self.client, self.self_pane), target, self.self_pane)
                    else: m.rr.native_provider_check(self.client, target)
                self.assertEqual([], self.texts())
        self.recheck.side_effect = None

    def test_missing_hint_token_cannot_be_reused_for_another_pane_or_general_refresh(self):
        row, item, ps = self.context()
        target = m.target_from(self.client, item, ps, self.self_pane, selected_row=row)
        token = m.rr.native_provider_check(self.client, target, item)
        other = self.client.add('other', '/work', 'claude')
        self.client.terms[other]['agentIdentity'] = None
        _, ps = self.client.inventory()
        with self.assertRaises(m.Deferred):
            m.rr.eligible(self.client.terms[other], self.client.frames[other], ps, self.self_pane,
                          True, tui_idle=True, verified_provider=token)
        with self.assertRaises(m.Deferred):
            m.rr.eligible(item, self.client.frames['term_target'], ps, self.self_pane, True, tui_idle=True)
        self.assertEqual([], self.texts())

    def test_missing_hint_process_drift_after_durable_status_intent_has_no_transport(self):
        original = m.Recorder.record
        def record(recorder, phase, **values):
            result = original(recorder, phase, **values)
            if phase == 'sending' and values.get('step') == 'status':
                self.recheck.side_effect = m.Deferred('exception-live-proof-changed')
            return result
        with patch.object(m.Recorder, 'record', new=record):
            ident = self.prepare()
        stored = self.load(ident)
        self.assertEqual('uncertain', stored['prepareState'])
        self.assertEqual('exception-live-proof-changed', stored['targets'][0]['reason'])
        self.assertEqual([], self.texts())
        self.assertTrue(any(e['phase'] == 'sending' for e in stored['events']))
        self.assertFalse(any(e['phase'] == 'accepted' for e in stored['events']))


if __name__ == '__main__':
    unittest.main()
