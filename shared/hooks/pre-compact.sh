#!/usr/bin/env bash
# pre-compact — PreCompact. **넛지가 실패했을 때의 마지막 관문.**
#
# 왜: 사전 넛지는 **유저가 롤오버 안내에 반응한다**는 전제 위에 있다. 그런데 auto-compact 는
#     유저를 안 거친다 — 임계를 한 턴에 건너뛰면 컨텍스트가 바로 압축된다.
#     그때 `state/` 가 낡아 있으면 **무엇을 하던 중이었는지가 사라진다.**
#
# 🔑 `/clear` 앞엔 훅이 없지만(2026-08-07 문서 확인) **compact 앞엔 있다.**
#    preClear 에서 못 한 "막고 기록부터"를 이 경로에선 할 수 있다.
#
# 판정 재료는 `session-end` 와 같다 — `mark-changed` 가 남긴 `tr-changed-<sid>`.
#   `require-record`(Stop)가 기록을 확인하면 지운다 → **여기서 살아 있으면 미기록**이다.
#
# ⚠️ **한 번만 막는다.** compact 를 계속 막으면 컨텍스트가 차오르다 API 한계에 부딪힌다.
#    막는 목적은 기록할 틈을 주는 것이지 압축을 없애는 게 아니다.
#
# ⚠️ `manual`(유저가 `/compact`) 은 **막지 않는다.** 의도한 행동을 훅이 되돌리지 않는다.
#    대신 미기록이면 알린다 — 판단은 유저가 한다.
set -uo pipefail
. "${CLAUDE_PLUGIN_ROOT:?}/hooks/lib.sh" 2>/dev/null || exit 0

input="$(cat 2>/dev/null || true)"
command -v jq >/dev/null 2>&1 || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

sid="$(printf '%s' "$input" | jq -r '.session_id // ""' 2>/dev/null || true)"
trig="$(printf '%s' "$input" | jq -r '.compaction_trigger // ""' 2>/dev/null || true)"
[ -n "$sid" ] || exit 0

mark="${TMPDIR:-/tmp}/tr-changed-${sid}"
cnt_f="${TMPDIR:-/tmp}/tr-compact-blocks-${sid}"
cnt=$(cat "$cnt_f" 2>/dev/null || echo 0)
case "$trig" in manual) ;; *) trig="auto" ;; esac
changed=false; [ -e "$mark" ] && changed=true
lifecycle_core="${CLAUDE_PLUGIN_ROOT:?}/hooks/core/decision.py"
lifecycle_adapter="${CLAUDE_PLUGIN_ROOT:?}/hooks/lifecycle-adapter.py"
[ -r "$lifecycle_core" ] && [ -r "$lifecycle_adapter" ] || exit 0
event="$(jq -nc --arg sid "$sid" --arg trigger "$trig" --argjson changed "$changed" \
  --argjson count "$cnt" \
  '{schema_version:1,event:"context.compacting",session:{id:$sid},compact:{changed:$changed,trigger:$trigger,block_count:$count}}')"
result="$(printf '%s' "$event" | python3 "$lifecycle_core" 2>/dev/null || true)"
action="$(printf '%s' "$result" | jq -r '.action // "compact.pass"' 2>/dev/null || true)"
case "$action" in
  compact.block)
    next="$(printf '%s' "$result" | jq -r '.data.next_block_count // 1')"
    printf '%s\n' "$next" > "$cnt_f" 2>/dev/null || true
    printf '%s' "$result" | python3 "$lifecycle_adapter" render-compact >&2 2>/dev/null || true
    exit 2
  ;;
  compact.warn)
    printf '%s' "$result" | python3 "$lifecycle_adapter" render-compact 2>/dev/null || true
  ;;
esac
exit 0
