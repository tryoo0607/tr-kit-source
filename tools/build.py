#!/usr/bin/env python3
"""Build target kits from executable TOML recipes."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tomllib
from pathlib import Path

from tools.gen_readme import generate_readme
from tools.transform import LEFTOVER, TEXT_EXT, strip_guards, sub_tokens


class BuildError(RuntimeError):
    pass


SCHEMA_KEYS = {
    "schema_version",
    "recipe_keys",
    "output_keys",
    "import_keys",
    "import_scopes",
    "artifact_keys",
    "artifact_scopes",
    "composition_keys",
    "composition_kinds",
    "composition_scopes",
    "generator_keys",
    "generator_kinds",
    "generator_scopes",
    "delivery_keys",
    "delivery_sync_keys",
}

SLOT = re.compile(r"\{\{slot:([a-z][a-z0-9.-]*)\}\}")
CAPABILITY_KEYS = {"required", "format"}
PACK_CONTRACT_KEYS = {"schema_version", "contract_version", "pack_keys", "exports"}
PACK_MANIFEST_KEYS = {"schema_version", "name", "version", "toolchain_contract"}
EXPORT_KEYS = {"source"}
PACK_NAME = re.compile(r"[a-z][a-z0-9-]*")
SEMVER = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")


def _read_toml(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise BuildError(f"cannot read recipe {path}: {exc}") from exc


def _reject_unknown(data: dict, allowed: set[str], where: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise BuildError(f"unknown keys in {where}: {sorted(unknown)}")


def _load_recipe_schema(root: Path) -> dict:
    path = root / "recipes" / "_schema.toml"
    schema = _read_toml(path)
    _reject_unknown(schema, SCHEMA_KEYS, path.name)
    if schema.get("schema_version") != 1:
        raise BuildError("unsupported recipe contract schema_version")
    for key in SCHEMA_KEYS - {"schema_version"}:
        values = schema.get(key)
        if not isinstance(values, list) or not values or not all(
            isinstance(value, str) for value in values
        ):
            raise BuildError(f"recipe contract {key} must be a non-empty string list")
    return schema


def _load_pack_contract(toolchain_root: Path) -> dict:
    contract_path = toolchain_root / "core" / "contracts" / "pack-v1.toml"
    contract = _read_toml(contract_path)
    _reject_unknown(contract, PACK_CONTRACT_KEYS, contract_path.name)
    if contract.get("schema_version") != 1 or type(contract.get("contract_version")) is not int:
        raise BuildError("unsupported toolchain pack contract")
    pack_keys = contract.get("pack_keys")
    if (
        not isinstance(pack_keys, list)
        or not all(isinstance(key, str) for key in pack_keys)
        or len(pack_keys) != len(set(pack_keys))
        or set(pack_keys) != PACK_MANIFEST_KEYS
    ):
        raise BuildError("toolchain pack contract pack_keys are invalid")

    exports = contract.get("exports")
    if not isinstance(exports, dict):
        raise BuildError("toolchain pack contract exports must be a table")
    for name, export in exports.items():
        if not isinstance(name, str) or not PACK_NAME.fullmatch(name):
            raise BuildError(f"invalid toolchain export name: {name}")
        if not isinstance(export, dict):
            raise BuildError(f"toolchain export {name} must be a table")
        _reject_unknown(export, EXPORT_KEYS, f"toolchain export {name}")
        source = export.get("source")
        if not isinstance(source, str):
            raise BuildError(f"toolchain export {name} requires a source")
        resolved = _source_path(toolchain_root, source)
        if not resolved.exists():
            raise BuildError(f"toolchain export {name} source does not exist: {source}")
    return contract


def _validate_external_pack(root: Path, toolchain_root: Path) -> None:
    contract = _load_pack_contract(toolchain_root)
    pack_keys = contract["pack_keys"]

    manifest_path = root / "pack.toml"
    manifest = _read_toml(manifest_path)
    _reject_unknown(manifest, set(pack_keys), manifest_path.name)
    if manifest.get("schema_version") != 1:
        raise BuildError("unsupported pack.toml schema_version")
    if manifest.get("toolchain_contract") != contract["contract_version"]:
        raise BuildError("unsupported toolchain contract in pack.toml")
    name = manifest.get("name")
    if not isinstance(name, str) or not PACK_NAME.fullmatch(name):
        raise BuildError("pack.toml name must be lowercase kebab-case")
    version = manifest.get("version")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        raise BuildError("pack.toml version must be SemVer major.minor.patch")


def discover_targets(root: Path, *, toolchain_root: Path | None = None) -> list[str]:
    root = root.resolve()
    toolchain_root = (toolchain_root or root).resolve()
    recipe_dir = root / "recipes"
    if not recipe_dir.is_dir():
        raise BuildError(f"recipe directory does not exist: {recipe_dir}")
    _load_recipe_schema(toolchain_root)
    if root != toolchain_root:
        _validate_external_pack(root, toolchain_root)

    legacy = sorted(
        path.name for path in recipe_dir.iterdir() if path.suffix in {".yaml", ".yml"}
    )
    if legacy:
        raise BuildError(f"unsupported recipe files would be ignored: {legacy}")

    targets = sorted(path.stem for path in recipe_dir.glob("*.toml") if not path.name.startswith("_"))
    if not targets:
        raise BuildError("no target recipes found")
    return targets


def select_targets(
    root: Path, requested: list[str], *, toolchain_root: Path | None = None
) -> list[str]:
    available = discover_targets(root, toolchain_root=toolchain_root)
    if not requested:
        return available
    unknown = sorted(set(requested) - set(available))
    if unknown:
        raise BuildError(f"unknown build targets: {unknown}")
    if len(requested) != len(set(requested)):
        raise BuildError("duplicate build targets are not allowed")
    return requested


def _load_recipe(root: Path, target: str, toolchain_root: Path) -> dict:
    schema = _load_recipe_schema(toolchain_root)
    path = _source_path(root, f"recipes/{target}.toml")
    if not path.is_file():
        raise BuildError(f"target recipe does not exist: {path}")
    target_data = _read_toml(path)
    _reject_unknown(target_data, set(schema["recipe_keys"]), path.name)

    base_data: dict = {}
    extends = target_data.get("extends")
    if extends:
        if not isinstance(extends, str):
            raise BuildError(f"base recipe does not exist: {extends}")
        base_path = _source_path(root, f"recipes/{extends}")
        if Path(extends).name != extends or not base_path.is_file():
            raise BuildError(f"base recipe does not exist: {extends}")
        base_data = _read_toml(base_path)
        _reject_unknown(base_data, set(schema["recipe_keys"]), base_path.name)

    recipe = {**base_data, **target_data}
    recipe["artifacts"] = [
        *base_data.get("artifacts", []),
        *target_data.get("artifacts", []),
    ]
    recipe["imports"] = [
        *base_data.get("imports", []),
        *target_data.get("imports", []),
    ]
    recipe["generators"] = [
        *base_data.get("generators", []),
        *target_data.get("generators", []),
    ]
    recipe["compositions"] = [
        *base_data.get("compositions", []),
        *target_data.get("compositions", []),
    ]

    if recipe.get("schema_version") != 1:
        raise BuildError(f"[{target}] unsupported recipe schema_version")
    if recipe.get("target") != target:
        raise BuildError(f"[{target}] recipe target must match its filename")
    if not isinstance(recipe.get("glossary"), str):
        raise BuildError(f"[{target}] glossary is required")
    output = recipe.get("output")
    if not isinstance(output, dict):
        raise BuildError(f"[{target}] output table is required")
    _reject_unknown(output, set(schema["output_keys"]), f"{target}.output")
    if not isinstance(output.get("payload"), str):
        raise BuildError(f"[{target}] output.payload is required")
    delivery = recipe.get("delivery")
    if not isinstance(delivery, dict):
        raise BuildError(f"[{target}] delivery table is required")
    _reject_unknown(delivery, set(schema["delivery_keys"]), f"{target}.delivery")
    repository = delivery.get("repository")
    if not isinstance(repository, str) or not re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository
    ):
        raise BuildError(f"[{target}] delivery.repository must be owner/name")
    mode = delivery.get("mode", "partial")
    if mode not in {"partial", "managed-root"}:
        raise BuildError(f"[{target}] delivery.mode must be partial or managed-root")
    for key in ("generated", "prepare", "checks"):
        value = delivery.get(key)
        if not isinstance(value, list):
            raise BuildError(f"[{target}] delivery.{key} must be a list")
    if not all(isinstance(path, str) for path in delivery["generated"]):
        raise BuildError(f"[{target}] delivery.generated must contain strings")
    for key in ("prepare", "checks"):
        if not all(
            isinstance(command, list)
            and command
            and all(isinstance(arg, str) and arg for arg in command)
            for command in delivery[key]
        ):
            raise BuildError(f"[{target}] delivery.{key} must contain argv arrays")
    sync = delivery.get("sync")
    if not isinstance(sync, list) or (mode == "partial" and not sync):
        raise BuildError(f"[{target}] partial delivery.sync must be a non-empty list")
    if mode == "managed-root" and (sync or delivery["generated"] or delivery["prepare"]):
        raise BuildError(
            f"[{target}] managed-root delivery owns the complete output; "
            "sync, generated, and prepare must be empty"
        )
    for index, mapping in enumerate(sync):
        if not isinstance(mapping, dict):
            raise BuildError(f"[{target}] delivery.sync[{index}] must be a table")
        _reject_unknown(
            mapping,
            set(schema["delivery_sync_keys"]),
            f"{target}.delivery.sync[{index}]",
        )
        if not all(isinstance(mapping.get(key), str) for key in ("source", "destination")):
            raise BuildError(
                f"[{target}] delivery.sync[{index}] requires source and destination"
            )
    return recipe


def _load_capabilities(root: Path) -> dict[str, dict]:
    path = _source_path(root, "core/contracts/capabilities.toml")
    data = _read_toml(path)
    _reject_unknown(data, {"schema_version", "capabilities"}, str(path))
    if data.get("schema_version") != 1:
        raise BuildError("unsupported capability contract schema_version")
    capabilities = data.get("capabilities")
    if not isinstance(capabilities, dict):
        raise BuildError("capability contract must define capabilities")
    for name, contract in capabilities.items():
        if not isinstance(name, str) or not isinstance(contract, dict):
            raise BuildError("invalid capability contract")
        _reject_unknown(contract, CAPABILITY_KEYS, f"capability {name}")
        if not isinstance(contract.get("required"), bool):
            raise BuildError(f"capability {name} requires boolean required")
        if contract.get("format") != "markdown-fragment":
            raise BuildError(f"capability {name} has unsupported format")
    return capabilities


def _load_composition_capabilities(
    root: Path, toolchain_root: Path
) -> dict[str, dict]:
    capabilities = _load_capabilities(toolchain_root)
    if root == toolchain_root:
        return capabilities

    pack_contract = root / "core" / "contracts" / "capabilities.toml"
    if not pack_contract.exists():
        return capabilities
    pack_capabilities = _load_capabilities(root)
    overlap = set(capabilities) & set(pack_capabilities)
    if overlap:
        raise BuildError(
            f"external pack cannot override toolchain capabilities: {sorted(overlap)}"
        )
    return {**capabilities, **pack_capabilities}


def _load_tokens(root: Path, glossary_rel: str, toolchain_root: Path) -> dict[str, str]:
    if glossary_rel.startswith("toolchain:"):
        target = glossary_rel.removeprefix("toolchain:")
        if not re.fullmatch(r"[a-z][a-z0-9-]*", target):
            raise BuildError(f"invalid toolchain glossary: {glossary_rel}")
        glossary = toolchain_root / "glossary" / f"{target}.toml"
        schema = toolchain_root / "glossary" / "_schema.toml"
    else:
        glossary = _source_path(root, glossary_rel)
        schema = glossary.parent / "_schema.toml"
    if not glossary.is_file() or not schema.is_file():
        raise BuildError(f"glossary or schema does not exist: {glossary_rel}")
    expected = set(_read_toml(schema).get("tokens", {}))
    values = _read_toml(glossary)
    missing = expected - set(values)
    extra = set(values) - expected
    if missing or extra:
        raise BuildError(
            f"glossary keys differ from schema: missing={sorted(missing)} extra={sorted(extra)}"
        )
    if not all(isinstance(value, str) for value in values.values()):
        raise BuildError("glossary values must be strings")
    return values


def _source_path(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise BuildError(f"source must stay inside repository: {relative}")
    root = root.resolve()
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise BuildError(f"source must stay inside repository: {relative}") from exc
    return candidate


def _output_path(base: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise BuildError(f"destination must stay inside target output: {relative}")
    base = base.resolve()
    candidate = (base / path).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise BuildError(f"destination must stay inside target output: {relative}") from exc
    return candidate


def _substitute(value: str, tokens: dict[str, str], where: str) -> str:
    rendered = sub_tokens(value, tokens)
    if LEFTOVER.search(rendered):
        raise BuildError(f"unresolved token in {where}")
    return rendered


def _render_text(path: Path, target: str, tokens: dict[str, str]) -> str:
    text = sub_tokens(strip_guards(path.read_text(), target), tokens)
    if LEFTOVER.search(text):
        raise BuildError(f"unresolved token in {path}")
    if "<!-- if:" in text or "<!-- /if -->" in text:
        raise BuildError(f"unresolved target guard in {path}")
    return text


def _compose_skill(
    root: Path,
    source: Path,
    slot_sources: dict[str, str],
    capabilities: dict[str, dict],
    target: str,
    tokens: dict[str, str],
) -> str:
    template = _render_text(source, target, tokens)
    declared = set(capabilities)
    markers = set(SLOT.findall(template))
    mapped = set(slot_sources)

    undeclared = (markers | mapped) - declared
    if undeclared:
        raise BuildError(f"[{target}] undeclared capability slot: {sorted(undeclared)}")
    missing = {
        name
        for name in markers - mapped
        if capabilities[name]["required"]
    }
    if missing:
        raise BuildError(f"[{target}] missing required slot mapping: {sorted(missing)}")
    unused = mapped - markers
    if unused:
        raise BuildError(f"[{target}] slot mapping not used by source: {sorted(unused)}")

    rendered = template
    for name in sorted(markers):
        fragment_path = _source_path(root, slot_sources[name])
        if not fragment_path.is_file():
            raise BuildError(f"[{target}] slot fragment does not exist: {slot_sources[name]}")
        fragment = _render_text(fragment_path, target, tokens)
        if capabilities[name]["format"] == "markdown-fragment" and fragment.lstrip(
            "\ufeff \t\r\n"
        ).startswith("---\n"):
            raise BuildError(f"[{target}] slot {name} must be a markdown fragment, not a complete document")
        rendered = rendered.replace(f"{{{{slot:{name}}}}}", fragment.rstrip("\n"))

    leftover = SLOT.findall(rendered)
    if leftover:
        raise BuildError(f"[{target}] unresolved slots: {sorted(set(leftover))}")
    return rendered


def _artifact_files(source: Path) -> list[tuple[Path, Path]]:
    if source.is_file():
        return [] if source.suffix in {".pyc", ".pyo"} else [(source, Path())]
    files: list[tuple[Path, Path]] = []
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if path.is_symlink():
            raise BuildError(f"source trees must not contain symlinks: {path}")
        if (
            path.is_file()
            and "__pycache__" not in relative.parts
            and path.suffix not in {".pyc", ".pyo"}
        ):
            files.append((path, relative))
    return files


def build_target(
    root: Path, target: str, *, toolchain_root: Path | None = None
) -> int:
    root = root.resolve()
    toolchain_root = (toolchain_root or root).resolve()
    schema = _load_recipe_schema(toolchain_root)
    if root != toolchain_root:
        _validate_external_pack(root, toolchain_root)
    recipe = _load_recipe(root, target, toolchain_root)
    if root != toolchain_root and recipe["glossary"] != f"toolchain:{target}":
        raise BuildError(
            f"[{target}] external pack must use matching toolchain glossary"
        )
    tokens = _load_tokens(root, recipe["glossary"], toolchain_root)
    target_root = _output_path(root, f"out/{target}")
    payload_rel = _substitute(recipe["output"]["payload"], tokens, f"{target}.output.payload")
    payload_root = _output_path(target_root, payload_rel)
    owners: dict[Path, str] = {}
    written = 0

    imports = recipe["imports"]
    if imports and root == toolchain_root:
        raise BuildError(f"[{target}] toolchain imports are only valid for external packs")
    export_contracts = _load_pack_contract(toolchain_root).get("exports", {}) if imports else {}
    for imported in imports:
        if not isinstance(imported, dict):
            raise BuildError(f"[{target}] import must be a table")
        _reject_unknown(imported, set(schema["import_keys"]), f"{target}.import")
        import_id = imported.get("id")
        export_name = imported.get("export")
        destination = imported.get("destination")
        scope = imported.get("scope")
        if not all(
            isinstance(value, str)
            for value in (import_id, export_name, destination, scope)
        ):
            raise BuildError(
                f"[{target}] import requires string id/export/destination/scope"
            )
        if scope not in set(schema["import_scopes"]):
            raise BuildError(f"[{target}] import {import_id} has invalid scope: {scope}")
        export = export_contracts.get(export_name)
        if not isinstance(export, dict):
            raise BuildError(f"[{target}] unknown toolchain export: {export_name}")
        source = _source_path(toolchain_root, export["source"])
        destination = _substitute(
            destination, tokens, f"{target}.import.{import_id}.destination"
        )
        base = payload_root if scope == "payload" else target_root
        destination_root = _output_path(base, destination)
        for path, relative in _artifact_files(source):
            output = destination_root / relative if source.is_dir() else destination_root
            if output in owners:
                raise BuildError(
                    f"[{target}] output collision: {output.relative_to(target_root)} "
                    f"owned by {owners[output]} and {import_id}"
                )
            owners[output] = import_id
            output.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix in TEXT_EXT:
                output.write_text(_render_text(path, target, tokens))
            else:
                output.write_bytes(path.read_bytes())
            output.chmod(path.stat().st_mode)
            written += 1

    for artifact in recipe["artifacts"]:
        if not isinstance(artifact, dict):
            raise BuildError(f"[{target}] artifact must be a table")
        _reject_unknown(artifact, set(schema["artifact_keys"]), f"{target}.artifact")
        artifact_id = artifact.get("id")
        source_rel = artifact.get("source")
        destination = artifact.get("destination")
        scope = artifact.get("scope")
        if not all(isinstance(value, str) for value in (artifact_id, source_rel, destination, scope)):
            raise BuildError(f"[{target}] artifact requires string id/source/destination/scope")
        if scope not in set(schema["artifact_scopes"]):
            raise BuildError(f"[{target}] artifact {artifact_id} has invalid scope: {scope}")

        source = _source_path(root, source_rel)
        if not source.exists():
            raise BuildError(f"[{target}] source does not exist: {source_rel}")
        destination = _substitute(destination, tokens, f"{target}.artifact.{artifact_id}.destination")
        base = payload_root if scope == "payload" else target_root
        destination_root = _output_path(base, destination)

        for path, relative in _artifact_files(source):
            output = destination_root / relative if source.is_dir() else destination_root
            if output in owners:
                raise BuildError(
                    f"[{target}] output collision: {output.relative_to(target_root)} "
                    f"owned by {owners[output]} and {artifact_id}"
                )
            owners[output] = artifact_id
            output.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix in TEXT_EXT:
                output.write_text(_render_text(path, target, tokens))
            else:
                output.write_bytes(path.read_bytes())
            output.chmod(path.stat().st_mode)
            written += 1

    compositions = recipe["compositions"]
    capabilities = (
        _load_composition_capabilities(root, toolchain_root)
        if compositions
        else {}
    )
    for composition in compositions:
        if not isinstance(composition, dict):
            raise BuildError(f"[{target}] composition must be a table")
        _reject_unknown(composition, set(schema["composition_keys"]), f"{target}.composition")
        composition_id = composition.get("id")
        kind = composition.get("kind")
        source_rel = composition.get("source")
        destination = composition.get("destination")
        scope = composition.get("scope")
        slots = composition.get("slots")
        if not all(
            isinstance(value, str)
            for value in (composition_id, kind, source_rel, destination, scope)
        ) or not isinstance(slots, dict) or not all(
            isinstance(name, str) and isinstance(path, str) for name, path in slots.items()
        ):
            raise BuildError(
                f"[{target}] composition requires string id/kind/source/destination/scope and slots table"
            )
        if kind not in set(schema["composition_kinds"]):
            raise BuildError(f"[{target}] unsupported composition kind: {kind}")
        if scope not in set(schema["composition_scopes"]):
            raise BuildError(f"[{target}] composition {composition_id} has invalid scope: {scope}")

        source = _source_path(root, source_rel)
        if not source.is_file():
            raise BuildError(f"[{target}] composition source does not exist: {source_rel}")
        destination = _substitute(
            destination,
            tokens,
            f"{target}.composition.{composition_id}.destination",
        )
        base = payload_root if scope == "payload" else target_root
        output = _output_path(base, destination)
        if output in owners:
            raise BuildError(
                f"[{target}] output collision: {output.relative_to(target_root)} "
                f"owned by {owners[output]} and {composition_id}"
            )
        owners[output] = composition_id
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            _compose_skill(root, source, slots, capabilities, target, tokens)
        )
        output.chmod(source.stat().st_mode)
        written += 1

    for generator in recipe["generators"]:
        if not isinstance(generator, dict):
            raise BuildError(f"[{target}] generator must be a table")
        _reject_unknown(generator, set(schema["generator_keys"]), f"{target}.generator")
        generator_id = generator.get("id")
        kind = generator.get("kind")
        destination = generator.get("destination")
        scope = generator.get("scope")
        if not all(isinstance(value, str) for value in (generator_id, kind, destination, scope)):
            raise BuildError(f"[{target}] generator requires string id/kind/destination/scope")
        if scope not in set(schema["generator_scopes"]):
            raise BuildError(f"[{target}] generator {generator_id} has invalid scope: {scope}")
        base = payload_root if scope == "payload" else target_root
        output = _output_path(
            base,
            _substitute(destination, tokens, f"{target}.generator.{generator_id}.destination"),
        )
        if output in owners:
            raise BuildError(
                f"[{target}] output collision: {output.relative_to(target_root)} "
                f"owned by {owners[output]} and {generator_id}"
            )
        owners[output] = generator_id
        if kind not in set(schema["generator_kinds"]):
            raise BuildError(f"[{target}] unsupported generator kind: {kind}")
        if output != payload_root / "README.md":
            raise BuildError(f"[{target}] skill-readme destination must be payload README.md")
        generate_readme(payload_root, target, tokens["KIT_REPO"])
        written += 1

    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack-root", type=Path)
    parser.add_argument("targets", nargs="*")
    args = parser.parse_args()
    toolchain_root = Path(__file__).resolve().parent.parent
    root = (args.pack_root or toolchain_root).resolve()
    try:
        targets = select_targets(root, args.targets, toolchain_root=toolchain_root)
        out = root / "out"
        if out.is_symlink():
            raise BuildError("output root must stay inside target output")
        if out.exists():
            shutil.rmtree(out)

        for target in targets:
            print(f"== build: {target} ==")
            build_target(root, target, toolchain_root=toolchain_root)
    except BuildError as exc:
        sys.exit(f"FAIL: {exc}")

    print(f"done -> {out}")
    for target in targets:
        actual = sum(1 for path in (out / target).rglob("*") if path.is_file())
        print(f"  {target}: {actual} files")


if __name__ == "__main__":
    main()
