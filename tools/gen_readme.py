#!/usr/bin/env python3
"""Generate a target README from built skill frontmatter."""

import argparse
import re
from pathlib import Path


def frontmatter(text: str) -> dict:
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    values = {}
    for line in match.group(1).splitlines():
        item = re.match(r"([A-Za-z_]+):\s*(.*)", line)
        if item:
            values[item.group(1)] = item.group(2).strip()
    return values


def generate_readme(out_dir: Path, target: str, kit_name: str) -> None:
    rows = []
    skill_dir = out_dir / "skills"
    if skill_dir.is_dir():
        for skill in sorted(path for path in skill_dir.iterdir() if path.is_dir()):
            source = skill / "SKILL.md"
            if source.is_file():
                metadata = frontmatter(source.read_text())
                rows.append(
                    (metadata.get("name", skill.name), metadata.get("description", ""))
                )

    output = [
        f"# {kit_name}",
        "",
        f"개인 kit — **{len(rows)}개 스킬**. `tr-kit-source`에서 `build.sh {target}`로 생성(수동 유지 X).",
        "",
        "## 스킬",
        "",
        "| 스킬 | 발동 |",
        "|---|---|",
    ]
    for name, description in rows:
        output.append(f'| `{name}` | {description.replace("|", "\\|")} |')

    command_dir = out_dir / "commands"
    if command_dir.is_dir():
        commands = sorted(
            str(path.relative_to(command_dir)) for path in command_dir.rglob("*.md")
        )
        if commands:
            output += ["", "## 커맨드", ""]
            output += [f"- `{command}`" for command in commands]

    (out_dir / "README.md").write_text("\n".join(output) + "\n")
    print(f"  [{target}] README.md — 스킬 {len(rows)}개")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--kit-name", required=True)
    args = parser.parse_args()
    generate_readme(args.out, args.target, args.kit_name)


if __name__ == "__main__":
    main()
