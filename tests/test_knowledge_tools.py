import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.build import build_target


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/knowledge"
INDEX = SKILL / "scripts/knowledge_index.py"
LINT = SKILL / "scripts/knowledge_lint.py"


class KnowledgeToolsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name)
        (self.repo / "sources/dev").mkdir(parents=True)
        (self.repo / "wiki/dev").mkdir(parents=True)
        (self.repo / "wiki/inbox").mkdir(parents=True)
        (self.repo / "README.md").write_text("# Knowledge\n", encoding="utf-8")
        (self.repo / "log.md").write_text(
            "# Knowledge Log\n\n## [2026-09-03] ingest | Example\n",
            encoding="utf-8",
        )
        (self.repo / "sources/dev/example.md").write_text(
            """---
kind: source
title: Example Source
source_type: experiment
storage: inline
captured: 2026-09-03
tags: []
---

Immutable observation.
""",
            encoding="utf-8",
        )
        (self.repo / "wiki/dev/first.md").write_text(
            """---
kind: wiki
title: First
summary: First note
tags: [demo]
links: [wiki/dev/second.md]
sources: [sources/dev/example.md]
status: evergreen
created: 2026-09-03
updated: 2026-09-03
---

See the [source](../../sources/dev/example.md).
""",
            encoding="utf-8",
        )
        (self.repo / "wiki/dev/second.md").write_text(
            """---
kind: wiki
title: Second
summary: Second note
tags: []
links: [wiki/dev/first.md]
sources: [sources/dev/example.md]
status: seed
created: 2026-09-03
updated: 2026-09-03
---

Related synthesis.
""",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temporary.cleanup()

    def run_tool(self, script: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(script), *args, str(self.repo)],
            check=False,
            text=True,
            capture_output=True,
        )

    def test_index_generation_is_deterministic_and_checkable(self):
        generated = self.run_tool(INDEX)
        self.assertEqual(generated.returncode, 0, generated.stdout + generated.stderr)
        self.assertIn("UPDATED index.md", generated.stdout)
        self.assertIn("First note", (self.repo / "index.md").read_text())
        self.assertTrue((self.repo / "wiki/dev/index.md").is_file())
        self.assertTrue((self.repo / "wiki/inbox/index.md").is_file())
        self.assertTrue((self.repo / "sources/dev/index.md").is_file())

        checked = self.run_tool(INDEX, "--check")
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        self.assertIn("OK indexes are current", checked.stdout)

        note = self.repo / "wiki/dev/first.md"
        note.write_text(note.read_text().replace("First note", "Changed summary"))
        drift = self.run_tool(INDEX, "--check")
        self.assertEqual(drift.returncode, 1)
        self.assertIn("DRIFT index.md", drift.stdout)

    def test_lint_accepts_valid_repository_after_index_generation(self):
        self.assertEqual(self.run_tool(INDEX).returncode, 0)
        linted = self.run_tool(LINT)
        self.assertEqual(linted.returncode, 0, linted.stdout + linted.stderr)
        self.assertIn("SUMMARY errors=0 warnings=0", linted.stdout)

    def test_lint_reports_broken_source_and_markdown_links(self):
        note = self.repo / "wiki/dev/first.md"
        note.write_text(
            note.read_text()
            .replace("sources/dev/example.md", "sources/dev/missing.md")
            .replace("../../sources/dev/example.md", "../../sources/dev/gone.md"),
            encoding="utf-8",
        )
        self.assertEqual(self.run_tool(INDEX).returncode, 0)
        linted = self.run_tool(LINT)
        self.assertEqual(linted.returncode, 1)
        self.assertIn("missing source record", linted.stdout)
        self.assertIn("broken markdown link", linted.stdout)

    def test_lint_rejects_payload_paths_that_escape_their_storage_root(self):
        source = self.repo / "sources/dev/example.md"
        source.write_text(
            source.read_text()
            .replace("storage: inline", "storage: repository")
            .replace("tags: []", "relative_path: ../../outside.pdf\ntags: []")
            .replace("Immutable observation.", ""),
            encoding="utf-8",
        )
        self.assertEqual(self.run_tool(INDEX).returncode, 0)
        linted = self.run_tool(LINT)
        self.assertEqual(linted.returncode, 1)
        self.assertIn("relative_path must stay local", linted.stdout)

    def test_skill_resources_survive_both_target_builds(self):
        for target in ("claude", "codex"):
            build_target(ROOT, target)
            skill = ROOT / f"out/{target}/plugins/tr-{target}/skills/knowledge"
            self.assertTrue((skill / "references/schema.md").is_file())
            self.assertTrue((skill / "references/operations.md").is_file())
            self.assertTrue((skill / "references/retrieval.md").is_file())
            self.assertTrue((skill / "scripts/knowledge_index.py").is_file())
            self.assertTrue((skill / "scripts/knowledge_lint.py").is_file())


if __name__ == "__main__":
    unittest.main()
