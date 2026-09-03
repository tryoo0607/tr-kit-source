#!/usr/bin/env bash
# inject-hot-rules — 플러그인 root CLAUDE.md(hot 규칙)를 세션 컨텍스트로 주입.
#
# 왜: 플러그인 root의 CLAUDE.md는 Claude Code가 자동 로드하지 않는다.
#     기존 해법은 ~/.claude/CLAUDE.md 의 @import 였으나 **로컬 clone 경로 하드코딩**이라
#     포터블하지 않았다. SessionStart 훅은 ${CLAUDE_PLUGIN_ROOT} 로 해결되므로
#     플러그인만 설치하면 어느 머신에서든 동작한다.
#
# 사양: SessionStart 훅의 plain stdout 은 그대로 세션 컨텍스트에 추가된다.
#       matcher 생략 = startup·resume·clear·compact·fork 전부 매칭.
#       compact 는 창을 비우는 동작이므로 전문을 다시 싣지 않고 핵심 포인터만 넣는다.
#
# 원칙: 세션 시작을 절대 막지 않는다. 문제가 있으면 조용히 빠진다(exit 0).
set -uo pipefail

RULES="${CLAUDE_PLUGIN_ROOT:-}/CLAUDE.md"

[ -n "${CLAUDE_PLUGIN_ROOT:-}" ] || exit 0
[ -r "$RULES" ] || exit 0

input="$(cat 2>/dev/null || true)"
source_kind=""
if command -v jq >/dev/null 2>&1; then
  source_kind="$(printf '%s' "$input" | jq -r '.source // ""' 2>/dev/null || true)"
fi

if [ "$source_kind" = "compact" ]; then
  cat <<'EOF'
<!-- compact 최소 hot 규칙 -->
기본 한국어, 사실·근거 우선. 되돌리기 어렵거나 외부로 나가는 액션은 실행 전 확인한다.
백본 단계·가정·확신 없는 것을 드러내고, 파일 변경은 `_local-docs`에 기록한다.
상세 전역 정책이 필요하면 `${CLAUDE_PLUGIN_ROOT}/CLAUDE.md`를 직접 읽어라.
EOF
  exit 0
fi

cat "$RULES"
