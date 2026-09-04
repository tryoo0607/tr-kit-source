#!/usr/bin/env python3
"""Claude transport for the target-neutral lifecycle contract."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any


TAIL_BYTES = 4 * 1024 * 1024
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def _read_json() -> dict[str, Any]:
    value = json.load(sys.stdin)
    return value if isinstance(value, dict) else {}


def _state_root() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    # Historical namespace retained so existing rollover notices survive updates.
    # This is not a dependency on the retired claude-remote host binary.
    return base / "claude-remote"


def _session_id(raw: dict[str, Any]) -> str:
    value = raw.get("session_id", "")
    return value if isinstance(value, str) and SAFE_ID.fullmatch(value) else ""


def _transcript(raw: dict[str, Any]) -> Path | None:
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")).resolve()
    projects = (config / "projects").resolve()
    candidate = raw.get("transcript_path")
    if not isinstance(candidate, str) or not candidate:
        return None
    path = Path(candidate).resolve()
    return path if path.is_relative_to(projects) and path.is_file() else None


def _tail_lines(path: Path) -> list[bytes]:
    with path.open("rb") as stream:
        size = stream.seek(0, 2)
        start = max(size - TAIL_BYTES, 0)
        stream.seek(start)
        data = stream.read()
    lines = data.splitlines()
    return lines[1:] if start and lines else lines


def _used_tokens(path: Path) -> int | None:
    for line in reversed(_tail_lines(path)):
        try:
            usage = json.loads(line).get("message", {}).get("usage")
            if not isinstance(usage, dict):
                continue
            values = [
                usage.get("input_tokens", 0),
                usage.get("cache_creation_input_tokens", 0),
                usage.get("cache_read_input_tokens", 0),
            ]
            if all(isinstance(value, int) and value >= 0 for value in values):
                return sum(values)
        except (json.JSONDecodeError, AttributeError, TypeError):
            continue
    return None


def _positive_env(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, default))
        return value if value > 0 else default
    except ValueError:
        return default


def context_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    sid = _session_id(raw)
    path = _transcript(raw)
    used = _used_tokens(path) if sid and path else None
    if used is None:
        return None
    window = _positive_env("TR_CLAUDE_CONTEXT_WINDOW", 200_000)
    notice = _state_root() / "rollover-budget"
    return {
        "schema_version": 1,
        "event": "context.observed",
        "session": {"id": sid},
        "context": {"used_tokens": used, "window_tokens": window},
        "policy": {
            "prepare": {
                "mode": "remaining",
                "value": _positive_env("TR_CLAUDE_PREP_REMAINING", 80_000),
            },
            "handoff": {
                "mode": "remaining",
                "value": _positive_env("TR_CLAUDE_HANDOFF_REMAINING", 50_000),
            },
        },
        "memory": {
            "prepare_notified": (notice / f"{sid}.prep").exists(),
            "handoff_notified": (notice / f"{sid}.handoff").exists(),
        },
    }


def render_context(result: dict[str, Any]) -> str:
    action = result.get("action")
    data = result.get("data", {})
    sid = data.get("session_id", "")
    if not isinstance(sid, str) or not SAFE_ID.fullmatch(sid):
        return ""
    remaining = data.get("remaining_tokens")
    notice = _state_root() / "rollover-budget"
    if action == "rollover.prepare":
        notice.mkdir(parents=True, exist_ok=True)
        (notice / f"{sid}.prep").touch()
        return (
            f"⚠️ **Claude 컨텍스트 잔여 {remaining:,}토큰 — 롤오버 기록을 준비한다.**\n"
            "현재 milestone을 마무리하며 `state/<slug>.md`를 최신화한다. 아직 `/clear`할 시점은 아니다.\n\n"
        )
    if action == "rollover.handoff":
        notice.mkdir(parents=True, exist_ok=True)
        (notice / f"{sid}.prep").touch()
        (notice / f"{sid}.handoff").touch()
        return (
            f"⛔ **Claude 컨텍스트 잔여 {remaining:,}토큰 — `/clear`로 인계할 시점이다.**\n"
            "새 작업을 시작하지 말고 현재 milestone과 `state/<slug>.md`만 마무리한 뒤 `/clear`를 안내한다.\n\n"
        )
    return ""


def resume_event(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "event": "session.started",
        "session": {"id": _session_id(raw) or "unknown"},
        "resume": {"pending_origin_session": "", "state_available": False},
    }


def render_compact(result: dict[str, Any]) -> str:
    action = result.get("action")
    trigger = result.get("data", {}).get("trigger")
    if action == "compact.block":
        return (
            "auto-compact를 한 번 막았다. 파일을 고쳤는데 작업 기록이 갱신되지 않았다.\n\n"
            "지금 milestone과 `state/<slug>.md`를 마무리하고 유저에게 `/clear`를 권한다. "
            "다음 compact는 막지 않는다.\n"
        )
    if action == "compact.warn" and trigger == "manual":
        return (
            "⚠️ **기록이 안 된 채 `/compact` 한다.** 압축 후 첫 턴에 "
            "`state/<slug>.md`부터 최신화한다.\n\n"
        )
    if action == "compact.warn":
        return (
            "⚠️ **기록 없이 auto-compact 된다.** 첫 턴에 `state/`를 채우고 "
            "필요하면 transcript를 읽는다.\n\n"
        )
    return ""


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) == 2 else ""
    try:
        raw = _read_json()
        if mode == "context-event":
            value = context_event(raw)
            if value:
                print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
        elif mode == "render-context":
            sys.stdout.write(render_context(raw))
        elif mode == "resume-event":
            print(json.dumps(resume_event(raw), ensure_ascii=False, separators=(",", ":")))
        elif mode == "render-compact":
            sys.stdout.write(render_compact(raw))
        elif mode == "ack-resume":
            pass
        else:
            raise ValueError("unknown mode")
    except (OSError, ValueError, json.JSONDecodeError):
        return


if __name__ == "__main__":
    main()
