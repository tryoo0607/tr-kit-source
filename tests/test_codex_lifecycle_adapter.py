import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "adapters/codex/hooks/lifecycle-adapter.py"
SPEC = importlib.util.spec_from_file_location("codex_lifecycle_adapter", ADAPTER)
assert SPEC and SPEC.loader
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


class HappyContinuityKeyTest(unittest.TestCase):
    def test_explicit_override_precedes_happy_reconnect_session(self):
        with mock.patch.dict(
            os.environ,
            {
                "TR_CONTINUITY_KEY": "test-override",
                "HAPPY_RECONNECT_SESSION_ID": "cmtmhzv831zkxny15ad0rbxz0",
            },
            clear=True,
        ):
            self.assertEqual(adapter._continuity_key(), "test-override")

    def test_valid_happy_reconnect_session_precedes_pid_discovery(self):
        with (
            mock.patch.dict(
                os.environ,
                {"HAPPY_RECONNECT_SESSION_ID": "cmtmhzv831zkxny15ad0rbxz0"},
                clear=True,
            ),
            mock.patch.object(adapter, "_happy_session_key") as pid_discovery,
        ):
            self.assertEqual(
                adapter._continuity_key(),
                "happy-cmtmhzv831zkxny15ad0rbxz0",
            )
            pid_discovery.assert_not_called()

    def test_invalid_happy_reconnect_session_is_rejected_before_pid_fallback(self):
        with (
            mock.patch.dict(
                os.environ,
                {"HAPPY_RECONNECT_SESSION_ID": "../../other-marker"},
                clear=True,
            ),
            mock.patch.object(
                adapter,
                "_happy_session_key",
                return_value="happy-pid-fallback",
            ),
        ):
            self.assertEqual(adapter._continuity_key(), "happy-pid-fallback")

    def test_unique_happy_host_ancestor_becomes_continuity_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            sessions = Path(tmp) / "sessions.json"
            sessions.write_text(
                json.dumps(
                    {
                        "sessions": {
                            "happy-a": {"metadata": {"hostPid": 101}},
                            "happy-b": {"metadata": {"hostPid": 202}},
                        }
                    }
                )
            )

            self.assertEqual(
                adapter._happy_session_key(sessions, {1, 101, 303}),
                "happy-happy-a",
            )

    def test_missing_or_ambiguous_happy_host_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            sessions = Path(tmp) / "sessions.json"
            sessions.write_text(
                json.dumps(
                    {
                        "sessions": {
                            "happy-a": {"metadata": {"hostPid": 101}},
                            "happy-b": {"metadata": {"hostPid": 202}},
                        }
                    }
                )
            )

            self.assertEqual(adapter._happy_session_key(sessions, {303}), "")
            self.assertEqual(adapter._happy_session_key(sessions, {101, 202}), "")


if __name__ == "__main__":
    unittest.main()
