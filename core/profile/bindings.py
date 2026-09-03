#!/usr/bin/env python3
"""Contract-driven setup for non-secret runtime profile bindings."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from string import Template
from typing import Iterable, Mapping, Sequence

try:
    from . import resolver
except ImportError:  # direct script/import from a generated plugin
    import resolver  # type: ignore


Scalar = str | int | float | bool
CONTRACT_ROOTS = {"schema_version", "keys"}
KEY_FIELDS = {
    "name",
    "type",
    "required_by",
    "default",
    "values",
    "must_exist",
    "must_be_git_worktree",
    "required_files",
    "required_directories",
}
DISCOVERY_ROOTS = {"schema_version", "bindings"}
DISCOVERY_FIELDS = {"key", "candidates"}


class BindingError(RuntimeError):
    pass


@dataclass(frozen=True)
class BindingStatus:
    key: str
    state: str
    value: Scalar | None = None
    detail: str = ""


def read_toml(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise BindingError(f"cannot read TOML {path}: {exc}") from exc


def _reject_unknown(data: Mapping[str, object], allowed: set[str], where: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise BindingError(f"unknown keys in {where}: {sorted(unknown)}")


def load_contracts(paths: Sequence[Path]) -> dict[str, dict]:
    contracts: dict[str, dict] = {}
    for path in paths:
        data = read_toml(path)
        _reject_unknown(data, CONTRACT_ROOTS, str(path))
        if data.get("schema_version") != 1 or not isinstance(data.get("keys"), list):
            raise BindingError(f"unsupported binding contract: {path}")
        for entry in data["keys"]:
            if not isinstance(entry, dict):
                raise BindingError(f"binding key must be a table: {path}")
            _reject_unknown(entry, KEY_FIELDS, f"binding key in {path}")
            name = entry.get("name")
            kind = entry.get("type")
            required_by = entry.get("required_by")
            if (
                not isinstance(name, str)
                or not name
                or name in contracts
                or kind not in {"path", "relative_path", "boolean", "enum"}
                or not isinstance(required_by, list)
                or not all(isinstance(item, str) and item for item in required_by)
            ):
                raise BindingError(f"invalid or duplicate binding key in {path}: {name}")
            if kind == "path":
                for field in ("must_exist", "must_be_git_worktree"):
                    if not isinstance(entry.get(field), bool):
                        raise BindingError(f"{field} must be boolean: {name}")
                for field in ("required_files", "required_directories"):
                    values = entry.get(field)
                    if not isinstance(values, list) or not all(
                        isinstance(item, str) and item for item in values
                    ):
                        raise BindingError(f"{field} must be a string list: {name}")
            if kind == "enum":
                values = entry.get("values")
                if not isinstance(values, list) or not values or not all(
                    isinstance(item, str) and item for item in values
                ):
                    raise BindingError(f"enum values must be strings: {name}")
            if "default" in entry:
                validate_value(entry["default"], entry)
            contracts[name] = entry
    return contracts


def load_discovery(paths: Sequence[Path]) -> dict[str, list[str]]:
    discovery: dict[str, list[str]] = {}
    for path in paths:
        data = read_toml(path)
        _reject_unknown(data, DISCOVERY_ROOTS, str(path))
        if data.get("schema_version") != 1 or not isinstance(data.get("bindings"), list):
            raise BindingError(f"unsupported discovery contract: {path}")
        for entry in data["bindings"]:
            if not isinstance(entry, dict):
                raise BindingError(f"discovery binding must be a table: {path}")
            _reject_unknown(entry, DISCOVERY_FIELDS, f"discovery binding in {path}")
            key = entry.get("key")
            candidates = entry.get("candidates")
            if (
                not isinstance(key, str)
                or not key
                or key in discovery
                or not isinstance(candidates, list)
                or not candidates
                or not all(isinstance(item, str) and item for item in candidates)
            ):
                raise BindingError(f"invalid or duplicate discovery binding in {path}")
            discovery[key] = candidates
    return discovery


def validate_value(value: object, contract: Mapping[str, object]) -> Scalar:
    kind = contract["type"]
    name = str(contract["name"])
    if kind == "boolean":
        if not isinstance(value, bool):
            raise BindingError(f"binding value must be boolean: {name}")
        return value
    if kind == "enum":
        if not isinstance(value, str) or value not in contract["values"]:
            raise BindingError(f"binding value is outside enum: {name}")
        return value
    if kind == "relative_path":
        if not isinstance(value, str) or not value:
            raise BindingError(f"binding value must be a non-empty relative path: {name}")
        pure = PurePosixPath(value)
        if pure.is_absolute() or ".." in pure.parts or value in {".", "./"}:
            raise BindingError(f"unsafe relative path binding: {name}")
        return value
    if not isinstance(value, str) or not value:
        raise BindingError(f"binding path must be a non-empty string: {name}")
    original = Path(value).expanduser()
    if not original.is_absolute():
        raise BindingError(f"binding path must be absolute: {name}")
    try:
        path = original.resolve(strict=bool(contract["must_exist"]))
    except (OSError, RuntimeError) as exc:
        raise BindingError(f"binding path does not exist: {name}={value}") from exc
    if not path.is_dir():
        raise BindingError(f"binding path is not a directory: {name}={path}")
    if contract["must_be_git_worktree"]:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
            text=True,
            capture_output=True,
        )
        if result.returncode != 0 or result.stdout.strip() != "true":
            raise BindingError(f"binding path is not a git worktree: {name}={path}")
    missing_files = [
        item for item in contract["required_files"] if not (path / item).is_file()
    ]
    missing_directories = [
        item for item in contract["required_directories"] if not (path / item).is_dir()
    ]
    if missing_files or missing_directories:
        raise BindingError(
            f"binding path markers are missing: {name} "
            f"files={missing_files} directories={missing_directories}"
        )
    return str(path)


def _expand_candidate(value: str, home: Path) -> str:
    try:
        return Template(value).substitute({"HOME": str(home)})
    except (KeyError, ValueError) as exc:
        raise BindingError(f"unsupported discovery variable: {value}") from exc


def discover(key: str, contract: Mapping[str, object], candidates: Sequence[str], home: Path) -> Scalar:
    valid: list[Scalar] = []
    for candidate in candidates:
        rendered = _expand_candidate(candidate, home)
        if contract["type"] == "path" and not Path(rendered).expanduser().exists():
            continue
        try:
            valid.append(validate_value(rendered, contract))
        except BindingError:
            continue
    unique = list(dict.fromkeys(valid))
    if not unique:
        raise BindingError(f"no valid discovery candidate for {key}")
    if len(unique) > 1:
        raise BindingError(
            f"multiple discovery candidates for {key}: "
            + ", ".join(str(value) for value in unique)
        )
    return unique[0]


def _parse_set(values: Sequence[str], contracts: Mapping[str, dict]) -> dict[str, Scalar]:
    parsed: dict[str, Scalar] = {}
    for item in values:
        if "=" not in item:
            raise BindingError(f"--set must be KEY=VALUE: {item}")
        key, raw = item.split("=", 1)
        if key not in contracts:
            raise BindingError(f"unknown binding key: {key}")
        kind = contracts[key]["type"]
        value: Scalar
        if kind == "boolean":
            if raw not in {"true", "false"}:
                raise BindingError(f"boolean --set must be true or false: {key}")
            value = raw == "true"
        else:
            value = raw
        parsed[key] = validate_value(value, contracts[key])
    return parsed


def evaluate(
    contracts: Mapping[str, dict],
    discovery: Mapping[str, list[str]],
    profile: resolver.Profile,
    explicit: Mapping[str, Scalar],
    selected: set[str] | None,
    home: Path,
) -> list[BindingStatus]:
    statuses: list[BindingStatus] = []
    for key, contract in sorted(contracts.items()):
        if selected is not None and key not in selected:
            continue
        if key in explicit:
            statuses.append(BindingStatus(key, "explicit", explicit[key]))
            continue
        if key in profile.values:
            try:
                value = validate_value(profile.values[key], contract)
                statuses.append(
                    BindingStatus(key, "configured", value, str(profile.source(key)))
                )
            except BindingError as exc:
                statuses.append(BindingStatus(key, "invalid", detail=str(exc)))
            continue
        if key in discovery:
            try:
                value = discover(key, contract, discovery[key], home)
                statuses.append(BindingStatus(key, "discovered", value))
            except BindingError as exc:
                state = "ambiguous" if str(exc).startswith("multiple") else "missing"
                statuses.append(BindingStatus(key, state, detail=str(exc)))
            continue
        if "default" in contract:
            statuses.append(BindingStatus(key, "defaulted", contract["default"]))
        else:
            statuses.append(BindingStatus(key, "missing"))
    return statuses


def _flatten(prefix: tuple[str, ...], value: object) -> dict[str, Scalar]:
    if isinstance(value, dict):
        result: dict[str, Scalar] = {}
        for name, child in value.items():
            result.update(_flatten((*prefix, name), child))
        return result
    if not prefix or not isinstance(value, (str, int, float, bool)):
        raise BindingError("managed profile contains a non-scalar value")
    return {".".join(prefix): value}


def inspect_managed(path: Path, marker: str) -> tuple[str, dict[str, Scalar]]:
    if path.is_symlink():
        raise BindingError(f"managed profile must not be a symlink: {path}")
    if not path.exists():
        return "", {}
    before = path.read_text()
    if not before.startswith(f"{marker}\n"):
        raise BindingError(f"refusing to overwrite unmanaged profile: {path}")
    data = read_toml(path)
    if data.pop("schema_version", None) != 1:
        raise BindingError(f"unsupported managed profile schema: {path}")
    return before, _flatten((), data)


def _toml_value(value: Scalar) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def render_managed(values: Mapping[str, Scalar], marker: str) -> str:
    groups: dict[str, list[tuple[str, Scalar]]] = {}
    for dotted, value in sorted(values.items()):
        if "." not in dotted:
            raise BindingError(f"managed key must be dotted: {dotted}")
        table, name = dotted.rsplit(".", 1)
        groups.setdefault(table, []).append((name, value))
    lines = [marker, "schema_version = 1"]
    for table, entries in groups.items():
        lines.extend(["", f"[{table}]"])
        lines.extend(f"{name} = {_toml_value(value)}" for name, value in entries)
    return "\n".join(lines) + "\n"


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary_path.chmod(0o600)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _show(statuses: Iterable[BindingStatus]) -> None:
    for status in statuses:
        value = "" if status.value is None else f" value={status.value}"
        detail = "" if not status.detail else f" detail={status.detail}"
        print(f"{status.state:10} {status.key}{value}{detail}")


def run_cli(
    *,
    contract_paths: Sequence[Path],
    discovery_paths: Sequence[Path] = (),
    managed_name: str,
    managed_marker: str,
    argv: Sequence[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-dir", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "apply"):
        command = subparsers.add_parser(name)
        command.add_argument("--key", action="append", default=[])
        command.add_argument("--set", action="append", default=[])
        if name == "apply":
            command.add_argument("--yes", action="store_true")
    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("--required-by")
    get_parser = subparsers.add_parser("get")
    get_parser.add_argument("key")
    args = parser.parse_args(argv)

    contracts = load_contracts(contract_paths)
    discovery = load_discovery(discovery_paths)
    unknown = set(discovery) - set(contracts)
    if unknown:
        raise BindingError(f"discovery declares unknown binding keys: {sorted(unknown)}")
    directory = (args.profile_dir or resolver.profile_directory()).expanduser()
    target = directory / managed_name
    if target.is_symlink():
        raise BindingError(f"managed profile must not be a symlink: {target}")
    try:
        profile = resolver.load_profile(directory)
    except resolver.ProfileError as exc:
        raise BindingError(str(exc)) from exc

    if args.command == "get":
        if args.key not in contracts:
            raise BindingError(f"unknown binding key: {args.key}")
        if args.key in profile.values:
            value = validate_value(profile.values[args.key], contracts[args.key])
        elif "default" in contracts[args.key]:
            value = contracts[args.key]["default"]
        else:
            raise BindingError(f"binding key is not configured: {args.key}")
        print("true" if value is True else "false" if value is False else value)
        return 0

    if args.command == "doctor":
        selected = {
            key
            for key, contract in contracts.items()
            if args.required_by is None or args.required_by in contract["required_by"]
        }
        statuses = evaluate(contracts, {}, profile, {}, selected, Path.home())
        _show(statuses)
        failures = [item for item in statuses if item.state in {"missing", "invalid"}]
        if failures and args.required_by is not None:
            raise BindingError(f"required bindings are not ready: {args.required_by}")
        if any(item.state == "invalid" for item in statuses):
            raise BindingError("configured bindings are invalid")
        return 0

    selected = set(args.key) if args.key else None
    if selected is not None and not selected <= set(contracts):
        raise BindingError(f"unknown binding keys: {sorted(selected - set(contracts))}")
    explicit = _parse_set(args.set, contracts)
    if selected is not None and not set(explicit) <= selected:
        raise BindingError("every --set key must also be selected by --key")
    statuses = evaluate(
        contracts, discovery, profile, explicit, selected, Path.home()
    )
    _show(statuses)

    before, managed = inspect_managed(target, managed_marker)
    for status in statuses:
        if status.state in {"explicit", "discovered"} and status.value is not None:
            managed[status.key] = status.value
    after = render_managed(managed, managed_marker) if managed else before
    print(f"profile: {target}")
    print("permissions: directory=700 fragment=600")
    if before == after:
        print("no changes")
    else:
        print(
            "".join(
                difflib.unified_diff(
                    before.splitlines(keepends=True),
                    after.splitlines(keepends=True),
                    fromfile=str(target),
                    tofile=str(target),
                )
            ),
            end="",
        )
    if args.command == "apply":
        if not args.yes:
            raise BindingError("apply requires --yes after reviewing the plan")
        if before != after:
            _write_atomic(target, after)
            print("applied")
    return 0


def main() -> None:
    raise SystemExit("bindings.py is a library; use setup.py or a pack wrapper")


if __name__ == "__main__":
    main()
