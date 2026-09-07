import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.build import build_target


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core/llm-wiki/scripts"
INDEX = CORE / "llm_wiki_index.py"
LINT = CORE / "llm_wiki_lint.py"
MIGRATE = ROOT / "skills/project/scripts/local_docs_migrate.py"
sys.path.insert(0, str(CORE))

from _llm_wiki_common import work_metadata


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

    def test_work_metadata_ignores_tables_after_the_first_section(self):
        body_tables = (
            """| 단계 | 항목 | 커밋 |
|---|---|---|
| P0 | 준비 | abc123 |""",
            """| 단계 | 결과 |
|---|---|
| P0 | 완료 |""",
            "본문 표 없음",
        )
        for index, body_table in enumerate(body_tables):
            with self.subTest(body_table=body_table):
                path = self.docs / f"state/metadata-{index}.md"
                path.write_text(
                    f"""# 예시 작업

| 단계 | **점검** (검증 중) |
| 갱신 | 2026-09-07 |

## 진행

{body_table}
""",
                    encoding="utf-8",
                )
                metadata = work_metadata(path)
                self.assertEqual(metadata["단계"], "**점검** (검증 중)")
                self.assertNotIn("P0", metadata)

        duplicate = self.docs / "state/duplicate-metadata.md"
        duplicate.write_text(
            """# 중복 메타 작업

| 단계 | **계획** (첫 값) |
| 단계 | **수행** (잘못된 중복) |
| 갱신 | 2026-09-07 |

## 진행
""",
            encoding="utf-8",
        )
        self.assertEqual(work_metadata(duplicate)["단계"], "**계획** (첫 값)")

    def test_project_lint_warns_for_invalid_stage_and_placeholder_values(self):
        self.assertEqual(self.run_tool(MIGRATE, "--apply").returncode, 0)
        state = self.docs / "state/task.md"
        state.write_text(
            state.read_text(encoding="utf-8")
            .replace("**수행** (implementation 완료, rollout pending)", "항목 | 커밋")
            .replace("2026-09-04 12:00", "2026-08-06 14:20"),
            encoding="utf-8",
        )
        self.assertEqual(self.run_tool(INDEX, "--project").returncode, 0)

        linted = self.run_tool(LINT, "--project")

        self.assertEqual(linted.returncode, 0, linted.stdout + linted.stderr)
        self.assertIn("README.md: placeholder stable purpose", linted.stdout)
        self.assertIn("state/task.md: invalid work metadata: 단계", linted.stdout)
        self.assertIn("state/task.md: placeholder work metadata: 갱신", linted.stdout)

        readme = self.docs / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8").replace(
                "| 목적 | 확인 필요 |",
                "| 목적 | 이 기록 공간이 다루는 project 경계 |",
            ),
            encoding="utf-8",
        )
        linted = self.run_tool(LINT, "--project")
        self.assertIn("README.md: placeholder stable purpose", linted.stdout)

    def test_project_lint_accepts_all_six_work_stages(self):
        self.assertEqual(self.run_tool(MIGRATE, "--apply").returncode, 0)
        readme = self.docs / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8").replace(
                "| 목적 | 확인 필요 |", "| 목적 | local-docs v2 검증 |"
            ),
            encoding="utf-8",
        )
        template = (self.docs / "state/task.md").read_text(encoding="utf-8")
        for stage in ("진입", "정의", "계획", "수행", "점검", "마무리"):
            (self.docs / f"state/{stage}.md").write_text(
                template.replace(
                    "**수행** (implementation 완료, rollout pending)", f"**{stage}** (검증)"
                ),
                encoding="utf-8",
            )
        self.assertEqual(self.run_tool(INDEX, "--project").returncode, 0)

        linted = self.run_tool(LINT, "--project")

        self.assertEqual(linted.returncode, 0, linted.stdout + linted.stderr)
        self.assertNotIn("invalid work metadata: 단계", linted.stdout)

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
