#!/usr/bin/env bash
# session-end — SessionEnd. **preClear 가 없어서 생긴 자리를 메운다.**
#
# 🔑 `/clear` 앞에 도는 훅은 **존재하지 않는다** (2026-08-07 공식 문서 확인).
#    SessionEnd 는 사후이고 `exit 2` 로 막지도 못한다. 그래서 여기서 하는 일은
#    "막기"가 아니라 **"손실의 흔적을 남기기"** 다:
#
#      기록 없이 끊겼다  →  흔적 파일  →  다음 세션의 SessionStart 가 읽고 복구
#
#    막을 수 없으면 **알아채기라도 해야 한다.** 조용히 사라지는 게 제일 나쁘다.
#    (2026-08-07 실측: `state/handoff-repo.md` 가 이미 끝난 일을 미결로 적은 채 인계됐다)
#
# 판정 재료: `mark-changed` 가 남긴 `tr-changed-<sid>`.
#   Stop 훅(require-record)이 기록을 확인하면 이 마크를 **지운다**.
#   그러므로 **여기서 마크가 살아 있다 = 고쳤는데 기록이 없다.**
#
# 키가 sid 가 아닌 이유: `/clear` 는 새 session_id 를 만든다. 끊긴 세션과 이어받을
#   세션을 잇는 유일한 공통 축이 **tmux 세션 이름**이다.
#
# 원칙: 세션 종료를 절대 방해하지 않는다(exit 0).
set -uo pipefail
. "${CLAUDE_PLUGIN_ROOT:?}/hooks/lib.sh" 2>/dev/null || exit 0

input="$(cat 2>/dev/null || true)"
command -v jq >/dev/null 2>&1 || exit 0

get() { printf '%s' "$input" | jq -r "$1 // \"\"" 2>/dev/null || true; }
sid="$(get .session_id)"
[ -n "$sid" ] || exit 0

mark="${TMPDIR:-/tmp}/tr-changed-${sid}"
[ -e "$mark" ] || exit 0        # 기록이 끝났거나 아무것도 안 고쳤다 → 남길 게 없다

key="$(tmux display-message -p '#S' 2>/dev/null || echo default)"
d="$(tr_state)/unrecorded"
mkdir -p "$d" 2>/dev/null || exit 0

{
  printf 'reason\t%s\n'     "$(get .reason)"
  printf 'when\t%s\n'       "$(date '+%Y-%m-%d %H:%M:%S')"
  printf 'sid\t%s\n'        "$sid"
  printf 'cwd\t%s\n'        "$(get .cwd)"
  printf 'transcript\t%s\n' "$(get .transcript_path)"
} > "$d/$key" 2>/dev/null || true

rm -f "$mark" 2>/dev/null || true
exit 0
