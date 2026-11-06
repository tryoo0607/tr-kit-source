"""Enrollment, effective hooks, chaining and conflict-safe recovery in disposable repositories."""
import json
import os
from pathlib import Path
import subprocess
import unittest

from test_commit_guard import GuardFixture, module

installer = module('git_guard_install', 'git-guard-install.py')


class InstallTests(GuardFixture):
    def setUp(self):
        super().setUp()
        self.state = self.base / 'stable-runtime'

    def enroll(self, **kwargs):
        report = installer.plan(self.repo, self.state, self.scanner, **kwargs)
        installer.apply(report)
        return report

    def test_plan_readonly_bytes_modes_and_rollback(self):
        hooks = self.repo / '.git/hooks'
        original = hooks / 'pre-commit'
        original.write_bytes(b'#!/bin/sh\nexit 0\n# custom bytes\n')
        original.chmod(0o751)
        before = installer.snapshot(original)
        other = hooks / 'post-commit'
        other.write_text('untouched')
        report = installer.plan(self.repo, self.state, self.scanner)
        self.assertEqual(before, installer.snapshot(original))
        self.assertFalse(self.state.exists())
        installer.apply(report)
        self.assertEqual('active', installer.status(self.state)['status'])
        self.stage('clean', 'benign')
        self.git('commit', '-qm', 'test: allowed')
        self.assertEqual('rolled-back', installer.status(self.state, True)['status'])
        self.assertEqual(before, installer.snapshot(original))
        self.assertEqual('untouched', other.read_text())
        self.assertFalse((hooks / 'pre-push').exists())
        self.assertEqual('rolled-back', installer.status(self.state, True)['status'])

    def test_actual_commit_blocks_artifact_and_secret_without_index_mutation(self):
        self.enroll(local_only=['evidence/**'])
        self.stage('evidence/run', 'benign')
        before = self.git('write-tree').stdout
        p = self.git('commit', '-qm', 'test: blocked', check=False)
        self.assertNotEqual(0, p.returncode)
        self.assertIn(b'local-only', p.stderr)
        self.assertEqual(before, self.git('write-tree').stdout)
        self.git('rm', '--cached', 'evidence/run')
        self.stage('file', 'SYNTHETIC_SECRET')
        p = self.git('commit', '-qm', 'test: blocked', check=False)
        self.assertNotEqual(0, p.returncode)
        self.assertNotIn(b'SYNTHETIC_SECRET', p.stderr)

    def test_existing_hook_failure_preserved_and_later_edit_conflict(self):
        hook = self.repo / '.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\nexit 17\n')
        hook.chmod(0o755)
        self.enroll()
        self.stage('clean', 'benign')
        direct = subprocess.run([str(hook)], cwd=self.repo, capture_output=True)
        self.assertEqual(17, direct.returncode)
        p = self.git('commit', '-qm', 'test: rejected by original', check=False)
        self.assertNotEqual(0, p.returncode)
        self.assertFalse(self.git('rev-parse', '--verify', 'HEAD', check=False).returncode == 0)
        hook.write_text('later user edit')
        self.assertEqual('conflict', installer.status(self.state)['status'])
        with self.assertRaisesRegex(installer.InstallError, 'rollback conflict'):
            installer.status(self.state, True)
        self.assertEqual('later user edit', hook.read_text())

    def test_legacy_precommit_cannot_stage_secret_after_initial_guard(self):
        hook = self.repo / '.git/hooks/pre-commit'
        hook.write_text('#!/usr/bin/env python3\nimport subprocess,sys\nfrom pathlib import Path\n'
                        'Path("legacy-args").write_text(repr(sys.argv[1:]))\n'
                        'Path("legacy-secret").write_text("SYNTHETIC_SECRET")\n'
                        'subprocess.run(["git", "add", "--", "legacy-secret"], check=True)\n')
        hook.chmod(0o755)
        self.enroll()
        self.stage('clean', 'benign')
        direct = subprocess.run([str(hook), 'literal arg', '--flag'], cwd=self.repo, capture_output=True)
        self.assertNotEqual(0, direct.returncode)
        self.assertIn(b'secret detected', direct.stderr)
        self.assertNotIn(b'SYNTHETIC_SECRET', direct.stderr)
        self.assertEqual("['literal arg', '--flag']", (self.repo / 'legacy-args').read_text())
        # Restore the initial benign index so the actual commit reaches the legacy hook again.
        self.git('rm', '--cached', 'legacy-secret')
        p = self.git('commit', '-qm', 'test: legacy staging blocked', check=False)
        self.assertNotEqual(0, p.returncode)
        self.assertIn(b'secret detected', p.stderr)
        self.assertNotEqual(0, self.git('rev-parse', '--verify', 'HEAD', check=False).returncode)
        self.assertIn(b'legacy-secret', self.git('diff', '--cached', '--name-only').stdout)

    def test_pre_push_chain_receives_exact_argv_stdin_and_blocks_outgoing_secret(self):
        log = self.base / 'push-log'
        hook = self.repo / '.git/hooks/pre-push'
        hook.write_text('#!/usr/bin/env python3\nimport sys,json\nfrom pathlib import Path\n' +
                        f'Path({str(log)!r}).write_text(json.dumps([sys.argv[1:],sys.stdin.read()]))\n')
        hook.chmod(0o755)
        self.enroll()
        self.stage('clean', 'benign')
        tip = self.commit()
        payload = self.push_data(tip).encode()
        result = subprocess.run([str(hook), 'remote odd', 'url space'], cwd=self.repo, input=payload, capture_output=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([['remote odd', 'url space'], payload.decode()], json.loads(log.read_text()))
        self.stage('bad', 'SYNTHETIC_SECRET')
        bad = self.commit()
        result = subprocess.run([str(hook), 'remote', 'url'], cwd=self.repo, input=self.push_data(bad, tip).encode(), capture_output=True)
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn(b'SYNTHETIC_SECRET', result.stderr)

    def test_actual_push_to_local_bare_remote(self):
        self.enroll()
        remote = self.base / 'remote.git'
        subprocess.run(['git', 'init', '--bare', '-q', str(remote)], check=True)
        subprocess.run(['git', '-C', str(remote), 'config', 'receive.denyDeleteCurrent', 'ignore'], check=True)
        self.git('remote', 'add', 'fixture', str(remote))
        self.stage('clean', 'benign')
        self.git('commit', '-qm', 'test: benign')
        self.git('push', 'fixture', 'HEAD:refs/heads/main')
        self.stage('bad', 'SYNTHETIC_SECRET')
        self.commit()
        p = self.git('push', 'fixture', 'HEAD:refs/heads/main', check=False)
        self.assertNotEqual(0, p.returncode)
        self.assertIn(b'secret detected', p.stderr)
        self.git('push', 'fixture', ':refs/heads/main')

    def test_custom_hooks_path_and_linked_worktree_not_implicitly_enrolled(self):
        custom = self.base / 'custom hooks'
        custom.mkdir()
        self.git('config', 'core.hooksPath', str(custom))
        self.stage('clean', 'benign')
        self.commit()
        linked = self.base / 'linked'
        self.git('worktree', 'add', '-q', str(linked))
        report = self.enroll()
        self.assertEqual(str(custom), report['hooks'])
        # Other worktrees that share hooks remain unenrolled, preserving their original behavior.
        (linked / 'other').write_text('SYNTHETIC_SECRET')
        subprocess.run(['git', '-C', str(linked), 'add', 'other'], check=True)
        subprocess.run(['git', '-C', str(linked), 'commit', '-qm', 'test: unenrolled'], check=True)
        self.assertEqual(str(custom), self.git('config', '--get', 'core.hooksPath').stdout.decode().strip())
        installer.status(self.state, True)
        # Enroll the linked worktree explicitly with its effective common hooks path.
        report = installer.plan(linked, self.base / 'linked-runtime', self.scanner)
        self.assertEqual(str(custom), report['hooks'])
        installer.apply(report)
        (linked / 'new').write_text('SYNTHETIC_SECRET')
        subprocess.run(['git', '-C', str(linked), 'add', 'new'], check=True)
        p = subprocess.run(['git', '-C', str(linked), 'commit', '-qm', 'test: blocked'], capture_output=True)
        self.assertNotEqual(0, p.returncode)

    def test_relative_hooks_path_and_preapply_conflict(self):
        custom = self.repo / 'custom hooks'
        custom.mkdir()
        self.git('config', 'core.hooksPath', 'custom hooks')
        report = installer.plan(self.repo, self.state, self.scanner)
        self.assertEqual(str(custom), report['hooks'])
        hook = custom / 'pre-commit'
        hook.write_text('later user hook')
        with self.assertRaisesRegex(installer.InstallError, 'pre-apply conflict'):
            installer.apply(report)
        self.assertFalse(self.state.exists())
        self.assertEqual('later user hook', hook.read_text())

    def test_preapply_hooks_configuration_drift_changes_no_files(self):
        hooks = self.repo / '.git/hooks'
        original = hooks / 'pre-commit'
        original.write_text('#!/bin/sh\nexit 0\n')
        original.chmod(0o755)
        before = installer.snapshot(original)
        report = installer.plan(self.repo, self.state, self.scanner)
        new_hooks = self.base / 'new-hooks'
        self.git('config', 'core.hooksPath', str(new_hooks))
        with self.assertRaisesRegex(installer.InstallError, 'configuration changed'):
            installer.apply(report)
        self.assertFalse(self.state.exists())
        self.assertFalse(new_hooks.exists())
        self.assertEqual(before, installer.snapshot(original))
        self.assertFalse((hooks / 'pre-push').exists())
        self.assertFalse((hooks / 'pre-commit.tr-kit-original').exists())

    def test_preapply_effective_hooks_path_drift_changes_no_files(self):
        old_hooks = self.base / 'old-hooks'
        new_hooks = self.base / 'new-hooks'
        old_hooks.mkdir()
        new_hooks.mkdir()
        link = self.base / 'hooks-link'
        link.symlink_to(old_hooks, target_is_directory=True)
        self.git('config', 'core.hooksPath', str(link))
        report = installer.plan(self.repo, self.state, self.scanner)
        self.assertEqual(str(old_hooks), report['hooks'])
        link.unlink()
        link.symlink_to(new_hooks, target_is_directory=True)
        with self.assertRaisesRegex(installer.InstallError, 'effective hooks path changed'):
            installer.apply(report)
        self.assertFalse(self.state.exists())
        self.assertEqual([], list(old_hooks.iterdir()))
        self.assertEqual([], list(new_hooks.iterdir()))

    def test_backup_enrollment_verification_and_no_secret_exemption(self):
        with self.assertRaisesRegex(installer.InstallError, 'verified'):
            installer.plan(self.repo, self.state, self.scanner, allow_artifacts=['evidence/**'])
        backup = self.base / 'tr-local-docs'
        self.repo.rename(backup)
        self.repo = backup
        self.enroll(local_only=['_bmad-output/**'], allow_artifacts=['_bmad-output/**'])
        self.stage('_bmad-output/clean', 'benign')
        self.git('commit', '-qm', 'test: backup allowed')
        self.stage('_bmad-output/secret', 'SYNTHETIC_SECRET')
        self.assertNotEqual(0, self.git('commit', '-qm', 'test: backup secret blocked', check=False).returncode)

    def test_backup_allowance_requires_exact_directory_component(self):
        backup = self.base / 'tr-local-docs'
        self.repo.rename(backup)
        self.repo = backup
        for pattern in ('other_bmad-output/**', 'project/other_bmad-output/**', '*/other_bmad-output/**'):
            with self.subTest(pattern=pattern), self.assertRaisesRegex(installer.InstallError, 'explicit'):
                installer.plan(self.repo, self.state, self.scanner, allow_artifacts=[pattern])
        for pattern in ('_bmad-output/**', 'project/_bmad-output/**', '*/_bmad-output/**', '**/_bmad-output/**'):
            with self.subTest(pattern=pattern):
                report = installer.plan(self.repo, self.state, self.scanner, allow_artifacts=[pattern])
                self.assertEqual(str(backup), report['repository'])

    def test_manager_symlink_runtime_and_config_conflicts(self):
        hook = self.repo / '.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\n# generated by pre-commit\n')
        with self.assertRaisesRegex(installer.InstallError, 'unsupported'):
            installer.plan(self.repo, self.state, self.scanner)
        hook.unlink()
        hook.symlink_to(self.scanner)
        with self.assertRaisesRegex(installer.InstallError, 'symlink'):
            installer.plan(self.repo, self.state, self.scanner)
        hook.unlink()
        with self.assertRaisesRegex(installer.InstallError, 'outside'):
            installer.plan(self.repo, self.repo / 'runtime', self.scanner)
        self.enroll()
        self.git('config', 'core.hooksPath', '/later/change')
        with self.assertRaisesRegex(installer.InstallError, 'configuration changed'):
            installer.status(self.state, True)


if __name__ == '__main__':
    unittest.main()

@unittest.skipUnless(os.environ.get('TR_GITLEAKS_TEST_BINARY'), 'real Gitleaks integration is opt-in')
class RealGitHookTests(GuardFixture):
    def test_real_gitleaks_commit_push_and_rollback(self):
        self.scanner = Path(os.environ['TR_GITLEAKS_TEST_BINARY'])
        state = self.base / 'real-runtime'
        installer.apply(installer.plan(self.repo, state, self.scanner))
        self.stage('clean', 'ordinary fixture content')
        self.git('commit', '-qm', 'test: clean real scanner')
        remote = self.base / 'real-remote.git'
        subprocess.run(['git', 'init', '--bare', '-q', str(remote)], check=True)
        self.git('remote', 'add', 'fixture', str(remote))
        self.git('push', 'fixture', 'HEAD:refs/heads/check')
        token = 'ghp_' + 'F7zR4mN8qT2vL6cX9bW3sH5kJ1dP0eA4rU8i'
        self.stage('bad', token)
        before = self.git('write-tree').stdout
        p = self.git('commit', '-qm', 'test: synthetic secret', check=False)
        self.assertNotEqual(0, p.returncode)
        self.assertNotIn(token.encode(), p.stderr)
        self.assertEqual(before, self.git('write-tree').stdout)
        self.commit()
        p = self.git('push', 'fixture', 'HEAD:refs/heads/check', check=False)
        self.assertNotEqual(0, p.returncode)
        self.assertNotIn(token.encode(), p.stderr)
        self.assertEqual('rolled-back', installer.status(state, True)['status'])
