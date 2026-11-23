"""Owned transport doubles only; no user terminal or native account is touched."""
import copy
from contextlib import redirect_stdout
import importlib.util
import json
import io
import os
from pathlib import Path
import tempfile
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
            frame = self.frames[h]
            frame['latestCursor'] = str(int(frame['latestCursor']) + 1)
            if command == '/status':
                identity = self.identities[h]
                frame['delta'] = ['Session ID: '+identity['sessionId'], 'cwd: '+identity['cwd'],
                                  'Permissions: '+identity['permissions']]
                if self.terms[h]['agentIdentity'] == 'claude':
                    frame['delta'].append('Version: '+self.claude_version)
                else:
                    frame['delta'].insert(0, 'OpenAI Codex (v'+self.codex_version+')')
                frame['tail'] = frame['delta'] + ['›' if self.terms[h]['agentIdentity'] == 'codex' else '❯']
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
        self.client.installed_codex_version = '0.172.0'
        self.client.sent.clear()
        row = self.execute(ident, 'restore')['targets'][0]
        self.assertEqual('manual-restart-required', row['state'])
        self.assertEqual('native-resume-version-unverified', row['reason'])
        self.assertEqual([], self.client.created)
        self.assertEqual([], self.client.sent)

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
        def ready(*args):
            self.assertEqual([], self.client.sent)
            calls.append(True)
            if len(calls) == 1:
                raise m.Deferred('child-state-unknown')
            return original(*args)
        with patch.object(m, 'target_from', side_effect=ready), patch.object(m.time, 'sleep') as sleep:
            row = self.execute(ident, 'restore')['targets'][0]
        self.assertEqual('restarted', row['state'])
        self.assertEqual(2, len(calls))
        sleep.assert_called_once_with(0.2)
        self.assertEqual(['/status'], self.texts())
        self.assertEqual(1, len(self.client.created))

    def test_owned_restore_persistent_child_unknown_stops_without_status_or_second_create(self):
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

    def test_prepare_timeout_is_durable_and_prevents_new_status_submission(self):
        self.client.fail = 'timeout'
        ident = self.prepare()
        self.assertEqual('uncertain', self.load(ident)['prepareState'])
        self.client.fail = None
        with self.assertRaisesRegex(m.Deferred, 'unresolved-batch'):
            self.prepare()
        self.assertEqual(1, len(self.client.sent))

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


if __name__ == '__main__':
    unittest.main()
