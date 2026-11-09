"""Isolated Git fixtures; synthetic strings only, scanner diagnostics never disclosed."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'common/base/scripts' / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

guard = module('commit_guard', 'commit-guard.py')


class GuardFixture(unittest.TestCase):
    def setUp(self):
        environment = mock.patch.dict(os.environ, {'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_NOSYSTEM': '1'})
        environment.start()
        self.addCleanup(environment.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'core.excludesFile', '/dev/null')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.scanner = self.base / 'scanner'
        self.scanner.write_text('''#!/usr/bin/env python3
import sys,os,json
from pathlib import Path
if sys.argv[1] == 'version':
 print('8.30.1');sys.exit(0)
assert not any(k.startswith('GITLEAKS_') for k in os.environ)
assert '--ignore-gitleaks-allow' in sys.argv
assert '--config' in sys.argv and '--gitleaks-ignore-path' in sys.argv
files = [p for p in Path(sys.argv[2]).iterdir() if b'SYNTHETIC_SECRET' in p.read_bytes()]
Path(sys.argv[sys.argv.index('--report-path')+1]).write_text(json.dumps([{'File': str(p)} for p in files]))
sys.exit(42 if files else 0)
''')
        self.scanner.chmod(0o755)
        self.policy = self.base / 'policy.json'
        self.entry = {'path': str(self.repo), 'local_only': ['evidence/**'], 'allow_artifacts': []}
        self.save_policy()

    def save_policy(self):
        self.policy.write_text(json.dumps({'gitleaks': str(self.scanner), 'repositories': [self.entry]}))

    def git(self, *args, check=True, input=None):
        return subprocess.run(['git', '-C', str(self.repo), *args], capture_output=True, check=check, input=input)

    def stage(self, name, text):
        p = self.repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        self.git('add', '--', name)

    def commit(self):
        self.git('-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'test: fixture')
        return self.git('rev-parse', 'HEAD').stdout.decode().strip()

    def push_data(self, local, remote='0'*40):
        return f'refs/heads/main {local} refs/heads/main {remote}\n'


class CommitGuardTests(GuardFixture):
    def test_unborn_odd_names_and_partial_staging(self):
        for name in ['-option', 'space name', 'line\nbreak', '한국어']:
            self.stage(name, 'benign\n')
        (self.repo / 'space name').write_text('SYNTHETIC_SECRET')
        before = self.git('write-tree').stdout
        guard.check_index(self.repo, self.policy)
        self.assertEqual(before, self.git('write-tree').stdout)
        self.git('add', '--', 'space name')
        with self.assertRaisesRegex(guard.GuardError, 'secret detected'):
            guard.check_index(self.repo, self.policy)
        self.assertIn('SYNTHETIC_SECRET', (self.repo / 'space name').read_text())

    def test_colon_filename_uses_its_actual_index_and_outgoing_blob(self):
        self.stage('cover', 'benign')
        self.stage('0:cover', 'SYNTHETIC_SECRET')
        with self.assertRaisesRegex(guard.GuardError, 'secret detected'):
            guard.check_index(self.repo, self.policy)
        tip = self.commit()
        with self.assertRaisesRegex(guard.GuardError, 'secret detected'):
            guard.check_push(self.repo, self.policy, self.push_data(tip))

    def test_gitlink_pointer_without_superproject_object_and_artifact_policy(self):
        sub = self.base / 'submodule'
        subprocess.run(['git', 'init', '-q', str(sub)], check=True)
        subprocess.run(['git', '-C', str(sub), '-c', 'user.name=Fixture',
                        '-c', 'user.email=fixture@example.invalid', 'commit', '--allow-empty',
                        '-qm', 'test: submodule'], check=True)
        oid = subprocess.run(['git', '-C', str(sub), 'rev-parse', 'HEAD'],
                             check=True, capture_output=True).stdout.decode().strip()
        self.assertNotEqual(0, self.git('cat-file', '-e', oid, check=False).returncode)
        self.git('update-index', '--add', '--cacheinfo', '160000', oid, 'module')
        guard.check_index(self.repo, self.policy)
        tip = self.commit()
        guard.check_push(self.repo, self.policy, self.push_data(tip))
        self.git('update-index', '--add', '--cacheinfo', '160000', oid, 'evidence/module')
        with self.assertRaisesRegex(guard.GuardError, 'local-only artifact'):
            guard.check_index(self.repo, self.policy)
        tip = self.commit()
        with self.assertRaisesRegex(guard.GuardError, 'local-only artifact'):
            guard.check_push(self.repo, self.policy, self.push_data(tip))

    def test_registered_artifact_and_explicit_backup_still_scan(self):
        self.stage('evidence/run.txt', 'benign')
        with self.assertRaisesRegex(guard.GuardError, 'local-only'):
            guard.check_index(self.repo, self.policy)
        self.entry['allow_artifacts'] = ['evidence/**']
        self.save_policy()
        guard.check_index(self.repo, self.policy)
        self.stage('evidence/run.txt', 'SYNTHETIC_SECRET')
        with self.assertRaisesRegex(guard.GuardError, 'secret detected'):
            guard.check_index(self.repo, self.policy)

    def test_runs_not_globally_forbidden_and_delete_rename_detached(self):
        self.stage('runs/source.py', 'print(1)')
        guard.check_index(self.repo, self.policy)
        self.commit()
        self.git('checkout', '--detach', '-q')
        self.git('mv', 'runs/source.py', 'renamed')
        guard.check_index(self.repo, self.policy)
        self.commit()
        self.git('rm', 'renamed')
        guard.check_index(self.repo, self.policy)

    def test_push_multiple_refs_tags_deletion_missing_base_and_intermediate_secret(self):
        self.stage('a', 'benign')
        base = self.commit()
        self.stage('a', 'SYNTHETIC_SECRET')
        bad = self.commit()
        self.stage('a', 'benign again')
        tip = self.commit()
        with self.assertRaisesRegex(guard.GuardError, 'secret detected'):
            guard.check_push(self.repo, self.policy, self.push_data(tip, base))
        guard.check_push(self.repo, self.policy, self.push_data('0'*40, tip))
        with self.assertRaisesRegex(guard.GuardError, 'Git inspection'):
            guard.check_push(self.repo, self.policy, self.push_data(tip, 'f'*40))
        self.git('tag', '-a', 'test', '-m', 'tag', base)
        tag = self.git('rev-parse', 'test').stdout.decode().strip()
        guard.check_push(self.repo, self.policy, self.push_data(tag) + self.push_data(base))
        self.git('tag', '-a', 'secret-tag', '-m', 'SYNTHETIC_SECRET', base)
        tag = self.git('rev-parse', 'secret-tag').stdout.decode().strip()
        with self.assertRaisesRegex(guard.GuardError, 'tag object'):
            guard.check_push(self.repo, self.policy, self.push_data(tag))
        self.git('hash-object', '-w', '--stdin', input=b'blob')
        oid = self.git('hash-object', '--stdin', input=b'blob').stdout.decode().strip()
        with self.assertRaises(guard.GuardError):
            guard.check_push(self.repo, self.policy, self.push_data(oid))

    def test_unknown_input_and_shallow_new_branch_fail_closed(self):
        self.stage('a', 'clean')
        tip = self.commit()
        with self.assertRaisesRegex(guard.GuardError, 'malformed'):
            guard.check_push(self.repo, self.policy, 'not ref update')
        shallow = self.base / 'shallow'
        subprocess.run(['git', 'clone', '-q', '--depth=1', self.repo.as_uri(), str(shallow)], check=True)
        self.repo = shallow
        self.entry['path'] = str(shallow)
        self.save_policy()
        with self.assertRaisesRegex(guard.GuardError, 'shallow'):
            guard.check_push(shallow, self.policy, self.push_data(tip))

    def test_scanner_failures_missing_timeout_and_environment(self):
        self.stage('a', 'benign')
        with mock.patch.dict(os.environ, {'GITLEAKS_CONFIG_TOML': 'disable everything'}):
            guard.check_index(self.repo, self.policy)
        self.scanner.write_text('#!/bin/sh\nexit 1\n')
        with self.assertRaisesRegex(guard.GuardError, 'scanner failed'):
            guard.check_index(self.repo, self.policy)
        self.scanner.unlink()
        with self.assertRaisesRegex(guard.GuardError, 'missing'):
            guard.check_index(self.repo, self.policy)
        with mock.patch.object(guard.subprocess, 'run', side_effect=subprocess.TimeoutExpired('scanner', 1)):
            with self.assertRaises(subprocess.TimeoutExpired):
                guard.scan([b'benign'], '/trusted/scanner')

    def test_many_candidates_use_one_scanner_and_private_neutral_files(self):
        for number in range(100):
            self.stage(f'nested/file-{number}.txt', 'clean fixture')
        original = guard.subprocess.run
        calls = []
        def inspect(argv, **kwargs):
            if argv[0] == str(self.scanner):
                calls.append(argv)
                payload = Path(argv[2])
                self.assertEqual(0o700, payload.stat().st_mode & 0o777)
                self.assertEqual(100, len(list(payload.iterdir())))
                for path in payload.iterdir():
                    self.assertEqual(0o600, path.stat().st_mode & 0o777)
                    self.assertTrue(path.name.startswith('candidate-'))
            return original(argv, **kwargs)
        with mock.patch.object(guard.subprocess, 'run', side_effect=inspect):
            guard.check_index(self.repo, self.policy)
        self.assertEqual(1, len(calls))
        self.assertFalse(Path(calls[0][2]).exists())

    def test_push_batches_messages_tags_and_blobs_once(self):
        self.stage('a', 'clean')
        first = self.commit()
        self.stage('b', 'clean too')
        tip = self.commit()
        self.git('tag', '-a', 'batch-tag', '-m', 'clean tag', tip)
        tag = self.git('rev-parse', 'batch-tag').stdout.decode().strip()
        with mock.patch.object(guard, 'scan', wraps=guard.scan) as scan:
            guard.check_push(self.repo, self.policy, self.push_data(tag))
        self.assertEqual(1, scan.call_count)
        labels = [label for label, blob in scan.call_args.args[0]]
        self.assertIn('a', labels)
        self.assertIn('b', labels)
        self.assertTrue(any(label.startswith('tag object ') for label in labels))
        self.assertTrue(any(label.startswith('commit message ') for label in labels))

    def test_malformed_and_unknown_report_paths_fail_closed(self):
        for report in ('{}', '[]', '[{"File":"../candidate-00000000"}]',
                       '[{"File":"candidate-99999999"}]', '[{"File":null}]'):
            self.scanner.write_text('#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\n' +
                                    f'Path(sys.argv[sys.argv.index("--report-path")+1]).write_text({report!r})\n' +
                                    'sys.exit(42)\n')
            with self.assertRaisesRegex(guard.GuardError, 'invalid findings'):
                guard.scan([('safe label', b'fixture')], self.scanner)

    def test_agent_both_products_and_never_evaluates(self):
        for product in ('claude', 'codex'):
            for command in ['git add .', 'git add -A', 'git add --all', 'git -C /tmp add -u',
                            'git commit --no-verify', 'git commit -am test', 'git commit --all', 'git push --no-verify', 'git -c core.hooksPath=/tmp commit',
                            'SKIP=gitleaks git commit', 'git add . && touch /tmp/not-executed']:
                result = guard.agent(product, {'tool_name': 'Bash', 'tool_input': {'command': command}})
                self.assertEqual('deny', result['hookSpecificOutput']['permissionDecision'], command)
            for command in ['git add -- source.py', 'git status', 'git push -n', 'git add -- -A', 'git commit -mthis-message', 'git commit -m "-a"', 'git commit -m "test: okay"']:
                self.assertEqual({}, guard.agent(product, {'tool_input': {'cmd': command}}))

    def test_agent_environment_bypass_scoped_to_literal_commit_push(self):
        for product in ('claude', 'codex'):
            for command in ('SKIP=slow pytest', 'HUSKY=0 npm install --ignore-scripts',
                            'GIT_CONFIG_COUNT=0 python3 fixture.py', 'SKIP=slow git status',
                            'SKIP=slow pytest && git commit -m fixture',
                            'HUSKY=0 npm install --ignore-scripts; git push',
                            'git commit -m "SKIP=fixture"'):
                with self.subTest(product=product, command=command):
                    self.assertEqual({}, guard.agent(product, {'tool_input': {'command': command}}))
            for prefix in ('SKIP=gitleaks', 'HUSKY=0', 'GIT_CONFIG_COUNT=1',
                           'GIT_CONFIG_KEY_0=core.hooksPath'):
                for operation in ('commit -m fixture', 'push'):
                    for command in (f'{prefix} git {operation}',
                                    f'env {prefix} git -C /tmp {operation}',
                                    f'echo fixture && {prefix} git {operation}'):
                        with self.subTest(product=product, command=command):
                            result = guard.agent(product, {'tool_input': {'command': command}})
                            self.assertEqual('deny', result['hookSpecificOutput']['permissionDecision'])

    def test_agent_hookspath_case_variants_both_products(self):
        for product in ('claude', 'codex'):
            for key in ('core.hookspath', 'CORE.HOOKSPATH', 'Core.HooksPath'):
                for command in (f'git -c {key}=/dev/null commit -m fixture',
                                f'git -c{key}=/dev/null push',
                                f'git --config-env {key}=HOOK_PATH push',
                                f'git --config-env={key}=HOOK_PATH commit -m fixture'):
                    with self.subTest(product=product, command=command):
                        result = guard.agent(product, {'tool_input': {'command': command}})
                        self.assertEqual('deny', result['hookSpecificOutput']['permissionDecision'])
            self.assertIsNone(guard.command_reason('git -c note.value=Core.HooksPath status'))

    def test_agent_update_flags_with_explicit_scope_both_products(self):
        for product in ('claude', 'codex'):
            for flag in ('-A', '-u', '--all', '--update'):
                for scope in ('source.py', 'src/', 'src/**', '-A'):
                    command = f'git add {flag} -- {scope}'
                    with self.subTest(product=product, command=command):
                        self.assertEqual({}, guard.agent(product, {'tool_input': {'command': command}}))
                for scope in ('', '.', './', '*', '**', ':/', ':(top)*', ':(glob)**'):
                    command = f'git add {flag}' + (f' -- {scope}' if scope else '')
                    with self.subTest(product=product, command=command):
                        result = guard.agent(product, {'tool_input': {'command': command}})
                        self.assertEqual('deny', result['hookSpecificOutput']['permissionDecision'])


@unittest.skipUnless(os.environ.get('TR_GITLEAKS_TEST_BINARY'), 'set TR_GITLEAKS_TEST_BINARY for pinned real-scanner integration')
class RealGitleaksTests(GuardFixture):
    def test_actual_clean_secret_and_trusted_config(self):
        self.scanner = Path(os.environ['TR_GITLEAKS_TEST_BINARY'])
        self.save_policy()
        self.stage('clean', 'plain fixture text')
        guard.check_index(self.repo, self.policy)
        # Runtime assembly avoids embedding a usable credential; the token is synthetic.
        token = 'ghp_' + 'F7zR4mN8qT2vL6cX9bW3sH5kJ1dP0eA4rU8i'
        self.stage('secret', token + ' # gitleaks:allow')
        (self.repo / '.gitleaks.toml').write_text('title="disable"\n')
        with mock.patch.dict(os.environ, {'GITLEAKS_CONFIG_TOML': 'title="disable"'}):
            with self.assertRaisesRegex(guard.GuardError, 'secret detected'):
                guard.check_index(self.repo, self.policy)

    def test_actual_arbitrary_filenames_and_binary_adjacent_credentials(self):
        self.scanner = Path(os.environ['TR_GITLEAKS_TEST_BINARY'])
        token = ('ghp_' + 'F7zR4mN8qT2vL6cX9bW3sH5kJ1dP0eA4rU8i').encode()
        for label in ('package-lock.json', 'vendor/secret.svg', 'image.png', 'fixture.test', 'odd\nname'):
            for data in (token, b'\x00\xffprefix\n' + token + b'\n\x00suffix'):
                with self.subTest(label=label, binary=data != token):
                    with self.assertRaisesRegex(guard.GuardError, 'secret detected') as caught:
                        guard.scan([(label, data)], self.scanner)
                    self.assertNotIn(token.decode(), str(caught.exception))

    def test_actual_go_sum_checksum_exception_preserves_secret_checks(self):
        import base64
        import hashlib
        self.scanner = Path(os.environ['TR_GITLEAKS_TEST_BINARY'])
        digest = base64.b64encode(hashlib.sha256(b'synthetic checksum').digest()).decode()
        line = f'cloud.google.com/go/auth v1.2.3 h1:{digest}\n'
        for version in ('v1.2.3', 'v1.2.3/go.mod', 'v0.0.0-20260101000000-abcdefabcdef', 'v2.3.4+incompatible'):
            guard.scan([('nested/go.sum', line.replace('v1.2.3', version).encode())], self.scanner)
        token = 'ghp_' + 'F7zR4mN8qT2vL6cX9bW3sH5kJ1dP0eA4rU8i'
        cases = [
            ('checksums.txt', line),
            ('go.sum', line.replace('h1:', 'h2:')),
            ('go.sum', line.replace(digest, digest[:-3] + 'abc')),
            ('go.sum', line.rstrip() + ' extra\n'),
            ('go.sum', line + token),
            ('go.sum', line.replace('cloud.google.com/go/auth', 'github.com/' + token)),
        ]
        for label, data in cases:
            with self.subTest(label=label, case=cases.index((label, data))):
                with self.assertRaisesRegex(guard.GuardError, 'secret detected'):
                    guard.scan([(label, data.encode())], self.scanner)
        # The exception cannot leak to another candidate in the same invocation.
        with self.assertRaisesRegex(guard.GuardError, 'secret detected'):
            guard.scan([('go.sum', line.encode()), ('other.txt', line.encode())], self.scanner)
        self.save_policy()
        self.stage('go.sum', line)
        guard.check_index(self.repo, self.policy)
        clean = self.commit()
        guard.check_push(self.repo, self.policy, self.push_data(clean))
        self.stage('go.sum', line + token)
        with self.assertRaisesRegex(guard.GuardError, 'secret detected'):
            guard.check_index(self.repo, self.policy)
        dirty = self.commit()
        with self.assertRaisesRegex(guard.GuardError, 'secret detected'):
            guard.check_push(self.repo, self.policy, self.push_data(dirty, clean))

    def test_actual_colon_filename_and_gitlink_pointer(self):
        self.scanner = Path(os.environ['TR_GITLEAKS_TEST_BINARY'])
        self.save_policy()
        self.stage('cover', 'benign')
        token = 'ghp_' + 'F7zR4mN8qT2vL6cX9bW3sH5kJ1dP0eA4rU8i'
        self.stage('0:cover', token)
        with self.assertRaisesRegex(guard.GuardError, 'secret detected'):
            guard.check_index(self.repo, self.policy)
        tip = self.commit()
        with self.assertRaisesRegex(guard.GuardError, 'secret detected'):
            guard.check_push(self.repo, self.policy, self.push_data(tip))
        self.stage('0:cover', 'clean')
        self.git('update-index', '--add', '--cacheinfo', '160000', 'f'*40, 'module')
        guard.check_index(self.repo, self.policy)
        clean_tip = self.commit()
        guard.check_push(self.repo, self.policy, self.push_data(clean_tip, tip))

    def test_actual_scanner_error_is_distinct_and_redacted(self):
        real = str(Path(os.environ['TR_GITLEAKS_TEST_BINARY']).resolve())
        self.scanner.write_text('#!/usr/bin/env python3\nimport os,sys\n' +
                                f'os.execv({real!r}, [{real!r}, "--fixture-unknown-flag", *sys.argv[1:]])\n')
        self.save_policy()
        self.stage('clean', 'plain fixture')
        with self.assertRaisesRegex(guard.GuardError, 'scanner failed'):
            guard.check_index(self.repo, self.policy)


if __name__ == '__main__':
    unittest.main()
