"""Synthetic official JSON and owned fake proc trees; no user native lookup."""
import copy
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / 'common/base/skills/session/scripts'

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

m = module('live_fixture', ROOT / 'claude_live_sessions.py')
rr = module('refresh_fixture', ROOT / 'runtime_refresh.py')
ORIGINAL_PROCESS = m.process
SESSION = '01a1c848-8ff2-7e90-bcec-44a3ca07a21b'


class Live(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / 'home'
        self.proc = self.root / 'proc'
        self.pid = 123
        self.path = self.proc / str(self.pid)
        (self.path / 'ns').mkdir(parents=True)
        (self.proc / 'self/ns').mkdir(parents=True)
        (self.path / 'ns/pid').symlink_to('pid:[42]')
        (self.proc / 'self/ns/pid').symlink_to('pid:[42]')
        self.exe = self.home / '.local/share/claude/versions/2.1.331'
        self.exe.parent.mkdir(parents=True)
        self.exe.write_bytes(b'owned native fixture')
        self.exe.chmod(0o700)
        (self.path / 'exe').symlink_to(self.exe)
        (self.path / 'cwd').symlink_to('/work')
        self.write_stat()
        self.write_status()
        (self.path / 'environ').write_bytes(b'UNRELATED_SECRET=never-export\0ORCA_PANE_KEY=tab:manual\0')
        self.rows = [{'pid': self.pid, 'cwd': '/work', 'kind': 'interactive', 'sessionId': SESSION,
                      'startedAt': 100000000, 'name': 'SECRET NAME', 'status': 'active'}]
        self.queries = []
        self.mutate = None
        self.json_calls = 0
        original_process = ORIGINAL_PROCESS
        self.patches = [patch.object(m.Path, 'home', return_value=self.home),
                        patch.object(m.shutil, 'which', return_value=str(self.exe)),
                        patch.object(m, 'process', side_effect=lambda adapter, pid:
                                     original_process(adapter, pid, proc_root=self.proc, home=self.home)),
                        patch.object(rr, 'native_command', side_effect=self.native)]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def write_stat(self, start=100):
        fields = ['S'] + ['0'] * 18 + [str(start)]
        (self.path / 'stat').write_text(str(self.pid) + ' (claude worker) ' + ' '.join(fields))

    def write_status(self, uid=None, nspid=None):
        uid = os.getuid() if uid is None else uid
        (self.path / 'status').write_text('Uid:\t' + '\t'.join([str(uid)]*4) + '\nNSpid:\t' +
                                         (str(self.pid) if nspid is None else nspid) + '\n')

    def native(self, provider, args, cwd, *, executable=None):
        self.assertEqual('claude', provider)
        self.assertEqual('/work', cwd)
        self.assertEqual(str(self.exe), executable)
        self.queries.append(args)
        if args == ['--version']:
            return '2.1.331 (Claude Code)\n'
        self.assertEqual(['agents', '--json'], args)
        self.json_calls += 1
        if self.mutate and self.json_calls == 2:
            self.mutate()
        return json.dumps(self.rows)

    def observe(self):
        return m.observe(rr, '/work', 'tab:manual', expected=SESSION)

    def test_live_identity_discards_volatile_fields_and_uses_proc_start(self):
        result = self.observe()
        self.assertEqual(100, result['process']['startTicks'])
        self.assertEqual(SESSION, result['sessionId'])
        self.assertFalse({'startedAt', 'name', 'status'} & result.keys())
        self.assertNotIn('SECRET', str(result))
        self.assertNotIn('never-export', str(result))
        m.validate(rr, result)
        m.recheck(rr, result)
        self.assertEqual([['--version'], ['agents', '--json'], ['agents', '--json']], self.queries)

    def test_changed_status_and_started_at_are_not_identity_authority(self):
        def drift():
            self.rows[0].update(status='busy', name='changed', startedAt={'arbitrary': 'metadata'})
        self.mutate = drift
        self.observe()

    def test_new_boot_or_pid_can_reprove_same_uuid_without_old_process(self):
        old = self.observe()
        self.write_stat(200)
        (self.path / 'ns/pid').unlink()
        (self.proc / 'self/ns/pid').unlink()
        (self.path / 'ns/pid').symlink_to('pid:[43]')
        (self.proc / 'self/ns/pid').symlink_to('pid:[43]')
        fresh = self.observe()
        self.assertNotEqual(old, fresh)
        with self.assertRaises(rr.Deferred):
            m.recheck(rr, old)

    def test_supported_older_executables_and_new_pid_are_freshly_proved(self):
        for version in ('2.1.319', '2.1.329'):
            old_exe = self.exe.with_name(version)
            old_exe.write_bytes(b'owned older native fixture')
            old_exe.chmod(0o700)
            (self.path/'exe').unlink(); (self.path/'exe').symlink_to(old_exe)
            self.assertEqual(str(old_exe), self.observe()['process']['executable']['path'])
        old = self.observe()
        self.path.rename(self.proc/'456')
        self.path = self.proc/'456'; self.pid = 456
        self.write_stat(200); self.write_status()
        self.rows[0]['pid'] = 456
        fresh = self.observe()
        self.assertEqual(old['sessionId'], fresh['sessionId'])
        self.assertNotEqual(old['pid'], fresh['pid'])

    def test_background_same_pane_and_unreadable_relevant_process_are_barriers(self):
        shutil.copytree(self.path, self.proc/'456', symlinks=True)
        (self.proc/'456/stat').write_text('456 (claude) ' + ' '.join(['S']+['0']*18+['100']))
        (self.proc/'456/status').write_text('Uid:\t'+'\t'.join([str(os.getuid())]*4)+'\nNSpid:\t456\n')
        self.rows.append({**self.rows[0], 'pid': 456, 'kind': 'background',
                          'sessionId': '01a1c848-8ff2-7e90-bcec-44a3ca07a21c'})
        with self.assertRaisesRegex(rr.Deferred, 'ambiguous'): self.observe()
        self.rows[1]['kind'] = 'interactive'
        (self.proc/'456/environ').unlink()
        with self.assertRaisesRegex(rr.Deferred, 'process-unverifiable'): self.observe()
        # An unrelated cwd is outside the bounded relevant process observations.
        self.rows[1]['cwd'] = '/other'
        self.observe()

    def test_known_absence_requires_two_complete_official_responses(self):
        self.rows = []
        proof = m.observe_absent(rr, '/work', 'tab:manual', expected=SESSION)
        self.assertEqual('absent', proof['kind'])
        self.assertEqual(SESSION, proof['sessionId'])
        self.assertNotIn('pid', proof)
        m.recheck(rr, proof)
        # A selected live process in another pane preserves the same absence.
        self.rows = [{'pid': self.pid, 'cwd': '/work', 'kind': 'interactive',
                      'sessionId': '01a1c848-8ff2-7e90-bcec-44a3ca07a21c'}]
        (self.path/'environ').write_bytes(b'ORCA_PANE_KEY=tab:selected\0')
        self.assertEqual(proof, m.observe_absent(rr, '/work', 'tab:manual', expected=SESSION))
        # A failed/unreadable live observation cannot become an empty response.
        (self.path/'environ').unlink()
        with self.assertRaisesRegex(rr.Deferred, 'process-unverifiable'):
            m.observe_absent(rr, '/work', 'tab:manual', expected=SESSION)

    def test_cold_checks_other_cwd_process_for_pane_reuse_and_unreadability(self):
        self.rows[0].update(cwd='/elsewhere', sessionId='01a1c848-8ff2-7e90-bcec-44a3ca07a21c')
        (self.path/'cwd').unlink(); (self.path/'cwd').symlink_to('/elsewhere')
        (self.path/'environ').write_bytes(b'ORCA_PANE_KEY=tab:other\0')
        proof = m.observe_absent(rr, '/work', 'tab:manual', expected=SESSION)
        self.assertEqual('absent', proof['kind'])
        (self.path/'environ').write_bytes(b'ORCA_PANE_KEY=tab:manual\0')
        with self.assertRaisesRegex(rr.Deferred, 'pane-reused'):
            m.observe_absent(rr, '/work', 'tab:manual', expected=SESSION)
        (self.path/'environ').unlink()
        with self.assertRaisesRegex(rr.Deferred, 'process-unverifiable'):
            m.observe_absent(rr, '/work', 'tab:manual', expected=SESSION)

    def test_absence_refuses_expected_uuid_anywhere_and_any_kind_or_pane_reuse(self):
        for kind in ('interactive', 'background'):
            self.rows[0].update(cwd='/elsewhere', kind=kind)
            with self.assertRaisesRegex(rr.Deferred, 'still-live'):
                m.observe_absent(rr, '/work', 'tab:manual', expected=SESSION)
        self.rows[0].update(cwd='/work', sessionId='01a1c848-8ff2-7e90-bcec-44a3ca07a21c')
        with self.assertRaisesRegex(rr.Deferred, 'pane-reused'):
            m.observe_absent(rr, '/work', 'tab:manual', expected=SESSION)
        (self.path/'environ').write_bytes(b'ORCA_PANE_KEY=tab:other\0')
        self.rows[0]['sessionId'] = SESSION
        with self.assertRaisesRegex(rr.Deferred, 'still-live'):
            m.observe_absent(rr, '/work', 'tab:manual', expected=SESSION)

    def test_absence_appearing_in_second_json_and_transport_or_proc_failure_never_prove_absence(self):
        self.rows = []
        def appeared():
            self.rows.append({'pid': self.pid, 'cwd': '/elsewhere', 'kind': 'interactive', 'sessionId': SESSION})
        self.mutate = appeared
        with self.assertRaisesRegex(rr.Deferred, 'still-live'):
            m.observe_absent(rr, '/work', 'tab:manual', expected=SESSION)
        for failure in ('exception-native-json-invalid', 'native-cli-unavailable-or-timeout',
                        'native-cli-diagnostics-unverified', 'exception-live-proof-changed'):
            with patch.object(rr, 'native_command', side_effect=rr.Deferred(failure)), self.assertRaises(rr.Deferred):
                m.observe_absent(rr, '/work', 'tab:manual', expected=SESSION)

    def test_unsafe_process_evidence_refuses_without_export(self):
        cases = ('uid', 'start', 'stat', 'namespace', 'nested-pid', 'missing-nspid', 'environment',
                 'duplicate-pane', 'large-env', 'pane', 'cwd', 'executable', 'unobserved-version', 'writable-executable', 'missing')
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as unused:
                # Isolate mutations by rebuilding each owned fixture.
                fixture = Live('test_live_identity_discards_volatile_fields_and_uses_proc_start')
                fixture.setUp()
                try:
                    if case == 'uid': fixture.write_status(uid=os.getuid()+1)
                    elif case == 'start': fixture.write_stat(0)
                    elif case == 'stat': (fixture.path/'stat').write_text('partial')
                    elif case == 'namespace':
                        (fixture.path/'ns/pid').unlink(); (fixture.path/'ns/pid').symlink_to('pid:[999]')
                    elif case == 'nested-pid': fixture.write_status(nspid='123 2')
                    elif case == 'missing-nspid': (fixture.path/'status').write_text('Uid:\t0\t0\t0\t0\n')
                    elif case == 'environment': (fixture.path/'environ').write_bytes(b'ORCA_PANE_KEY=tab:manual')
                    elif case == 'duplicate-pane': (fixture.path/'environ').write_bytes(b'ORCA_PANE_KEY=a\0ORCA_PANE_KEY=b\0')
                    elif case == 'large-env': (fixture.path/'environ').write_bytes(b'x'*131073)
                    elif case == 'pane': (fixture.path/'environ').write_bytes(b'ORCA_PANE_KEY=other\0')
                    elif case == 'cwd': (fixture.path/'cwd').unlink(); (fixture.path/'cwd').symlink_to('/elsewhere')
                    elif case == 'executable': (fixture.path/'exe').unlink(); (fixture.path/'exe').symlink_to('/bin/sh')
                    elif case == 'unobserved-version':
                        unsupported = fixture.exe.with_name('2.1.330')
                        unsupported.write_bytes(b'owned unobserved native fixture'); unsupported.chmod(0o700)
                        (fixture.path/'exe').unlink(); (fixture.path/'exe').symlink_to(unsupported)
                    elif case == 'writable-executable': fixture.exe.chmod(0o777)
                    elif case == 'missing': (fixture.path/'environ').unlink()
                    with self.assertRaises(rr.Deferred) as error:
                        fixture.observe()
                    self.assertNotIn('SECRET', str(error.exception))
                finally:
                    fixture.doCleanups()

    def test_late_pid_reuse_exec_cwd_pane_namespace_or_uuid_drift_refuses(self):
        for case in ('pid-start', 'exe', 'cwd', 'pane', 'uuid', 'json-pid', 'namespace'):
            with self.subTest(case=case):
                fixture = Live('test_live_identity_discards_volatile_fields_and_uses_proc_start')
                fixture.setUp()
                def drift():
                    if case == 'pid-start': fixture.write_stat(200)
                    elif case == 'exe': fixture.exe.write_bytes(b'replaced executable')
                    elif case == 'cwd': (fixture.path/'cwd').unlink(); (fixture.path/'cwd').symlink_to('/other')
                    elif case == 'pane': (fixture.path/'environ').write_bytes(b'ORCA_PANE_KEY=other\0')
                    elif case == 'uuid': fixture.rows[0]['sessionId'] = '01a1c848-8ff2-7e90-bcec-44a3ca07a21c'
                    elif case == 'json-pid': fixture.rows[0]['pid'] = 456
                    else:
                        (fixture.path/'ns/pid').unlink(); (fixture.path/'ns/pid').symlink_to('pid:[99]')
                fixture.mutate = drift
                try:
                    with self.assertRaises(rr.Deferred): fixture.observe()
                finally:
                    fixture.doCleanups()

    def test_json_partial_duplicate_unknown_wrong_kind_and_uuid_refuse(self):
        valid = json.dumps(self.rows)
        bad = ('{', '{}', '[null]', valid.replace('123', 'true'), valid.replace('interactive', 'unknown'),
               valid.replace(SESSION, 'unknown'), valid.replace('"cwd": "/work"', '"cwd": "relative"'),
               valid.replace('"pid": 123', '"pid": 123, "pid": 123'),
               json.dumps(self.rows*2), ' '*m.MAX_JSON+'[]', '['*2000 + ']'*2000)
        for value in bad:
            with self.subTest(value=value[:80]), self.assertRaises(rr.Deferred):
                m.parse(rr, value)
        self.rows[0]['kind'] = 'background'
        with self.assertRaises(rr.Deferred): self.observe()
        self.rows[0]['kind'] = 'interactive'
        self.rows[0]['sessionId'] = '01a1c848-8ff2-7e90-bcec-44a3ca07a21c'
        with self.assertRaisesRegex(rr.Deferred, 'mismatch'): self.observe()

    def test_transport_diagnostics_partial_and_unproven_producer_refuse(self):
        for failure in ('native-cli-output-limit', 'native-cli-diagnostics-unverified', 'native-cli-failed',
                        'native-cli-unavailable-or-timeout', 'native-cli-cleanup-unverified'):
            with patch.object(rr, 'native_command', side_effect=rr.Deferred(failure)), self.assertRaisesRegex(rr.Deferred, failure):
                self.observe()
        with patch.object(rr, 'native_command', return_value='2.1.329 (Claude Code)'), self.assertRaises(rr.Deferred):
            self.observe()
        with patch.object(m.shutil, 'which', return_value=None), self.assertRaises(rr.Deferred):
            self.observe()


    def test_producer_is_rechecked_around_every_bounded_operation(self):
        for changed_call in (1, 2, 3):
            with self.subTest(changed_call=changed_call):
                fixture = Live('test_live_identity_discards_volatile_fields_and_uses_proc_start')
                fixture.setUp()
                calls = []
                def replaced(provider, args, cwd, *, executable=None):
                    calls.append(args)
                    result = fixture.native(provider, args, cwd, executable=executable)
                    if len(calls) == changed_call:
                        fixture.exe.write_bytes(b'replaced query producer')
                    return result
                try:
                    with patch.object(rr, 'native_command', side_effect=replaced), self.assertRaisesRegex(
                            rr.Deferred, 'proof-changed'):
                        fixture.observe()
                    self.assertEqual(changed_call, len(calls))
                finally:
                    fixture.doCleanups()

    def test_producer_change_before_operation_and_at_final_boundary_stops(self):
        query = m.query_executable(rr)
        self.exe.write_bytes(b'replaced before next bounded operation')
        with patch.object(rr, 'native_command') as native, self.assertRaisesRegex(rr.Deferred, 'proof-changed'):
            m.query_command(rr, query, ['agents', '--json'], '/work')
        native.assert_not_called()
        proof = self.observe()
        self.exe.write_bytes(b'replaced after final native query')
        with self.assertRaisesRegex(rr.Deferred, 'proof-changed'):
            m.recheck(rr, proof)


class ExactProducerTransport(unittest.TestCase):
    """Owned real bounded transport; caller and target resolve relative PATH differently."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / 'home'
        self.caller = self.root / 'caller'
        self.target = self.root / 'target'
        for path in (self.caller / 'relative-bin', self.target / 'relative-bin'):
            path.mkdir(parents=True)
        self.exe = self.home / '.local/share/claude/versions/2.1.331'
        self.exe.parent.mkdir(parents=True)
        self.marker = self.root / 'wrong-producer-invoked'
        self.log = self.root / 'official-invocations'
        self.write_producer()
        (self.caller / 'relative-bin/claude').symlink_to(self.exe)
        alternate = self.target / 'relative-bin/claude'
        alternate.write_text('#!' + sys.executable + '\nfrom pathlib import Path\n'
                             'Path(' + repr(str(self.marker)) + ').write_text("invoked")\n'
                             'print("[]")\n')
        alternate.chmod(0o700)
        original_cwd = Path.cwd()
        os.chdir(self.caller)
        self.addCleanup(os.chdir, original_cwd)
        for item in (patch.dict(os.environ, {'PATH': 'relative-bin'}),
                     patch.object(m.Path, 'home', return_value=self.home)):
            item.start()
            self.addCleanup(item.stop)

    def write_producer(self, extra=''):
        self.exe.write_text('#!' + sys.executable + '\nimport sys\nfrom pathlib import Path\n'
                            'with Path(' + repr(str(self.log)) + ').open("a") as out:\n'
                            '    out.write(" ".join(sys.argv[1:]) + "\\n")\n' + extra +
                            'print("2.1.331 (Claude Code)" if sys.argv[1:] == ["--version"] else "[]")\n')
        self.exe.chmod(0o700)

    def observe(self):
        return m.observe_absent(rr, str(self.target), 'tab:manual', expected=SESSION)

    def test_exact_verified_producer_runs_all_three_queries_under_target_cwd(self):
        self.assertEqual(Path('relative-bin/claude'), Path(shutil.which('claude')))
        proof = self.observe()
        self.assertEqual('absent', proof['kind'])
        self.assertEqual(str(self.exe), proof['queryExecutable']['path'])
        self.assertEqual(['--version', 'agents --json', 'agents --json'], self.log.read_text().splitlines())
        self.assertFalse(self.marker.exists())
        m.recheck(rr, proof)

    def test_real_producer_replacement_during_first_query_stops_without_fallback(self):
        self.write_producer('with Path(__file__).open("a") as own:\n    own.write("# replacement\\n")\n')
        with self.assertRaisesRegex(rr.Deferred, 'proof-changed'):
            self.observe()
        self.assertEqual(['--version'], self.log.read_text().splitlines())
        self.assertFalse(self.marker.exists())

    def test_real_failed_producer_stops_without_fallback_or_next_query(self):
        self.write_producer('sys.exit(3)\n')
        with self.assertRaisesRegex(rr.Deferred, 'native-cli-failed'):
            self.observe()
        self.assertEqual(['--version'], self.log.read_text().splitlines())
        self.assertFalse(self.marker.exists())


class Selected332Launch(unittest.TestCase):
    write_stat = Live.write_stat
    write_status = Live.write_status
    observe = Live.observe

    def setUp(self):
        Live.setUp(self)
        self.exe.rename(self.exe.with_name('2.1.332'))
        self.exe = self.exe.with_name('2.1.332')
        self.patches[1].stop()
        current_path = patch.object(m.shutil, 'which', return_value=str(self.exe))
        current_path.start()
        self.addCleanup(current_path.stop)
        (self.path/'exe').unlink()
        (self.path/'exe').symlink_to(self.exe)
        self.parent = self.proc/'42'
        self.parent.mkdir()
        environment = b'HOME='+os.fsencode(self.home)+b'\0ORCA_PANE_KEY=tab:manual\0TOKEN=opaque-secret\0'
        (self.path/'environ').write_bytes(environment)
        (self.parent/'environ').write_bytes(environment)
        owned_roots = patch.object(m.checked, 'project_roots', return_value=[Path('/work')])
        owned_roots.start()
        self.addCleanup(owned_roots.stop)
        self.arguments = b'claude\0--dangerously-skip-permissions\0'
        (self.path/'cmdline').write_bytes(self.arguments)
        self.child = dict(pid=self.pid, ppid=42, uid=os.getuid(), pgrp=self.pid,
                          sid=42, tty=5, foreground=self.pid, starttime=100)
        self.shell = dict(pid=42, ppid=1, uid=os.getuid(), pgrp=42,
                          sid=42, tty=5, foreground=self.pid, starttime=10)
        self.shell_exe = dict(path=str(Path('/usr/bin/zsh').resolve()), uid=0, mode=0o100755)
        for item in (patch.object(rr, 'proc_process', side_effect=lambda pid, reason:
                                 copy.deepcopy(self.child if pid == self.pid else self.shell)),
                     patch.object(rr, 'proc_executable', return_value=self.shell_exe)):
            item.start()
            self.addCleanup(item.stop)

    def native(self, provider, args, cwd, *, executable=None):
        if args == ['--version']:
            self.queries.append(args)
            return '2.1.332 (Claude Code)\n'
        return Live.native(self, provider, args, cwd, executable=executable)

    def test_selected_launch_strict_classification_and_opaque_environment(self):
        proof = self.observe()
        launch = m.selected_launch(rr, proof, proc_root=self.proc)
        self.assertEqual('fixed-bypass', launch['argumentClass'])
        self.assertNotIn('opaque-secret', str(launch))
        self.assertNotIn('--dangerously', str(launch))
        # Session identity helpers still succeed without reading exception argv.
        (self.path/'cmdline').unlink()
        m.recheck(rr, proof)
        with self.assertRaisesRegex(rr.Deferred, 'options-unverified'):
            m.selected_launch(rr, proof, proc_root=self.proc)

    def test_selected_launch_options_and_environment_drift_are_manual(self):
        proof = self.observe()
        for suffix in (b'--settings\0secret-path\0', b'--plugin-dir\0private-path\0',
                       b'--add-dir\0/tmp\0', b'--mcp-config\0config\0', b'--continue\0',
                       b'--resume\0wrong-uuid\0', b'--dangerously-skip-permissions\0', b'prompt\0'):
            with self.subTest(suffix=suffix):
                (self.path/'cmdline').write_bytes(self.arguments+suffix)
                with self.assertRaisesRegex(rr.Deferred, 'options-unverified'):
                    m.selected_launch(rr, proof, proc_root=self.proc)
        (self.path/'cmdline').write_bytes(self.arguments+b'--resume\0'+SESSION.encode()+b'\0')
        self.assertEqual('fixed-bypass-exact-resume', m.selected_launch(rr, proof, proc_root=self.proc)['argumentClass'])
        (self.parent/'environ').write_bytes((self.parent/'environ').read_bytes().replace(b'opaque-secret', b'drift'))
        # Parent initial environ is not authority for future exports. Only the
        # checked child launcher compares actual inherited environment at exec.
        self.assertEqual('fixed-bypass-exact-resume', m.selected_launch(rr, proof, proc_root=self.proc)['argumentClass'])

    def test_observed_legacy_selected_executables_keep_query332_and_strict_argv(self):
        for version in ('2.1.319', '2.1.329', '2.1.331'):
            with self.subTest(version=version):
                source = self.exe.with_name(version)
                source.write_bytes(b'owned legacy native fixture')
                source.chmod(0o700)
                (self.path / 'exe').unlink()
                (self.path / 'exe').symlink_to(source)
                proof = self.observe()
                if version == '2.1.331':
                    with self.assertRaisesRegex(rr.Deferred, 'source-version-mismatch'):
                        m.selected_launch(rr, proof, proc_root=self.proc)
                else:
                    launch = m.selected_launch(rr, proof, proc_root=self.proc)
                    self.assertEqual('fixed-bypass', launch['argumentClass'])
                    self.assertEqual('2.1.332', proof['producerVersion'])
                    self.assertNotIn('opaque-secret', str(launch))

    def test_original_pid_presence_never_becomes_exit_proof(self):
        proof = self.observe()
        launch = m.selected_launch(rr, proof, proc_root=self.proc)
        with self.assertRaisesRegex(rr.Deferred, 'shell-unconfirmed'):
            m.exited(rr, proof, launch, {'shell': self.shell, 'executable': self.shell_exe})


if __name__ == '__main__':
    unittest.main()
