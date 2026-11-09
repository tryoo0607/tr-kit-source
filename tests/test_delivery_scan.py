"""Opt in locally with TR_KIT_TEST_GITLEAKS; required with the pinned binary in CI."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import test_delivery
import delivery
from delivery_scan import scan, ScanError, FindingsError, _native


class IntegrityTests(unittest.TestCase):
    setUp = test_delivery.DeliveryTests.setUp
    run_git = test_delivery.DeliveryTests.run_git

    def rewrite(self, path, data):
        path.write_text(json.dumps(data, indent=2) + '\n')

    def refresh_release(self, package):
        report = json.loads((package / 'release.json').read_bytes())
        report['files'] = {str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(package.rglob('*')) if p.is_file() and p.name != 'release.json'}
        self.rewrite(package / 'release.json', report)

    def test_duplicate_and_incomplete_assembly_rejected(self):
        package = self.output / 'codex'
        assembly = package / 'plugins/tr-codex/assembly.json'
        report = json.loads(assembly.read_bytes())
        report['files'].pop(next(iter(report['files'])))
        self.rewrite(assembly, report)
        self.refresh_release(package)
        with self.assertRaisesRegex(ValueError, 'assembly integrity'):
            delivery.verify(package, 'codex', self.revision)
        release = package / 'release.json'
        release.write_text('{"files": {}, "files": {}}')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            delivery.verify(package, 'codex', self.revision)

    def test_scanner_missing_and_wrong_version(self):
        for executable in (self.root / 'missing', Path('/bin/true')):
            with self.assertRaises(ScanError):
                scan(self.output / 'codex', 'codex', self.revision, executable)

    def test_wrong_digest_changed_payload_and_fake_assembly_revision(self):
        package = self.output / 'codex'
        release = package / 'release.json'
        original = release.read_bytes()
        report = json.loads(original)
        target_name = next(iter(report['files']))
        report['files'][target_name] = '0' * 64
        self.rewrite(release, report)
        with self.assertRaisesRegex(ValueError, 'release integrity'):
            delivery.verify(package, 'codex', self.revision)
        release.write_bytes(original)
        target = package / target_name
        payload = target.read_bytes()
        target.write_bytes(payload + b'changed')
        with self.assertRaisesRegex(ValueError, 'release integrity'):
            delivery.verify(package, 'codex', self.revision)
        target.write_bytes(payload)
        assembly = package / 'plugins/tr-codex/assembly.json'
        forged = json.loads(assembly.read_bytes())
        forged['source_revision'] = 'b' * 40
        self.rewrite(assembly, forged)
        self.refresh_release(package)
        with self.assertRaisesRegex(ValueError, 'assembly provenance'):
            delivery.verify(package, 'codex', self.revision)

    def test_malformed_unknown_and_failed_report_are_scanner_errors(self):
        for data, code in [('not JSON', 42), ('[]', 42), ('[]', 2),
                           (json.dumps([{'File': '../candidate-00000000'}]), 42)]:
            def fake(command, **kwargs):
                Path(command[command.index('--report-path') + 1]).write_text(data)
                return subprocess.CompletedProcess(command, code)
            with patch('delivery_scan.subprocess.run', side_effect=fake):
                with self.assertRaises(ScanError):
                    _native({'release.json': b'{}'}, '/scanner')

    def test_second_product_scan_failure_prevents_both_remote_writes(self):
        origin, before = test_delivery.DeliveryTests.repository(self)
        original_git = delivery.git
        source = Path(delivery.__file__).resolve().parents[1]
        def git(repo, *args):
            if repo == source:
                return self.revision if args == ('rev-parse', 'HEAD') else ''
            return original_git(repo, *args)
        argv = ['delivery.py', '--built-root', str(self.output), '--clone-root', str(self.root / 'clones'),
                '--source-revision', self.revision, '--gitleaks', '/scanner', '--push']
        counts = {'original': 0, 'classified': 0, 'projection': 0, 'unresolved': 0}
        with patch('sys.argv', argv), patch.object(delivery, 'git', side_effect=git), \
             patch.object(delivery, 'scan', side_effect=[counts, ScanError('scanner failed')]), \
             patch.dict(os.environ, {'TR_KIT_ALLOW_PUSH': '1',
                 'TR_KIT_CODEX_REPOSITORY_URL': str(origin), 'TR_KIT_CLAUDE_REPOSITORY_URL': str(origin)}):
            with self.assertRaises(ScanError):
                delivery.main()
        self.assertEqual(before, self.run_git('--git-dir', origin, 'rev-parse', 'main'))

    def test_scanner_timeout_is_distinct_from_findings(self):
        with patch('delivery_scan.subprocess.run', side_effect=subprocess.TimeoutExpired('scanner', 35)):
            with self.assertRaises(ScanError):
                _native({'release.json': b'{}'}, '/scanner')


@unittest.skipUnless(os.environ.get('TR_KIT_TEST_GITLEAKS'), 'real pinned scanner opt-in')
class RealScannerTests(IntegrityTests):
    def test_generated_products_classify_only_verified_checksums(self):
        for product in ('codex', 'claude'):
            package = self.output / product
            (package / 'api_key').write_text('a real payload whose digest is not a credential')
            self.refresh_release(package)
            result = scan(package, product, self.revision, os.environ['TR_KIT_TEST_GITLEAKS'])
            self.assertGreater(result['classified'], 0)
            self.assertEqual(0, result['unresolved'])
            self.assertEqual(result['original'], result['classified'])

    def test_extra_field_and_key_secret_block(self):
        package = self.output / 'codex'
        # Generated at runtime to avoid committing a literal credential fixture.
        token = 'abc' + hashlib.sha256(b'credential fixture').hexdigest()[:30]
        release = package / 'release.json'
        report = json.loads(release.read_bytes())
        report['api_key'] = token
        self.rewrite(release, report)
        with self.assertRaises(FindingsError):
            scan(package, 'codex', self.revision, os.environ['TR_KIT_TEST_GITLEAKS'])
        del report['api_key']
        self.rewrite(release, report)
        target = package / ('api_key=' + token)
        target.write_text('payload')
        self.refresh_release(package)
        with self.assertRaises(FindingsError):
            scan(package, 'codex', self.revision, os.environ['TR_KIT_TEST_GITLEAKS'])

    def test_copied_checksum_other_field_and_payload_block(self):
        package = self.output / 'codex'
        release = package / 'release.json'
        report = json.loads(release.read_bytes())
        report['api_key'] = next(iter(report['files'].values()))
        self.rewrite(release, report)
        with self.assertRaises(FindingsError):
            scan(package, 'codex', self.revision, os.environ['TR_KIT_TEST_GITLEAKS'])
        del report['api_key']
        self.rewrite(release, report)
        (package / 'copied.txt').write_text('    "api_key": "' + next(iter(report['files'].values())) + '"\n')
        self.refresh_release(package)
        with self.assertRaises(FindingsError):
            scan(package, 'codex', self.revision, os.environ['TR_KIT_TEST_GITLEAKS'])

    def test_stronger_rule_is_never_classified(self):
        token = 'gh' + 'p_' + hashlib.sha256(b'strong credential fixture').hexdigest()[:36]
        findings = _native({'ordinary': ('token=' + token).encode()}, os.environ['TR_KIT_TEST_GITLEAKS'])
        self.assertTrue(any(finding['RuleID'] == 'github-pat' for _, finding in findings))


class PreparedStateTests(IntegrityTests):
    def prepared(self):
        origin, _ = test_delivery.DeliveryTests.repository(self)
        state = delivery.prepare(self.output / 'codex', self.root / 'clone', 'codex', self.revision, str(origin))
        return state

    def test_stale_parent_ref_package_and_index_are_rejected(self):
        for variant in ('parent', 'ref', 'package', 'index', 'index_blob', 'remote'):
            with self.subTest(variant=variant):
                self.setUp()
                state = self.prepared()
                if variant == 'parent':
                    self.run_git('-C', state.clone, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                                 'commit', '--allow-empty', '-m', 'chore: intermediate')
                elif variant == 'ref':
                    self.run_git('-C', state.clone, 'checkout', '-b', 'other')
                elif variant == 'package':
                    (state.package / '.tr-kit-generated').write_text('changed')
                elif variant == 'index':
                    self.run_git('-C', state.clone, 'rm', '--cached', 'release.json')
                elif variant == 'index_blob':
                    changed = self.root / 'changed-blob'
                    changed.write_text('unverified staged bytes')
                    oid = self.run_git('-C', state.clone, 'hash-object', '-w', changed)
                    self.run_git('-C', state.clone, 'update-index', '--cacheinfo', '100644', oid, 'release.json')
                else:
                    self.run_git('-C', self.root / 'seed', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                                 'commit', '--allow-empty', '-m', 'chore: concurrent remote')
                    self.run_git('-C', self.root / 'seed', 'push', 'origin', 'main')
                with patch.object(delivery, 'scan') as scanner:
                    with self.assertRaises(ValueError):
                        delivery.audit(state, '/scanner', create_commit=True)
                    scanner.assert_not_called()

    def test_commit_hook_mutation_blocks_publication(self):
        for variant in ('index', 'extra_commit'):
            with self.subTest(variant=variant):
                self.setUp()
                state = self.prepared()
                hook = state.clone / '.git/hooks/post-commit'
                if variant == 'index':
                    hook.write_text('#!/bin/sh\ngit rm --cached release.json >/dev/null\n')
                else:
                    hook.write_text('#!/bin/sh\nrm "$0"\ngit commit --allow-empty -m "chore: intermediate" >/dev/null\n')
                hook.chmod(0o755)
                with patch.object(delivery, 'scan', return_value={}):
                    with self.assertRaises(ValueError):
                        delivery.audit(state, '/scanner', create_commit=True)
                self.assertEqual(state.parent, self.run_git('--git-dir', state.url, 'rev-parse', 'main'))

    def test_commit_message_hook_cannot_add_secret_or_trailer(self):
        state = self.prepared()
        hook = state.clone / '.git/hooks/commit-msg'
        token = hashlib.sha256(b'commit message fixture').hexdigest()[:35]
        hook.write_text('#!/bin/sh\nprintf "\\napi_key=' + token + '\\n" >> "$1"\n')
        hook.chmod(0o755)
        with patch.object(delivery, 'scan', return_value={}):
            with self.assertRaisesRegex(ValueError, 'commit message'):
                delivery.audit(state, '/scanner', create_commit=True)
        self.assertEqual(state.parent, self.run_git('--git-dir', state.url, 'rev-parse', 'main'))

    def test_both_audits_finish_before_first_push_without_late_scanning(self):
        original_root = self.root
        origins = {}
        for product in ('codex', 'claude'):
            self.root = original_root / product
            self.root.mkdir()
            origins[product], _ = test_delivery.DeliveryTests.repository(self)
        self.root = original_root
        original_git = delivery.git
        source = Path(delivery.__file__).resolve().parents[1]
        calls = []
        def scanner(*args, **kwargs):
            calls.append('scan')
            self.assertNotIn('push', calls)
            return {}
        def git(repo, *args):
            if repo == source:
                return self.revision if args == ('rev-parse', 'HEAD') else ''
            if args[0] == 'push':
                self.assertEqual(2, calls.count('scan'))
                calls.append('push')
            return original_git(repo, *args)
        argv = ['delivery.py', '--built-root', str(self.output), '--clone-root', str(self.root / 'clones'),
                '--source-revision', self.revision, '--gitleaks', '/scanner', '--push']
        with patch('sys.argv', argv), patch.object(delivery, 'git', side_effect=git), \
             patch.object(delivery, 'scan', side_effect=scanner), \
             patch.dict(os.environ, {'TR_KIT_ALLOW_PUSH': '1',
                 'TR_KIT_CODEX_REPOSITORY_URL': str(origins['codex']),
                 'TR_KIT_CLAUDE_REPOSITORY_URL': str(origins['claude'])}):
            delivery.main()
        self.assertEqual(['scan', 'scan', 'push', 'push'], calls)


@unittest.skipUnless(os.environ.get('TR_KIT_TEST_GITLEAKS'), 'real pinned scanner opt-in')
class OutgoingScannerTests(IntegrityTests):
    def test_old_unchanged_finding_is_recorded_but_modified_renamed_new_block(self):
        for variant in ('unchanged', 'modified', 'renamed', 'new'):
            with self.subTest(variant=variant):
                self.setUp()
                origin, _ = test_delivery.DeliveryTests.repository(self)
                token = 'api_key=' + hashlib.sha256(b'existing remote fixture').hexdigest()[:35]
                seed = self.root / 'seed'
                (seed / 'legacy.txt').write_text(token)
                self.run_git('-C', seed, 'add', '--', 'legacy.txt')
                self.run_git('-C', seed, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                             'commit', '-m', 'test: existing remote fixture')
                self.run_git('-C', seed, 'push', 'origin', 'main')
                package = self.output / 'codex'
                (package / 'legacy.txt').write_text(token + ('\n' if variant == 'modified' else ''))
                if variant == 'renamed':
                    (package / 'legacy.txt').rename(package / 'renamed.txt')
                elif variant == 'new':
                    (package / 'new.txt').write_text(token)
                self.refresh_release(package)
                state = delivery.prepare(package, self.root / 'clone', 'codex', self.revision, str(origin))
                if variant == 'unchanged':
                    result = delivery.audit(state, os.environ['TR_KIT_TEST_GITLEAKS'])
                    self.assertEqual(0, result.counts['unresolved'])
                    self.assertEqual(1, result.counts['unchanged_original'])
                    self.assertEqual(delivery.tree_blobs(state.clone, state.parent)['legacy.txt'],
                                     dict(state.unchanged)['legacy.txt'])
                else:
                    with self.assertRaises(FindingsError):
                        delivery.audit(state, os.environ['TR_KIT_TEST_GITLEAKS'])
