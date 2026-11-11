import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/build.py'
spec = importlib.util.spec_from_file_location('redesign_assembly', SCRIPT)
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class AssemblyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'source'
        self.base = self.root / 'common/base'
        self.base.mkdir(parents=True)
        (self.base / 'instructions.md').write_text('Shared rules\n')
        for product, name in [('claude', 'CLAUDE'), ('codex', 'AGENTS')]:
            folder = self.root / 'adapters' / product
            folder.mkdir(parents=True)
            (folder / (name + '.md.template')).write_text('{{COMMON_INSTRUCTIONS}}\n')
        self.origin = Path(self.tmp.name) / 'origin'
        skill = self.origin / 'skills/review'
        (skill / 'scripts').mkdir(parents=True)
        (skill / 'SKILL.md').write_text('---\nname: review\ndescription: Review\nhooks:\n  Stop: []\n---\nReview\n')
        (skill / 'scripts/check.py').write_text('print("ok")\n')
        (skill / 'scripts/check.py').chmod(0o755)
        (self.origin / 'hooks').mkdir()
        (self.origin / 'hooks/hooks.json').write_text('{"hooks":{"SessionStart":[]}}')
        for args in [('init',), ('add', '.'), ('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'fixture')]:
            subprocess.run(['git', '-C', str(self.origin), *args], check=True, capture_output=True)
        self.commit = subprocess.check_output(['git', '-C', str(self.origin), 'rev-parse', 'HEAD'], text=True).strip()
        self.declaration = f'schema_version = 1\n[[skills]]\nid = "review"\nsource = "{self.origin}"\nrevision = "{self.commit}"\npath = "skills/review"\n'
        (self.base / 'dependencies.toml').write_text(self.declaration)
        self.output = Path(self.tmp.name) / 'output'

    def test_claude_preserves_skill_hook_and_excludes_plugin_hook(self):
        build.assemble(self.root, 'claude', self.output)
        self.assertIn('hooks:', (self.output / 'skills/review/SKILL.md').read_text())
        self.assertTrue((self.output / 'skills/review/scripts/check.py').exists())
        self.assertEqual(0o755, (self.output / 'skills/review/scripts/check.py').stat().st_mode & 0o777)
        self.assertNotIn(build.MODIFICATION_NOTICE, (self.output / 'skills/review/SKILL.md').read_text())
        self.assertFalse((self.output / 'hooks').exists())
        self.assertEqual('Shared rules\n\n', (self.output / 'CLAUDE.md').read_text())
        report = json.loads((self.output / 'assembly.json').read_text())
        self.assertEqual(self.commit, report['dependencies'][0]['revision'])

    def test_codex_rejects_unadapted_skill_hook(self):
        with self.assertRaisesRegex(build.BuildError, 'hook adapter required'):
            build.assemble(self.root, 'codex', self.output)
        self.assertFalse(self.output.exists())

    def test_local_python_cache_is_not_packaged(self):
        scripts = self.base / 'scripts'
        (scripts / '__pycache__').mkdir(parents=True)
        (scripts / '__pycache__/helper.cpython-312.pyc').write_bytes(b'local cache')
        (scripts / 'helper.py').write_text('print("helper")\n')
        build.assemble(self.root, 'claude', self.output)
        self.assertTrue((self.output / 'scripts/helper.py').is_file())
        self.assertFalse(list(self.output.rglob('*.pyc')))

    def test_session_runtime_refresh_script_is_in_both_products(self):
        (self.base / 'dependencies.toml').write_text('schema_version=1\n')
        actual = SCRIPT.parents[1] / 'common/base/skills/session'
        import shutil
        shutil.copytree(actual, self.base / 'skills/session')
        for product in ('claude', 'codex'):
            with self.subTest(product=product):
                output = self.output / product
                build.assemble(self.root, product, output)
                helper = output / 'skills/session/scripts/runtime_refresh.py'
                self.assertEqual((actual / 'scripts/runtime_refresh.py').read_bytes(), helper.read_bytes())
                result = subprocess.run(['python3', str(helper), '--help'], capture_output=True, text=True)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn('inspect', result.stdout)

    def test_repository_alias_resolves_only_in_selected_cache(self):
        declaration = self.declaration.replace(str(self.origin), self.origin.name)
        (self.base / 'dependencies.toml').write_text(declaration)
        build.assemble(self.root, 'claude', self.output, source_cache=self.origin.parent)
        self.assertTrue((self.output / 'skills/review/SKILL.md').is_file())

    def test_codex_marketplace_has_versioned_payload_and_no_legacy_tree(self):
        (self.base / 'dependencies.toml').write_text('schema_version=1\n')
        command = ['python3', str(SCRIPT.with_name('package.py')), '--root', str(self.root),
                   '--output', str(self.output), '--version', '0.6.0', '--source-revision', self.commit]
        result = subprocess.run(command, text=True, capture_output=True, check=True)
        self.assertFalse(json.loads(result.stdout)['installed'])
        marketplace = json.loads((self.output / '.agents/plugins/marketplace.json').read_text())
        self.assertEqual('./plugins/tr-codex', marketplace['plugins'][0]['source']['path'])
        self.assertEqual('tr-codex', marketplace['name'])
        payload = self.output / 'plugins/tr-codex'
        manifest = json.loads((payload / '.codex-plugin/plugin.json').read_text())
        self.assertEqual(f'0.6.0+codex.{self.commit[:12]}', manifest['version'])
        self.assertTrue((payload / 'assembly.json').is_file())
        self.assertFalse((payload / 'backbone').exists())
        installer = SCRIPT.parents[1] / 'install.sh'
        dry = subprocess.run(['bash', str(installer), 'codex', str(self.output)],
                             text=True, capture_output=True)
        self.assertEqual(0, dry.returncode, dry.stderr)
        self.assertIn('[dry-run]', dry.stdout)
        (payload / 'AGENTS.md').write_text('unreviewed change')
        tampered = subprocess.run(['bash', str(installer), 'codex', str(self.output)],
                                  text=True, capture_output=True)
        self.assertNotEqual(0, tampered.returncode)
        self.assertIn('integrity mismatch', tampered.stderr)
        second = subprocess.run(command, text=True, capture_output=True)
        self.assertNotEqual(0, second.returncode)
        self.assertTrue((payload / 'assembly.json').is_file())

    def test_resources_preserve_runtime_without_enabling_hooks(self):
        (self.base / 'dependencies.toml').write_text(self.declaration +
            'resources=[{source="hooks", target="runtimes/review/hooks"}]\n')
        build.assemble(self.root, 'claude', self.output)
        self.assertTrue((self.output / 'runtimes/review/hooks/hooks.json').is_file())
        self.assertFalse((self.output / 'hooks').exists())
        report = json.loads((self.output / 'assembly.json').read_text())
        self.assertEqual([], report['plugin_hooks'])
        self.assertEqual('hooks', report['dependencies'][0]['resources'][0]['source'])

    def test_resource_traversal_and_collision_are_rejected(self):
        for source, target in [('hooks', '../escape'), ('../escape', 'runtime'), ('hooks', 'skills/review')]:
            with self.subTest(source=source, target=target):
                (self.base / 'dependencies.toml').write_text(self.declaration +
                    f'resources=[{{source="{source}", target="{target}"}}]\n')
                with self.assertRaises(build.BuildError):
                    build.assemble(self.root, 'claude', self.output)
                self.assertFalse(self.output.exists())

    def test_product_mcp_configuration_is_packaged(self):
        path = self.root / 'adapters/claude/mcp.json'
        path.write_text('{"mcpServers":{"memory":{"command":"python3","args":[]}}}')
        build.assemble(self.root, 'claude', self.output)
        self.assertEqual(json.loads(path.read_text()), json.loads((self.output / '.mcp.json').read_text()))

    def test_codex_mcp_launches_packaged_helper_from_an_unrelated_workspace(self):
        (self.base / 'dependencies.toml').write_text('schema_version=1\n')
        actual_adapter = SCRIPT.parents[1] / 'adapters/codex/mcp.json'
        (self.root / 'adapters/codex/mcp.json').write_bytes(actual_adapter.read_bytes())
        helper = self.base / 'scripts/records.py'
        helper.parent.mkdir()
        helper.write_text('import json,sys; print(json.dumps({"args":sys.argv[1:]}))\n')
        build.assemble(self.root, 'codex', self.output)
        unrelated = Path(self.tmp.name) / 'caller'; unrelated.mkdir()
        launcher = (
            'import json,pathlib,subprocess,sys; root=pathlib.Path(sys.argv[1]); '
            'spec=json.loads((root/".mcp.json").read_text())["mcpServers"]["claude-mem"]; '
            'cwd=(root/spec["cwd"]).resolve() if "cwd" in spec else pathlib.Path.cwd(); '
            'p=subprocess.run([spec["command"],*spec["args"]],cwd=cwd,check=True,capture_output=True,text=True); '
            'print(p.stdout,end="")'
        )
        launched = subprocess.run(['python3', '-c', launcher, str(self.output)],
                                  cwd=unrelated, capture_output=True, text=True)
        self.assertEqual(0, launched.returncode, launched.stderr)
        self.assertEqual({'args': ['mem-mcp']}, json.loads(launched.stdout))

    def test_duplicate_declaration_is_error(self):
        (self.root / 'adapters/claude/dependencies.toml').write_text(self.declaration)
        with self.assertRaisesRegex(build.BuildError, 'duplicate'):
            build.assemble(self.root, 'claude', self.output)

    def test_dirty_checkout_is_rejected(self):
        (self.origin / 'extra').write_text('changed')
        with self.assertRaisesRegex(build.BuildError, 'dirty source'):
            build.assemble(self.root, 'claude', self.output)

    def test_path_escape_is_rejected(self):
        (self.base / 'dependencies.toml').write_text(self.declaration.replace('skills/review', '../outside'))
        with self.assertRaisesRegex(build.BuildError, 'escapes'):
            build.assemble(self.root, 'claude', self.output)

    def test_output_is_never_overwritten(self):
        self.output.mkdir()
        (self.output / 'keep').write_text('original')
        with self.assertRaisesRegex(build.BuildError, 'already exists'):
            build.assemble(self.root, 'claude', self.output)
        self.assertEqual('original', (self.output / 'keep').read_text())

    def test_unresolved_template_leaves_no_output(self):
        (self.root / 'adapters/claude/CLAUDE.md.template').write_text('{{COMMON_INSTRUCTIONS}}\n{{MISSING}}')
        with self.assertRaisesRegex(build.BuildError, 'unresolved'):
            build.assemble(self.root, 'claude', self.output)
        self.assertFalse(self.output.exists())

    def binding(self, text):
        folder = self.root / 'adapters/claude/skills/review'
        folder.mkdir(parents=True)
        (folder / 'bindings.toml').write_text(text)

    def test_binding_preserves_frontmatter_and_original(self):
        self.binding('schema_version = 1\nruntime_note = "Resolve skill_dir from the loaded skill path."\n'
                     '[[replacements]]\nfile="SKILL.md"\nold="\\nReview\\n"\nnew="\\nRead script\\n"\ncount=1\n'
                     'target_file="scripts/check.py"\n')
        original = (self.origin / 'skills/review/SKILL.md').read_text()
        build.assemble(self.root, 'claude', self.output)
        content = (self.output / 'skills/review/SKILL.md').read_text()
        self.assertTrue(content.startswith('---\nname: review\n'))
        self.assertIn('hooks:', content)
        self.assertIn('Resolve skill_dir', content)
        self.assertEqual(1, content.count(build.MODIFICATION_NOTICE))
        self.assertEqual(original, (self.origin / 'skills/review/SKILL.md').read_text())
        self.assertFalse((self.output / 'skills/review/bindings.toml').exists())
        self.assertEqual(1, len(json.loads((self.output / 'assembly.json').read_text())['bindings']))

    def test_binding_drift_blocks_output(self):
        self.binding('schema_version=1\n[[replacements]]\nfile="SKILL.md"\nold="not present"\nnew="replacement"\ncount=1\n')
        with self.assertRaisesRegex(build.BuildError, 'source drift'):
            build.assemble(self.root, 'claude', self.output)
        self.assertFalse(self.output.exists())

    def test_binding_missing_skill_blocks_output(self):
        self.binding('schema_version=1\n[[replacements]]\nfile="SKILL.md"\nold="Review\\n"\nnew="Other\\n"\ncount=1\ntarget_skill="other"\n')
        with self.assertRaisesRegex(build.BuildError, 'missing linked skill'):
            build.assemble(self.root, 'claude', self.output)

    def test_binding_cannot_modify_executable(self):
        self.binding('schema_version=1\n[[replacements]]\nfile="scripts/check.py"\nold="ok"\nnew="changed"\ncount=1\n')
        with self.assertRaisesRegex(build.BuildError, 'only modify Markdown'):
            build.assemble(self.root, 'claude', self.output)

    def test_required_skill_must_be_declared(self):
        (self.base / 'dependencies.toml').write_text(self.declaration + 'requires=["missing"]\n')
        with self.assertRaisesRegex(build.BuildError, 'required skill'):
            build.assemble(self.root, 'claude', self.output)

    def test_common_binding_then_product_binding_for_external_skill(self):
        folder = self.base / 'skills/review'
        folder.mkdir(parents=True)
        (folder / 'bindings.toml').write_text('schema_version=1\nruntime_note="Shared policy"\n')
        self.binding('schema_version=1\n[[replacements]]\nfile="SKILL.md"\n'
                     'old="Shared policy"\nnew="Shared policy with product call"\ncount=1\n')
        build.assemble(self.root, 'claude', self.output)
        text = (self.output / 'skills/review/SKILL.md').read_text()
        self.assertIn('Shared policy with product call', text)
        self.assertEqual(1, text.count(build.MODIFICATION_NOTICE))
        self.assertFalse(list(self.output.rglob('bindings.toml')))
        report = json.loads((self.output / 'assembly.json').read_text())
        self.assertEqual(['common', 'claude'], [item['scope'] for item in report['bindings']])

    def test_license_is_copied_from_verified_checkout(self):
        (self.base / 'dependencies.toml').write_text(self.declaration + 'license_files=["AGREEMENT", "NOTICE"]\n')
        # A file outside the selected skill but tracked by the pinned source.
        (self.origin / 'AGREEMENT').write_text('Preserve this license\n')
        (self.origin / 'NOTICE').write_text('Upstream attribution\n')
        subprocess.run(['git', '-C', str(self.origin), 'add', 'AGREEMENT', 'NOTICE'], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(self.origin), '-c', 'user.name=Test', '-c',
                        'user.email=test@example.invalid', 'commit', '-m', 'license'], check=True, capture_output=True)
        commit = subprocess.check_output(['git', '-C', str(self.origin), 'rev-parse', 'HEAD'], text=True).strip()
        declaration = (self.base / 'dependencies.toml').read_text().replace(self.commit, commit)
        (self.base / 'dependencies.toml').write_text(declaration)
        build.assemble(self.root, 'claude', self.output)
        self.assertEqual('Preserve this license\n', (self.output / 'skills/review/AGREEMENT').read_text())
        self.assertEqual(b'Upstream attribution\n', (self.output / 'skills/review/NOTICE').read_bytes())

    def test_metadata_only_change_has_notice_after_frontmatter(self):
        self.binding('schema_version=1\n[[replacements]]\nfile="SKILL.md"\n'
                     'old="description: Review"\nnew="description: >-\\n  Review"\ncount=1\n')
        original = (self.origin / 'skills/review/SKILL.md').read_text()
        build.assemble(self.root, 'claude', self.output)
        result = (self.output / 'skills/review/SKILL.md').read_text()
        expected = original.replace('description: Review', 'description: >-\n  Review')
        self.assertEqual(expected, result.replace(build.MODIFICATION_NOTICE, '', 1))
        self.assertGreater(result.index(build.MODIFICATION_NOTICE), result.index('\n---\n', 4))

    def test_local_binding_does_not_claim_upstream_modification(self):
        local = self.base / 'skills/local'
        local.mkdir(parents=True)
        (local / 'SKILL.md').write_text('---\nname: local\ndescription: Local\n---\nOwn text.\n')
        (local / 'bindings.toml').write_text('schema_version=1\nruntime_note="Local product connection"\n')
        build.assemble(self.root, 'claude', self.output)
        result = (self.output / 'skills/local/SKILL.md').read_text()
        self.assertIn('Local product connection', result)
        self.assertNotIn(build.MODIFICATION_NOTICE, result)

    def test_changed_resource_markdown_is_marked_without_changing_original(self):
        (self.origin / 'README.md').write_text('# Upstream\nOriginal link.\n')
        subprocess.run(['git', '-C', str(self.origin), 'add', 'README.md'], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(self.origin), '-c', 'user.name=Test', '-c',
                        'user.email=test@example.invalid', 'commit', '-m', 'resource'], check=True, capture_output=True)
        revision = subprocess.check_output(['git', '-C', str(self.origin), 'rev-parse', 'HEAD'], text=True).strip()
        declaration = self.declaration.replace(self.commit, revision)
        declaration += 'resources=[{source="README.md",target="skills/review/UPSTREAM-README.md"}]\n'
        (self.base / 'dependencies.toml').write_text(declaration)
        self.binding('schema_version=1\n[[replacements]]\nfile="UPSTREAM-README.md"\n'
                     'old="Original link."\nnew="Pinned link."\ncount=1\n')
        build.assemble(self.root, 'claude', self.output)
        result = (self.output / 'skills/review/UPSTREAM-README.md').read_text()
        self.assertTrue(result.startswith(build.MODIFICATION_NOTICE))
        self.assertEqual('# Upstream\nPinned link.\n', result.replace(build.MODIFICATION_NOTICE, '', 1))
        self.assertEqual('# Upstream\nOriginal link.\n', (self.origin / 'README.md').read_text())
        self.assertEqual('', subprocess.check_output(['git', '-C', str(self.origin), 'status', '--porcelain'], text=True))

    def test_invalid_license_inputs_leave_no_release(self):
        for value in ['../outside', '/etc/passwd', 'missing']:
            with self.subTest(path=value):
                (self.base / 'dependencies.toml').write_text(self.declaration + f'license_files=["{value}"]\n')
                with self.assertRaises(build.BuildError):
                    build.assemble(self.root, 'claude', self.output)
                self.assertFalse(self.output.exists())

    def test_wrapped_dependency_preserves_one_entrypoint_and_original(self):
        folder = self.base / 'skills/review'
        folder.mkdir(parents=True)
        wrapper = '---\nname: review\ndescription: Local wrapper\n---\nRead selected upstream docs.\n'
        (folder / 'SKILL.md').write_text(wrapper)
        (self.base / 'dependencies.toml').write_text(self.declaration + 'wrapped=true\n')
        original = (self.origin / 'skills/review/SKILL.md').read_bytes()
        build.assemble(self.root, 'claude', self.output)
        result = self.output / 'skills/review'
        self.assertEqual(wrapper, (result / 'SKILL.md').read_text())
        self.assertEqual(original, (result / 'upstream/GUIDE.md').read_bytes())
        self.assertEqual([result / 'SKILL.md'], list(result.rglob('SKILL.md')))
        self.assertTrue((result / 'upstream/scripts/check.py').exists())

    def test_wrapped_dependency_without_local_entrypoint_is_rejected(self):
        (self.base / 'dependencies.toml').write_text(self.declaration + 'wrapped=true\n')
        with self.assertRaisesRegex(build.BuildError, 'missing wrapper'):
            build.assemble(self.root, 'claude', self.output)
        self.assertFalse(self.output.exists())

    def test_codex_declares_discoverable_skill_directory(self):
        (self.base / 'dependencies.toml').write_text('schema_version=1\n')
        folder = self.base / 'skills/review'
        folder.mkdir(parents=True)
        (folder / 'SKILL.md').write_text('---\nname: review\ndescription: Review\n---\nRead files.\n')
        build.assemble(self.root, 'codex', self.output)
        manifest = json.loads((self.output / '.codex-plugin/plugin.json').read_text())
        self.assertEqual('./skills/', manifest['skills'])
        self.assertTrue((self.output / manifest['skills'] / 'review/SKILL.md').is_file())


if __name__ == '__main__':
    unittest.main()
