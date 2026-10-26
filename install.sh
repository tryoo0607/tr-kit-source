#!/usr/bin/env bash
# Register a verified local Codex marketplace. Existing installations are not removed.
set -euo pipefail
target="${1:-}"
marketplace="${2:-}"
mode="${3:-}"
if [ "$target" != codex ] || [ -z "$marketplace" ] || { [ -n "$mode" ] && [ "$mode" != --apply ]; }; then
  echo "usage: install.sh codex MARKETPLACE_DIRECTORY [--apply]" >&2
  exit 2
fi
python3 - "$marketplace" <<'PY'
import json
import hashlib
from pathlib import Path
import sys
root = Path(sys.argv[1]).resolve()
metadata = json.loads((root / '.agents/plugins/marketplace.json').read_text())
if metadata['name'] != 'tr-codex':
    raise SystemExit('unexpected marketplace identity')
source = metadata['plugins'][0]['source']
if source != {'source': 'local', 'path': './plugins/tr-codex'}:
    raise SystemExit('unexpected plugin source')
payload = root / 'plugins/tr-codex'
manifest = json.loads((payload / '.codex-plugin/plugin.json').read_text())
if manifest['name'] != 'tr-codex' or not (payload / 'assembly.json').is_file():
    raise SystemExit('missing or unexpected verified payload')
assembly = json.loads((payload / 'assembly.json').read_text())
for name, expected in assembly['files'].items():
    path = (payload / name).resolve()
    if not path.is_relative_to(payload.resolve()) or not path.is_file():
        raise SystemExit('assembly path is invalid or missing')
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit('assembly integrity mismatch: ' + name)
print('marketplace:', root)
print('plugin:', manifest['name'], manifest['version'])
PY
if [ "$mode" = --apply ]; then
  codex plugin marketplace add "$marketplace"
  codex plugin add tr-codex@tr-codex
else
  printf '[dry-run] codex plugin marketplace add %q\n' "$marketplace"
  printf '[dry-run] codex plugin add tr-codex@tr-codex\n'
fi
echo 'Existing plugins and global AGENTS.md are unchanged. Follow ROLLOUT.md for takeover and rollback.'
