import subprocess
import unittest
from pathlib import Path

from tools.build import build_target


ROOT = Path(__file__).resolve().parents[1]


class PublicBoundaryTest(unittest.TestCase):
    def forbidden_tokens(self) -> list[str]:
        return [
            "tr-kit-" + "private",
            "tr-" + "private",
            "no" + "tion",
            "claude-" + "inno",
            "cr-" + "inno",
            "tab" + "cloudit",
            "z" + "440",
            "game" + "01",
            "dev" + "01",
            "to-" + "nas",
            "to-" + "inno",
            "/home/" + "tryoo0607",
        ]

    def source_files(self) -> list[Path]:
        result = subprocess.check_output(
            [
                "git",
                "-C",
                str(ROOT),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            text=True,
        )
        return [ROOT / line for line in result.splitlines() if line]

    def test_private_skills_are_not_public_sources(self):
        private_skills = [
            "homelab",
            "counsel",
            "english",
            "algo",
            "packages",
            "shopping",
            "no" + "tion",
        ]
        for name in private_skills:
            self.assertFalse((ROOT / "skills" / name / "SKILL.md").exists(), name)

    def test_source_has_no_private_pack_or_personal_environment_identifiers(self):
        failures: list[str] = []
        this_file = Path(__file__).resolve()
        for path in self.source_files():
            if path.resolve() == this_file or not path.is_file():
                continue
            try:
                text = path.read_text().lower()
            except UnicodeDecodeError:
                continue
            for token in self.forbidden_tokens():
                if token.lower() in text:
                    failures.append(f"{path.relative_to(ROOT)}:{token}")
        self.assertEqual(failures, [])

    def test_generated_repositories_have_no_private_environment_identifiers(self):
        failures: list[str] = []
        for target in ("claude", "codex"):
            build_target(ROOT, target)
            output = ROOT / "out" / target
            for path in output.rglob("*"):
                if not path.is_file():
                    continue
                try:
                    text = path.read_text().lower()
                except UnicodeDecodeError:
                    continue
                for token in self.forbidden_tokens():
                    if token.lower() in text:
                        failures.append(f"{target}/{path.relative_to(output)}:{token}")
        self.assertEqual(failures, [])

    def test_public_author_handle_is_limited_to_release_metadata(self):
        allowed = {
            Path("README.md"),
            Path(".github/CODEOWNERS"),
            Path("adapters/claude/.claude-plugin/plugin.json"),
            Path("adapters/codex/.codex-plugin/plugin.json"),
            Path("packaging/claude/.claude-plugin/marketplace.json"),
            Path("packaging/claude/README.md"),
            Path("packaging/codex/README.md"),
            Path("recipes/claude.toml"),
            Path("recipes/codex.toml"),
            Path("tests/test_codex_packaging.py"),
        }
        found: set[Path] = set()
        for path in self.source_files():
            if path.resolve() == Path(__file__).resolve():
                continue
            if not path.is_file():
                continue
            try:
                if "tryoo" + "0607" in path.read_text():
                    found.add(path.relative_to(ROOT))
            except UnicodeDecodeError:
                pass
        self.assertEqual(found, allowed)


if __name__ == "__main__":
    unittest.main()
