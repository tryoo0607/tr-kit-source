import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from package import package
import delivery


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        base = self.source / 'common/base'
        (base / 'skills/example').mkdir(parents=True)
        (base / 'instructions.md').write_text('Rules\n')
        (base / 'skills/example/SKILL.md').write_text('---\nname: example\ndescription: Example\n---\nRun\n')
        (base / 'skills/example/.gitignore').write_text('ignored.txt\n')
        (base / 'skills/example/ignored.txt').write_text('Required upstream asset\n')
        (self.source / 'VERSION').write_text('0.6.0\n')
        for product, filename in [('codex', 'AGENTS'), ('claude', 'CLAUDE')]:
            adapter = self.source / 'adapters' / product
            adapter.mkdir(parents=True)
            (adapter / f'{filename}.md.template').write_text('{{COMMON_INSTRUCTIONS}}\n')
        self.revision = 'a' * 40
        self.output = self.root / 'built'
        for product in ('codex', 'claude'):
            package(self.source, self.output / product, product, source_revision=self.revision)

    def run_git(self, *args):
        return subprocess.check_output(['git', *map(str, args)], text=True, stderr=subprocess.DEVNULL).strip()

    def repository(self):
        origin = self.root / 'remote.git'
        self.run_git('init', '--bare', '--initial-branch=main', origin)
        seed = self.root / 'seed'
        self.run_git('clone', origin, seed)
        (seed / 'old-hook').write_text('legacy\n')
        self.run_git('-C', seed, 'add', '.')
        self.run_git('-C', seed, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                     'commit', '-m', 'chore: seed')
        self.run_git('-C', seed, 'push', 'origin', 'main')
        return origin, self.run_git('--git-dir', origin, 'rev-parse', 'main')

    def test_both_real_marketplaces_are_stable_and_verified(self):
        for product in ('codex', 'claude'):
            first = self.output / product
            delivery.verify(first, product, self.revision)
            second = self.root / f'again-{product}'
            package(self.source, second, product, source_revision=self.revision)
            self.assertEqual((first / 'release.json').read_bytes(), (second / 'release.json').read_bytes())
            report = json.loads((first / 'release.json').read_text())
            self.assertEqual(f'0.6.0+{product}.{self.revision[:12]}', report['version'])

    def test_tamper_extra_file_and_wrong_revision_are_rejected(self):
        first = self.output / 'codex'
        with self.assertRaisesRegex(ValueError, 'provenance'):
            delivery.verify(first, 'codex', 'b' * 40)
        (first / 'extra').write_text('unexpected')
        with self.assertRaisesRegex(ValueError, 'integrity'):
            delivery.verify(first, 'codex', self.revision)

    def test_dry_run_preserves_remote_and_push_keeps_history_then_noop(self):
        origin, before = self.repository()
        clone = self.root / 'delivery'
        delivery.prepare(self.output / 'codex', clone, 'codex', self.revision, str(origin))
        self.assertFalse((clone / 'old-hook').exists())
        self.assertIn('plugins/tr-codex/skills/example/ignored.txt',
                      self.run_git('-C', clone, 'ls-files').splitlines())
        self.assertEqual(before, self.run_git('--git-dir', origin, 'rev-parse', 'main'))
        with patch.dict(os.environ, {'TR_KIT_ALLOW_PUSH': '0'}):
            with self.assertRaisesRegex(ValueError, 'requires'):
                delivery.publish(clone, self.revision)
        with patch.dict(os.environ, {'TR_KIT_ALLOW_PUSH': '1'}):
            self.assertEqual('pushed', delivery.publish(clone, self.revision))
            self.assertEqual(before, self.run_git('--git-dir', origin, 'rev-parse', 'main^'))
            again = self.root / 'again'
            self.assertEqual('', delivery.prepare(self.output / 'codex', again, 'codex', self.revision, str(origin)))
            self.assertEqual('no-op', delivery.publish(again, self.revision))
        with self.assertRaisesRegex(ValueError, 'already exist'):
            delivery.prepare(self.output / 'codex', clone, 'codex', self.revision, str(origin))


if __name__ == '__main__':
    unittest.main()
