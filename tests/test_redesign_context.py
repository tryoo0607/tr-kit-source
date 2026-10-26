import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('context_check', ROOT / 'common/base/skills/skill-authoring/scripts/context_check.py')
context = importlib.util.module_from_spec(spec)
spec.loader.exec_module(context)


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'skills/demo').mkdir(parents=True)
        (self.root / 'skills/demo/SKILL.md').write_text('---\nname: demo\ndescription: Demo\n---\nBody\n')
        (self.root / 'guide.md').write_text('# Guide\n## Pick\nsmall\n```md\n## Not a heading\n```\n## Other\nlarge\n')

    def test_section_boundary_ignores_code_examples(self):
        text = context.read_text(self.root, {'path': 'guide.md', 'section': 'Pick'})
        self.assertIn('Not a heading', text)
        self.assertNotIn('large', text)

    def test_full_skill_is_required(self):
        with self.assertRaises(ValueError):
            context.read_text(self.root, {'path': 'skills/demo/SKILL.md', 'section': 'Body'})

    def test_missing_and_outside_reads_fail(self):
        for item in [{'path': 'guide.md', 'section': 'Missing'}, {'path': '../outside'}]:
            with self.subTest(item=item), self.assertRaises(ValueError):
                context.read_text(self.root, item)

    def test_added_duplicate_read_fails_comparison(self):
        read = {'path': 'guide.md'}
        report = context.compare(self.root, self.root, [{'name': 'duplicate', 'before': [read], 'after': [read, read]}])
        self.assertFalse(report['passed'])
        self.assertGreater(report['cases'][0]['after']['duplicate_chars'], 0)

    def test_dynamic_exclusion_is_reported_not_counted_as_measured(self):
        read = {'path': 'guide.md'}
        report = context.compare(self.root, self.root, [{'name': 'dynamic', 'before': [read], 'after': [read], 'unmeasured': ['CLI guide']}])
        self.assertTrue(report['passed'])
        self.assertEqual(['CLI guide'], report['cases'][0]['unmeasured'])


if __name__ == '__main__':
    unittest.main()
