#!/usr/bin/env python3
"""Inject optional public profile behavior at session start without blocking it."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_resolver():
    here = Path(__file__).resolve()
    candidates = [
        here.parents[1] / "profile" / "resolver.py",  # generated plugin: hooks/../profile
        here.parents[2] / "core" / "profile" / "resolver.py",  # source tree
    ]
    for path in candidates:
        if not path.is_file():
            continue
        spec = importlib.util.spec_from_file_location("_tr_kit_profile_context", path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    return None


def main() -> None:
    try:
        runtime = load_resolver()
        if runtime is None:
            return
        profile = runtime.load_profile()
        if profile.values.get("public.features.dive_ambient") is True:
            print(
                "🤿 dive ambient가 opt-in 상태다. 작업 중 정말 관련 있고 가치 있는 "
                "주제가 있을 때만 응답 끝에 1회성 한 줄로 제안한다. 남발하거나 "
                "작업을 막지 않는다."
            )
    except Exception:
        return


if __name__ == "__main__":
    main()
