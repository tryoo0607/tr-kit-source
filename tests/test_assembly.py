"""Fresh own-only assembly, explicit pins and real gates; no native installation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'common/base/scripts'))
import provider_links
from upstream_guard import make_catalog
spec=importlib.util.spec_from_file_location('kit_assemble',ROOT/'scripts/assemble.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

class Assembly(unittest.TestCase):
    def test_mcp_templates_stay_in_product_source_path(self):
        for product,suffix in (('codex','toml'),('claude','json')):
            rel=f'adapters/{product}/mcp/claude-mem.{suffix}.in'
            inventory=builder.inventory(ROOT,product)
            self.assertIn(rel,inventory)
            self.assertNotIn('.mcp.json',inventory)
            self.assertNotIn('config.toml',inventory)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.root=self.base/'kit';self.root.mkdir()
        for rel in ('common/base/skills/own','common/base/scripts','adapters/codex','adapters/claude','scripts'):
            (self.root/rel).mkdir(parents=True,exist_ok=True)
        (self.root/'common/base/instructions.md').write_text('Own user instructions\n')
        (self.root/'common/base/workflow.md').write_text('Own conditional workflow\n')
        (self.root/'common/base/skills/own/SKILL.md').write_text('Own connector instructions\n')
        for product,name in (('codex','AGENTS.md'),('claude','CLAUDE.md')):
            (self.root/f'adapters/{product}/{name}.template').write_text('{{COMMON_INSTRUCTIONS}}\n')
        self.external=self.base/'original.md';self.external.write_text('Synthetic external original, outside kit only.\n')
        self.cat=self.base/'catalog.json';self.cat.write_text(json.dumps(make_catalog([self.external])))
        self.output=self.base/'bundle'
        self.scope=self.base/'scope.json';self.save_scope()
        self.providers=self.base/'providers.json';self.save_providers()

    def save_scope(self,components=None,artifacts=None):
        self.scope.write_text(json.dumps({'version':1,'components':components or ['common/base','adapters','scripts'],
                                         'artifacts':artifacts if artifacts is not None else [str(self.output)]}))

    def entry(self,**changes):
        return {'id':'official-fixture','entry':str(self.external),'kind':'skill',
                'products':['codex','claude'],'sha256':hashlib.sha256(self.external.read_bytes()).hexdigest(),
                'source':'fixture, not official origin evidence','version':'1',**changes}

    def save_providers(self,entries=None):
        self.providers.write_text(json.dumps({'version':1,'providers':[self.entry()] if entries is None else entries}))

    def build(self,product='codex',scanner=None):
        # Most tests isolate gate/output invariants. One separate case uses real scanner.
        with (mock.patch.object(builder.secrets,'trusted_scanner',return_value=Path('/not-executed')),
              mock.patch.object(builder.secrets,'scan',side_effect=scanner)):
            return builder.build(self.root,product,self.output,self.cat,self.scope,self.providers)

    def test_own_only_both_products(self):
        for product,name in (('codex','AGENTS.md'),('claude','CLAUDE.md')):
            self.output=self.base/product;self.save_scope()
            record=self.build(product)
            self.assertFalse(record['native_installable'])
            self.assertEqual((self.output/name).read_text(),'Own user instructions\n\n')
            self.assertFalse((self.output/'original.md').exists())
            self.assertNotIn(self.external.read_text(),''.join(p.read_text() for p in self.output.rglob('*') if p.is_file()))
            self.assertNotIn('entry',record['external'][0])
            self.assertEqual(record['external'][0]['product_status'],'entry-pin-verified')

    def test_source_bundle_preserves_relative_dependency_paths(self):
        (self.root/'common/base/scripts/config.toml').write_text('version = 1')
        (self.root/'common/base/skills/own/SKILL.md').write_text('[config](../../scripts/config.toml)')
        self.build()
        skill=self.output/'common/base/skills/own/SKILL.md'
        self.assertTrue(skill.is_file())
        self.assertEqual((skill.parent/'../../scripts/config.toml').read_text(),'version = 1')
        self.assertEqual((self.output/'common/base/workflow.md').read_bytes(),(self.output/'workflow.md').read_bytes())

    def test_only_selected_product_adapter_skills_are_shipped(self):
        for product in ('codex','claude'):
            p=self.root/f'adapters/{product}/skills/artifact-publish/references/external.md'
            p.parent.mkdir(parents=True);p.write_text('Own '+product+' provider connection')
        for product,other in (('codex','claude'),('claude','codex')):
            self.output=self.base/product;self.save_scope();self.build(product)
            self.assertTrue((self.output/f'adapters/{product}/skills/artifact-publish/references/external.md').is_file())
            self.assertFalse((self.output/f'adapters/{other}').exists())

    def test_product_adapter_reference_symlink_is_not_vendored(self):
        p=self.root/'adapters/codex/skills/artifact-publish/references/external.md'
        p.parent.mkdir(parents=True);p.symlink_to(self.external)
        with self.assertRaises(ValueError):self.build()
        self.assertFalse(self.output.exists())

    def test_existing_output_refused_and_preserved(self):
        self.output.mkdir();(self.output/'existing').write_text('preserve')
        with self.assertRaises(ValueError):self.build()
        self.assertEqual((self.output/'existing').read_text(),'preserve')

    def test_output_must_be_explicit_artifact_before_write(self):
        self.save_scope(artifacts=[])
        with self.assertRaises(ValueError):self.build()
        self.assertFalse(self.output.exists())

    def test_declared_components_must_cover_consumed_sources(self):
        self.save_scope(components=['common/base'])
        with self.assertRaises(ValueError):self.build()
        self.assertFalse(self.output.exists())

    def test_original_copy_blocks_before_write(self):
        (self.root/'common/base/skills/own/copy').write_bytes(self.external.read_bytes())
        with self.assertRaises(ValueError):self.build()
        self.assertFalse(self.output.exists())

    def test_external_provider_cannot_be_kit_component(self):
        self.save_providers([self.entry(entry=str(self.root/'common/base/workflow.md'))])
        with self.assertRaises(provider_links.LinkError):self.build()
        self.assertFalse(self.output.exists())

    def test_missing_provider_is_unavailable_without_install(self):
        self.external.unlink()
        with self.assertRaises(Exception):self.build()
        self.assertFalse(self.output.exists())

    def test_pin_drift_is_not_automatically_adopted(self):
        entry=self.entry();self.external.write_text('changed')
        self.save_providers([entry])
        with self.assertRaises(provider_links.LinkError):provider_links.verify(self.root,self.providers,'codex')
        self.assertEqual(json.loads(self.providers.read_text())['providers'][0]['sha256'],entry['sha256'])

    def test_unsupported_product_not_inspected_or_faked_available(self):
        self.save_providers([self.entry(products=['claude'],entry=str(self.base/'missing'))])
        result=provider_links.verify(self.root,self.providers,'codex')
        self.assertEqual(result[0]['product_status'],'unsupported')
        with self.assertRaises(FileNotFoundError):provider_links.verify(self.root,self.providers,'claude')

    def test_provider_metadata_rejects_ambiguous_shapes(self):
        for value in ([self.entry(),self.entry()], [self.entry(products=['codex','codex'])],
                      [self.entry(sha256='changed')], [self.entry(entry='relative')],
                      [self.entry(id='bad id')]):
            self.save_providers(value)
            with self.assertRaises(provider_links.LinkError):provider_links.verify(self.root,self.providers,'codex')

    def test_source_references_are_not_followed_into_bundle(self):
        (self.root/'common/base/skills/own/linked').symlink_to(self.external)
        with self.assertRaises(ValueError):self.build()
        self.assertFalse(self.output.exists())

    def test_old_transform_or_vendoring_inputs_refused(self):
        for relative in ('bindings.toml','upstream/renamed.md'):
            path=self.root/'common/base/skills/own'/relative
            path.parent.mkdir(exist_ok=True);path.write_text('old transform input')
            with self.assertRaises(ValueError):self.build()
            self.assertFalse(self.output.exists());path.unlink()

    def test_transfer_gate_rejects_output_copy(self):
        real=builder.inspect
        def inspect(root,cat,scope,phase):
            if phase=='transfer':(self.output/'extra').write_bytes(self.external.read_bytes())
            return real(root,cat,scope,phase)
        with mock.patch.object(builder,'inspect',side_effect=inspect):
            with self.assertRaises(ValueError):self.build()
        self.assertTrue((self.output/'assembly.json').is_file(),'partial inventory must stay available for diagnosis')

    def test_source_changed_during_build_not_certified(self):
        real=builder.inspect
        def inspect(root,cat,scope,phase):
            if phase=='transfer':(self.root/'common/base/workflow.md').write_text('changed source')
            return real(root,cat,scope,phase)
        with mock.patch.object(builder,'inspect',side_effect=inspect):
            with self.assertRaises(ValueError):self.build()

    def test_actual_output_checked_after_scan_and_not_deleted(self):
        def mutate(*args):(self.output/'unexpected').write_text('new bytes')
        with self.assertRaises(ValueError):self.build(scanner=mutate)
        self.assertEqual((self.output/'unexpected').read_text(),'new bytes')

    def test_manifest_rewrite_during_scan_not_certified(self):
        def mutate(*args):(self.output/'assembly.json').write_text('{}')
        with self.assertRaises(ValueError):self.build(scanner=mutate)

    def test_scanner_failure_is_not_success_or_auto_cleanup(self):
        def fail(*args):raise RuntimeError('synthetic scanner failure')
        with self.assertRaises(RuntimeError):self.build(scanner=fail)
        self.assertTrue(self.output.exists())

    def test_own_bundle_with_real_pinned_gitleaks(self):
        result=builder.build(self.root,'codex',self.output,self.cat,self.scope,self.providers)
        self.assertEqual(len(result['files']),5)

    def test_provider_declaration_changed_during_build_not_certified(self):
        real=builder.inspect
        def inspect(root,cat,scope,phase):
            if phase=='transfer':self.save_providers([self.entry(version='2')])
            return real(root,cat,scope,phase)
        with mock.patch.object(builder,'inspect',side_effect=inspect):
            with self.assertRaises(ValueError):self.build()

    def test_instruction_template_cannot_vendor_external_reference(self):
        self.external.write_text('{{COMMON_INSTRUCTIONS}}\nexternal template body')
        self.cat.write_text(json.dumps(make_catalog([self.external])))
        self.save_providers()
        p=self.root/'adapters/codex/AGENTS.md.template';p.unlink();p.symlink_to(self.external)
        with self.assertRaises(ValueError):self.build()
        self.assertFalse(self.output.exists())

    def test_checksum_paths_not_mistaken_for_secret_values(self):
        (self.root/'common/base/skills/own/authoring.md').write_text('Own authoring policy')
        record=builder.build(self.root,'codex',self.output,self.cat,self.scope,self.providers)
        self.assertTrue(any(e['path'].endswith('/authoring.md') for e in record['files']))

    def test_manifest_path_does_not_exempt_real_secret(self):
        name='ghp_'+hashlib.sha256(b'nonexistent manifest path token').hexdigest()[:36]
        (self.root/'common/base/skills/own'/name).write_text('safe file body')
        with self.assertRaises(builder.secrets.GuardError):
            builder.build(self.root,'codex',self.output,self.cat,self.scope,self.providers)

    def test_real_scanner_blocks_secret_in_bundle(self):
        # A deterministic nonexistent token; never an account credential.
        key='ghp_'+hashlib.sha256(b'own assembly synthetic token').hexdigest()[:36]
        (self.root/'common/base/workflow.md').write_text('token='+key)
        with self.assertRaises(builder.secrets.GuardError):
            builder.build(self.root,'codex',self.output,self.cat,self.scope,self.providers)
        self.assertTrue(self.output.exists())
