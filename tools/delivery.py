#!/usr/bin/env python3
"""Verify recipe-driven delivery in disposable clones without pushing."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from tools.build import BuildError, _load_recipe, _load_tokens, _substitute, build_target, select_targets


class DeliveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class SyncMapping:
    source: str
    destination: str


@dataclass(frozen=True)
class DeliverySpec:
    target: str
    repository: str
    mode: str
    generated: tuple[str, ...]
    prepare: tuple[tuple[str, ...], ...]
    checks: tuple[tuple[str, ...], ...]
    sync: tuple[SyncMapping, ...]


def _relative_path(value: str, where: str, *, allow_dot: bool = False) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or (not allow_dot and path == Path(".")):
        raise DeliveryError(f"{where} must stay inside its root: {value}")
    return path


def load_delivery_spec(root: Path, target: str) -> DeliverySpec:
    root = root.resolve()
    recipe = _load_recipe(root, target, root)
    tokens = _load_tokens(root, recipe["glossary"], root)
    delivery = recipe["delivery"]

    generated = tuple(
        _substitute(value, tokens, f"{target}.delivery.generated").rstrip("/")
        for value in delivery["generated"]
    )
    for value in generated:
        _relative_path(value, f"{target}.delivery.generated")

    mappings = []
    for index, item in enumerate(delivery["sync"]):
        source = _substitute(item["source"], tokens, f"{target}.delivery.sync[{index}].source")
        destination = _substitute(
            item["destination"], tokens, f"{target}.delivery.sync[{index}].destination"
        )
        _relative_path(source, f"{target}.delivery.sync[{index}].source", allow_dot=True)
        _relative_path(destination, f"{target}.delivery.sync[{index}].destination")
        mappings.append(SyncMapping(source, destination.rstrip("/")))

    destinations = [mapping.destination for mapping in mappings]
    for index, left in enumerate(destinations):
        for right in destinations[index + 1 :]:
            if left == right or left.startswith(f"{right}/") or right.startswith(f"{left}/"):
                raise DeliveryError(f"[{target}] overlapping delivery destinations: {left}, {right}")

    return DeliverySpec(
        target=target,
        repository=delivery["repository"],
        mode=delivery.get("mode", "partial"),
        generated=generated,
        prepare=tuple(tuple(command) for command in delivery["prepare"]),
        checks=tuple(tuple(command) for command in delivery["checks"]),
        sync=tuple(mappings),
    )


def _run(argv: tuple[str, ...] | list[str], cwd: Path, *, capture: bool = True) -> str:
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            check=True,
            text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.STDOUT if capture else None,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        output = getattr(exc, "stdout", "") or ""
        command = " ".join(argv)
        raise DeliveryError(f"command failed in {cwd}: {command}\n{output}".rstrip()) from exc
    return result.stdout if capture else ""


def _git(repo: Path, *args: str) -> str:
    return _run(["git", "-C", str(repo), *args], repo).strip()


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        digest.update(str(relative).encode())
        digest.update(b"\0")
        digest.update(str(path.lstat().st_mode & 0o777).encode())
        digest.update(b"\0")
        if path.is_symlink():
            digest.update(os.readlink(path).encode())
        elif path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise DeliveryError(f"delivery source is not a directory: {source}")
    if destination.exists() or destination.is_symlink():
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, symlinks=True)


def _assert_managed_tree_safe(root: Path) -> None:
    if not root.is_dir():
        raise DeliveryError(f"managed-root output is not a directory: {root}")
    if not (root / ".tr-kit-generated").is_file():
        raise DeliveryError("managed-root output is missing .tr-kit-generated")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise DeliveryError(f"managed-root output must not contain symlinks: {path}")


def _replace_managed_root(source: Path, destination: Path) -> None:
    _assert_managed_tree_safe(source)
    for path in destination.iterdir():
        if path.name == ".git":
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    for path in source.iterdir():
        target = destination / path.name
        if path.is_dir():
            shutil.copytree(path, target)
        else:
            shutil.copy2(path, target)


def _apply_sync(spec: DeliverySpec, output_root: Path, repo: Path) -> None:
    if spec.mode == "managed-root":
        _replace_managed_root(output_root, repo)
        return
    for mapping in spec.sync:
        source = output_root / _relative_path(
            mapping.source, f"{spec.target}.delivery source", allow_dot=True
        )
        destination = repo / _relative_path(
            mapping.destination, f"{spec.target}.delivery destination"
        )
        _copy_tree(source, destination)


def _changed_paths(repo: Path) -> tuple[str, ...]:
    output = _run(
        ["git", "-C", str(repo), "status", "--porcelain=v1", "--untracked-files=all"],
        repo,
    )
    paths = []
    for line in output.splitlines():
        value = line[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        paths.append(value)
    return tuple(sorted(paths))


def _path_allowed(path: str, spec: DeliverySpec) -> bool:
    if spec.mode == "managed-root":
        return True
    if path in spec.generated:
        return True
    return any(
        path == mapping.destination or path.startswith(f"{mapping.destination}/")
        for mapping in spec.sync
    )


def _assert_boundaries(repo: Path, spec: DeliverySpec) -> tuple[str, ...]:
    changed = _changed_paths(repo)
    outside = [path for path in changed if not _path_allowed(path, spec)]
    if outside:
        raise DeliveryError(f"[{spec.target}] changes escaped recipe ownership: {outside}")
    return changed


def _assert_payload_unchanged(spec: DeliverySpec, output_root: Path, repo: Path) -> None:
    if spec.mode == "managed-root":
        if _tree_digest(output_root) != _tree_digest(repo):
            raise DeliveryError(f"[{spec.target}] prepare command changed managed-root output")
        return
    for mapping in spec.sync:
        source = output_root / mapping.source
        destination = repo / mapping.destination
        if _tree_digest(source) != _tree_digest(destination):
            raise DeliveryError(
                f"[{spec.target}] prepare command changed source-owned path: {mapping.destination}"
            )


def _prepare(spec: DeliverySpec, repo: Path) -> None:
    for command in spec.prepare:
        _run(command, repo)


def verify_target(spec: DeliverySpec, output_root: Path, source_repo: Path) -> tuple[str, ...]:
    source_repo = source_repo.resolve()
    if not (source_repo / ".git").exists() and not _git(source_repo, "rev-parse", "--git-dir"):
        raise DeliveryError(f"target repository is not a git worktree: {source_repo}")
    if _git(source_repo, "status", "--porcelain"):
        raise DeliveryError(f"target repository must be clean: {source_repo}")
    expected_suffix = f"{spec.repository}.git"
    remote = _git(source_repo, "remote", "get-url", "origin")
    if not (remote.endswith(expected_suffix) or remote.rstrip("/").endswith(spec.repository)):
        raise DeliveryError(
            f"[{spec.target}] origin does not match recipe repository: {remote} != {spec.repository}"
        )
    source_head = _git(source_repo, "rev-parse", "HEAD")

    with tempfile.TemporaryDirectory(prefix=f"tr-kit-delivery-{spec.target}-") as tmp:
        clone = Path(tmp) / spec.target
        _run(["git", "clone", "--no-hardlinks", "--quiet", str(source_repo), str(clone)], Path(tmp))
        _git(clone, "checkout", "--quiet", "--detach", source_head)

        _apply_sync(spec, output_root, clone)
        _prepare(spec, clone)
        changed = _assert_boundaries(clone, spec)
        _assert_payload_unchanged(spec, output_root, clone)
        first_digest = _tree_digest(clone)

        _apply_sync(spec, output_root, clone)
        _prepare(spec, clone)
        _assert_boundaries(clone, spec)
        _assert_payload_unchanged(spec, output_root, clone)
        if first_digest != _tree_digest(clone):
            raise DeliveryError(f"[{spec.target}] delivery is not idempotent")

        before_checks = _tree_digest(clone)
        for command in spec.checks:
            _run(command, clone)
        if before_checks != _tree_digest(clone):
            _assert_boundaries(clone, spec)
            raise DeliveryError(f"[{spec.target}] check command modified the target clone")
        _git(clone, "diff", "--check")
        return changed


def deploy_target(
    spec: DeliverySpec,
    output_root: Path,
    repo: Path,
    *,
    source_revision: str,
) -> tuple[str, ...]:
    """Verify in isolation, then commit and normally push a disposable clone."""
    if os.environ.get("TR_KIT_ALLOW_PUSH") != "1":
        raise DeliveryError("deployment requires TR_KIT_ALLOW_PUSH=1")
    if not re.fullmatch(r"[0-9a-f]{40}", source_revision):
        raise DeliveryError("deployment requires a full lowercase source revision")

    verify_target(spec, output_root, repo)
    _apply_sync(spec, output_root, repo)
    changed = _assert_boundaries(repo, spec)
    _assert_payload_unchanged(spec, output_root, repo)
    before_checks = _tree_digest(repo)
    for command in spec.checks:
        _run(command, repo)
    if before_checks != _tree_digest(repo):
        raise DeliveryError(f"[{spec.target}] check command modified the deployment clone")
    _git(repo, "diff", "--check")
    if not changed:
        return ()

    _git(repo, "config", "user.name", "github-actions[bot]")
    _git(
        repo,
        "config",
        "user.email",
        "41898282+github-actions[bot]@users.noreply.github.com",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", f"chore: tr-kit-source {source_revision[:7]} 배포")
    _git(repo, "push", "origin", "HEAD:main")
    return changed


def _repo_arguments(values: list[str]) -> dict[str, Path]:
    result = {}
    for value in values:
        if "=" not in value:
            raise DeliveryError(f"--repo must be TARGET=PATH: {value}")
        target, path = value.split("=", 1)
        if not target or target in result or not path:
            raise DeliveryError(f"invalid or duplicate --repo: {value}")
        result[target] = Path(path)
    return result


def _clone_repositories(specs: dict[str, DeliverySpec], clone_root: Path) -> dict[str, Path]:
    clone_root = clone_root.resolve()
    clone_root.mkdir(parents=True, exist_ok=True)
    if any(clone_root.iterdir()):
        raise DeliveryError(f"--clone-root must be empty: {clone_root}")
    repositories = {}
    for target, spec in specs.items():
        destination = clone_root / target
        repository_url = os.environ.get(
            f"TR_KIT_{target.upper().replace('-', '_')}_REPOSITORY_URL"
        )
        if repository_url:
            _run(["git", "clone", "--quiet", repository_url, str(destination)], clone_root)
        else:
            _run(
                ["gh", "repo", "clone", spec.repository, str(destination), "--", "--quiet"],
                clone_root,
            )
        repositories[target] = destination
    return repositories


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="*")
    parser.add_argument(
        "--repo",
        action="append",
        default=[],
        metavar="TARGET=PATH",
        help="clean local checkout used as the disposable-clone source",
    )
    parser.add_argument(
        "--clone-root",
        type=Path,
        help="empty directory where recipe repositories are cloned with gh",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="commit and normally push disposable clones (requires TR_KIT_ALLOW_PUSH=1)",
    )
    parser.add_argument(
        "--source-revision",
        default="",
        help="full source commit SHA recorded in deployment commits",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    try:
        targets = select_targets(root, args.targets)
        specs = {target: load_delivery_spec(root, target) for target in targets}
        if args.repo and args.clone_root:
            raise DeliveryError("use either --repo or --clone-root, not both")
        if args.push and (not args.clone_root or args.repo):
            raise DeliveryError("--push requires --clone-root and does not accept --repo")
        repositories = (
            _clone_repositories(specs, args.clone_root)
            if args.clone_root
            else _repo_arguments(args.repo)
        )
        missing = sorted(set(targets) - set(repositories))
        extra = sorted(set(repositories) - set(targets))
        if missing or extra:
            raise DeliveryError(f"repository mapping differs: missing={missing} extra={extra}")

        for target in targets:
            output_root = root / "out" / target
            if output_root.exists():
                shutil.rmtree(output_root)
            build_target(root, target)
            spec = specs[target]
            if args.push:
                changed = deploy_target(
                    spec,
                    output_root,
                    repositories[target],
                    source_revision=args.source_revision,
                )
                result = "no-op" if not changed else f"pushed {len(changed)} changed paths"
                print(f"[{target}] deployment OK — {result}")
            else:
                changed = verify_target(spec, output_root, repositories[target])
                print(f"[{target}] dry-run OK — {len(changed)} changed paths, boundaries/checks/idempotence passed")
    except (BuildError, DeliveryError) as exc:
        sys.exit(f"FAIL: {exc}")


if __name__ == "__main__":
    main()
