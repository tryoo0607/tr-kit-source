#!/usr/bin/env bash
# auth-warn — SessionStart 훅. 세션 열 때 Claude Code 인증 만료/임박이면 경고를 컨텍스트로 주입.
#
# 감지 로직은 bin `claude-auth-check`(셸 채널)에 있음 — 여기선 그걸 호출해 결과를 stdout으로.
# SessionStart 훅의 stdout = 세션 컨텍스트에 추가됨. 정상이면 아무것도 안 냄.
#
# 원칙: 세션 시작을 절대 막지 않는다(문제 시 조용히 exit 0).
set -uo pipefail

CHK="$HOME/.local/bin/claude-auth-check"
[ -x "$CHK" ] || exit 0            # bin 미설치면 스킵

msg="$("$CHK" 2>&1 1>/dev/null)" || true   # 경고는 stderr로 나옴 → 캡처
[ -n "$msg" ] && printf '🔐 %s\n' "$msg"
exit 0
