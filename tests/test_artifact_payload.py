"""Selected upload bytes use the existing scanner; tests never publish."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('artifact_gate',ROOT/'scripts/check-artifact-secrets.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)

class Payload(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.root=self.base/'payload';self.root.mkdir()
        (self.root/'index.html').write_text('<html>safe artifact</html>')

    def check(self,scanner=None):
        with mock.patch.object(gate.secrets,'trusted_scanner',return_value=Path('/not-run')):
            with mock.patch.object(gate.secrets,'scan',side_effect=scanner):return gate.check(self.root)

    def test_actual_names_and_bytes_including_hidden_ignored_are_scanned(self):
        (self.root/'.hidden').write_text('hidden evidence');(self.root/'.gitignore').write_text('.hidden')
        captured=[]
        result=self.check(lambda blobs,tool:captured.extend(blobs))
        self.assertEqual(result['files'],3)
        self.assertIn(('.hidden',b'hidden evidence'),captured)
        self.assertIn('index.html',json.loads(captured[-1][1]))
        self.assertIn('not approval',result['limits'])

    def test_no_target_file_mutation(self):
        before={p.name:p.read_bytes() for p in self.root.iterdir()}
        self.check()
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.root.iterdir()})

    def test_bytes_and_name_changes_change_fingerprint(self):
        first=self.check()['fingerprint'];(self.root/'index.html').write_text('<html>changed</html>')
        second=self.check()['fingerprint'];self.assertNotEqual(first,second)
        (self.root/'index.html').rename(self.root/'renamed.html')
        self.assertNotEqual(second,self.check()['fingerprint'])

    def test_reference_and_root_reference_refused(self):
        (self.root/'link').symlink_to(self.root/'index.html')
        with self.assertRaises(ValueError):self.check()
        (self.root/'link').unlink()
        alias=self.base/'alias';alias.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):gate.snapshot(alias)

    def test_fifo_refused_without_read(self):
        if not hasattr(os,'mkfifo'):self.skipTest('FIFO unsupported')
        os.mkfifo(self.root/'pipe')
        with self.assertRaises(ValueError):self.check()

    def test_opaque_archive_requires_expanded_payload(self):
        (self.root/'archive').write_bytes(b'PK\x03\x04compressed data')
        with self.assertRaises(ValueError):self.check()

    def test_empty_payload_not_certified(self):
        (self.root/'index.html').unlink()
        with self.assertRaises(ValueError):self.check()

    def test_bytes_limit_and_node_limit(self):
        with mock.patch.object(gate,'MAX_BYTES',4):
            with self.assertRaises(ValueError):self.check()
        with mock.patch.object(gate,'MAX_NODES',1):
            with self.assertRaises(ValueError):self.check()

    def test_total_byte_limit_not_only_individual_files(self):
        (self.root/'index.html').write_bytes(b'aaaa');(self.root/'other').write_bytes(b'bbbb')
        with mock.patch.object(gate,'MAX_BYTES',6):
            with self.assertRaises(ValueError):self.check()

    def test_modification_during_scan_not_certified(self):
        with self.assertRaises(ValueError):self.check(lambda *args:(self.root/'index.html').write_text('changed'))

    def test_new_hidden_file_during_scan_not_certified(self):
        with self.assertRaises(ValueError):self.check(lambda *args:(self.root/'.new').write_text('changed'))

    def test_removed_file_during_scan_not_certified(self):
        with self.assertRaises(ValueError):self.check(lambda *args:(self.root/'index.html').unlink())

    def test_missing_scanner_is_not_success(self):
        with mock.patch.object(gate.secrets,'trusted_scanner',side_effect=RuntimeError('unavailable')):
            with self.assertRaises(gate.InspectionUnavailable):gate.check(self.root)

    def test_scanner_failure_is_not_clean(self):
        def fail(*args):raise RuntimeError('fixture private scanner output')
        with self.assertRaises(gate.InspectionUnavailable):self.check(fail)

    def test_real_pinned_scanner_accepts_clean_and_rejects_synthetic_token(self):
        self.assertEqual(gate.check(self.root)['status'],'pass')
        key='ghp_'+hashlib.sha256(b'nonexistent publish credential fixture').hexdigest()[:36]
        (self.root/'index.html').write_text(key)
        with self.assertRaises(gate.secrets.GuardError):gate.check(self.root)

    def test_real_scanner_checks_secret_in_filename(self):
        name='ghp_'+hashlib.sha256(b'nonexistent file name credential').hexdigest()[:36]
        (self.root/name).write_text('safe content')
        with self.assertRaises(gate.secrets.GuardError):gate.check(self.root)

    def test_real_cli_finding_does_not_print_payload_or_paths(self):
        key='ghp_'+hashlib.sha256(b'nonexistent CLI credential fixture').hexdigest()[:36]
        (self.root/'index.html').write_text(key)
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/check-artifact-secrets.py'),'--root',str(self.root)],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,2);self.assertEqual(json.loads(result.stdout)['status'],'finding')
        self.assertNotIn(key,result.stdout+result.stderr);self.assertNotIn('index.html',result.stdout+result.stderr)

    def test_real_cli_unavailable_is_distinct(self):
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/check-artifact-secrets.py'),'--root',str(self.base/'missing')],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,2);self.assertEqual(json.loads(result.stdout)['status'],'unavailable')
        self.assertNotIn(str(self.base/'missing'),result.stdout+result.stderr)

    def test_unavailable_diagnostic_is_safe_stage_and_kind(self):
        error=PermissionError('SYNTHETIC_PRIVATE_PATH')
        with mock.patch.object(gate,'snapshot',side_effect=error):
            with self.assertRaises(gate.InspectionUnavailable) as caught:gate.check(self.root)
        self.assertEqual((caught.exception.stage,caught.exception.kind),('inventory','permission'))
        self.assertNotIn('SYNTHETIC_PRIVATE_PATH',str(caught.exception))

    def test_scanner_permission_has_distinct_stage(self):
        with mock.patch.object(gate.secrets,'trusted_scanner',return_value=Path('/not-run')):
            with mock.patch.object(gate.secrets,'scan',side_effect=PermissionError('SYNTHETIC_PRIVATE_OUTPUT')):
                with self.assertRaises(gate.InspectionUnavailable) as caught:gate.check(self.root)
        self.assertEqual((caught.exception.stage,caught.exception.kind),('scanner','permission'))
