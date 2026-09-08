#!/usr/bin/env python3
"""Fail-closed Git synchronization for a shared local-docs collection."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Mapping, Sequence


def _plugin_root() -> Path:
    return Path(__file__).resolve().parents[3]


CORE_SCRIPTS = _plugin_root() / "core/llm-wiki/scripts"
sys.path.insert(0, str(CORE_SCRIPTS))
from llm_wiki_index import update_indexes  # noqa: E402


class SyncBlocked(RuntimeError):
    def __init__(self, reason: str, message: str, conflicts: Sequence[str] = ()):
        super().__init__(message)
        self.reason = reason
        self.conflicts = list(conflicts)


@dataclass(frozen=True)
class Settings:
    root: Path
    docs: Path
    remote: str
    branch: str
    expected_remote: str
    scope: str
    scanner: str
    git: str
    quiet_seconds: int
    status_path: Path
    lock_path: Path


class Sync:
    def __init__(self, settings: Settings, environ: Mapping[str, str] | None = None):
        self.settings = settings
        self.environ = dict(os.environ if environ is None else environ)

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                [self.settings.git, "-C", str(self.settings.root), *args],
                check=False,
                text=True,
                capture_output=True,
                env=self.environ,
            )
        except OSError as exc:
            raise SyncBlocked("git", "Git executable is unavailable") from exc
        if check and result.returncode:
            raise subprocess.CalledProcessError(
                result.returncode,
                result.args,
                output=result.stdout,
                stderr=result.stderr,
            )
        return result

    def _git_optional(self, *args: str) -> str | None:
        result = self.git(*args, check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    def _status_snapshot(
        self,
        state: str,
        command: str,
        reason: str,
        message: str,
        conflicts: Sequence[str] = (),
    ) -> dict[str, object]:
        local_head = self._git_optional("rev-parse", "HEAD")
        remote_ref = f"refs/remotes/{self.settings.remote}/{self.settings.branch}"
        remote_head = self._git_optional("rev-parse", "--verify", remote_ref)
        ahead = None
        behind = None
        if local_head and remote_head:
            counts = self._git_optional(
                "rev-list", "--left-right", "--count", f"{local_head}...{remote_head}"
            )
            if counts:
                left, right = counts.split()
                ahead, behind = int(left), int(right)
        dirty_paths = self.dirty(check=False)
        return {
            "schema_version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "host": socket.gethostname(),
            "state": state,
            "command": command,
            "reason": reason,
            "message": message,
            "root": str(self.settings.root),
            "remote": self.settings.remote,
            "branch": self.settings.branch,
            "scope": self.settings.scope,
            "local_head": local_head,
            "remote_head": remote_head,
            "ahead": ahead,
            "behind": behind,
            "conflicts": sorted(set(conflicts)),
            "dirty": bool(dirty_paths),
            "dirty_paths": dirty_paths,
        }

    def record(
        self,
        state: str,
        command: str,
        reason: str,
        message: str,
        conflicts: Sequence[str] = (),
    ) -> dict[str, object]:
        payload = self._status_snapshot(state, command, reason, message, conflicts)
        path = self.settings.status_path
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return payload

    def validate(self) -> None:
        root = self.settings.root
        if not root.is_dir() or not self.settings.docs.is_dir():
            raise SyncBlocked("root", "root or _docs directory is missing")
        inside = self.git("rev-parse", "--is-inside-work-tree", check=False)
        if inside.returncode or inside.stdout.strip() != "true":
            raise SyncBlocked("root", "root is not a Git worktree")
        top = self.git("rev-parse", "--show-toplevel").stdout.strip()
        if Path(top).resolve() != root:
            raise SyncBlocked("root", "configured root is not the Git top level")
        actual_branch = self.git("branch", "--show-current").stdout.strip()
        if actual_branch != self.settings.branch:
            raise SyncBlocked("branch", "current branch does not match configured branch")
        remote = self.git("remote", "get-url", self.settings.remote, check=False)
        if remote.returncode:
            raise SyncBlocked("remote", "configured Git remote is missing")
        if not self.settings.expected_remote:
            raise SyncBlocked("scope-remote", "expected remote is required")
        if remote.stdout.strip() != self.settings.expected_remote:
            raise SyncBlocked("scope-remote", "Git remote does not match the allowed remote")
        if self.settings.scope not in {"personal", "work"}:
            raise SyncBlocked("scope-remote", "scope must be explicitly personal or work")
        scanner_path = shutil.which(self.settings.scanner)
        if not scanner_path or not os.access(scanner_path, os.X_OK):
            raise SyncBlocked("scanner", "gitleaks scanner is unavailable")
        conflicts = self._conflicts()
        if conflicts:
            raise SyncBlocked("git-state", "unmerged paths require manual resolution", conflicts)
        git_dir = Path(self.git("rev-parse", "--git-dir").stdout.strip())
        if not git_dir.is_absolute():
            git_dir = root / git_dir
        if any((git_dir / marker).exists() for marker in ("rebase-merge", "rebase-apply", "MERGE_HEAD")):
            raise SyncBlocked("git-state", "an unfinished Git operation requires manual resolution")

    def scan(self) -> None:
        command = [
            self.settings.scanner,
            "dir",
            str(self.settings.docs),
            "--no-banner",
            "--redact",
        ]
        config = self.settings.docs / ".gitleaks.toml"
        if config.is_file():
            command.extend(["--config", str(config)])
        try:
            result = subprocess.run(
                command,
                check=False,
                text=True,
                capture_output=True,
                env=self.environ,
            )
        except OSError as exc:
            raise SyncBlocked("scanner", "gitleaks scanner is unavailable") from exc
        if result.returncode:
            raise SyncBlocked("secret-scan", "gitleaks rejected the local-docs tree")

    def dirty(self, check: bool = True) -> list[str]:
        result = self.git(
            "status", "--porcelain=v1", "--untracked-files=all", check=check
        )
        if result.returncode:
            return []
        output = result.stdout
        return [line for line in output.splitlines() if line]

    def _stage_docs(self) -> None:
        self.git("add", "-A", "--", "_docs")

    def _staged(self) -> bool:
        return self.git("diff", "--cached", "--quiet", check=False).returncode == 1

    def _commit(self, suffix: str = "") -> bool:
        self._stage_docs()
        if not self._staged():
            return False
        host = socket.gethostname().split(".", 1)[0]
        subject = f"chore(local-docs): sync from {host}{suffix}"
        self.git("commit", "-m", subject)
        return True

    def _generate_indexes(self) -> list[Path]:
        changed: list[Path] = []
        for project in sorted(self.settings.docs.iterdir()):
            if not project.is_dir():
                continue
            if not (project / "wiki").is_dir() or not (project / "sources").is_dir():
                continue
            changed.extend(update_indexes(project, check=False, project=True))
        return changed

    def _index_drift(self) -> list[Path]:
        drift: list[Path] = []
        for project in sorted(self.settings.docs.iterdir()):
            if not project.is_dir():
                continue
            if not (project / "wiki").is_dir() or not (project / "sources").is_dir():
                continue
            drift.extend(update_indexes(project, check=True, project=True))
        return drift

    def _conflicts(self) -> list[str]:
        output = self.git("diff", "--name-only", "--diff-filter=U", check=False).stdout
        return [line for line in output.splitlines() if line]

    def _rebase(self) -> None:
        target = f"{self.settings.remote}/{self.settings.branch}"
        result = self.git("rebase", target, check=False)
        if result.returncode:
            conflicts = self._conflicts()
            self.git("rebase", "--abort", check=False)
            raise SyncBlocked("conflict", "rebase conflict requires manual resolution", conflicts)

    def _fetch(self) -> None:
        result = self.git(
            "fetch", "--prune", self.settings.remote, self.settings.branch, check=False
        )
        if result.returncode:
            raise SyncBlocked("fetch", "Git fetch failed")

    def _refresh_after_rebase(self) -> None:
        self._generate_indexes()
        self.scan()
        self._commit(" (index)")

    def doctor(self) -> None:
        self.validate()
        self.scan()

    def pull(self) -> None:
        self.validate()
        if self.dirty():
            raise SyncBlocked("dirty-pull", "pull requires a clean worktree")
        self._fetch()
        target = f"{self.settings.remote}/{self.settings.branch}"
        ancestor = self.git("merge-base", "--is-ancestor", "HEAD", target, check=False)
        if ancestor.returncode == 0:
            self.git("merge", "--ff-only", target)
        else:
            self._rebase()
        if self._index_drift():
            raise SyncBlocked("index-drift", "pulled indexes are not deterministic")

    def publish(self) -> None:
        self.validate()
        self.scan()
        self._generate_indexes()
        self.scan()
        self._commit()
        self._fetch()
        self._rebase()
        self._refresh_after_rebase()
        push = self.git(
            "push", self.settings.remote, f"HEAD:{self.settings.branch}", check=False
        )
        if push.returncode == 0:
            return
        self._fetch()
        self._rebase()
        self._refresh_after_rebase()
        retry = self.git(
            "push", self.settings.remote, f"HEAD:{self.settings.branch}", check=False
        )
        if retry.returncode:
            raise SyncBlocked("push", "normal push failed after one retry")

    def quiet(self) -> bool:
        cutoff = time.time() - self.settings.quiet_seconds
        return all(
            not path.is_file() or path.stat().st_mtime <= cutoff
            for path in self.settings.docs.rglob("*")
        )

    def auto(self) -> str:
        self.validate()
        if not self.quiet():
            return "quiet-window"
        self.publish()
        return "published"

    def live_status(self) -> dict[str, object]:
        try:
            previous = json.loads(self.settings.status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}
        current = self._status_snapshot(
            str(previous.get("state", "unknown")),
            "status",
            str(previous.get("reason", "none")),
            str(previous.get("message", "no previous sync result")),
            previous.get("conflicts", []),
        )
        current["last_result"] = previous
        return current


@contextmanager
def locked(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SyncBlocked("locked", "another local-docs sync is running") from exc
        yield


def _profile_value(key: str) -> str | None:
    profile_scripts = _plugin_root() / "profile"
    if not profile_scripts.is_dir():
        profile_scripts = _plugin_root() / "core/profile"
    sys.path.insert(0, str(profile_scripts))
    try:
        import resolver

        return str(resolver.load_profile().get(key))
    except (ImportError, OSError, RuntimeError):
        return None


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    projects = (
        os.environ.get("TR_LOCAL_DOCS_ROOT")
        or _profile_value("public.paths.projects")
        or str(Path.home() / "projects")
    )
    scope = (
        os.environ.get("TR_LOCAL_DOCS_SCOPE")
        or _profile_value("public.scope.default")
        or "unknown"
    )
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    parser = argparse.ArgumentParser(prog="local-docs-sync")
    parser.add_argument("--root", type=Path, default=projects)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default="main")
    parser.add_argument(
        "--expected-remote",
        default=os.environ.get("LOCAL_DOCS_SYNC_EXPECTED_REMOTE", ""),
    )
    parser.add_argument("--scope", choices=("personal", "work", "unknown"), default=scope)
    parser.add_argument("--scanner", default="gitleaks")
    parser.add_argument("--git", default="git")
    parser.add_argument("--quiet-seconds", type=int, default=60)
    parser.add_argument(
        "--status-path",
        type=Path,
        default=state_home / "local-docs-sync/status.json",
    )
    parser.add_argument(
        "--lock-path",
        type=Path,
        default=state_home / "local-docs-sync/sync.lock",
    )
    parser.add_argument("command", choices=("doctor", "pull", "publish", "status", "auto"))
    return parser.parse_args(argv)


def settings_from(args: argparse.Namespace) -> Settings:
    root = args.root.expanduser().resolve()
    if args.quiet_seconds < 0:
        raise SyncBlocked("arguments", "quiet seconds must not be negative")
    return Settings(
        root=root,
        docs=root / "_docs",
        remote=args.remote,
        branch=args.branch,
        expected_remote=args.expected_remote,
        scope=args.scope,
        scanner=args.scanner,
        git=args.git,
        quiet_seconds=args.quiet_seconds,
        status_path=args.status_path.expanduser().resolve(),
        lock_path=args.lock_path.expanduser().resolve(),
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        settings = settings_from(args)
        sync = Sync(settings)
        if args.command == "status":
            print(json.dumps(sync.live_status(), ensure_ascii=False, indent=2, sort_keys=True))
            return 0

        def execute() -> tuple[str, str]:
            if args.command == "doctor":
                sync.doctor()
                return "healthy", "doctor checks passed"
            if args.command == "pull":
                sync.pull()
                return "pulled", "pull completed"
            if args.command == "publish":
                sync.publish()
                return "published", "publish completed"
            result = sync.auto()
            message = (
                "auto skipped for quiet window"
                if result == "quiet-window"
                else "auto publish completed"
            )
            return result, message

        if args.command in {"pull", "publish", "auto"}:
            with locked(settings.lock_path):
                reason, message = execute()
        else:
            reason, message = execute()
        state = "skipped" if reason == "quiet-window" else "success"
        payload = sync.record(state, args.command, reason, message)
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except SyncBlocked as exc:
        if "sync" not in locals():
            print(f"BLOCKED {exc.reason}: {exc}", file=sys.stderr)
            return 2
        payload = sync.record("blocked", args.command, exc.reason, str(exc), exc.conflicts)
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 2
    except subprocess.CalledProcessError:
        payload = sync.record("failed", args.command, "git", "unexpected Git failure")
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
