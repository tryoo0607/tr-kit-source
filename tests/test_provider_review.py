"""Synthetic review records test drift/selection, never official authenticity."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'common/base/scripts'))
import provider_review as review
import orca_connection


class Review(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.kit = self.base / 'kit'; self.kit.mkdir()
        self.install = self.base / 'synthetic-install'; self.install.mkdir()
        self.entry = self.install / 'SKILL.md'; self.entry.write_text('Own synthetic skill fixture.')
        self.resource = self.install / 'template.md'; self.resource.write_text('Own synthetic template.')
        self.receipt = self.base / 'manager-receipt.json'; self.receipt.write_text('{"synthetic":true}')
        self.declaration = self.base / 'providers.json'
        self.provider = {'id': 'example', 'kind': 'skill', 'entry': str(self.entry),
                         'sha256': hashlib.sha256(self.entry.read_bytes()).hexdigest(),
                         'source': 'synthetic fixture', 'version': 'fixture-1', 'products': ['codex', 'claude']}
        self.declaration.write_text(json.dumps({'version': 1, 'providers': [self.provider]}))
        self.path = self.base / 'review.json'
        self.doc = self.snapshot()
        self.doc.update(review_status='reviewed', unresolved=[],
                        products={p: {'status': 'supported', 'basis': 'Synthetic reviewed fixture only.'} for p in ('codex', 'claude')})
        self.save()

    def snapshot(self):
        return review.snapshot(self.kit, self.declaration, 'codex', 'example', 'skill', self.install,
                               'native-plugin', 'https://example.invalid/official-fixture', [self.receipt])

    def save(self):
        self.path.write_text(json.dumps(self.doc))

    def verify(self, product='codex'):
        return review.verify(self.kit, self.declaration, product, 'example', 'skill', self.path)

    def test_snapshot_pending_no_false_authenticity(self):
        self.assertEqual(self.snapshot()['review_status'], 'pending')
        for p in ('codex', 'claude'):
            result = self.verify(p)
            self.assertEqual(result['status'], 'review-record-verified')
            self.assertFalse(result['native_verified']); self.assertFalse(result['provenance_authenticated'])

    def test_pending_or_unresolved_or_unsupported_not_executable(self):
        for field, value in [('review_status', 'pending'), ('unresolved', ['missing runtime']),
                             ('products', {'codex': {'status': 'unsupported', 'basis': 'not supported'}}),
                             ('products', {'codex': {'status': 'supported', 'basis': '  '}})]:
            with self.subTest(field=field, value=value):
                original = copy.deepcopy(self.doc)
                self.doc[field] = value; self.save()
                with self.assertRaises(ValueError): self.verify()
                self.doc = original

    def test_reference_drift_entry_unchanged_refused(self):
        self.resource.write_text('changed resource')
        with self.assertRaises(ValueError): self.verify()

    def test_missing_resource_refused(self):
        self.resource.unlink()
        with self.assertRaises(ValueError): self.verify()

    def test_added_resource_refused(self):
        (self.install / 'new.py').write_text('pass')
        with self.assertRaises(ValueError): self.verify()

    def test_entry_repin_cannot_reuse_old_review(self):
        self.entry.write_text('changed entry')
        self.provider['sha256'] = hashlib.sha256(self.entry.read_bytes()).hexdigest()
        self.declaration.write_text(json.dumps({'version': 1, 'providers': [self.provider]}))
        with self.assertRaises(ValueError): self.verify()

    def test_manager_evidence_drift_refused(self):
        self.receipt.write_text('changed receipt')
        with self.assertRaises(ValueError): self.verify()

    def test_missing_product_not_inferred_from_declaration(self):
        del self.doc['products']['claude']; self.save()
        with self.assertRaises(ValueError): self.verify('claude')

    def test_unselected_missing_provider_not_probed(self):
        self.declaration.write_text(json.dumps({'version': 1, 'providers': [self.provider,
            {**self.provider, 'id': 'missing', 'entry': str(self.base / 'absent')}]}))
        self.assertEqual(self.verify()['id'], 'example')

    def test_configured_route_requires_review_and_returns_pinned_entry(self):
        config = {'providers': str(self.declaration), 'provider_reviews': {}}
        with mock.patch.object(review.runtime_config, 'load', return_value=(None, config)):
            with self.assertRaisesRegex(ValueError, 'review missing'):
                review.verify_configured(self.kit, 'example', 'skill', 'codex')
            config['provider_reviews']['example'] = str(self.path)
            self.assertEqual(str(self.entry), review.verify_configured(self.kit, 'example', 'skill', 'codex')['entry'])

    def test_symlink_resource_not_followed(self):
        (self.install / 'alias').symlink_to(self.receipt)
        with self.assertRaises(ValueError): self.verify()

    def test_linked_ancestor_rejected(self):
        alias = self.base / 'alias'; alias.symlink_to(self.install, target_is_directory=True)
        with self.assertRaises(ValueError): review.tree(alias)

    def test_tree_limits_not_silent_truncation(self):
        with mock.patch.object(review, 'MAX_FILES', 1):
            with self.assertRaises(ValueError): self.snapshot()
        with mock.patch.object(review, 'MAX_BYTES', 1):
            with self.assertRaises(ValueError): self.snapshot()

    def test_release_cli_layouts_verify_and_reject_drift(self):
        self.provider['kind'] = 'cli'
        self.declaration.write_text(json.dumps({'version': 1, 'providers': [self.provider]}))
        for layout in ('standalone-cli', 'appimage'):
            with self.subTest(layout=layout):
                link = self.install / 'alias'
                if layout == 'appimage':
                    link.symlink_to(self.resource.name)
                doc = review.snapshot(self.kit, self.declaration, 'codex', 'example', 'cli', self.install,
                                      'official-release', 'https://example.invalid/release', [self.receipt], layout)
                self.assertEqual(1 if layout == 'standalone-cli' else 3, len(doc['files']))
                doc.update(review_status='reviewed', unresolved=[],
                           products={'codex': {'status': 'supported', 'basis': 'Synthetic fixture.'}})
                self.path.write_text(json.dumps(doc))
                review.verify(self.kit, self.declaration, 'codex', 'example', 'cli', self.path)
                if layout == 'appimage':
                    link.unlink()
                    link.symlink_to('../' + self.receipt.name)
                    with self.assertRaisesRegex(ValueError, 'unsupported installation link'):
                        review.verify(self.kit, self.declaration, 'codex', 'example', 'cli', self.path)

    def test_orca_launcher_checked_again_before_execution(self):
        selector = self.base / 'installed'
        launcher = self.base / 'orca'
        launcher.write_text(f'#!/bin/sh\nexec "{selector}" "$@"\n')
        launcher.chmod(0o700)
        selector.symlink_to(self.entry)
        evidence = self.base / 'orca-launcher.json'
        evidence.write_text(json.dumps({
            'selector': str(selector),
            'launchers': {str(launcher): review.digest(launcher.read_bytes())},
        }))
        cli = {**self.provider, 'id': 'orca-cli', 'kind': 'cli'}
        self.declaration.write_text(json.dumps({'version': 1, 'providers': [cli]}))
        doc = review.snapshot(self.kit, self.declaration, 'codex', 'orca-cli', 'cli', self.install,
                              'official-release', 'https://example.invalid/release', [evidence], 'appimage')
        doc.update(review_status='reviewed', unresolved=[],
                   products={'codex': {'status': 'supported', 'basis': 'Synthetic fixture.'}})
        self.path.write_text(json.dumps(doc))
        config = {'providers': str(self.declaration), 'provider_reviews': {'orca-cli': str(self.path)}}
        with mock.patch.object(orca_connection, 'ROOT', self.kit), \
                mock.patch.object(orca_connection.runtime_config, 'load', return_value=(None, config)):
            connection = orca_connection.OrcaConnection(str(launcher), 'codex')
            self.assertEqual(str(self.entry), connection.checked_entry())
            selector.unlink()
            selector.symlink_to(self.resource)
            with self.assertRaisesRegex(ValueError, 'launcher target changed'):
                connection.checked_entry()

    def test_cli_package_tracks_nested_binary_and_internal_links(self):
        self.provider['kind'] = 'cli'
        self.declaration.write_text(json.dumps({'version': 1, 'providers': [self.provider]}))
        alias = self.install / 'alias'
        alias.symlink_to(self.resource.name)
        def snapshot(method='npm'):
            return review.snapshot(self.kit, self.declaration, 'codex', 'example', 'cli', self.install,
                                   method, 'https://example.invalid/package', [self.receipt], 'cli-package')
        with self.assertRaisesRegex(ValueError, 'incompatible'):
            snapshot('official-release')
        doc = snapshot()
        doc.update(review_status='reviewed', unresolved=[],
                   products={'codex': {'status': 'supported', 'basis': 'Synthetic fixture.'}})
        self.path.write_text(json.dumps(doc))
        def verify():
            return review.verify(self.kit, self.declaration, 'codex', 'example', 'cli', self.path)
        self.assertEqual(3, verify()['files'])
        self.resource.write_text('changed nested resource')
        with self.assertRaisesRegex(ValueError, 'resources or evidence changed'):
            verify()
        alias.unlink()
        alias.symlink_to('../' + self.receipt.name)
        with self.assertRaisesRegex(ValueError, 'unsupported installation link'):
            verify()

    def test_own_root_and_unrelated_installation_rejected(self):
        for path in (self.kit, self.base / 'missing'):
            with self.assertRaises(ValueError):
                review.snapshot(self.kit, self.declaration, 'codex', 'example', 'skill', path,
                                'npm', 'https://example.invalid', [self.receipt])

    def test_comparison_reports_resources_and_contract_no_auto_accept(self):
        new = copy.deepcopy(self.doc)
        new['files'] = [x for x in new['files'] if x['path'] != 'template.md']
        new['files'][0]['sha256'] = '0' * 64
        new['files'].append({'path': 'new.md', 'sha256': '1' * 64, 'size': 3})
        new['provider']['version'] = 'fixture-2'
        new['products']['claude']['status'] = 'unsupported'
        after = self.base / 'after.json'; after.write_text(json.dumps(new))
        before = self.path.read_bytes()
        result = review.compare(self.path, after)
        self.assertEqual(result['added'], ['new.md']); self.assertEqual(result['removed'], ['template.md'])
        self.assertEqual(result['changed'], ['SKILL.md']); self.assertTrue(result['identity_changed'])
        self.assertTrue(result['product_contract_changed']); self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(result['status'], 'comparison-only')

    def test_corrupt_or_traversal_inventory_rejected(self):
        for path in ('../escape', '/absolute', 'a/../b', '.'):
            self.doc['files'][0]['path'] = path; self.save()
            with self.assertRaises(ValueError): self.verify()

    def test_cli_failure_redacts_external_fields(self):
        self.path.write_text('{"SYNTHETIC_PRIVATE_FIELD":"not echoed"}')
        result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/provider-review.py'), 'verify',
            '--root', str(self.kit), '--declaration', str(self.declaration), '--product', 'codex',
            '--id', 'example', '--kind', 'skill', '--review', str(self.path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('SYNTHETIC_PRIVATE_FIELD', result.stdout + result.stderr)
        self.assertNotIn(str(self.path), result.stdout + result.stderr)


if __name__ == '__main__': unittest.main()
