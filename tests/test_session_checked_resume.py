"""Owned exec-gate subprocesses: actual inherited env, mocked native exec only."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
import tempfile
import unittest
import uuid
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'common/base/skills/session/scripts/claude_checked_resume.py'
spec = importlib.util.spec_from_file_location('checked_fixture', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SESSION = '11111111-1111-4111-8111-111111111111'
RUNNER = '''import importlib.util,sys
sys.dont_write_bytecode=True
s=importlib.util.spec_from_file_location('gate',sys.argv[1])
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def owned_exec(fd,args,env):
    assert args == [str(m.Path.home()/'.local/share/claude/versions/2.1.332'),'--dangerously-skip-permissions','--resume',sys.argv[4]]
    print('OWNED_FIXED_EXEC')
m.os.execve=owned_exec
try:
    m.run(sys.argv[2],sys.argv[3])
except (m.Refused,OSError,ValueError,KeyError,TypeError):
    print('OWNED_REFUSED');sys.exit(2)
'''


class CheckedResume(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.state = self.root / 'state'
        self.state.mkdir(mode=0o700)
        self.native = self.home / '.local/share/claude/versions/2.1.332'
        self.native.parent.mkdir(parents=True)
        self.native.write_bytes(b'owned exec mock, never executed')
        self.native.chmod(0o700)
        self.env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        self.env.update(HOME=str(self.home), ORCA_PANE_KEY='owned:pane', OWNED_TOKEN='private-env-fixture')
        self.env.pop('CLAUDE_CONFIG_DIR', None)
        subprocess.run(['/usr/bin/git', '-C', str(self.root), 'init', '--quiet'], env=self.env, check=True)
        raw = Path('/proc/self/stat').read_text().rpartition(') ')[2].split()
        exe = Path('/proc/self/exe')
        info = exe.stat()
        self.shell_executable = dict(path=os.readlink(exe), device=info.st_dev, inode=info.st_ino,
                                     uid=info.st_uid, mode=info.st_mode, mtime=info.st_mtime_ns)
        self.shell = dict(pid=os.getpid(), starttime=int(raw[19]), uid=os.getuid(),
                          sid=int(raw[3]), pgrp=int(raw[2]), tty=int(raw[4]))

    def proof(self, helper=m):
        with patch.dict(os.environ, self.env, clear=True):
            native = dict(sessionId=SESSION, cwd=str(self.root), paneKey='owned:pane',
                          process={'executable': {'path': str(self.native)}},
                          queryExecutable=helper.file_identity(self.native, executable=True))
            launch = dict(environment=helper.environment_proof(dict(os.environb), str(self.root)),
                          shell=self.shell, shellExecutable=self.shell_executable)
            return helper.write_proof(self.state, batch_id=str(uuid.uuid4()), attempt_id=str(uuid.uuid4()),
                                      native=native, launch=launch)

    def run_child(self, proof, env=None, source=SOURCE):
        return subprocess.run([str(Path('/usr/bin/python3').resolve()), '-I', '-S', '-c', RUNNER,
                               str(source), proof['path'], proof['sha256'], SESSION],
                              env=self.env if env is None else env, cwd=self.root,
                              capture_output=True, text=True, timeout=10)

    def test_actual_inherited_environment_execs_once_with_fixed_args(self):
        proof = self.proof()
        result = self.run_child(proof)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual('OWNED_FIXED_EXEC\n', result.stdout)
        self.assertEqual(0o400, Path(proof['path']).stat().st_mode & 0o777)
        reused = self.run_child(proof)
        self.assertEqual(2, reused.returncode)
        self.assertNotIn('OWNED_FIXED_EXEC', reused.stdout)
        self.assertTrue(Path(proof['path'] + '.used').exists())
        self.assertNotIn('private-env-fixture', Path(proof['path']).read_text())
        self.assertNotIn('--dangerously', Path(proof['path']).read_text())

    def test_changed_actual_exports_stop_before_exec_without_parent_environ_authority(self):
        for mutation in ('changed', 'unset', 'profile-path'):
            with self.subTest(mutation=mutation):
                proof = self.proof()
                env = dict(self.env)
                if mutation == 'changed': env['OWNED_TOKEN'] = 'changed-export'
                elif mutation == 'unset': env.pop('OWNED_TOKEN')
                else: env['CLAUDE_CONFIG_DIR'] = str(self.home / '.other')
                result = self.run_child(proof, env)
                self.assertEqual(2, result.returncode, result.stdout + result.stderr)
                self.assertNotIn('OWNED_FIXED_EXEC', result.stdout)
                self.assertTrue(Path(proof['path'] + '.used').exists())
                self.assertTrue(Path(proof['path'] + '.refused').exists())
                self.assertEqual(2, self.run_child(proof).returncode)

    def test_changed_profile_native_and_source_refuse_before_exec(self):
        proof = self.proof()
        (self.home / '.claude.json').write_text('{"owned":"profile-drift"}')
        self.assertEqual(2, self.run_child(proof).returncode)
        (self.home / '.claude.json').unlink()
        proof = self.proof()
        self.native.write_bytes(b'changed native identity')
        self.assertEqual(2, self.run_child(proof).returncode)
        copied = self.root / 'source'
        copied.mkdir()
        for name in ('claude_checked_resume.py', 'claude_live_sessions.py', 'runtime_refresh.py', 'session_restart.py'):
            shutil.copyfile(SOURCE.with_name(name), copied / name)
            (copied / name).chmod(0o600)
        spec = importlib.util.spec_from_file_location('owned_copy', copied / SOURCE.name)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        proof = self.proof(helper)
        with (copied / 'runtime_refresh.py').open('a') as out: out.write('\n# owned source drift\n')
        self.assertEqual(2, self.run_child(proof, source=copied / SOURCE.name).returncode)

    def test_changed_symlinked_or_unsafe_proof_never_executes(self):
        for mutation in ('contents', 'symlink', 'mode', 'hardlink', 'copied'):
            with self.subTest(mutation=mutation):
                proof = self.proof()
                path = Path(proof['path'])
                if mutation == 'contents':
                    path.chmod(0o600)
                    path.write_text(path.read_text().replace(SESSION, str(uuid.uuid4())))
                    path.chmod(0o400)
                elif mutation == 'symlink':
                    saved = path.with_suffix('.saved')
                    path.rename(saved)
                    path.symlink_to(saved)
                elif mutation == 'mode': path.chmod(0o600)
                elif mutation == 'copied':
                    copied = self.root / 'private-copy'
                    copied.mkdir(mode=0o700)
                    shutil.copyfile(path, copied / path.name)
                    (copied / path.name).chmod(0o400)
                    proof['path'] = str(copied / path.name)
                else: os.link(path, path.with_suffix('.linked'))
                result = self.run_child(proof)
                self.assertEqual(2, result.returncode)
                self.assertNotIn('OWNED_FIXED_EXEC', result.stdout)

    def test_isolated_python_does_not_load_sitecustomize_or_pythonpath(self):
        malicious = self.root / 'injection'
        malicious.mkdir()
        marker = self.root / 'unexpected-site-hook'
        (malicious / 'sitecustomize.py').write_text('open(' + repr(str(marker)) + ',"w").write("ran")')
        self.env['PYTHONPATH'] = str(malicious)
        self.env['PYTHONSTARTUP'] = str(malicious / 'sitecustomize.py')
        proof = self.proof()
        result = self.run_child(proof)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertFalse(marker.exists())
        command = m.command(proof)
        self.assertIn(' -I -S ', command)
        self.assertNotIn('private-env-fixture', command)

    def test_inspect_intent_refuses_source_native_or_consumed_proof(self):
        proof = self.proof()
        with patch.dict(os.environ, self.env, clear=True):
            self.assertEqual(SESSION, m.inspect_proof(proof)['sessionId'])
            altered = copy.deepcopy(proof)
            altered['sha256'] = '0' * 64
            with self.assertRaises(m.Refused): m.inspect_proof(altered)
            Path(proof['path'] + '.used').write_text('owned claim')
            with self.assertRaises(m.Refused): m.inspect_proof(proof)



class DataProfile(unittest.TestCase):
    setUp = CheckedResume.setUp
    proof = CheckedResume.proof
    run_child = CheckedResume.run_child

    def profile(self, version='2.1.332'):
        with patch.dict(os.environ, self.env, clear=True):
            return m.environment_proof(dict(os.environb), str(self.root), version=version)

    def write(self, path, value, mode=0o664):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        path.chmod(mode)

    def test_explicit_runtime_projection_all_versions_retains_every_unknown_field(self):
        state = self.home / '.claude.json'
        base = {'account': {'id': 'owned'}, 'mcpServers': {'owned': {'command': 'owned'}},
                'projects': {str(self.root): {'hasTrustDialogAccepted': True, 'allowedTools': ['Read'],
                                            'mcpServers': {'owned': {'command': 'owned'}}}}}
        for version in ('2.1.319', '2.1.329', '2.1.332'):
            with self.subTest(version=version):
                self.write(state, base)
                before = self.profile(version)
                changed = copy.deepcopy(base)
                for key in m.RUNTIME_KEYS[version][0]: changed[key] = {'observed': 2}
                for key in m.RUNTIME_KEYS[version][1]: changed['projects'][str(self.root)][key] = 2
                self.write(state, changed)
                self.assertEqual(before, self.profile(version))
                for unknown in ('cachedUnknownPolicy', 'lastUnknownPreference', 'apiKeyHelper', 'preferences'):
                    drift = copy.deepcopy(changed)
                    drift[unknown] = 'meaningful'
                    self.write(state, drift)
                    self.assertNotEqual(before, self.profile(version), unknown)
        with self.assertRaises(m.Refused): self.profile('2.1.333')

    def test_runtime_only_empty_projects_normalize_without_dropping_meaningful_data(self):
        state = self.home / '.claude.json'
        self.write(state, {'account': 'owned'})
        before = self.profile()
        for projects in ({}, {'/new': {}}, {'/new': {'lastSessionId': 'owned'}}):
            self.write(state, {'account': 'owned', 'projects': projects})
            self.assertEqual(before, self.profile())
        for key, value in (('allowedTools', []), ('hasTrustDialogAccepted', False),
                           ('mcpServers', {}), ('lastUnknownPolicy', None)):
            self.write(state, {'account': 'owned', 'projects': {'/new': {'lastSessionId': 'owned', key: value}}})
            self.assertNotEqual(before, self.profile(), key)

    def test_settings_permissions_mcp_trust_account_and_unknown_changes_are_detected(self):
        state = self.home / '.claude.json'
        for before, after in (({'account': 'one'}, {'account': 'two'}),
                              ({'projects': {'/p': {'hasTrustDialogAccepted': True}}},
                               {'projects': {'/p': {'hasTrustDialogAccepted': False}}}),
                              ({'projects': {'/p': {'allowedTools': ['Read']}}},
                               {'projects': {'/p': {'allowedTools': ['Bash']}}}),
                              ({'projects': {'/p': {'mcpServers': {'x': 1}}}},
                               {'projects': {'/p': {'mcpServers': {'x': 2}}}})):
            self.write(state, before)
            expected = self.profile()
            self.write(state, after)
            self.assertNotEqual(expected, self.profile())
        settings = self.home / '.claude/settings.json'
        self.write(settings, {'permissions': {'allow': ['Read']}})
        expected = self.profile()
        info = settings.stat()
        original = settings.read_text()
        settings.write_text(original.replace('Read', 'Bash'))  # Same size and mtime.
        os.utime(settings, ns=(info.st_atime_ns, info.st_mtime_ns))
        self.assertEqual(info.st_size, settings.stat().st_size)
        self.assertNotEqual(expected, self.profile())
        for relative in ('.mcp.json', '.claude/settings.local.json'):
            path = self.root / relative
            self.write(path, {'servers': {'x': 1}})
            expected = self.profile()
            self.write(path, {'servers': {'x': 2}})
            self.assertNotEqual(expected, self.profile())
        credential = self.home / '.claude/.credentials.json'
        self.write(credential, {'accessToken': 'one'}, 0o600)
        expected = self.profile()
        self.write(credential, {'accessToken': 'two'}, 0o600)
        self.assertNotEqual(expected, self.profile())  # No account-refresh exception.

    def test_custom_config_directory_is_unsupported_without_any_data_change(self):
        custom = self.home / '.alternate-claude'
        self.write(custom / 'settings.json', {'permissions': {'allow': ['Read']}})
        self.env['CLAUDE_CONFIG_DIR'] = str(custom)
        with self.assertRaises(m.Refused): self.profile()
        self.assertEqual({'permissions': {'allow': ['Read']}}, json.loads((custom / 'settings.json').read_text()))

    def test_benign_0664_data_and_replacement_do_not_freeze_inode_or_timestamp(self):
        state = self.home / '.claude.json'
        self.write(state, {'account': 'owned', 'numStartups': 1})
        self.write(self.home / '.claude/settings.json', {'permissions': {'allow': ['Read']}})
        expected = self.profile()
        proof = self.proof()
        replacement = state.with_suffix('.pending')
        self.write(replacement, {'account': 'owned', 'numStartups': 2,
                                 'projects': {'/new': {'lastSessionId': 'owned'}}})
        os.replace(replacement, state)
        self.assertEqual(expected, self.profile())
        result = self.run_child(proof)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual('OWNED_FIXED_EXEC\n', result.stdout)
        settings = self.home / '.claude/settings.json'
        replacement = settings.with_suffix('.pending')
        self.write(replacement, {'permissions': {'allow': ['Read']}})
        os.replace(replacement, settings)
        self.assertEqual(expected, self.profile())

    def test_duplicate_json_unsafe_files_and_read_races_refuse(self):
        path = self.home / '.claude/settings.json'
        self.write(path, {'owned': 1})
        for data in ('{"owned":1,"owned":2}', '{"nested":{"x":1,"x":2}}', '{"x":NaN}'):
            path.write_text(data)
            with self.assertRaises((m.Refused, ValueError)): self.profile()
        self.write(path, {'owned': 1}, 0o666)
        with self.assertRaises(m.Refused): self.profile()
        self.write(path, {'owned': 1})
        original = m.os.fstat
        calls = [0]
        def changed(fd):
            info = original(fd)
            calls[0] += 1
            if calls[0] == 2:
                values = {key: getattr(info, key) for key in ('st_dev', 'st_ino', 'st_uid', 'st_gid', 'st_mode',
                          'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')}
                values['st_ctime_ns'] += 1
                return SimpleNamespace(**values)
            return info
        with patch.object(m.os, 'fstat', side_effect=changed):
            with self.assertRaises(m.Refused): m.stable_data(path)
        stored = path.with_suffix('.stored')
        path.rename(stored)
        path.symlink_to(stored)
        with self.assertRaises(m.Refused): self.profile()

    def auth_inputs(self):
        self.env.update(GIT_TERMINAL_PROMPT='0', GIT_ASKPASS=str(self.root / 'never-execute-askpass'),
                        GIT_CONFIG_COUNT='2', GIT_CONFIG_KEY_0='credential.interactive',
                        GIT_CONFIG_VALUE_0='never', GIT_CONFIG_KEY_1='credential.guiPrompt',
                        GIT_CONFIG_VALUE_1='false')

    def test_auth_only_git_inputs_are_removed_only_from_discovery_child(self):
        baseline = self.profile()
        self.auth_inputs()
        original_env = dict(self.env)
        run = m.subprocess.run
        probes = []
        def probe(*args, **kwargs):
            probes.append(True)
            self.assertFalse(any(key.startswith(b'GIT_') for key in kwargs['env']))
            self.assertEqual('rev-parse', args[0][3])
            self.assertEqual(['--path-format=absolute', '--show-toplevel', '--git-common-dir',
                              '--is-bare-repository'], args[0][4:])
            return run(*args, **kwargs)
        with patch.object(m.subprocess, 'run', side_effect=probe):
            actual = self.profile()
        self.assertTrue(probes)
        self.assertTrue(self.env == original_env)  # Do not dump inherited values on assertion failure.
        self.assertEqual(baseline['profileSha256'], actual['profileSha256'])
        self.assertNotEqual(baseline['environmentSha256'], actual['environmentSha256'])

    def test_git_auth_count_and_index_shape_is_bounded_complete_and_exact(self):
        for count in (None, b'', b'0', b'1', b'2'):
            values = {b'HOME': os.fsencode(self.home), b'GIT_ASKPASS': b'/owned/never-executed'}
            if count is not None: values[b'GIT_CONFIG_COUNT'] = count
            n = int(count or b'0')
            for index, name in enumerate((b'credential.interactive', b'credential.guiprompt')[:n]):
                values[b'GIT_CONFIG_KEY_' + str(index).encode()] = name
                values[b'GIT_CONFIG_VALUE_' + str(index).encode()] = b'false'
            self.assertFalse(any(key.startswith(b'GIT_') for key in m.git_discovery_environment(values)))
        for count in (b'-1', b'3', b'999999999999999999999999', b'01', b'+1', b'bad', b' '):
            with self.subTest(count=count), self.assertRaises(m.Refused):
                m.git_discovery_environment({b'GIT_CONFIG_COUNT': count})
        malformed = [
            {b'GIT_CONFIG_KEY_0': b'credential.interactive'},
            {b'GIT_CONFIG_COUNT': b'0', b'GIT_CONFIG_KEY_0': b'credential.interactive'},
            {b'GIT_CONFIG_COUNT': b'1', b'GIT_CONFIG_KEY_0': b'credential.interactive'},
            {b'GIT_CONFIG_COUNT': b'1', b'GIT_CONFIG_VALUE_0': b'false'},
            {b'GIT_CONFIG_COUNT': b'1', b'GIT_CONFIG_KEY_1': b'credential.interactive', b'GIT_CONFIG_VALUE_1': b'false'},
            {b'GIT_CONFIG_COUNT': b'1', b'GIT_CONFIG_KEY_00': b'credential.interactive', b'GIT_CONFIG_VALUE_00': b'false'},
            {b'GIT_CONFIG_COUNT': b'2', b'GIT_CONFIG_KEY_0': b'credential.interactive', b'GIT_CONFIG_VALUE_0': b'false',
             b'GIT_CONFIG_KEY_1': b'credential.interactive', b'GIT_CONFIG_VALUE_1': b'never'},
        ]
        for values in malformed:
            with self.subTest(values_index=len(values)), self.assertRaises(m.Refused):
                m.git_discovery_environment(values)

    def test_unknown_git_context_and_config_injection_refuse_before_any_subprocess(self):
        self.auth_inputs()
        with patch.dict(os.environ, self.env, clear=True):
            original = dict(os.environb)
        for key in (b'core.worktree', b'core.hooksPath', b'core.fsmonitor', b'include.path',
                    b'includeIf.gitdir:/owned.path', b'alias.rev-parse', b'credential.helper',
                    b'credential.provider', b'credential.https://owned.invalid.interactive', b'unknown.option'):
            values = dict(original)
            values[b'GIT_CONFIG_KEY_0'] = key
            values[b'GIT_CONFIG_VALUE_0'] = b'!owned-never-execute'
            with self.subTest(config_class=key), patch.object(m.subprocess, 'run') as run:
                with self.assertRaises(m.Refused): m.project_roots(self.root, values)
                run.assert_not_called()
        for key in (b'GIT_DIR', b'GIT_WORK_TREE', b'GIT_COMMON_DIR', b'GIT_CONFIG_PARAMETERS',
                    b'GIT_CONFIG_GLOBAL', b'GIT_TRACE', b'GIT_UNKNOWN'):
            values = dict(original)
            values[key] = b'/owned/untrusted'
            with self.subTest(context=key), patch.object(m.subprocess, 'run') as run:
                with self.assertRaises(m.Refused): m.project_roots(self.root, values)
                run.assert_not_called()
        for key, value in ((b'GIT_CONFIG_VALUE_0', b'!owned-never-execute'),
                           (b'GIT_CONFIG_VALUE_1', b'not-a-boolean'),
                           (b'GIT_TERMINAL_PROMPT', b'!owned-never-execute'),
                           (b'GIT_ASKPASS', b'/owned/path\nwrong'),
                           (b'GIT_CONFIG_KEY_0', b'credential.interactive\ninclude.path')):
            values = dict(original)
            values[key] = value
            with self.subTest(field=key), patch.object(m.subprocess, 'run') as run:
                with self.assertRaises(m.Refused): m.project_roots(self.root, values)
                run.assert_not_called()

    def test_auth_inputs_never_execute_askpass_and_native_exec_keeps_original_env(self):
        self.auth_inputs()
        marker = self.root / 'askpass-must-not-run'
        askpass = Path(self.env['GIT_ASKPASS'])
        askpass.write_text('#!/bin/sh\ntouch ' + str(marker) + '\n')
        askpass.chmod(0o700)
        proof = self.proof()
        checked_runner = RUNNER.replace("    print('OWNED_FIXED_EXEC')", "    assert env == dict(m.os.environ)\n"
            "    assert env['GIT_CONFIG_COUNT'] == '2'\n"
            "    assert env['GIT_CONFIG_KEY_0'] == 'credential.interactive'\n"
            "    assert env['GIT_CONFIG_VALUE_0'] == 'never'\n"
            "    assert env['GIT_CONFIG_KEY_1'] == 'credential.guiPrompt'\n"
            "    assert env['GIT_CONFIG_VALUE_1'] == 'false'\n"
            "    assert 'GIT_ASKPASS' in env and env['GIT_TERMINAL_PROMPT'] == '0'\n"
            "    print('OWNED_FIXED_EXEC')")
        with patch.dict(globals(), {'RUNNER': checked_runner}):
            result = self.run_child(proof)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual('OWNED_FIXED_EXEC\n', result.stdout)
        self.assertFalse(marker.exists())
        contents = Path(proof['path']).read_text()
        self.assertNotIn('GIT_CONFIG', contents)
        self.assertNotIn('credential.interactive', contents)

    def test_changed_auth_env_is_still_rejected_before_native_exec(self):
        self.auth_inputs()
        for field, value in (('GIT_CONFIG_VALUE_0', 'false'), ('GIT_CONFIG_VALUE_1', 'true'),
                             ('GIT_TERMINAL_PROMPT', '1'), ('GIT_ASKPASS', str(self.root / 'other-askpass'))):
            with self.subTest(field=field):
                proof = self.proof()
                changed = dict(self.env)
                changed[field] = value
                result = self.run_child(proof, changed)
                self.assertEqual(2, result.returncode)
                self.assertNotIn('OWNED_FIXED_EXEC', result.stdout)
                self.assertTrue(Path(proof['path'] + '.used').exists())
                self.assertTrue(Path(proof['path'] + '.refused').exists())

    def test_git_root_main_worktree_and_legacy_local_settings_all_remain_bound(self):
        def git(*args):
            return subprocess.run(['/usr/bin/git', '-C', str(self.root), *args], env=self.env,
                                  check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        git('-c', 'user.name=Owned', '-c', 'user.email=owned@example.test', 'commit', '--allow-empty', '-m', 'owned')
        worktree = self.root / 'linked'
        git('worktree', 'add', '--quiet', str(worktree), '-b', 'owned-worktree')
        cwd = worktree / 'nested'
        cwd.mkdir()
        for path in (cwd / '.claude/settings.local.json', worktree / '.claude/settings.local.json',
                     self.root / '.claude/settings.local.json', self.root / '.mcp.json'):
            self.write(path, {'owned': 1})
        def profile():
            with patch.dict(os.environ, self.env, clear=True):
                return m.environment_proof(dict(os.environb), str(cwd))
        expected = profile()
        for path in (cwd / '.claude/settings.local.json', worktree / '.claude/settings.local.json',
                     self.root / '.claude/settings.local.json', self.root / '.mcp.json'):
            self.write(path, {'owned': 2})
            self.assertNotEqual(expected, profile(), str(path))
            self.write(path, {'owned': 1})
        self.assertEqual(expected, profile())
        with patch.dict(os.environ, self.env, clear=True):
            values = dict(os.environb)
            values[b'GIT_WORK_TREE'] = os.fsencode(self.root)
            with self.assertRaises(m.Refused): m.environment_proof(values, str(cwd))
            with patch.object(m.Path, 'exists', return_value=False), patch.object(m.Path, 'is_symlink', return_value=False):
                with self.assertRaises(m.Refused): m.project_roots(cwd, values)
        git_marker = worktree / '.git'
        with patch.object(m, 'owned_entry', wraps=m.owned_entry) as guarded:
            profile()
            self.assertTrue(any(call.args[0] == git_marker for call in guarded.call_args_list))
        info = git_marker.lstat()
        with patch.object(m.os, 'getuid', return_value=info.st_uid + 1):
            with self.assertRaises(m.Refused): m.owned_entry(git_marker, directory=False)


if __name__ == '__main__':
    unittest.main()
