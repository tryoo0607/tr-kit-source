import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class HappyHostInstallTest(unittest.TestCase):
    def test_dry_run_lists_host_assets_without_writing(self):
        with tempfile.TemporaryDirectory() as raw:
            dest = Path(raw)
            result = subprocess.run(
                ["bash", "install.sh", "happy-host", "--dest", str(dest)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn("happy-cycle", result.stdout)
            self.assertIn("happy-daemon.service", result.stdout)
            self.assertFalse((dest / ".local/bin/happy-cycle").exists())

    def test_staged_apply_copies_assets_without_touching_systemd(self):
        with tempfile.TemporaryDirectory() as raw:
            dest = Path(raw)
            subprocess.run(
                ["/bin/bash", "install.sh", "happy-host", "--dest", str(dest), "--apply"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
            helper = dest / ".local/bin/happy-cycle"
            self.assertTrue(helper.is_file())
            self.assertTrue(helper.stat().st_mode & 0o111)
            self.assertTrue(
                (dest / ".config/systemd/user/happy-daemon.service").is_file()
            )
            timer = dest / ".config/systemd/user/happy-session-snapshot.timer"
            self.assertIn("Persistent=true", timer.read_text())

    def test_host_assets_are_temporary_and_do_not_auto_restore_sessions(self):
        assets = list((ROOT / "host/happy").rglob("*"))
        files = [path for path in assets if path.is_file() and "__pycache__" not in path.parts]
        self.assertTrue(files)
        for path in files:
            self.assertIn("TEMPORARY_HAPPY_COMPAT", path.read_text(), path)
        unit_names = {path.name for path in (ROOT / "host/happy/systemd").iterdir()}
        self.assertNotIn("happy-session-restore.service", unit_names)

    def test_apply_replaces_legacy_unit_symlink_without_touching_local_env(self):
        with tempfile.TemporaryDirectory() as raw:
            dest = Path(raw) / "stage"
            legacy = Path(raw) / "legacy-happy-daemon.service"
            legacy.write_text("legacy\n")
            unit = dest / ".config/systemd/user/happy-daemon.service"
            unit.parent.mkdir(parents=True)
            unit.symlink_to(legacy)

            subprocess.run(
                ["bash", "install.sh", "happy-host", "--dest", str(dest), "--apply"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertFalse(unit.is_symlink())
            self.assertEqual(legacy.read_text(), "legacy\n")
            self.assertFalse((dest / ".config/happy/env").exists())


if __name__ == "__main__":
    unittest.main()
