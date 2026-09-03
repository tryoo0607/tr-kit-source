import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from tools.build import BuildError, build_target, discover_targets


TOOLCHAIN_ROOT = Path(__file__).resolve().parents[1]


class ExternalPackBuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pack = Path(self.tmp.name) / "pack"
        self.pack.mkdir()
        self.write(
            "pack.toml",
            """
            schema_version = 1
            name = "example-private"
            version = "0.5.0"
            toolchain_contract = 2
            """,
        )
        self.write("skills/example/SKILL.md", "hello {{AGENT}}\n")
        self.write(
            "recipes/codex.toml",
            """
            schema_version = 1
            target = "codex"
            glossary = "toolchain:codex"

            [output]
            payload = "."

            [delivery]
            repository = "example/example-pack"
            generated = []
            prepare = []
            checks = []

            [[delivery.sync]]
            source = "."
            destination = "dist/codex/example-plugin"

            [[artifacts]]
            id = "private-skills"
            source = "skills"
            destination = "skills"
            scope = "payload"
            """,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, path: str, content: str) -> None:
        target = self.pack / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(content).lstrip())

    def test_external_pack_uses_toolchain_contract_and_glossary(self):
        self.assertEqual(
            discover_targets(self.pack, toolchain_root=TOOLCHAIN_ROOT), ["codex"]
        )

        build_target(self.pack, "codex", toolchain_root=TOOLCHAIN_ROOT)

        rendered = self.pack / "out/codex/skills/example/SKILL.md"
        self.assertEqual(rendered.read_text(), "hello Codex\n")

    def test_external_pack_composition_uses_public_capability_contract(self):
        self.write(
            "templates/composed/SKILL.md",
            "before\n{{slot:artifact.render}}\nafter\n",
        )
        self.write("adapters/render.md", "render for {{AGENT}}\n")
        with (self.pack / "recipes/codex.toml").open("a") as recipe:
            recipe.write(
                textwrap.dedent(
                    """

                    [[compositions]]
                    id = "composed-skill"
                    kind = "skill"
                    source = "templates/composed/SKILL.md"
                    destination = "skills/composed/SKILL.md"
                    scope = "payload"
                    slots = { "artifact.render" = "adapters/render.md" }
                    """
                )
            )

        build_target(self.pack, "codex", toolchain_root=TOOLCHAIN_ROOT)

        rendered = self.pack / "out/codex/skills/composed/SKILL.md"
        self.assertEqual(rendered.read_text(), "before\nrender for Codex\nafter\n")

    def test_external_pack_can_import_named_toolchain_export(self):
        with (self.pack / "recipes/codex.toml").open("a") as recipe:
            recipe.write(
                textwrap.dedent(
                    """

                    [[imports]]
                    id = "runtime-profile"
                    export = "runtime-profile-v1"
                    destination = "_vendor/tr-kit/profile"
                    scope = "payload"
                    """
                )
            )

        build_target(self.pack, "codex", toolchain_root=TOOLCHAIN_ROOT)

        self.assertTrue(
            (self.pack / "out/codex/_vendor/tr-kit/profile/resolver.py").is_file()
        )

    def test_external_pack_cannot_import_unknown_toolchain_export(self):
        with (self.pack / "recipes/codex.toml").open("a") as recipe:
            recipe.write(
                textwrap.dedent(
                    """

                    [[imports]]
                    id = "unknown"
                    export = "private-internal"
                    destination = "vendor"
                    scope = "payload"
                    """
                )
            )

        with self.assertRaisesRegex(BuildError, "unknown toolchain export"):
            build_target(self.pack, "codex", toolchain_root=TOOLCHAIN_ROOT)

    def test_toolchain_import_cannot_overwrite_pack_artifact(self):
        self.write("collision.py", "pack owned\n")
        with (self.pack / "recipes/codex.toml").open("a") as recipe:
            recipe.write(
                textwrap.dedent(
                    """

                    [[imports]]
                    id = "runtime-profile"
                    export = "runtime-profile-v1"
                    destination = "_vendor/tr-kit/profile"
                    scope = "payload"

                    [[artifacts]]
                    id = "collision"
                    source = "collision.py"
                    destination = "_vendor/tr-kit/profile/resolver.py"
                    scope = "payload"
                    """
                )
            )

        with self.assertRaisesRegex(BuildError, "output collision"):
            build_target(self.pack, "codex", toolchain_root=TOOLCHAIN_ROOT)

    def test_external_pack_rejects_nested_source_symlink(self):
        outside = Path(self.tmp.name) / "outside.txt"
        outside.write_text("outside\n")
        (self.pack / "skills" / "leak.txt").symlink_to(outside)

        with self.assertRaisesRegex(BuildError, "must not contain symlinks"):
            build_target(self.pack, "codex", toolchain_root=TOOLCHAIN_ROOT)

    def test_external_pack_can_declare_pack_local_capability(self):
        self.write(
            "core/contracts/capabilities.toml",
            """
            schema_version = 1

            [capabilities."sample.integration"]
            required = true
            format = "markdown-fragment"
            """,
        )
        self.write(
            "templates/sample/SKILL.md",
            "sample\n{{slot:sample.integration}}\n",
        )
        self.write("adapters/sample.md", "Codex sample adapter\n")
        with (self.pack / "recipes/codex.toml").open("a") as recipe:
            recipe.write(
                textwrap.dedent(
                    """

                    [[compositions]]
                    id = "sample-skill"
                    kind = "skill"
                    source = "templates/sample/SKILL.md"
                    destination = "skills/sample/SKILL.md"
                    scope = "payload"
                    slots = { "sample.integration" = "adapters/sample.md" }
                    """
                )
            )

        build_target(self.pack, "codex", toolchain_root=TOOLCHAIN_ROOT)

        rendered = self.pack / "out/codex/skills/sample/SKILL.md"
        self.assertEqual(rendered.read_text(), "sample\nCodex sample adapter\n")

    def test_external_pack_cannot_override_public_capability(self):
        self.write(
            "core/contracts/capabilities.toml",
            """
            schema_version = 1

            [capabilities."artifact.render"]
            required = true
            format = "markdown-fragment"
            """,
        )
        self.write(
            "templates/composed/SKILL.md",
            "{{slot:artifact.render}}\n",
        )
        self.write("adapters/render.md", "override\n")
        with (self.pack / "recipes/codex.toml").open("a") as recipe:
            recipe.write(
                textwrap.dedent(
                    """

                    [[compositions]]
                    id = "override"
                    kind = "skill"
                    source = "templates/composed/SKILL.md"
                    destination = "skills/composed/SKILL.md"
                    scope = "payload"
                    slots = { "artifact.render" = "adapters/render.md" }
                    """
                )
            )

        with self.assertRaisesRegex(BuildError, "cannot override"):
            build_target(self.pack, "codex", toolchain_root=TOOLCHAIN_ROOT)

    def test_external_pack_requires_manifest(self):
        (self.pack / "pack.toml").unlink()

        with self.assertRaisesRegex(BuildError, "pack.toml"):
            discover_targets(self.pack, toolchain_root=TOOLCHAIN_ROOT)

    def test_external_pack_rejects_unsupported_toolchain_contract(self):
        manifest = (self.pack / "pack.toml").read_text()
        (self.pack / "pack.toml").write_text(
            manifest.replace("toolchain_contract = 2", "toolchain_contract = 999")
        )

        with self.assertRaisesRegex(BuildError, "toolchain contract"):
            discover_targets(self.pack, toolchain_root=TOOLCHAIN_ROOT)

    def test_external_pack_source_cannot_escape_pack_root(self):
        recipe = (self.pack / "recipes/codex.toml").read_text()
        (self.pack / "recipes/codex.toml").write_text(
            recipe.replace('source = "skills"', 'source = "../outside"')
        )

        with self.assertRaisesRegex(BuildError, "stay inside"):
            build_target(self.pack, "codex", toolchain_root=TOOLCHAIN_ROOT)

    def test_external_pack_must_use_matching_toolchain_glossary(self):
        recipe = (self.pack / "recipes/codex.toml").read_text()
        (self.pack / "recipes/codex.toml").write_text(
            recipe.replace("toolchain:codex", "toolchain:claude")
        )

        with self.assertRaisesRegex(BuildError, "matching toolchain glossary"):
            build_target(self.pack, "codex", toolchain_root=TOOLCHAIN_ROOT)

    def test_external_pack_source_symlink_cannot_escape_pack_root(self):
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        (outside / "SKILL.md").write_text("outside\n")
        for child in (self.pack / "skills/example").iterdir():
            child.unlink()
        (self.pack / "skills/example").rmdir()
        (self.pack / "skills").rmdir()
        (self.pack / "skills").symlink_to(outside, target_is_directory=True)

        with self.assertRaisesRegex(BuildError, "stay inside"):
            build_target(self.pack, "codex", toolchain_root=TOOLCHAIN_ROOT)

    def test_external_pack_target_recipe_symlink_cannot_escape_pack_root(self):
        outside = Path(self.tmp.name) / "outside-recipe.toml"
        outside.write_text((self.pack / "recipes/codex.toml").read_text())
        (self.pack / "recipes/codex.toml").unlink()
        (self.pack / "recipes/codex.toml").symlink_to(outside)

        with self.assertRaisesRegex(BuildError, "stay inside"):
            build_target(self.pack, "codex", toolchain_root=TOOLCHAIN_ROOT)

    def test_external_pack_base_recipe_symlink_cannot_escape_pack_root(self):
        outside = Path(self.tmp.name) / "outside-base.toml"
        outside.write_text("schema_version = 1\n")
        (self.pack / "recipes/_base.toml").symlink_to(outside)
        recipe = (self.pack / "recipes/codex.toml").read_text()
        (self.pack / "recipes/codex.toml").write_text(
            recipe.replace("schema_version = 1", 'schema_version = 1\nextends = "_base.toml"', 1)
        )

        with self.assertRaisesRegex(BuildError, "stay inside"):
            build_target(self.pack, "codex", toolchain_root=TOOLCHAIN_ROOT)

    def test_external_pack_output_symlink_cannot_escape_pack_root(self):
        outside = Path(self.tmp.name) / "outside-output"
        outside.mkdir()
        (self.pack / "out").symlink_to(outside, target_is_directory=True)

        with self.assertRaisesRegex(BuildError, "target output"):
            build_target(self.pack, "codex", toolchain_root=TOOLCHAIN_ROOT)

    def test_external_pack_builds_through_public_cli(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.build",
                "--pack-root",
                str(self.pack),
                "codex",
            ],
            cwd=TOOLCHAIN_ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("done ->", result.stdout)
        self.assertEqual(
            (self.pack / "out/codex/skills/example/SKILL.md").read_text(),
            "hello Codex\n",
        )

    def test_external_pack_cli_rejects_output_symlink(self):
        outside = Path(self.tmp.name) / "outside-output"
        outside.mkdir()
        (self.pack / "out").symlink_to(outside, target_is_directory=True)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.build",
                "--pack-root",
                str(self.pack),
                "codex",
            ],
            cwd=TOOLCHAIN_ROOT,
            text=True,
            capture_output=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("target output", result.stderr)
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
