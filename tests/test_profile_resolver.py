import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from core.profile.resolver import ProfileError, load_profile, profile_directory


ROOT = Path(__file__).resolve().parents[1]


class RuntimeProfileResolverTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name: str, content: str) -> Path:
        path = self.directory / name
        path.write_text(textwrap.dedent(content).lstrip())
        return path

    def test_merges_public_and_private_extension_keys_in_filename_order(self):
        first = self.write(
            "50-example-plugin.toml",
            """
            schema_version = 1

            [public.repositories]
            knowledge = "/projects/knowledge"

            [extensions.example-plugin.repositories]
            workspace = "/projects/workspace"
            """,
        )
        last = self.write(
            "90-local.toml",
            """
            schema_version = 1

            [extensions.example-plugin.repositories]
            workspace = "/override/workspace"
            """,
        )

        profile = load_profile(self.directory)

        self.assertEqual(profile.get("public.repositories.knowledge"), "/projects/knowledge")
        self.assertEqual(
            profile.get("extensions.example-plugin.repositories.workspace"),
            "/override/workspace",
        )
        self.assertEqual(
            profile.source("extensions.example-plugin.repositories.workspace"), last
        )
        self.assertEqual(
            profile.overrides,
            (("extensions.example-plugin.repositories.workspace", first, last),),
        )

    def test_public_resolver_does_not_require_private_key_declarations(self):
        self.write(
            "50-extension.toml",
            """
            schema_version = 1

            [extensions.any-plugin.custom]
            arbitrary_key = "value"
            """,
        )

        profile = load_profile(self.directory)

        self.assertEqual(
            profile.get("extensions.any-plugin.custom.arbitrary_key"), "value"
        )

    def test_rejects_unknown_top_level_namespace(self):
        self.write(
            "bad.toml",
            """
            schema_version = 1
            [private]
            value = "not namespaced"
            """,
        )

        with self.assertRaisesRegex(ProfileError, "top-level"):
            load_profile(self.directory)

    def test_rejects_secret_shaped_keys(self):
        self.write(
            "bad.toml",
            """
            schema_version = 1
            [extensions.demo]
            api_key = "must-not-live-here"
            """,
        )

        with self.assertRaisesRegex(ProfileError, "secret-like"):
            load_profile(self.directory)

    def test_rejects_non_scalar_values(self):
        self.write(
            "bad.toml",
            """
            schema_version = 1
            [public.repositories]
            paths = ["one", "two"]
            """,
        )

        with self.assertRaisesRegex(ProfileError, "non-secret scalar"):
            load_profile(self.directory)

    def test_missing_key_is_explicit(self):
        self.write("empty.toml", "schema_version = 1\n")
        profile = load_profile(self.directory)

        with self.assertRaisesRegex(ProfileError, "not configured"):
            profile.get("public.repositories.knowledge")

    def test_profile_directory_respects_an_explicit_empty_environment(self):
        self.assertEqual(
            profile_directory({}),
            Path.home() / ".config" / "tr-kit" / "profile.d",
        )

    def test_cli_get_and_doctor(self):
        self.write(
            "50-demo.toml",
            """
            schema_version = 1
            [extensions.demo]
            enabled = true
            """,
        )
        command = [
            sys.executable,
            str(ROOT / "core/profile/resolver.py"),
            "--profile-dir",
            str(self.directory),
        ]

        get_result = subprocess.run(
            [*command, "get", "extensions.demo.enabled"],
            text=True,
            capture_output=True,
        )
        doctor_result = subprocess.run(
            [*command, "doctor"], text=True, capture_output=True
        )

        self.assertEqual(get_result.returncode, 0, get_result.stderr)
        self.assertEqual(get_result.stdout, "true\n")
        self.assertEqual(doctor_result.returncode, 0, doctor_result.stderr)
        self.assertEqual(doctor_result.stdout, "ok fragments=1 values=1 overrides=0\n")


if __name__ == "__main__":
    unittest.main()
