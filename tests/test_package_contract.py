import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build import assemble,BuildError
from package import package

class PackageContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'src';self.base=self.root/'common/base';self.base.mkdir(parents=True)
        (self.base/'instructions.md').write_text('rules\n');(self.root/'VERSION').write_text('1.0.0\n')
        for product,title in [('codex','AGENTS'),('claude','CLAUDE')]:
            p=self.root/'adapters'/product;p.mkdir(parents=True);(p/(title+'.md.template')).write_text('{{COMMON_INSTRUCTIONS}}\n')
        self.out=Path(self.tmp.name)/'out'
    def hooks(self):
        p=self.root/'adapters/claude/hooks';p.mkdir();(p/'hooks.json').write_text('{"hooks":{"SessionStart":[]}}')
    def test_named_package_uses_one_identity_and_source(self):
        package(self.root,self.out,'codex',source_revision='a'*40,name='example-addon',repository='owner/addon',source_repository='owner/source')
        m=json.loads((self.out/'.agents/plugins/marketplace.json').read_text())
        self.assertEqual(m['name'],'example-addon')
        f=self.out/'plugins/example-addon/.codex-plugin/plugin.json'
        self.assertEqual(json.loads(f.read_text())['name'],'example-addon')
        self.assertIn('owner/source',(self.out/'README.md').read_text())
        assembly=json.loads((f.parents[1]/'assembly.json').read_text())
        self.assertEqual(assembly['source_revision'],'a'*40)
        self.assertEqual(assembly['build_contract'],1)
    def test_own_hooks_require_explicit_opt_in(self):
        self.hooks()
        with self.assertRaisesRegex(BuildError,'explicit opt-in'):assemble(self.root,'claude',self.out)
        self.assertFalse(self.out.exists())
    def test_own_hooks_are_reported_when_explicit(self):
        self.hooks();assemble(self.root,'claude',self.out,plugin_hooks=True)
        self.assertEqual(json.loads((self.out/'assembly.json').read_text())['plugin_hooks'],['SessionStart'])
    def test_shared_guard_hooks_are_explicitly_packaged_for_both_products(self):
        import shutil,hashlib
        source=Path(__file__).resolve().parents[1]
        scripts=self.base/'scripts';scripts.mkdir()
        shutil.copy2(source/'common/base/scripts/commit-guard.py',scripts/'commit-guard.py')
        for product in ('claude','codex'):
            shutil.copytree(source/f'adapters/{product}/hooks',self.root/f'adapters/{product}/hooks')
            output=self.out/product
            assemble(self.root,product,output,plugin_hooks=True)
            report=json.loads((output/'assembly.json').read_text())
            self.assertEqual(['PreToolUse'],report['plugin_hooks'])
            self.assertEqual(hashlib.sha256((scripts/'commit-guard.py').read_bytes()).hexdigest(),report['files']['scripts/commit-guard.py'])
            self.assertTrue((output/'hooks/hooks.json').is_file())

    def test_resource_is_copied_and_hashed(self):
        (self.root/'helper.py').write_text('print(1)\n')
        (self.base/'resources.toml').write_text('schema_version=1\n[[files]]\nsource="helper.py"\ntarget="scripts/helper.py"\n')
        assemble(self.root,'claude',self.out)
        self.assertEqual((self.out/'scripts/helper.py').read_text(),'print(1)\n')
        self.assertIn('scripts/helper.py',json.loads((self.out/'assembly.json').read_text())['files'])
    def test_invalid_identity_refused_before_output(self):
        with self.assertRaises(ValueError):package(self.root,self.out,source_revision='a'*40,name='../escape')
        self.assertFalse(self.out.exists())

if __name__=='__main__':unittest.main()
