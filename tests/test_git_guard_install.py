"""Explicit enrollment tested only with disposable Git repositories/local remotes."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest import mock

from test_secret_legacy import GuardFixture, ROOT, guard, REAL_TRUSTED_SCANNER

sys.path.insert(0,str(ROOT/'common/base/scripts'))
import git_guard_install as installer


class InstallTests(GuardFixture):
    def setUp(self):
        super().setUp()
        self.state=self.base/'stable runtime'
        self.real_scanner=REAL_TRUSTED_SCANNER()
        self.hooks=self.repo/'.git/hooks'
        self.key='ghp_'+hashlib.sha256(b'G1 synthetic no real account').hexdigest()[:36]

    def plan(self,**kwargs):
        return installer.plan(self.repo,self.state,self.real_scanner,**kwargs)

    def enroll(self,**kwargs):
        report=self.plan(**kwargs)
        installer.apply(report,installer.plan_id(report))
        return report

    def custom(self,event,body,mode=0o755):
        p=self.hooks/event;p.write_text(body);p.chmod(mode);return p

    def cli(self,action,*args):
        return subprocess.run([sys.executable,'-B',str(ROOT/'scripts/git-guard-install.py'),
             action,'--state',str(self.state),*args],capture_output=True)

    def test_readonly_plan_public_receipt_and_byte_mode_restore(self):
        hook=self.custom('pre-commit','#!/bin/sh\n# custom\nexit 0\n',0o751)
        before=installer.snapshot(hook)
        post=self.hooks/'post-commit';post.write_text('unrelated')
        report=self.plan()
        self.assertEqual(before,installer.snapshot(hook));self.assertFalse(self.state.exists())
        self.assertNotIn('bytes',json.dumps(installer.public(report)))
        installer.apply(report,installer.plan_id(report))
        self.assertEqual('active',installer.status(self.state)['status'])
        self.assertEqual(0o700,self.state.stat().st_mode & 0o777)
        self.assertEqual(0o600,(self.state/'receipt.json').stat().st_mode & 0o777)
        self.stage('clean','benign');self.git('commit','-qm','test: clean')
        self.assertEqual('rolled-back',installer.status(self.state,True)['status'])
        self.assertEqual(before,installer.snapshot(hook));self.assertFalse((self.hooks/'pre-push').exists())
        self.assertEqual('unrelated',post.read_text())
        self.assertEqual('rolled-back',installer.status(self.state,True)['status'])
        self.assertFalse(list(self.state.rglob('gitleaks')))

    def test_actual_commit_blocks_artifact_and_secret_without_index_mutation(self):
        self.enroll(local_only=['evidence/**'])
        self.stage('evidence/run.txt','benign');before=self.git('write-tree').stdout
        bad=self.git('commit','-qm','test: blocked',check=False)
        self.assertNotEqual(0,bad.returncode);self.assertIn(b'policy_violation',bad.stdout+bad.stderr)
        self.assertEqual(before,self.git('write-tree').stdout)
        self.git('rm','--cached','evidence/run.txt');self.stage('fixture',self.key)
        bad=self.git('commit','-qm','test: secret',check=False)
        self.assertNotEqual(0,bad.returncode);self.assertNotIn(self.key.encode(),bad.stdout+bad.stderr)

    def test_original_exit_and_arguments_preserved(self):
        log=self.base/'args'
        hook=self.custom('pre-commit','#!/usr/bin/env python3\nimport sys,json\nfrom pathlib import Path\n'+
                         f'Path({str(log)!r}).write_text(json.dumps(sys.argv[1:]))\nraise SystemExit(17)\n')
        self.enroll();self.stage('clean','benign')
        p=subprocess.run([str(hook),'literal arg','--flag'],cwd=self.repo,capture_output=True)
        self.assertEqual(17,p.returncode)
        self.assertEqual(['literal arg','--flag'],json.loads(log.read_text()))

    def test_existing_precommit_cannot_stage_secret_after_first_check(self):
        self.custom('pre-commit','#!/usr/bin/env python3\nimport subprocess\nfrom pathlib import Path\n'+
                    f'Path("injected").write_text({self.key!r})\n'+
                    'subprocess.run(["git","add","--","injected"],check=True)\n')
        self.enroll();self.stage('clean','benign')
        p=self.git('commit','-qm','test: hook mutation',check=False)
        self.assertNotEqual(0,p.returncode);self.assertIn(b'finding',p.stdout+p.stderr)
        self.assertNotIn(self.key.encode(),p.stdout+p.stderr)
        self.assertNotEqual(0,self.git('rev-parse','--verify','HEAD',check=False).returncode)
        self.assertIn(b'injected',self.git('diff','--cached','--name-only').stdout)

    def test_prepush_exact_stdin_argv_and_original_failure(self):
        log=self.base/'push-log'
        hook=self.custom('pre-push','#!/usr/bin/env python3\nimport sys,json\nfrom pathlib import Path\n'+
             f'Path({str(log)!r}).write_text(json.dumps([sys.argv[1:],sys.stdin.read()]))\nraise SystemExit(19)\n')
        self.stage('clean','benign');tip=self.commit();self.enroll()
        data=self.push_data(tip).encode()
        p=subprocess.run([str(hook),'remote odd','url space'],cwd=self.repo,input=data,capture_output=True)
        self.assertEqual(19,p.returncode)
        self.assertEqual([['remote odd','url space'],data.decode()],json.loads(log.read_text()))

    def test_actual_local_bare_remote_push_blocked_and_delete_ref_supported(self):
        self.enroll();remote=self.base/'remote.git'
        subprocess.run(['git','init','--bare','-q',str(remote)],check=True)
        self.git('remote','add','fixture',str(remote));self.stage('clean','benign')
        self.git('commit','-qm','test: clean');self.git('push','fixture','HEAD:refs/heads/main')
        original=subprocess.run(['git','--git-dir',str(remote),'rev-parse','refs/heads/main'],capture_output=True,check=True).stdout
        self.stage('secret',self.key);tree=self.git('write-tree').stdout.decode().strip()
        # Create the outgoing fixture without disabling or bypassing any hook.
        tip=self.git('commit-tree',tree,'-p','HEAD',input=b'test: synthetic outgoing\n').stdout.decode().strip()
        bad=self.git('push','fixture',tip+':refs/heads/main',check=False)
        self.assertNotEqual(0,bad.returncode);self.assertNotIn(self.key.encode(),bad.stdout+bad.stderr)
        after=subprocess.run(['git','--git-dir',str(remote),'rev-parse','refs/heads/main'],capture_output=True,check=True).stdout
        self.assertEqual(original,after)
        self.git('push','fixture',':refs/heads/main')

    def test_custom_hooks_scan_linked_worktree_and_preserve_original(self):
        self.stage('clean','benign');self.commit()
        linked=self.base/'linked';self.git('worktree','add','-q',str(linked))
        hooks=self.base/'custom hooks';hooks.mkdir();self.git('config','core.hooksPath',str(hooks))
        self.hooks=hooks
        log=self.base/'original-ran'
        self.custom('pre-commit',f'#!/bin/sh\nprintf ran >> {str(log)!r}\n')
        report=self.enroll();self.assertEqual(str(hooks),report['hooks'])
        (linked/'other').write_text(self.key)
        subprocess.run(['git','-C',str(linked),'add','--','other'],check=True)
        p=subprocess.run(['git','-C',str(linked),'commit','-qm','test: linked finding'],capture_output=True)
        self.assertNotEqual(0,p.returncode);self.assertIn(b'finding',p.stdout+p.stderr)
        self.assertFalse(log.exists())
        (linked/'other').write_text('benign')
        subprocess.run(['git','-C',str(linked),'add','--','other'],check=True)
        subprocess.run(['git','-C',str(linked),'commit','-qm','test: linked clean'],check=True)
        self.assertEqual('ran',log.read_text())
        foreign=self.base/'foreign'
        subprocess.run(['git','init','-q',str(foreign)],check=True)
        subprocess.run(['git','-C',str(foreign),'config','core.hooksPath',str(hooks)],check=True)
        self.assertEqual('uncovered',installer.status(self.state,repo=foreign)['status'])
        blocked=subprocess.run([str(hooks/'pre-commit')],cwd=foreign,capture_output=True)
        self.assertNotEqual(0,blocked.returncode)
        self.assertEqual('ran',log.read_text())
        self.assertEqual(str(hooks),self.git('config','--get','core.hooksPath').stdout.decode().strip())
        self.assertEqual('rolled-back',installer.status(self.state,True)['status'])

    def test_new_linked_worktree_checks_its_index_and_outgoing_refs_on_demand(self):
        self.stage('base','benign');self.commit()
        self.stage('main-only',self.key)
        self.enroll(local_only=['evidence/**'])
        linked=self.base/'new-linked';self.git('worktree','add','-qb','new-linked',str(linked))
        remote=self.base/'linked-remote.git'
        subprocess.run(['git','init','--bare','-q',str(remote)],check=True)

        def child(*args, input=None, check=True):
            return subprocess.run(['git','-C',str(linked),*args],input=input,capture_output=True,check=check)

        status=json.loads(self.cli('status','--repo',str(linked)).stdout)
        self.assertEqual(('active','shared-worktrees',str(linked)),
                         (status['status'],status['scope'],status['worktree']))
        (linked/'clean').write_text('benign')
        child('add','clean');child('commit','-qm','test: linked clean')
        child('push',str(remote),'HEAD:refs/heads/main')
        self.assertIn(b'main-only',self.git('diff','--cached','--name-only').stdout)

        (linked/'secret').write_text(self.key)
        child('add','secret')
        bad=child('commit','-qm','test: linked secret',check=False)
        self.assertNotEqual(0,bad.returncode);self.assertIn(b'finding',bad.stdout+bad.stderr)
        tree=child('write-tree').stdout.decode().strip()
        tip=child('commit-tree',tree,'-p','HEAD',input=b'test: outgoing synthetic fixture\n').stdout.decode().strip()
        pushed=child('push',str(remote),tip+':refs/heads/blocked',check=False)
        self.assertNotEqual(0,pushed.returncode);self.assertIn(b'finding',pushed.stdout+pushed.stderr)
        self.assertNotIn(self.key.encode(),bad.stderr+pushed.stderr)
        child('rm','--cached','secret')
        artifact=linked/'evidence/run.txt';artifact.parent.mkdir();artifact.write_text('benign')
        child('add','evidence/run.txt')
        violation=child('commit','-qm','test: linked artifact',check=False)
        self.assertNotEqual(0,violation.returncode);self.assertIn(b'policy_violation',violation.stdout+violation.stderr)

        self.git('config','extensions.worktreeConfig','true')
        hooks=self.base/'different-hooks';hooks.mkdir()
        child('config','--worktree','core.hooksPath',str(hooks))
        uncovered=self.cli('status','--repo',str(linked))
        self.assertEqual(2,uncovered.returncode)
        self.assertEqual('worktree uses different hooks',json.loads(uncovered.stdout)['reason'])

    def test_relative_missing_hooks_directory_and_recovery(self):
        self.hooks=self.repo/'custom hooks';self.git('config','core.hooksPath','custom hooks')
        report=self.plan();self.assertFalse(self.hooks.exists());self.assertFalse(self.state.exists())
        installer.apply(report);self.assertTrue((self.hooks/'pre-commit').is_file())
        installer.status(self.state,True);self.assertFalse(self.hooks.exists())

    def test_preapply_conflicts_change_no_target_files(self):
        report=self.plan();hook=self.custom('pre-commit','user edit')
        with self.assertRaisesRegex(installer.InstallError,'file conflict'):installer.apply(report)
        self.assertFalse(self.state.exists());self.assertEqual('user edit',hook.read_text())
        hook.unlink();report=self.plan();self.git('config','core.hooksPath',str(self.base/'new hooks'))
        with self.assertRaisesRegex(installer.InstallError,'configuration/path'):installer.apply(report)
        self.assertFalse(self.state.exists());self.assertFalse((self.base/'new hooks').exists())

    def test_plan_digest_changed_rejected_without_writes(self):
        report=self.plan()
        with self.assertRaisesRegex(installer.InstallError,'reviewed plan'):installer.apply(report,'0'*64)
        self.assertFalse(self.state.exists())

    def test_postinstall_edits_config_and_symlinks_prevent_rollback(self):
        self.enroll();hook=self.hooks/'pre-commit';hook.write_text('later user edit')
        self.assertEqual('conflict',installer.status(self.state)['status'])
        with self.assertRaisesRegex(installer.InstallError,'rollback conflict'):installer.status(self.state,True)
        self.assertEqual('later user edit',hook.read_text());self.assertTrue((self.hooks/'pre-push').is_file())

    def test_partial_apply_failure_restores_original_bytes_and_modes(self):
        hook=self.custom('pre-commit','#!/bin/sh\nexit 0\n',0o751);before=installer.snapshot(hook)
        report=self.plan();save=installer.save;once=[False]
        def broken(path,value):
            if path==self.hooks/'pre-push' and not once[0]:
                once[0]=True;raise OSError('injected write failure')
            return save(path,value)
        with mock.patch.object(installer,'save',side_effect=broken):
            with self.assertRaises(OSError):installer.apply(report)
        self.assertEqual(before,installer.snapshot(hook));self.assertFalse((self.hooks/'pre-push').exists())
        self.assertEqual('rolled-back',installer.status(self.state)['status'])
        self.assertFalse((self.hooks/'.tr-kit-guard.lock').exists())

    def test_symlink_managed_hook_backup_and_state_rejected(self):
        target=self.hooks/'pre-commit';target.symlink_to(self.real_scanner)
        with self.assertRaisesRegex(installer.InstallError,'symlink'):self.plan()
        target.unlink();self.custom('pre-commit','#!/bin/sh\n# generated by pre-commit\n')
        with self.assertRaisesRegex(installer.InstallError,'managed'):self.plan()
        target.unlink();(self.hooks/'pre-commit.tr-kit-original').write_text('occupied')
        with self.assertRaisesRegex(installer.InstallError,'occupied'):self.plan()
        (self.hooks/'pre-commit.tr-kit-original').unlink()
        with self.assertRaisesRegex(installer.InstallError,'outside'):
            installer.plan(self.repo,self.repo/'state',self.real_scanner)
        self.enroll()
        with self.assertRaisesRegex(installer.InstallError,'state must be new'):self.plan()
        with self.assertRaisesRegex(installer.InstallError,'managed'):
            installer.plan(self.repo,self.base/'other-state',self.real_scanner)

    def test_policy_edit_blocks_hook_and_conflict_safe_restore(self):
        self.enroll();self.stage('clean','benign')
        policy=self.state/'policy.json';data=json.loads(policy.read_text());data['gitleaks']=str(self.base/'missing')
        policy.write_text(json.dumps(data))
        bad=self.git('commit','-qm','test: unavailable',check=False)
        self.assertNotEqual(0,bad.returncode);self.assertIn(b'unavailable',bad.stdout+bad.stderr)
        self.assertEqual('conflict',installer.status(self.state)['status'])

    def test_cli_requires_explicit_paths_and_reviewed_plan(self):
        p=self.cli('plan','--repo',str(self.repo),'--gitleaks',str(self.real_scanner))
        self.assertEqual(0,p.returncode,p.stderr);report=json.loads(p.stdout)
        bad=self.cli('apply','--repo',str(self.repo),'--gitleaks',str(self.real_scanner))
        self.assertNotEqual(0,bad.returncode);self.assertFalse(self.state.exists())
        p=self.cli('apply','--repo',str(self.repo),'--gitleaks',str(self.real_scanner),'--expect-plan',report['plan_id'])
        self.assertEqual(0,p.returncode,p.stderr);self.assertEqual('active',json.loads(p.stdout)['status'])
        self.assertEqual('rolled-back',json.loads(self.cli('rollback').stdout)['status'])

    def test_backup_exception_does_not_exempt_secrets(self):
        backup=self.base/'tr-local-docs';self.repo.rename(backup);self.repo=backup;self.hooks=backup/'.git/hooks'
        self.enroll(local_only=['_bmad-output/**'],allow_artifacts=['_bmad-output/**'])
        self.stage('_bmad-output/report.md','benign');self.git('commit','-qm','test: backup allowed')
        linked=self.base/'other-backup';self.git('worktree','add','-qb','other-backup',str(linked))
        (linked/'_bmad-output/report.md').write_text('changed')
        subprocess.run(['git','-C',str(linked),'add','--','_bmad-output/report.md'],check=True)
        rejected=subprocess.run(['git','-C',str(linked),'commit','-qm','test: linked backup denied'],capture_output=True)
        self.assertNotEqual(0,rejected.returncode);self.assertIn(b'policy_violation',rejected.stdout+rejected.stderr)
        self.stage('_bmad-output/secret.md',self.key)
        p=self.git('commit','-qm','test: backup secret',check=False)
        self.assertNotEqual(0,p.returncode);self.assertIn(b'finding',p.stdout+p.stderr)

    def test_external_scanner_missing_does_not_prevent_original_restore(self):
        import tomllib
        prefix=self.base/'fixture-provision';(prefix/'bin').mkdir(parents=True)
        scanner=prefix/'bin/gitleaks';scanner.write_bytes(self.scanner.read_bytes());scanner.chmod(0o755)
        pin=tomllib.loads((ROOT/'common/base/scripts/secret-tools.toml').read_text())['gitleaks']
        (prefix/'provisioned.json').write_text(json.dumps({'version':pin['version'],
            'archive_sha256':pin['linux_x64_sha256'],'binary_sha256':installer.digest(scanner.read_bytes())}))
        report=installer.plan(self.repo,self.state,scanner);installer.apply(report)
        scanner.unlink()
        self.assertEqual('unavailable',installer.status(self.state)['status'])
        self.stage('clean','benign');bad=self.git('commit','-qm','test: missing scanner',check=False)
        self.assertNotEqual(0,bad.returncode)
        self.assertEqual('rolled-back',installer.status(self.state,True)['status'])

    def test_hooks_lock_refuses_concurrent_plan_without_mutation(self):
        lock=self.hooks/'.tr-kit-guard.lock';lock.write_text('another operation')
        with self.assertRaisesRegex(installer.InstallError,'lock'):self.plan()
        self.assertFalse(self.state.exists());self.assertEqual('another operation',lock.read_text())

    def test_unexecutable_original_is_preserved_without_execution(self):
        marker=self.base/'should-not-exist'
        hook=self.custom('pre-commit',f'#!/bin/sh\ntouch {str(marker)!r}\n',0o644)
        before=installer.snapshot(hook);self.enroll();self.stage('clean','benign')
        self.git('commit','-qm','test: non executable original')
        self.assertFalse(marker.exists());installer.status(self.state,True)
        self.assertEqual(before,installer.snapshot(hook))

    def test_relative_hooks_config_symlink_retarget_is_detected(self):
        first=self.base/'first-hooks';second=self.base/'second-hooks';first.mkdir();second.mkdir()
        link=self.base/'hook-link';link.symlink_to(first,target_is_directory=True)
        self.git('config','core.hooksPath',str(link));report=self.plan()
        link.unlink();link.symlink_to(second,target_is_directory=True)
        with self.assertRaisesRegex(installer.InstallError,'configuration/path'):installer.apply(report)
        self.assertFalse(self.state.exists());self.assertEqual([],list(first.iterdir()))

    def test_alternate_index_is_scanned_by_real_commit_hook(self):
        self.enroll();self.stage('clean','benign');self.git('commit','-qm','test: initial')
        alternate=self.base/'alternate-index';env=dict(os.environ,GIT_INDEX_FILE=str(alternate))
        subprocess.run(['git','-C',str(self.repo),'read-tree','HEAD'],env=env,check=True)
        (self.repo/'bad').write_text(self.key)
        subprocess.run(['git','-C',str(self.repo),'add','--','bad'],env=env,check=True)
        p=subprocess.run([str(self.hooks/'pre-commit')],cwd=self.repo,env=env,capture_output=True)
        self.assertNotEqual(0,p.returncode);self.assertIn(b'finding',p.stdout+p.stderr)
        self.assertNotIn(b'bad',self.git('diff','--cached','--name-only').stdout)


class PolicyTests(GuardFixture):
    def test_handwritten_unrestricted_exceptions_fail_in_index_and_push(self):
        self.entry['allow_artifacts']=['evidence/**'];self.save_policy();self.stage('evidence/a','benign')
        with self.assertRaisesRegex(guard.GuardError,'artifact allowances'):guard.check_index(self.repo,self.policy)
        with self.assertRaisesRegex(guard.GuardError,'artifact allowances'):guard.check_push(self.repo,self.policy,'')

    def test_exact_backup_suffix_and_actual_git_root(self):
        root=self.base/'tr-local-docs';self.repo.rename(root);self.repo=root
        for pattern in ['evidence/**','other_bmad-output/**','p/_bmad-output/*','/p/_bmad-output/**','../_bmad-output/**','p//_bmad-output/**']:
            with self.subTest(pattern=pattern),self.assertRaises(guard.GuardError):
                guard.validate_artifact_policy(root,{'allow_artifacts':[pattern]})
        for pattern in ['_bmad-output/**','project/_bmad-output/**','*/_bmad-output/**','**/_bmad-output/**']:
            guard.validate_artifact_policy(root,{'allow_artifacts':[pattern]})
        # A declared path alias cannot give another actual root the backup exception.
        self.entry['path']=str(root);self.entry['allow_artifacts']=['_bmad-output/**'];self.save_policy()
        self.stage('_bmad-output/report.md','benign');guard.check_index(root,self.policy)

    def test_data_only_cat_heredoc_with_own_source_is_not_environment_output(self):
        source=(ROOT/'common/base/scripts/git_guard_install.py').read_text()
        command="cat > example.py <<'PY'\n"+source+"\nPY\n"
        self.assertIsNone(guard.disclosure_reason(guard.literal_command_view(command)))
        # Actual shell disclosure remains executable and blocked after the terminator.
        self.assertIsNotNone(guard.disclosure_reason(guard.literal_command_view(command+'printenv\n')))
