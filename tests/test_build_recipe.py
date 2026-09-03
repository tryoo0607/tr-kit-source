import tempfile
import textwrap
import unittest
from pathlib import Path

from tools.build import BuildError, build_target, discover_targets, select_targets


class RecipeBuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "recipes").mkdir()
        (self.root / "recipes" / "_schema.toml").write_text(
            textwrap.dedent(
                """
                schema_version = 1
                recipe_keys = ["schema_version", "target", "extends", "glossary", "output", "imports", "artifacts", "compositions", "generators", "delivery"]
                output_keys = ["payload"]
                import_keys = ["id", "export", "destination", "scope"]
                import_scopes = ["payload", "target"]
                artifact_keys = ["id", "source", "destination", "scope"]
                artifact_scopes = ["payload", "target"]
                composition_keys = ["id", "kind", "source", "destination", "scope", "slots"]
                composition_kinds = ["skill"]
                composition_scopes = ["payload", "target"]
                generator_keys = ["id", "kind", "destination", "scope"]
                generator_kinds = ["skill-readme"]
                generator_scopes = ["payload", "target"]
                delivery_keys = ["repository", "generated", "prepare", "checks", "sync"]
                delivery_sync_keys = ["source", "destination"]
                """
            ).lstrip()
        )
        (self.root / "glossary").mkdir()
        (self.root / "glossary" / "_schema.toml").write_text(
            '[tokens.NAME]\ndesc = "name"\n'
        )
        (self.root / "glossary" / "demo.toml").write_text('NAME = "demo"\n')

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, path: str, content: str) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(content).lstrip())

    def recipe(self, artifacts: str) -> None:
        self.write(
            "recipes/demo.toml",
            f"""
            schema_version = 1
            target = "demo"
            glossary = "glossary/demo.toml"

            [output]
            payload = "."

            [delivery]
            repository = "example/demo"
            generated = []
            prepare = []
            checks = []

            [[delivery.sync]]
            source = "."
            destination = "plugins/demo"

            {artifacts}
            """,
        )

    def test_builds_declared_tree_and_substitutes_tokens(self):
        self.write("source/SKILL.md", "hello {{NAME}}\n")
        self.recipe(
            """
            [[artifacts]]
            id = "source"
            source = "source"
            destination = "skills"
            scope = "payload"
            """
        )

        build_target(self.root, "demo")

        self.assertEqual(
            (self.root / "out/demo/skills/SKILL.md").read_text(), "hello demo\n"
        )

    def test_ignores_python_bytecode_caches_in_source_trees(self):
        self.write("source/file.md", "content\n")
        self.write("source/__pycache__/module.cpython-312.pyc", "transient\n")
        self.write("source/module.pyc", "transient\n")
        self.recipe(
            """
            [[artifacts]]
            id = "source"
            source = "source"
            destination = "."
            scope = "payload"
            """
        )

        build_target(self.root, "demo")

        self.assertTrue((self.root / "out/demo/file.md").is_file())
        self.assertFalse((self.root / "out/demo/__pycache__").exists())
        self.assertFalse((self.root / "out/demo/module.pyc").exists())

    def test_rejects_two_artifacts_with_same_output_path(self):
        self.write("one/file.md", "one\n")
        self.write("two/file.md", "two\n")
        self.recipe(
            """
            [[artifacts]]
            id = "one"
            source = "one"
            destination = "."
            scope = "payload"

            [[artifacts]]
            id = "two"
            source = "two"
            destination = "."
            scope = "payload"
            """
        )

        with self.assertRaisesRegex(BuildError, "output collision"):
            build_target(self.root, "demo")

    def test_internal_recipe_cannot_request_toolchain_import(self):
        self.recipe(
            """
            [[imports]]
            id = "runtime"
            export = "runtime-profile-v1"
            destination = "vendor/profile"
            scope = "payload"
            """
        )

        with self.assertRaisesRegex(BuildError, "only valid for external packs"):
            build_target(self.root, "demo")

    def test_rejects_missing_declared_source(self):
        self.recipe(
            """
            [[artifacts]]
            id = "missing"
            source = "does-not-exist"
            destination = "."
            scope = "payload"
            """
        )

        with self.assertRaisesRegex(BuildError, "source does not exist"):
            build_target(self.root, "demo")

    def test_rejects_unresolved_token(self):
        self.write("source/file.md", "{{UNKNOWN}}\n")
        self.recipe(
            """
            [[artifacts]]
            id = "source"
            source = "source"
            destination = "."
            scope = "payload"
            """
        )

        with self.assertRaisesRegex(BuildError, "unresolved token"):
            build_target(self.root, "demo")

    def test_rejects_unresolved_destination_token(self):
        self.write("source/file.md", "content\n")
        self.recipe(
            """
            [[artifacts]]
            id = "source"
            source = "source"
            destination = "{{UNKNOWN}}"
            scope = "payload"
            """
        )

        with self.assertRaisesRegex(BuildError, "unresolved token"):
            build_target(self.root, "demo")

    def test_rejects_legacy_recipe_that_build_would_ignore(self):
        self.write("recipes/demo.toml", 'schema_version = 1\ntarget = "demo"\n')
        self.write("recipes/dead.yaml", "overrides: {{}}\n")

        with self.assertRaisesRegex(BuildError, "unsupported recipe"):
            discover_targets(self.root)

        with self.assertRaisesRegex(BuildError, "unsupported recipe"):
            select_targets(self.root, ["demo"])

    def test_composes_skill_with_named_capability_slot(self):
        self.write(
            "core/skills/diagram/SKILL.md",
            "before\n{{slot:artifact.render}}\nafter\n",
        )
        self.write(
            "core/contracts/capabilities.toml",
            """
            schema_version = 1

            [capabilities."artifact.render"]
            required = true
            format = "markdown-fragment"
            """,
        )
        self.write("adapters/demo/capabilities/artifact-render.md", "render demo\n")
        self.recipe(
            """
            [[compositions]]
            id = "diagram"
            kind = "skill"
            source = "core/skills/diagram/SKILL.md"
            destination = "skills/diagram/SKILL.md"
            scope = "payload"
            slots = { "artifact.render" = "adapters/demo/capabilities/artifact-render.md" }
            """
        )

        build_target(self.root, "demo")

        self.assertEqual(
            (self.root / "out/demo/skills/diagram/SKILL.md").read_text(),
            "before\nrender demo\nafter\n",
        )

    def test_rejects_missing_required_slot_mapping(self):
        self.write("core/skills/diagram/SKILL.md", "{{slot:artifact.render}}\n")
        self.write(
            "core/contracts/capabilities.toml",
            """
            schema_version = 1
            [capabilities."artifact.render"]
            required = true
            format = "markdown-fragment"
            """,
        )
        self.recipe(
            """
            [[compositions]]
            id = "diagram"
            kind = "skill"
            source = "core/skills/diagram/SKILL.md"
            destination = "skills/diagram/SKILL.md"
            scope = "payload"
            slots = {}
            """
        )

        with self.assertRaisesRegex(BuildError, "missing required slot"):
            build_target(self.root, "demo")

    def test_rejects_slot_not_declared_by_core_contract(self):
        self.write("core/skills/diagram/SKILL.md", "{{slot:artifact.render}}\n")
        self.write(
            "core/contracts/capabilities.toml",
            """
            schema_version = 1
            [capabilities."artifact.render"]
            required = true
            format = "markdown-fragment"
            """,
        )
        self.write("adapters/demo/capabilities/unknown.md", "unknown\n")
        self.recipe(
            """
            [[compositions]]
            id = "diagram"
            kind = "skill"
            source = "core/skills/diagram/SKILL.md"
            destination = "skills/diagram/SKILL.md"
            scope = "payload"
            slots = { "artifact.unknown" = "adapters/demo/capabilities/unknown.md" }
            """
        )

        with self.assertRaisesRegex(BuildError, "undeclared capability slot"):
            build_target(self.root, "demo")

    def test_rejects_complete_skill_as_slot_fragment(self):
        self.write("core/skills/diagram/SKILL.md", "{{slot:artifact.render}}\n")
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
            "adapters/demo/capabilities/artifact-render.md",
            "\ufeff---\nname: copied-skill\n---\n",
        )
        self.recipe(
            """
            [[compositions]]
            id = "diagram"
            kind = "skill"
            source = "core/skills/diagram/SKILL.md"
            destination = "skills/diagram/SKILL.md"
            scope = "payload"
            slots = { "artifact.render" = "adapters/demo/capabilities/artifact-render.md" }
            """
        )

        with self.assertRaisesRegex(BuildError, "must be a markdown fragment"):
            build_target(self.root, "demo")


if __name__ == "__main__":
    unittest.main()
