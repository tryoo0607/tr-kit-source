import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "adapters/codex/hooks/lifecycle-adapter.py"
SPEC = importlib.util.spec_from_file_location("codex_lifecycle_adapter", ADAPTER)
assert SPEC and SPEC.loader
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


class HappyContinuityKeyTest(unittest.TestCase):
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
