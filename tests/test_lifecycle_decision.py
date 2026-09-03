import unittest

from core.lifecycle.decision import LifecycleError, decide


def event(kind: str, **payload):
    return {
        "schema_version": 1,
        "event": kind,
        "session": {"id": "session-1"},
        **payload,
    }


class ContextDecisionTest(unittest.TestCase):
    def test_ratio_budget_has_prepare_and_handoff_stages(self):
        base = {
            "policy": {
                "prepare": {"mode": "ratio", "value": 60},
                "handoff": {"mode": "ratio", "value": 75},
            },
            "memory": {"prepare_notified": False, "handoff_notified": False},
        }

        at_59 = decide(event("context.observed", context={"used_tokens": 59, "window_tokens": 100}, **base))
        at_60 = decide(event("context.observed", context={"used_tokens": 60, "window_tokens": 100}, **base))
        at_75 = decide(event("context.observed", context={"used_tokens": 75, "window_tokens": 100}, **base))

        self.assertEqual(at_59["action"], "none")
        self.assertEqual(at_60["action"], "rollover.prepare")
        self.assertEqual(at_75["action"], "rollover.handoff")

    def test_remaining_token_budget_is_window_size_independent(self):
        result = decide(
            event(
                "context.observed",
                context={"used_tokens": 150_000, "window_tokens": 200_000},
                policy={
                    "prepare": {"mode": "remaining", "value": 80_000},
                    "handoff": {"mode": "remaining", "value": 50_000},
                },
                memory={"prepare_notified": False, "handoff_notified": False},
            )
        )

        self.assertEqual(result["action"], "rollover.handoff")
        self.assertEqual(result["data"]["remaining_tokens"], 50_000)

    def test_notification_memory_makes_each_stage_one_shot(self):
        result = decide(
            event(
                "context.observed",
                context={"used_tokens": 80, "window_tokens": 100},
                policy={
                    "prepare": {"mode": "ratio", "value": 60},
                    "handoff": {"mode": "ratio", "value": 75},
                },
                memory={"prepare_notified": True, "handoff_notified": True},
            )
        )

        self.assertEqual(result["action"], "none")


class ChangeDecisionTest(unittest.TestCase):
    def test_quoted_comparison_and_command_names_are_read_only(self):
        for command in (
            "jq 'select(.a > 1)' data.json",
            'grep " rm " notes.txt',
            "awk '$1 > 5' values.txt",
            "[[ $left > $right ]] && printf newer",
        ):
            with self.subTest(command=command):
                result = decide(
                    event(
                        "tool.completed",
                        tool={"kind": "command", "command": command, "record_path": False},
                    )
                )
                self.assertEqual(result["action"], "none")

    def test_actual_mutating_commands_and_redirection_are_marked(self):
        for command in (
            "sed -i s/old/new/ file.txt",
            "git -C repo commit -m test",
            "printf value > output.txt",
            "grep x input | tee output.txt",
        ):
            with self.subTest(command=command):
                result = decide(
                    event(
                        "tool.completed",
                        tool={"kind": "command", "command": command, "record_path": False},
                    )
                )
                self.assertEqual(result["action"], "change.mark")

    def test_record_writes_do_not_mark_the_turn(self):
        result = decide(
            event(
                "tool.completed",
                tool={"kind": "file_write", "command": "", "record_path": True},
            )
        )
        self.assertEqual(result["action"], "none")


class LifecycleGateDecisionTest(unittest.TestCase):
    def test_stop_blocks_then_falls_back(self):
        block = decide(
            event(
                "response.stopping",
                record={"changed": True, "fresh": False, "block_count": 0, "max_blocks": 2},
            )
        )
        fallback = decide(
            event(
                "response.stopping",
                record={"changed": True, "fresh": False, "block_count": 2, "max_blocks": 2},
            )
        )
        self.assertEqual(block["action"], "record.block")
        self.assertEqual(fallback["action"], "record.fallback")

    def test_auto_compact_blocks_once_but_manual_only_warns(self):
        auto = decide(
            event(
                "context.compacting",
                compact={"changed": True, "trigger": "auto", "block_count": 0},
            )
        )
        manual = decide(
            event(
                "context.compacting",
                compact={"changed": True, "trigger": "manual", "block_count": 0},
            )
        )
        self.assertEqual(auto["action"], "compact.block")
        self.assertEqual(manual["action"], "compact.warn")

    def test_new_session_consumes_pending_handoff(self):
        resume = decide(
            event(
                "session.started",
                resume={
                    "pending_origin_session": "old-session",
                    "state_available": True,
                },
            )
        )
        same = decide(
            event(
                "session.started",
                resume={
                    "pending_origin_session": "session-1",
                    "state_available": True,
                },
            )
        )
        self.assertEqual(resume["action"], "resume.inject")
        self.assertEqual(same["action"], "none")

    def test_rejects_unknown_event_kind(self):
        with self.assertRaisesRegex(LifecycleError, "unsupported lifecycle event"):
            decide(event("unknown"))


if __name__ == "__main__":
    unittest.main()
