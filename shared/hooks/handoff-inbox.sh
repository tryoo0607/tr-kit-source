#!/usr/bin/env bash
# handoff-inbox — SessionStart. configured handoff repository의 수신함.
#
# 왜: clear 인계는 mtime 으로 자동 판정된다(같은 디스크·초 단위 연속). 머신간은 그게
#     무너진다 — 받는 세션이 며칠 뒤에 열리고, mtime 은 "누가 마지막에 만졌나"지
#     "내가 받을 게 뭔가"가 아니다. 그래서 **유저가 포인터를 줘야** 했다.
#
#     수신함 모델이 그걸 없앤다: **"이 머신 앞으로 온 것 중 미처리"** 를 훅이 센다.
#
# 처리 표시 = **`done/` 하위로 이동**. 파일 안 상태 필드가 아니라 위치로 표시한다 —
#   grep 이 아니라 `ls` 로 판정되어야 훅이 싸다.
#
# ⚠️ 네트워크가 세션 시작을 붙잡지 않게 한다: fetch 는 `timeout` 으로 자르고,
#    10분 스로틀을 건다. fetch 가 실패해도 **가진 `origin/main` 으로 목록은 낸다.**
#
# 원칙: 세션 시작을 절대 막지 않는다(exit 0).
set -uo pipefail
. "${CLAUDE_PLUGIN_ROOT:?}/hooks/lib.sh" 2>/dev/null || exit 0

repo="$(tr_profile_get public.repositories.handoffs || true)"
box="$(tr_profile_get public.handoff.inbox || true)"
[ -d "$repo/.git" ] || exit 0
case "$box" in
  ""|/*|.|./|../*|*/../*|*/..) exit 0 ;;
esac

# ── fetch (스로틀 10분 · 4초 상한). 실패해도 계속 간다.
fh="$repo/.git/FETCH_HEAD"
if [ ! -e "$fh" ] || [ -z "$(find "$fh" -newermt '-10 minutes' -print -quit 2>/dev/null)" ]; then
  timeout 4 git -C "$repo" fetch --quiet origin main >/dev/null 2>&1 || true
fi

ref="origin/main"
git -C "$repo" rev-parse --verify --quiet "$ref" >/dev/null 2>&1 || ref="HEAD"

mapfile -t pend < <(
  git -C "$repo" ls-tree -r --name-only "$ref" -- "$box" 2>/dev/null \
    | grep -v "/done/" | grep -v '/\.gitkeep$'
)
[ "${#pend[@]}" -gt 0 ] || exit 0

printf '\n## 📬 수신함 — `%s` 앞으로 미처리 %s건\n\n' "$box" "${#pend[@]}"
for p in "${pend[@]}"; do printf -- '- `%s`\n' "$p"; done
printf '\n`%s` 의 `%s` 다. **유저가 포인터를 줄 필요가 없다** — 이게 그 자리다.\n' "$repo" "$ref"
printf '이어받으라는 요청이면 `git -C "%s" pull` 후 해당 파일을 읽어라.\n' "$repo"
printf '처리를 마치면 **`%s/done/` 으로 옮겨** 커밋한다 — 위치가 곧 처리 표시다.\n' "$box"
printf '(요청이 없으면 목록만 알리고 넘어간다. 스스로 착수하지 않는다)\n\n'
exit 0
