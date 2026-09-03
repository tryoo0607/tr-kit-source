#!/usr/bin/env bash
# require-record — Stop. 파일을 고쳤는데 기록을 안 했으면 응답을 못 끝내게 한다.
#
# 이게 "기록은 반드시 남긴다"를 L4(규율)에서 **L3(강제)** 로 올린다.
# 규율은 잊히지만 이건 exit 2 로 실제로 막는다. (T8 에서 실측 확인: 2회 차단됨)
#
# 판정: 변경 마크(PostToolUse)가 있고, state/*.md 중 그보다 새 것이 없으면 → 막는다.
#       mtime 비교라 셸에서 정확히 된다.
#
# 🔑 교착 방지 — 게이트(이 훅)와 정책(권한)은 서로 다른 걸 막는다.
#    훅이 "써라"고 해도 Write 권한이 없으면 모델은 끝낼 수도, 쓸 수도 없다(T8 실측).
#    그래서 두 겹으로 푼다:
#      C) {{HOST_SETTINGS}} 이 `_docs/` 쓰기를 미리 allow 한다  → 애초에 안 막힌다
#      B) 그래도 못 쓰면 N회 후 **훅이 직접 최소 기록을 남기고** 통과시킨다
#    강제가 사람을 가두면 안 된다. 기록이 목적이지 차단이 목적이 아니다.
set -uo pipefail
. "${CLAUDE_PLUGIN_ROOT:?}/hooks/lib.sh" 2>/dev/null || exit 0

MAX_BLOCKS=2            # 이만큼 막고도 안 되면 B 로 넘어간다

input="$(cat 2>/dev/null || true)"
sid="default"
if command -v jq >/dev/null 2>&1; then
  sid="$(printf '%s' "$input" | jq -r '.session_id // "default"' 2>/dev/null || echo default)"
  # 훅이 부른 응답에서 또 부르는 루프 방지
  if [ "$(printf '%s' "$input" | jq -r '.stop_hook_active // false' 2>/dev/null)" = "true" ]; then
    : # 아래 카운터가 이미 처리한다. 여기선 참고만.
  fi
fi

mark="${TMPDIR:-/tmp}/tr-changed-${sid}"
[ -e "$mark" ] || exit 0        # 이 턴에 아무것도 안 고쳤다 → 볼 것 없음

# ── 🔑 판정 축 = **이 턴에 고친 파일이 속한 프로젝트들**. cwd 가 아니다. (2026-08-11)
#    `mark-changed` 가 남긴 목록을 쓴다. 예전엔 `tr_docs()`(cwd)라서,
#    다른 repo를 고치고 거기 기록했는데도 **cwd가 현재 project면 차단**됐다
#    (cases/hooks/require-record-wrong-project.md).
pf="${TMPDIR:-/tmp}/tr-changed-projects-${sid}"
projs=""
[ -r "$pf" ] && projs="$(cat "$pf" 2>/dev/null || true)"
if [ -z "$projs" ]; then                 # 옛 세션 호환 — 목록이 없으면 예전처럼 cwd
  projs="$(tr_project)"
fi
[ -n "$projs" ] || { rm -f "$mark"; exit 0; }

# state/ 또는 exec/ 에 마크보다 새 파일이 있나 = 기록했나
#   🔑 exec/ 도 봐야 한다 — 안 그러면 "끝난 작업은 exec 로 옮겨라"라고 시켜놓고
#      옮겨도 안 풀린다(2026-08-06 첫 실사용에서 발견). 마무리한 작업이 제일 흔한 경우다.
#   ⚠️ **한 곳이라도 기록됐으면 통과**시킨다. 한 턴에 여러 프로젝트를 고쳤을 때
#      전부에 기록을 요구하면 오탐이 된다 — 대개 한 작업이고 기록도 하나다.
docs=""
fresh=false
while IFS= read -r proj; do
  [ -n "$proj" ] || continue
  [ -n "$docs" ] || docs="$DOCS_ROOT/$proj"      # 안내문에 쓸 대표 경로 = 첫 번째
  for d in state exec; do
    [ -d "$DOCS_ROOT/$proj/$d" ] || continue
    if [ -n "$(find "$DOCS_ROOT/$proj/$d" -maxdepth 1 -name '*.md' -newer "$mark" -print -quit 2>/dev/null)" ]; then
      fresh=true
      break 2
    fi
  done
done <<EOF
$projs
EOF
[ -n "$docs" ] || { rm -f "$mark" "$pf"; exit 0; }

cnt_f="${TMPDIR:-/tmp}/tr-record-blocks-${sid}"
cnt=$(cat "$cnt_f" 2>/dev/null || echo 0)
lifecycle_core="${CLAUDE_PLUGIN_ROOT:?}/hooks/core/decision.py"
command -v jq >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1 \
  && [ -r "$lifecycle_core" ] || exit 0
event="$(jq -nc --arg sid "$sid" --argjson fresh "$fresh" --argjson count "$cnt" \
  --argjson max "$MAX_BLOCKS" \
  '{schema_version:1,event:"response.stopping",session:{id:$sid},record:{changed:true,fresh:$fresh,block_count:$count,max_blocks:$max}}')"
result="$(printf '%s' "$event" | python3 "$lifecycle_core" 2>/dev/null || true)"
action="$(printf '%s' "$result" | jq -r '.action // "record.pass"' 2>/dev/null || true)"

if [ "$action" = "record.pass" ]; then
  rm -f "$mark" "$pf" "$cnt_f"
  exit 0
fi

if [ "$action" = "record.block" ]; then
  cnt="$(printf '%s' "$result" | jq -r '.data.next_block_count // 1')"
  printf '%s\n' "$cnt" > "$cnt_f"
  { printf '파일을 고쳤는데 작업 기록이 갱신되지 않았다. 끝내기 전에 남겨라.\n\n'
    printf '  %s/state/<slug>.md\n' "$docs"
    # 한 턴에 여러 프로젝트를 고쳤으면 **어디든 한 곳**에 남기면 풀린다 — 후보를 보여준다.
    n_p="$(printf '%s\n' "$projs" | grep -c . || true)"
    if [ "${n_p:-1}" -gt 1 ]; then
      printf '\n이 턴에 고친 프로젝트가 %s개다 — **어디든 한 곳**에 남기면 된다:\n' "$n_p"
      printf '%s\n' "$projs" | sed 's#^#  · ~/projects/_docs/#'
    fi
    printf '\n무엇을 했고, 무엇을 가정했고, 무엇이 확신 없는지. 형식 = LOCAL-DOCS-SCHEMA.md.\n'
    printf '이미 끝난 작업이면 exec/ 로 옮겨라. (%s/%s — 이후엔 훅이 최소 기록만 남기고 통과시킨다)\n' \
      "$cnt" "$MAX_BLOCKS"
  } >&2
  exit 2
fi

# ── B. 여기까지 왔으면 모델이 못 쓴 것이다(권한·환경). 훅이 직접 남긴다.
#     내용은 빈약하지만 **"고쳤는데 기록이 없다"는 구멍은 막는다.**
mkdir -p "$docs/state" 2>/dev/null || true
fallback="$docs/state/_unrecorded.md"
# 🔑 헤더는 append 블록 밖에서 쓴다 — `{ [ -e ] || ... } >> f` 는 리다이렉트가
#    블록보다 먼저 파일을 만들어 `[ -e ]` 가 언제나 참이 된다(2026-08-06 실사용에서 발견).
if [ ! -e "$fallback" ]; then
  printf '# 기록되지 않은 변경 (훅 자동 생성)\n\n훅이 남긴 것이라 내용이 없다. **사람이 채우거나 지운다.**\n무엇을 고쳤는지는 `git log` 나 세션 트랜스크립트를 봐야 한다.\n\n' \
    > "$fallback" 2>/dev/null || true
fi
printf -- '- %s · 세션 `%s` — 파일 변경이 있었으나 상태 파일이 갱신되지 않았다\n' \
  "$(date '+%Y-%m-%d %H:%M')" "${sid:0:8}" >> "$fallback" 2>/dev/null || true

rm -f "$mark" "$cnt_f" "$pf"
printf '⚠️ 기록이 없어 훅이 `state/_unrecorded.md` 에 한 줄 남겼다. 내용은 사람이 채워야 한다.\n' >&2
exit 0
