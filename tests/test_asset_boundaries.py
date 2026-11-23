"""Own source policy/glue regressions; fixtures never invoke a production index."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'common/base/scripts'))
import assets
import profile_config as config
spec=importlib.util.spec_from_file_location('git_excludes',ROOT/'common/base/scripts/git-excludes.py')
ignores=importlib.util.module_from_spec(spec);spec.loader.exec_module(ignores)

class Boundaries(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        env=patch.dict(os.environ,{'TR_ASSETS_STATE_ROOT':str(self.root/'state')})
        env.start();self.addCleanup(env.stop)

    def test_unknown_ownership_and_invalid_identifier(self):
        for role,group,project in [('typo','g','p'),('project','bad name','p'),('project','g','?')]:
            with self.subTest(role=role,group=group):
                with self.assertRaises(ValueError): assets.scope_path(self.root,role,group,project)
        self.assertFalse((self.root/'groups').exists())

    def test_prepare_preflights_both_directories(self):
        scope=self.root/'scope';scope.mkdir();(scope/'extracted').symlink_to(self.root/'outside')
        with self.assertRaises(ValueError): assets.prepare(scope,True)
        self.assertFalse((scope/'originals').exists())

    def test_scope_alias_and_parent_alias_rejected(self):
        real=self.root/'real';real.mkdir();alias=self.root/'alias';alias.symlink_to(real,target_is_directory=True)
        for path in [alias,alias/'child']:
            with self.subTest(path=path):
                with self.assertRaises(ValueError): assets.prepare(path,True)
        self.assertEqual(list(real.iterdir()),[])

    def test_state_key_symlink_rejected(self):
        scope=self.root/'scope';assets.prepare(scope,True)
        state=assets.state_path(scope);state.parent.mkdir(parents=True)
        outside=self.root/'outside';outside.mkdir();state.symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError): assets.qmd_connection(scope)
        self.assertEqual(list(outside.iterdir()),[])

    def test_explicit_missing_config_never_defaults(self):
        with self.assertRaises(FileNotFoundError): assets.configured_scope(self.root/'missing','project','g','p')
        self.assertFalse((self.root/'missing').exists())

    def test_config_typo_rejected_even_with_assets_override(self):
        cfg=self.root/'config.toml';cfg.write_text('schema_version=1\n[projects.p]\nassets="/tmp/p"\nasssets="/tmp/other"\n')
        with self.assertRaises(ValueError): assets.configured_scope(cfg,'project','g','p')

    def test_config_full_contract_and_independent_knowledge(self):
        value={'schema_version':1,'roots':{'assets':'~/projects/_tr-assets'},
          'projects':{'p':{'code':'/p','sync':{'enabled':False}}},
          'groups':{'g':{'documents':'/docs/g'}},'knowledge':{'documents':'/knowledge'},
          'documents':{'sync':{'enabled':True,'targets':['backup'],'exclude':['private/file.md']}},
          'sync_targets':{'backup':{'repository':'/docs','remote':'origin'}}}
        self.assertIs(config.validate(value),value)
        self.assertNotIn('sync',value['knowledge'])
        self.assertEqual(value['projects']['p']['sync'],{'enabled':False})

    def test_config_invalid_types_paths_targets_and_excludes(self):
        bad=[{'schema_version':True},{'roots':{'assets':'relative'}},{'roots':{'assets':'/a/../b'}},
             {'groups':{'bad name':{}}},{'common':{'sync':{'enabled':'true'}}},
             {'common':{'sync':{'enabled':True}}},{'common':{'sync':{'targets':['unknown']}}},
             {'common':{'sync':{'exclude':['private/../all']}}},{'common':{'sync':{'exclude':['*']}}},
             {'common':{'sync':{'targets':[[]]}}},{'documents':{'sync':{'exclude':['x','x']}}},
             {'sync_targets':{'x':{'repository':'/x','remote':'https://host'}}}]
        for item in bad:
            with self.subTest(item=item):
                with self.assertRaises(ValueError): config.validate({'schema_version':1,**item})

    def test_freshness_malformed_provenance(self):
        scope=self.root/'scope';assets.prepare(scope,True)
        original,output,meta=assets.output_paths(scope,'a.pdf');original.write_text('original')
        output.parent.mkdir();output.write_text('extracted');meta.write_text('[]')
        self.assertEqual(assets.freshness(scope,'a.pdf'),'stale')
        self.assertEqual(assets.extract(scope,'a.pdf',['missing-executable'])['status'],'stale')
        self.assertEqual(output.read_text(),'extracted')

    def test_extract_rejects_override_before_mutation(self):
        scope=self.root/'scope';assets.prepare(scope,True);(scope/'originals/a.pdf').write_text('original')
        for options in [['--output=/elsewhere'],['--to','html'],[False]]:
            with self.subTest(options=options):
                with self.assertRaises(ValueError): assets.extract(scope,'a.pdf',['unused'],options)
        self.assertEqual(list((scope/'extracted').iterdir()),[])

    def prepared_index(self):
        scope=self.root/'scope';assets.prepare(scope,True)
        original,output,meta=assets.output_paths(scope,'a.pdf');original.write_text('original')
        output.parent.mkdir();output.write_text('extracted')
        meta.write_text(json.dumps({'original':str(original),'sha256':assets.digest(original),'output_sha256':assets.digest(output)}))
        with patch.object(assets.shutil,'which',return_value='/fake/qmd'),patch.object(assets.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'','')):
            self.assertEqual(assets.index(scope)['status'],'indexed')
        return scope

    def test_qmd_malformed_hit_and_errors_are_not_exposed(self):
        scope=self.prepared_index()
        for response in [subprocess.CompletedProcess([],0,'[{"file": []}]',''),subprocess.CompletedProcess([],1,'','sensitive diagnostic fixture')]:
            with patch.object(assets.shutil,'which',return_value='/fake/qmd'),patch.object(assets.subprocess,'run',return_value=response):
                report=assets.search([scope],'a.pdf')
            self.assertEqual(report['scopes'][0]['status'],'unindexed')
            self.assertEqual(len(report['results']),1)
            self.assertNotIn('sensitive diagnostic fixture',json.dumps(report))

    def test_qmd_timeout_is_explicit_fallback(self):
        scope=self.prepared_index()
        with patch.object(assets.shutil,'which',return_value='/fake/qmd'),patch.object(assets.subprocess,'run',side_effect=subprocess.TimeoutExpired('qmd',60)):
            report=assets.search([scope],'a.pdf')
        self.assertEqual(report['scopes'][0]['error'],'TimeoutExpired')
        self.assertEqual(report['results'][0]['freshness'],'fresh')

    def test_search_does_not_create_state_or_scan_sibling(self):
        scope=self.root/'scope';assets.prepare(scope,True);(scope/'originals/a.pdf').write_text('fixture')
        sibling=self.root/'other';sibling.mkdir();(sibling/'a.pdf').write_text('fixture')
        report=assets.search([scope],'a')
        self.assertEqual(len(report['results']),1)
        self.assertFalse((self.root/'state').exists())

    def test_global_ignore_symlink_rejected_and_plan_no_writes(self):
        target=self.root/'target';target.write_text('preserve\n');link=self.root/'alias';link.symlink_to(target)
        with self.assertRaises(ValueError): ignores.setup(link,apply=True)
        self.assertEqual(target.read_text(),'preserve\n')
        missing=self.root/'new/ignore';ignores.setup(missing,apply=False)
        self.assertFalse(missing.parent.exists())

    def test_backup_preflight_prevents_global_mutation(self):
        repo=self.root/'tr-local-docs';subprocess.run(['git','init',str(repo)],check=True,capture_output=True)
        (repo/'.gitignore').symlink_to(self.root/'outside')
        excludes=self.root/'ignore'
        with self.assertRaises(ValueError): ignores.setup(excludes,repo,True)
        self.assertFalse(excludes.exists())

    def test_ignore_apply_is_idempotent_and_retains_policy(self):
        env={'GIT_CONFIG_GLOBAL':str(self.root/'gitconfig'),'GIT_CONFIG_NOSYSTEM':'1'}
        repo=self.root/'tr-local-docs';subprocess.run(['git','init',str(repo)],check=True,capture_output=True)
        excludes=self.root/'ignore';excludes.write_text('keep\n*.secret\n')
        with patch.dict(os.environ,env):
            ignores.setup(excludes,repo,True);before=excludes.read_bytes()
            ignores.setup(excludes,repo,True)
            self.assertEqual(excludes.read_bytes(),before)
        self.assertEqual((repo/'.gitignore').read_text(),'!_bmad-output/\n')
        self.assertTrue(excludes.read_text().startswith('keep\n*.secret\n'))

    def test_explicit_scope_does_not_probe_default_config(self):
        with patch.object(sys, 'argv', ['assets.py', 'scope', '--scope', str(self.root/'explicit')]), patch.object(Path, 'exists', side_effect=AssertionError('default config probed')), patch('builtins.print') as printed:
            assets.main()
        self.assertEqual(json.loads(printed.call_args.args[0])['scope'], str(self.root/'explicit'))

    def test_cli_config_failure_is_fixed_diagnostic(self):
        cfg=self.root/'bad.toml';cfg.write_text('schema_version=1\nsecret_field="private diagnostic content"\n')
        proc=subprocess.run([sys.executable,'-B',str(ROOT/'common/base/scripts/assets.py'),'scope','--config',str(cfg),'--ownership','environment'],capture_output=True,text=True)
        self.assertEqual(proc.returncode,2)
        self.assertEqual(json.loads(proc.stdout),{'status':'unavailable','error':'ValueError'})
        self.assertEqual(proc.stderr,'')
        self.assertNotIn('private diagnostic content',proc.stdout)

    def test_cli_does_not_leave_source_bytecode(self):
        import shutil
        source=self.root/'own-scripts';source.mkdir()
        for name in ['assets.py','profile_config.py']:
            shutil.copyfile(ROOT/'common/base/scripts'/name,source/name)
        proc=subprocess.run([sys.executable,str(source/'assets.py'),'scope','--scope',str(self.root/'explicit')],capture_output=True,text=True)
        self.assertEqual(proc.returncode,0)
        self.assertFalse((source/'__pycache__').exists())

if __name__=='__main__': unittest.main()
