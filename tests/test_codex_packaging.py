import ast
import json
import subprocess
import unittest
from pathlib import Path

from tools.build import _load_recipe, build_target


ROOT = Path(__file__).resolve().parents[1]


class CodexPackagingTest(unittest.TestCase):
    def test_core_adapter_release_versions_and_claude_metadata(self):
        claude = json.loads(
            (ROOT / "adapters/claude/.claude-plugin/plugin.json").read_text()
        )
        codex = json.loads(
            (ROOT / "adapters/codex/.codex-plugin/plugin.json").read_text()
        )

        self.assertEqual(claude["version"], "0.5.5")
        self.assertEqual(codex["version"], "0.5.5")
        self.assertEqual(claude["author"]["name"], "tryoo0607")
        self.assertNotIn("개인", claude["description"] + codex["description"])
        self.assertEqual(claude["license"], "Apache-2.0")
        self.assertEqual(codex["license"], "Apache-2.0")
        self.assertTrue(
            (ROOT / "LICENSE").read_text().lstrip().startswith("Apache License\n")
        )

    def test_plugin_manifest_matches_codex_plugin_contract(self):
        manifest = json.loads(
            (ROOT / "adapters/codex/.codex-plugin/plugin.json").read_text()
        )

        self.assertNotIn("hooks", manifest)
        self.assertEqual(manifest["author"]["name"], "tryoo0607")
        self.assertEqual(manifest["license"], "Apache-2.0")

        interface = manifest["interface"]
        required = {
            "displayName",
            "shortDescription",
            "longDescription",
            "developerName",
            "category",
            "capabilities",
            "defaultPrompt",
        }
        self.assertTrue(required <= set(interface))
        self.assertTrue(all(isinstance(interface[key], str) for key in required - {"capabilities", "defaultPrompt"}))
        self.assertTrue(interface["capabilities"])
        self.assertTrue(all(isinstance(value, str) for value in interface["capabilities"]))
        self.assertTrue(interface["defaultPrompt"])
        self.assertTrue(all(isinstance(value, str) for value in interface["defaultPrompt"]))

        self.assertTrue((ROOT / "adapters/codex/hooks/hooks.json").is_file())

    def test_build_outputs_are_complete_generated_repository_trees(self):
        for target, marketplace in (
            ("claude", ".claude-plugin/marketplace.json"),
            ("codex", ".agents/plugins/marketplace.json"),
        ):
            build_target(ROOT, target)
            root = ROOT / "out" / target
            self.assertTrue((root / ".tr-kit-generated").is_file())
            self.assertTrue((root / marketplace).is_file())
            self.assertTrue((root / "LICENSE").is_file())
            self.assertTrue((root / "NOTICE").is_file())
            self.assertEqual(
                (root / "NOTICE").read_bytes(),
                (ROOT / "NOTICE").read_bytes(),
            )
            self.assertTrue((root / "README.md").is_file())
            self.assertTrue((root / f"plugins/tr-{target}/README.md").is_file())
            self.assertFalse((root / "setup").exists())
            self.assertFalse((root / "plugins/tr-web").exists())

    def test_every_declared_source_survives_a_clean_git_export(self):
        for target in ("claude", "codex"):
            recipe = _load_recipe(ROOT, target, ROOT)
            for entry in [*recipe["artifacts"], *recipe["compositions"]]:
                source = entry["source"]
                tracked = subprocess.check_output(
                    ["git", "-C", str(ROOT), "ls-files", "--", source],
                    text=True,
                ).splitlines()
                self.assertTrue(tracked, f"{target}:{source}")

    def test_project_skill_description_is_yaml_safe_quoted_text(self):
        skill = (ROOT / "skills/project/SKILL.md").read_text()
        description_line = next(
            line for line in skill.splitlines() if line.startswith("description: ")
        )
        value = description_line.removeprefix("description: ")

        self.assertIn(value[:1], {"'", '"'})
        self.assertIsInstance(ast.literal_eval(value), str)


if __name__ == "__main__":
    unittest.main()
