import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
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
        self.read['tail'] = ['❯']
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
            self.read['tail'] = self.delta + ['❯']
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
        identity = {'sessionId': '01a1c848-8ff2-7e90-bcec-44a3ca07a21b', 'cwd': '/work', 'permissions': 'Full Access'}
        with patch.object(m, 'native_status', return_value=identity), patch.object(m, 'shell_guard'):
            result = m.apply(self.client, self.plan, self.self_pane, self.temp.name)
        row = result['results'][0]
        self.assertEqual(row['before'], row['after'])
        self.assertEqual('unverified', row['consumption'])
        texts = [args[args.index('--text')+1] for args in self.client.sent]
        self.assertEqual(['/exit', 'codex resume '+identity['sessionId']], texts)
        self.assertNotIn('--last', ' '.join(texts))

    def test_identity_permission_mismatch_stops(self):
        before = {'sessionId': 'id', 'cwd': '/work', 'permissions': 'Full Access'}
        after = dict(before, permissions='different')
        with patch.object(m, 'native_status', side_effect=[before, after]), patch.object(m, 'shell_guard'):
            result = m.apply(self.client, self.plan, self.self_pane, self.temp.name)
        self.assertEqual('native-identity-or-permissions-mismatch', result['stopped'])

    def test_shell_must_be_current_and_empty(self):
        self.client.target['agentIdentity'] = None
        self.client.read['tail'] = ['user@host:/work$']
        m.shell_guard(self.client, self.plan, self.plan['targets'][0], {'cursor': '10', 'sessionId': '01a1c848-8ff2-7e90-bcec-44a3ca07a21b'})
        for lines in (['old$','codex menu'], ['user$ unfinished'], ['›']):
            self.client.read['tail'] = lines
            with self.assertRaises(m.Deferred):
                m.shell_guard(self.client, self.plan, self.plan['targets'][0], {'cursor': '10', 'sessionId': '01a1c848-8ff2-7e90-bcec-44a3ca07a21b'})

    def test_native_status_metadata_and_hostile_input(self):
        text = 'Session: 01a1c848-8ff2-7e90-bcec-44a3ca07a21b\nDirectory: /work\nPermissions: Full Access\n'
        self.assertEqual('/work', m.status('codex', text)['cwd'])
        with self.assertRaises(m.Deferred):
            m.status('codex', text.replace('01a1c848-8ff2-7e90-bcec-44a3ca07a21b', '$(touch /tmp/pwned)'))
        for value in (None, [], {'schema': 99}, dict(self.plan, createdAt=time.time()-301), dict(self.plan, operationId={})):
            with self.assertRaises(m.Deferred):
                m.validate_plan(value)

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

    def test_complete_fresh_status_ignores_valid_old_screen(self):
        client = self.status_with_old_screen([
            'Session: 01a1c848-8ff2-7e90-bcec-44a3ca07a21b', 'Directory: /work', 'Permissions: fresh'])
        with m.Journal(self.temp.name, self.plan['operationId']) as journal:
            result = m.native_status(client, self.plan, self.plan['targets'][0], self.self_pane, journal)
        self.assertEqual('01a1c848-8ff2-7e90-bcec-44a3ca07a21b', result['sessionId'])
        self.assertEqual('fresh', result['permissions'])

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
        identity = {'sessionId': '01a1c848-8ff2-7e90-bcec-44a3ca07a21b', 'cwd': '/work', 'permissions': 'Full Access'}
        with patch.object(m, 'native_status', return_value=identity), patch.object(m, 'shell_guard'), \
             patch.object(m, 'guard', side_effect=[(None, {'latestCursor': '10'}), m.Deferred('agent-identity-unknown'), None]), \
             patch.object(m.time, 'sleep'):
            result = m.apply(self.client, self.plan, self.self_pane, self.temp.name)
        self.assertEqual([], result['remaining'])
        self.assertEqual(2, len(self.client.sent))

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

    def test_claude_partial_listing_reads_until_complete_without_sending(self):
        client,plan=self.claude_plan();target=plan['targets'][0]
        heading=['❯ /plugin list --enabled','  ⎿  Installed plugins:','────','❯']
        complete=heading[:2]+['• example@market (v1.0.0, user) ✔ enabled']+heading[2:]
        frame=lambda rows:{'source':'screen','tail':rows,'latestCursor':'6'}
        validate=lambda text:m.claude_plugin_listing(text,self.installation)
        args=(client,plan,target,self.self_pane,'/plugin list --enabled',frame(heading),'────',validate,'claude-runtime-plugin-list-unknown')
        frames=[(client.target,frame(rows)) for rows in (heading,complete)]
        with patch.object(m,'guard',side_effect=frames) as guard,patch.object(m.time,'sleep'):
            _,text=m.claude_complete_response(*args)
        self.assertEqual({'example@market:user':'1.0.0'},validate(text))
        self.assertEqual(2,guard.call_count)
        self.assertEqual([],client.sent)
        for changed in (frame(heading+['❯ /status','❯']),frame(heading+complete),dict(frame(complete),latestCursor='7')):
            with patch.object(m,'guard',return_value=(client.target,changed)),patch.object(m.time,'sleep'):
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
        frames=[(client.target,frame) for frame in (before,early,ready)]
        with patch.object(m,'guard',side_effect=frames) as guard,patch.object(m.time,'sleep'):
            _,text=m.native_query(client,plan,target,self.self_pane,Mock(),'/plugin list --enabled','plugin-preflight',
                completion=(lambda text:m.claude_plugin_listing(text,self.installation),'claude-runtime-plugin-list-unknown'))
        self.assertEqual({'example@market:user':'1.0.0'},m.claude_plugin_listing(text,self.installation))
        self.assertEqual(3,guard.call_count)
        self.assertEqual(1,len(client.sent))

    def test_claude_partial_reload_waits_for_summary_without_resending(self):
        client,plan=self.claude_plan();target=plan['targets'][0]
        initial={'source':'screen','tail':['❯ /reload-plugins','────','❯'],'latestCursor':'6'}
        complete=dict(initial,tail=['❯ /reload-plugins',*client.responses['/reload-plugins'],'────','❯'])
        with patch.object(m,'guard',return_value=(client.target,complete)),patch.object(m.time,'sleep'):
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
                with self.subTest(command=command,case=case), patch.object(m,'guard',side_effect=lambda *a,**k:(client.target,next(first,current))),patch.object(m.time,'sleep'):
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
        identity = {'sessionId': '01a1c848-8ff2-7e90-bcec-44a3ca07a21b', 'cwd': '/work', 'permissions': 'Full Access'}
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


if __name__ == '__main__':
    unittest.main()
