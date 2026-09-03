#!/usr/bin/env python3
"""Resolve non-secret runtime settings from ordered profile.d TOML fragments."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


Scalar = str | int | float | bool
Override = tuple[str, Path, Path]
CONTRACT_KEYS = {
    "schema_version",
    "fragment_schema_version",
    "allowed_roots",
    "allowed_value_types",
    "extension_pattern",
    "secret_segments",
    "precedence",
}


class ProfileError(RuntimeError):
    pass


@dataclass(frozen=True)
class Profile:
    values: Mapping[str, Scalar]
    sources: Mapping[str, Path]
    overrides: tuple[Override, ...]
    fragments: tuple[Path, ...]

    def get(self, key: str) -> Scalar:
        if key not in self.values:
            raise ProfileError(f"profile key is not configured: {key}")
        return self.values[key]

    def source(self, key: str) -> Path:
        if key not in self.sources:
            raise ProfileError(f"profile key is not configured: {key}")
        return self.sources[key]


def _read_toml(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ProfileError(f"cannot read profile fragment {path}: {exc}") from exc


def _load_contract() -> dict:
    path = Path(__file__).resolve().parent / "contracts" / "profile-v1.toml"
    contract = _read_toml(path)
    unknown = set(contract) - CONTRACT_KEYS
    if unknown:
        raise ProfileError(f"unknown runtime profile contract keys: {sorted(unknown)}")
    if contract.get("schema_version") != 1:
        raise ProfileError("unsupported runtime profile contract")
    if contract.get("fragment_schema_version") != 1:
        raise ProfileError("unsupported runtime profile fragment contract")
    for key in ("allowed_roots", "allowed_value_types", "secret_segments"):
        value = contract.get(key)
        if not isinstance(value, list) or not value or not all(
            isinstance(item, str) for item in value
        ):
            raise ProfileError(f"runtime profile contract {key} must be a string list")
    if contract.get("precedence") != "filename-ascending-last-wins":
        raise ProfileError("unsupported runtime profile precedence")
    pattern = contract.get("extension_pattern")
    if not isinstance(pattern, str):
        raise ProfileError("runtime profile extension_pattern must be a string")
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ProfileError("invalid runtime profile extension_pattern") from exc
    return contract


def profile_directory(environ: Mapping[str, str] | None = None) -> Path:
    environ = os.environ if environ is None else environ
    configured = environ.get("TR_KIT_PROFILE_DIR")
    if configured:
        return Path(configured).expanduser()
    config_home = environ.get("XDG_CONFIG_HOME")
    base = Path(config_home).expanduser() if config_home else Path.home() / ".config"
    return base / "tr-kit" / "profile.d"


def _scalar_type(value: object) -> str | None:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    return None


def _flatten(
    prefix: tuple[str, ...],
    value: object,
    source: Path,
    allowed_value_types: set[str],
) -> dict[str, Scalar]:
    if isinstance(value, dict):
        flattened: dict[str, Scalar] = {}
        for name, child in value.items():
            if not isinstance(name, str) or not name:
                raise ProfileError(f"invalid profile key in {source}")
            flattened.update(
                _flatten((*prefix, name), child, source, allowed_value_types)
            )
        return flattened
    if not prefix or _scalar_type(value) not in allowed_value_types:
        dotted = ".".join(prefix) or "<root>"
        raise ProfileError(f"profile value must be a non-secret scalar: {dotted} in {source}")
    return {".".join(prefix): value}


def _validate_key(key: str, source: Path, contract: dict) -> None:
    segments = key.split(".")
    secret_segments = set(contract.get("secret_segments", []))
    normalized = {segment.lower().replace("-", "_") for segment in segments}
    forbidden = normalized & secret_segments
    if forbidden:
        raise ProfileError(
            f"secret-like profile key is forbidden: {key} in {source}"
        )


def _check_shape_conflict(key: str, existing: Mapping[str, Scalar], source: Path) -> None:
    for other in existing:
        if key.startswith(f"{other}.") or other.startswith(f"{key}."):
            raise ProfileError(
                f"profile table/scalar shape conflict: {key} and {other} in {source}"
            )


def load_profile(directory: Path | None = None) -> Profile:
    directory = (directory or profile_directory()).expanduser()
    if directory.exists() and not directory.is_dir():
        raise ProfileError(f"profile path is not a directory: {directory}")

    contract = _load_contract()
    allowed_roots = set(contract.get("allowed_roots", []))
    allowed_value_types = set(contract.get("allowed_value_types", []))
    extension_pattern = re.compile(contract.get("extension_pattern", r"$^"))
    fragments = tuple(sorted(directory.glob("*.toml"))) if directory.is_dir() else ()
    values: dict[str, Scalar] = {}
    sources: dict[str, Path] = {}
    overrides: list[Override] = []

    for fragment in fragments:
        data = _read_toml(fragment)
        if data.pop("schema_version", None) != contract.get("fragment_schema_version"):
            raise ProfileError(f"unsupported profile schema_version in {fragment}")
        unknown = set(data) - allowed_roots
        if unknown:
            raise ProfileError(
                f"unknown top-level profile namespace in {fragment}: {sorted(unknown)}"
            )
        extensions = data.get("extensions", {})
        if not isinstance(extensions, dict) or any(
            not extension_pattern.fullmatch(name) for name in extensions
        ):
            raise ProfileError(f"invalid extensions namespace in {fragment}")

        for root, node in data.items():
            if not isinstance(node, dict):
                raise ProfileError(f"top-level profile namespace must be a table: {root}")
            for key, value in _flatten(
                (root,), node, fragment, allowed_value_types
            ).items():
                _validate_key(key, fragment, contract)
                _check_shape_conflict(key, values, fragment)
                if key in sources:
                    overrides.append((key, sources[key], fragment))
                values[key] = value
                sources[key] = fragment

    return Profile(values, sources, tuple(overrides), fragments)


def _print_value(value: Scalar) -> None:
    if isinstance(value, bool):
        print("true" if value else "false")
    else:
        print(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-dir", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    get_parser = subparsers.add_parser("get")
    get_parser.add_argument("key")
    subparsers.add_parser("sources")
    subparsers.add_parser("doctor")
    args = parser.parse_args()

    try:
        profile = load_profile(args.profile_dir)
        if args.command == "get":
            _print_value(profile.get(args.key))
        elif args.command == "sources":
            print(
                json.dumps(
                    {key: str(path) for key, path in sorted(profile.sources.items())},
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(
                f"ok fragments={len(profile.fragments)} "
                f"values={len(profile.values)} overrides={len(profile.overrides)}"
            )
    except ProfileError as exc:
        sys.exit(f"FAIL: {exc}")


if __name__ == "__main__":
    main()
