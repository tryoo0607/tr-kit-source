#!/usr/bin/env python3
"""Codex transport for the target-neutral lifecycle contract."""

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
    return base / "codex-remote"


def _session_key() -> str:
    raw = os.environ.get("TR_SESSION_KEY", "default")
    return raw if SAFE_ID.fullmatch(raw) else re.sub(r"[^A-Za-z0-9._-]", "_", raw)


def _session_id(raw: dict[str, Any]) -> str:
    value = raw.get("session_id", "")
    return value if isinstance(value, str) and SAFE_ID.fullmatch(value) else ""


def _rollout(raw: dict[str, Any], sid: str) -> Path | None:
    codex_root = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).resolve()
    sessions = (codex_root / "sessions").resolve()
    candidate = raw.get("transcript_path") or raw.get("rollout_path")
    if isinstance(candidate, str) and candidate:
        path = Path(candidate).resolve()
        if path.is_relative_to(sessions) and path.is_file():
            return path
    if sid and sessions.is_dir():
        return next(sessions.rglob(f"*-{sid}.jsonl"), None)
    return None


def _tail_lines(path: Path) -> list[bytes]:
    with path.open("rb") as stream:
        size = stream.seek(0, 2)
        start = max(size - TAIL_BYTES, 0)
        stream.seek(start)
        data = stream.read()
    lines = data.splitlines()
    return lines[1:] if start and lines else lines


def _usage(path: Path) -> tuple[int, int] | None:
    for line in reversed(_tail_lines(path)):
        try:
            record = json.loads(line)
            if record.get("type") != "event_msg" or record.get("payload", {}).get("type") != "token_count":
                continue
            info = record["payload"].get("info")
            window = info.get("model_context_window")
            used = info.get("last_token_usage", {}).get("input_tokens")
            if isinstance(window, int) and window > 0 and isinstance(used, int) and used >= 0:
                return used, window
        except (json.JSONDecodeError, AttributeError, KeyError, TypeError):
            continue
    return None


def context_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    sid = _session_id(raw)
    path = _rollout(raw, sid)
    usage = _usage(path) if sid and path else None
    if not usage:
        return None
    notice = _state_root() / "rollover-budget"
    return {
        "schema_version": 1,
        "event": "context.observed",
        "session": {"id": sid},
        "context": {"used_tokens": usage[0], "window_tokens": usage[1]},
        "policy": {
            "prepare": {"mode": "ratio", "value": 60},
            "handoff": {"mode": "ratio", "value": 75},
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
    percent = data.get("used_percent")
    notice = _state_root() / "rollover-budget"
    if action == "rollover.prepare":
        notice.mkdir(parents=True, exist_ok=True)
        (notice / f"{sid}.prep").touch()
        return (
            f"⚠️ **Codex 컨텍스트 {percent}% — 독립 인계 준비를 시작한다.**\n"
            "현재 milestone을 마무리하며 `state/<slug>.md`의 단계·결정·미결을 최신화한다. "
            "75%에 도달하면 resume/fork가 아닌 새 독립 세션으로 넘긴다.\n\n"
        )
    if action == "rollover.handoff":
        notice.mkdir(parents=True, exist_ok=True)
        (notice / f"{sid}.prep").touch()
        (notice / f"{sid}.handoff").touch()
        pending = _state_root() / "pending-handoff"
        pending.mkdir(parents=True, exist_ok=True)
        (pending / _session_key()).write_text(sid + "\n")
        return (
            f"⛔ **Codex 컨텍스트 {percent}% — 새 독립 세션으로 인계할 시점이다.**\n"
            "새 작업을 시작하지 말고 milestone과 `state/<slug>.md`를 마무리한다. 응답 끝에 "
            "인계 파일 하나·다음 작업·검증 계획이 든 시작 프롬프트를 제공한다. "
            "resume/fork하지 말고 새 독립 세션에서 이어간다.\n\n"
        )
    return ""


def resume_event(raw: dict[str, Any]) -> dict[str, Any]:
    sid = _session_id(raw) or "unknown"
    marker = _state_root() / "pending-handoff" / _session_key()
    origin = marker.read_text().strip() if marker.is_file() else ""
    return {
        "schema_version": 1,
        "event": "session.started",
        "session": {"id": sid},
        "resume": {
            "pending_origin_session": origin,
            "state_available": os.environ.get("TR_STATE_AVAILABLE") == "1",
        },
    }


def ack_resume() -> None:
    marker = _state_root() / "pending-handoff" / _session_key()
    marker.unlink(missing_ok=True)


def render_compact(result: dict[str, Any]) -> str:
    action = result.get("action")
    trigger = result.get("data", {}).get("trigger")
    if action == "compact.block":
        return (
            "Codex auto-compact를 한 번 막았다. 파일을 고쳤는데 작업 기록이 갱신되지 않았다.\n\n"
            "milestone과 `state/<slug>.md`를 마무리하고 인계 파일 하나·다음 작업·검증 계획이 "
            "든 시작 프롬프트를 제공한다. resume/fork하지 말고 새 독립 세션으로 넘긴다.\n"
        )
    if action == "compact.warn" and trigger == "manual":
        return (
            "⚠️ **기록이 안 된 채 Codex 컨텍스트를 compact한다.** 압축 후 `state/`를 먼저 "
            "최신화하고 새 독립 세션으로 인계한다.\n\n"
        )
    if action == "compact.warn":
        return (
            "⚠️ **기록 없이 Codex auto-compact 된다.** 첫 턴에 `state/`를 채우고 "
            "resume/fork가 아닌 새 독립 세션으로 인계한다.\n\n"
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
        elif mode == "ack-resume":
            ack_resume()
        elif mode == "render-compact":
            sys.stdout.write(render_compact(raw))
        else:
            raise ValueError("unknown mode")
    except (OSError, ValueError, json.JSONDecodeError):
        return


if __name__ == "__main__":
    main()
