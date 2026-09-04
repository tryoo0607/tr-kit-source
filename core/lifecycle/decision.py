#!/usr/bin/env python3
"""Evaluate normalized lifecycle events without knowing the host product."""

from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import PurePath
from typing import Any


class LifecycleError(ValueError):
    pass


CONTROL = {";", "&&", "||", "|", "&", "(", ")"}
REDIRECT_OUT = {">", ">>", ">&", "&>", "&>>"}
DIRECT_MUTATORS = {
    "chmod",
    "chown",
    "cp",
    "install",
    "ln",
    "mkdir",
    "mv",
    "rm",
    "tee",
    "touch",
    "truncate",
}
GIT_MUTATORS = {
    "add",
    "am",
    "apply",
    "cherry-pick",
    "commit",
    "merge",
    "mv",
    "rebase",
    "reset",
    "restore",
    "revert",
    "rm",
    "switch",
}
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*", re.DOTALL)


def _mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LifecycleError(f"{where} must be an object")
    return value


def _integer(value: Any, where: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise LifecycleError(f"{where} must be an integer >= {minimum}")
    return value


def _boolean(value: Any, where: str) -> bool:
    if not isinstance(value, bool):
        raise LifecycleError(f"{where} must be a boolean")
    return value


def _result(action: str, **data: Any) -> dict[str, Any]:
    return {"schema_version": 1, "action": action, "data": data}


def _threshold_reached(
    threshold: dict[str, Any], used: int, window: int, where: str
) -> bool:
    mode = threshold.get("mode")
    value = _integer(threshold.get("value"), f"{where}.value")
    if mode == "ratio":
        if value > 100:
            raise LifecycleError(f"{where}.value must be <= 100 for ratio mode")
        return used * 100 >= window * value
    if mode == "remaining":
        return max(window - used, 0) <= value
    raise LifecycleError(f"{where}.mode must be ratio or remaining")


def _decide_context(event: dict[str, Any]) -> dict[str, Any]:
    context = _mapping(event.get("context"), "context")
    policy = _mapping(event.get("policy"), "policy")
    memory = _mapping(event.get("memory"), "memory")
    used = _integer(context.get("used_tokens"), "context.used_tokens")
    window = _integer(context.get("window_tokens"), "context.window_tokens", minimum=1)
    if used > window:
        used = window
    prepare = _mapping(policy.get("prepare"), "policy.prepare")
    handoff = _mapping(policy.get("handoff"), "policy.handoff")
    prepare_notified = _boolean(
        memory.get("prepare_notified"), "memory.prepare_notified"
    )
    handoff_notified = _boolean(
        memory.get("handoff_notified"), "memory.handoff_notified"
    )
    continuity_key = memory.get("continuity_key")
    project = memory.get("project")
    data = {
        "session_id": event["session"]["id"],
        "used_percent": used * 100 // window,
        "used_tokens": used,
        "window_tokens": window,
        "remaining_tokens": max(window - used, 0),
    }
    if isinstance(continuity_key, str) and continuity_key:
        data["continuity_key"] = continuity_key
    if isinstance(project, str) and project:
        data["project"] = project
    if _threshold_reached(handoff, used, window, "policy.handoff"):
        return _result("none", **data) if handoff_notified else _result(
            "rollover.handoff", **data
        )
    if _threshold_reached(prepare, used, window, "policy.prepare"):
        return _result("none", **data) if prepare_notified else _result(
            "rollover.prepare", **data
        )
    return _result("none", **data)


def _mask_quoted(command: str) -> str:
    """Hide quoted prose before tokenizing; false negatives are safer than false marks."""
    out: list[str] = []
    quote = ""
    escaped = False
    for char in command:
        if escaped:
            out.append(" " if quote else char)
            escaped = False
            continue
        if char == "\\" and quote != "'":
            out.append(" " if quote else char)
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = ""
            out.append("\n" if char == "\n" else " ")
            continue
        if char in {"'", '"'}:
            quote = char
            out.append(" ")
            continue
        out.append(char)
    return "".join(out)


def _segments(command: str) -> tuple[list[list[str]], bool]:
    lexer = shlex.shlex(_mask_quoted(command), posix=True, punctuation_chars=";&|<>")
    lexer.whitespace_split = True
    lexer.commenters = "#"
    segments: list[list[str]] = []
    current: list[str] = []
    has_mutating_redirect = False
    in_double_brackets = False
    try:
        tokens = list(lexer)
    except ValueError:
        return [], False
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "[[":
            in_double_brackets = True
            index += 1
            continue
        if token == "]]" and in_double_brackets:
            in_double_brackets = False
            index += 1
            continue
        if in_double_brackets:
            index += 1
            continue
        if token in REDIRECT_OUT:
            if current and current[-1].isdigit():
                current.pop()
            target = tokens[index + 1] if index + 1 < len(tokens) else ""
            redirects_to_fd = token == ">&" and target.isdigit()
            redirects_to_dev_null = target == "/dev/null"
            if not redirects_to_fd and not redirects_to_dev_null:
                has_mutating_redirect = True
            index += 2 if target else 1
            continue
        if token in CONTROL:
            if current:
                segments.append(current)
                current = []
            index += 1
            continue
        if token == "<":
            index += 1
            continue
        current.append(token)
        index += 1
    if current:
        segments.append(current)
    return segments, has_mutating_redirect


def _command_head(segment: list[str]) -> tuple[str, list[str]]:
    index = 0
    while index < len(segment) and ASSIGNMENT.fullmatch(segment[index]):
        index += 1
    while index < len(segment) and PurePath(segment[index]).name in {
        "command",
        "env",
        "sudo",
    }:
        index += 1
        while index < len(segment) and (
            segment[index].startswith("-") or ASSIGNMENT.fullmatch(segment[index])
        ):
            index += 1
    if index >= len(segment):
        return "", []
    return PurePath(segment[index]).name, segment[index + 1 :]


def command_mutates(command: str) -> bool:
    segments, has_output_redirect = _segments(command)
    if has_output_redirect:
        return True
    for segment in segments:
        head, args = _command_head(segment)
        if head in DIRECT_MUTATORS:
            return True
        if head == "sed" and any(arg == "-i" or arg.startswith("-i") for arg in args):
            return True
        if head == "git":
            index = 0
            while index < len(args):
                arg = args[index]
                if arg in {"-C", "--git-dir", "--work-tree"}:
                    index += 2
                    continue
                if arg.startswith("-"):
                    index += 1
                    continue
                if arg in GIT_MUTATORS:
                    return True
                if arg == "checkout" and "--" in args[index + 1 :]:
                    return True
                break
        if head == "gh" and len(args) >= 2 and args[:2] == ["repo", "create"]:
            return True
    return False


def _decide_tool(event: dict[str, Any]) -> dict[str, Any]:
    tool = _mapping(event.get("tool"), "tool")
    record_path = _boolean(tool.get("record_path"), "tool.record_path")
    if record_path:
        return _result("none")
    kind = tool.get("kind")
    if kind == "file_write":
        return _result("change.mark")
    if kind == "command":
        command = tool.get("command")
        if not isinstance(command, str):
            raise LifecycleError("tool.command must be a string")
        return _result("change.mark" if command_mutates(command) else "none")
    raise LifecycleError("tool.kind must be file_write or command")


def _decide_stop(event: dict[str, Any]) -> dict[str, Any]:
    record = _mapping(event.get("record"), "record")
    changed = _boolean(record.get("changed"), "record.changed")
    fresh = _boolean(record.get("fresh"), "record.fresh")
    count = _integer(record.get("block_count"), "record.block_count")
    maximum = _integer(record.get("max_blocks"), "record.max_blocks", minimum=1)
    if not changed or fresh:
        return _result("record.pass")
    if count < maximum:
        return _result("record.block", next_block_count=count + 1)
    return _result("record.fallback")


def _decide_compact(event: dict[str, Any]) -> dict[str, Any]:
    compact = _mapping(event.get("compact"), "compact")
    changed = _boolean(compact.get("changed"), "compact.changed")
    trigger = compact.get("trigger")
    count = _integer(compact.get("block_count"), "compact.block_count")
    if trigger not in {"auto", "manual"}:
        raise LifecycleError("compact.trigger must be auto or manual")
    if not changed:
        return _result("compact.pass", trigger=trigger)
    if trigger == "manual" or count >= 1:
        return _result("compact.warn", trigger=trigger)
    return _result("compact.block", trigger=trigger, next_block_count=count + 1)


def _decide_session(event: dict[str, Any]) -> dict[str, Any]:
    resume = _mapping(event.get("resume"), "resume")
    origin = resume.get("pending_origin_session")
    available = _boolean(resume.get("state_available"), "resume.state_available")
    current = event["session"]["id"]
    if isinstance(origin, str) and origin and origin != current and available:
        project = resume.get("project")
        return _result(
            "resume.inject",
            **({"project": project} if isinstance(project, str) and project else {}),
        )
    return _result("none")


def decide(event: dict[str, Any]) -> dict[str, Any]:
    event = _mapping(event, "event")
    if event.get("schema_version") != 1:
        raise LifecycleError("unsupported lifecycle schema_version")
    session = _mapping(event.get("session"), "session")
    if not isinstance(session.get("id"), str) or not session["id"]:
        raise LifecycleError("session.id must be a non-empty string")
    kind = event.get("event")
    if kind == "context.observed":
        return _decide_context(event)
    if kind == "tool.completed":
        return _decide_tool(event)
    if kind == "response.stopping":
        return _decide_stop(event)
    if kind == "context.compacting":
        return _decide_compact(event)
    if kind == "session.started":
        return _decide_session(event)
    raise LifecycleError(f"unsupported lifecycle event: {kind}")


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        json.dump(decide(payload), sys.stdout, ensure_ascii=False, separators=(",", ":"))
        sys.stdout.write("\n")
    except (json.JSONDecodeError, LifecycleError) as exc:
        sys.exit(f"FAIL: {exc}")


if __name__ == "__main__":
    main()
