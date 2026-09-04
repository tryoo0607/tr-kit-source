import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from core.lifecycle.decision import decide


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


class AdapterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.state = Path(self.tmp.name) / "state"
        self.home.mkdir()
        self.state.mkdir()
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "XDG_STATE_HOME": str(self.state),
            "TR_CONTINUITY_KEY": "happy-codex-project",
            "TR_PROJECT": "demo",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def adapter(self, target: str) -> Path:
        return ROOT / "adapters" / target / "hooks" / "lifecycle-adapter.py"

    def run_adapter(self, target: str, mode: str, payload: dict) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["python3", str(self.adapter(target)), mode],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )

    def codex_payload(self, fixture: str, session_id: str = "codex-session") -> dict:
        sessions = self.home / ".codex" / "sessions" / "2026" / "09" / "03"
        sessions.mkdir(parents=True, exist_ok=True)
        rollout = sessions / f"rollout-{session_id}.jsonl"
        rollout.write_text((FIXTURES / fixture).read_text())
        return {"session_id": session_id, "transcript_path": str(rollout)}

    def test_codex_adapter_normalizes_ratio_budget_and_renders_one_shot(self):
        event_proc = self.run_adapter(
            "codex", "context-event", self.codex_payload("codex-context-60.jsonl")
        )
        self.assertEqual(event_proc.returncode, 0, event_proc.stderr)
        result = decide(json.loads(event_proc.stdout))
        self.assertEqual(result["action"], "rollover.prepare")

        render = self.run_adapter("codex", "render-context", result)
        self.assertIn("60%", render.stdout)
        self.assertIn("/clear", render.stdout)
        self.assertIn("인계 준비", render.stdout)

        repeated_event = json.loads(
            self.run_adapter(
                "codex", "context-event", self.codex_payload("codex-context-60.jsonl")
            ).stdout
        )
        self.assertEqual(decide(repeated_event)["action"], "none")

    def test_codex_handoff_is_consumed_only_after_clear_in_same_continuity(self):
        observed = json.loads(
            self.run_adapter(
                "codex", "context-event", self.codex_payload("codex-context-75.jsonl", "old")
            ).stdout
        )
        result = decide(observed)
        self.assertEqual(result["action"], "rollover.handoff")
        rendered = self.run_adapter("codex", "render-context", result)
        self.assertIn("/clear", rendered.stdout)
        self.assertIn("하셔도 됩니다", rendered.stdout)

        same = json.loads(
            self.run_adapter("codex", "resume-event", {"session_id": "old"}).stdout
        )
        self.assertEqual(decide(same)["action"], "none")

        self.env["TR_STATE_AVAILABLE"] = "1"
        new = json.loads(
            self.run_adapter("codex", "resume-event", {"session_id": "new"}).stdout
        )
        self.assertEqual(decide(new)["action"], "resume.inject")
        self.assertEqual(decide(new)["data"]["project"], "demo")
        self.run_adapter("codex", "ack-resume", {"session_id": "new"})
        after_ack = json.loads(
            self.run_adapter("codex", "resume-event", {"session_id": "newer"}).stdout
        )
        self.assertEqual(decide(after_ack)["action"], "none")

    def test_codex_below_prepare_threshold_is_silent(self):
        event_proc = self.run_adapter(
            "codex", "context-event", self.codex_payload("codex-context-59.jsonl")
        )
        self.assertEqual(decide(json.loads(event_proc.stdout))["action"], "none")

    def test_claude_adapter_uses_remaining_tokens_not_fixed_percent(self):
        transcript = self.home / ".claude" / "projects" / "demo" / "session.jsonl"
        transcript.parent.mkdir(parents=True)
        transcript.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "usage": {
                            "input_tokens": 10_000,
                            "cache_creation_input_tokens": 20_000,
                            "cache_read_input_tokens": 120_000,
                        }
                    },
                }
            )
            + "\n"
        )
        payload = {"session_id": "claude-session", "transcript_path": str(transcript)}

        event_proc = self.run_adapter("claude", "context-event", payload)
        self.assertEqual(event_proc.returncode, 0, event_proc.stderr)
        normalized = json.loads(event_proc.stdout)
        self.assertEqual(normalized["context"]["used_tokens"], 150_000)
        self.assertEqual(normalized["policy"]["handoff"], {"mode": "remaining", "value": 50_000})
        self.assertEqual(decide(normalized)["action"], "rollover.handoff")

    def test_adapter_rejects_transcript_outside_product_state_root(self):
        payload = {"session_id": "safe", "transcript_path": "/tmp/not-owned.jsonl"}
        for target in ("claude", "codex"):
            with self.subTest(target=target):
                result = self.run_adapter(target, "context-event", payload)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
