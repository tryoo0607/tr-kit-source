import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.delivery import (
    DeliveryError,
    DeliverySpec,
    SyncMapping,
    deploy_target,
    verify_target,
)


class DeliveryDryRunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.output = self.root / "out"
        self.repo = self.root / "repo"
        (self.output / "payload").mkdir(parents=True)
        (self.output / "payload/new.txt").write_text("new\n")
        (self.repo / "plugins/demo").mkdir(parents=True)
        (self.repo / "plugins/demo/old.txt").write_text("old\n")
        (self.repo / "outside.txt").write_text("preserve\n")
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo, check=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "git@github.com:example/demo.git"],
            cwd=self.repo,
            check=True,
        )
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "initial"], cwd=self.repo, check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def spec(self, *, prepare=(), generated=()) -> DeliverySpec:
        return DeliverySpec(
            target="demo",
            repository="example/demo",
            mode="partial",
            generated=tuple(generated),
            prepare=tuple(tuple(command) for command in prepare),
            checks=(("python3", "-c", "from pathlib import Path; assert Path('outside.txt').read_text() == 'preserve\\n'"),),
            sync=(SyncMapping("payload", "plugins/demo"),),
        )

    def spec_with_checks(self, checks) -> DeliverySpec:
        spec = self.spec()
        return DeliverySpec(
            target=spec.target,
            repository=spec.repository,
            mode=spec.mode,
            generated=spec.generated,
            prepare=spec.prepare,
            checks=tuple(tuple(command) for command in checks),
            sync=spec.sync,
        )

    def test_dry_run_is_isolated_boundary_checked_and_idempotent(self):
        changed = verify_target(self.spec(), self.output, self.repo)

        self.assertEqual(changed, ("plugins/demo/new.txt", "plugins/demo/old.txt"))
        self.assertTrue((self.repo / "plugins/demo/old.txt").is_file())
        self.assertFalse((self.repo / "plugins/demo/new.txt").exists())

    def test_allows_declared_target_generated_file(self):
        command = (
            "python3",
            "-c",
            "from pathlib import Path; Path('SUMMARY.md').write_text('generated\\n')",
        )

        changed = verify_target(
            self.spec(prepare=(command,), generated=("SUMMARY.md",)), self.output, self.repo
        )

        self.assertIn("SUMMARY.md", changed)

    def test_rejects_prepare_command_that_overwrites_source_owned_payload(self):
        command = (
            "python3",
            "-c",
            "from pathlib import Path; Path('plugins/demo/new.txt').write_text('overwritten\\n')",
        )

        with self.assertRaisesRegex(DeliveryError, "changed source-owned path"):
            verify_target(self.spec(prepare=(command,)), self.output, self.repo)

    def test_rejects_prepare_command_that_escapes_declared_ownership(self):
        command = (
            "python3",
            "-c",
            "from pathlib import Path; Path('unexpected.txt').write_text('unexpected\\n')",
        )

        with self.assertRaisesRegex(DeliveryError, "escaped recipe ownership"):
            verify_target(self.spec(prepare=(command,)), self.output, self.repo)

    def test_rejects_check_command_that_modifies_clone(self):
        command = (
            "python3",
            "-c",
            "from pathlib import Path; Path('plugins/demo/new.txt').write_text('changed\\n')",
        )

        with self.assertRaisesRegex(DeliveryError, "check command modified"):
            verify_target(self.spec_with_checks((command,)), self.output, self.repo)

    def test_managed_root_replaces_every_tracked_path_in_disposable_clone(self):
        (self.output / ".tr-kit-generated").write_text("managed by tr-kit-source\n")
        (self.output / "README.md").write_text("generated repository\n")
        spec = DeliverySpec(
            target="demo",
            repository="example/demo",
            mode="managed-root",
            generated=(),
            prepare=(),
            checks=(),
            sync=(),
        )

        changed = verify_target(spec, self.output, self.repo)

        self.assertIn("outside.txt", changed)
        self.assertIn("README.md", changed)
        self.assertTrue((self.repo / "outside.txt").is_file())
        self.assertFalse((self.repo / "README.md").exists())

    def test_managed_root_requires_marker(self):
        spec = DeliverySpec(
            target="demo",
            repository="example/demo",
            mode="managed-root",
            generated=(),
            prepare=(),
            checks=(),
            sync=(),
        )

        with self.assertRaisesRegex(DeliveryError, "missing .tr-kit-generated"):
            verify_target(spec, self.output, self.repo)

    def test_deploy_requires_explicit_environment_gate(self):
        spec = self.spec()
        with self.assertRaisesRegex(DeliveryError, "TR_KIT_ALLOW_PUSH"):
            deploy_target(spec, self.output, self.repo, source_revision="a" * 40)


if __name__ == "__main__":
    unittest.main()
