"""Real CLI checks for the bounded snapshot comparator, never live infrastructure."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = (Path(__file__).resolve().parents[1] /
          'common/base/skills/homelab-audit/scripts/compare-snapshots.py')


@unittest.skipUnless(shutil.which('git'), 'Git is required for snapshot comparison')
class SnapshotChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.expected = self.root / 'expected.conf'
        self.observed = self.root / 'observed.conf'
        self.expected.write_text('synthetic-private-content=one\n')
        self.observed.write_bytes(self.expected.read_bytes())

    def invoke(self, expected_code, status, environment=None):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(self.expected), str(self.observed)],
            capture_output=True, text=True, env=environment)
        self.assertEqual(result.returncode, expected_code, result.stderr)
        body = json.loads(result.stdout)
        self.assertEqual(body['status'], status)
        self.assertFalse(body['live_verified'])
        self.assertNotIn('synthetic-private-content', result.stdout + result.stderr)
        self.assertNotIn(str(self.root), result.stdout + result.stderr)
        return body

    def test_identical_snapshots_unchanged(self):
        original = (self.expected.read_bytes(), self.observed.read_bytes())
        self.invoke(0, 'match')
        self.assertEqual(original, (self.expected.read_bytes(), self.observed.read_bytes()))

    def test_different_snapshots_unchanged_without_raw_diff(self):
        self.observed.write_text('synthetic-private-content=two\n')
        original = (self.expected.read_bytes(), self.observed.read_bytes())
        self.invoke(1, 'drift')
        self.assertEqual(original, (self.expected.read_bytes(), self.observed.read_bytes()))

    def test_missing_observation_is_unknown(self):
        self.observed.unlink()
        self.invoke(2, 'unknown')

    def test_directory_is_unknown(self):
        self.observed.unlink()
        self.observed.mkdir()
        self.invoke(2, 'unknown')

    def test_symlink_is_unknown(self):
        self.observed.unlink()
        self.observed.symlink_to(self.expected)
        self.invoke(2, 'unknown')

    def test_hardlink_does_not_prove_independent_observation(self):
        self.observed.unlink()
        self.observed.hardlink_to(self.expected)
        self.assertEqual(self.invoke(2, 'unknown')['reason'], 'same_input')

    def test_missing_git_is_unknown(self):
        environment = os.environ.copy()
        environment['PATH'] = str(self.root / 'missing-bin')
        self.invoke(2, 'unknown', environment)

    def test_external_diff_is_not_executed(self):
        marker = self.root / 'external-diff-ran'
        executable = self.root / 'external-diff'
        executable.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n')
        executable.chmod(0o700)
        environment = os.environ.copy()
        environment['GIT_EXTERNAL_DIFF'] = str(executable)
        self.observed.write_text('different\n')
        self.invoke(1, 'drift', environment)
        self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
