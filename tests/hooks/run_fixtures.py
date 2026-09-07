#!/usr/bin/env python3
"""Run hook fixtures against every generated target that ships the hook.

Fixture contract:
  fixtures/<hook>/<case>.json              hook stdin
  fixtures/<hook>/<case>.expect            shared expectations
  fixtures/<hook>/<case>.<target>.expect   optional target override
  fixtures/<hook>/<case>.setup             optional sandbox setup script
  fixtures/<hook>/<case>.targets           optional whitespace/comma target allowlist

The runner replaces target-aware placeholders in fixture content. A missing
hook means the case does not apply to that target; it is skipped rather than
treated as a failure.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
TARGETS = {
    "claude": ROOT / "out/claude/plugins/tr-claude",
    "codex": ROOT / "out/codex/plugins/tr-codex",
}
TARGET_VALUES = {
    "claude": {
        "STATE_DIR": "claude-remote",
        "KIT_REPO": "tr-claude",
        "TRANSCRIPT_ROOT": ".claude/projects/fixture",
    },
    "codex": {
        "STATE_DIR": "codex-remote",
        "KIT_REPO": "tr-codex",
        "TRANSCRIPT_ROOT": ".codex/sessions/2026/09/04",
    },
}


def render(text: str, *, sandbox: Path, plugin: Path, target: str) -> str:
    values = {
        "SB": str(sandbox),
        "PLUGIN": str(plugin),
        "TARGET": target,
        **TARGET_VALUES[target],
    }
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    unresolved = sorted(set(re.findall(r"\{\{([A-Z][A-Z0-9_]*)\}\}", text)))
    if unresolved:
        raise ValueError(f"unresolved fixture placeholders: {unresolved}")
    return text


def selected_for_target(case_path: Path, target: str) -> bool:
    path = case_path.with_suffix(".targets")
    if not path.exists():
        return True
    allowed = {item for item in re.split(r"[\s,]+", path.read_text()) if item}
    unknown = allowed - TARGETS.keys()
    if unknown:
        raise ValueError(f"unknown targets in {path}: {sorted(unknown)}")
    return target in allowed


def expectation_path(case_path: Path, target: str) -> Path:
    override = case_path.with_name(f"{case_path.stem}.{target}.expect")
    return override if override.exists() else case_path.with_suffix(".expect")


def prepare_sandbox(sandbox: Path, plugin: Path, target: str, setup: Path) -> tuple[Path, dict[str, str]]:
    for relative in ("tmp", "state", "projects/_docs", ".claude", "bin"):
        (sandbox / relative).mkdir(parents=True, exist_ok=True)
    tmux = sandbox / "bin/tmux"
    tmux.write_text("#!/bin/sh\nexit 1\n")
    tmux.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(sandbox),
            "TMPDIR": str(sandbox / "tmp"),
            "XDG_STATE_HOME": str(sandbox / "state"),
            "CLAUDE_PLUGIN_ROOT": str(plugin),
            "TR_KIT_TARGET": target,
            "SB": str(sandbox),
            "PLUGIN": str(plugin),
            "TARGET": target,
            "PATH": f"{sandbox / 'bin'}:{env.get('PATH', '')}",
        }
    )
    env.pop("TMUX", None)

    if setup.exists():
        setup_text = render(setup.read_text(), sandbox=sandbox, plugin=plugin, target=target)
        result = subprocess.run(
            ["bash"],
            input=setup_text,
            text=True,
            cwd=sandbox,
            env=env,
            capture_output=True,
        )
        if result.returncode:
            detail = (result.stdout + result.stderr).strip()
            raise RuntimeError(f"setup exit {result.returncode}: {detail}")

    cwd_file = sandbox / ".cwd"
    cwd = Path(cwd_file.read_text().strip()) if cwd_file.exists() else sandbox
    return cwd, env


def check_expectations(expect: Path, output: str, returncode: int, sandbox: Path) -> list[str]:
    errors: list[str] = []
    for raw_line in expect.read_text().splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line:
            continue
        kind, separator, argument = line.partition(" ")
        if not separator:
            errors.append(f"invalid directive: {line}")
            continue
        if kind == "exit":
            if returncode != int(argument):
                errors.append(f"exit {returncode} != {argument}")
        elif kind == "match":
            if re.search(argument, output) is None:
                errors.append(f"missing: {argument}")
        elif kind == "nomatch":
            if re.search(argument, output) is not None:
                errors.append(f"unexpected: {argument}")
        elif kind == "file":
            if not (sandbox / argument).exists():
                errors.append(f"missing file: {argument}")
        elif kind == "nofile":
            if (sandbox / argument).exists():
                errors.append(f"unexpected file: {argument}")
        elif kind == "maxbytes":
            size = len(output.encode())
            if size > int(argument):
                errors.append(f"output {size}B > {argument}B")
        else:
            errors.append(f"unknown directive: {kind}")
    return errors


def run_case(hook: str, case_path: Path, target: str, plugin: Path) -> tuple[list[str], str]:
    with tempfile.TemporaryDirectory(prefix="tr-hook-fixture-") as temp:
        sandbox = Path(temp)
        setup = case_path.with_suffix(".setup")
        try:
            cwd, env = prepare_sandbox(sandbox, plugin, target, setup)
        except RuntimeError as exc:
            return [str(exc)], ""

        payload = render(case_path.read_text(), sandbox=sandbox, plugin=plugin, target=target)
        result = subprocess.run(
            ["bash", str(plugin / f"hooks/{hook}.sh")],
            input=payload,
            text=True,
            cwd=cwd,
            env=env,
            capture_output=True,
        )
        output = result.stdout + result.stderr
        expect = expectation_path(case_path, target)
        if not expect.exists():
            return [f"missing expectation: {expect.name}"], output
        rendered_expect = render(expect.read_text(), sandbox=sandbox, plugin=plugin, target=target)
        rendered_path = sandbox / ".expect"
        rendered_path.write_text(rendered_expect)
        return check_expectations(rendered_path, output, result.returncode, sandbox), output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", action="append", choices=sorted(TARGETS))
    parser.add_argument("--hook", action="append", help="limit execution to named hooks")
    parser.add_argument("--build", action="store_true", help="build generated targets first")
    parser.add_argument("--verbose", action="store_true", help="print every passing case")
    args = parser.parse_args()

    targets = args.target or list(TARGETS)
    hooks = set(args.hook or [])
    if args.build:
        subprocess.run([str(ROOT / "build.sh")], cwd=ROOT, check=True)

    passed = failed = skipped = 0
    for hook_dir in sorted(path for path in FIXTURES.iterdir() if path.is_dir()):
        hook = hook_dir.name
        if hooks and hook not in hooks:
            continue
        if args.verbose:
            print(f"-- {hook}")
        for case_path in sorted(hook_dir.glob("*.json")):
            for target in targets:
                plugin = TARGETS[target]
                script = plugin / f"hooks/{hook}.sh"
                if not script.exists() or not selected_for_target(case_path, target):
                    skipped += 1
                    continue
                errors, output = run_case(hook, case_path, target, plugin)
                label = f"{target}:{hook}/{case_path.stem}"
                if not errors:
                    if args.verbose:
                        print(f"  PASS {label}")
                    passed += 1
                    continue
                print(f"  FAIL {label}")
                for error in errors:
                    print(f"       {error}")
                if output.strip():
                    print("       output:")
                    for line in output.rstrip().splitlines():
                        print(f"         {line}")
                failed += 1

    print(f"hook fixtures: {passed} passed, {failed} failed, {skipped} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
