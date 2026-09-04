#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

from _knowledge_common import markdown_targets, records, string_list
from knowledge_index import update_indexes


SOURCE_REQUIRED = {"kind", "title", "source_type", "storage", "captured"}
WIKI_REQUIRED = {"kind", "title", "summary", "tags", "links", "sources", "status", "created", "updated"}
STORAGE = {"inline", "repository", "external", "remote"}
STATUS = {"seed", "evergreen", "archived"}
LOG_HEADER = re.compile(r"^## \[\d{4}-\d{2}-\d{2}\] (capture|ingest|query|lint|migrate) \| .+")


def _safe_relative(raw: object) -> bool:
    path = Path(str(raw))
    return bool(str(raw)) and not path.is_absolute() and ".." not in path.parts


def lint(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for directory in ("sources", "wiki"):
        if not (root / directory).is_dir():
            errors.append(f"missing directory: {directory}/")
    for filename in ("README.md", "log.md"):
        if not (root / filename).is_file():
            errors.append(f"missing file: {filename}")

    source_records = records(root, "sources")
    wiki_records = records(root, "wiki")
    source_paths = {item.relative.as_posix() for item in source_records}
    wiki_paths = {item.relative.as_posix() for item in wiki_records}
    inbound: set[str] = set()

    for item in source_records:
        label = item.relative.as_posix()
        missing = sorted(SOURCE_REQUIRED - item.metadata.keys())
        if missing:
            errors.append(f"{label}: missing fields {', '.join(missing)}")
        if item.metadata.get("kind") != "source":
            errors.append(f"{label}: kind must be source")
        storage = item.metadata.get("storage")
        if storage not in STORAGE:
            errors.append(f"{label}: invalid storage {storage!r}")
        if storage == "inline" and not item.body:
            errors.append(f"{label}: inline source has no body")
        if storage == "repository":
            reference = item.metadata.get("relative_path")
            if not reference:
                errors.append(f"{label}: repository source requires relative_path")
            elif not _safe_relative(reference):
                errors.append(f"{label}: repository relative_path must stay local: {reference}")
            elif not (item.path.parent / str(reference)).exists():
                errors.append(f"{label}: repository payload does not exist: {reference}")
        if storage == "external":
            for key in ("profile_key", "relative_path"):
                if not item.metadata.get(key):
                    errors.append(f"{label}: external source requires {key}")
            reference = item.metadata.get("relative_path")
            if reference and not _safe_relative(reference):
                errors.append(f"{label}: external relative_path must be relative: {reference}")
        if storage == "remote" and not item.metadata.get("origin"):
            errors.append(f"{label}: remote source requires origin")

    for item in wiki_records:
        label = item.relative.as_posix()
        missing = sorted(WIKI_REQUIRED - item.metadata.keys())
        if missing:
            errors.append(f"{label}: missing fields {', '.join(missing)}")
        if item.metadata.get("kind") != "wiki":
            errors.append(f"{label}: kind must be wiki")
        status = item.metadata.get("status")
        if status not in STATUS:
            errors.append(f"{label}: invalid status {status!r}")

        sources = string_list(item.metadata.get("sources"))
        if not sources:
            message = f"{label}: no source records"
            (warnings if status == "seed" else errors).append(message)
        for reference in sources:
            if reference not in source_paths:
                errors.append(f"{label}: missing source record: {reference}")

        for reference in string_list(item.metadata.get("links")):
            inbound.add(reference)
            if reference not in wiki_paths:
                errors.append(f"{label}: missing wiki link: {reference}")

        for reference in markdown_targets(item.body):
            target = (item.path.parent / reference).resolve()
            try:
                target.relative_to(root)
            except ValueError:
                errors.append(f"{label}: link escapes repository: {reference}")
                continue
            if not target.exists():
                errors.append(f"{label}: broken markdown link: {reference}")

    for item in wiki_records:
        label = item.relative.as_posix()
        if "inbox" not in item.relative.parts and label not in inbound:
            warnings.append(f"{label}: orphan wiki note")

    log = root / "log.md"
    if log.is_file():
        for number, line in enumerate(log.read_text(encoding="utf-8").splitlines(), start=1):
            if line.startswith("## ") and not LOG_HEADER.fullmatch(line):
                errors.append(f"log.md:{number}: invalid operation header")

    for path in update_indexes(root, check=True):
        errors.append(f"{path.relative_to(root)}: generated index drift")

    return sorted(set(errors)), sorted(set(warnings))


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint an LLM Wiki knowledge repository.")
    parser.add_argument("repository", type=Path)
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    args = parser.parse_args()
    root = args.repository.resolve()
    if not root.is_dir():
        parser.error(f"repository does not exist: {root}")

    errors, warnings = lint(root)
    for message in errors:
        print(f"ERROR {message}")
    for message in warnings:
        print(f"WARN {message}")
    print(f"SUMMARY errors={len(errors)} warnings={len(warnings)}")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
