"""Runtime route selection shares the assembly pin validator, never executes providers."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'common/base/scripts'))
import provider_links as links

class Routes(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.root=self.base/'kit';self.root.mkdir()
        self.original=self.base/'official/SKILL.md';self.original.parent.mkdir();self.original.write_text('Synthetic separately installed entry.\n')
        self.policy=self.base/'providers.json';self.entry={'id':'bmad-build','kind':'skill','entry':str(self.original),
        'products':['codex','claude'],'sha256':hashlib.sha256(self.original.read_bytes()).hexdigest(),
        'version':'fixture','source':'synthetic fixture; not official provenance proof'}
        self.save()

    def save(self,items=None):
        self.policy.write_text(json.dumps({'version':1,'providers':items or [self.entry]}))

    def resolve(self,product='codex',kind='skill',name='bmad-build'):
        return links.resolve(self.root,self.policy,product,name,kind)

    def cli(self,**changes):
        return subprocess.run([sys.executable,'-B',str(ROOT/'common/base/scripts/provider_links.py'),
        '--root',str(self.root),'--declaration',str(self.policy),'--product',changes.get('product','codex'),
        '--id',changes.get('name','bmad-build'),'--kind',changes.get('kind','skill')],capture_output=True,text=True,timeout=10)

    def test_both_products_resolve_current_bytes(self):
        for product in ('codex','claude'):
            result=self.resolve(product)
            self.assertEqual(result['entry'],str(self.original));self.assertEqual(result['product_status'],'entry-pin-verified')
            self.assertIn('provenance',result['limits'])

    def test_large_cli_bound_is_distinct_from_skill_bound(self):
        with patch.object(links, 'MAX_SKILL_BYTES', 1), patch.object(links, 'MAX_CLI_BYTES', 128):
            with self.assertRaisesRegex(ValueError, 'unsupported external entry'):
                self.resolve()
            self.entry['kind'] = 'cli'
            self.save()
            self.assertEqual(str(self.original), self.resolve(kind='cli')['entry'])

    def test_unselected_missing_provider_does_not_block_runtime(self):
        self.save([self.entry,{**self.entry,'id':'unused','entry':str(self.base/'absent')}])
        self.assertEqual(self.resolve()['id'],'bmad-build')
        with self.assertRaises(FileNotFoundError):links.verify(self.root,self.policy,'codex')

    def test_selected_missing_entry_is_unavailable(self):
        self.original.unlink()
        with self.assertRaises(FileNotFoundError):self.resolve()

    def test_kind_mismatch_is_not_silent_cli_or_skill_switch(self):
        with self.assertRaises(links.LinkError):self.resolve(kind='cli')

    def test_product_not_supported_is_not_available(self):
        self.entry['products']=['codex'];self.save()
        with self.assertRaises(links.LinkError):self.resolve(product='claude')

    def test_pin_drift_not_repinned(self):
        before=self.policy.read_bytes();self.original.write_text('new upstream bytes')
        with self.assertRaises(links.LinkError):self.resolve()
        self.assertEqual(before,self.policy.read_bytes())

    def test_no_name_based_fallback(self):
        with self.assertRaises(links.LinkError):self.resolve(name='bmad-prd')

    def test_duplicate_identifier_refused(self):
        self.save([self.entry,self.entry])
        with self.assertRaises(links.LinkError):self.resolve()

    def test_own_wrapper_cannot_be_external_entry(self):
        own=self.root/'SKILL.md';own.write_bytes(self.original.read_bytes())
        self.entry['entry']=str(own);self.save()
        with self.assertRaises(links.LinkError):self.resolve()

    def test_skill_entry_requires_actual_skill_file(self):
        other=self.original.with_name('guide.md');self.original.rename(other)
        self.entry['entry']=str(other);self.save()
        with self.assertRaises(links.LinkError):self.resolve()

    def test_entry_symlink_resolves_to_pinned_external_identity(self):
        alias=self.base/'alias';alias.symlink_to(self.original.parent,target_is_directory=True)
        self.entry['entry']=str(alias/'SKILL.md');self.save()
        self.assertEqual(self.resolve()['entry'],str(self.original))

    def test_success_cli_returns_pin_but_does_not_execute_entry(self):
        marker=self.base/'must-not-exist'
        self.original.write_text('raise RuntimeError("must not execute")\n'+str(marker))
        self.entry['sha256']=hashlib.sha256(self.original.read_bytes()).hexdigest();self.save()
        before=self.original.read_bytes();result=self.cli()
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout);self.assertEqual(data['entry'],str(self.original))
        self.assertNotIn('source',data);self.assertNotIn('version',data)
        self.assertEqual(before,self.original.read_bytes());self.assertFalse(marker.exists())

    def test_failure_cli_does_not_echo_fields_or_provider_content(self):
        self.policy.write_text('{"unexpected":"SYNTHETIC_PRIVATE_FIELD"}')
        result=self.cli();self.assertEqual(result.returncode,2)
        self.assertEqual(json.loads(result.stdout)['status'],'unavailable')
        self.assertNotIn('SYNTHETIC_PRIVATE_FIELD',result.stdout+result.stderr)
        self.assertNotIn(self.original.read_text(),result.stdout+result.stderr)
