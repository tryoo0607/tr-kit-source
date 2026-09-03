import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TARGETS = ("claude", "codex")
SKILLS = {
    "diagram": "artifact.render",
    "analysis": "artifact.html-render",
    "prototype": "artifact.html-render",
    "session": "session.control",
    "kit": "kit.delivery",
}


class CoreSkillCompositionTest(unittest.TestCase):
    def recipe(self, target: str) -> dict:
        return tomllib.loads((ROOT / "recipes" / f"{target}.toml").read_text())

    def test_logical_skills_are_core_owned_not_target_complete_copies(self):
        for skill in SKILLS:
            with self.subTest(skill=skill):
                self.assertTrue((ROOT / "core/skills" / skill / "SKILL.md").is_file())
                for target in TARGETS:
                    self.assertFalse(
                        (ROOT / "adapters" / target / "skills" / skill / "SKILL.md").exists()
                    )

    def test_each_target_composes_every_core_skill_with_declared_capability(self):
        for target in TARGETS:
            recipe = self.recipe(target)
            copied_sources = {
                item["source"] for item in recipe.get("artifacts", [])
            }
            self.assertNotIn(f"adapters/{target}/skills", copied_sources)
            compositions = {
                item["destination"]: item
                for item in recipe.get("compositions", [])
            }
            for skill, capability in SKILLS.items():
                with self.subTest(target=target, skill=skill):
                    item = compositions[f"skills/{skill}/SKILL.md"]
                    self.assertEqual(item["source"], f"core/skills/{skill}/SKILL.md")
                    fragment = ROOT / item["slots"][capability]
                    self.assertTrue(fragment.is_file())
                    self.assertFalse(fragment.read_text().lstrip().startswith("---"))

    def test_shared_references_live_with_the_core_skill(self):
        expected = {
            "analysis": {"skeleton.html", "spec.md", "svg-patterns.md"},
            "prototype": {"frames.md"},
            "session": {"handoff.md"},
            "kit": {"authoring.md", "output-format.md"},
        }
        for skill, names in expected.items():
            actual = {
                path.name
                for path in (ROOT / "core/skills" / skill / "references").glob("*")
                if path.is_file()
            }
            with self.subTest(skill=skill):
                self.assertEqual(actual, names)

    def test_target_capability_fragments_keep_host_mechanisms_separate(self):
        cases = {
            ("claude", "artifact-html-render.md"): "Artifact",
            ("codex", "artifact-html-render.md"): "$visualize",
            ("claude", "session-control.md"): "claude-remote",
            ("codex", "session-control.md"): "독립 세션",
            ("claude", "kit-delivery.md"): "Claude kit",
            ("codex", "kit-delivery.md"): "Codex",
        }
        for (target, name), marker in cases.items():
            with self.subTest(target=target, fragment=name):
                text = (ROOT / "adapters" / target / "capabilities" / name).read_text()
                self.assertIn(marker, text)

    def test_target_specific_deep_guidance_is_copied_as_references(self):
        expected = {
            "skills/session/references/host-control.md": "session-host-control.md",
            "skills/kit/references/delivery.md": "kit-delivery.md",
        }
        for target in TARGETS:
            artifacts = {
                item["destination"]: Path(item["source"]).name
                for item in self.recipe(target).get("artifacts", [])
            }
            for destination, source_name in expected.items():
                with self.subTest(target=target, destination=destination):
                    self.assertEqual(artifacts[destination], source_name)

    def test_core_skill_sources_do_not_name_target_mechanisms(self):
        forbidden = (
            "Claude",
            "Codex",
            "Artifact",
            "$visualize",
            "claude-remote",
            "claude plugin",
            "/clear",
            "fonts.googleapis",
        )
        for skill in SKILLS:
            for path in (ROOT / "core/skills" / skill).rglob("*"):
                if not path.is_file():
                    continue
                text = path.read_text()
                for token in forbidden:
                    with self.subTest(skill=skill, path=path.name, token=token):
                        self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
