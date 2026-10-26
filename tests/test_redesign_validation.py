import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('redesign_validation', ROOT / 'scripts/validate.py')
validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validation)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.skill = self.root / 'example'
        self.skill.mkdir()
        self.creator = self.root / 'creator'
        (self.creator / 'scripts').mkdir(parents=True)
        # Models the pinned validator's older metadata contract.
        (self.creator / 'scripts/quick_validate.py').write_text(
            'from pathlib import Path\nimport yaml\n'
            'def validate_skill(folder):\n'
            '    data=yaml.safe_load((Path(folder)/"SKILL.md").read_text().split("---")[1])\n'
            '    return (not set(data)-{"name","description"}, "metadata validation")\n')

    def check(self, extra):
        source = '---\nname: example\ndescription: Useful guidance\n' + extra + '---\nBody\n'
        path = self.skill / 'SKILL.md'
        path.write_text(source)
        result = validation.validate_skill(self.skill, self.creator)
        self.assertEqual(source, path.read_text())
        self.assertFalse(list(self.creator.rglob('*.pyc')))
        return result[0]

    def test_compatibility_is_validated_without_modifying_source(self):
        self.assertTrue(self.check('compatibility: Requires wt\n'))

    def test_unknown_fields_still_reach_the_pinned_validator(self):
        self.assertFalse(self.check('compatibility: Requires wt\nunknown: value\n'))

    def test_invalid_compatibility_is_rejected(self):
        self.assertFalse(self.check('compatibility: [wt]\n'))

    def test_folder_name_must_match(self):
        self.check('')
        path = self.skill / 'SKILL.md'
        path.write_text(path.read_text().replace('name: example', 'name: other'))
        self.assertFalse(validation.validate_skill(self.skill, self.creator)[0])


if __name__ == '__main__':
    unittest.main()
