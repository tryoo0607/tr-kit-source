#!/usr/bin/env python3
"""Inventory and safely rolling-refresh running Happy/Codex root sessions."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, NamedTuple


class RefreshError(RuntimeError):
    pass


class Session(NamedTuple):
    session_id: str
    host_pid: int
    path: Path
    flavor: str
    lifecycle: str
    turn_state: str
    current: bool
    alive: bool
    skill_count: int


def ancestor_pids(start: int | None = None) -> set[int]:
    pid = start if start is not None else os.getppid()
    found: set[int] = set()
    while pid > 1 and pid not in found:
        found.add(pid)
        try:
            status = Path(f"/proc/{pid}/status").read_text().splitlines()
            pid = int(next(line for line in status if line.startswith("PPid:")).split()[1])
        except (OSError, StopIteration, ValueError, IndexError):
            break
    return found


def pid_alive(pid: int) -> bool:
    if pid <= 1:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, PermissionError):
        return False


def _event_state(line: str) -> str:
    marker = "[Codex] Event: "
    _, found, payload = line.partition(marker)
    if not found:
        return "unknown"
    try:
        kind = json.loads(payload).get("type")
    except (json.JSONDecodeError, AttributeError):
        return "unknown"
    if kind == "task_started":
        return "busy"
    if kind == "task_complete":
        return "idle"
    return "unknown"


def classify_log(text: str) -> str:
    state = "unknown"
    for line in text.splitlines():
        observed = _event_state(line)
        if observed != "unknown":
            state = observed
    return state


def log_state(log_dir: Path, pid: int) -> str:
    candidates = sorted(log_dir.glob(f"*-pid-{pid}.log"), key=lambda path: path.stat().st_mtime)
    if not candidates:
        return "unknown"
    try:
        with candidates[-1].open("rb") as stream:
            position = stream.seek(0, 2)
            carry = b""
            while position > 0:
                size = min(position, 1024 * 1024)
                position -= size
                stream.seek(position)
                parts = (stream.read(size) + carry).splitlines()
                carry = parts[0] if parts else carry
                for raw in reversed(parts[1:]):
                    observed = _event_state(raw.decode("utf-8", errors="replace"))
                    if observed != "unknown":
                        return observed
            if carry:
                return _event_state(carry.decode("utf-8", errors="replace"))
            return "unknown"
    except OSError:
        return "unknown"


def load_sessions(home: Path) -> list[Session]:
    store = home / ".happy/sessions.json"
    try:
        values = json.loads(store.read_text()).get("sessions", {})
    except (OSError, json.JSONDecodeError, AttributeError) as exc:
        raise RefreshError(f"cannot read Happy session store: {store}") from exc
    if not isinstance(values, dict):
        raise RefreshError("Happy session store has no sessions object")

    ancestors = ancestor_pids()
    result: list[Session] = []
    for session_id, raw in values.items():
        metadata = raw.get("metadata", {}) if isinstance(raw, dict) else {}
        if not isinstance(session_id, str) or not isinstance(metadata, dict):
            continue
        pid = metadata.get("hostPid")
        path = metadata.get("path")
        flavor = metadata.get("flavor", "")
        if not isinstance(pid, int) or not isinstance(path, str) or flavor != "codex":
            continue
        skills = metadata.get("skills", [])
        skill_count = (
            sum(isinstance(item, str) and item.startswith("tr-codex:") for item in skills)
            if isinstance(skills, list)
            else 0
        )
        result.append(
            Session(
                session_id=session_id,
                host_pid=pid,
                path=Path(path),
                flavor=flavor,
                lifecycle=str(metadata.get("lifecycleState", "unknown")),
                turn_state=log_state(home / ".happy/logs", pid),
                current=pid in ancestors,
                alive=pid_alive(pid),
                skill_count=skill_count,
            )
        )
    return sorted(result, key=lambda item: item.session_id)


def validate_target(session: Session, expected_pid: int) -> None:
    if session.current:
        raise RefreshError(f"{session.session_id}: current session is excluded")
    if not session.alive or session.lifecycle != "running":
        raise RefreshError(f"{session.session_id}: session is not running")
    if session.turn_state != "idle":
        raise RefreshError(f"{session.session_id}: session is not idle ({session.turn_state})")
    if session.host_pid != expected_pid:
        raise RefreshError(
            f"{session.session_id}: stale PID (expected {expected_pid}, current {session.host_pid})"
        )


def parse_target(value: str) -> tuple[str, int]:
    session_id, separator, raw_pid = value.partition("=")
    if not separator or not session_id:
        raise argparse.ArgumentTypeError("target must be HAPPY_SESSION_ID=EXPECTED_PID")
    try:
        pid = int(raw_pid)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected PID must be an integer") from exc
    if pid <= 1:
        raise argparse.ArgumentTypeError("expected PID must be greater than 1")
    return session_id, pid


def wait_stopped(pid: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not pid_alive(pid):
            return True
        time.sleep(0.2)
    return not pid_alive(pid)


def resumed_metadata(home: Path, session_id: str) -> dict[str, Any]:
    try:
        value = json.loads((home / ".happy/sessions.json").read_text())
        metadata = value.get("sessions", {}).get(session_id, {}).get("metadata", {})
        return metadata if isinstance(metadata, dict) else {}
    except (OSError, json.JSONDecodeError, AttributeError):
        return {}


def wait_resumed(home: Path, session_id: str, old_pid: int, timeout: float) -> tuple[int, int]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        metadata = resumed_metadata(home, session_id)
        pid = metadata.get("hostPid")
        skills = metadata.get("skills", [])
        if isinstance(pid, int) and pid != old_pid and pid_alive(pid):
            count = (
                sum(isinstance(item, str) and item.startswith("tr-codex:") for item in skills)
                if isinstance(skills, list)
                else 0
            )
            return pid, count
        time.sleep(0.2)
    raise RefreshError(f"{session_id}: resume launch was not observed before timeout")


def refresh_one(
    home: Path, session: Session, expected_pid: int, timeout: float
) -> dict[str, Any]:
    validate_target(session, expected_pid)
    os.kill(session.host_pid, signal.SIGTERM)
    if not wait_stopped(session.host_pid, timeout):
        raise RefreshError(
            f"{session.session_id}: SIGTERM timeout; left stopped workflow for manual inspection"
        )
    try:
        process = subprocess.Popen(
            ["happy", "resume", session.session_id],
            cwd=session.path,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        raise RefreshError(f"{session.session_id}: failed to launch happy resume: {exc}") from exc
    new_pid, skill_count = wait_resumed(
        home, session.session_id, session.host_pid, timeout
    )
    return {
        "session_id": session.session_id,
        "old_host_pid": session.host_pid,
        "resume_launcher_pid": process.pid,
        "new_host_pid": new_pid,
        "tr_codex_skills": skill_count,
        "status": "resumed",
    }


def public_record(session: Session) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "host_pid": session.host_pid,
        "path": str(session.path),
        "flavor": session.flavor,
        "lifecycle": session.lifecycle,
        "turn_state": session.turn_state,
        "current": session.current,
        "alive": session.alive,
        "tr_codex_skills": session.skill_count,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument(
        "--home",
        type=Path,
        default=Path.home(),
        help=argparse.SUPPRESS,
    )
    commands = value.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory", help="read-only Happy/Codex root inventory")
    inventory.add_argument("--json", action="store_true")
    refresh = commands.add_parser("refresh", help="plan or apply exact idle session refreshes")
    refresh.add_argument("targets", nargs="+", type=parse_target, metavar="SESSION=PID")
    refresh.add_argument("--apply", action="store_true", help="send SIGTERM and launch happy resume")
    refresh.add_argument("--timeout", type=float, default=15.0)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        sessions = load_sessions(args.home)
        if args.command == "inventory":
            records = [public_record(session) for session in sessions]
            if args.json:
                print(json.dumps(records, ensure_ascii=False, indent=2))
            else:
                for item in records:
                    print(
                        "{session_id}\tpid={host_pid}\t{turn_state}\tcurrent={current}"
                        "\talive={alive}\tskills={tr_codex_skills}\t{path}".format(**item)
                    )
            return 0

        by_id = {session.session_id: session for session in sessions}
        selected = []
        for session_id, expected_pid in args.targets:
            session = by_id.get(session_id)
            if session is None:
                raise RefreshError(f"{session_id}: session not found")
            validate_target(session, expected_pid)
            selected.append((session, expected_pid))
        if not args.apply:
            print(json.dumps([public_record(item[0]) for item in selected], ensure_ascii=False, indent=2))
            print("PLAN ONLY — add --apply only after explicit user approval", file=sys.stderr)
            return 0
        results = [
            refresh_one(args.home, session, expected_pid, args.timeout)
            for session, expected_pid in selected
        ]
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0
    except RefreshError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
