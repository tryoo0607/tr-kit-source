#!/usr/bin/env bash
# kit-verify — Stop. kit source를 고쳤으면 빠른 hard validation까지가 한 벌이다.
#
# source와 생성 target은 다른 저장소다. 현재 Stop event의 cwd에서 source worktree를
# 식별하며, target 이름이나 ~/projects 아래의 고정 경로를 추측하지 않는다.
# 전체 unit/integration 검증은 `python3 tools/validate.py full`과 CI가 소유한다.
set -uo pipefail
. "${CLAUDE_PLUGIN_ROOT:?}/hooks/lib.sh" 2>/dev/null || exit 0

MAX_BLOCKS=2
input="$(cat 2>/dev/null || true)"
sid="default"
event_cwd=""
if command -v jq >/dev/null 2>&1; then
  sid="$(printf '%s' "$input" | jq -r '.session_id // "default"' 2>/dev/null || echo default)"
  event_cwd="$(printf '%s' "$input" | jq -r '.cwd // ""' 2>/dev/null || true)"
fi

is_source_root() {
  local root="${1:-}"
  [ -n "$root" ] \
    && [ -f "$root/recipes/_schema.toml" ] \
    && [ -f "$root/core/contracts/pack-v1.toml" ] \
    && [ -f "$root/tools/build.py" ] \
    && [ -f "$root/tools/validate.py" ]
}

repo=""
for candidate in "${TR_KIT_SOURCE_ROOT:-}" "$event_cwd" "$PWD"; do
  [ -n "$candidate" ] || continue
  root="$(git -C "$candidate" rev-parse --show-toplevel 2>/dev/null || true)"
  if is_source_root "$root"; then
    repo="$root"
    break
  fi
done
[ -n "$repo" ] || exit 0

head="$(git -C "$repo" rev-parse HEAD 2>/dev/null || true)"
dirty="$(git -C "$repo" status --porcelain 2>/dev/null | head -1)"
worktree_fingerprint() {
  {
    printf 'HEAD %s\n' "$head"
    git -C "$repo" diff --binary HEAD -- 2>/dev/null || true
    git -C "$repo" ls-files --others --exclude-standard 2>/dev/null | while IFS= read -r relative; do
      printf 'UNTRACKED %s ' "$relative"
      git hash-object -- "$repo/$relative" 2>/dev/null || true
    done
  } | git hash-object --stdin 2>/dev/null
}

fingerprint="$(worktree_fingerprint)"
repo_key="$(printf '%s' "$repo" | cksum | awk '{print $1}')"
seen_f="${TMPDIR:-/tmp}/tr-kit-seen-${sid}-${repo_key}"
seen="$(cat "$seen_f" 2>/dev/null || true)"

[ "$fingerprint" != "$seen" ] || exit 0
if [ -z "$seen" ] && [ -z "$dirty" ]; then
  printf '%s' "$fingerprint" > "$seen_f" 2>/dev/null
  exit 0
fi

cnt_f="${TMPDIR:-/tmp}/tr-kit-blocks-${sid}-${repo_key}"
if ! vout="$(python3 "$repo/tools/validate.py" hook 2>&1)"; then
  cnt="$(cat "$cnt_f" 2>/dev/null || echo 0)"
  cnt=$((cnt + 1))
  printf '%s\n' "$cnt" > "$cnt_f" 2>/dev/null || true
  if [ "$cnt" -le "$MAX_BLOCKS" ]; then
    {
      printf 'kit source를 고쳤는데 hook validation이 실패한다. 끝내기 전에 고쳐라.\n\n'
      printf '%s\n' "$vout" | tail -30
      printf '\n(%s/%s — 이후엔 통과시키되 실패를 알린다)\n' "$cnt" "$MAX_BLOCKS"
    } >&2
    exit 2
  fi
  printf '⚠️ hook validation이 실패한 채로 넘어간다 (%s회). 유저에게 알려라.\n' "$cnt" >&2
  printf '%s' "$fingerprint" > "$seen_f" 2>/dev/null || true
  rm -f "$cnt_f" 2>/dev/null || true
  exit 0
fi

rm -f "$cnt_f" 2>/dev/null || true
printf '%s' "$fingerprint" > "$seen_f" 2>/dev/null || true
exit 0
