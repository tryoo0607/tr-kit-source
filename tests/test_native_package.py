"""Native own layout, no upstream installs; isolated CLI actions are test doubles."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'common/base/scripts'))
import assemble
import package
import plugin_runtime
from upstream_guard import make_catalog
spec=importlib.util.spec_from_file_location('plugin_lifecycle',ROOT/'scripts/plugin-lifecycle.py')
lifecycle=importlib.util.module_from_spec(spec);spec.loader.exec_module(lifecycle)


class NativePackage(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name).resolve()
        original=self.base/'external.md';original.write_text('Synthetic foreign body: not included in any kit file.\n')
        self.catalog=self.base/'catalog.json';self.catalog.write_text(json.dumps(make_catalog([original])))
        self.providers=self.base/'providers.json';self.providers.write_text('{"version":1,"providers":[]}')
        self.scan=mock.patch.object(assemble.secrets,'scan',return_value=None);self.scan.start();self.addCleanup(self.scan.stop)
        self.scanner=mock.patch.object(assemble.secrets,'trusted_scanner',return_value=Path('/test-only-scanner'))
        self.scanner.start();self.addCleanup(self.scanner.stop)

    def build(self,product='codex',version='0.0.0-g5.1',profile='review',name='release'):
        output=self.base/name;scope=self.base/(name+'-scope.json')
        scope.write_text(json.dumps({'version':1,'components':['common/base','adapters','scripts','LICENSE','NOTICE','SECURITY.md','INSTALL.md'],
                                    'artifacts':[str(output)]}))
        assemble.build(ROOT,product,output,self.catalog,scope,self.providers,native={'version':version,'profile':profile})
        return output

    def test_both_native_manifests_and_relative_links_preserved(self):
        for product in ('codex','claude'):
            out=self.build(product,name=product);report=package.verify(out,product)
            payload=Path(report['payload']);self.assertFalse(report['operational_ready']);self.assertFalse(report['mcp_registered'])
            self.assertTrue((payload/'common/base/skills/mem-search/SKILL.md').is_file())
            self.assertFalse((payload/'skills').exists());self.assertFalse((payload/'CLAUDE.md').exists())
            self.assertFalse((payload/'.mcp.json').exists())
            self.assertTrue((payload/'adapters'/product/'mcp').is_dir())

    def test_review_profile_explicitly_has_no_protection_claim(self):
        report=package.verify(self.build(),'codex');payload=Path(report['payload'])
        self.assertEqual(set(json.loads((payload/'hooks/hooks.json').read_text())['hooks']),{'SessionStart'})
        self.assertEqual(report['profile'],'review');self.assertFalse(report['operational_ready'])

    def test_guarded_profile_composes_existing_checks_without_duplicate_context(self):
        for product in ('codex','claude'):
            report=package.verify(self.build(product,profile='guarded',name=product),'codex' if product=='codex' else 'claude')
            hooks=json.loads((Path(report['payload'])/'hooks/hooks.json').read_text())['hooks']
            self.assertEqual(len(hooks['SessionStart']),1);self.assertEqual(len(hooks['PreToolUse']),2)
            self.assertEqual(len(hooks['PostToolUse']),2)
            if product=='claude':self.assertEqual(len(hooks['PostToolUseFailure']),2)
            text=json.dumps(hooks);self.assertNotIn('@@',text);self.assertNotIn(str(ROOT),text)

    def test_tampered_payload_refused(self):
        out=self.build();(out/'plugins/tr-codex/common/base/instructions.md').write_text('tamper')
        with self.assertRaises(ValueError):package.verify(out,'codex')

    def test_extra_or_symlink_payload_refused(self):
        out=self.build();extra=out/'unexpected';extra.write_text('new')
        with self.assertRaises(ValueError):package.verify(out,'codex')
        extra.unlink();extra.symlink_to(self.base/'external.md')
        with self.assertRaises(ValueError):package.verify(out,'codex')

    def test_wrong_product_and_malformed_path_refused(self):
        out=self.build()
        with self.assertRaises(ValueError):package.verify(out,'claude')
        manifest=out/'assembly.json';doc=json.loads(manifest.read_text());doc['files'][0]['path']='../escape';manifest.write_text(json.dumps(doc))
        with self.assertRaises(ValueError):package.verify(out,'codex')

    def test_source_changed_before_transfer_not_certified(self):
        with mock.patch.object(assemble,'output_bytes',side_effect=ValueError('concurrent output drift')):
            with self.assertRaises(ValueError):self.build()
        self.assertTrue((self.base/'release/assembly.json').is_file())

    def test_no_overwrite_or_fake_revision(self):
        output=self.build()
        with self.assertRaises(ValueError):self.build()
        report=package.verify(output,'codex');self.assertNotIn('source_revision',report)
        self.assertRegex(report['source_inventory_sha256'],r'^[a-f0-9]{64}$')

    def test_bad_profile_and_version_refused(self):
        for version,profile in [('not-semver','review'),('0.0.0','automatic')]:
            with self.assertRaises(ValueError):package.native_files(ROOT,'codex',assemble.inventory(ROOT,'codex'),{'version':version,'profile':profile})

    def test_installed_payload_record_covers_exact_manager_payload(self):
        for product in ('codex','claude'):
            out=self.build(product=product,name='payload-'+product)
            payload=out/'plugins'/('tr-'+product);record=json.loads((payload/'installation.json').read_text())
            actual={str(p.relative_to(payload)) for p in payload.rglob('*') if p.is_file()}
            self.assertEqual(actual,{r['path'] for r in record['files']}|{'installation.json'})
            self.assertEqual(record['product'],product)
            self.assertEqual(record['name'],'tr-'+product)

    def test_payload_record_cannot_omit_files_even_with_updated_outer_manifest(self):
        out=self.build();target=out/'plugins/tr-codex/installation.json'
        record=json.loads(target.read_text());record['files'].pop();target.write_bytes(package.encoded(record))
        outer=json.loads((out/'assembly.json').read_text())
        for item in outer['files']:
            if item['path']=='plugins/tr-codex/installation.json':item['sha256']=package.digest(target.read_bytes())
        (out/'assembly.json').write_bytes(package.encoded(outer))
        with self.assertRaisesRegex(ValueError,'payload inventory'):package.verify(out,'codex')

    def test_explicit_other_own_identity_reuses_envelope_and_lifecycle(self):
        output=self.base/'addon';scope=self.base/'addon-scope.json'
        scope.write_text(json.dumps({'version':1,'components':['common/base','adapters','scripts','LICENSE','NOTICE','SECURITY.md','INSTALL.md'],'artifacts':[str(output)]}))
        def renderer(root,product,files,options):
            manifest={'name':'local-addon','version':options['version'],'skills':'./common/base/skills/','hooks':'./hooks/hooks.json'}
            return package.wrap_native_files(product,files,manifest,{'hooks':{}},options['profile'],['test-only prerequisite'])
        assemble.build(ROOT,'codex',output,self.catalog,scope,self.providers,
                       native={'version':'0.0.0-test','profile':'guarded'},native_renderer=renderer)
        with self.assertRaises(ValueError):package.verify(output,'codex')
        release=package.verify(output,'codex',expected_name='local-addon');self.assertEqual(release['name'],'local-addon')
        value=lifecycle.plan('install',output,'codex',self.base/'addon-prefix',Path('/usr/bin/true').resolve(),expected_name='local-addon')
        self.assertIn('local-addon@local-addon',value['commands'][1]);self.assertFalse((self.base/'addon-prefix').exists())
        for name in ('../outside','--flag','bad/name'):
            with self.assertRaises(ValueError):package.verify(output,'codex',expected_name=name)

    def test_initial_context_uses_own_source_and_absolute_workflow_pointer(self):
        result=plugin_runtime.context(ROOT,{'hook_event_name':'SessionStart','source':'compact'})
        text=result['hookSpecificOutput']['additionalContext']
        self.assertIn(str(ROOT/'workflow.md'),text);self.assertIn((ROOT/'common/base/instructions.md').read_text(),text)
        self.assertNotIn('외부 실행 성공',text)

    def test_missing_context_not_success(self):
        with self.assertRaises(ValueError):plugin_runtime.context(self.base,{'hook_event_name':'SessionStart'})
        with self.assertRaises(ValueError):plugin_runtime.context(ROOT,{'hook_event_name':'Other'})

    def test_missing_upstream_binding_denies_pre(self):
        env=dict(os.environ);env.pop('TR_KIT_UPSTREAM_BINDING',None)
        env['TR_KIT_RUNTIME_CONFIG']=str(self.base/'missing-runtime.json')
        r=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/plugin-runtime.py'),'upstream','--product','codex','--event','PreToolUse'],
            input='{"hook_event_name":"PreToolUse"}',text=True,capture_output=True,env=env)
        self.assertEqual(json.loads(r.stdout)['hookSpecificOutput']['permissionDecision'],'deny')

    def test_malformed_native_input_returns_explicit_failure_response(self):
        for raw in ('[]','null','true','"text"'):
            with self.subTest(raw=raw):
                r=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/plugin-runtime.py'),'upstream','--product','codex','--event','PreToolUse'],
                    input=raw,text=True,capture_output=True)
                self.assertEqual(r.returncode,0,r.stderr)
                self.assertEqual(json.loads(r.stdout)['hookSpecificOutput']['permissionDecision'],'deny')

    def test_malformed_upstream_binding_not_passed_to_shell(self):
        binding=self.base/'guard.json';binding.write_text('{"root":"/tmp","catalog":"relative","scope":"/tmp/scope"}')
        with mock.patch.dict(os.environ,{'TR_KIT_UPSTREAM_BINDING':str(binding)}):
            with self.assertRaises(ValueError):plugin_runtime.upstream(ROOT,'codex','PreToolUse',b'{}')

    def test_lifecycle_plan_does_not_create_prefix_or_execute_cli(self):
        out=self.build();cli=Path('/usr/bin/true').resolve();prefix=self.base/'isolated'
        value=lifecycle.plan('install',out,'codex',prefix,cli)
        self.assertFalse(prefix.exists());self.assertEqual(len(value['commands']),2)
        with self.assertRaises(ValueError):lifecycle.apply(value,'unreviewed')
        self.assertFalse(prefix.exists())

    def test_static_plan_skips_scanner_but_apply_requires_it_before_writes(self):
        out=self.build();prefix=self.base/'isolated';cli=Path('/usr/bin/true').resolve()
        with mock.patch.object(assemble.secrets,'trusted_scanner',side_effect=ValueError('scanner unavailable')):
            value=lifecycle.plan('install',out,'codex',prefix,cli)
            self.assertIn('not executed',value['scan'])
            with self.assertRaises(ValueError):lifecycle.apply(value,value['plan_id'])
        self.assertFalse(prefix.exists())

    def test_lifecycle_refuses_unmanaged_existing_prefix(self):
        out=self.build();prefix=self.base/'existing';prefix.mkdir()
        with self.assertRaises(ValueError):lifecycle.plan('install',out,'codex',prefix,Path('/usr/bin/true').resolve())
        with self.assertRaises(ValueError):lifecycle.plan('remove',out,'codex',prefix,Path('/usr/bin/true').resolve())

    def test_lifecycle_partial_failure_not_retried(self):
        out=self.build();cli=Path('/usr/bin/false').resolve();prefix=self.base/'isolated'
        value=lifecycle.plan('install',out,'codex',prefix,cli)
        with self.assertRaises(ValueError):lifecycle.apply(value,value['plan_id'])
        self.assertEqual(lifecycle.read_state(prefix)['phase'],'partial')
        self.assertFalse((prefix/'.operation.lock').exists())
        with self.assertRaises(ValueError):lifecycle.plan('update',out,'codex',prefix,cli)

    def test_lifecycle_fake_cli_cycle_preserves_releases(self):
        first=self.build();second=self.build(version='0.0.0-g5.2',name='release2');prefix=self.base/'isolated'
        cli=Path('/usr/bin/true').resolve()
        with mock.patch.object(lifecycle,'cached_payload',return_value='synthetic-verified-cache'), mock.patch.object(lifecycle,'uninstall_status',return_value={'native_uninstalled':True,'cache_retained':False}):
            for action,path in [('install',first),('update',second),('rollback',first),('remove',first)]:
                value=lifecycle.plan(action,path,'codex',prefix,cli);state=lifecycle.apply(value,value['plan_id'])
                self.assertEqual(state['phase'],'removed' if action=='remove' else 'installed')
        self.assertTrue(first.exists());self.assertTrue(second.exists());self.assertTrue(prefix.exists())

    def test_lifecycle_rechecks_cli_and_package_hashes(self):
        out=self.build();cli=self.base/'cli';cli.write_text('#!/bin/sh\nexit 0\n');cli.chmod(0o700)
        value=lifecycle.plan('install',out,'codex',self.base/'isolated',cli);cli.write_text('#!/bin/sh\nexit 1\n')
        with self.assertRaises(ValueError):lifecycle.apply(value,value['plan_id'])

    def test_managed_prefix_symlink_cannot_redirect_native_config(self):
        out=self.build();prefix=self.base/'isolated';cli=Path('/usr/bin/true').resolve()
        value=lifecycle.plan('install',out,'codex',prefix,cli)
        with mock.patch.object(lifecycle,'cached_payload',return_value='synthetic-verified-cache'):
            lifecycle.apply(value,value['plan_id'])
        config=prefix/'codex';config.rmdir();config.symlink_to(self.base,target_is_directory=True)
        with self.assertRaises(ValueError):lifecycle.plan('remove',out,'codex',prefix,cli)

    def test_native_hook_renderer_validation_is_not_bypassed(self):
        # A renderer failure must prevent native activation output; do not just
        # load an unchecked template with unknown handler/event fields.
        with mock.patch('importlib.util.spec_from_file_location',side_effect=ValueError('renderer unavailable')):
            with self.assertRaises(ValueError):package.native_files(ROOT,'codex',assemble.inventory(ROOT,'codex'),{'version':'0.0.0','profile':'guarded'})

    def test_claude_commands_keep_data_no_force_or_trust(self):
        out=self.build('claude');commands=lifecycle.commands('claude',Path('/bin/true'),'update',out)
        self.assertIn('--keep-data',commands[0]);text=json.dumps(commands)
        for bad in ('--force','--prune','--yes','trust','auth.json'):self.assertNotIn(bad,text)

    def test_native_remove_exit_zero_without_valid_registry_is_not_success(self):
        out=self.build();prefix=self.base/'isolated';cli=Path('/usr/bin/true').resolve()
        value=lifecycle.plan('install',out,'codex',prefix,cli)
        with mock.patch.object(lifecycle,'cached_payload',return_value='synthetic-verified-cache'):
            lifecycle.apply(value,value['plan_id'])
        manifest=prefix/'codex/plugins/cache/tr-codex/tr-codex/local/.codex-plugin/plugin.json'
        manifest.parent.mkdir(parents=True);manifest.write_text('{"name":"tr-codex"}')
        value=lifecycle.plan('remove',out,'codex',prefix,cli)
        with self.assertRaises(ValueError):lifecycle.apply(value,value['plan_id'])
        self.assertEqual(lifecycle.read_state(prefix)['phase'],'partial');self.assertTrue(manifest.exists())

    def test_native_registry_proves_uninstall_without_deleting_retained_cache(self):
        cli=Path('/usr/bin/true').resolve();prefix=self.base/'retained';(prefix/'home').mkdir(parents=True)
        for product,key,doc in [('codex','pluginId',{'installed':[{'pluginId':'other@other'}],'available':[]}),
                                ('claude','id',[{'id':'other@other'}])]:
            retained=prefix/('codex' if product=='codex' else 'claude')/'plugins/cache/local-addon';retained.mkdir(parents=True)
            marker=retained/'keep';marker.write_text('Own cached version; preserved.')
            result=type('Reply',(),{'returncode':0,'stdout':json.dumps(doc).encode()})()
            with mock.patch.object(lifecycle.subprocess,'run',return_value=result):
                status=lifecycle.uninstall_status(prefix,product,cli,'local-addon',package.digest(cli.read_bytes()))
            self.assertTrue(status['native_uninstalled']);self.assertTrue(status['cache_retained']);self.assertTrue(marker.exists())

    def test_native_uninstall_status_malformed_or_still_registered_is_not_success(self):
        cli=Path('/usr/bin/true').resolve();prefix=self.base/'unknown';(prefix/'home').mkdir(parents=True)
        for product,doc in [('codex',{}),('codex',{'installed':'bad'}),('codex',{'installed':[{}]}),
                            ('codex',{'installed':[{'pluginId':'local-addon@local-addon'}]}),
                            ('claude',{}),('claude',[{}]),('claude',[{'id':'local-addon@local-addon'}])]:
            result=type('Reply',(),{'returncode':0,'stdout':json.dumps(doc).encode()})()
            with mock.patch.object(lifecycle.subprocess,'run',return_value=result):
                with self.assertRaises(ValueError):lifecycle.uninstall_status(prefix,product,cli,'local-addon',package.digest(cli.read_bytes()))


if __name__=='__main__':unittest.main()
