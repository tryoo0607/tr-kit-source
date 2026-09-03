import contextlib
import io
import os
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from core.profile.bindings import BindingError, load_contracts, run_cli


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "core/profile/contracts/public-keys-v1.toml"


class ProfileBindingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.profile = self.root / "profile.d"
        self.repo = self.root / "knowledge"
        self.repo.mkdir()
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)
        (self.repo / "index.md").write_text("# Index\n")

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *argv: str):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = run_cli(
                contract_paths=[CONTRACT],
                managed_name="50-tr-kit.toml",
                managed_marker="# managed-by: tr-kit/profile-setup",
                argv=["--profile-dir", str(self.profile), *argv],
            )
        return code, output.getvalue()

    def test_contract_defaults_are_typed(self):
        contracts = load_contracts([CONTRACT])
        self.assertIs(contracts["public.features.dive_ambient"]["default"], False)
        self.assertEqual(contracts["public.scope.default"]["default"], "unknown")

    def test_plan_is_read_only_and_apply_writes_only_selected_key(self):
        key = "public.repositories.knowledge"
        _, plan = self.cli("plan", "--key", key, "--set", f"{key}={self.repo}")
        self.assertIn("explicit", plan)
        self.assertFalse(self.profile.exists())

        self.cli("apply", "--yes", "--key", key, "--set", f"{key}={self.repo}")
        target = self.profile / "50-tr-kit.toml"
        self.assertIn(str(self.repo), target.read_text())
        self.assertEqual(stat.S_IMODE(self.profile.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

        _, second = self.cli("apply", "--yes", "--key", key)
        self.assertIn("no changes", second)

    def test_partial_setup_does_not_require_unrelated_repositories(self):
        key = "public.repositories.knowledge"
        self.cli("apply", "--yes", "--key", key, "--set", f"{key}={self.repo}")
        _, output = self.cli("doctor", "--required-by", "knowledge")
        self.assertIn("configured", output)

    def test_required_skill_fails_when_binding_is_missing(self):
        with self.assertRaisesRegex(BindingError, "required bindings"):
            self.cli("doctor", "--required-by", "career")

    def test_user_override_wins_without_rewriting_it(self):
        self.profile.mkdir()
        override = self.profile / "90-local.toml"
        override.write_text(
            textwrap.dedent(
                f"""
                schema_version = 1
                [public.repositories]
                knowledge = "{self.repo}"
                """
            ).lstrip()
        )
        before = override.read_bytes()
        _, output = self.cli("doctor", "--required-by", "knowledge")
        self.assertIn(str(override), output)
        self.assertEqual(override.read_bytes(), before)

    def test_refuses_unmanaged_and_symlink_targets(self):
        self.profile.mkdir()
        target = self.profile / "50-tr-kit.toml"
        target.write_text("schema_version = 1\n")
        with self.assertRaisesRegex(BindingError, "unmanaged"):
            self.cli("plan")
        target.unlink()
        real = self.root / "real.toml"
        real.write_text("schema_version = 1\n")
        target.symlink_to(real)
        with self.assertRaisesRegex(BindingError, "symlink"):
            self.cli("plan")

    def test_rejects_unsafe_relative_path_and_wrong_boolean(self):
        with self.assertRaisesRegex(BindingError, "unsafe relative"):
            self.cli(
                "plan",
                "--key",
                "public.handoff.inbox",
                "--set",
                "public.handoff.inbox=../outside",
            )
        with self.assertRaisesRegex(BindingError, "true or false"):
            self.cli(
                "plan",
                "--key",
                "public.features.dive_ambient",
                "--set",
                "public.features.dive_ambient=yes",
            )

    def test_empty_plan_does_not_create_a_fragment(self):
        _, output = self.cli("plan")
        self.assertIn("profile:", output)
        self.assertFalse(self.profile.exists())

    def test_setup_cli_reports_errors_without_traceback(self):
        result = subprocess.run(
            [
                "python3",
                str(ROOT / "core/profile/setup.py"),
                "--profile-dir",
                str(self.profile),
                "get",
                "public.repositories.career",
            ],
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class ProfileContextTest(unittest.TestCase):
    def run_hook(self, value: bool | None) -> str:
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary)
            if value is not None:
                (profile / "50-test.toml").write_text(
                    "schema_version = 1\n[public.features]\n"
                    f"dive_ambient = {'true' if value else 'false'}\n"
                )
            with mock.patch.dict(os.environ, {"TR_KIT_PROFILE_DIR": str(profile)}):
                result = subprocess.run(
                    ["python3", str(ROOT / "shared/hooks/profile-context.py")],
                    text=True,
                    capture_output=True,
                    env=os.environ.copy(),
                )
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout

    def test_dive_context_is_opt_in(self):
        self.assertEqual(self.run_hook(None), "")
        self.assertEqual(self.run_hook(False), "")
        self.assertIn("dive ambient", self.run_hook(True))


if __name__ == "__main__":
    unittest.main()
