import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "host/happy/happy_cycle.py"
SPEC = importlib.util.spec_from_file_location("happy_cycle", HELPER)
assert SPEC and SPEC.loader
cycle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cycle)


class HappyCycleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / ".happy").mkdir()
        self.state = self.home / ".local/state/tr-kit/happy-cycle/snapshot.json"

    def tearDown(self):
        self.tmp.cleanup()

    def write_store(self, sessions):
        (self.home / ".happy/sessions.json").write_text(
            json.dumps({"sessions": sessions})
        )

    def test_inventory_requires_process_identity_not_stale_alive_pid(self):
        self.write_store(
            {
                "cmt-live": {
                    "metadata": {
                        "hostPid": 101,
                        "path": str(self.home),
                        "flavor": "claude",
                        "lifecycleState": "running",
                    }
                },
                "cmt-stale": {
                    "metadata": {
                        "hostPid": 202,
                        "path": str(self.home),
                        "flavor": "codex",
                        "lifecycleState": "running",
                    }
                },
            }
        )

        with mock.patch.object(
            cycle, "pid_matches_session", side_effect=lambda pid, sid: sid == "cmt-live"
        ):
            sessions = cycle.live_sessions(self.home)

        self.assertEqual([item.session_id for item in sessions], ["cmt-live"])

    def test_snapshot_is_dry_run_then_atomic_apply(self):
        sessions = [
            cycle.Session("cmt-live", 101, self.home, "claude"),
        ]
        with mock.patch.object(cycle, "live_sessions", return_value=sessions):
            cycle.snapshot(self.home, self.state, apply=False)
            self.assertFalse(self.state.exists())
            cycle.snapshot(self.home, self.state, apply=True)

        payload = json.loads(self.state.read_text())
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["sessions"][0]["session_id"], "cmt-live")
        self.assertFalse(self.state.with_suffix(".tmp").exists())

    def test_empty_observation_does_not_replace_nonempty_snapshot(self):
        self.state.parent.mkdir(parents=True)
        self.state.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "sessions": [
                        {
                            "session_id": "cmt-old",
                            "host_pid": 303,
                            "path": str(self.home),
                            "flavor": "claude",
                        }
                    ],
                }
            )
        )
        before = self.state.read_text()
        with mock.patch.object(cycle, "live_sessions", return_value=[]):
            cycle.snapshot(self.home, self.state, apply=True)
        self.assertEqual(self.state.read_text(), before)

    def test_cycle_validation_rejects_changed_pid_before_signalling(self):
        saved = [cycle.Session("cmt-live", 101, self.home, "claude")]
        current = [cycle.Session("cmt-live", 202, self.home, "claude")]
        with mock.patch.object(cycle, "live_sessions", return_value=current):
            with self.assertRaisesRegex(cycle.CycleError, "PID changed"):
                cycle.validate_cycle_targets(self.home, saved)

    def test_resume_environment_reads_host_config_without_shell_execution(self):
        config = self.home / ".config/happy/env"
        config.parent.mkdir(parents=True)
        config.write_text(
            'export HAPPY_SERVER_URL="https://happy.example"\n'
            'HAPPY_PLUGIN_DIRS=/srv/plugins/current\n'
        )

        environment = cycle.resume_environment(self.home)

        self.assertEqual(environment["HAPPY_SERVER_URL"], "https://happy.example")
        self.assertEqual(environment["HAPPY_PLUGIN_DIRS"], "/srv/plugins/current")
        self.assertIn(str(self.home / ".asdf/shims"), environment["PATH"])

    def test_noninteractive_cycle_requires_explicit_yes(self):
        with mock.patch.object(cycle.sys.stdin, "isatty", return_value=False):
            with self.assertRaisesRegex(cycle.CycleError, "--yes"):
                cycle.confirm_cycle(2, False)
        cycle.confirm_cycle(2, True)

    def test_cycle_does_not_signal_sessions_when_daemon_preflight_fails(self):
        saved = [cycle.Session("cmt-live", 101, self.home, "claude")]
        self.state.parent.mkdir(parents=True)
        self.state.write_text(json.dumps(cycle.snapshot_payload(saved)))
        with (
            mock.patch.object(cycle, "validate_cycle_targets", return_value=saved),
            mock.patch.object(cycle.os, "kill") as kill,
            mock.patch.object(
                cycle, "restart_daemon", side_effect=cycle.CycleError("daemon failed")
            ),
            mock.patch.object(cycle, "restore") as restore,
        ):
            with self.assertRaisesRegex(cycle.CycleError, "daemon failed"):
                cycle.cycle_worker(self.home, self.state, 0.01)
        kill.assert_not_called()
        restore.assert_not_called()

    def test_restore_launches_all_sessions_before_waiting_for_registration(self):
        saved = [
            cycle.Session("cmt-first", 101, self.home, "codex"),
            cycle.Session("cmt-second", 202, self.home, "codex"),
        ]
        launchers = [mock.Mock(pid=301), mock.Mock(pid=302)]
        with (
            mock.patch.object(cycle, "load_snapshot", return_value=saved),
            mock.patch.object(cycle, "live_sessions", return_value=[]),
            mock.patch.object(cycle.subprocess, "Popen", side_effect=launchers) as popen,
            mock.patch.object(
                cycle,
                "wait_resumed_sessions",
                return_value=({"cmt-first": 401, "cmt-second": 402}, []),
            ) as wait,
        ):
            results = cycle.restore(
                self.home, self.state, apply=True, timeout=60, already_locked=True
            )

        self.assertEqual(popen.call_count, 2)
        wait.assert_called_once_with(
            self.home, {"cmt-first", "cmt-second"}, timeout=60
        )
        self.assertEqual(
            [item["new_host_pid"] for item in results],
            [401, 402],
        )


if __name__ == "__main__":
    unittest.main()
