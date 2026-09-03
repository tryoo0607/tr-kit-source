#!/usr/bin/env python3
"""Manage public tr-kit runtime bindings."""

from pathlib import Path

try:
    from .bindings import BindingError, run_cli
except ImportError:
    from bindings import BindingError, run_cli  # type: ignore


ROOT = Path(__file__).resolve().parent


def main() -> None:
    try:
        raise SystemExit(
            run_cli(
                contract_paths=[ROOT / "contracts" / "public-keys-v1.toml"],
                managed_name="50-tr-kit.toml",
                managed_marker="# managed-by: tr-kit/profile-setup",
            )
        )
    except (BindingError, OSError) as exc:
        raise SystemExit(f"FAIL: {exc}") from exc


if __name__ == "__main__":
    main()
