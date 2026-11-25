import copy
from contextlib import redirect_stderr, redirect_stdout
from contextlib import ExitStack, contextmanager
import fcntl
import io
import importlib.util
import json
import os
import pty
from pathlib import Path
import subprocess
import signal
import select
import shlex
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

SCRIPT = Path(__file__).resolve().parents[1] / 'common/base/skills/session/scripts/runtime_refresh.py'
spec = importlib.util.spec_from_file_location('runtime_refresh', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
REAL_PLUGIN_INVENTORY = m.plugin_inventory


def terminal(handle='term_target', leaf='target'):
    return dict(handle=handle, ptyId='pty-'+leaf, incarnationId='inc-'+leaf,
                worktreeId='workspace', worktreePath='/work', executionHostId='local',
                tabId='tab', leafId=leaf, agentIdentity='codex', agentWait=None,
                orphaned=False, connected=True, writable=True)


def agent(t):
    return dict(paneKey=m.pane(t), agentType='codex', state='idle', mainAgent={'state': 'idle'},
                programStatus={'state': 'idle'}, subagentObservation='live', children=[])


def codex_screen_pair(cwd='/work'):
    """Synthetic observed line order/equality only; this is not native evidence."""
    lines = {i: 'fixture-line-'+str(i) for i in range(1, 21)}
    card = ['  >_ OpenAI Codex (v0.167.2)', *[lines[i] for i in range(5, 10)],
            '  Directory:           '+cwd, '  Permissions:         Full Access',
            *[lines[i] for i in range(10, 15)],
            '  Session:             11111111-1111-4111-8111-111111111111',
            *[lines[i] for i in range(15, 19)]]
    before = ['› earlier fixture instruction', *[lines[i] for i in range(1, 5)],
              '/status', *card, '› Ask Codex to do anything', lines[19], lines[20]]
    after = [before[0], *card[-6:], '/status', *card,
             '› Ask Codex to do anything', lines[19], lines[20]]
    return before, after


def completed_hook_error_screen(version='0.167.2', composer='› Ask Codex to do anything'):
    """Synthetic history only: never copy personal native frames into fixtures."""
    return ['  >_ OpenAI Codex (v'+version+')', '› fixture completed request',
            '• fixture response', '• Hook failed',
            '  └ plugin contents changed; hook approval required',
            '  Worked for 3s • 1:02 PM', '  ↳ fixture completion recap', composer,
            '  fixture-model default · /work · fixture', '  ← for agents · ? for shortcuts']


class Fake:
    environment = None
    runtime = 'runtime'

    def __init__(self):
        self.target = terminal()
        self.self = terminal('term_self', 'self')
        self.agents = [agent(self.self), agent(self.target)]
        self.read = {'source': 'screen', 'tail': ['›'], 'latestCursor': '10'}
        self.sent = []
        self.fail = None

    def inventory(self):
        return ({'terminals': [copy.deepcopy(self.self), copy.deepcopy(self.target)],
                 'truncated': False, 'hostScope': {'hostIds': ['local'], 'omittedHostIds': ['remote'],
                                                  'omittedHostSelectors': [{'selector': '--environment remote'}]}},
                {'worktrees': [{'worktreeId': 'workspace', 'agents': self.agents}]})

    def observe(self, handle):
        return copy.deepcopy(self.self if handle == self.self['handle'] else self.target), copy.deepcopy(self.read)

    def call(self, *args):
        if args[:2] == ('terminal', 'read'):
            return {'terminal': {'source': 'stream', 'tail': [
                'To continue this session, run:', '  codex resume 01a1c848-8ff2-7e90-bcec-44a3ca07a21b']}}
        if args[:2] == ('terminal', 'send'):
            self.sent.append(args)
            if self.fail:
                raise m.Deferred(self.fail)
        return {'send': {'accepted': True}, 'mutation': {'requestId': 'request'}, 'wait': {'satisfied': True}}


class ClaudeFake(Fake):
    def __init__(self):
        super().__init__()
        self.target['agentIdentity'] = 'claude'
        self.agents[1]['agentType'] = 'claude'
        self.read['tail'] = ['❯', 'Permission mode: default']
        self.delta = []
        self.responses = {
            '/status': ['Session ID: 01a1c848-8ff2-7e90-bcec-44a3ca07a21b', 'Working directory: /work',
                        'Permission mode: default', 'Version: 2.1.289'],
            '/help': ['/reload-plugins Reload active plugins'],
            '/plugin list --enabled': ['example@market 1.0.0 user enabled'],
            '/reload-plugins': ['Reloaded: 1 plugins · 2 skills · 0 agents · 1 hooks · 0 plugin MCP servers · 0 plugin LSP servers'],
        }

    def call(self, *args):
        if args[:2] == ('terminal', 'read'):
            return {'terminal': {'source': 'stream', 'tail': self.delta}}
        result = super().call(*args)
        if args[:2] == ('terminal', 'send'):
            self.delta = self.responses[args[args.index('--text')+1]]
            self.read['tail'] = self.delta + ['❯', 'Permission mode: default']
            self.read['latestCursor'] = str(int(self.read['latestCursor'])+1)
        return result


class ClaudeModalFake(ClaudeFake):
    def __init__(self):
        super().__init__()
        self.agents[1].update(state='done', mainAgent={'state':'done'}, programStatus=None)
        self.agents[1].pop('children')
        self.agents[1].pop('subagentObservation')
        self.read['tail']=['❯','  ⏵⏵ bypass permissions on (shift+tab to cycle)']
        self.modal = None
        self.help_page = 0
        self.stale = False

    def call(self,*args):
        if args[:2] != ('terminal','send'):
            return super().call(*args)
        self.sent.append(args)
        text=args[args.index('--text')+1]
        if self.stale:
            return {'send':{'accepted':True},'mutation':{'requestId':'request'}}
        if text == '/status':
            self.modal='/status'
            self.read['tail']=['   Settings  Status   Config   Usage   Stats',
                '   Version: 2.1.322','   Session ID: 01a1c848-8ff2-7e90-bcec-44a3ca07a21b',
                '   cwd: /work','   Esc to cancel']
        elif text == '/help':
            self.modal='/help'
            self.read['tail']=['   Help  General   Commands   Custom commands','   General help','   Esc to cancel']
        elif text == '\x1b':
            self.modal=None
            self.read['tail']=['❯','  ⏵⏵ bypass permissions on (shift+tab to cycle)']
        elif text == '\x1b[C':
            self.read['tail']=['   Help  General   Commands   Custom commands','   Browse default commands','   ❯ /add-dir','   Esc to cancel']
        elif text == '\x1b[B' * 10:
            self.help_page += 1
            self.read['tail']=['   Help  General   Commands   Custom commands','   Browse default commands',
                                '   ❯ /reload-plugins' if self.help_page == 3 else '   ❯ /other', '   Esc to cancel']
        else:
            response=(['example@market (v1.0.0, user) ✔ enabled']
                      if text == '/plugin list --enabled' else self.responses[text])
            self.read['tail']=['❯ '+text]+response+['❯','  ⏵⏵ bypass permissions on (shift+tab to cycle)']
        # Raw keys use the observed no-mutation receipt; commands retain request IDs.
        if '--enter' not in args:
            return {'send':{'handle':self.target['handle'],'accepted':True,'bytesWritten':len(text.encode('utf-8'))}}
        return {'send':{'accepted':True},'mutation':{'requestId':'request'}}


class RuntimeRefreshTests(unittest.TestCase):
    def setUp(self):
        self.installation = {'state': 'observed', 'nativeVersion': '0.167.1', 'plugins': [
            {'id': 'example@market', 'version': '1.0.0', 'enabled': True, 'scope': 'user'}]}
        inventory_patch = patch.object(m, 'plugin_inventory', return_value=self.installation)
        self.inventory = inventory_patch.start()
        self.addCleanup(inventory_patch.stop)
        self.client = Fake()
        self.self_pane = m.pane(self.client.self)
        self.report = m.inspect(self.client, self.self_pane)
        self.plan = m.make_plan(self.report, ['term_target'])
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def test_inspect_is_read_only_and_metadata_only(self):
        self.client.target['preview'] = 'SECRET prompt'
        report = m.inspect(self.client, self.self_pane)
        self.assertEqual([], self.client.sent)
        self.assertNotIn('SECRET', json.dumps(report))
        self.assertEqual('self', report['targets'][0]['reason'])
        self.assertEqual(['remote'], report['hostScope']['omittedHostIds'])

    def test_self_unidentified_defers_every_target(self):
        result = m.inspect(self.client, None)
        self.assertTrue(all(t['reason'] == 'self-unidentified' for t in result['targets']))

    def test_busy_draft_approval_children_unknown_matrix(self):
        cases = [('busy-or-state-unknown', lambda c: c.agents[1].update(state='working')),
                 ('draft', lambda c: c.read.update(tail=['› unfinished'])),
                 ('approval-or-wait', lambda c: c.target.update(agentWait={'state': 'waiting'})),
                 ('child-work', lambda c: c.agents[1].update(subagents=[{'state': 'working'}])),
                 ('child-state-unknown', lambda c: c.agents[1].pop('subagentObservation')),
                 ('invalid-json-shape', lambda c: c.agents[1].pop('programStatus')),
                 ('screen-unknown', lambda c: c.read.update(source='buffer')),
                 ('approval-or-menu', lambda c: c.read.update(tail=['›', 'Enter to confirm']))]
        for reason, change in cases:
            with self.subTest(reason=reason):
                client = Fake(); change(client)
                report = m.inspect(client, self.self_pane)
                self.assertEqual(reason, report['targets'][1]['reason'])
                self.assertEqual([], client.sent)

    def test_explicit_unique_selection_only(self):
        for selected in ([], ['term_target', 'term_target'], ['term_self'], ['missing']):
            with self.assertRaises(m.Deferred):
                m.make_plan(self.report, selected)

    def test_incarnation_runtime_and_state_race_prevent_input(self):
        for change in (lambda c: c.target.update(incarnationId='new'),
                       lambda c: setattr(c, 'runtime', 'new'),
                       lambda c: c.agents[1].update(state='working')):
            with self.subTest(change=change):
                client = Fake(); change(client)
                with tempfile.TemporaryDirectory() as folder:
                    result = m.apply(client, self.plan, self.self_pane, folder)
                self.assertIn('stopped', result)
                self.assertEqual([], client.sent)

    def test_metadata_wait_rechecks_state_before_whole_apply(self):
        changes = [('busy-or-state-unknown', lambda c: c.agents[1].update(state='working')),
                   ('draft', lambda c: c.read.update(draft='pending', tail=['› pending'])),
                   ('runtime-changed', lambda c: setattr(c, 'runtime', 'new')),
                   ('target-changed', lambda c: c.target.update(incarnationId='new')),
                   ('self-unidentified', lambda c: c.self.update(leafId='new'))]
        for expected, mutate in changes:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as folder:
                client = Fake()
                def lookup(*args):
                    mutate(client)
                    return self.installation
                with patch.object(m, 'plugin_inventory', side_effect=lookup):
                    result = m.apply(client, self.plan, self.self_pane, folder)
                self.assertEqual(expected, result['stopped'])
                self.assertEqual([], client.sent)

    def test_five_minutes_remains_apply_start_deadline(self):
        now = [1000.0]
        plan = dict(self.plan, createdAt=now[0])
        def lookup(*args):
            now[0] = 1301.0
            return self.installation
        with patch.object(m.time, 'time', side_effect=lambda: now[0]), patch.object(m, 'plugin_inventory', side_effect=lookup):
            result = m.apply(self.client, plan, self.self_pane, self.temp.name)
        self.assertEqual(1, len(self.client.sent))
        self.assertEqual('native-response-freshness-unknown', result['stopped'])

    def test_remote_apply_is_delegated_without_input(self):
        self.plan['environment'] = 'remote'
        with self.assertRaisesRegex(m.Deferred, 'delegate'):
            m.apply(self.client, self.plan, self.self_pane, self.temp.name)
        self.assertEqual([], self.client.sent)

    def test_timeout_does_not_resend_and_same_operation_cannot_replay(self):
        self.client.fail = 'cli-unavailable-or-timeout'
        result = m.apply(self.client, self.plan, self.self_pane, self.temp.name)
        self.assertEqual(1, len(self.client.sent))
        self.assertEqual(['term_target'], result['remaining'])
        self.assertIn('journal', result['recovery'])
        with self.assertRaisesRegex(m.Deferred, 'already-started'):
            m.apply(self.client, self.plan, self.self_pane, self.temp.name)
        self.assertEqual(1, len(self.client.sent))

    def test_parallel_apply_lock(self):
        with m.Journal(self.temp.name, self.plan['operationId']):
            with self.assertRaisesRegex(m.Deferred, 'locked'):
                m.apply(self.client, self.plan, self.self_pane, self.temp.name)
        self.assertEqual([], self.client.sent)

    def test_first_failure_stops_rest(self):
        self.plan['targets'].append(copy.deepcopy(self.plan['targets'][0]))
        self.plan['targets'][1]['handle'] = 'term_other'
        self.plan['targets'][1]['identity']['handle'] = 'term_other'
        self.client.fail = 'timeout'
        result = m.apply(self.client, self.plan, self.self_pane, self.temp.name)
        self.assertEqual(['term_target', 'term_other'], result['remaining'])
        self.assertEqual(1, len(self.client.sent))

    def test_success_compares_identity_and_leaves_consumption_unverified(self):
        identity = {'sessionId': '01a1c848-8ff2-7e90-bcec-44a3ca07a21b', 'cwd': '/work', 'permissions': 'Full Access', 'resumeMode': 'codex-full-access', 'nativeVersion': '0.171.0'}
        with patch.object(m, 'native_status', return_value=identity), patch.object(m, 'shell_guard'):
            result = m.apply(self.client, self.plan, self.self_pane, self.temp.name)
        row = result['results'][0]
        self.assertEqual(row['before'], row['after'])
        self.assertEqual('unverified', row['consumption'])
        texts = [args[args.index('--text')+1] for args in self.client.sent]
        self.assertEqual(['/exit', 'codex resume '+identity['sessionId']+' --dangerously-bypass-approvals-and-sandbox'], texts)
        self.assertNotIn('--last', ' '.join(texts))

    def test_identity_permission_mismatch_stops(self):
        before = {'sessionId': '01a1c848-8ff2-7e90-bcec-44a3ca07a21b', 'cwd': '/work', 'permissions': 'Full Access', 'resumeMode': 'codex-full-access', 'nativeVersion': '0.171.0'}
        after = dict(before, permissions='different')
        with patch.object(m, 'native_status', side_effect=[before, after]), patch.object(m, 'shell_guard'):
            result = m.apply(self.client, self.plan, self.self_pane, self.temp.name)
        self.assertEqual('native-identity-or-permissions-mismatch', result['stopped'])

    def test_codex_known_cli_upgrade_keeps_identity_mode_comparison(self):
        before = {'sessionId': '01a1c848-8ff2-7e90-bcec-44a3ca07a21b', 'cwd': '/work',
                  'permissions': 'Full Access', 'resumeMode': 'codex-full-access', 'nativeVersion': '0.167.2'}
        after = dict(before, nativeVersion='0.171.0')
        self.installation['nativeVersion'] = '0.171.0'
        self.plan['targets'][0]['installation'] = copy.deepcopy(self.installation)
        with patch.object(m, 'native_status', side_effect=[before, after]), patch.object(m, 'shell_guard'):
            result = m.apply(self.client, self.plan, self.self_pane, self.temp.name)
        self.assertEqual([], result['remaining'])
        self.assertEqual('native-resume-observed', result['results'][0]['refresh'])

    def test_shell_must_be_current_and_empty(self):
        self.client.target['agentIdentity'] = None
        self.client.read['tail'] = ['user@host:/work$']
        m.shell_guard(self.client, self.plan, self.plan['targets'][0], {'cursor': '10', 'sessionId': '01a1c848-8ff2-7e90-bcec-44a3ca07a21b'})
        for lines in (['old$','codex menu'], ['user$ unfinished'], ['›']):
            self.client.read['tail'] = lines
            with self.assertRaises(m.Deferred):
                m.shell_guard(self.client, self.plan, self.plan['targets'][0], {'cursor': '10', 'sessionId': '01a1c848-8ff2-7e90-bcec-44a3ca07a21b'})

    def glyph_shell(self):
        self.client.read['tail'] = ['NAS prompt context', '❯']
        inventory = self.client.inventory
        def complete():
            ts, ps = inventory()
            ps.update(truncated=False, hostScope={'hostIds': ['local']})
            return ts, ps
        self.client.inventory = complete
        return self.plan['targets'][0], {'cursor': '10', 'sessionId': '01a1c848-8ff2-7e90-bcec-44a3ca07a21b'}

    def test_glyph_shell_requires_fixed_process_and_fresh_exit_proof(self):
        target, evidence = self.glyph_shell()
        with patch.object(m, 'target_shell_process_proof', return_value={'generation': 1}):
            m.shell_guard(self.client, self.plan, target, evidence)
            self.assertEqual({'generation': 1}, self.client.target_shell_proof['process'])
            m.shell_guard(self.client, self.plan, target, evidence)
            with patch.object(self.client, 'call', return_value={'terminal': {'source': 'stream', 'tail': []}}):
                with self.assertRaisesRegex(m.Deferred, 'shell-unconfirmed'):
                    m.shell_guard(self.client, self.plan, target, evidence)
            self.assertEqual([], self.client.sent)
        with patch.object(m, 'target_shell_process_proof', return_value={'generation': 2}):
            with self.assertRaisesRegex(m.Deferred, 'target-shell-proof-changed'):
                m.shell_guard(self.client, self.plan, target, evidence)

    def test_glyph_false_prompt_and_live_agent_matrix_never_sends(self):
        for unsafe in ('typed', 'draft', 'repl', 'child', 'parent', 'child-pane', 'duplicate-pane', 'wait', 'busy', 'remote', 'incomplete'):
            with self.subTest(unsafe=unsafe):
                self.client = Fake()
                target, evidence = self.glyph_shell()
                if unsafe == 'typed': self.client.read['tail'][-1] = '❯ command'
                elif unsafe == 'draft': self.client.read['draft'] = 'secret'
                elif unsafe == 'repl': self.client.read['tail'][-1] = '>>> '
                elif unsafe == 'child': self.client.agents[1]['children'] = [{'state': 'running'}]
                elif unsafe == 'parent': self.client.agents[1]['parentPaneKey'] = 'tab:other'
                elif unsafe == 'child-pane':
                    self.client.agents.append({'paneKey': 'tab:child', 'parentPaneKey': 'tab:target'})
                elif unsafe == 'duplicate-pane':
                    inventory = self.client.inventory
                    def duplicate():
                        ts, ps = inventory()
                        ts['terminals'].append(terminal('term_duplicate'))
                        return ts, ps
                    self.client.inventory = duplicate
                elif unsafe == 'wait': self.client.target['agentWait'] = {'kind': 'approval'}
                elif unsafe == 'busy': self.client.agents[1]['programStatus']['state'] = 'running'
                elif unsafe == 'remote': self.client.environment = 'remote'
                else:
                    inventory = self.client.inventory
                    def incomplete():
                        ts, ps = inventory()
                        ps['truncated'] = True
                        return ts, ps
                    self.client.inventory = incomplete
                with patch.object(m, 'target_shell_process_proof', return_value={'fixed': True}):
                    with self.assertRaises(m.Deferred):
                        m.shell_guard(self.client, self.plan, target, evidence)
                self.assertEqual([], self.client.sent)
                self.assertIsNone(getattr(self.client, 'target_shell_proof', None))

    def test_glyph_resume_rechecks_durable_write_and_retains_sending_without_transport(self):
        target, evidence = self.glyph_shell()
        process = {'generation': 1}
        journal = Mock()
        with patch.object(m, 'target_shell_process_proof', side_effect=lambda identity: copy.deepcopy(process)):
            m.shell_guard(self.client, self.plan, target, evidence)
            def durable(*args, **kwargs):
                process['generation'] = 2
            journal.record.side_effect = durable
            with self.assertRaisesRegex(m.Deferred, 'target-shell-proof-changed'):
                m.send(self.client, journal, target, 'codex resume exact', 'exact-resume')
        self.assertEqual([], self.client.sent)
        journal.record.assert_called_once_with('sending', handle=target['handle'], step='exact-resume')

    def test_legacy_absolute_shell_does_not_require_target_process_probe(self):
        for suffix in ('$', '#'):
            self.client.read['tail'] = ['user@host:/work' + suffix]
            with patch.object(m, 'target_shell_process_proof', side_effect=AssertionError('legacy branch')):
                m.shell_guard(self.client, self.plan, self.plan['targets'][0],
                              {'cursor': '10', 'sessionId': '01a1c848-8ff2-7e90-bcec-44a3ca07a21b'})

    def test_native_status_metadata_and_hostile_input(self):
        text = 'Session: 01a1c848-8ff2-7e90-bcec-44a3ca07a21b\nDirectory: /work\nPermissions: Full Access\n'
        self.assertEqual('/work', m.status('codex', text)['cwd'])
        with self.assertRaises(m.Deferred):
            m.status('codex', text.replace('01a1c848-8ff2-7e90-bcec-44a3ca07a21b', '$(touch /tmp/pwned)'))
        for value in (None, [], {'schema': 99}, dict(self.plan, createdAt=time.time()-301), dict(self.plan, operationId={})):
            with self.assertRaises(m.Deferred):
                m.validate_plan(value)

    def test_resume_commands_preserve_only_two_observed_modes_and_ignore_stored_flags(self):
        session = '01a1c848-8ff2-7e90-bcec-44a3ca07a21b'
        cases = [('codex', 'Full Access', '0.171.0',
                  'codex resume '+session+' --dangerously-bypass-approvals-and-sandbox'),
                 ('claude', 'bypass permissions', '2.1.330',
                  'claude --dangerously-skip-permissions --resume '+session)]
        for provider, permissions, version, expected in cases:
            text = 'Session ID: '+session+'\ncwd: /work\nPermissions: '+permissions+'\n'
            if version:
                text += ('OpenAI Codex (v'+version+')\n' if provider == 'codex' else 'Version: '+version+'\n')
            native = m.status(provider, text)
            native.update(command='touch /tmp/not-authorized', flags=['--fake-flag'], environment={'PATH': '/fake'})
            with self.subTest(provider=provider):
                self.assertEqual(expected, m.resume_command(provider, native, installed_version=version))
                legacy = dict(native)
                legacy.pop('resumeMode')
                with self.assertRaisesRegex(m.Deferred, 'native-resume-permissions-unverified'):
                    m.resume_command(provider, legacy, installed_version=version)
                native['resumeMode'] = '--fake-flag'
                with self.assertRaisesRegex(m.Deferred, 'native-resume-permissions-unverified'):
                    m.resume_command(provider, native, installed_version=version)

    def test_unverified_default_custom_special_and_wrong_claude_version_never_get_options(self):
        session = '01a1c848-8ff2-7e90-bcec-44a3ca07a21b'
        cases = [('codex', 'default', None), ('codex', 'Custom (workspace, Ask for approval)', None),
                 ('codex', 'Full Access --fake-flag', None), ('claude', 'default', '2.1.330'),
                 ('claude', 'bypass permissions', '2.1.332'), ('claude', 'plan', '2.1.330')]
        for provider, permission, version in cases:
            text = 'Session ID: '+session+'\ncwd: /work\nPermissions: '+permission+'\n'
            if version:
                text += ('OpenAI Codex (v'+version+')\n' if provider == 'codex' else 'Version: '+version+'\n')
            with self.subTest(provider=provider, permission=permission, version=version):
                native = m.status(provider, text)
                self.assertIsNone(native['resumeMode'])
                with self.assertRaisesRegex(m.Deferred, 'native-resume-permissions-unverified'):
                    m.resume_command(provider, native, installed_version=version)

    def test_refresh_unverified_custom_stops_before_exit(self):
        identity = {'sessionId': '01a1c848-8ff2-7e90-bcec-44a3ca07a21b', 'cwd': '/work',
                    'permissions': 'Custom (workspace, Ask for approval)', 'resumeMode': None}
        with patch.object(m, 'native_status', return_value=identity):
            result = m.apply(self.client, self.plan, self.self_pane, self.temp.name)
        self.assertEqual('native-resume-permissions-unverified', result['stopped'])
        self.assertEqual([], self.client.sent)

    def test_claude_unverified_dependencies_defer_without_input(self):
        self.plan['targets'][0]['provider'] = 'claude'
        result = m.apply(self.client, self.plan, self.self_pane, self.temp.name)
        self.assertEqual('claude-reload-support-and-dependencies-unverified', result['stopped'])
        self.assertEqual([], self.client.sent)

    def test_send_receipt_and_wait_fail_closed(self):
        with m.Journal(self.temp.name, self.plan['operationId']) as journal:
            with patch.object(self.client, 'call', return_value={'send': {'accepted': False}}):
                with self.assertRaises(m.Deferred):
                    m.send(self.client, journal, self.plan['targets'][0], '/status', 'status')
        with patch.object(self.client, 'call', return_value={'wait': {'satisfied': False}}):
            with self.assertRaisesRegex(m.Deferred, 'unsatisfied'):
                m.wait_idle(self.client, self.plan['targets'][0])

    def test_status_requires_fresh_output_before_exit(self):
        with m.Journal(self.temp.name, self.plan['operationId']) as journal:
            with self.assertRaisesRegex(m.Deferred, 'freshness'):
                m.native_status(self.client, self.plan, self.plan['targets'][0], self.self_pane, journal)
        self.assertEqual(1, len(self.client.sent))
        self.assertEqual('/status', self.client.sent[0][self.client.sent[0].index('--text')+1])

    def delayed_codex(self, *, partial=False, change=None):
        client = self.client
        clock = [0.0]
        fields = ['OpenAI Codex (v0.167.2)', 'Session: 01a1c848-8ff2-7e90-bcec-44a3ca07a21b',
                  'Directory: /work', 'Permissions: Full Access']
        original_observe, original_call = client.observe, client.call
        def observe(handle):
            if client.sent:
                if partial or clock[0] >= 0.59:
                    body = fields if clock[0] >= 0.59 else fields[:3]
                    client.read.update(latestCursor='11', tail=['› /status', *body, '›'])
                if change and clock[0] >= 0.1:
                    change(client)
            return original_observe(handle)
        def call(*args):
            if args[:2] == ('terminal', 'read'):
                body = fields if clock[0] >= 0.59 else fields[:3]
                return {'terminal': {'source': 'stream', 'tail': ['› /status', *body, '›']}}
            return original_call(*args)
        client.observe, client.call = observe, call
        return client, clock

    def test_codex_delayed_059_second_and_partial_status_use_one_send_and_no_wait_inventory(self):
        for partial in (False, True):
            with self.subTest(partial=partial):
                self.client = Fake()
                # Unchanged historical ordinary-command output is not a new
                # boundary while acknowledgement precedes rendering.
                self.client.read['tail'] = ['› earlier ordinary command', 'done', '›']
                client, clock = self.delayed_codex(partial=partial)
                self.inventory.reset_mock()
                with patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]), \
                     patch.object(m.time, 'sleep', side_effect=lambda duration: clock.__setitem__(0, clock[0]+duration)):
                    native = m.native_status(client, self.plan, self.plan['targets'][0], self.self_pane, Mock())
                self.assertGreaterEqual(clock[0], 0.59)
                self.assertLess(clock[0], 3)
                self.assertEqual('/work', native['cwd'])
                self.assertEqual(1, len(client.sent))
                self.assertEqual(1, self.inventory.call_count)
                self.assertEqual('11', self.plan['targets'][0]['nativeProof']['cursor'])

    def screen_only_codex(self, before, after, *, stream=None, cursor='10'):
        client = Fake()
        client.read['tail'] = before
        original = client.call
        def call(*args):
            if args[:2] == ('terminal', 'read'):
                return {'terminal': {'source': 'stream', 'tail': []} if stream is None else stream}
            result = original(*args)
            if args[:2] == ('terminal', 'send'):
                client.read.update(tail=after, latestCursor=cursor)
            return result
        client.call = call
        return client

    def run_screen_status(self, client, plan=None):
        clock = [0.0]
        with patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(m.time, 'sleep', side_effect=lambda duration: clock.__setitem__(0, clock[0]+duration)):
            return m.native_status(client, plan or self.plan,
                                   (plan or self.plan)['targets'][0], self.self_pane, Mock())

    def test_codex_screen_append_and_synthetic_cropped_repeat_prove_new_boundary_without_cursor_progress(self):
        before, cropped = codex_screen_pair()
        full = before[:-3] + cropped[7:]
        for after in (cropped, full):
            with self.subTest(cropped=after == cropped):
                client = self.screen_only_codex(before, after)
                self.inventory.reset_mock()
                identity = self.run_screen_status(client)
                self.assertEqual({'sessionId': '11111111-1111-4111-8111-111111111111',
                                  'cwd': '/work', 'permissions': 'Full Access',
                                  'nativeVersion': '0.167.2', 'resumeMode': 'codex-full-access'}, identity)
                self.assertEqual(m.output_proof(client.read), self.plan['targets'][0]['nativeProof'])
                self.assertEqual({'cursor', 'screenSha256'}, set(self.plan['targets'][0]['nativeProof']))
                self.assertEqual(1, self.inventory.call_count)
                self.assertEqual(1, len(client.sent))

    def test_codex_cropped_repeat_pins_unique_first_request_after_startup_ui(self):
        before, after = codex_screen_pair()
        startup = ['  >_ OpenAI Codex (v0.172.0)', '  /work', '  permissions: YOLO mode']
        before = startup + before
        client = self.screen_only_codex(before, after)
        native = self.run_screen_status(client)
        self.assertEqual('11111111-1111-4111-8111-111111111111', native['sessionId'])
        self.assertEqual(m.output_proof(client.read), self.plan['targets'][0]['nativeProof'])
        self.assertEqual(1, len(client.sent))

    def test_codex_pinned_first_request_needs_unique_request_and_session_suffix(self):
        before, after = codex_screen_pair()
        startup = ['  >_ OpenAI Codex (v0.172.0)', '  /work', '  permissions: YOLO mode']
        original = startup + before
        cases = {
            'different-pin': (original, ['› different request', *after[1:]]),
            'duplicate-old-request': (startup + [before[0], *before], after),
            'later-request-as-pin': (startup + ['› first request', *before], after),
            'slash-command-as-pin': (startup + ['› /help', *before[1:]], ['› /help', *after[1:]]),
            'missing-previous-session': (original, [x for i, x in enumerate(after)
                                                   if not (i < 7 and 'Session:' in x)]),
            'changed-retained-suffix': (original, [x+' changed' if i == 2 else x
                                                  for i, x in enumerate(after)]),
            'intervening-command': (original, [*after[:8], '/help', *after[8:]]),
            'same-frame': (after, after),
            'footer-only': (after, [*after[:-1], 'clock changed']),
        }
        for name, (previous, current) in cases.items():
            with self.subTest(name=name):
                client = self.screen_only_codex(previous, current)
                with self.assertRaises(m.Deferred):
                    self.run_screen_status(client)
                self.assertEqual(1, len(client.sent))
                self.assertNotIn('nativeProof', self.plan['targets'][0])

    def popup_pair(self, cwd='/work', displayed_cwd=None):
        before, after = codex_screen_pair(cwd)
        before = [line.replace('v0.167.2', 'v0.172.0') for line in before]
        after = [line.replace('v0.167.2', 'v0.172.0') for line in after]
        before = [line.replace('fixture-line-5', '  Model: GPT-6.2-Sol (reasoning low, summaries auto)') for line in before]
        after = [line.replace('fixture-line-5', '  Model: GPT-6.2-Sol (reasoning low, summaries auto)') for line in after]
        footer = ['  GPT-6.2-Sol default · '+(displayed_cwd or cwd)+' · fixture',
                  '  ← for agents · ? for shortcuts']
        before[-2:] = footer
        after[-2:] = footer
        popup = (' › /status      show current session configuration and token usage '
                 ' /statusline configure which items appear in the status line '
                 '› /status '+footer[0])
        return before, after, popup

    def test_codex_01720_exact_autocomplete_repaint_and_known_footer_is_not_a_command(self):
        for cursor in ('10', '11'):
            for hints in (False, True):
                with self.subTest(cursor=cursor, hints=hints):
                    before, after, popup = self.popup_pair()
                    if hints:
                        popup += ' ← for agents · ? for shortcuts'
                    stream = {'source': 'stream', 'tail': ['', popup, *after[7:-3]]}
                    client = self.screen_only_codex(before, after, stream=stream, cursor=cursor)
                    native = self.run_screen_status(client)
                    self.assertEqual('11111111-1111-4111-8111-111111111111', native['sessionId'])
                    self.assertEqual('0.172.0', native['nativeVersion'])
                    self.assertEqual(1, len(client.sent))
                    self.assertEqual('/status ', client.sent[0][client.sent[0].index('--text')+1])

    def test_status_wire_space_requires_latest_visible_01720_and_keeps_legacy_input(self):
        for version in ('0.167.1', '0.167.2', '0.171.0', '0.172.0'):
            with self.subTest(version=version):
                before, after = codex_screen_pair()
                before = [line.replace('0.167.2', version) for line in before]
                after = [line.replace('0.167.2', version) for line in after]
                # Historical01720 must not override a later supported header.
                before.insert(0, '>_ OpenAI Codex (v0.172.0)')
                client = self.screen_only_codex(before, after)
                self.run_screen_status(client)
                self.assertEqual(['/status ' if version == '0.172.0' else '/status'],
                    [args[args.index('--text')+1] for args in client.sent])
        # An installed172 or fresh172 reply cannot stand in for the pre-send header.
        _, after, _ = self.popup_pair()
        client = self.screen_only_codex(['›'], after,
            stream={'source': 'stream', 'tail': after[7:-3]}, cursor='11')
        self.run_screen_status(client)
        self.assertEqual(['/status'], [args[args.index('--text')+1] for args in client.sent])

    def test_status_wire_space_leaves_other_commands_and_claude_unchanged(self):
        before, _, _ = self.popup_pair()
        client = self.screen_only_codex(before, ['done', '›'],
            stream={'source': 'stream', 'tail': ['done']}, cursor='11')
        m.native_query(client, self.plan, self.plan['targets'][0], self.self_pane,
                       Mock(), '/help', 'help')
        self.assertEqual(['/help'], [args[args.index('--text')+1] for args in client.sent])
        client = ClaudeFake()
        plan = m.inspect(client, self.self_pane)
        m.native_status(client, plan, plan['targets'][1], self.self_pane, Mock())
        self.assertEqual(['/status'], [args[args.index('--text')+1] for args in client.sent])

    def test_status_wire_space_preserves_typed_input_and_draft_refusals(self):
        before, after, _ = self.popup_pair()
        for kind in ('typed-other', 'draft'):
            with self.subTest(kind=kind):
                previous = [*before[:-3], '› do other work', *before[-2:]] if kind == 'typed-other' else before
                client = self.screen_only_codex(previous, after)
                if kind == 'draft':
                    client.read['draft'] = 'unfinished'
                with self.assertRaisesRegex(m.Deferred, '^draft$'):
                    self.run_screen_status(client)
                self.assertEqual([], client.sent)

    def test_status_wire_space_preserves_receipts_and_timeout_single_send(self):
        before, after, _ = self.popup_pair()
        for failure in ('rejected', 'missing-request', 'missing-mutation', 'timeout'):
            with self.subTest(failure=failure):
                client = self.screen_only_codex(before, after)
                original = client.call
                def call(*args):
                    result = original(*args)
                    if args[:2] == ('terminal', 'send'):
                        if failure == 'timeout':
                            raise m.Deferred('cli-unavailable-or-timeout')
                        response = {'send': {'accepted': failure != 'rejected'}}
                        if failure != 'missing-mutation':
                            response['mutation'] = {} if failure == 'missing-request' else {'requestId': 'request'}
                        return response
                    return result
                client.call = call
                expected = ('cli-unavailable-or-timeout' if failure == 'timeout'
                            else 'invalid-json-shape' if failure == 'missing-mutation'
                            else 'send-receipt-unknown')
                with self.assertRaisesRegex(m.Deferred, '^'+expected+'$'):
                    self.run_screen_status(client)
                self.assertEqual(['/status '], [args[args.index('--text')+1] for args in client.sent])
                self.assertNotIn('nativeProof', self.plan['targets'][0])

    def test_codex_01720_popup_footer_uses_receiver_home_abbreviation_only(self):
        home = Path('/receiver/home')
        with patch.object(m.Path, 'home', return_value=home):
            for cwd, shown in ((str(home), '~'), (str(home/'project'), '~/project'),
                               (str(home/'project'), str(home/'project'))):
                with self.subTest(cwd=cwd, shown=shown):
                    before, after, popup = self.popup_pair(cwd, shown)
                    fresh = '\n'.join([popup, *after[7:-3]])
                    response = '\n'.join(after[8:-3])
                    self.assertEqual('\n'.join(after[7:-3]), m.codex_status_stream_text(
                        fresh, '\n'.join(before), '\n'.join(after), response))
            for cwd, shown in (('/receiver/home-other/project', '~/project'),
                               ('/other/project', '~/project'), (str(home), '~/')):
                with self.subTest(cwd=cwd, shown=shown):
                    before, after, popup = self.popup_pair(cwd, shown)
                    fresh = '\n'.join([popup, *after[7:-3]])
                    self.assertEqual(fresh, m.codex_status_stream_text(
                        fresh, '\n'.join(before), '\n'.join(after), '\n'.join(after[8:-3])))

    def test_codex_01720_autocomplete_filter_never_hides_other_commands_or_unknown_ui(self):
        before, after, popup = self.popup_pair()
        cases = {
            'changed-caption': [popup.replace('show current session', 'unknown caption')],
            'changed-menu-command': [popup.replace('/statusline', '/help')],
            'changed-composer': [popup.replace('› /status  ', '› /help  ')],
            'unknown-footer': [popup.replace('fixture', 'other title')],
            'changed-default': [popup.replace('default ·', 'fast ·')],
            'empty-title': [popup.replace('fixture', '')],
            'missing-composer': [popup.replace('› /status   GPT', 'GPT')],
            'actual-help': [popup, '/help'],
            'actual-user-message': [popup, '› do different work'],
            'prefixed-command': ['› /help '+popup],
            'ansi-control': ['\x1b[31m'+popup],
            'duplicate-popup': [popup, popup],
            'later-popup': ['previous output', popup],
            'typed-identical-menu-text': ['› '+popup.strip()],
            'typed-status-with-invalid-arguments': [popup, 'Unknown arguments for /status'],
        }
        for name, prefix in cases.items():
            with self.subTest(name=name):
                client = self.screen_only_codex(before, after,
                    stream={'source': 'stream', 'tail': [*prefix, *after[7:-3]]}, cursor='11')
                with self.assertRaises(m.Deferred):
                    self.run_screen_status(client)
                self.assertEqual(1, len(client.sent))
                self.assertNotIn('nativeProof', self.plan['targets'][0])

    def test_codex_01720_popup_requires_model_cwd_and_known_footer_structure(self):
        before, after, popup = self.popup_pair()
        for old, new in (('GPT-6.2-Sol default · /work', 'GPT-6.2-Sol default · /other'),
                         ('GPT-6.2-Sol default', 'OtherModel default'),
                         ('← for agents · ? for shortcuts', '› unrelated footer command')):
            with self.subTest(changed=new):
                previous = [line.replace(old, new) for line in before]
                current = [line.replace(old, new) for line in after]
                changed_popup = popup.replace(old, new)
                client = self.screen_only_codex(previous, current,
                    stream={'source': 'stream', 'tail': [changed_popup, *current[7:-3]]}, cursor='11')
                with self.assertRaises(m.Deferred):
                    self.run_screen_status(client)

    def test_codex_01720_popup_never_strips_matching_row_from_response_body(self):
        before, after, popup = self.popup_pair()
        response = '\n'.join(after[8:-3])
        for prefix in ('/status\n', 'ordinary output\n'):
            text = prefix+popup+'\n/status\n'+response
            self.assertEqual(text, m.codex_status_stream_text(text, '\n'.join(before),
                                                           '\n'.join(after), response))

    def test_codex_01720_autocomplete_needs_independent_screen_proof_and_supported_version(self):
        before, after, popup = self.popup_pair()
        for version in ('0.167.2', '0.171.0'):
            with self.subTest(version=version):
                old_before = [line.replace('0.172.0', version) for line in before]
                old_after = [line.replace('0.172.0', version) for line in after]
                client = self.screen_only_codex(old_before, old_after,
                    stream={'source': 'stream', 'tail': [popup, *old_after[7:-3]]}, cursor='11')
                with self.assertRaises(m.Deferred):
                    self.run_screen_status(client)
        with self.assertRaises(m.Deferred):
            m.codex_status_stream_text(popup, '\n'.join(before), '\n'.join(after), '')

    def test_codex_01720_popup_cannot_supply_screen_freshness_or_identity(self):
        before, after, popup = self.popup_pair()
        for name, current in {
            'unchanged': before,
            'missing-session': [line for line in after if 'Session:' not in line],
            'wrong-current-cwd': [line.replace('Directory:           /work',
                                               'Directory:           /other') for line in after],
            'wrong-current-uuid': [line.replace('11111111-1111-4111-8111-111111111111',
                '22222222-2222-4222-8222-222222222222') if i > 7 else line
                for i, line in enumerate(after)],
        }.items():
            with self.subTest(name=name):
                client = self.screen_only_codex(before, current,
                    stream={'source': 'stream', 'tail': [popup, *after[7:-3]]}, cursor='10')
                with self.assertRaises(m.Deferred):
                    self.run_screen_status(client)
                self.assertEqual(1, len(client.sent))
                self.assertNotIn('nativeProof', self.plan['targets'][0])

    def test_codex_screen_append_returns_only_new_card_metadata(self):
        before, after = codex_screen_pair()
        after = [line.replace('11111111-1111-4111-8111-111111111111',
                              '22222222-2222-4222-8222-222222222222') if i > 7 else line
                 for i, line in enumerate(after)]
        native = self.run_screen_status(self.screen_only_codex(before, after))
        self.assertEqual('22222222-2222-4222-8222-222222222222', native['sessionId'])

    def test_codex_screen_exposed_card_without_substantial_history_anchor_is_rejected(self):
        _, after = codex_screen_pair()
        for history in ([], [''], [' '], ['/status'], ['› /status'], ['› Ask Codex to do anything']):
            with self.subTest(history=history):
                client = self.screen_only_codex([*history, '›'], [*history, *after[7:]])
                with self.assertRaises(m.Deferred):
                    self.run_screen_status(client)
                self.assertEqual(1, len(client.sent))
                self.assertNotIn('nativeProof', self.plan['targets'][0])
        client = self.screen_only_codex(['›', 'fixture footer'], [*after[7:], 'fixture footer'])
        with self.assertRaises(m.Deferred):
            self.run_screen_status(client)
        self.assertEqual(1, len(client.sent))
        # Complete retained task history anchors the first status without any
        # prior native card; cropping still requires its stronger Session proof.
        history = ['› earlier fixture instruction', 'fixture completed work']
        client = self.screen_only_codex([*history, '›'], [*history, *after[7:]])
        self.assertEqual('11111111-1111-4111-8111-111111111111',
                         self.run_screen_status(client)['sessionId'])
        self.assertEqual(1, len(client.sent))

    def test_codex_screen_identity_rejects_parser_recognizable_malformed_fields_before_partial_fill(self):
        before, after = codex_screen_pair()
        expected = m.codex_screen_identity('\n'.join(after[8:-3]))
        for label, value in (('Session', '22222222-2222-4222-8222-222222222222'),
                             ('cwd', '/other'), ('Permissions', 'default')):
            for malformed in (label+'\n: '+value, label+'\u00a0: '+value,
                              '\u00a0'+label+': '+value, '│\u2003'+label+': '+value,
                              label+'\n:\n'+value):
                with self.subTest(malformed=malformed):
                    with self.assertRaisesRegex(m.Deferred, 'native-response-identity-malformed'):
                        m.codex_screen_identity(malformed, expected=expected)
                    client = self.screen_only_codex(before, after,
                        stream={'source': 'stream', 'tail': [malformed]})
                    with self.assertRaises(m.Deferred):
                        self.run_screen_status(client)
                    self.assertEqual(1, len(client.sent))
                    self.assertNotIn('nativeProof', self.plan['targets'][0])
        for valid in ('', 'Session:\t'+expected['sessionId'],
                      '│ Session ID : '+expected['sessionId']+' │',
                      '\tPermissions:\tFull Access', '    Directory: /work'):
            with self.subTest(valid=valid):
                self.assertEqual(expected, m.codex_screen_identity(valid, expected=expected))

    def test_codex_advanced_stream_cannot_supply_old_identity_after_incomplete_standalone_status(self):
        before, _ = codex_screen_pair()
        partial = before[:-3] + ['/status', *before[-3:]]
        client = self.screen_only_codex(before, partial, cursor='11',
            stream={'source': 'stream', 'tail': before[6:-3]})
        with self.assertRaisesRegex(m.Deferred, 'native-identity-unknown'):
            self.run_screen_status(client)
        self.assertEqual(1, len(client.sent))
        self.assertNotIn('nativeProof', self.plan['targets'][0])
        for command in ('/status', '/help'):
            text = '\n'.join([*before[6:-3], command, '›'])
            if command == '/status':
                self.assertEqual('›', m.current_status_response('codex', text))
            else:
                with self.assertRaisesRegex(m.Deferred, 'native-response-boundary-changed'):
                    m.current_status_response('codex', text)
        # Standalone Codex syntax does not change Claude response handling.
        self.assertEqual('/status\n❯', m.current_status_response('claude', '/status\n❯'))

    def test_codex_screen_stale_repaint_exposed_marker_and_ambiguous_crop_never_prove_freshness(self):
        before, after = codex_screen_pair()
        cases = {
            'unchanged': before,
            'footer-only': before[:-1] + ['clock changed'],
            'old-marker-exposed': before[5:],
            'unanchored-crop': after[3:],
            'history-exposure': [*before[:5], *after[7:]],
            'changed-history': ['› a different instruction', *after[1:]],
            'inserted-command': [*after[:7], '› other command', *after[7:]],
        }
        for label, displayed in cases.items():
            with self.subTest(label=label):
                client = self.screen_only_codex(before, displayed)
                with self.assertRaises(m.Deferred):
                    self.run_screen_status(client)
                self.assertNotIn('nativeProof', self.plan['targets'][0])
                self.assertEqual(1, len(client.sent))
        # Two identical possible old suffix occurrences make the crop ambiguous.
        ambiguous = before[:-3] + before[19:-3] + before[-3:]
        self.assertIsNone(m.codex_screen_status('\n'.join(ambiguous), '\n'.join(after)))
        for displayed in (after, after[:-1] + ['clock changed']):
            with self.subTest(repeated_cropped=True, displayed=displayed[-1]):
                client = self.screen_only_codex(after, displayed)
                with self.assertRaises(m.Deferred):
                    self.run_screen_status(client)
                self.assertEqual(1, len(client.sent))
                self.assertNotIn('nativeProof', self.plan['targets'][0])
        client = self.screen_only_codex(['›', *after[7:-3]], after[7:])
        with self.assertRaises(m.Deferred):
            self.run_screen_status(client)
        self.assertEqual(1, len(client.sent))

    def test_codex_screen_missing_duplicate_and_intervening_response_boundaries_are_rejected(self):
        before, after = codex_screen_pair()
        cases = {
            'missing-header': after[:8] + after[9:],
            'unknown-header': [line.replace('v0.167.2', 'v9.9.9') if i > 7 else line
                               for i, line in enumerate(after)],
            'missing-session': [line for i, line in enumerate(after) if i < 8 or 'Session:' not in line],
            'empty-permission': [line.split(':')[0]+':' if i > 7 and 'Permissions:' in line else line
                                 for i, line in enumerate(after)],
            'duplicate-session': after[:-3] + [after[21]] + after[-3:],
            'duplicate-cwd': after[:-3] + ['cwd: /work'] + after[-3:],
            'duplicate-permission': after[:-3] + ['Permissions: Full Access'] + after[-3:],
            'ordinary-command': after[:-3] + ['› completed ordinary command'] + after[-3:],
            'standalone-command': after[:-3] + ['/help'] + after[-3:],
            'startup': after[:-3] + ['  >_ OpenAI Codex (v0.167.2)'] + after[-3:],
            'resume': after[:-3] + ['To continue this session: codex resume old'] + after[-3:],
        }
        for label, displayed in cases.items():
            with self.subTest(label=label):
                client = self.screen_only_codex(before, displayed)
                with self.assertRaises(m.Deferred):
                    self.run_screen_status(client)
                self.assertEqual(1, len(client.sent))
                self.assertNotIn('nativeProof', self.plan['targets'][0])

    def test_codex_screen_stream_partial_agreement_and_conflicts_never_bypass_stream_rejection(self):
        before, after = codex_screen_pair()
        for tail in ([], ['/status'], ['Session: 11111111-1111-4111-8111-111111111111'],
                     ['Directory: /work', 'Permissions: Full Access'], after[8:-3]):
            with self.subTest(agreeing=tail):
                client = self.screen_only_codex(before, after, stream={'source': 'stream', 'tail': tail})
                self.assertEqual('/work', self.run_screen_status(client)['cwd'])
                self.assertEqual(1, len(client.sent))
        rejected = [
            {'source': 'screen', 'tail': []}, {'source': 'stream', 'tail': [None]},
            {'source': 'stream', 'tail': 'invalid'},
            {'source': 'stream', 'tail': ['\x1b[2J']},
            *[{'source': 'stream', 'tail': tail} for tail in (
                ['Session: 22222222-2222-4222-8222-222222222222'], ['Directory: /other'],
                ['Permissions: default'], ['Session: invalid'], ['cwd: ~/../work'],
                ['Permissions:', 'Session: 11111111-1111-4111-8111-111111111111'],
                ['OpenAI Codex (v9.9.9)'], ['› ordinary command'], ['/help'],
                ['To continue this session, run: codex resume old'],
                ['Claude Code v2.1.330'],
                ['Session: 11111111-1111-4111-8111-111111111111'] * 2,
                ['Session: 22222222-2222-4222-8222-222222222222', *after[8:-3]])]
        ]
        for stream in rejected:
            with self.subTest(rejected=stream):
                client = self.screen_only_codex(before, after, stream=stream)
                with self.assertRaises(m.Deferred):
                    self.run_screen_status(client)
                self.assertEqual(1, len(client.sent))
                self.assertNotIn('nativeProof', self.plan['targets'][0])

    def test_codex_screen_partial_card_waits_passively_without_resending(self):
        before, after = codex_screen_pair()
        client = self.screen_only_codex(before, after)
        original = client.observe
        reads = [0]
        def observe(handle):
            item, frame = original(handle)
            if client.sent:
                reads[0] += 1
                if reads[0] < 4:
                    frame['tail'] = [line for i, line in enumerate(after) if i < 8 or 'Session:' not in line]
            return item, frame
        client.observe = observe
        self.assertEqual('/work', self.run_screen_status(client)['cwd'])
        self.assertGreaterEqual(reads[0], 5)
        self.assertEqual(1, len(client.sent))

    def test_codex_screen_confirmed_original_frame_and_all_passive_guards_remain_required(self):
        before, after = codex_screen_pair()
        changes = {
            'runtime': lambda c: setattr(c, 'runtime', 'other'),
            'identity': lambda c: c.target.update(incarnationId='other'),
            'provider': lambda c: c.target.update(agentIdentity='claude'),
            'self': lambda c: c.self.update(leafId='gone'),
            'busy': lambda c: c.agents[1].update(state='working'),
            'draft': lambda c: c.read.update(draft='typed'),
            'child': lambda c: c.agents[1].update(children=[{'state': 'working'}]),
            'approval': lambda c: c.target.update(agentWait={'state': 'waiting'}),
            'cursor': lambda c: c.read.update(latestCursor='11'),
            'screen': lambda c: c.read['tail'].append('changed footer'),
        }
        for label, change in changes.items():
            with self.subTest(label=label):
                client = self.screen_only_codex(before, after)
                original, count = client.inventory, [0]
                def inventory():
                    if client.sent:
                        count[0] += 1
                        if count[0] == 2:
                            change(client)
                    return original()
                client.inventory = inventory
                with self.assertRaises(m.Deferred):
                    self.run_screen_status(client)
                self.assertEqual(1, len(client.sent))
                self.assertNotIn('nativeProof', self.plan['targets'][0])

    def test_codex_screen_home_path_keeps_strict_receiver_expansion_and_workspace_match(self):
        before, after = codex_screen_pair('~/projects/sandbox/example')
        with patch.object(m.Path, 'home', return_value=Path('/receiver')):
            client = self.screen_only_codex(before, after)
            client.target['worktreePath'] = '/receiver/projects/sandbox/example'
            plan = copy.deepcopy(self.plan)
            plan['targets'][0]['identity'] = m.fingerprint(client.target)
            self.assertEqual(client.target['worktreePath'], self.run_screen_status(client, plan)['cwd'])
            for cwd in ('~/../work', '~/work ', '$HOME/work', '/different'):
                before, after = codex_screen_pair(cwd)
                client = self.screen_only_codex(before, after)
                with self.subTest(cwd=cwd), self.assertRaises(m.Deferred):
                    self.run_screen_status(client)
                self.assertEqual(1, len(client.sent))

    def test_codex_pending_observation_rejects_each_state_and_boundary_drift(self):
        changes = {
            'runtime': lambda c: setattr(c, 'runtime', 'other'),
            'provider': lambda c: c.target.update(agentIdentity='claude'),
            'identity': lambda c: c.target.update(incarnationId='other'),
            'self': lambda c: c.self.update(leafId='gone'),
            'busy': lambda c: c.agents[1].update(state='working'),
            'draft': lambda c: c.read.update(draft='typed'),
            'child': lambda c: c.agents[1].update(children=[{'state': 'working'}]),
            'boundary': lambda c: c.read.update(tail=['› ordinary command', '›']),
        }
        for label, change in changes.items():
            with self.subTest(label=label):
                self.client = Fake()
                client, clock = self.delayed_codex(change=change)
                with patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]), \
                     patch.object(m.time, 'sleep', side_effect=lambda duration: clock.__setitem__(0, clock[0]+duration)):
                    with self.assertRaises(m.Deferred):
                        m.native_status(client, self.plan, self.plan['targets'][0], self.self_pane, Mock())
                self.assertEqual(1, len(client.sent))
                self.assertLess(clock[0], 0.59)

    def test_codex_cursor_progress_with_unchanged_ordinary_screen_waits_for_delayed_status(self):
        self.client.read['tail'] = ['› earlier ordinary command', 'done', '›']
        client, clock = self.delayed_codex(change=lambda c: c.read.update(latestCursor='11'))
        with patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(m.time, 'sleep', side_effect=lambda duration: clock.__setitem__(0, clock[0]+duration)):
            native = m.native_status(client, self.plan, self.plan['targets'][0], self.self_pane, Mock())
        self.assertGreaterEqual(clock[0], 0.59)
        self.assertEqual('/work', native['cwd'])
        self.assertEqual(1, len(client.sent))
        self.assertEqual('11', self.plan['targets'][0]['nativeProof']['cursor'])

    def test_codex_pending_deadline_never_resends_or_reuses_old_status(self):
        client, clock = self.delayed_codex()
        client.observe = Fake.observe.__get__(client)
        with patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(m.time, 'sleep', side_effect=lambda duration: clock.__setitem__(0, clock[0]+duration)):
            with self.assertRaisesRegex(m.Deferred, 'freshness'):
                m.native_status(client, self.plan, self.plan['targets'][0], self.self_pane, Mock())
        self.assertEqual(1, len(client.sent))
        self.assertLessEqual(clock[0], 3)

    def test_codex_delayed_complete_response_requires_same_confirmed_frame_proof(self):
        client, clock = self.delayed_codex()
        original = client.observe
        complete_reads = [0]
        def observe(handle):
            item, frame = original(handle)
            if clock[0] >= 0.59:
                complete_reads[0] += 1
                if complete_reads[0] > 1:
                    frame['tail'].append('later output')
            return item, frame
        client.observe = observe
        with patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(m.time, 'sleep', side_effect=lambda duration: clock.__setitem__(0, clock[0]+duration)):
            with self.assertRaisesRegex(m.Deferred, 'native-response-proof-changed'):
                m.native_status(client, self.plan, self.plan['targets'][0], self.self_pane, Mock())
        self.assertEqual(1, len(client.sent))

    def test_codex_slow_observation_within_fifteen_seconds_preserves_single_send_and_proof(self):
        for elapsed in (3.1, 14.9):
            with self.subTest(elapsed=elapsed):
                self.client = Fake()
                client, clock = self.delayed_codex()
                original = client.observe
                def observe(handle):
                    if client.sent:
                        clock[0] = elapsed
                    return original(handle)
                client.observe = observe
                with patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]):
                    native = m.native_status(client, self.plan, self.plan['targets'][0], self.self_pane, Mock())
                self.assertEqual('/work', native['cwd'])
                self.assertEqual(1, len(client.sent))
                self.assertEqual(m.output_proof(client.read), self.plan['targets'][0]['nativeProof'])

    def test_codex_slow_observation_still_rejects_state_drift_before_fifteen_seconds(self):
        for change in ('draft', 'runtime', 'proof'):
            with self.subTest(change=change):
                self.client = Fake()
                client, clock = self.delayed_codex()
                original, observations = client.observe, [0]
                def observe(handle):
                    if client.sent:
                        clock[0] = 3.1
                        observations[0] += 1
                        if change == 'draft':
                            client.read['draft'] = 'typed'
                        elif change == 'runtime':
                            client.runtime = 'other'
                    item, frame = original(handle)
                    if change == 'proof' and observations[0] > 1:
                        frame['tail'].append('changed footer')
                    return item, frame
                client.observe = observe
                with patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]):
                    with self.assertRaises(m.Deferred):
                        m.native_status(client, self.plan, self.plan['targets'][0], self.self_pane, Mock())
                self.assertEqual(1, len(client.sent))

    def test_codex_response_after_observation_deadline_is_not_accepted(self):
        client, clock = self.delayed_codex()
        original = client.observe
        def observe(handle):
            if client.sent:
                clock[0] = 15.1
            return original(handle)
        client.observe = observe
        with patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]):
            with self.assertRaisesRegex(m.Deferred, 'native-response-deadline'):
                m.native_status(client, self.plan, self.plan['targets'][0], self.self_pane, Mock())
        self.assertEqual(1, len(client.sent))

    def test_receiver_home_cwd_strict_normalization_and_exact_workspace(self):
        with patch.object(m.Path, 'home', return_value=Path('/receiver')):
            self.assertEqual('/receiver', m.receiver_cwd('~'))
            self.assertEqual('/receiver/projects/local/general', m.receiver_cwd('~/projects/local/general'))
            for value in ('~user/work', '$HOME/work', 'relative', '~/../work', '~/./work',
                          '~//work', '~/work/', '~/$(pwd)', '~/work\\other', '~/a/~', '~/ work', '~/work '):
                with self.subTest(value=value), self.assertRaises(m.Deferred):
                    m.receiver_cwd(value)
            client, clock = self.delayed_codex()
            real_status = m.status
            def home_status(provider, text):
                return real_status(provider, text.replace('Directory: /work', 'Directory: ~/work'))
            with patch.object(m, 'status', side_effect=home_status), \
                 patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]), \
                 patch.object(m.time, 'sleep', side_effect=lambda duration: clock.__setitem__(0, clock[0]+duration)):
                with self.assertRaisesRegex(m.Deferred, 'cwd-mismatch'):
                    m.native_status(client, self.plan, self.plan['targets'][0], self.self_pane, Mock())
            self.client = Fake()
            self.client.target['worktreePath'] = '/receiver/work'
            matching_plan = copy.deepcopy(self.plan)
            matching_plan['targets'][0]['identity'] = m.fingerprint(self.client.target)
            client, clock = self.delayed_codex()
            with patch.object(m, 'status', side_effect=home_status), \
                 patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]), \
                 patch.object(m.time, 'sleep', side_effect=lambda duration: clock.__setitem__(0, clock[0]+duration)):
                native = m.native_status(client, matching_plan, matching_plan['targets'][0], self.self_pane, Mock())
            self.assertEqual('/receiver/work', native['cwd'])

    def test_status_preserves_ambiguous_home_whitespace_and_valid_field_alignment(self):
        def text(directory):
            return ('OpenAI Codex (v0.167.2)\nSession: 01a1c848-8ff2-7e90-bcec-44a3ca07a21b\n'
                    + directory + '\nPermissions: Full Access\n›')
        with patch.object(m.Path, 'home', return_value=Path('/receiver')):
            for value in ('~/work ', '~/work\t', '~ ', '~/ work', '~/work\u00a0'):
                with self.subTest(value=value), self.assertRaises(m.Deferred):
                    m.status('codex', text('    Directory:  '+value))
            for directory, expected in (
                    ('    Directory:       ~/work', '/receiver/work'),
                    ('│ Directory: ~/work│', '/receiver/work'),
                    ('    Directory:       ~', '/receiver'),
                    ('│ Directory: /work        │', '/work'),
                    ('    Directory: /work   ', '/work')):
                with self.subTest(directory=directory):
                    self.assertEqual(expected, m.status('codex', text(directory))['cwd'])

    def status_with_old_screen(self, fresh):
        client = Fake()
        client.read['tail'] = ['Session: 11111111-1111-4111-8111-111111111111',
                               'Directory: /work', 'Permissions: old', '›']
        original_call = client.call
        def call(*args):
            if args[:2] == ('terminal', 'read'):
                return {'terminal': {'source': 'stream', 'tail': fresh}}
            result = original_call(*args)
            if args[:2] == ('terminal', 'send'):
                # Only the command echo advances output; the screen stays stale.
                client.read['latestCursor'] = str(int(client.read['latestCursor'])+1)
            return result
        client.call = call
        return client

    def test_echo_or_incomplete_fresh_status_never_uses_old_screen_or_exits(self):
        for fresh in (['/status'], ['Session: 01a1c848-8ff2-7e90-bcec-44a3ca07a21b', 'Directory: /work']):
            with self.subTest(fresh=fresh), tempfile.TemporaryDirectory() as folder:
                client = self.status_with_old_screen(fresh)
                result = m.apply(client, self.plan, self.self_pane, folder)
                self.assertEqual('native-identity-unknown', result['stopped'])
                self.assertEqual(['/status'], [a[a.index('--text')+1] for a in client.sent])
                self.assertEqual([], result['results'])

    def test_complete_stream_status_disagreeing_with_current_screen_is_unverified(self):
        client = self.status_with_old_screen([
            'Session: 01a1c848-8ff2-7e90-bcec-44a3ca07a21b', 'Directory: /work', 'Permissions: fresh'])
        with m.Journal(self.temp.name, self.plan['operationId']) as journal:
            with self.assertRaisesRegex(m.Deferred, 'native-response-identity-changed'):
                m.native_status(client, self.plan, self.plan['targets'][0], self.self_pane, journal)
        self.assertEqual(['/status'], [args[args.index('--text')+1] for args in client.sent])

    def test_status_boundary_rejects_historical_fields_after_completed_ordinary_prompt(self):
        for provider, prompt in (('codex', '›'), ('claude', '❯')):
            fields = ['Session ID: 01a1c848-8ff2-7e90-bcec-44a3ca07a21b',
                      'cwd: /work', 'Permissions: Full Access', 'Version: 2.1.330']
            for question in ('say hello', 'Ask Codex to do anything else'):
                with self.subTest(provider=provider, question=question):
                    text = '\n'.join(fields + [prompt+' '+question, 'Completed answer', prompt])
                    with self.assertRaisesRegex(m.Deferred, 'native-response-boundary-changed'):
                        m.current_status_response(provider, text)

    def test_status_boundary_keeps_known_codex_placeholder_and_subsequent_status(self):
        fields = ['Session ID: 01a1c848-8ff2-7e90-bcec-44a3ca07a21b',
                  'cwd: /work', 'Permissions: Full Access', 'Version: 2.1.330']
        text = '\n'.join(fields + ['› Ask Codex to do anything'])
        self.assertEqual(text, m.current_status_response('codex', text))
        for provider, prompt in (('codex', '›'), ('claude', '❯')):
            with self.subTest(provider=provider):
                fresh = [line.replace('01a1c848-8ff2-7e90-bcec-44a3ca07a21b',
                                      '11111111-1111-4111-8111-111111111111') for line in fields]
                text = '\n'.join(fields + [prompt+' say hello', 'Completed answer', prompt,
                                          prompt+' /status'] + fresh + [prompt])
                self.assertEqual('\n'.join(fresh+[prompt]), m.current_status_response(provider, text))

    def test_final_journal_fsync_failure_preserves_completed_targets(self):
        second = copy.deepcopy(self.plan['targets'][0])
        second['handle'] = second['identity']['handle'] = 'term_second'
        self.plan['targets'].append(second)
        completed = [{'handle': 'term_target', 'refresh': 'done'}, {'handle': 'term_second', 'refresh': 'done'}]
        original_record = m.Journal.record
        def record(journal, phase, **values):
            if phase == 'finished':
                with patch.object(m.os, 'fsync', side_effect=OSError('SECRET fsync failure')):
                    return original_record(journal, phase, **values)
            return original_record(journal, phase, **values)
        with patch.object(m, 'refresh', side_effect=completed) as refresh, patch.object(m.Journal, 'record', record):
            result = m.apply(self.client, self.plan, self.self_pane, self.temp.name)
        self.assertEqual(completed, result['results'])
        self.assertEqual([], result['remaining'])
        self.assertEqual('journal-or-local-io-failed', result['stopped'])
        self.assertEqual('term_second', result['recovery']['handle'])
        self.assertEqual('final-journal-record', result['recovery']['phase'])
        self.assertEqual(second['identity'], result['recovery']['identity'])
        self.assertEqual(2, refresh.call_count)
        self.assertEqual([], self.client.sent)
        self.assertNotIn('SECRET', json.dumps(result))

    def test_final_journal_replacement_preserves_results_and_victim(self):
        victim = Path(self.temp.name) / 'victim'; victim.write_text('keep')
        original_record = m.Journal.record
        def record(journal, phase, **values):
            if phase == 'finished':
                journal.path.unlink(); journal.path.symlink_to(victim)
            return original_record(journal, phase, **values)
        completed = {'handle': 'term_target', 'refresh': 'done'}
        with patch.object(m, 'refresh', return_value=completed) as refresh, patch.object(m.Journal, 'record', record):
            result = m.apply(self.client, self.plan, self.self_pane, self.temp.name)
        self.assertEqual([completed], result['results'])
        self.assertEqual([], result['remaining'])
        self.assertEqual('journal-record-replaced', result['stopped'])
        self.assertEqual('final-journal-record', result['recovery']['phase'])
        self.assertEqual('keep', victim.read_text())
        refresh.assert_called_once()
        self.assertEqual([], self.client.sent)

    def test_observed_codex_01672_placeholder_and_typed_same_text(self):
        idle = {'source': 'screen', 'tail': ['>_ OpenAI Codex (v0.167.2)', '› Ask Codex to do anything'], 'draft': None}
        self.assertIn('v0.167.2', m.idle_screen('codex', idle))
        for tail in (['>_ OpenAI Codex (v0.167.2)', '›'], idle['tail']):
            with self.subTest(tail=tail):
                typed = dict(idle, tail=tail, draft='Ask Codex to do anything')
                with self.assertRaisesRegex(m.Deferred, '^draft$'):
                    m.idle_screen('codex', typed)
        restored = dict(idle, draft=None)
        self.assertIn('v0.167.2', m.idle_screen('codex', restored))
        unknown = dict(idle, tail=['>_ OpenAI Codex (v0.167.3)', '› Ask Codex to do anything'])
        with self.assertRaisesRegex(m.Deferred, '^draft$'):
            m.idle_screen('codex', unknown)

    def test_observed_codex_01710_placeholder_contract_and_unknown_patch(self):
        header = ['  >_ OpenAI Codex (v0.171.0)', '  >_ OpenAI Codex (v0.171.0)']
        for stage, draft, prompt in [('before', None, '› Ask Codex to do anything'),
                                      ('typed', 'Ask Codex to do anything', '›'),
                                      ('cleared', None, '› Ask Codex to do anything')]:
            with self.subTest(stage=stage):
                frame = {'source': 'screen', 'tail': header + [prompt], 'draft': draft}
                if draft:
                    with self.assertRaisesRegex(m.Deferred, '^draft$'):
                        m.idle_screen('codex', frame)
                else:
                    self.assertIn('v0.171.0', m.idle_screen('codex', frame))
        typed_same_screen = {'source': 'screen', 'tail': header + ['› Ask Codex to do anything'],
                             'draft': 'Ask Codex to do anything'}
        with self.assertRaisesRegex(m.Deferred, '^draft$'):
            m.idle_screen('codex', typed_same_screen)
        with self.assertRaisesRegex(m.Deferred, '^draft$'):
            m.idle_screen('codex', {'source': 'screen', 'tail': ['OpenAI Codex (v0.171.1)', '› Ask Codex to do anything']})

    def test_observed_headerless_placeholder_allows_readonly_but_never_typed_text_or_unknown_header(self):
        empty = {'source': 'screen', 'tail': ['› Ask Codex to do anything']}
        m.idle_screen('codex', empty)
        for typed in (dict(empty, draft='Ask Codex to do anything'),
                      {'source': 'screen', 'tail': ['›'], 'draft': 'Ask Codex to do anything'}):
            with self.assertRaisesRegex(m.Deferred, '^draft$'):
                m.idle_screen('codex', typed)
        m.idle_screen('codex', empty)
        for header in ('OpenAI Codex (v0.172.1)', 'OpenAI Codex (v0.173.0)', 'OpenAI Codex (vunknown)', 'OpenAI Codex (v'):
            for prompt in ('›', '› Ask Codex to do anything'):
                with self.subTest(header=header, prompt=prompt):
                    with self.assertRaisesRegex(m.Deferred, '^draft$'):
                        m.idle_screen('codex', {'source': 'screen', 'tail': [header, prompt]})

    def test_codex_fresh_status_version_gates_resume_independently_of_placeholder(self):
        fields = 'Session ID: 01a1c848-8ff2-7e90-bcec-44a3ca07a21b\ncwd: /work\nPermissions: Full Access\n'
        for version in ('0.167.1', '0.167.2', '0.171.0', '0.172.0', '0.172.1', '0.173.0', None):
            text = ('>_ OpenAI Codex (v'+version+')\n' if version else '') + fields
            native = m.status('codex', text)
            self.assertEqual(version, native['nativeVersion'])
            if version in ('0.167.1', '0.167.2', '0.171.0', '0.172.0'):
                self.assertEqual('codex-full-access', native['resumeMode'])
            else:
                self.assertIsNone(native['resumeMode'])
                with self.assertRaises(m.Deferred):
                    m.resume_command('codex', native, installed_version='0.171.0')
        known = m.status('codex', 'OpenAI Codex (v0.171.0)\n'+fields)
        with self.assertRaisesRegex(m.Deferred, 'native-resume-version-unverified'):
            m.resume_command('codex', known, installed_version='0.173.0')

    def test_codex_01720_placeholder_draft_and_permission_boundaries(self):
        header = '>_ OpenAI Codex (v0.172.0)'
        frame = {'source': 'screen', 'tail': [header, '› Ask Codex to do anything'], 'draft': None}
        self.assertIn(header, m.idle_screen('codex', frame))
        with self.assertRaisesRegex(m.Deferred, '^draft$'):
            m.idle_screen('codex', dict(frame, draft='Ask Codex to do anything'))
        fields = 'Session ID: 01a1c848-8ff2-7e90-bcec-44a3ca07a21b\ncwd: /work\nPermissions: '
        for permission in ('Full Access', 'default', 'Custom'):
            with self.subTest(permission=permission):
                native = m.status('codex', header+'\n'+fields+permission)
                if permission == 'Full Access':
                    self.assertEqual(shlex.join(['codex', 'resume', native['sessionId'], '--dangerously-bypass-approvals-and-sandbox', '--no-alt-screen', 'Reply only TR_KIT_RESTART_READY. Do not use tools or perform any other action.']),
                                     m.resume_command('codex', native, installed_version='0.172.0'))
                else:
                    with self.assertRaisesRegex(m.Deferred, 'native-resume-permissions-unverified'):
                        m.resume_command('codex', native, installed_version='0.172.0')

    def test_real_codex_omitted_roster_and_placeholder(self):
        self.client.agents[1].pop('children')
        self.client.agents[1].pop('subagentObservation')
        self.client.agents[1].update(state='done', mainAgent={'state': 'done'})
        self.client.read['tail'] = ['>_ OpenAI Codex (v0.167.1)', '› Ask Codex to do anything']
        self.assertEqual('idle', m.inspect(self.client, self.self_pane)['targets'][1]['state'])
        self.client.read['draft'] = 'Ask Codex to do anything'
        self.assertEqual('draft', m.inspect(self.client, self.self_pane)['targets'][1]['reason'])

    def test_cli_selection_once_no_fallback(self):
        with patch.dict(os.environ, {'ORCA_CLI_COMMAND': '/custom/orca'}):
            client = m.Orca()
        response = json.dumps({'ok': True, 'result': {}, '_meta': {'runtimeId': 'r'}})
        with patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, response, '')) as run:
            client.call('terminal', 'list')
        self.assertEqual('/custom/orca', run.call_args.args[0][0])

    def test_unknown_journal_blocks_new_operation(self):
        self.client.fail = 'timeout'
        m.apply(self.client, self.plan, self.self_pane, self.temp.name)
        other = copy.deepcopy(self.plan)
        other['operationId'] = '11111111-1111-4111-8111-111111111111'
        with self.assertRaisesRegex(m.Deferred, 'unresolved-operation'):
            m.apply(self.client, other, self.self_pane, self.temp.name)
        self.assertEqual(1, len(self.client.sent))

    def test_hostile_handle_is_rejected_before_cli(self):
        self.plan['targets'][0]['identity']['handle'] = '--interrupt'
        with self.assertRaises(m.Deferred):
            m.apply(self.client, self.plan, self.self_pane, self.temp.name)
        self.assertEqual([], self.client.sent)

    def test_latest_native_status_wins_over_scrollback(self):
        text = 'Session: 01a1c848-8ff2-7e90-bcec-44a3ca07a21b\nDirectory: /work\nPermissions: old\n'
        self.assertEqual('new', m.status('codex', text + text.replace('old', 'new'))['permissions'])

    def test_resumed_hook_handshake_only_retries_read_only_guard(self):
        identity = {'sessionId': '01a1c848-8ff2-7e90-bcec-44a3ca07a21b', 'cwd': '/work', 'permissions': 'Full Access', 'resumeMode': 'codex-full-access', 'nativeVersion': '0.171.0'}
        with patch.object(m, 'native_status', return_value=identity), patch.object(m, 'shell_guard'), \
             patch.object(m, 'guard', side_effect=[(None, {'latestCursor': '10'}), m.Deferred('agent-identity-unknown'), None]), \
             patch.object(m.time, 'sleep'):
            result = m.apply(self.client, self.plan, self.self_pane, self.temp.name)
        self.assertEqual([], result['remaining'])
        self.assertEqual(2, len(self.client.sent))

    def test_resumed_readiness_transient_child_state_requires_full_guard_before_return(self):
        calls = []
        def readiness(*args, **kwargs):
            self.assertEqual([], self.client.sent)
            calls.append(True)
            if len(calls) == 1:
                raise m.Deferred('child-state-unknown')
        with patch.object(m, 'guard', side_effect=readiness), patch.object(m.time, 'sleep') as sleep:
            m.wait_resumed(self.client, self.plan, self.plan['targets'][0], self.self_pane)
        self.assertEqual(2, len(calls))
        sleep.assert_called_once_with(0.2)
        self.assertEqual([], self.client.sent)

    def test_resumed_readiness_persistent_child_unknown_stops_at_deadline_without_input(self):
        with patch.object(m, 'guard', side_effect=m.Deferred('child-state-unknown')) as guard, \
             patch.object(m.time, 'monotonic', side_effect=[0, 0, 10]), patch.object(m.time, 'sleep') as sleep:
            with self.assertRaisesRegex(m.Deferred, '^child-state-unknown$'):
                m.wait_resumed(self.client, self.plan, self.plan['targets'][0], self.self_pane)
        self.assertEqual(2, guard.call_count)
        sleep.assert_called_once_with(0.2)
        self.assertEqual([], self.client.sent)

    def test_resumed_readiness_never_retries_other_safety_guards(self):
        for reason in ('child-work', 'busy-or-state-unknown', 'approval-or-wait', 'approval-or-menu', 'draft'):
            with self.subTest(reason=reason), patch.object(m, 'guard', side_effect=m.Deferred(reason)) as guard, \
                 patch.object(m.time, 'sleep') as sleep:
                with self.assertRaisesRegex(m.Deferred, '^'+reason+'$'):
                    m.wait_resumed(self.client, self.plan, self.plan['targets'][0], self.self_pane)
                guard.assert_called_once()
                sleep.assert_not_called()
        self.assertEqual([], self.client.sent)

    def claude_plan(self):
        self.installation = dict(self.installation, nativeVersion='2.1.289', dependenciesReady=True)
        self.inventory.return_value = self.installation
        client = ClaudeFake()
        plan = m.make_plan(m.inspect(client, self.self_pane), ['term_target'])
        return client, plan

    def test_claude_native_reload_positive_contract(self):
        client, plan = self.claude_plan()
        result = m.apply(client, plan, self.self_pane, self.temp.name)
        self.assertEqual([], result['remaining'])
        row = result['results'][0]
        self.assertEqual('native-reload-observed', row['refresh'])
        self.assertEqual('unverified', row['consumption'])
        self.assertEqual({'example@market:user': '1.0.0'}, row['installedVersion'])
        commands = [a[a.index('--text')+1] for a in client.sent]
        self.assertEqual(['/status', '/help', '/plugin list --enabled', '/reload-plugins', '/status'], commands)

    def test_claude_stale_listing_is_diagnostic_and_reloads(self):
        self.installation['plugins'][0]['version'] = '2.0.0'
        for body in ('example@market 1.0.0 user enabled',
                     '  ⎿  Installed plugins:\n  • example@market (v1.0.0, user) ✔ enabled\n────',
                     '  ⎿  Installed plugins:\n  • example@market (v1.0.0, user) ✔ enabled\n'+' '*100+'◐ medium · /effort\n────',
                     '  ⎿  Installed plugins:\n  • example@market (v1.0.0, user) ✔ enabled\n'+' '*58+'Scroll wheel is sending arrow keys · use PgUp/PgDn to scroll\n────'):
            client, plan = self.claude_plan()
            client.responses['/plugin list --enabled'] = [body]
            with tempfile.TemporaryDirectory() as directory:
                result = m.apply(client, plan, self.self_pane, directory)
                self.assertEqual([], result['remaining'], result)
                row = result['results'][0]
                self.assertEqual({'example@market:user':'1.0.0'}, row['runtimeListedVersionsBefore'])
                self.assertEqual({'example@market:user':'2.0.0'}, row['installedVersion'])
                self.assertFalse(row['runtimeListingMatchesInstalledBefore'])
                self.assertIsNone(row['consumedVersion'])
                self.assertEqual('unverified', row['consumption'])
                events=json.loads((Path(directory)/(plan['operationId']+'.json')).read_text())['events']
                self.assertTrue(any(e.get('phase')=='runtime-listing-before' and e['matchesInstalled'] is False for e in events))

    def test_claude_invalid_runtime_listing_never_reloads(self):
        good='example@market (v1.0.0, user) ✔ enabled'
        for body in ('', 'No plugins installed.', good+'\n'+good,
                     good+'\nother@market (v1.0.0, user) ✔ enabled',
                     good.replace('user','project'), good.replace('enabled','disabled'),
                     good.replace('✔ enabled',''), good.replace('1.0.0','unknown'),
                     good.replace('1.0.0','^1.0.0'), good.replace('(v1.0.0, user)','(user)'),
                     good.replace('1.0.0','1.0.0-..'), good.replace('1.0.0','1.0.0+_'),
                     good.replace('1.0.0','1.0.0-01'), good.replace('1.0.0','01.0.0'),
                     good+'\n  ◐ medium · /effort',
                     good+'\n────\n  ◐ medium · /effort',
                     '  ◐ medium · /effort\n────\n'+good,
                     good+'\n  ◐ medium · /effort\n────\n  ◐ medium · /effort\n────',
                     good+'\n────\n  ◐ medium · /effort extra',
                     good+'\n────\n  ◐ unknown · /effort',
                     good+'\n  Scroll wheel is sending arrow keys · use PgUp/PgDn to scroll extra\n────',
                     good+'\n  Scroll wheel is sending arrow keys · use PgUp/PgDn to scroll',
                     good+'\n• another (v1.0.0, user) ✔ enabled'):
            client,plan=self.claude_plan()
            client.responses['/plugin list --enabled']=body.splitlines()
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                result=m.apply(client,plan,self.self_pane,directory)
                self.assertTrue(result.get('stopped'),result)
                self.assertFalse(any(a[a.index('--text')+1]=='/reload-plugins' for a in client.sent))
        ambiguous=dict(self.installation,plugins=[self.installation['plugins'][0],dict(self.installation['plugins'][0],scope='project')])
        with self.assertRaisesRegex(m.Deferred,'ambiguous'):
            m.claude_plugin_listing(good,ambiguous)

    def test_claude_331_on_listing_requires_actual_observed_actor_version(self):
        good = '• example@market (v1.0.0, user) ✔ on'
        expected = {'example@market:user': '1.0.0'}
        self.assertEqual(expected, m.claude_plugin_listing(good, self.installation, '2.1.331'))
        for version in (None, '', '2.1.329', '2.1.330', '2.1.332'):
            with self.subTest(version=version), self.assertRaises(m.Deferred):
                m.claude_plugin_listing(good, {**self.installation, 'nativeVersion': '2.1.331'}, version)
        for bad in (good.replace('on', 'off'), good.replace('on', 'unknown'), good+'\n'+good,
                    good.replace('user', 'project'), good.replace('1.0.0', 'unknown'),
                    good.replace('✔ on', 'on'), good.replace('✔ on', '✔on'), ''):
            with self.subTest(bad=bad), self.assertRaises(m.Deferred):
                m.claude_plugin_listing(bad, self.installation, '2.1.331')
        self.assertEqual([], self.client.sent)

    def test_claude_331_real_caller_passes_fresh_actor_version_and_keeps_stale_diagnostic(self):
        client, plan = self.claude_plan()
        self.installation.update(nativeVersion='2.1.331')
        client.responses['/status'] = ['Session ID: 11111111-1111-4111-8111-111111111111',
                                       'cwd: /work', 'Permissions: default', 'Version: 2.1.331']
        client.responses['/plugin list --enabled'] = ['example@market (v0.9.0, user) ✔ on']
        with tempfile.TemporaryDirectory() as directory:
            result = m.apply(client, plan, self.self_pane, directory)
        self.assertEqual([], result['remaining'], result)
        self.assertFalse(result['results'][0]['runtimeListingMatchesInstalledBefore'])
        self.assertEqual({'example@market:user': '0.9.0'}, result['results'][0]['runtimeListedVersionsBefore'])

    def test_claude_partial_listing_reads_until_complete_without_sending(self):
        client,plan=self.claude_plan();target=plan['targets'][0]
        heading=['❯ /plugin list --enabled','  ⎿  Installed plugins:','────','❯']
        complete=heading[:2]+['• example@market (v1.0.0, user) ✔ enabled']+heading[2:]
        frame=lambda rows:{'source':'screen','tail':rows,'latestCursor':'6'}
        validate=lambda text:m.claude_plugin_listing(text,self.installation)
        args=(client,plan,target,self.self_pane,'/plugin list --enabled',frame(heading),'────',validate,'claude-runtime-plugin-list-unknown')
        frames=[(client.target,frame(rows)) for rows in (heading,complete)]
        with patch.object(m,'passive_guard',side_effect=frames) as guard,patch.object(m.time,'sleep'):
            _,text=m.claude_complete_response(*args)
        self.assertEqual({'example@market:user':'1.0.0'},validate(text))
        self.assertEqual(2,guard.call_count)
        self.assertEqual([],client.sent)
        for changed in (frame(heading+['❯ /status','❯']),frame(heading+complete),dict(frame(complete),latestCursor='7')):
            with patch.object(m,'passive_guard',return_value=(client.target,changed)),patch.object(m.time,'sleep'):
                with self.assertRaisesRegex(m.Deferred,'boundary-changed'):
                    m.claude_complete_response(*args)

    def test_claude_partial_stream_never_reuses_past_screen_listing(self):
        client,plan=self.claude_plan();target=plan['targets'][0]
        client.responses['/plugin list --enabled']=['Installed plugins:']
        old=['❯ /plugin list --enabled','example@market (v1.0.0, user) ✔ enabled','❯']
        client.read['tail']=old
        original_call=client.call
        def call(*args):
            result=original_call(*args)
            if args[:2]==('terminal','send'):client.read['tail']=old
            return result
        client.call=call
        with patch.object(m,'claude_complete_response') as completion:
            with self.assertRaisesRegex(m.Deferred,'plugin-list-unknown'):
                m.native_query(client,plan,target,self.self_pane,Mock(),'/plugin list --enabled','plugin-preflight',
                    completion=(lambda text:m.claude_plugin_listing(text,self.installation),'claude-runtime-plugin-list-unknown'))
            completion.assert_not_called()

    def test_claude_waits_for_new_screen_echo_after_incomplete_stream(self):
        client,plan=self.claude_plan();target=plan['targets'][0]
        client.responses['/plugin list --enabled']=['Installed plugins:']
        before={'source':'screen','tail':['❯'],'latestCursor':'10'}
        early=dict(before,latestCursor='11')
        ready=dict(early,tail=['❯ /plugin list --enabled','• example@market (v1.0.0, user) ✔ enabled','❯'])
        frames=[(client.target,frame) for frame in (early,ready)]
        with patch.object(m,'guard',return_value=(client.target,before)), \
             patch.object(m,'passive_guard',side_effect=frames) as guard,patch.object(m.time,'sleep'):
            _,text=m.native_query(client,plan,target,self.self_pane,Mock(),'/plugin list --enabled','plugin-preflight',
                completion=(lambda text:m.claude_plugin_listing(text,self.installation),'claude-runtime-plugin-list-unknown'))
        self.assertEqual({'example@market:user':'1.0.0'},m.claude_plugin_listing(text,self.installation))
        self.assertEqual(2,guard.call_count)
        self.assertEqual(1,len(client.sent))

    def test_claude_partial_reload_waits_for_summary_without_resending(self):
        client,plan=self.claude_plan();target=plan['targets'][0]
        initial={'source':'screen','tail':['❯ /reload-plugins','────','❯'],'latestCursor':'6'}
        complete=dict(initial,tail=['❯ /reload-plugins',*client.responses['/reload-plugins'],'────','❯'])
        with patch.object(m,'passive_guard',return_value=(client.target,complete)),patch.object(m.time,'sleep'):
            _,text=m.claude_complete_response(client,plan,target,self.self_pane,'/reload-plugins',initial,'────',
                lambda text:m.claude_reload_summary(text,self.installation),'claude-reload-completion-unknown')
        self.assertEqual(1,m.claude_reload_summary(text,self.installation)['plugins'])
        self.assertEqual([],client.sent)

    def test_claude_positive_contract_with_omitted_empty_roster(self):
        client, _ = self.claude_plan()
        client.agents[1].pop('children')
        client.agents[1].pop('subagentObservation')
        client.agents[1].update(state='done', mainAgent={'state': 'done'}, programStatus={'state': 'done'})
        report = m.inspect(client, self.self_pane)
        plan = m.make_plan(report, ['term_target'])
        result = m.apply(client, plan, self.self_pane, self.temp.name)
        self.assertEqual([], result['remaining'])
        client.agents[1]['subagentObservation'] = 'unverifiable'
        self.assertEqual('child-state-unknown', m.inspect(client, self.self_pane)['targets'][1]['reason'])

    def test_claude_null_and_missing_program_require_idle_completion_matrix(self):
        for missing in (False,True):
            client=ClaudeModalFake()
            if missing:client.agents[1].pop('programStatus')
            report=m.inspect(client,self.self_pane)
            self.assertEqual('idle',report['targets'][1]['state'])
            for change in (lambda c:c.agents[1].update(state='working'),
                           lambda c:c.agents[1].update(mainAgent={'state':'idle'}),
                           lambda c:c.agents[1].update(subagentObservation='unverifiable'),
                           lambda c:c.agents[1].update(children=[{'state':'working'}]),
                           lambda c:c.read.update(tail=['❯ draft']),
                           lambda c:c.target.update(agentWait={'state':'waiting'})):
                other=ClaudeModalFake(); change(other)
                self.assertEqual('deferred',m.inspect(other,self.self_pane)['targets'][1]['state'])
                self.assertEqual([],other.sent)
        client=ClaudeModalFake()
        with patch.object(client,'call',return_value={'wait':{'satisfied':False}}):
            self.assertEqual('idle-wait-unsatisfied',m.inspect(client,self.self_pane)['targets'][1]['reason'])

    def test_claude_screen_only_modals_listing_reload_and_same_identity(self):
        self.installation.update(nativeVersion='2.1.322',dependenciesReady=True)
        client=ClaudeModalFake()
        plan=m.make_plan(m.inspect(client,self.self_pane),['term_target'])
        result=m.apply(client,plan,self.self_pane,self.temp.name)
        self.assertEqual([],result['remaining'],result)
        self.assertEqual(result['results'][0]['before'],result['results'][0]['after'])
        self.assertEqual('bypass permissions',result['results'][0]['before']['permissions'])
        self.assertEqual(3,client.help_page)
        events=json.loads((Path(self.temp.name)/(plan['operationId']+'.json')).read_text())['events']
        raw=[event for event in events if event.get('receiptKind') == 'raw-key']
        self.assertTrue(raw)
        self.assertEqual({1,3,30},{event['bytesWritten'] for event in raw})
        self.assertTrue(all(event['handle'] == client.target['handle'] and event['accepted'] is True for event in raw))
        self.assertTrue(all('requestId' not in event for event in raw))
        self.assertTrue(all('--enter' not in args for args in client.sent if args[args.index('--text')+1].startswith('\x1b')))

    def test_claude_21330_status_close_footer_requires_observed_header_version_and_footer(self):
        text = '\n'.join(['  Settings  Status   Config   Usage   Stats',
                          '  Version:           2.1.330',
                          '  Session ID: 01a1c848-8ff2-7e90-bcec-44a3ca07a21b',
                          '  cwd: /work', '  ←/→ to switch · Esc to close'])
        self.assertTrue(m.claude_modal(text, '/status'))
        for version in ('2.1.329', '2.1.331'):
            self.assertTrue(m.claude_modal(text.replace('2.1.330', version), '/status'))
        for invalid in (text.replace('2.1.330', '2.1.332'),
                        text.replace('Version:', 'Unknown version:'),
                        text.replace('Settings  Status   Config   Usage   Stats', 'Unknown header'),
                        text.replace('Esc to close', 'Esc to quit'),
                        text.replace('Esc to close', 'Esc to close now')):
            with self.subTest(invalid=invalid):
                self.assertFalse(m.claude_modal(invalid, '/status'))
        self.assertFalse(m.claude_modal(text, '/reload-plugins'))
        help_text = text.replace('Settings  Status   Config   Usage   Stats',
                                 'Help  General   Commands   Custom commands')
        self.assertFalse(m.claude_modal(help_text, '/help'))

    def test_claude_21330_status_modal_still_rejects_approval_prompts(self):
        text = 'Settings Status Config Usage Stats\nVersion: 2.1.330\n←/→ to switch · Esc to close'
        for prompt in ('Approve this action', 'Allow once', 'Trust this', 'Select an option',
                       'Enter to confirm', 'Yes, proceed'):
            with self.subTest(prompt=prompt):
                self.assertFalse(m.claude_modal(text+'\n'+prompt, '/status'))

    def test_claude_21330_native_status_closes_observed_modal_with_one_raw_escape(self):
        self.installation.update(nativeVersion='2.1.330')
        client = ClaudeModalFake()
        plan = m.make_plan(m.inspect(client, self.self_pane), ['term_target'])
        original = client.call
        def new_status(*args):
            result = original(*args)
            if args[:2] == ('terminal', 'send') and args[args.index('--text')+1] == '/status':
                client.read['tail'] = ['  Settings  Status   Config   Usage   Stats',
                                      '  Version:           2.1.330',
                                      '  Session ID: 01a1c848-8ff2-7e90-bcec-44a3ca07a21b',
                                      '  cwd: /work', '  ←/→ to switch · Esc to close']
            return result
        with patch.object(client, 'call', side_effect=new_status):
            identity = m.native_status(client, plan, plan['targets'][0], self.self_pane, Mock())
        self.assertEqual('2.1.330', identity['nativeVersion'])
        self.assertEqual('/work', identity['cwd'])
        self.assertEqual('bypass permissions', identity['permissions'])
        self.assertEqual(['/status', '\x1b'], [args[args.index('--text')+1] for args in client.sent])
        self.assertNotIn('--enter', client.sent[-1])
        self.assertIsNone(client.modal)

    def test_claude_modal_response_proof_survives_last_inventory_before_escape(self):
        client = ClaudeModalFake()
        plan = m.make_plan(m.inspect(client, self.self_pane), ['term_target'])
        original = m.installation_guard
        modal_checks = []
        def changing(target):
            result = original(target)
            if client.modal == '/status':
                modal_checks.append(True)
                if len(modal_checks) == 1:
                    client.read['latestCursor'] = '11'
                    client.read['tail'] = [line.replace('01a1c848-8ff2-7e90-bcec-44a3ca07a21b',
                                                        '11111111-1111-4111-8111-111111111111')
                                           for line in client.read['tail']]
            return result
        with patch.object(m, 'installation_guard', side_effect=changing):
            with self.assertRaisesRegex(m.Deferred, 'native-response-proof-changed'):
                m.native_status(client, plan, plan['targets'][0], self.self_pane, Mock())
        self.assertEqual(1, len(modal_checks))
        self.assertEqual(['/status'], [args[args.index('--text')+1] for args in client.sent])
        self.assertNotIn('nativeProof', plan['targets'][0])

    def test_claude_current_modal_missing_uuid_never_fills_it_from_history(self):
        client = ClaudeModalFake()
        client.read['tail'] = ['Session ID: 11111111-1111-4111-8111-111111111111',
                               'cwd: /work', 'Version: 2.1.330', '❯',
                               'Permission mode: bypass permissions']
        plan = m.make_plan(m.inspect(client, self.self_pane), ['term_target'])
        call = client.call
        def incomplete(*args):
            result = call(*args)
            if args[:2] == ('terminal', 'send'):
                client.read['tail'] = ['Session ID: 11111111-1111-4111-8111-111111111111',
                    'cwd: /work', 'Version: 2.1.330', '❯',
                    'Settings Status Config Usage Stats', 'Version: 2.1.330', 'cwd: /work',
                    '←/→ to switch · Esc to close']
            return result
        with patch.object(client, 'call', side_effect=incomplete):
            with self.assertRaisesRegex(m.Deferred, 'native-identity-unknown'):
                m.native_status(client, plan, plan['targets'][0], self.self_pane, Mock())
        self.assertEqual(['/status'], [args[args.index('--text')+1] for args in client.sent])
        self.assertNotIn('nativeProof', plan['targets'][0])

    def test_status_response_observation_has_no_second_installation_lookup(self):
        client, plan = self.claude_plan()
        calls = []
        lookup = m.installation_guard
        def before_input_only(target):
            calls.append(True)
            self.assertEqual([], client.sent)
            return lookup(target)
        with patch.object(m, 'installation_guard', side_effect=before_input_only):
            native = m.native_status(client, plan, plan['targets'][0], self.self_pane, Mock())
        self.assertEqual('/work', native['cwd'])
        self.assertEqual([True], calls)
        self.assertTrue(plan['targets'][0]['nativeProof'])

    def test_claude_status_waits_for_permission_and_uses_latest_confirmed_cursor(self):
        client, plan = self.claude_plan()
        client.read['tail'] = ['❯']
        original = client.call
        stream_cursors = []
        def render_footer(_):
            self.assertEqual([], client.sent)
            client.read.update(tail=['❯', 'Permission mode: default'], latestCursor='20')
        def calls(*args):
            if args[:2] == ('terminal', 'send'):
                self.assertEqual('20', client.read['latestCursor'])
                self.assertEqual('default', m.claude_permission(m.screen(client.read)))
            if args[:2] == ('terminal', 'read'):
                stream_cursors.append(args[args.index('--cursor')+1])
            return original(*args)
        with patch.object(m.time, 'sleep', side_effect=render_footer), patch.object(client, 'call', side_effect=calls):
            native = m.native_status(client, plan, plan['targets'][0], self.self_pane, Mock())
        self.assertEqual('default', native['permissions'])
        self.assertEqual(['20'], stream_cursors)
        self.assertEqual(['/status'], [args[args.index('--text')+1] for args in client.sent])

    def test_claude_21330_agent_hint_permission_footer_requires_exact_observed_context(self):
        footer = '  ⏵⏵ bypass permissions on (shift+tab to cycle)'
        header = '  ▐▛███▛█   Claude Code v2.1.330'
        observed = header+'\n❯\n'+footer+' · ← for agents'
        self.assertEqual('bypass permissions', m.claude_permission(footer))
        self.assertEqual('bypass permissions', m.claude_permission(observed))
        for invalid in (observed.replace(header+'\n', ''),
                        observed.replace(header, '예시: Claude Code v2.1.330'),
                        observed.replace('▐▛███▛█', '▐▛███▜▌'),
                        observed.replace(header, 'Claude Code v2.1.330'),
                        observed.replace('2.1.330', '2.1.331'),
                        observed.replace('2.1.330', '2.1.3301'),
                        observed.replace('2.1.330', '2.1.330-beta'),
                        observed+'\nClaude Code v2.1.331',
                        observed+'\nClaude Code v',
                        observed.replace('Claude Code v2.1.330', 'Version: 2.1.330'),
                        observed.replace('← for agents', '← for tools'),
                        observed+' extra',
                        observed.replace('bypass permissions on', 'accept edits on')):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(m.Deferred, '^claude-permissions-unknown$'):
                    m.claude_permission(invalid)

    def test_claude_21330_agent_hint_footer_starts_status_without_permission_wait(self):
        client = ClaudeModalFake()
        client.read['tail'] = ['▐▛███▛█   Claude Code v2.1.330', '❯',
                              '  ⏵⏵ bypass permissions on (shift+tab to cycle) · ← for agents']
        plan = m.make_plan(m.inspect(client, self.self_pane), ['term_target'])
        original = client.call
        def current_version(*args):
            result = original(*args)
            if args[:2] == ('terminal', 'send') and args[args.index('--text')+1] == '/status':
                client.read['tail'] = [line.replace('Version: 2.1.322', 'Version: 2.1.330')
                                       for line in client.read['tail']]
            return result
        with patch.object(client, 'call', side_effect=current_version), patch.object(m.time, 'sleep') as sleep:
            native = m.native_status(client, plan, plan['targets'][0], self.self_pane, Mock())
        sleep.assert_not_called()
        self.assertEqual('bypass permissions', native['permissions'])
        self.assertEqual('2.1.330', native['nativeVersion'])
        self.assertEqual(['/status', '\x1b'], [args[args.index('--text')+1] for args in client.sent])

    def test_claude_status_permission_wait_persistent_unknown_has_zero_input_and_no_modal(self):
        client = ClaudeModalFake()
        plan = m.make_plan(m.inspect(client, self.self_pane), ['term_target'])
        client.read['tail'] = ['❯']
        for deadline in (False, True):
            with self.subTest(deadline=deadline), patch.object(m, 'guard', wraps=m.guard) as guard, \
                 patch.object(m.time, 'monotonic', side_effect=[0, 3] if deadline else None, return_value=0), \
                 patch.object(m.time, 'sleep') as sleep:
                with self.assertRaisesRegex(m.Deferred, '^claude-permissions-unknown$'):
                    m.native_status(client, plan, plan['targets'][0], self.self_pane, Mock())
                self.assertEqual(1 if deadline else 12, guard.call_count)
                self.assertEqual(0 if deadline else 11, sleep.call_count)
                self.assertEqual([], client.sent)
                self.assertIsNone(client.modal)

    def test_claude_status_permission_wait_never_retries_identity_draft_busy_or_other_guards(self):
        changes = [('target-changed', lambda c: c.target.update(incarnationId='changed')),
                   ('draft', lambda c: c.read.update(draft='pending')),
                   ('busy-or-state-unknown', lambda c: c.agents[1].update(
                       state='working', mainAgent={'state': 'working'}, programStatus={'state': 'working'},
                       subagentObservation='live', children=[])),
                   ('approval-or-wait', lambda c: c.target.update(agentWait={'state': 'waiting'})),
                   ('child-state-unknown', lambda c: c.agents[1].update(subagentObservation='unverifiable'))]
        for reason, change in changes:
            client = ClaudeModalFake()
            plan = m.make_plan(m.inspect(client, self.self_pane), ['term_target'])
            client.read['tail'] = ['❯']
            with self.subTest(reason=reason), patch.object(m.time, 'sleep', side_effect=lambda _: change(client)) as sleep:
                with self.assertRaisesRegex(m.Deferred, '^'+reason+'$'):
                    m.native_status(client, plan, plan['targets'][0], self.self_pane, Mock())
                sleep.assert_called_once_with(0.05)
                self.assertEqual([], client.sent)

    def test_claude_status_permission_wait_uses_latest_text_to_reject_stale_response(self):
        client, plan = self.claude_plan()
        client.read['tail'] = ['❯']
        def render_footer(_):
            client.read.update(tail=['❯ /status', *client.responses['/status'], '❯', 'Permission mode: default'],
                               latestCursor='20')
        original = client.call
        def stale(*args):
            if args[:2] == ('terminal', 'send'):
                client.sent.append(args)
                return {'send': {'accepted': True}, 'mutation': {'requestId': 'request'}}
            return original(*args)
        with patch.object(m.time, 'sleep', side_effect=render_footer), patch.object(m.time, 'monotonic', return_value=0), \
             patch.object(client, 'call', side_effect=stale):
            with self.assertRaisesRegex(m.Deferred, '^native-response-freshness-unknown$'):
                m.native_status(client, plan, plan['targets'][0], self.self_pane, Mock())
        self.assertEqual(['/status'], [args[args.index('--text')+1] for args in client.sent])

    def test_modal_raw_receipt_malformed_or_mismatched_stops_without_resend(self):
        client, plan=self.claude_plan()
        target=plan['targets'][0]
        modal={'source':'screen','tail':['Settings  Status   Config   Usage   Stats','Esc to cancel']}
        valid={'handle':target['handle'],'accepted':True,'bytesWritten':1}
        bad=[{},dict(valid,handle='term_other'),dict(valid,accepted=False),
             dict(valid,bytesWritten=0),dict(valid,bytesWritten=True),dict(valid,bytesWritten='1'),
             dict(valid,prompt={'processIncarnation':'changed'}),dict(valid,prompt=None)]
        payloads=[{'send':receipt} for receipt in bad]+[
            {'send':valid,'mutation':None},{'send':valid,'mutation':{}},
            {'send':valid,'mutation':{'requestId':''}}]
        for response in payloads:
            journal=Mock()
            with self.subTest(response=response), patch.object(m,'guard',return_value=(client.target,modal)) as guard, patch.object(client,'call',return_value=response) as call:
                with self.assertRaises(m.Deferred):
                    m.modal_key(client,plan,target,self.self_pane,journal,'/status','\x1b')
                self.assertEqual(1,call.call_count)
                self.assertEqual(1,guard.call_count)
                self.assertEqual(['sending'],[entry.args[0] for entry in journal.record.call_args_list])

    def test_modal_raw_optional_metadata_and_post_guard_are_validated(self):
        client, plan=self.claude_plan()
        target=plan['targets'][0]
        modal={'source':'screen','tail':['Settings  Status   Config   Usage   Stats','Esc to cancel']}
        receipt={'send':{'handle':target['handle'],'accepted':True,'bytesWritten':1,
                         'prompt':{'processIncarnation':target['identity']['incarnationId']}},
                 'mutation':{'requestId':'actual-request'}}
        journal=Mock()
        with patch.object(m,'guard',return_value=(client.target,modal)) as guard, patch.object(client,'call',side_effect=[receipt,{'wait':{'satisfied':True}}]) as call:
            m.modal_key(client,plan,target,self.self_pane,journal,'/status','\x1b')
            self.assertEqual(2,guard.call_count)
            self.assertEqual(2,call.call_count)
            metadata=journal.record.call_args.kwargs
            self.assertEqual('actual-request',metadata['requestId'])
            self.assertEqual(target['identity']['incarnationId'],metadata['processIncarnation'])
        with patch.object(m,'guard',side_effect=[(client.target,modal),m.Deferred('target-changed')]), patch.object(client,'call',side_effect=[receipt,{'wait':{'satisfied':True}}]) as call:
            with self.assertRaisesRegex(m.Deferred,'target-changed'):
                m.modal_key(client,plan,target,self.self_pane,Mock(),'/status','\x1b')
            self.assertEqual(1,sum(args.args[:2] == ('terminal','send') for args in call.call_args_list))

    def test_command_enter_still_requires_mutation_request_id(self):
        receipt={'send':{'handle':self.client.target['handle'],'accepted':True,'bytesWritten':7}}
        with patch.object(self.client,'call',return_value=receipt) as call:
            with self.assertRaises(m.Deferred):
                m.send(self.client,Mock(),self.plan['targets'][0],'/status','status')
            self.assertEqual(1,call.call_count)
            self.assertIn('--enter',call.call_args.args)

    def test_claude_stale_screen_never_counts_as_new_response(self):
        self.installation.update(nativeVersion='2.1.322',dependenciesReady=True)
        client=ClaudeModalFake(); client.stale=True
        plan=m.make_plan(m.inspect(client,self.self_pane),['term_target'])
        result=m.apply(client,plan,self.self_pane,self.temp.name)
        self.assertEqual('native-response-freshness-unknown',result['stopped'])
        self.assertEqual(1,len(client.sent))

    def test_claude_repeat_screen_response_requires_new_echo_boundary(self):
        for command, body in (('/plugin list --enabled','example@market (v1.0.0, user) ✔ enabled'),
                              ('/reload-plugins','Reloaded: 1 plugins · 2 skills · 0 agents · 1 hooks · 0 plugin MCP servers · 0 plugin LSP servers')):
            client, plan=self.claude_plan()
            target=plan['targets'][0]
            marker='❯ '+command
            previous={'source':'screen','tail':[marker,body,'❯'],'latestCursor':'10'}
            for case, extra in (('repeat',[marker,body,'❯']),('echo-only',[marker,'❯']),('stale',[])):
                current=dict(previous,tail=previous['tail']+extra)
                first=iter([previous])
                with self.subTest(command=command,case=case), \
                     patch.object(m,'guard',return_value=(client.target,previous)), \
                     patch.object(m,'passive_guard',return_value=(client.target,current)),patch.object(m.time,'sleep'):
                    if case == 'repeat':
                        _, fresh=m.native_query(client,plan,target,self.self_pane,Mock(),command,'repeat')
                        self.assertEqual(body,fresh)
                    else:
                        with self.assertRaisesRegex(m.Deferred,'native-response-freshness-unknown'):
                            m.native_query(client,plan,target,self.self_pane,Mock(),command,'repeat')

    def test_claude_preflight_failures_never_reload(self):
        for case in ('dependencies', 'unsupported', 'version', 'runtime-list'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as folder:
                client, plan = self.claude_plan()
                if case == 'dependencies':
                    self.installation['dependenciesReady'] = False
                elif case == 'unsupported':
                    client.responses['/help'] = ['/other-command Help']
                elif case == 'version':
                    client.responses['/status'][-1] = 'Version: 2.1.288'
                else:
                    client.responses['/plugin list --enabled'] = ['other@market 2.0.0 enabled']
                result = m.apply(client, plan, self.self_pane, folder)
                self.assertIn('stopped', result)
                self.assertFalse(any('/reload-plugins' == a[a.index('--text')+1] for a in client.sent))

    def test_claude_refused_partial_or_ambiguous_reload_stops(self):
        for response in ('Run /reload-plugins --force to apply.', 'Reloaded: 1 plugins. 1 errors during load.',
                         'Reloaded: 1 plugins (+ 1 dependencies: missing) resolved', 'Unknown reply'):
            with self.subTest(response=response), tempfile.TemporaryDirectory() as folder:
                client, plan = self.claude_plan()
                client.responses['/reload-plugins'] = [response]
                result = m.apply(client, plan, self.self_pane, folder)
                self.assertIn('stopped', result)
                self.assertEqual(['term_target'], result['remaining'])
                self.assertTrue(all('--force' not in a[a.index('--text')+1] for a in client.sent))

    def test_installation_drift_before_input_aborts(self):
        changed = copy.deepcopy(self.installation)
        changed['plugins'][0]['version'] = '2.0.0'
        self.inventory.return_value = changed
        result = m.apply(self.client, self.plan, self.self_pane, self.temp.name)
        self.assertEqual('installed-versions-drift', result['stopped'])
        self.assertEqual([], self.client.sent)

    def test_installation_drift_after_resume_stops(self):
        identity = {'sessionId': '01a1c848-8ff2-7e90-bcec-44a3ca07a21b', 'cwd': '/work', 'permissions': 'Full Access', 'resumeMode': 'codex-full-access', 'nativeVersion': '0.171.0'}
        changed = copy.deepcopy(self.installation)
        changed['plugins'][0]['enabled'] = False
        with patch.object(m, 'native_status', return_value=identity), patch.object(m, 'shell_guard'), \
             patch.object(m, 'guard', return_value=(None, {'latestCursor': '10'})), patch.object(m, 'installation_guard', side_effect=[self.installation, m.Deferred('installed-versions-drift')]):
            result = m.apply(self.client, self.plan, self.self_pane, self.temp.name)
        self.assertEqual('installed-versions-drift', result['stopped'])
        self.assertEqual(['term_target'], result['remaining'])

    def test_native_codex_inventory_exposes_versions_without_source_or_secrets(self):
        data = {'installed': [{'pluginId': 'example@market', 'version': '1.2.3', 'enabled': True,
                               'installed': True, 'source': {'path': 'SECRET'}}]}
        with patch.object(m, 'native_command', side_effect=['codex-cli 0.167.1', json.dumps(data)]) as native:
            result = REAL_PLUGIN_INVENTORY('codex', '/work')
        self.assertEqual('observed', result['state'])
        self.assertEqual('1.2.3', result['plugins'][0]['version'])
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertEqual([['--version'], ['plugin', 'list', '--json']], [call.args[1] for call in native.call_args_list])

    def test_claude_dependency_manifest_and_diagnostic_contract(self):
        root = Path(self.temp.name)
        entries = []
        for name, deps in [('example', ['helper']), ('helper', [])]:
            path = root / name / '.claude-plugin'
            path.mkdir(parents=True)
            (path / 'plugin.json').write_text(json.dumps({'name': name, 'version': '1.0.0', 'dependencies': deps}))
            entries.append({'id': name+'@market', 'version': '1.0.0', 'enabled': True,
                            'scope': 'user', 'installPath': str(path.parent)})
        for missing, diagnostic, expected in [(False, False, True), (True, False, False), (False, True, False)]:
            data = copy.deepcopy(entries[:1] if missing else entries)
            if diagnostic:
                data[0]['notes'] = ['SECRET missing dependency']
            with patch.object(m, 'native_command', side_effect=['2.1.289 (Claude Code)', json.dumps(data)]):
                result = REAL_PLUGIN_INVENTORY('claude', '/work')
            self.assertEqual('observed', result['state'])
            self.assertEqual(expected, result['dependenciesReady'])
            self.assertNotIn('SECRET', json.dumps(result))
        (root / 'example/.claude-plugin/plugin.json').write_text('{"name":"example","dependencies":[{"name":"helper","version":">=1"}]}')
        with patch.object(m, 'native_command', side_effect=['2.1.289 (Claude Code)', json.dumps(entries)]):
            self.assertFalse(REAL_PLUGIN_INVENTORY('claude', '/work')['dependenciesReady'])

    def test_claude_all_eight_installations_include_distinct_disabled_project_contexts(self):
        entries = [{'id': 'plugin'+str(i)+'@market', 'version': '1.0.0', 'enabled': False,
                    'scope': 'user', 'installPath': '/private/cache'} for i in range(6)]
        entries += [{'id': 'shared@market', 'version': '1.0.0', 'enabled': False, 'scope': 'local',
                     'installPath': '/private/cache', 'projectPath': path}
                    for path in ('/private/project-a', '/private/project-b')]
        with patch.object(m, 'native_command', side_effect=['2.1.330 (Claude Code)', json.dumps(entries)]):
            result = REAL_PLUGIN_INVENTORY('claude', '/work')
        self.assertEqual('observed', result['state'])
        self.assertEqual(8, len(result['plugins']))
        contexts = [p['projectContext'] for p in result['plugins'] if p['scope'] == 'local']
        self.assertEqual(2, len(set(contexts)))
        self.assertTrue(all(len(value) == 64 for value in contexts))
        self.assertEqual(8, len(m.installed_versions(result)))
        self.assertNotIn('/private/', json.dumps(result))
        self.assertNotIn('/private/', json.dumps(m.installed_versions(result)))

    def test_claude_same_project_context_duplicate_and_unknown_context_are_refused(self):
        base = {'id': 'shared@market', 'version': '1.0.0', 'enabled': False,
                'scope': 'local', 'projectPath': '/private/project-a'}
        with patch.object(m, 'native_command', side_effect=['2.1.330 (Claude Code)', json.dumps([base, base])]):
            result = REAL_PLUGIN_INVENTORY('claude', '/work')
        self.assertEqual('plugin-installation-ambiguous', result['reason'])
        for scope in ('project', 'local'):
            for path in (None, '', 'relative', '/private/../project', '//private/project', '/private/./project',
                         '/private/project\n', [], 'C:\\private\\project'):
                with self.subTest(scope=scope, path=path):
                    entry = dict(base, scope=scope, projectPath=path)
                    with patch.object(m, 'native_command', side_effect=['2.1.330 (Claude Code)', json.dumps([entry])]):
                        result = REAL_PLUGIN_INVENTORY('claude', '/work')
                    self.assertEqual('unverified', result['state'])
                    self.assertEqual('plugin-project-context-unknown', result['reason'])
        missing = dict(base)
        missing.pop('projectPath')
        with patch.object(m, 'native_command', side_effect=['2.1.330 (Claude Code)', json.dumps([missing])]):
            self.assertEqual('unverified', REAL_PLUGIN_INVENTORY('claude', '/work')['state'])

    def test_claude_project_context_change_remains_installation_drift(self):
        entry = {'id': 'shared@market', 'version': '1.0.0', 'enabled': False,
                 'scope': 'project', 'projectPath': '/private/project-a'}
        with patch.object(m, 'native_command', side_effect=['2.1.330 (Claude Code)', json.dumps([entry])]):
            before = REAL_PLUGIN_INVENTORY('claude', '/work')
        entry['projectPath'] = '/private/project-b'
        with patch.object(m, 'native_command', side_effect=['2.1.330 (Claude Code)', json.dumps([entry])]):
            after = REAL_PLUGIN_INVENTORY('claude', '/work')
        with patch.object(m, 'plugin_inventory', return_value=after):
            with self.assertRaisesRegex(m.Deferred, 'installed-versions-drift'):
                m.installation_guard({'provider': 'claude', 'identity': {'worktreePath': '/work'}, 'installation': before})

    def test_claude_enabled_duplicate_contexts_keep_dependencies_and_runtime_listing_ambiguous(self):
        root = Path(self.temp.name)
        for name, dependencies in [('main', ['helper']), ('helper', [])]:
            manifest = root/name/'.claude-plugin'
            manifest.mkdir(parents=True)
            (manifest/'plugin.json').write_text(json.dumps({'name': name, 'dependencies': dependencies}))
        entries = [{'id': 'main@market', 'version': '1.0.0', 'enabled': True, 'scope': 'user',
                    'installPath': str(root/'main')}]
        entries += [{'id': 'helper@market', 'version': '1.0.0', 'enabled': True, 'scope': 'local',
                     'projectPath': path, 'installPath': str(root/'helper')}
                    for path in ('/private/project-a', '/private/project-b')]
        with patch.object(m, 'native_command', side_effect=['2.1.330 (Claude Code)', json.dumps(entries)]):
            result = REAL_PLUGIN_INVENTORY('claude', '/work')
        self.assertEqual('observed', result['state'])
        self.assertEqual(3, len(result['plugins']))
        self.assertFalse(result['dependenciesReady'])
        with self.assertRaisesRegex(m.Deferred, 'claude-runtime-plugin-list-ambiguous'):
            m.claude_plugin_listing('', result)

    def test_invalid_native_inventory_fails_closed(self):
        for data in ('SECRET not-json', '[]', '{"installed":[{}]}'):
            with patch.object(m, 'native_command', side_effect=['codex-cli 0.167.1', data]):
                result = REAL_PLUGIN_INVENTORY('codex', '/work')
            self.assertEqual('unverified', result['state'])
            self.assertNotIn('SECRET', json.dumps(result))

    def test_manifest_drift_and_unreadable_manifest_preserve_native_versions(self):
        root = Path(self.temp.name) / 'plugin'
        manifest = root / '.claude-plugin/plugin.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text('{"name":"example","version":"1.0.0"}')
        entries = [{'id': 'example@market', 'version': '1.0.0', 'enabled': True, 'scope': 'user', 'installPath': str(root)}]
        def snapshot():
            with patch.object(m, 'native_command', side_effect=['2.1.289 (Claude Code)', json.dumps(entries)]):
                return REAL_PLUGIN_INVENTORY('claude', '/work')
        before = snapshot()
        manifest.write_text('{"name":"example","version":"1.0.0","description":"edited"}')
        self.assertNotEqual(before, snapshot())
        manifest.unlink()
        result = snapshot()
        self.assertEqual('observed', result['state'])
        self.assertEqual('1.0.0', result['plugins'][0]['version'])
        self.assertFalse(result['dependenciesReady'])

    def test_journal_parent_replacement_cannot_redirect_writes(self):
        root = Path(self.temp.name)
        folder = root / 'journal'
        outside = root / 'outside'; outside.mkdir()
        with m.Journal(folder, self.plan['operationId']) as journal:
            folder.rename(root / 'original')
            folder.symlink_to(outside, target_is_directory=True)
            journal.record('finished')
        self.assertEqual([], list(outside.iterdir()))
        stored = json.loads((root / 'original' / (self.plan['operationId']+'.json')).read_text())
        self.assertEqual('finished', stored['events'][-1]['phase'])

    def test_journal_root_and_parent_symlinks_do_not_write_outside(self):
        root = Path(self.temp.name)
        outside = root / 'outside'; outside.mkdir()
        link = root / 'link'; link.symlink_to(outside, target_is_directory=True)
        for path in (link, link / 'nested'):
            with self.assertRaises(m.Deferred):
                with m.Journal(path, self.plan['operationId']):
                    self.fail('symlink accepted')
        self.assertEqual([], list(outside.iterdir()))

    def test_journal_record_symlink_and_replacement_preserve_victim(self):
        root = Path(self.temp.name)
        victim = root / 'victim'; victim.write_text('keep')
        journal_root = root / 'journal'; journal_root.mkdir(mode=0o700)
        path = journal_root / (self.plan['operationId']+'.json')
        path.symlink_to(victim)
        with self.assertRaises(m.Deferred):
            with m.Journal(journal_root, self.plan['operationId']):
                self.fail('record symlink accepted')
        path.unlink()
        with m.Journal(journal_root, self.plan['operationId']) as journal:
            path.unlink(); path.symlink_to(victim)
            with self.assertRaisesRegex(m.Deferred, 'replaced'):
                journal.record('finished')
        self.assertEqual('keep', victim.read_text())

    def test_journal_lock_symlink_and_hardlink_preserve_victim(self):
        root = Path(self.temp.name)
        victim = root / 'victim'; victim.write_text('keep')
        journal_root = root / 'journal'; journal_root.mkdir(mode=0o700)
        lock = journal_root / 'apply.lock'; lock.symlink_to(victim)
        with self.assertRaises(m.Deferred):
            with m.Journal(journal_root, self.plan['operationId']):
                self.fail('lock symlink accepted')
        lock.unlink()
        with m.Journal(journal_root, self.plan['operationId']) as journal:
            os.link(journal.path, root / 'duplicate')
            with self.assertRaisesRegex(m.Deferred, 'replaced'):
                journal.record('finished')
        self.assertEqual('keep', victim.read_text())

    def test_stale_agent_hint_needs_fresh_exact_native_exit_and_shell(self):
        self.client.read['tail'] = ['user@host:/work$']
        self.client.agents[1].update(state='done', mainAgent={'state': 'done'})
        self.client.agents[1].pop('programStatus')
        evidence = {'cursor': '10', 'sessionId': '01a1c848-8ff2-7e90-bcec-44a3ca07a21b'}
        self.assertEqual('codex', self.client.target['agentIdentity'])
        m.shell_guard(self.client, self.plan, self.plan['targets'][0], evidence)
        with patch.object(self.client, 'call', return_value={'terminal': {'source': 'stream', 'tail': [
                'To continue this session, run: codex resume 11111111-1111-4111-8111-111111111111']}}):
            with self.assertRaisesRegex(m.Deferred, 'shell-unconfirmed'):
                m.shell_guard(self.client, self.plan, self.plan['targets'][0], evidence)
        with patch.object(self.client, 'call', return_value={'terminal': {'source': 'stream', 'tail': []}}):
            with self.assertRaisesRegex(m.Deferred, 'shell-unconfirmed'):
                m.shell_guard(self.client, self.plan, self.plan['targets'][0], evidence)
        for key, value in [('state', 'working'), ('children', [{'state': 'working'}]), ('subagentObservation', 'unverifiable')]:
            with self.subTest(key=key):
                saved = copy.deepcopy(self.client.agents[1])
                self.client.agents[1][key] = value
                with self.assertRaises(m.Deferred):
                    m.shell_guard(self.client, self.plan, self.plan['targets'][0], evidence)
                self.client.agents[1] = saved

    def test_native_permission_policy_is_not_an_approval_dialog(self):
        read = {'source': 'screen', 'tail': ['Permissions: Custom (workspace, Ask for approval)', '›']}
        m.idle_screen('codex', read)
        read['tail'].insert(1, 'Approval required to continue')
        with self.assertRaisesRegex(m.Deferred, 'approval-or-menu'):
            m.idle_screen('codex', read)

    def test_completed_historical_hook_error_keeps_original_text_frame_and_proof(self):
        for version in m.CODEX_RESUME_VERSIONS:
            for composer in ('›', '› Ask Codex to do anything'):
                with self.subTest(version=version, composer=composer):
                    read = dict(source='screen', tail=completed_hook_error_screen(version, composer),
                                draft=None, latestCursor='10')
                    original = copy.deepcopy(read)
                    proof = m.output_proof(read)
                    text = m.idle_screen('codex', read)
                    self.assertEqual('\n'.join(original['tail']), text)
                    self.assertIn('hook approval required', text)
                    self.assertEqual(original, read)
                    self.assertEqual(proof, m.output_proof(read))

    def test_completed_historical_hook_error_does_not_hide_dialogs_or_approval_prose(self):
        for dialog in ('Yes, proceed', 'Trust this workspace?', 'Select an option',
                       'Enter to confirm', 'Esc to cancel', 'Allow once',
                       'Approval required to continue', 'Please approve this request'):
            for position in (0, 6, 8, 10):
                with self.subTest(dialog=dialog, position=position):
                    lines = completed_hook_error_screen()
                    lines.insert(position, dialog)
                    with self.assertRaisesRegex(m.Deferred, '^approval-or-menu$'):
                        m.idle_screen('codex', {'source': 'screen', 'tail': lines})

    def test_historical_hook_error_requires_exact_pair_order_and_completion(self):
        good = completed_hook_error_screen()
        cases = {
            'missing-heading': good[:3]+good[4:],
            'changed-heading': [*good[:3], '• Tool failed', *good[4:]],
            'changed-message': [*good[:4], '  └ other hook approval required', *good[5:]],
            'extra-message': [*good[:4], good[4]+'; continue', *good[5:]],
            'changed-indent': [*good[:4], good[4].lstrip(), *good[5:]],
            'missing-completion': good[:5]+good[6:],
            'changed-completion': [*good[:5], '  Worked for 3s • unknown time', *good[6:]],
            'invalid-clock': [*good[:5], '  Worked for 3s • 13:02 PM', *good[6:]],
            'changed-duration-format': [*good[:5], '  Worked for 1m 3s • 1:02 PM', *good[6:]],
            'interleaved-error': [*good[:4], '  fixture output', *good[4:]],
            'interleaved-completion': [*good[:5], '  fixture output', *good[5:]],
            'reordered-pair': [*good[:3], good[4], good[3], *good[5:]],
            'old-completion-current-error': [*good[:3], good[5], *good[3:5], *good[6:]],
            'error-after-final-composer': [*good[:3], *good[6:], *good[3:6]],
            'ordinary-approval-prose': [*good[:3], 'Hook approval required for this request', *good[6:]],
        }
        for label, lines in cases.items():
            with self.subTest(label=label):
                with self.assertRaisesRegex(m.Deferred, '^approval-or-menu$'):
                    m.idle_screen('codex', {'source': 'screen', 'tail': lines})

    def test_historical_hook_error_rejects_multiple_pairs_and_ambiguous_boundaries(self):
        good = completed_hook_error_screen()
        for label, lines in {
            'two-completed-pairs': [*good[:6], *good[3:6], *good[6:]],
            'duplicate-heading': [*good[:3], good[3], *good[3:]],
            'duplicate-message': [*good[:4], good[4], *good[4:]],
            'duplicate-completion': [*good[:6], good[5], *good[6:]],
            'later-normal-turn-completion': [*good[:7], '› fixture later request',
                                            '• fixture later response',
                                            '  Worked for 4s • 1:03 PM', *good[7:]],
            'changed-second-boundary': [*good[:6], '  Worked for unknown', *good[6:]],
        }.items():
            with self.subTest(label=label):
                with self.assertRaisesRegex(m.Deferred, '^approval-or-menu$'):
                    m.idle_screen('codex', {'source': 'screen', 'tail': lines})

    def test_historical_hook_error_keeps_draft_prompt_version_and_control_refusals(self):
        good = completed_hook_error_screen()
        cases = [
            ('draft', dict(tail=good, draft='fixture draft')),
            ('draft', dict(tail=completed_hook_error_screen(composer='› fixture draft'))),
            ('draft', dict(tail=good[:7]+good[8:])),
            ('idle-prompt-unknown', dict(tail=[line for line in good if not line.startswith('›')])),
            ('approval-or-menu', dict(tail=good[1:])),
            ('draft', dict(tail=completed_hook_error_screen(version='9.9.9'))),
            ('draft', dict(tail=completed_hook_error_screen(version='broken version'))),
            ('approval-or-menu', dict(tail=['>_ OpenAI Codex (vbroken version)', *good])),
            ('approval-or-menu', dict(tail=[*good[:3], '\x07fixture bell', *good[3:]])),
            ('approval-or-menu', dict(tail=[*good[:3], '\rfixture carriage return', *good[3:]])),
            ('approval-or-menu', dict(tail=[*good[:3], '\x9bfixture control', *good[3:]])),
            ('screen-controls', dict(tail=[*good[:3], '\x1b[2J', *good[3:]])),
        ]
        for reason, fields in cases:
            with self.subTest(reason=reason, fields=fields):
                with self.assertRaisesRegex(m.Deferred, '^'+reason+'$'):
                    m.idle_screen('codex', dict(source='screen', **fields))
        claude = [line.replace('›', '❯') for line in good]
        claude[7] = '❯'
        with self.assertRaisesRegex(m.Deferred, '^approval-or-menu$'):
            m.idle_screen('claude', {'source': 'screen', 'tail': claude, 'draft': ''})

    def test_historical_hook_error_preserves_state_identity_child_and_wait_guards(self):
        cases = [
            ('busy-or-state-unknown', lambda c: c.agents[1].update(state='working')),
            ('busy-or-state-unknown', lambda c: c.agents[1].update(mainAgent={'state': 'working'})),
            ('busy-or-state-unknown', lambda c: c.agents[1].update(programStatus={'state': 'unknown'})),
            ('invalid-json-shape', lambda c: c.agents[1].pop('programStatus')),
            ('child-work', lambda c: c.agents[1].update(children=[{'state': 'working'}])),
            ('child-state-unknown', lambda c: c.agents[1].pop('subagentObservation')),
            ('approval-or-wait', lambda c: c.target.update(agentWait={'state': 'waiting'})),
            ('identity-unknown', lambda c: c.target.pop('incarnationId')),
        ]
        for reason, change in cases:
            with self.subTest(reason=reason):
                client = Fake()
                client.read['tail'] = completed_hook_error_screen()
                change(client)
                report = m.inspect(client, self.self_pane)
                self.assertEqual(reason, report['targets'][1]['reason'])
                self.assertEqual([], client.sent)

    def test_historical_hook_error_status_keeps_full_history_and_original_proof(self):
        before, cropped = codex_screen_pair()
        history = completed_hook_error_screen()[:7]
        before = history+before
        after = before[:-3]+cropped[7:]
        client = self.screen_only_codex(before, after)
        native = self.run_screen_status(client)
        self.assertEqual('11111111-1111-4111-8111-111111111111', native['sessionId'])
        self.assertEqual('Full Access', native['permissions'])
        self.assertEqual('codex-full-access', native['resumeMode'])
        self.assertEqual(after, client.read['tail'])
        self.assertEqual(m.output_proof(client.read), self.plan['targets'][0]['nativeProof'])
        self.assertEqual(['/status'], [args[args.index('--text')+1] for args in client.sent])

    def test_historical_hook_error_never_substitutes_for_native_freshness(self):
        before = completed_hook_error_screen()
        client = self.screen_only_codex(before, before)
        with self.assertRaisesRegex(m.Deferred, '^native-response-freshness-unknown$'):
            self.run_screen_status(client)
        self.assertEqual(1, len(client.sent))
        self.assertNotIn('nativeProof', self.plan['targets'][0])

    def test_native_launch_flags_are_not_an_approval_dialog(self):
        m.idle_screen('codex', {'source': 'screen', 'tail': [
            "user@host:/work$ codex '--dangerously-bypass-approvals-and-sandbox'", '›']})
        m.idle_screen('codex', {'source': 'screen', 'tail': [
            'user@host:/work$ codex --ask-for-approval never', '›']})

    def test_native_thread_lock_menu_stops_without_retry_or_fork(self):
        self.client.read['tail'] = ['This conversation is open in another app', 'r retry f fork']
        report = m.inspect(self.client, self.self_pane)
        self.assertEqual('native-session-in-use', report['targets'][1]['reason'])
        self.assertEqual([], self.client.sent)

    def test_local_io_failure_retains_recovery_coordinates(self):
        with patch.object(m, 'refresh', side_effect=OSError('SECRET local path')):
            result = m.apply(self.client, self.plan, self.self_pane, self.temp.name)
        self.assertEqual('journal-or-local-io-failed', result['stopped'])
        self.assertIn('journal', result['recovery'])
        self.assertNotIn('SECRET', json.dumps(result))

    def test_cli_failures_never_echo_private_output(self):
        for output in ('not JSON SECRET', '[]', '{"ok":false,"error":"SECRET"}', '{"ok":true,"result":{}}'):
            with patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, output, 'SECRET')):
                with self.assertRaises(m.Deferred) as error:
                    m.Orca().call('terminal', 'list')
                self.assertNotIn('SECRET', str(error.exception))
        with patch.object(subprocess, 'run', side_effect=subprocess.TimeoutExpired('orca', 1)):
            with self.assertRaisesRegex(m.Deferred, 'timeout'):
                m.Orca().call('terminal', 'list')

    def test_cli_uses_fixed_executable_no_shell(self):
        response = json.dumps({'ok': True, 'result': {}, '_meta': {'runtimeId': 'r'}})
        with patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, response, '')) as run:
            m.Orca('host; touch /tmp/pwned').call('terminal', 'list')
        self.assertEqual(m.Orca().executable, run.call_args.args[0][0])
        self.assertNotIn('shell', run.call_args.kwargs)


    def test_claude_331_observed_hints_with_omitted_draft_allow_only_status_and_reject_typed_input(self):
        self.installation.update(nativeVersion='2.1.331')
        for hint in m.CLAUDE_331_PLACEHOLDERS:
            with self.subTest(hint=hint):
                client = ClaudeModalFake()
                initial = [' ▐▛███▛█   Claude Code v2.1.331', hint,
                           '  ⏵⏵ bypass permissions on (shift+tab to cycle)']
                client.read['tail'] = initial
                self.assertNotIn('draft', client.read)
                plan = m.make_plan(m.inspect(client, self.self_pane), ['term_target'])
                original = client.call
                def new_status(*args):
                    result = original(*args)
                    if args[:2] == ('terminal', 'send') and args[args.index('--text')+1] == '/status':
                        client.read['tail'][1] = ' Version: 2.1.331'
                        client.read['tail'][-1] = ' ←/→ to switch · Esc to close'
                    return result
                with patch.object(client, 'call', side_effect=new_status):
                    native = m.native_status(client, plan, plan['targets'][0], self.self_pane, Mock())
                self.assertEqual('2.1.331', native['nativeVersion'])
                self.assertEqual(['/status', '\x1b'], [a[a.index('--text')+1] for a in client.sent])
                for visible in ('❯', hint):
                    client.sent.clear()
                    client.read.update(tail=[initial[0], visible, initial[-1]], draft=hint[2:])
                    with self.assertRaisesRegex(m.Deferred, 'draft'):
                        m.native_status(client, plan, plan['targets'][0], self.self_pane, Mock())
                    self.assertFalse(client.sent)


class NativeInventoryBounds(unittest.TestCase):
    """Real owned native processes, OS pipes and groups; no installed CLI."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        env = patch.dict(os.environ, {'PATH': str(self.root) + os.pathsep + os.environ['PATH']})
        env.start()
        self.addCleanup(env.stop)
        self.payload = {'installed': [{'pluginId': 'owned@test', 'version': '1.0.0',
                                       'enabled': True, 'installed': True}]}

    def executable(self, body, version="print('codex-cli 0.171.0')", provider='codex'):
        path = self.root / provider
        path.write_text('#!' + sys.executable + '\nimport os, sys, time, json, subprocess\n'
                        'from pathlib import Path\n'
                        "if sys.argv[1:] == ['--version']:\n    " + version + '\n    sys.exit(0)\n' + body + '\n')
        path.chmod(0o700)

    def output(self):
        return 'print(' + repr(json.dumps(self.payload)) + ')'

    def inventory(self):
        return REAL_PLUGIN_INVENTORY('codex', str(self.root))

    def child(self):
        return ("child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
                "Path('child.pid').write_text(str(child.pid))\n")

    def assert_dead(self, pid):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try:
                if (Path('/proc') / str(pid) / 'stat').read_text().split()[2] == 'Z':
                    return
            except (FileNotFoundError, ProcessLookupError):
                return
            time.sleep(0.02)
        self.fail('owned child still running')

    def test_assert_dead_accepts_process_disappearing_during_proc_read(self):
        with patch.object(Path, 'read_text', side_effect=ProcessLookupError(3, 'No such process')) as read, \
             patch.object(time, 'sleep') as pause:
            self.assert_dead(123)
        read.assert_called_once_with()
        pause.assert_not_called()

    def test_cold_beyond_fifteen_seconds_matches_warm_with_safe_progress(self):
        self.executable(self.output())
        warm = self.inventory()
        self.executable('time.sleep(15.2)\n' + self.output())
        progress = io.StringIO()
        start = time.monotonic()
        with redirect_stderr(progress):
            cold = self.inventory()
        self.assertGreater(time.monotonic() - start, 15)
        self.assertEqual(warm, cold)
        self.assertEqual('observed', cold['state'])
        frames = [json.loads(line) for line in progress.getvalue().splitlines()]
        self.assertGreaterEqual(len(frames), 3)
        self.assertTrue(all(set(f) == {'phase', 'provider', 'elapsedSeconds', 'timeoutSeconds'} for f in frames))
        self.assertTrue(all(f['timeoutSeconds'] == 180 for f in frames))
        self.assertNotIn(str(self.root), progress.getvalue())
        self.assertNotIn('owned@test', progress.getvalue())
        self.executable('time.sleep(0.06)\n' + self.output())
        client = Fake()
        client.target['worktreePath'] = str(self.root)
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(m, 'Orca', return_value=client), patch.object(m, 'INVENTORY_PROGRESS_INTERVAL', 0.01), \
             patch.dict(os.environ, {'ORCA_PANE_KEY': m.pane(client.self)}), redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(0, m.main(['inspect']))
        self.assertEqual('observed', json.loads(stdout.getvalue())['targets'][1]['installation']['state'])
        self.assertTrue(stderr.getvalue())

    def test_diagnostics_nonzero_invalid_encoding_and_shapes_are_unverified(self):
        entries = self.payload['installed']
        cases = [(self.output() + '\nsys.stderr.write(' + repr(diagnostic) + ')', 'native-cli-diagnostics-unverified')
                 for diagnostic in ('warning: SECRET partial catalogue', 'SECRET unknown diagnostic', '  ')]
        cases += [(self.output() + '\nsys.exit(3)', 'native-cli-failed'),
                  ("os.write(1, b'\\xff')", 'native-cli-invalid-encoding'),
                  ("os.write(2, b'\\xff')\n" + self.output(), 'native-cli-invalid-encoding')]
        cases += [('print(' + repr(data) + ')', None) for data in ('SECRET invalid', '{}', '[]', '{"installed":[{}]}',
                                                                 json.dumps({'installed': entries * 2}))]
        for body, reason in cases:
            with self.subTest(body=body):
                self.executable(body)
                result = self.inventory()
                self.assertEqual('unverified', result['state'])
                if reason:
                    self.assertEqual(reason, result['reason'])
                self.assertNotIn('SECRET', json.dumps(result))

    def test_deeply_nested_owned_inventory_returns_safe_unverified_json(self):
        payload = '{"installed":[],"nested":' + '['*10000 + ']'*10000 + '}'
        self.assertEqual(20026, len(payload.encode('utf-8')))
        self.executable('sys.stdout.write(' + repr(payload) + ')')
        result = self.inventory()
        self.assertEqual('unverified', result['state'])
        self.assertEqual('native-inventory-unreadable', result['reason'])
        self.assertNotIn('plugins', result)
        self.assertNotIn('nested', json.dumps(result))
        self.assertEqual(result, json.loads(json.dumps(result)))

    def test_whole_apply_blocks_exit_zero_partial_inventory_without_input(self):
        self.executable(self.output())
        client = Fake()
        client.target['worktreePath'] = str(self.root)
        own = m.pane(client.self)
        plan = m.make_plan(m.inspect(client, own), ['term_target'])
        self.executable(self.output() + "\nsys.stderr.write('SECRET partial catalogue')")
        result = m.apply(client, plan, own, self.root/'journal')
        self.assertEqual('installed-versions-unverified', result['stopped'])
        self.assertEqual([], client.sent)
        self.assertNotIn('SECRET', json.dumps(result))

    def test_real_floods_bound_both_pipes_and_cleanup_owned_children(self):
        for fd, limit in ((1, m.NATIVE_STDOUT_LIMIT), (2, m.NATIVE_STDERR_LIMIT)):
            with self.subTest(fd=fd):
                self.executable(self.child() + 'os.write(' + str(fd) + ", b'SECRET' * " + str(limit//6 + 1) + ')\ntime.sleep(30)')
                start = time.monotonic()
                result = self.inventory()
                self.assertEqual('native-cli-output-limit', result['reason'])
                self.assertLess(time.monotonic() - start, 3)
                self.assertNotIn('SECRET', json.dumps(result))
                self.assert_dead(int((self.root/'child.pid').read_text()))
        # Simultaneous pressure exceeds stderr before stdout: no sequential-pipe deadlock.
        self.executable(self.child() + "os.write(1, b'x'*100000)\nos.write(2, b'y'*100000)\ntime.sleep(30)")
        self.assertEqual('native-cli-output-limit', self.inventory()['reason'])
        self.assert_dead(int((self.root/'child.pid').read_text()))

    def test_timeout_after_leader_exit_still_reaps_owned_group(self):
        self.executable(self.child() + self.output())
        progress = io.StringIO()
        start = time.monotonic()
        with patch.object(m, 'CODEX_INVENTORY_TIMEOUT', 0.2), patch.object(m, 'INVENTORY_PROGRESS_INTERVAL', 0.03), redirect_stderr(progress):
            result = self.inventory()
        self.assertEqual('native-cli-unavailable-or-timeout', result['reason'])
        self.assertLess(time.monotonic() - start, 2)
        self.assert_dead(int((self.root/'child.pid').read_text()))
        self.assertNotIn(str(self.root), progress.getvalue())
        self.executable("child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\nPath('child.pid').write_text(str(child.pid))\n" + self.output())
        self.assertEqual('observed', self.inventory()['state'])
        self.assert_dead(int((self.root/'child.pid').read_text()))

    def test_only_codex_inventory_has_longer_deadline(self):
        self.executable('time.sleep(0.3)\n' + self.output(), "time.sleep(0.3); print('codex-cli 0.171.0')")
        with patch.object(m, 'NATIVE_TIMEOUT', 0.15), patch.object(m, 'CODEX_INVENTORY_TIMEOUT', 0.6):
            with self.assertRaisesRegex(m.Deferred, 'timeout'):
                m.native_command('codex', ['--version'], str(self.root))
            self.assertEqual(self.payload, json.loads(m.native_command('codex', ['plugin', 'list', '--json'], str(self.root))))
            self.executable("time.sleep(0.3)\nprint('[]')", provider='claude')
            with self.assertRaisesRegex(m.Deferred, 'timeout'):
                m.native_command('claude', ['plugin', 'list', '--json'], str(self.root))

    def test_exact_executable_retains_stdin_isolation_and_bounded_transport(self):
        exact = self.root / 'codex'
        args = ['owned-proof-query']
        self.executable('assert sys.stdin.buffer.read() == b""\n' + self.output())
        self.assertEqual(self.payload, json.loads(m.native_command(
            'codex', args, str(self.root), executable=str(exact))))
        cases = [("sys.stderr.write('SECRET diagnostic')", 'native-cli-diagnostics-unverified'),
                 ('sys.exit(3)', 'native-cli-failed'),
                 ('os.write(1, b"x" * ' + str(m.NATIVE_STDOUT_LIMIT + 1) + ')', 'native-cli-output-limit'),
                 ('time.sleep(30)', 'native-cli-unavailable-or-timeout')]
        for body, reason in cases:
            with self.subTest(reason=reason):
                child = ("child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], "
                         'stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n'
                         "Path('child.pid').write_text(str(child.pid))\n")
                self.executable(child + body)
                timeout = 0.2 if reason == 'native-cli-unavailable-or-timeout' else 2
                with patch.object(m, 'NATIVE_TIMEOUT', timeout), self.assertRaisesRegex(m.Deferred, reason) as failure:
                    m.native_command('codex', args, str(self.root), executable=str(exact))
                self.assertNotIn('SECRET', str(failure.exception))
                self.assert_dead(int((self.root/'child.pid').read_text()))

    def test_exact_executable_rejects_invalid_file_without_any_launch(self):
        self.executable(self.output())
        link = self.root / 'linked'
        link.symlink_to(self.root / 'codex')
        noexec = self.root / 'noexec'
        noexec.write_text('fixture')
        noexec.chmod(0o600)
        for exact in ('codex', str(self.root), str(self.root/'missing'), str(link), str(noexec),
                      str(self.root/'codex') + '\n', 123):
            with self.subTest(exact=exact), patch.object(subprocess, 'Popen') as launch, self.assertRaisesRegex(
                    m.Deferred, 'native-cli-executable-unverified'):
                m.native_command('codex', ['--version'], str(self.root), executable=exact)
            launch.assert_not_called()

    def test_full_non_drained_stderr_does_not_block_deadline_cleanup_or_repeat(self):
        self.executable(self.child() + 'time.sleep(30)')
        read_fd, write_fd = os.pipe()
        try:
            os.set_blocking(write_fd, False)
            while True:
                try:
                    os.write(write_fd, b'x' * 4096)
                except BlockingIOError:
                    break
            os.set_blocking(write_fd, True)
            original_flags = fcntl.fcntl(write_fd, fcntl.F_GETFL)
            code = ('import importlib.util, json, os, sys, fcntl, threading\n'
                    's=importlib.util.spec_from_file_location("owned", ' + repr(str(SCRIPT)) + ')\n'
                    'm=importlib.util.module_from_spec(s); s.loader.exec_module(m)\n'
                    'm.CODEX_INVENTORY_TIMEOUT=0.15; m.INVENTORY_PROGRESS_INTERVAL=0.01\n'
                    'flags=fcntl.fcntl(2,fcntl.F_GETFL); fds=len(os.listdir("/proc/self/fd")); threads=threading.active_count()\n'
                    'results=[]; pids=[]\n'
                    'for _ in range(3):\n'
                    ' results.append(m.plugin_inventory("codex", ' + repr(str(self.root)) + '))\n'
                    ' pids.append(int(open(' + repr(str(self.root/'child.pid')) + ').read()))\n'
                    'print(json.dumps({"results":results,"pids":pids,"flagsSame":flags==fcntl.fcntl(2,fcntl.F_GETFL),'
                    '"fdsSame":fds==len(os.listdir("/proc/self/fd")),"threadsSame":threads==threading.active_count()}))\n')
            helper = subprocess.Popen([sys.executable, '-B', '-c', code], stdout=subprocess.PIPE, stderr=write_fd,
                                      text=True, start_new_session=True)
            try:
                output, _ = helper.communicate(timeout=4)
            except subprocess.TimeoutExpired:
                os.killpg(helper.pid, signal.SIGKILL)
                helper.communicate()
                self.fail('full stderr blocked inventory deadline')
            self.assertEqual(0, helper.returncode)
            result = json.loads(output)
            self.assertTrue(result['flagsSame'] and result['fdsSame'] and result['threadsSame'])
            self.assertEqual(original_flags, fcntl.fcntl(write_fd, fcntl.F_GETFL))
            self.assertTrue(all(r['reason'] == 'native-cli-unavailable-or-timeout' for r in result['results']))
            for pid in result['pids']:
                self.assert_dead(pid)
        finally:
            os.close(read_fd)
            os.close(write_fd)

    def test_closed_broken_and_custom_stderr_cannot_break_inventory(self):
        self.executable('time.sleep(0.06)\n' + self.output())
        class Unwritable:
            def fileno(self):
                raise OSError('SECRET unwritable')
            def write(self, value):
                raise AssertionError('unbounded Python writer used')
        closed = io.StringIO()
        closed.close()
        read_fd, write_fd = os.pipe()
        os.close(read_fd)
        with os.fdopen(write_fd, 'w') as broken:
            flags = fcntl.fcntl(write_fd, fcntl.F_GETFL)
            for sink in (closed, Unwritable(), broken):
                with self.subTest(sink=type(sink)), redirect_stderr(sink), patch.object(m, 'INVENTORY_PROGRESS_INTERVAL', 0.01):
                    self.assertEqual('observed', self.inventory()['state'])
            self.assertEqual(flags, fcntl.fcntl(write_fd, fcntl.F_GETFL))


class ManagementBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.client = Fake()
        self.client.self['agentIdentity'] = None
        self.client.agents = [self.client.agents[1]]
        original = self.client.inventory
        def complete_inventory():
            ts, ps = original()
            ps.update(truncated=False, hostScope={'hostIds': ['local']})
            return ts, ps
        self.client.inventory = complete_inventory
        self.evidence = {'generation': 1}
        process = patch.object(m, 'management_process_proof', side_effect=lambda: copy.deepcopy(self.evidence))
        process.start()
        self.addCleanup(process.stop)
        ts, ps = self.client.inventory()
        self.client.management_self = m.management_observation(self.client, 'tab:self', ts['terminals'], ps)
        self.plan = {'runtimeId': self.client.runtime, 'selfPane': 'tab:self'}
        self.target = {'handle': self.client.target['handle'], 'identity': m.fingerprint(self.client.target),
                       'provider': 'codex'}

    def test_passive_guard_reads_self_before_final_target_and_then_only_local_proof(self):
        events = []
        observe, inventory = self.client.observe, self.client.inventory
        def traced_inventory():
            events.append('inventory')
            return inventory()
        def traced_observe(handle):
            events.append(handle)
            return observe(handle)
        with patch.object(self.client, 'inventory', side_effect=traced_inventory), \
             patch.object(self.client, 'observe', side_effect=traced_observe):
            m.passive_guard(self.client, self.plan, self.target, 'tab:self')
            m.send(self.client, Mock(), self.target, '/status', 'status')
        self.assertEqual(['inventory', 'term_self', 'term_target'], events)
        self.assertEqual(1, len(self.client.sent))

    def test_passive_guard_rechecks_process_after_target_observation(self):
        observe = self.client.observe
        def drift(handle):
            value = observe(handle)
            if handle == 'term_target':
                self.evidence['generation'] = 2
            return value
        with patch.object(self.client, 'observe', side_effect=drift):
            with self.assertRaisesRegex(m.Deferred, 'management-self-changed'):
                m.passive_guard(self.client, self.plan, self.target, 'tab:self')
        self.assertEqual([], self.client.sent)

    def test_sending_checks_before_record_and_again_after_record(self):
        journal = Mock()
        self.evidence['generation'] = 2
        with self.assertRaises(m.Deferred):
            m.send(self.client, journal, self.target, '/status', 'status')
        journal.record.assert_not_called()
        self.evidence['generation'] = 1
        journal.record.side_effect = lambda *args, **kwargs: self.evidence.update(generation=2)
        with self.assertRaises(m.Deferred):
            m.send(self.client, journal, self.target, '/status', 'status')
        journal.record.assert_called_once()
        self.assertEqual([], self.client.sent)

    def test_modal_key_checks_fixed_proof_at_both_durable_boundaries(self):
        self.client.target['agentIdentity'] = 'claude'
        self.client.agents[0]['agentType'] = 'claude'
        self.target['provider'] = 'claude'
        self.client.read['tail'] = [' Settings Status Config Usage Stats', ' Version: 2.1.330',
                                    ' ←/→ to switch · Esc to close']
        journal = Mock()
        with patch.object(m, 'installation_guard'), patch.object(m, 'wait_idle'):
            def drift_before_record(*args):
                self.evidence['generation'] = 2
                return True
            with patch.object(m, 'claude_modal', side_effect=drift_before_record):
                with self.assertRaises(m.Deferred):
                    m.modal_key(self.client, self.plan, self.target, 'tab:self', journal, '/status', '\x1b')
            journal.record.assert_not_called()
            self.evidence['generation'] = 1
            journal.record.side_effect = lambda *args, **kwargs: self.evidence.update(generation=2)
            with self.assertRaises(m.Deferred):
                m.modal_key(self.client, self.plan, self.target, 'tab:self', journal, '/status', '\x1b')
        journal.record.assert_called_once()
        self.assertEqual([], self.client.sent)


class ManagementProcessTests(unittest.TestCase):
    @contextmanager
    def proc_fixture(self, mutate=None):
        uid = os.getuid()
        processes = {
            42: dict(ppid=40, pgrp=42, sid=40, tty=1234, foreground=42, starttime=100),
            40: dict(ppid=1, pgrp=40, sid=40, tty=1234, foreground=42, starttime=90),
            # A detached shell/gitstatus-style background job on the same tty
            # is not foreground group membership and must not be overclaimed.
            60: dict(ppid=40, pgrp=60, sid=40, tty=1234, foreground=42, starttime=95)}
        exes = {42: os.path.realpath(sys.executable), 40: '/usr/bin/bash'}
        if mutate:
            mutate(processes, exes)
        read_text, path_stat, iterdir = Path.read_text, Path.stat, Path.iterdir
        readlink, os_stat = os.readlink, os.stat
        def read(path, *args, **kwargs):
            if path.parent.parent == Path('/proc') and path.name == 'stat':
                row = processes[int(path.parent.name)]
                if isinstance(row, Exception):
                    raise row
                if isinstance(row, str):
                    return row
                fields = ['S'] + ['0'] * 49
                for index, key in zip((1, 2, 3, 4, 5, 19), ('ppid', 'pgrp', 'sid', 'tty', 'foreground', 'starttime')):
                    fields[index] = str(row[key])
                return path.parent.name + ' (name with ) spaces) ' + ' '.join(fields)
            return read_text(path, *args, **kwargs)
        def metadata(path, *args, **kwargs):
            if path.parent == Path('/proc') and path.name.isdecimal():
                return SimpleNamespace(st_uid=uid)
            return path_stat(path, *args, **kwargs)
        def entries(path):
            if path == Path('/proc'):
                return iter(Path('/proc') / str(pid) for pid in processes)
            return iterdir(path)
        def executable(path, *args, **kwargs):
            value = str(path)
            if value.startswith('/proc/') and value.endswith('/exe'):
                return exes[int(value.split('/')[2])]
            return readlink(path, *args, **kwargs)
        def executable_stat(path, *args, **kwargs):
            value = str(path)
            if value.startswith('/proc/') and value.endswith('/exe'):
                pid = int(value.split('/')[2])
                return SimpleNamespace(st_dev=1, st_ino=pid, st_uid=0 if pid == 40 else uid,
                                       st_mode=0o100755, st_mtime_ns=100)
            return os_stat(path, *args, **kwargs)
        with ExitStack() as stack:
            stack.enter_context(patch.object(m.os, 'getpid', return_value=42))
            stack.enter_context(patch.object(m.Path, 'read_text', autospec=True, side_effect=read))
            stack.enter_context(patch.object(m.Path, 'stat', autospec=True, side_effect=metadata))
            stack.enter_context(patch.object(m.Path, 'iterdir', autospec=True, side_effect=entries))
            stack.enter_context(patch.object(m.os, 'readlink', side_effect=executable))
            stack.enter_context(patch.object(m.os, 'stat', side_effect=executable_stat))
            yield

    def test_proc_proves_executables_and_foreground_while_allowing_background_tty_job(self):
        with self.proc_fixture():
            proof = m.management_process_proof()
        self.assertEqual(42, proof['helper']['pid'])
        self.assertEqual(100, proof['helper']['starttime'])
        self.assertEqual('/usr/bin/bash', proof['parentExecutable']['path'])

    def test_proc_missing_tty_foreground_parent_or_executable_fails_closed(self):
        for unsafe in ('tty', 'pgrp', 'foreground', 'sid', 'parent-sid', 'parent-tty',
                       'parent-exe', 'helper-exe', 'member', 'malformed', 'permission'):
            def mutate(rows, exes):
                if unsafe in ('tty', 'pgrp', 'foreground', 'sid'):
                    rows[42][unsafe] = 0
                elif unsafe.startswith('parent-') and unsafe != 'parent-exe':
                    rows[40][unsafe[7:]] = 0
                elif unsafe == 'parent-exe':
                    exes[40] = '/tmp/bash'
                elif unsafe == 'helper-exe':
                    exes[42] = '/tmp/python3'
                elif unsafe == 'member':
                    rows[60]['pgrp'] = 42
                elif unsafe == 'malformed':
                    rows[60] = '60 (broken) invalid'
                else:
                    rows[60] = PermissionError('unreadable process')
            with self.subTest(unsafe=unsafe), self.proc_fixture(mutate):
                with self.assertRaises(m.Deferred):
                    m.management_process_proof()

    def test_vanished_scan_pid_is_distinct_from_unreadable_evidence(self):
        with self.proc_fixture(lambda rows, exes: rows.update({60: FileNotFoundError()})):
            self.assertEqual(42, m.management_process_proof()['helper']['pid'])

    def test_non_linux_is_unsupported_and_current_tool_without_tty_is_rejected(self):
        with patch.object(m.sys, 'platform', 'darwin'):
            with self.assertRaisesRegex(m.Deferred, 'management-process-unsupported'):
                m.management_process_proof()
        # Owned subprocess inherits no controlling TTY; it is not an eligible
        # management shell merely because it runs Python and has no native hint.
        code = ('import importlib.util; s=importlib.util.spec_from_file_location("rr", '+repr(str(SCRIPT))+'); '
                'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
                '\ntry: m.management_process_proof()\nexcept m.Deferred: print("rejected")\n')
        result = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True, timeout=10,
                                start_new_session=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('rejected', result.stdout.strip())

    def test_real_owned_pty_heredoc_helper_and_foreground_group_conflict(self):
        helper = '''import importlib.util, json, os, signal
spec = importlib.util.spec_from_file_location('owned_rr', SCRIPT_PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
proof = m.management_process_proof()
print('OWNED_PROOF_OK', proof['helper']['pid'] == os.getpid(), os.isatty(0), flush=True)
# A separate process group on this tty is allowed.
read_fd, write_fd = os.pipe()
background = os.fork()
if background == 0:
    os.close(read_fd)
    os.setpgid(0, 0)
    os.write(write_fd, b'x')
    signal.pause()
    os._exit(0)
os.close(write_fd)
os.read(read_fd, 1)
os.close(read_fd)
try:
    m.management_process_proof()
    print('OWNED_BACKGROUND_OK', flush=True)
finally:
    os.kill(background, signal.SIGKILL)
    os.waitpid(background, 0)
# Another member of the foreground group makes sole ownership unprovable.
read_fd, write_fd = os.pipe()
member = os.fork()
if member == 0:
    os.close(read_fd)
    os.write(write_fd, b'x')
    signal.pause()
    os._exit(0)
os.close(write_fd)
os.read(read_fd, 1)
os.close(read_fd)
try:
    try:
        m.management_process_proof()
        print('UNSAFE_ACCEPTED', flush=True)
    except m.Deferred:
        print('OWNED_GROUP_REJECTED', flush=True)
finally:
    os.kill(member, signal.SIGKILL)
    os.waitpid(member, 0)
'''.replace('SCRIPT_PATH', repr(str(SCRIPT)))
        pid, master = pty.fork()
        if pid == 0:
            os.execv('/bin/bash', ['bash', '--noprofile', '--norc', '-i'])
        output = bytearray()
        try:
            # Disable echo so only executed evidence can satisfy assertions.
            os.write(master, b"stty -echo; printf '\\nOWNED_READY\\n'\n")
            deadline = time.monotonic() + 5
            while b'\r\nOWNED_READY\r\n' not in output:
                if time.monotonic() >= deadline:
                    self.fail('owned PTY shell did not become ready')
                ready, _, _ = select.select([master], [], [], 0.1)
                if ready:
                    output.extend(os.read(master, 65536))
            output.clear()
            command = shlex.quote(sys.executable) + " -B - <<'OWNED_PROOF'\n" + helper + 'OWNED_PROOF\nexit\n'
            os.write(master, command.encode())
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                ready, _, _ = select.select([master], [], [], 0.1)
                if ready:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError:
                        break
                    if not chunk:
                        break
                    output.extend(chunk)
            else:
                self.fail('owned PTY exceeded deadline')
            _, status = os.waitpid(pid, 0)
            pid = None
            self.assertEqual(0, os.waitstatus_to_exitcode(status), output.decode(errors='replace'))
        finally:
            os.close(master)
            if pid is not None:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
        text = output.decode(errors='replace')
        self.assertIn('OWNED_PROOF_OK True False', text)
        self.assertIn('OWNED_BACKGROUND_OK', text)
        self.assertIn('OWNED_GROUP_REJECTED', text)
        self.assertNotIn('UNSAFE_ACCEPTED', text)


class TargetShellProcessTests(unittest.TestCase):
    @contextmanager
    def proc_fixture(self):
        uid = os.getuid()
        rows = {40: dict(pid=40, ppid=1, pgrp=40, sid=40, tty=1234, foreground=40, starttime=90, uid=uid),
                60: dict(pid=60, ppid=40, pgrp=60, sid=40, tty=1234, foreground=40, starttime=95, uid=uid)}
        exes = {40: dict(path='/usr/bin/zsh', device=1, inode=40, uid=0, mode=0o100755, mtime=100)}
        environments = {40: b'ORCA_PANE_KEY=tab:target\0PRIVATE_UNUSED=never-retained\0'}
        cwds = {40: '/work'}
        real_open, real_readlink = Path.open, os.readlink
        def readlink(path):
            value = str(path)
            if value.startswith('/proc/') and value.endswith('/cwd'):
                return cwds[int(value.split('/')[2])]
            return real_readlink(path)
        def process(pid, reason):
            value = rows[pid]
            if isinstance(value, Exception): raise value
            return copy.deepcopy(value)
        def environment(path, *args, **kwargs):
            if path.parent.parent == Path('/proc') and path.name == 'environ':
                value = environments[int(path.parent.name)]
                if isinstance(value, Exception): raise value
                return io.BytesIO(value)
            return real_open(path, *args, **kwargs)
        with ExitStack() as stack:
            stack.enter_context(patch.object(m, 'proc_process', side_effect=process))
            stack.enter_context(patch.object(m, 'proc_executable', side_effect=lambda pid: copy.deepcopy(exes[pid])))
            stack.enter_context(patch.object(m.Path, 'iterdir', return_value=[Path('/proc') / str(pid) for pid in rows]))
            stack.enter_context(patch.object(m.Path, 'open', autospec=True, side_effect=environment))
            stack.enter_context(patch.object(m.os, 'readlink', side_effect=readlink))
            yield rows, exes, environments, cwds

    def test_exact_pane_cwd_system_zsh_sole_foreground_retains_no_environment(self):
        with self.proc_fixture():
            proof = m.target_shell_process_proof(m.fingerprint(terminal()))
        self.assertEqual(40, proof['shell']['pid'])
        self.assertEqual('/usr/bin/zsh', proof['executable']['path'])
        self.assertEqual('/work', proof['cwd'])
        self.assertNotIn('PRIVATE_UNUSED', json.dumps(proof))
        self.assertNotIn('never-retained', json.dumps(proof))

    def test_wrong_process_identity_foreground_executable_and_environment_matrix(self):
        for unsafe in ('pane', 'duplicate-key', 'missing-key', 'environment-denied', 'cwd', 'uid',
                       'tty', 'pgrp', 'sid', 'foreground', 'starttime', 'exe-path', 'exe-uid',
                       'exe-mode', 'not-regular', 'member', 'duplicate', 'duplicate-bash', 'duplicate-dash',
                       'duplicate-other-cwd', 'native-foreground', 'permission'):
            with self.subTest(unsafe=unsafe), self.proc_fixture() as (rows, exes, environments, cwds):
                if unsafe == 'pane': environments[40] = b'ORCA_PANE_KEY=tab:wrong\0'
                elif unsafe == 'duplicate-key': environments[40] *= 2
                elif unsafe == 'missing-key': environments[40] = b'OTHER=1\0'
                elif unsafe == 'environment-denied': environments[40] = PermissionError()
                elif unsafe == 'cwd': cwds[40] = '/elsewhere'
                elif unsafe == 'uid': rows[40]['uid'] += 1
                elif unsafe in ('tty', 'pgrp', 'sid', 'foreground', 'starttime'): rows[40][unsafe] = 0
                elif unsafe == 'exe-path': exes[40]['path'] = '/tmp/zsh'
                elif unsafe == 'exe-uid': exes[40]['uid'] = 1000
                elif unsafe == 'exe-mode': exes[40]['mode'] |= 0o020
                elif unsafe == 'not-regular': exes[40]['mode'] = 0o040755
                elif unsafe == 'member': rows[60]['pgrp'] = 40
                elif unsafe.startswith('duplicate'):
                    rows[60].update(pid=60, pgrp=60, sid=60, foreground=60)
                    exes[60] = copy.deepcopy(exes[40])
                    environments[60] = environments[40]
                    cwds[60] = '/other' if unsafe == 'duplicate-other-cwd' else '/work'
                    if unsafe in ('duplicate-bash', 'duplicate-dash'):
                        exes[60]['path'] = '/usr/bin/' + unsafe.split('-')[1]
                elif unsafe == 'native-foreground': rows[40]['foreground'] = 60
                else: rows[60] = PermissionError()
                with self.assertRaises(m.Deferred):
                    m.target_shell_process_proof(m.fingerprint(terminal()))

    def test_process_pid_executable_cwd_pane_and_membership_drift_fails_closed(self):
        for drift in ('pid', 'executable', 'cwd', 'pane', 'member'):
            with self.subTest(drift=drift), self.proc_fixture() as (rows, exes, environments, cwds):
                entries = list(rows)
                scans = []
                def scan():
                    scans.append(True)
                    if len(scans) == 2:
                        if drift == 'pid': rows[40]['starttime'] += 1
                        elif drift == 'executable': exes[40]['inode'] += 1
                        elif drift == 'cwd': cwds[40] = '/other'
                        elif drift == 'pane': environments[40] = b'ORCA_PANE_KEY=tab:other\0'
                        else: rows[60]['pgrp'] = 40
                    return iter(Path('/proc') / str(pid) for pid in entries)
                with patch.object(m.Path, 'iterdir', side_effect=scan):
                    with self.assertRaises(m.Deferred):
                        m.target_shell_process_proof(m.fingerprint(terminal()))

    def test_nonlocal_and_nonlinux_cannot_use_process_proof(self):
        for platform, host in (('darwin', 'local'), ('linux', 'remote')):
            identity = m.fingerprint(terminal())
            identity['executionHostId'] = host
            with patch.object(m.sys, 'platform', platform):
                with self.assertRaisesRegex(m.Deferred, 'target-shell-process-unsupported'):
                    m.target_shell_process_proof(identity)

    def test_real_owned_pty_system_shell_is_bounded_to_zsh(self):
        # If zsh is absent this proves the real bash refusal, without installing
        # tools or presenting a simulated executable as a native zsh result.
        shell = '/usr/bin/zsh' if Path('/usr/bin/zsh').is_file() else '/bin/bash'
        pid, master = pty.fork()
        if pid == 0:
            env = dict(os.environ, ORCA_PANE_KEY='tab:target')
            os.execve(shell, [shell, '-f', '-i'] if shell.endswith('zsh') else
                      [shell, '--noprofile', '--norc', '-i'], env)
        try:
            os.write(master, b"stty -echo; printf '\\nOWNED_TARGET_READY\\n'\n")
            output = bytearray()
            deadline = time.monotonic() + 5
            while b'\r\nOWNED_TARGET_READY\r\n' not in output:
                if time.monotonic() >= deadline: self.fail('owned shell did not become ready')
                ready, _, _ = select.select([master], [], [], 0.1)
                if ready: output.extend(os.read(master, 65536))
            identity = m.fingerprint(terminal())
            identity['worktreePath'] = os.getcwd()
            if shell.endswith('zsh'):
                proof = m.target_shell_process_proof(identity)
                self.assertEqual(pid, proof['shell']['pid'])
            else:
                with self.assertRaisesRegex(m.Deferred, 'target-shell-process-unverifiable'):
                    m.target_shell_process_proof(identity)
        finally:
            os.close(master)
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)


class ClaudeNativeRecoveryContracts(unittest.TestCase):
    def test_observed_native_versions_and_distinct_launch_versions_require_explicit_mode(self):
        session = '11111111-1111-4111-8111-111111111111'
        for source in ('2.1.319', '2.1.329', '2.1.330', '2.1.331'):
            native = m.status('claude', '\n'.join(('Session ID: '+session, 'cwd: /work',
                              'Permission mode: bypass permissions', 'Version: '+source)))
            self.assertEqual('claude-bypass-permissions', native['resumeMode'])
            for launch in ('2.1.330', '2.1.331'):
                self.assertEqual('claude --dangerously-skip-permissions --resume '+session,
                                 m.resume_command('claude', native, installed_version=launch))
            for launch in ('2.1.319', '2.1.329', '2.1.332', None):
                with self.assertRaisesRegex(m.Deferred, 'version-unverified'):
                    m.resume_command('claude', native, installed_version=launch)
            native['resumeMode'] = None
            with self.assertRaisesRegex(m.Deferred, 'permissions-unverified'):
                m.resume_command('claude', native, installed_version='2.1.331')
        for source in ('2.1.318', '2.1.320', '2.1.328', '2.1.332'):
            self.assertIsNone(m.observed_resume_mode('claude', {'nativeVersion': source, 'permissions': 'bypass permissions'}))
        for permission in ('auto', 'default', 'acceptEdits', 'plan'):
            self.assertIsNone(m.observed_resume_mode('claude', {'nativeVersion': '2.1.331', 'permissions': permission}))

    def test_exact_331_placeholders_allow_observed_omitted_empty_draft_and_reject_typed_identical(self):
        for hint in m.CLAUDE_331_PLACEHOLDERS:
            frame = {'source': 'screen', 'tail': [
                ' ▐▛███▛█   Claude Code v2.1.331', hint,
                '  ⏵⏵ bypass permissions on (shift+tab to cycle)']}
            self.assertNotIn('draft', frame)  # owned331 empty/restored frame contract
            self.assertEqual('\n'.join(frame['tail']), m.idle_screen('claude', frame))
            self.assertEqual('bypass permissions', m.claude_permission(m.screen(frame)))
            self.assertEqual(m.screen(frame), m.current_status_response('claude', m.screen(frame)))
            for empty in (None, ''):
                self.assertEqual(m.screen(frame), m.idle_screen('claude', {**frame, 'draft': empty}))
            for change in ('typed-identical', 'typed-identical-stale-hint', 'typed-other', 'version',
                           'header', 'text', 'space', 'duplicate-version', 'approval'):
                with self.subTest(hint=hint, change=change):
                    invalid = copy.deepcopy(frame)
                    if change.startswith('typed-identical'):
                        invalid['draft'] = hint[2:]
                        if change == 'typed-identical': invalid['tail'][1] = '❯'
                    elif change == 'typed-other': invalid['draft'] = 'typed'
                    elif change == 'version': invalid['tail'][0] = invalid['tail'][0].replace('331', '330')
                    elif change == 'header': invalid['tail'].pop(0)
                    elif change == 'text': invalid['tail'][1] = '❯\u00a0Try "other text"'
                    elif change == 'space': invalid['tail'][1] = hint.replace('\u00a0', ' ')
                    elif change == 'duplicate-version': invalid['tail'].append('Claude Code v2.1.329')
                    elif change == 'approval': invalid['tail'].append('Allow once')
                    with self.assertRaises(m.Deferred): m.idle_screen('claude', invalid)


if __name__ == '__main__':
    unittest.main()
