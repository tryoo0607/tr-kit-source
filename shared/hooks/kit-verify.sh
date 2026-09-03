#!/usr/bin/env bash
# kit-verify — Stop. **kit 을 고쳤으면 검수까지가 한 벌이다.**
#
# 왜: `validate`·`kit-audit` 은 있는데 **아무것도 자동 실행하지 않았다.** 순전히 내 규율이라
#     잊혔다 — 2026-08-07 실측: 훅을 4번 고치고 3번 커밋하는 동안 `validate` 0회.
#     유저가 물어서 돌렸더니 `kit-audit` 이 즉시 잡았다(README 가 v0.7.20·훅 7 로 뒤처짐).
#     **규율(L4)이 실패한 자리를 훅(L3)으로 옮긴다.**
#
# 비용이 없다: 실측 `validate` 0.08초 · `kit-audit` 0.10초. Stop 타임아웃의 1% 다.
#
# 발동 조건 = **이 세션에서 kit repo 가 실제로 바뀌었나**. 두 신호를 본다:
#   ① 워킹트리가 dirty (커밋 전 편집)
#   ② HEAD 가 마지막 검사 때와 다르다 (커밋됨)
#   → 검사 후 HEAD 를 저장해 **같은 상태를 두 번 검사하지 않는다**(도배·교착 방지).
#
# 원칙: `validate` 는 게이트(차단), `kit-audit` 은 report-first(주입만).
set -uo pipefail
. "${CLAUDE_PLUGIN_ROOT:?}/hooks/lib.sh" 2>/dev/null || exit 0

MAX_BLOCKS=2            # 못 고치면 교착 대신 통과시킨다 (require-record 와 같은 규율)

repo="$PROJECTS/{{KIT_REPO}}"
[ -d "$repo/.git" ] || exit 0
[ -x "$repo/setup/tools/validate" ] || exit 0

input="$(cat 2>/dev/null || true)"
sid="default"
command -v jq >/dev/null 2>&1 && \
  sid="$(printf '%s' "$input" | jq -r '.session_id // "default"' 2>/dev/null || echo default)"

head="$(git -C "$repo" rev-parse HEAD 2>/dev/null || true)"
dirty="$(git -C "$repo" status --porcelain 2>/dev/null | head -1)"
seen_f="${TMPDIR:-/tmp}/tr-kit-seen-${sid}"
seen="$(cat "$seen_f" 2>/dev/null || true)"

# 깨끗하고 HEAD 도 그대로면 볼 것이 없다
[ -n "$dirty" ] || [ "$head" != "$seen" ] || exit 0
# 첫 턴에 아무것도 안 바꿨는데 도는 걸 막는다 — seen 이 비었고 clean 이면 기록만 하고 빠진다
if [ -z "$seen" ] && [ -z "$dirty" ]; then printf '%s' "$head" > "$seen_f" 2>/dev/null; exit 0; fi

cnt_f="${TMPDIR:-/tmp}/tr-kit-blocks-${sid}"

if ! vout="$("$repo/setup/tools/validate" 2>&1)"; then
  cnt=$(cat "$cnt_f" 2>/dev/null || echo 0); cnt=$((cnt + 1)); echo "$cnt" > "$cnt_f" 2>/dev/null || true
  if [ "$cnt" -le "$MAX_BLOCKS" ]; then
    {
      printf 'kit 을 고쳤는데 `validate` 가 실패한다. 끝내기 전에 고쳐라.\n\n'
      printf '%s\n' "$vout" | tail -20
      printf '\n(%s/%s — 이후엔 훅이 통과시키되 유저에게 알린다)\n' "$cnt" "$MAX_BLOCKS"
    } >&2
    exit 2
  fi
  printf '⚠️ **`validate` 가 실패한 채로 넘어간다** (%s회 시도). 유저에게 알려라.\n' "$cnt"
fi

# ── 훅 회귀 테스트 — `validate` 와 같은 등급의 게이트
# 왜 여기냐: 훅은 kit 자산의 절반(846줄)인데 고쳐도 아무것도 안 돌았다.
#   실측 2.2초/25케이스 → Stop 타임아웃(15초)에 여유 있게 들어간다.
#   ⚠️ `hook-test` 는 샌드박스에서 돌아 이 훅을 재귀 호출하지 않는다(가짜 repo 를 쓴다).
if [ -x "$repo/setup/tools/hook-test" ] && [ -d "$repo/tests/hooks" ]; then
  if ! tout="$("$repo/setup/tools/hook-test" 2>&1)"; then
    # 🔑 flake 계측 — `hook-test` 는 **재현 안 되는 간헐 실패**가 있다(state/hook-test-flake.md,
    #    4회 발생·수동 재실행은 늘 통과). kit-verify(Stop)가 주는 env 만이 유일한 미지수라
    #    **실패 그 순간의 env·locale·PATH·실패케이스를 박제**한다. 다음 발생 때 현장 증거가 된다.
    #    ⚠️ 재실행은 안 한다(Stop 타임아웃 15초 — hook-test 1회 ≈ 11초라 두 번 돌면 넘긴다).
    dump="$(tr_state)/flake-dump/$(date +%Y%m%d-%H%M%S)-$$"
    mkdir -p "$(dirname "$dump")" 2>/dev/null && {
      echo "== hook-test 실패 스냅샷 ($(date '+%F %T')) =="
      echo "-- 실패 케이스 --"; printf '%s\n' "$tout" | grep -E '❌|없음:|있으면|파일'
      echo "-- locale --"; locale 2>&1
      echo "-- LANG/LC/TMUX --"; echo "LANG=${LANG:-} LC_ALL=${LC_ALL:-} LC_CTYPE=${LC_CTYPE:-} TMUX=${TMUX:-(unset)}"
      echo "-- PATH --"; echo "${PATH:-}"
      echo "-- 도구 --"; for t in grep sed awk jq bash cksum locale; do printf '%s: ' "$t"; command -v "$t" 2>&1; done
      echo "-- env --"; env | sort
    } > "$dump" 2>&1
    cnt=$(cat "$cnt_f" 2>/dev/null || echo 0); cnt=$((cnt + 1)); echo "$cnt" > "$cnt_f" 2>/dev/null || true
    if [ "$cnt" -le "$MAX_BLOCKS" ]; then
      {
        printf '훅을 고쳤는데 `hook-test` 가 실패한다. 끝내기 전에 고쳐라.\n\n'
        printf '%s\n' "$tout" | grep -E '❌|없음:|있으면|파일' | head -20
        printf '\n(%s/%s — 이후엔 훅이 통과시키되 유저에게 알린다)\n' "$cnt" "$MAX_BLOCKS"
      } >&2
      exit 2
    fi
    printf '⚠️ **`hook-test` 가 실패한 채로 넘어간다** (%s회 시도). 유저에게 알려라.\n' "$cnt"
  fi
fi

rm -f "$cnt_f" 2>/dev/null || true
printf '%s' "$head" > "$seen_f" 2>/dev/null || true

# ── kit-audit 은 차단하지 않는다 — 지적이 있으면 다음 턴에 보이게 주입만.
[ -x "$repo/setup/tools/kit-audit" ] || exit 0
aout="$("$repo/setup/tools/kit-audit" 2>&1 || true)"

# ⚠️ 문자열로 판정하지 않는다. `kit-audit` 은 지적이 있어도 **`✅ 군살 없음` 을 같이 찍고
#    exit 0 으로 끝난다**(2026-08-07 실측: 드리프트 2건 + "군살 없음" + exit 0).
#    그래서 **`[섹션] N건` 의 N 을 합산**한다. 이게 유일하게 믿을 수 있는 신호다.
n="$(printf '%s\n' "$aout" | sed -n 's/.*\] \([0-9]\{1,\}\)건.*/\1/p' | awk '{s+=$1} END{print s+0}')"

# 🔑 스로틀 — 같은 지적을 매 Stop 반복하지 않는다(cry-wolf 방지). `aout` 이 바뀔 때만 알린다.
#    왜: 워킹트리가 dirty 로 오래 남으면(진행 중 편집) 이 훅이 매 Stop 돌아 **같은 드리프트를
#    도배**한다(2026-08-20 실측: 보류한 인계서 드리프트가 수십 턴 반복). "상시 뜨는 알림 =
#    안 보는 알림"은 kit 독트린이 경고하는 병이라, 여기서 **내용이 바뀔 때만** 알리게 막는다.
#    키 = sid(세션 수명 동안만 억제하면 충분). 버전·건수가 바뀌면 해시가 달라져 다시 알린다.
audit_seen_f="${TMPDIR:-/tmp}/tr-kit-audit-seen-${sid}"
if [ "${n:-0}" -le 0 ] 2>/dev/null; then rm -f "$audit_seen_f" 2>/dev/null || true; exit 0; fi
ahash="$(printf '%s' "$aout" | cksum | cut -d' ' -f1)"
[ "$(cat "$audit_seen_f" 2>/dev/null || true)" = "$ahash" ] && exit 0   # 이미 알린 것과 동일 → 조용
printf '%s' "$ahash" > "$audit_seen_f" 2>/dev/null || true

msg="⚠️ kit-audit 지적 ${n}건 (차단 아님 — 유저에게 알리고 판단을 받아라):\n$(printf '%s' "$aout" | grep -A3 -E '\] [1-9][0-9]*건' | tail -15)"
if command -v jq >/dev/null 2>&1; then
  jq -cn --arg m "$msg" \
    '{hookSpecificOutput:{hookEventName:"Stop",additionalContext:$m}}' 2>/dev/null || true
fi
exit 0
