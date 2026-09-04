from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FRONTMATTER_BOUNDARY = "---"
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
TABLE_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|$")


@dataclass(frozen=True)
class Record:
    path: Path
    relative: Path
    metadata: dict[str, Any]
    body: str


def _scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value == "[]":
        return []
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_scalar(item) for item in inner.split(",")]
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value[:1] in {"'", '"'}:
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            pass
    return value


def parse_markdown(path: Path, root: Path) -> Record:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    metadata: dict[str, Any] = {}
    body_start = 0

    if lines and lines[0].strip() == FRONTMATTER_BOUNDARY:
        try:
            boundary = next(
                index
                for index, line in enumerate(lines[1:], start=1)
                if line.strip() == FRONTMATTER_BOUNDARY
            )
        except StopIteration:
            boundary = -1

        if boundary >= 0:
            current_list: str | None = None
            for line in lines[1:boundary]:
                if current_list and re.match(r"^\s+-\s+", line):
                    metadata[current_list].append(_scalar(re.sub(r"^\s+-\s+", "", line)))
                    continue
                current_list = None
                if not line or line.lstrip().startswith("#") or ":" not in line:
                    continue
                key, value = line.split(":", 1)
                if key != key.lstrip():
                    continue
                key = key.strip()
                parsed = _scalar(value)
                metadata[key] = parsed
                if parsed == "":
                    metadata[key] = []
                    current_list = key
            body_start = boundary + 1

    return Record(
        path=path,
        relative=path.relative_to(root),
        metadata=metadata,
        body="\n".join(lines[body_start:]).strip(),
    )


def records(root: Path, section: str) -> list[Record]:
    directory = root / section
    if not directory.is_dir():
        return []
    return [
        parse_markdown(path, root)
        for path in sorted(directory.rglob("*.md"))
        if path.name != "index.md"
    ]


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def markdown_targets(body: str) -> list[str]:
    targets: list[str] = []
    for match in MARKDOWN_LINK.finditer(body):
        target = match.group(1).strip().strip("<>")
        if target.startswith(("http://", "https://", "mailto:", "qmd://", "#")):
            continue
        target = target.split("#", 1)[0]
        if target:
            targets.append(target)
    return targets


def relative_link(from_file: Path, to_file: Path) -> str:
    import os

    return Path(os.path.relpath(to_file, start=from_file.parent)).as_posix()


def table_cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def work_metadata(path: Path) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# ") and "title" not in metadata:
            metadata["title"] = line[2:].strip()
        match = TABLE_ROW.match(line)
        if match:
            key, value = match.groups()
            metadata[key.strip()] = value.strip()
    return metadata
