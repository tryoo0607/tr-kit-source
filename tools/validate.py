#!/usr/bin/env python3
"""Validate the public toolchain through one local and CI entry point."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLCHAIN_MARKERS = (
    "recipes/_schema.toml",
    "core/contracts/pack-v1.toml",
    "tools/build.py",
)
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REFERENCE_RE = re.compile(r"references/[A-Za-z0-9_./-]+\.(?:md|html|json|toml)")
LEFTOVER_RE = re.compile(r"\{\{(?:slot:|[A-Z])|<!--\s*/?if:")
CODEX_FORBIDDEN_RE = re.compile(r"claude|anthropic|클로드", re.IGNORECASE)
CODEX_ALLOWED_RE = re.compile(
    r"CLAUDE_PLUGIN_ROOT|claude-council|claude-devils|claude-personas|"
    r"artifact-pattern|k-skill은 Claude|CLAUDE\.md 래퍼",
    re.IGNORECASE,
)


class ValidationError(RuntimeError):
    pass


def is_toolchain_root(root: Path) -> bool:
    root = root.resolve()
    return all((root / marker).is_file() for marker in TOOLCHAIN_MARKERS)


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text()
    if not text.startswith("---\n"):
        raise ValidationError(f"missing frontmatter: {path}")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValidationError(f"unterminated frontmatter: {path}")
    values: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    return values


def validate_skill(path: Path) -> None:
    values = _frontmatter(path)
    name = values.get("name", "").strip("'\"")
    description = values.get("description", "").strip("'\"")
    if name != path.parent.name:
        raise ValidationError(
            f"skill name must match directory: {path} name={name!r}"
        )
    if not NAME_RE.fullmatch(name):
        raise ValidationError(f"invalid skill name: {path} name={name!r}")
    if not description:
        raise ValidationError(f"missing skill description: {path}")
    if len(description) > 1024:
        raise ValidationError(f"skill description exceeds 1024 characters: {path}")

    for reference in sorted(set(REFERENCE_RE.findall(path.read_text()))):
        if not (path.parent / reference).is_file():
            raise ValidationError(f"missing reference: {path} -> {reference}")


def _run(argv: list[str], *, cwd: Path = ROOT) -> None:
    try:
        subprocess.run(argv, cwd=cwd, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValidationError(f"command failed: {' '.join(argv)}") from exc


def _text_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            yield path, path.read_text()
        except UnicodeDecodeError:
            continue


def validate_generated(root: Path = ROOT) -> None:
    output = root / "out"
    if not output.is_dir():
        raise ValidationError(f"build output is missing: {output}")

    skill_count = 0
    for path in sorted(output.rglob("SKILL.md")):
        if path.parent.parent.name != "skills":
            continue
        validate_skill(path)
        skill_count += 1
    if skill_count == 0:
        raise ValidationError("generated output contains no skills")

    for path in sorted(output.rglob("*.json")):
        try:
            json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ValidationError(f"invalid JSON: {path}: {exc}") from exc

    for path in sorted(output.rglob("*.sh")):
        _run(["bash", "-n", str(path)], cwd=root)

    for path, file_text in _text_files(output):
        if LEFTOVER_RE.search(file_text):
            raise ValidationError(f"unresolved build marker: {path}")

    codex = output / "codex"
    for path, file_text in _text_files(codex):
        if path.name == "NOTICE":
            continue
        for number, line in enumerate(file_text.splitlines(), start=1):
            if CODEX_FORBIDDEN_RE.search(line) and not CODEX_ALLOWED_RE.search(line):
                raise ValidationError(
                    f"Codex output contains target vocabulary: {path}:{number}"
                )


def validate_hook_profile(root: Path = ROOT) -> None:
    if not is_toolchain_root(root):
        raise ValidationError(f"not a tr-kit toolchain root: {root}")
    _run([str(root / "build.sh")], cwd=root)
    validate_generated(root)


def validate_full_profile(root: Path = ROOT) -> None:
    _run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_*.py",
        ],
        cwd=root,
    )
    validate_hook_profile(root)
    _run(["bash", "tests/hooks/lifecycle-smoke.sh"], cwd=root)
    _run(["bash", "tests/hooks/kit-verify-smoke.sh"], cwd=root)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=("hook", "full"))
    args = parser.parse_args()
    try:
        if args.profile == "hook":
            validate_hook_profile()
        else:
            validate_full_profile()
    except ValidationError as exc:
        raise SystemExit(f"FAIL: {exc}") from exc
    print(f"source validation ({args.profile}): ok")


if __name__ == "__main__":
    main()
