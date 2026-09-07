#!/usr/bin/env python3
"""Snapshot, restore, and safely cycle Happy sessions.

TEMPORARY_HAPPY_COMPAT: remove with the Happy host integration after PolyGarden migration.
The snapshot stores resurrection coordinates only; conversation data remains in Happy.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import NamedTuple


SESSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class CycleError(RuntimeError):
    pass


class Session(NamedTuple):
    session_id: str
    host_pid: int
    path: Path
    flavor: str


def default_state(home: Path) -> Path:
    return home / ".local/state/tr-kit/happy-cycle/snapshot.json"


def pid_alive(pid: int) -> bool:
    if pid <= 1:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, PermissionError):
        return False


def pid_matches_session(pid: int, session_id: str) -> bool:
    """Reject stale/reused PIDs unless the Happy continuity ID matches."""
    if not pid_alive(pid):
        return False
    try:
        values = (Path(f"/proc/{pid}/environ").read_bytes()).split(b"\0")
    except OSError:
        return False
    expected = f"HAPPY_RECONNECT_SESSION_ID={session_id}".encode()
    return expected in values


def resume_environment(home: Path) -> dict[str, str]:
    environment = dict(os.environ)
    default_path = ":".join(
        (
            str(home / ".asdf/bin"),
            str(home / ".asdf/shims"),
            str(home / ".local/bin"),
            "/usr/local/bin",
            "/usr/bin",
            "/bin",
        )
    )
    environment["PATH"] = f"{default_path}:{environment.get('PATH', '')}".rstrip(":")
    source = home / ".config/happy/env"
    if not source.is_file():
        return environment
    for number, raw_line in enumerate(source.read_text().splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, raw_value = line.partition("=")
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise CycleError(f"invalid environment entry at {source}:{number}")
        try:
            values = shlex.split(raw_value, comments=True, posix=True)
        except ValueError as exc:
            raise CycleError(f"invalid environment value at {source}:{number}") from exc
        if len(values) > 1:
            raise CycleError(f"environment value must be quoted at {source}:{number}")
        environment[key] = values[0] if values else ""
    return environment


def session_store(home: Path) -> dict:
    store = home / ".happy/sessions.json"
    try:
        value = json.loads(store.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise CycleError(f"cannot read Happy session store: {store}") from exc
    sessions = value.get("sessions") if isinstance(value, dict) else None
    if not isinstance(sessions, dict):
        raise CycleError("Happy session store has no sessions object")
    return sessions


def live_sessions(home: Path) -> list[Session]:
    result: list[Session] = []
    for session_id, raw in session_store(home).items():
        metadata = raw.get("metadata", {}) if isinstance(raw, dict) else {}
        if not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id):
            continue
        if not isinstance(metadata, dict) or metadata.get("lifecycleState") != "running":
            continue
        pid = metadata.get("hostPid")
        path = metadata.get("path")
        flavor = metadata.get("flavor")
        if (
            not isinstance(pid, int)
            or not isinstance(path, str)
            or not isinstance(flavor, str)
            or not pid_matches_session(pid, session_id)
        ):
            continue
        result.append(Session(session_id, pid, Path(path), flavor))
    return sorted(result, key=lambda item: item.session_id)


def public_record(session: Session) -> dict[str, object]:
    return {
        "session_id": session.session_id,
        "host_pid": session.host_pid,
        "path": str(session.path),
        "flavor": session.flavor,
    }


def snapshot_payload(sessions: list[Session]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "created_at": int(time.time()),
        "sessions": [public_record(item) for item in sessions],
    }


@contextlib.contextmanager
def state_lock(state: Path):
    state.parent.mkdir(parents=True, exist_ok=True)
    lock = state.with_suffix(".lock")
    with lock.open("a+") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CycleError("another snapshot/restore/cycle operation is running") from exc
        yield


def snapshot(
    home: Path, state: Path, *, apply: bool, already_locked: bool = False
) -> list[Session]:
    if apply and not already_locked:
        with state_lock(state):
            return snapshot(home, state, apply=True, already_locked=True)
    sessions = live_sessions(home)
    print(json.dumps(snapshot_payload(sessions), ensure_ascii=False, indent=2))
    if not apply:
        print("PLAN ONLY — add --apply to replace the snapshot", file=sys.stderr)
        return sessions
    if not sessions and state.is_file():
        try:
            if load_snapshot(state):
                print("no verified live sessions; kept the existing non-empty snapshot", file=sys.stderr)
                return sessions
        except CycleError:
            pass
    state.parent.mkdir(parents=True, exist_ok=True)
    temporary = state.with_name(f".{state.name}.tmp-{os.getpid()}")
    try:
        temporary.write_text(
            json.dumps(snapshot_payload(sessions), ensure_ascii=False, indent=2) + "\n"
        )
        os.replace(temporary, state)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return sessions


def load_snapshot(state: Path) -> list[Session]:
    try:
        payload = json.loads(state.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise CycleError(f"cannot read snapshot: {state}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise CycleError("unsupported snapshot schema")
    raw_sessions = payload.get("sessions")
    if not isinstance(raw_sessions, list):
        raise CycleError("snapshot has no sessions list")
    result: list[Session] = []
    for raw in raw_sessions:
        if not isinstance(raw, dict):
            raise CycleError("invalid snapshot session")
        sid, pid, path, flavor = (
            raw.get("session_id"),
            raw.get("host_pid"),
            raw.get("path"),
            raw.get("flavor"),
        )
        if (
            not isinstance(sid, str)
            or not SESSION_ID.fullmatch(sid)
            or not isinstance(pid, int)
            or pid <= 1
            or not isinstance(path, str)
            or not Path(path).is_dir()
            or not isinstance(flavor, str)
        ):
            raise CycleError(f"invalid snapshot coordinate: {sid!r}")
        result.append(Session(sid, pid, Path(path), flavor))
    return result


def validate_cycle_targets(home: Path, saved: list[Session]) -> list[Session]:
    current = {item.session_id: item for item in live_sessions(home)}
    targets: list[Session] = []
    for item in saved:
        observed = current.get(item.session_id)
        if observed is None:
            continue
        if observed.host_pid != item.host_pid:
            raise CycleError(
                f"{item.session_id}: PID changed ({item.host_pid} -> {observed.host_pid})"
            )
        targets.append(observed)
    return targets


def wait_stopped(pid: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not pid_alive(pid):
            return True
        time.sleep(0.2)
    return not pid_alive(pid)


def wait_resumed_sessions(
    home: Path, session_ids: set[str], *, timeout: float
) -> tuple[dict[str, int], list[str]]:
    deadline = time.monotonic() + timeout
    pending = set(session_ids)
    observed: dict[str, int] = {}
    while time.monotonic() < deadline:
        try:
            sessions = live_sessions(home)
        except CycleError:
            sessions = []
        for item in sessions:
            if item.session_id in pending:
                observed[item.session_id] = item.host_pid
                pending.remove(item.session_id)
        if not pending:
            break
        time.sleep(0.25)
    return observed, sorted(pending)


def restore(
    home: Path,
    state: Path,
    *,
    apply: bool,
    timeout: float,
    already_locked: bool = False,
) -> list[dict[str, object]]:
    if apply and not already_locked:
        with state_lock(state):
            return restore(
                home, state, apply=True, timeout=timeout, already_locked=True
            )
    saved = load_snapshot(state)
    running = {item.session_id: item for item in live_sessions(home)}
    plan = [item for item in saved if item.session_id not in running]
    print(json.dumps([public_record(item) for item in plan], ensure_ascii=False, indent=2))
    if not apply:
        print("PLAN ONLY — add --apply to launch happy resume", file=sys.stderr)
        return []
    launchers: dict[str, int] = {}
    errors: list[str] = []
    for item in plan:
        try:
            launcher = subprocess.Popen(
                ["happy", "resume", item.session_id],
                cwd=item.path,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env=resume_environment(home),
            )
        except OSError as exc:
            errors.append(f"{item.session_id}: cannot launch happy resume: {exc}")
            continue
        launchers[item.session_id] = launcher.pid

    observed, missing = wait_resumed_sessions(
        home, set(launchers), timeout=timeout
    )
    results: list[dict[str, object]] = []
    for item in plan:
        new_pid = observed.get(item.session_id)
        if new_pid is None:
            continue
        results.append(
            {
                "session_id": item.session_id,
                "resume_launcher_pid": launchers[item.session_id],
                "new_host_pid": new_pid,
                "status": "resumed",
            }
        )
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if missing:
        errors.append(f"resume was not observed before timeout: {', '.join(missing)}")
    if errors:
        raise CycleError("; ".join(errors))
    return results


def restart_daemon(timeout: float) -> None:
    result = subprocess.run(
        ["systemctl", "--user", "restart", "happy-daemon.service"], check=False
    )
    if result.returncode != 0:
        raise CycleError("happy-daemon.service restart failed")
    deadline = time.monotonic() + timeout
    stable_since: float | None = None
    while time.monotonic() < deadline:
        active = subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet", "happy-daemon.service"],
            check=False,
        ).returncode == 0
        now = time.monotonic()
        if active:
            stable_since = stable_since or now
            if now - stable_since >= 5:
                return
        else:
            stable_since = None
        time.sleep(0.5)
    raise CycleError("happy-daemon.service did not stay active")


def cycle_worker(home: Path, state: Path, timeout: float) -> None:
    with state_lock(state):
        saved = load_snapshot(state)
        targets = validate_cycle_targets(home, saved)
        # Happy documents daemon stop/restart as session-preserving. Prove the
        # daemon is stable before terminating any resumable session roots.
        restart_daemon(timeout)
        for item in targets:
            os.kill(item.host_pid, signal.SIGTERM)
        failures = [
            item.session_id
            for item in targets
            if not wait_stopped(item.host_pid, timeout)
        ]
        errors = [f"SIGTERM timeout: {', '.join(failures)}"] if failures else []
        try:
            # Even when stopping or daemon restart failed, revive every session that did stop.
            # Still-running sessions are detected and skipped by restore().
            restore(home, state, apply=True, timeout=timeout, already_locked=True)
        except CycleError as exc:
            errors.append(str(exc))
        if errors:
            raise CycleError("; ".join(errors))


def launch_cycle_worker(home: Path, state: Path, timeout: float) -> str:
    unit = f"tr-happy-cycle-{int(time.time())}"
    command = [
        "systemd-run",
        "--user",
        "--collect",
        f"--unit={unit}",
        sys.executable,
        str(Path(__file__).resolve()),
        "--home",
        str(home),
        "--state",
        str(state),
        "_cycle-worker",
        "--timeout",
        str(timeout),
    ]
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise CycleError("failed to launch detached cycle worker")
    return unit


def confirm_cycle(count: int, assume_yes: bool) -> None:
    if assume_yes:
        return
    if not sys.stdin.isatty():
        raise CycleError("cycle confirmation requires a terminal or --yes")
    answer = input(f"cycle {count} Happy sessions now? [y/N] ").strip().lower()
    if answer not in {"y", "yes"}:
        raise CycleError("cycle cancelled")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)
    value.add_argument("--state", type=Path, help=argparse.SUPPRESS)
    commands = value.add_subparsers(dest="command", required=True)
    commands.add_parser("inventory", help="show verified live Happy sessions")
    for name in ("snapshot", "restore", "cycle"):
        command = commands.add_parser(name)
        command.add_argument("--apply", action="store_true")
        if name in {"restore", "cycle"}:
            command.add_argument("--timeout", type=float, default=60.0)
        if name == "cycle":
            command.add_argument("--yes", action="store_true")
    worker = commands.add_parser("_cycle-worker", help=argparse.SUPPRESS)
    worker.add_argument("--timeout", type=float, default=60.0)
    return value


def main() -> int:
    args = parser().parse_args()
    state = args.state or default_state(args.home)
    try:
        if args.command == "inventory":
            print(
                json.dumps(
                    [public_record(item) for item in live_sessions(args.home)],
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif args.command == "snapshot":
            snapshot(args.home, state, apply=args.apply)
        elif args.command == "restore":
            restore(args.home, state, apply=args.apply, timeout=args.timeout)
        elif args.command == "cycle":
            saved = snapshot(args.home, state, apply=args.apply)
            validate_cycle_targets(args.home, saved)
            if not saved:
                raise CycleError("no verified live sessions to cycle")
            if not args.apply:
                print("PLAN ONLY — add --apply to run the detached cycle", file=sys.stderr)
            else:
                confirm_cycle(len(saved), args.yes)
                unit = launch_cycle_worker(args.home, state, args.timeout)
                print(f"cycle launched as {unit}; inspect with journalctl --user -u {unit}")
        else:
            cycle_worker(args.home, state, args.timeout)
        return 0
    except CycleError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
