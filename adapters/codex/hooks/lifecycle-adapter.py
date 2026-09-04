#!/usr/bin/env python3
"""Codex transport for the target-neutral lifecycle contract."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


TAIL_BYTES = 4 * 1024 * 1024
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
HAPPY_SESSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def _read_json() -> dict[str, Any]:
    value = json.load(sys.stdin)
    return value if isinstance(value, dict) else {}


def _state_root() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return base / "codex-remote"


def _ancestor_pids(start: int | None = None) -> set[int]:
    pid = start if start is not None else os.getppid()
    found: set[int] = set()
    while pid > 1 and pid not in found:
        found.add(pid)
        try:
            for line in Path(f"/proc/{pid}/status").read_text().splitlines():
                if line.startswith("PPid:"):
                    pid = int(line.split()[1])
                    break
            else:
                break
        except (OSError, ValueError, IndexError):
            break
    return found


def _happy_session_key(sessions_path: Path, ancestor_pids: set[int]) -> str:
    # TEMPORARY_HAPPY_COMPAT: remove this branch after the PolyGarden cutover.
    try:
        sessions = json.loads(sessions_path.read_text()).get("sessions", {})
    except (OSError, json.JSONDecodeError, AttributeError):
        return ""
    if not isinstance(sessions, dict):
        return ""
    matches = []
    for session_id, value in sessions.items():
        metadata = value.get("metadata", {}) if isinstance(value, dict) else {}
        if (
            isinstance(session_id, str)
            and SAFE_ID.fullmatch(session_id)
            and isinstance(metadata, dict)
            and metadata.get("hostPid") in ancestor_pids
        ):
            matches.append(session_id)
    return f"happy-{matches[0]}" if len(matches) == 1 else ""


def _continuity_key() -> str:
    explicit = os.environ.get("TR_CONTINUITY_KEY", "")
    if explicit and SAFE_ID.fullmatch(explicit):
        return explicit
    # TEMPORARY_HAPPY_COMPAT: Happy injects this stable ID even when hostPid is stale.
    reconnect = os.environ.get("HAPPY_RECONNECT_SESSION_ID", "")
    if reconnect and HAPPY_SESSION_ID.fullmatch(reconnect):
        return f"happy-{reconnect}"
    happy = _happy_session_key(Path.home() / ".happy/sessions.json", _ancestor_pids())
    if happy:
        return happy
    tmux = os.environ.get("TMUX", "")
    pane = os.environ.get("TMUX_PANE", "")
    if tmux and pane:
        digest = hashlib.sha256(f"{tmux}\0{pane}".encode()).hexdigest()[:20]
        return f"tmux-{digest}"
    return ""


def _marker(key: str) -> Path | None:
    return _state_root() / "pending-handoff" / key if key else None


def _project() -> str:
    value = os.environ.get("TR_PROJECT", "")
    return value if value and SAFE_ID.fullmatch(value) else ""


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
    memory: dict[str, Any] = {
        "prepare_notified": (notice / f"{sid}.prep").exists(),
        "handoff_notified": (notice / f"{sid}.handoff").exists(),
    }
    key = _continuity_key()
    project = _project()
    if key:
        memory["continuity_key"] = key
    if project:
        memory["project"] = project
    return {
        "schema_version": 1,
        "event": "context.observed",
        "session": {"id": sid},
        "context": {"used_tokens": usage[0], "window_tokens": usage[1]},
        "policy": {
            "prepare": {"mode": "ratio", "value": 60},
            "handoff": {"mode": "ratio", "value": 75},
        },
        "memory": memory,
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
            f"⚠️ **Codex 컨텍스트 {percent}% — `/clear` 인계 준비를 시작한다.**\n"
            "현재 milestone을 마무리하며 `state/<slug>.md`의 단계·결정·미결을 최신화한다. "
            "아직 `/clear`할 시점은 아니다.\n\n"
        )
    if action == "rollover.handoff":
        notice.mkdir(parents=True, exist_ok=True)
        (notice / f"{sid}.prep").touch()
        (notice / f"{sid}.handoff").touch()
        key = data.get("continuity_key", "")
        marker = _marker(key) if isinstance(key, str) else None
        if marker:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(
                json.dumps(
                    {"origin_session": sid, "project": data.get("project", "")},
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )
        return (
            f"⛔ **Codex 컨텍스트 {percent}% — `/clear`로 인계할 시점이다.**\n"
            "새 작업을 시작하지 말고 현재 milestone과 `state/<slug>.md`의 단계·결정·미결·다음 검증을 "
            "마무리한다. 기록이 끝난 응답에서 **`인계 기록이 준비됐습니다. 이제 /clear 하셔도 됩니다.`**라고 안내한다.\n\n"
        )
    return ""


def resume_event(raw: dict[str, Any]) -> dict[str, Any]:
    sid = _session_id(raw) or "unknown"
    marker = _marker(_continuity_key())
    origin = ""
    project = ""
    if marker and marker.is_file():
        try:
            pending = json.loads(marker.read_text())
            if isinstance(pending, dict):
                origin = pending.get("origin_session", "")
                project = pending.get("project", "")
        except (OSError, json.JSONDecodeError):
            origin = ""
    return {
        "schema_version": 1,
        "event": "session.started",
        "session": {"id": sid},
        "resume": {
            "pending_origin_session": origin,
            "state_available": os.environ.get("TR_STATE_AVAILABLE") == "1",
            "project": project if isinstance(project, str) and SAFE_ID.fullmatch(project) else "",
        },
    }


def ack_resume() -> None:
    marker = _marker(_continuity_key())
    if marker:
        marker.unlink(missing_ok=True)


def render_compact(result: dict[str, Any]) -> str:
    action = result.get("action")
    trigger = result.get("data", {}).get("trigger")
    if action == "compact.block":
        return (
            "Codex auto-compact를 한 번 막았다. 파일을 고쳤는데 작업 기록이 갱신되지 않았다.\n\n"
            "milestone과 `state/<slug>.md`를 마무리한다. auto-compact는 같은 thread의 압축 재개이며 "
            "별도 thread로 오인하지 않는다.\n"
        )
    if action == "compact.warn" and trigger == "manual":
        return (
            "⚠️ **기록이 안 된 채 Codex 컨텍스트를 compact한다.** 압축 후 `state/`를 먼저 "
            "최신화하고 새 독립 세션으로 인계한다.\n\n"
        )
    if action == "compact.warn":
        return (
            "⚠️ **기록 없이 Codex auto-compact 된다.** 첫 턴에 `state/`를 채우고 "
            "같은 thread의 압축된 문맥에서 이어간다.\n\n"
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
