import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.build import build_target


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core/llm-wiki/scripts"
INDEX = CORE / "llm_wiki_index.py"
LINT = CORE / "llm_wiki_lint.py"
MIGRATE = ROOT / "skills/project/scripts/local_docs_migrate.py"


class LocalDocsV2Test(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.docs = Path(self.temporary.name) / "demo"
        (self.docs / "state").mkdir(parents=True)
        (self.docs / "exec").mkdir()
        (self.docs / "design").mkdir()
        (self.docs / "README.md").write_text(
            """# demo

| 스키마 | v1 |
|---|---|
| 현재 초점 | old task |
| 다음 | stale next |
""",
            encoding="utf-8",
        )
        (self.docs / "state/task.md").write_text(
            """# Active task

| profile | 고치기 |
| 단계 | **수행** (implementation 완료, rollout pending) |
| 갱신 | 2026-09-04 12:00 |

## 요구

- Keep state paths stable.

## 결정

## 미결

## 진행
""",
            encoding="utf-8",
        )
        (self.docs / "exec/done.md").write_text("# Completed work\n", encoding="utf-8")
        (self.docs / "design/legacy.md").write_text("# Legacy design\n", encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def run_tool(self, script: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(script), *args, str(self.docs)],
            check=False,
            text=True,
            capture_output=True,
        )

    def test_migration_is_dry_run_by_default_and_idempotent(self):
        dry = self.run_tool(MIGRATE)
        self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
        self.assertIn("DRY-RUN CREATE sources/", dry.stdout)
        self.assertIn("REVIEW design/", dry.stdout)
        self.assertFalse((self.docs / "sources").exists())
        self.assertTrue((self.docs / "design/legacy.md").is_file())

        applied = self.run_tool(MIGRATE, "--apply")
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertTrue((self.docs / "sources/index.md").is_file())
        self.assertTrue((self.docs / "wiki/index.md").is_file())
        self.assertTrue((self.docs / "state/task.md").is_file())
        self.assertTrue((self.docs / "exec/done.md").is_file())
        self.assertTrue((self.docs / "design/legacy.md").is_file())
        self.assertIn("| 스키마 | v2 |", (self.docs / "README.md").read_text())
        self.assertIn("| 목적 | 확인 필요 |", (self.docs / "README.md").read_text())
        self.assertNotIn("현재 초점", (self.docs / "README.md").read_text())

        before = {path.relative_to(self.docs): path.read_bytes() for path in self.docs.rglob("*") if path.is_file()}
        second = self.run_tool(MIGRATE, "--apply")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        after = {path.relative_to(self.docs): path.read_bytes() for path in self.docs.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_project_index_and_work_reference_lint(self):
        self.assertEqual(self.run_tool(MIGRATE, "--apply").returncode, 0)
        (self.docs / "wiki/architecture").mkdir()
        (self.docs / "wiki/architecture/build.md").write_text(
            """---
kind: wiki
title: Build architecture
summary: Common core and adapters are composed statically.
tags: [architecture]
links: []
sources: []
work_refs: [exec/done.md]
status: seed
created: 2026-09-04
updated: 2026-09-04
---

Project synthesis.
""",
            encoding="utf-8",
        )
        generated = self.run_tool(INDEX, "--project")
        self.assertEqual(generated.returncode, 0, generated.stdout + generated.stderr)
        root_index = (self.docs / "index.md").read_text()
        self.assertIn("## Active Work", root_index)
        self.assertIn("Active task", root_index)
        self.assertIn("Build architecture", root_index)

        linted = self.run_tool(LINT, "--project")
        self.assertEqual(linted.returncode, 0, linted.stdout + linted.stderr)
        self.assertIn("legacy content requires selective Wiki synthesis", linted.stdout)
        self.assertNotIn("missing work reference", linted.stdout)
        self.assertNotIn("completed-looking record", linted.stdout)

    def test_project_resources_survive_both_target_builds(self):
        for target in ("claude", "codex"):
            build_target(ROOT, target)
            plugin = ROOT / f"out/{target}/plugins/tr-{target}"
            self.assertTrue((plugin / "core/llm-wiki/scripts/llm_wiki_index.py").is_file())
            self.assertTrue((plugin / "skills/project/references/local-docs.md").is_file())
            built_migrate = plugin / "skills/project/scripts/local_docs_migrate.py"
            self.assertTrue(built_migrate.is_file())
            dry = self.run_tool(built_migrate)
            self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
            self.assertIn("OK dry-run only", dry.stdout)


if __name__ == "__main__":
    unittest.main()
