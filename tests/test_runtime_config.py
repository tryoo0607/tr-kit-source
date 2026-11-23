"""Host pointer selection and real guard subprocesses, no native trust claims."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT/'common/base/scripts'))
import runtime_config
from upstream_guard import make_catalog


class RuntimeConfig(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name).resolve()
        self.config = self.base/'runtime.json'
        self.binding = self.base/'binding.json'
        self.doc = {'schema_version': 1, 'product': 'codex',
                    'providers': str(self.base/'providers.json'),
                    'provider_reviews': {'sample': str(self.base/'review.json')},
                    'upstream_binding': str(self.binding)}
        self.save()
        self.env = mock.patch.dict(os.environ, {'TR_KIT_RUNTIME_CONFIG': str(self.config)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def save(self):
        self.config.write_text(json.dumps(self.doc))
        self.config.chmod(0o600)

    def call(self, product, action, payload):
        env = dict(os.environ)
        env.pop('TR_KIT_UPSTREAM_BINDING', None)
        args = [sys.executable, '-B', str(ROOT/'scripts/plugin-runtime.py'), action, '--product', product]
        if action == 'upstream':
            args += ['--event', payload['hook_event_name']]
        result = subprocess.run(args, input=json.dumps(payload), text=True,
                                capture_output=True, env=env, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_load_pointers_without_opening_unselected_resources(self):
        for product in ('codex', 'claude'):
            self.doc['product'] = product
            self.save()
            path, data = runtime_config.load(product)
            self.assertEqual(path, self.config)
            self.assertEqual(data, self.doc)
            self.assertFalse((self.base/'review.json').exists())

    def test_default_product_specific_location(self):
        for product in ('codex', 'claude'):
            target = self.base/'.config/tr-kit'/('runtime-'+product+'.json')
            target.parent.mkdir(parents=True, exist_ok=True)
            self.doc['product'] = product
            target.write_text(json.dumps(self.doc))
            target.chmod(0o600)
            with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(Path, 'home', return_value=self.base):
                self.assertEqual(runtime_config.load(product)[0], target)

    def test_schema_product_unknown_duplicate_and_boolean_rejected(self):
        for change in ({'product': 'claude'}, {'unknown': True}, {'schema_version': True},
                       {'provider_reviews': {}}, {'providers': 'relative'}):
            original = dict(self.doc)
            self.doc.update(change)
            self.save()
            with self.assertRaises(ValueError):
                runtime_config.load('codex')
            self.doc = original
        self.config.write_text(json.dumps(self.doc)[:-1]+',"product":"codex"}')
        with self.assertRaises(ValueError):
            runtime_config.load('codex')

    def test_explicit_bad_selection_does_not_fall_back(self):
        for selected in ('', 'relative', str(self.base/'missing')):
            with mock.patch.dict(os.environ, {'TR_KIT_RUNTIME_CONFIG': selected}):
                with self.assertRaises((ValueError, OSError)):
                    runtime_config.load('codex')

    def test_symlink_alias_permissions_and_nonregular_rejected(self):
        alias = self.base/'alias'
        alias.symlink_to(self.config)
        for selected in (str(alias), str(self.base/'sub/../runtime.json'), str(self.base)):
            with mock.patch.dict(os.environ, {'TR_KIT_RUNTIME_CONFIG': selected}):
                with self.assertRaises((ValueError, OSError)):
                    runtime_config.load('codex')
        self.config.chmod(0o622)
        with self.assertRaises(ValueError):
            runtime_config.load('codex')

    def test_context_cli_delivers_only_explicit_pointers_for_both_products(self):
        for product in ('codex', 'claude'):
            self.doc['product'] = product
            self.save()
            result = self.call(product, 'context', {'hook_event_name': 'SessionStart'})
            text = result['hookSpecificOutput']['additionalContext']
            self.assertIn(str(self.config), text)
            self.assertIn(self.doc['providers'], text)
            self.assertIn('provider_reviews[ID]', text)
            self.assertNotIn(self.doc['provider_reviews']['sample'], text)

    def test_context_missing_config_reports_not_ready(self):
        self.config.unlink()
        self.assertFalse(self.call('codex', 'context', {'hook_event_name': 'SessionStart'})['continue'])

    def test_real_guard_routes_host_binding_scope_and_original_for_both_products(self):
        project = self.base/'kit'
        project.mkdir()
        original = self.base/'official.md'
        content = 'Synthetic official body. Preserve source and connect without copying.\n'*3
        original.write_text(content)
        catalog = self.base/'catalog.json'
        catalog.write_text(json.dumps(make_catalog([original])))
        scope = self.base/'scope.json'
        scope.write_text(json.dumps({'version': 1, 'components': ['.'], 'artifacts': []}))
        self.binding.write_text(json.dumps({'root': str(project), 'catalog': str(catalog), 'scope': str(scope)}))
        for product in ('codex', 'claude'):
            self.doc['product'] = product
            self.save()
            for body, target, blocked in [('Own connector\n', project/'x', False),
                                           (content, project/'x', True),
                                           (content, self.base/'outside', False)]:
                tool, data = 'Write', {'file_path': str(target), 'content': body}
                if product == 'codex':
                    tool = 'apply_patch'
                    data = {'command': '*** Begin Patch\n*** Add File: '+str(target)+'\n'+
                            ''.join('+'+line+'\n' for line in body.splitlines())+'*** End Patch'}
                result = self.call(product, 'upstream', {'hook_event_name': 'PreToolUse',
                    'cwd': str(project), 'tool_name': tool, 'tool_input': data})
                if blocked:
                    self.assertEqual(result['hookSpecificOutput']['permissionDecision'], 'deny')
                else:
                    self.assertEqual(result, {})
            self.assertEqual(original.read_text(), content)

    def test_explicit_legacy_binding_takes_precedence_without_fallback(self):
        import plugin_runtime
        with mock.patch.dict(os.environ, {'TR_KIT_UPSTREAM_BINDING': 'relative'}):
            with self.assertRaises(ValueError):
                plugin_runtime.upstream(ROOT, 'codex', 'PreToolUse', b'{}')


if __name__ == '__main__':
    unittest.main()
