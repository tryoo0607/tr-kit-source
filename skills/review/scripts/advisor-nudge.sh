#!/usr/bin/env bash
# advisor-nudge — (옵션) Stop 훅. 턴 종료 시 self-review 리마인더 주입.
#
# 기본 OFF. 자동 배선 안 함(모든 세션에 매 턴 훅 강요 방지) — 유저가 켤 때만.
# 켜는 법:
#   1) export TR_ADVISOR=on
#   2) {{HOST_SETTINGS}} 의 Stop 훅에 이 스크립트를 등록 (경로는 설치 위치에 맞게)
#      상세 = review/references/priority.md
#
# 안전: TR_ADVISOR!=on 이면 즉시 exit 0. 절대 stop 을 막지 않음(비차단, decision 없음).
#       문제 있으면 조용히 빠짐.
set -uo pipefail

cat >/dev/null 2>&1 || true      # stdin 소비(안 써도 배수)

[ "${TR_ADVISOR:-off}" = "on" ] || exit 0

# 비차단 리마인더만 — stop 을 막지 않는다(decision 없음).
cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"Stop","additionalContext":"🔍 advisor self-check(WATCHDOG 기준): ①요구 이탈 없나 ②검증 얕지 않나(성급한 '완료'?) ③안 본 각도 없나 ④삽질/오버엔지니어링 아닌가. concern↑면 마무리 전 짚기. on-track이면 무시."}}
JSON
exit 0
