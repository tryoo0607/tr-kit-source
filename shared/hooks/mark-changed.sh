#!/usr/bin/env bash
# mark-changed — PostToolUse(Write·Edit). "이 턴에 파일을 고쳤다"를 마크.
#
# 왜: Stop 훅이 **매 턴** 기록을 요구하면 오탐이 많다(대화만 하는 턴).
#     "실제로 뭔가 바꿨는데 기록을 안 한 경우"만 잡으려면 변경 사실이 필요하다.
#
# 마크는 mtime 이 전부다 — 내용은 안 쓴다. Stop 이 state 파일 mtime 과 비교한다.
#
# 원칙: 절대 작업을 막지 않는다(exit 0).
set -uo pipefail
. "${CLAUDE_PLUGIN_ROOT:?}/hooks/lib.sh" 2>/dev/null || exit 0

input="$(cat 2>/dev/null || true)"

sid="default"
if command -v jq >/dev/null 2>&1; then
  sid="$(printf '%s' "$input" | jq -r '.session_id // "default"' 2>/dev/null || echo default)"
fi

# 🔑 기록 자체를 고친 건 마크하지 않는다 — 안 그러면 영원히 안 풀린다
path="" tool="" cmd=""
if command -v jq >/dev/null 2>&1; then
  path="$(printf '%s' "$input" | jq -r '.tool_input.file_path // ""' 2>/dev/null || true)"
  tool="$(printf '%s' "$input" | jq -r '.tool_name // ""' 2>/dev/null || true)"
  cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // ""' 2>/dev/null || true)"
fi
record_path=false
case "$path" in
  "$HOME"/projects/_docs/*|*/_local-docs/*) record_path=true ;;
esac
# Bash 도구는 file_path를 주지 않으므로 raw command에서 기록 저장소 경계를 보완한다.
# 실제 변경 명령인지 여부는 아래 공통 코어가 별도로 판정한다.
case "$cmd" in
  *"$HOME/projects/_docs/"*|*"~/projects/_docs/"*|*"/_local-docs/"*) record_path=true ;;
esac

# ── raw tool payload를 normalized event로 바꾼 뒤 공통 코어가 변경 여부를 판정한다.
# Bash 문자열 포함 매칭은 폐기했다. 코어 lexer가 quoted prose를 가리고 실제 명령·출력
# redirection만 본다. 애매하면 마크하지 않아 조회 세션을 막는 것보다 false negative를 택한다.
lifecycle_core="${CLAUDE_PLUGIN_ROOT:?}/hooks/core/decision.py"
command -v jq >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1 \
  && [ -r "$lifecycle_core" ] || exit 0
kind="file_write"; [ "$tool" = "Bash" ] && kind="command"
event="$(jq -nc \
  --arg sid "$sid" --arg kind "$kind" --arg command "$cmd" --argjson record_path "$record_path" \
  '{schema_version:1,event:"tool.completed",session:{id:$sid},tool:{kind:$kind,command:$command,record_path:$record_path}}')"
action="$(printf '%s' "$event" | python3 "$lifecycle_core" 2>/dev/null \
  | jq -r '.action // "none"' 2>/dev/null || true)"
[ "$action" = "change.mark" ] || exit 0

# ── 🔑 프로젝트 판정 = **고친 파일의 경로**. cwd 가 아니다. (2026-08-11)
#
# 예전엔 `tr_docs()`(cwd 기반)였다. 구멍이 둘이었다:
#   ① cwd 가 `~` 면(세션 대부분이 거기서 뜬다) 빈 값 → **exit 0 → 마크를 아예 안 찍었다.**
#      기록 강제가 **조용히 꺼져 있었다.**
#   ② 다른 프로젝트를 작업하다 kit 도구 때문에 `cd ~/projects/{{KIT_REPO}}` 하면
#      `require-record` 가 엉뚱한 프로젝트를 보고 **오탐 차단**했다
#      (cases/hooks/require-record-wrong-project.md).
#
# 🔑 *"작업한 프로젝트"* 와 *"지금 서 있는 디렉토리"* 는 다른 축이다 —
#    영역 판정에서 이미 겪은 결론이다(cases/scopes/work-scope-leaks-to-personal.md).
#
# ⚠️ Bash 는 대상 경로를 알 수 없다 → cwd 로 폴백한다. 완벽하진 않지만 예전보다 안 나쁘다.
proj=""
[ -n "$path" ] && proj="$(tr_project "$path")"
[ -n "$proj" ] || proj="$(tr_project)"
[ -n "$proj" ] || exit 0        # 어느 프로젝트에도 안 속하면 기록 강제 대상이 아니다
docs="$DOCS_ROOT/$proj"

# 🔑 tmux명 키 breadcrumb — "이 세션이 마지막으로 고친 프로젝트". (2026-08-20)
#    왜 tmux명이냐: sid 는 /clear 에 바뀌고 TMPDIR 은 휘발한다. 재개(inject-state·
#    session-check)가 cwd=`~` 세션의 것을 집으려면 **clear 를 넘어 사는** 앵커가 필요하다.
#    tr_resume_state ②단이 이걸 읽는다. (rollover·register·unrecorded 와 같은 raw #S 키)
_tn="$(tmux display-message -p '#S' 2>/dev/null || true)"
if [ -n "$_tn" ]; then
  _bcd="$(tr_state)/last-project"
  mkdir -p "$_bcd" 2>/dev/null && printf '%s\n' "$proj" > "$_bcd/$_tn" 2>/dev/null || true
fi

# 🔑 **한 턴에 한 번만 만든다. 이미 있으면 mtime 을 건드리지 않는다.** (2026-08-13)
#
# 예전엔 변경마다 `: > "$mark"` 로 **잘라 써서 mtime 이 매번 갱신**됐다.
# `require-record` 는 *"마크보다 새로운 기록이 있나"* 로 판정하는데, 실제 작업 순서는
#   ① 코드 고침 → ② `state/` 에 기록 → ③ **커밋·push·백업**
# 이라 ③이 마크를 갱신해 **방금 쓴 ②를 앞질렀다.** 기록이 있는데도 차단됐다(실측:
# 기록 14:11:54 · 마크 14:13:18). 그리고 **③은 늘 있다** — 항상 걸리는 구조였다.
#
# 이제 마크 mtime = **그 턴 첫 변경 시각**이다. 그 뒤 아무 때나 쓴 기록이 통과한다.
# 턴 경계는 그대로다 — `require-record` 가 성공·폴백 시 마크를 지운다.
mark="${TMPDIR:-/tmp}/tr-changed-${sid}"
[ -e "$mark" ] || : > "$mark" 2>/dev/null || true

# 🔑 **어느 프로젝트를 고쳤는지**를 같이 남긴다 — `require-record` 의 판정 재료다.
#    한 턴에 여러 프로젝트를 고칠 수 있으므로 목록이다(중복은 안 넣는다).
pf="${TMPDIR:-/tmp}/tr-changed-projects-${sid}"
grep -qxF "$proj" "$pf" 2>/dev/null || printf '%s\n' "$proj" >> "$pf" 2>/dev/null || true

# ── 🔑 작업이 길어지면 state/ 를 만들라고 알린다
# 왜 3회냐: 파일 하나 고치고 끝나는 휘발성 작업엔 걸리지 않게. lazy 원칙 그대로다.
#   Stop 훅은 "끝낼 때"만 강제해서 **진행 중 가시성**의 자리가 비어 있었다
#   (2026-08-06 감사 — 세션 내내 state/ 가 하나도 없었다).
STATE_HINT_AT=3
cf="${TMPDIR:-/tmp}/tr-edits-${sid}"
n=$(cat "$cf" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$cf" 2>/dev/null || true

if [ "$n" = "$STATE_HINT_AT" ] && \
   [ -z "$(find "$docs/state" -maxdepth 1 -name '*.md' -print -quit 2>/dev/null)" ]; then
  cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"📌 파일을 3번째 고쳤다. 작업이 길어지고 있으니 `state/<slug>.md` 를 지금 만들어라 — 지금 단계·요구·결정·미결. 형식 = LOCAL-DOCS-SCHEMA.md. 이게 있어야 진행 상황이 사람에게 보이고, 롤오버 때 재주입된다."}}
JSON
fi
exit 0
