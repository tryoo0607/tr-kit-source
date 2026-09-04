import tempfile
import unittest
from pathlib import Path

from tools.validate import ValidationError, is_toolchain_root, validate_skill


ROOT = Path(__file__).resolve().parents[1]


class SourceValidationTest(unittest.TestCase):
    def test_recognizes_toolchain_by_owned_contract_markers(self):
        self.assertTrue(is_toolchain_root(ROOT))
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(is_toolchain_root(Path(tmp)))

    def test_skill_name_must_match_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "actual" / "SKILL.md"
            skill.parent.mkdir()
            skill.write_text("---\nname: wrong\ndescription: demo\n---\n")

            with self.assertRaisesRegex(ValidationError, "name must match"):
                validate_skill(skill)

    def test_referenced_skill_file_must_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "demo" / "SKILL.md"
            skill.parent.mkdir()
            skill.write_text(
                "---\nname: demo\ndescription: demo\n---\n"
                "Read `references/missing.md`.\n"
            )

            with self.assertRaisesRegex(ValidationError, "missing reference"):
                validate_skill(skill)


if __name__ == "__main__":
    unittest.main()
