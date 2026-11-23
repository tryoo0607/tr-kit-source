"""Real Git events in disposable repositories; no production enrollment."""
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from test_secret_legacy import GuardFixture, ROOT, REAL_TRUSTED_SCANNER


class GitEvents(GuardFixture):
    def setUp(self):
        super().setUp()
        self.scanner=REAL_TRUSTED_SCANNER()
        self.save_policy()
        self.synthetic_key='ghp_'+hashlib.sha256(b'no real account synthetic git event').hexdigest()[:36]

    def hook(self,event,mode):
        spec=importlib.util.spec_from_file_location('render_git',ROOT/'scripts/render-git-secret-hook.py')
        renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
        hook=self.repo/'.git/hooks'/event
        hook.write_text(renderer.render(mode,ROOT,self.repo,self.policy,Path(sys.executable)))
        hook.chmod(0o755)

    def test_actual_precommit_blocks_bad_stage_and_preserves_index(self):
        self.hook('pre-commit','index')
        self.stage('fixture',self.synthetic_key)
        before=self.git('write-tree').stdout
        bad=self.git('commit','-m','test: fixture',check=False)
        self.assertNotEqual(bad.returncode,0)
        self.assertNotIn(self.synthetic_key.encode(),bad.stdout+bad.stderr)
        self.assertEqual(before,self.git('write-tree').stdout)
        self.stage('fixture','safe')
        good=self.git('commit','-m','test: fixture',check=False)
        self.assertEqual(good.returncode,0,good.stderr)

    def test_actual_prepush_rejects_outgoing_secret_local_bare_remote(self):
        remote=self.base/'remote.git'
        subprocess.run(['git','init','--bare','-q',str(remote)],check=True)
        self.git('remote','add','fixture',str(remote))
        self.stage('fixture','safe');self.git('commit','-m','test: clean')
        self.hook('pre-push','push')
        self.assertEqual(self.git('push','fixture','HEAD:refs/heads/main',check=False).returncode,0)
        original=subprocess.run(['git','--git-dir',str(remote),'rev-parse','refs/heads/main'],capture_output=True,check=True).stdout
        self.stage('fixture',self.synthetic_key);self.git('commit','-m','test: outgoing')
        bad=self.git('push','fixture','HEAD:refs/heads/main',check=False)
        self.assertNotEqual(bad.returncode,0)
        self.assertNotIn(self.synthetic_key.encode(),bad.stdout+bad.stderr)
        after=subprocess.run(['git','--git-dir',str(remote),'rev-parse','refs/heads/main'],capture_output=True,check=True).stdout
        self.assertEqual(original,after)
