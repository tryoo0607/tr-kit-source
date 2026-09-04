#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path


def _core_scripts() -> Path:
    root = Path(__file__).resolve().parents[3]
    candidates = (root / "core/llm-wiki/scripts",)
    for candidate in candidates:
        if (candidate / "llm_wiki_index.py").is_file():
            return candidate
    raise RuntimeError("cannot locate llm-wiki core scripts")


CORE_SCRIPTS = _core_scripts()
sys.path.insert(0, str(CORE_SCRIPTS))
from llm_wiki_index import update_indexes  # noqa: E402


DYNAMIC_README_ROW = re.compile(r"^\|\s*(현재 초점|다음)\s*\|")
SCHEMA_ROW = re.compile(r"^(\|\s*스키마\s*\|\s*)v\d+(\s*\|\s*)$")


def _readme_v2(root: Path) -> str:
    path = root / "README.md"
    if not path.is_file():
        return "\n".join(
            [
                f"# {root.name}",
                "",
                "| 스키마 | v2 |",
                "|---|---|",
                "| 목적 | 확인 필요 |",
                "",
            ]
        )

    lines = path.read_text(encoding="utf-8").splitlines()
    result: list[str] = []
    found_schema = False
    found_purpose = False
    for line in lines:
        if DYNAMIC_README_ROW.match(line):
            continue
        if re.match(r"^\|\s*목적\s*\|", line):
            found_purpose = True
        match = SCHEMA_ROW.match(line)
        if match:
            line = f"{match.group(1)}v2{match.group(2)}"
            found_schema = True
        result.append(line)

    if not found_schema:
        insert_at = 1 if result and result[0].startswith("# ") else 0
        block = ["", "| 스키마 | v2 |", "|---|---|", "| 목적 | 확인 필요 |"]
        result[insert_at:insert_at] = block
    elif not found_purpose:
        schema_at = next(index for index, line in enumerate(result) if SCHEMA_ROW.match(line))
        insert_at = schema_at + 1
        if insert_at < len(result) and re.match(r"^\|\s*-+", result[insert_at]):
            insert_at += 1
        result.insert(insert_at, "| 목적 | 확인 필요 |")
    return "\n".join(result).rstrip() + "\n"


def _log_v2(root: Path) -> str:
    return "\n".join(
        [
            "# Project Knowledge Log",
            "",
            f"## [{date.today().isoformat()}] migrate | local-docs v2",
            "",
            "- Result: Added the LLM Wiki layer while preserving state and exec paths.",
            "",
        ]
    )


def plan(root: Path) -> list[str]:
    actions: list[str] = []
    for directory in ("sources", "wiki"):
        if not (root / directory).is_dir():
            actions.append(f"CREATE {directory}/")
    if (root / "design").exists():
        actions.append("REVIEW design/ for selective synthesis into wiki/design/")
    if (root / "decisions.md").exists():
        actions.append("REVIEW decisions.md for synthesis into wiki/decisions.md")
    if not (root / "log.md").is_file():
        actions.append("CREATE log.md")
    expected_readme = _readme_v2(root)
    current_readme = (root / "README.md").read_text(encoding="utf-8") if (root / "README.md").is_file() else None
    if current_readme != expected_readme:
        actions.append("UPDATE README.md")
    if update_indexes(root, check=True, project=True):
        actions.append("GENERATE index.md, wiki/index.md, sources/index.md")
    return actions


def apply(root: Path) -> None:
    (root / "sources").mkdir(parents=True, exist_ok=True)
    (root / "wiki").mkdir(parents=True, exist_ok=True)
    if not (root / "log.md").is_file():
        (root / "log.md").write_text(_log_v2(root), encoding="utf-8")
    readme = root / "README.md"
    expected_readme = _readme_v2(root)
    if not readme.is_file() or readme.read_text(encoding="utf-8") != expected_readme:
        readme.write_text(expected_readme, encoding="utf-8")
    update_indexes(root, check=False, project=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate one local-docs project from v1 to hybrid v2.")
    parser.add_argument("project_docs", type=Path)
    parser.add_argument("--apply", action="store_true", help="Apply the plan. Default is dry-run.")
    args = parser.parse_args()
    root = args.project_docs.resolve()
    if not root.is_dir():
        parser.error(f"project docs do not exist: {root}")

    actions = plan(root)
    for action in actions:
        print(f"{'APPLY' if args.apply else 'DRY-RUN'} {action}")
    if args.apply:
        apply(root)
        print("OK local-docs v2 applied")
    else:
        print("OK dry-run only; no files changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
