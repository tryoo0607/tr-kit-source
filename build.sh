#!/usr/bin/env bash
# Build the promoted source. Codex is the first rollout target.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
target="${1:-codex}"
if [ "$#" -gt 0 ]; then shift; fi
case "$target" in
  codex|claude) exec python3 "$ROOT/scripts/package.py" --product "$target" "$@" ;;
  *) echo "usage: build.sh [codex|claude] --output NEW_DIRECTORY" >&2; exit 2 ;;
esac
