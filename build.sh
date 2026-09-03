#!/usr/bin/env bash
# tr-kit-source 빌드 — executable TOML recipe → out/<target>/
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}" exec python3 "$ROOT/tools/build.py" "$@"
