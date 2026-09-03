import shutil
import tempfile
import unittest
from pathlib import Path

from tools.build import build_target


ROOT = Path(__file__).resolve().parents[1]


class FakeTargetExtensionTest(unittest.TestCase):
    def test_third_target_builds_with_recipe_and_adapter_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = Path(tmp) / "source"
            shutil.copytree(
                ROOT,
                sandbox,
                ignore=shutil.ignore_patterns(".git", "out", "__pycache__"),
            )

            glossary = (sandbox / "glossary/codex.toml").read_text()
            glossary = glossary.replace('PRODUCT = "Codex"', 'PRODUCT = "Fake Host"')
            glossary = glossary.replace('AGENT = "Codex"', 'AGENT = "Fake Agent"')
            glossary = glossary.replace('KIT_REPO = "tr-codex"', 'KIT_REPO = "tr-fake"')
            (sandbox / "glossary/fake.toml").write_text(glossary)

            adapter = sandbox / "adapters/fake/capabilities"
            shutil.copytree(sandbox / "adapters/codex/capabilities", adapter)
            for fragment in adapter.glob("*.md"):
                fragment.write_text(fragment.read_text() + "\nFAKE_TARGET_ADAPTER\n")

            recipe = (sandbox / "recipes/codex.toml").read_text()
            recipe = recipe.replace('target = "codex"', 'target = "fake"')
            recipe = recipe.replace('glossary/codex.toml', 'glossary/fake.toml')
            recipe = recipe.replace('payload = "plugins/{{KIT_REPO}}"', 'payload = "."')
            recipe = recipe.replace("adapters/codex", "adapters/fake")
            recipe = recipe.split('[[artifacts]]\nid = "codex-hooks"', 1)[0] + "\n" + "\n".join(
                section
                for section in recipe.split("\n\n")
                if section.startswith("[[compositions]]")
            )
            (sandbox / "recipes/fake.toml").write_text(recipe)

            build_target(sandbox, "fake")

            for skill in ("diagram", "analysis", "prototype", "session", "kit"):
                rendered = sandbox / f"out/fake/skills/{skill}/SKILL.md"
                self.assertTrue(rendered.is_file(), skill)
                self.assertIn("FAKE_TARGET_ADAPTER", rendered.read_text())


if __name__ == "__main__":
    unittest.main()
