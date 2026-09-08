import json
import fcntl
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "skills/project/scripts/local_docs_sync.py"


class LocalDocsSyncTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.remote = self.base / "remote.git"
        self.clone_a = self.base / "host-a"
        self.clone_b = self.base / "host-b"
        self.scanner = self.base / "gitleaks"
        subprocess.run(["git", "init", "--bare", str(self.remote)], check=True, capture_output=True)
        subprocess.run(["git", "clone", str(self.remote), str(self.clone_a)], check=True, capture_output=True)
        for clone in (self.clone_a, self.clone_b):
            if clone == self.clone_b:
                continue
            self.configure(clone)
        (self.clone_a / "_docs/demo/wiki").mkdir(parents=True)
        (self.clone_a / "_docs/demo/sources").mkdir()
        (self.clone_a / "_docs/demo/state").mkdir()
        (self.clone_a / "_docs/demo/README.md").write_text("# Demo\n", encoding="utf-8")
        self.git(self.clone_a, "add", "_docs")
        self.git(self.clone_a, "commit", "-m", "chore: initialize")
        self.git(self.clone_a, "branch", "-M", "main")
        self.git(self.clone_a, "push", "-u", "origin", "main")
        subprocess.run(
            ["git", "--git-dir", str(self.remote), "symbolic-ref", "HEAD", "refs/heads/main"],
            check=True,
        )
        subprocess.run(["git", "clone", str(self.remote), str(self.clone_b)], check=True, capture_output=True)
        self.configure(self.clone_b)
        self.scanner.write_text(
            """#!/bin/sh
docs=""
for arg in "$@"; do
  if [ -d "$arg" ] && [ "$(basename "$arg")" = "_docs" ]; then docs="$arg"; fi
done
if [ -n "$docs" ] && grep -R -q 'LEAK_ME' "$docs"; then
  echo "leak found" >&2
  exit 1
fi
exit 0
""",
            encoding="utf-8",
        )
        self.scanner.chmod(0o755)

    def tearDown(self):
        self.temporary.cleanup()

    def configure(self, clone):
        self.git(clone, "config", "user.name", "Sync Test")
        self.git(clone, "config", "user.email", "sync@example.invalid")

    def git(self, clone, *args, check=True):
        return subprocess.run(
            ["git", "-C", str(clone), *args],
            check=check,
            text=True,
            capture_output=True,
        )

    def run_sync(
        self,
        clone,
        command,
        *,
        git="git",
        env=None,
        quiet=0,
        expected_remote=None,
    ):
        status = self.base / f"{clone.name}-status.json"
        actual_env = os.environ.copy()
        if env:
            actual_env.update(env)
        return subprocess.run(
            [
                sys.executable,
                str(SYNC),
                "--root",
                str(clone),
                "--status-path",
                str(status),
                "--lock-path",
                str(self.base / f"{clone.name}-sync.lock"),
                "--scanner",
                str(self.scanner),
                "--git",
                git,
                "--scope",
                "personal",
                "--expected-remote",
                str(self.remote if expected_remote is None else expected_remote),
                "--quiet-seconds",
                str(quiet),
                command,
            ],
            check=False,
            text=True,
            capture_output=True,
            env=actual_env,
        )

    def status(self, clone):
        return json.loads(
            (self.base / f"{clone.name}-status.json").read_text(encoding="utf-8")
        )

    def test_different_files_rebase_and_publish(self):
        (self.clone_a / "_docs/demo/state/a.md").write_text("from nas\n", encoding="utf-8")
        first = self.run_sync(self.clone_a, "publish")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)

        (self.clone_b / "_docs/demo/state").mkdir(parents=True, exist_ok=True)
        (self.clone_b / "_docs/demo/state/b.md").write_text("from host b\n", encoding="utf-8")
        second = self.run_sync(self.clone_b, "publish")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        pulled = self.run_sync(self.clone_a, "pull")
        self.assertEqual(pulled.returncode, 0, pulled.stdout + pulled.stderr)
        self.assertEqual((self.clone_a / "_docs/demo/state/a.md").read_text(), "from nas\n")
        self.assertEqual((self.clone_a / "_docs/demo/state/b.md").read_text(), "from host b\n")

    def test_same_file_conflict_blocks_and_aborts_rebase(self):
        shared_a = self.clone_a / "_docs/demo/state/shared.md"
        shared_a.write_text("base\n", encoding="utf-8")
        self.assertEqual(self.run_sync(self.clone_a, "publish").returncode, 0)
        self.assertEqual(self.run_sync(self.clone_b, "pull").returncode, 0)

        shared_a.write_text("nas\n", encoding="utf-8")
        shared_b = self.clone_b / "_docs/demo/state/shared.md"
        shared_b.write_text("host b\n", encoding="utf-8")
        self.assertEqual(self.run_sync(self.clone_a, "publish").returncode, 0)
        blocked = self.run_sync(self.clone_b, "publish")

        self.assertNotEqual(blocked.returncode, 0)
        state = self.status(self.clone_b)
        self.assertEqual(state["state"], "blocked")
        self.assertIn("_docs/demo/state/shared.md", state["conflicts"])
        self.assertFalse((self.clone_b / ".git/rebase-merge").exists())
        self.assertFalse((self.clone_b / ".git/rebase-apply").exists())
        self.assertEqual(self.git(self.clone_b, "status", "--porcelain").stdout, "")

    def test_secret_blocks_before_commit(self):
        before = self.git(self.clone_a, "rev-parse", "HEAD").stdout.strip()
        (self.clone_a / "_docs/demo/state/leak.md").write_text("LEAK_ME\n", encoding="utf-8")
        blocked = self.run_sync(self.clone_a, "publish")
        self.assertNotEqual(blocked.returncode, 0)
        self.assertEqual(self.git(self.clone_a, "rev-parse", "HEAD").stdout.strip(), before)
        self.assertEqual(self.status(self.clone_a)["reason"], "secret-scan")

    def test_dirty_pull_is_blocked_without_mutation(self):
        (self.clone_a / "_docs/demo/state/dirty.md").write_text("dirty\n", encoding="utf-8")
        before = self.git(self.clone_a, "rev-parse", "HEAD").stdout.strip()
        blocked = self.run_sync(self.clone_a, "pull")
        self.assertNotEqual(blocked.returncode, 0)
        self.assertEqual(self.git(self.clone_a, "rev-parse", "HEAD").stdout.strip(), before)
        self.assertEqual(self.status(self.clone_a)["reason"], "dirty-pull")

    def test_publish_regenerates_project_indexes(self):
        note = self.clone_a / "_docs/demo/wiki/note.md"
        note.write_text(
            """---
kind: wiki
title: Note
summary: Indexed summary
tags: []
links: []
sources: []
status: seed
created: 2026-09-08
updated: 2026-09-08
---

Body.
""",
            encoding="utf-8",
        )
        published = self.run_sync(self.clone_a, "publish")
        self.assertEqual(published.returncode, 0, published.stdout + published.stderr)
        self.assertIn("Indexed summary", (self.clone_a / "_docs/demo/index.md").read_text())
        self.assertEqual(self.git(self.clone_a, "status", "--porcelain").stdout, "")

    def test_network_outage_is_visible_and_keeps_local_commit(self):
        (self.clone_a / "_docs/demo/state/offline.md").write_text("offline\n", encoding="utf-8")
        missing = self.base / "missing.git"
        self.git(self.clone_a, "remote", "set-url", "origin", str(missing))
        result = self.run_sync(
            self.clone_a,
            "publish",
            expected_remote=missing,
        )
        self.assertNotEqual(result.returncode, 0)
        state = self.status(self.clone_a)
        self.assertEqual(state["state"], "blocked")
        self.assertEqual(state["reason"], "fetch")
        self.assertEqual(self.git(self.clone_a, "status", "--porcelain").stdout, "")
        self.assertIn("local-docs", self.git(self.clone_a, "log", "-1", "--pretty=%s").stdout)

    def test_non_fast_forward_push_retries_once(self):
        racer = self.base / "racer"
        subprocess.run(["git", "clone", str(self.remote), str(racer)], check=True, capture_output=True)
        self.configure(racer)
        wrapper = self.base / "git-race"
        flag = self.base / "raced"
        wrapper.write_text(
            f"""#!/bin/sh
case " $* " in
  *" push "*)
    if [ ! -e "{flag}" ]; then
      touch "{flag}"
      mkdir -p "{racer}/_docs/demo/state"
      printf 'race\\n' > "{racer}/_docs/demo/state/race.md"
      /usr/bin/git -C "{racer}" add _docs
      /usr/bin/git -C "{racer}" commit -m "chore: race"
      /usr/bin/git -C "{racer}" push origin main
    fi
    ;;
esac
exec /usr/bin/git "$@"
""",
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        (self.clone_a / "_docs/demo/state/local.md").write_text("local\n", encoding="utf-8")

        published = self.run_sync(self.clone_a, "publish", git=str(wrapper))

        self.assertEqual(published.returncode, 0, published.stdout + published.stderr)
        self.assertTrue(flag.exists())
        self.assertTrue((self.clone_a / "_docs/demo/state/race.md").is_file())
        self.assertEqual(self.status(self.clone_a)["state"], "success")

    def test_doctor_fails_closed_on_scope_or_remote_mismatch(self):
        mismatch = subprocess.run(
            [
                sys.executable,
                str(SYNC),
                "--root",
                str(self.clone_a),
                "--status-path",
                str(self.base / "doctor-status.json"),
                "--scanner",
                str(self.scanner),
                "--scope",
                "work",
                "--expected-remote",
                str(self.base / "other.git"),
                "doctor",
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(mismatch.returncode, 0)
        state = json.loads((self.base / "doctor-status.json").read_text(encoding="utf-8"))
        self.assertEqual(state["reason"], "scope-remote")

    def test_auto_respects_quiet_window(self):
        before = self.git(self.clone_a, "rev-parse", "HEAD").stdout.strip()
        (self.clone_a / "_docs/demo/state").mkdir(parents=True, exist_ok=True)
        (self.clone_a / "_docs/demo/state/writing.md").write_text(
            "still writing\n", encoding="utf-8"
        )

        result = self.run_sync(self.clone_a, "auto", quiet=60)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.status(self.clone_a)["state"], "skipped")
        self.assertEqual(self.status(self.clone_a)["reason"], "quiet-window")
        self.assertEqual(self.git(self.clone_a, "rev-parse", "HEAD").stdout.strip(), before)

    def test_status_includes_last_result_and_remote_difference(self):
        doctor = self.run_sync(self.clone_a, "doctor")
        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)

        status = self.run_sync(self.clone_a, "status")

        self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
        payload = json.loads(status.stdout)
        self.assertEqual(payload["last_result"]["state"], "success")
        self.assertEqual(payload["ahead"], 0)
        self.assertEqual(payload["behind"], 0)

    def test_doctor_reports_dirty_state_without_committing_it(self):
        (self.clone_a / "_docs/demo/state").mkdir(parents=True, exist_ok=True)
        (self.clone_a / "_docs/demo/state/pending.md").write_text(
            "pending\n", encoding="utf-8"
        )
        before = self.git(self.clone_a, "rev-parse", "HEAD").stdout.strip()

        doctor = self.run_sync(self.clone_a, "doctor")

        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
        state = self.status(self.clone_a)
        self.assertTrue(state["dirty"])
        self.assertIn("?? _docs/demo/state/pending.md", state["dirty_paths"])
        self.assertEqual(self.git(self.clone_a, "rev-parse", "HEAD").stdout.strip(), before)

    def test_mutation_commands_fail_when_host_lock_is_held(self):
        lock_path = self.base / f"{self.clone_a.name}-sync.lock"
        lock_path.touch()
        with lock_path.open("r+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_sync(self.clone_a, "publish")

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.status(self.clone_a)["reason"], "locked")
