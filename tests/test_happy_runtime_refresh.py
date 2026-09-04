import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "adapters/codex/capabilities/scripts/happy_runtime_refresh.py"
SPEC = importlib.util.spec_from_file_location("happy_runtime_refresh", HELPER)
assert SPEC and SPEC.loader
refresh = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(refresh)


class HappyRuntimeRefreshTest(unittest.TestCase):
    def test_log_state_uses_last_model_turn_boundary(self):
        completed = '[10:00] [Codex] Event: {"type":"task_complete"}'
        started = '[10:01] [Codex] Event: {"type":"task_started"}'
        self.assertEqual(refresh.classify_log(completed), "idle")
        self.assertEqual(
            refresh.classify_log(f"{completed}\n{started}"),
            "busy",
        )
        self.assertEqual(refresh.classify_log("git status only"), "unknown")

    def test_nested_event_text_inside_tool_output_does_not_change_state(self):
        started = '[10:01] [Codex] Event: {"type":"task_started"}'
        nested = (
            '[10:02] [Codex] Event: {"type":"exec_command_end",'
            '"output":"old \\\"type\\\":\\\"task_complete\\\""}'
        )
        self.assertEqual(refresh.classify_log(f"{started}\n{nested}"), "busy")

    def test_apply_guard_rejects_current_busy_and_stale_pid(self):
        base = refresh.Session(
            session_id="happy-a",
            host_pid=101,
            path=Path("/tmp/demo"),
            flavor="codex",
            lifecycle="running",
            turn_state="idle",
            current=False,
            alive=True,
            skill_count=22,
        )
        refresh.validate_target(base, 101)

        for changed, message in (
            ({"current": True}, "current session"),
            ({"turn_state": "busy"}, "not idle"),
            ({"alive": False}, "not running"),
        ):
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(refresh.RefreshError, message):
                    refresh.validate_target(base._replace(**changed), 101)

        with self.assertRaisesRegex(refresh.RefreshError, "stale PID"):
            refresh.validate_target(base, 999)


if __name__ == "__main__":
    unittest.main()
