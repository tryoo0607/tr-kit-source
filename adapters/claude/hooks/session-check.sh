#!/usr/bin/env bash
# session-check — SessionStart. 영역(scope) 주입 + 심링크 검사.
#
# 영역은 태그가 아니라 **런타임 판정**이다(결정 #19) — 어디서 하는 일인지는
# cwd·remote 가 안다. 그래서 여기서 판정해 해당 규칙을 주입한다.
#
# 심링크는 정본이 아니다(결정 #26). 깨져도 시스템은 안 멈춘다 — 여기서 조용히 고친다.
#
# 원칙: 세션 시작을 절대 막지 않는다(exit 0).
set -uo pipefail
. "${CLAUDE_PLUGIN_ROOT:?}/hooks/lib.sh" 2>/dev/null || exit 0

input="$(cat 2>/dev/null || true)"
source_kind="" sid=""
if command -v jq >/dev/null 2>&1; then
  source_kind="$(printf '%s' "$input" | jq -r '.source // ""' 2>/dev/null || true)"
  sid="$(printf '%s' "$input" | jq -r '.session_id // ""' 2>/dev/null || true)"
fi

generate() {

# ── /clear 는 새 대화 id 를 만든다. claude-remote 의 sessions.log 는 세션을 처음
#    만들 때 잡은 id 를 그대로 들고 있어서, 갱신하지 않으면 `restart` 가
#    **clear 하기 전 대화를 살린다**(2026-08-06 실측). 여기서 최신 id 로 덮는다.
if [ "$source_kind" = "clear" ] || [ "$source_kind" = "fork" ]; then
  log="$(tr_state)/sessions.log"
  # ⛔ **id 형식을 검증한다.** 이 로그는 `restore` 의 부활 좌표다 — 쓰레기가 한 줄 들어가면
  #    `lookup_latest` 가 그걸 집고, cycle 이 **없는 대화를 되살리려다 세션을 잃는다.**
  #    (2026-08-06 실측: 훅을 손으로 테스트하다 `session_id=t` 가 박혀 스냅샷까지 오염됐다)
  case "$sid" in
    [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]-*-*-*-*) ;;
    *) sid="" ;;
  esac
  if [ -n "$sid" ] && [ -w "$log" ] && [ -n "${TMUX:-}" ]; then
    tmux_name="$(tmux display-message -p '#S' 2>/dev/null || true)"
    canonical="${tmux_name#claude-}"
    if [ -n "$canonical" ] && [ "$canonical" != "$tmux_name" ]; then
      printf '%s\t%s\t%s\t%s\n' "$(date '+%Y-%m-%d %H:%M:%S')" \
        "$canonical" "$sid" "$PWD" >> "$log"
    fi
  fi
fi

# ── 롤오버 재개 플래그 — /clear·compact 직후 첫 프롬프트에서 inject-state 가 「재개 요약」을 띄운다.
#    키는 tmux 세션명(clear 를 넘어 안정적). sid 는 clear 때 바뀌므로 안 쓴다.
if { [ "$source_kind" = "clear" ] || [ "$source_kind" = "compact" ]; } && [ -n "${TMUX:-}" ]; then
  _tn="$(tmux display-message -p '#S' 2>/dev/null || true)"
  if [ -n "$_tn" ]; then
    _rd="$(tr_state)/rollover"
    mkdir -p "$_rd" 2>/dev/null && : > "$_rd/$_tn" 2>/dev/null || true
  fi
fi

# ── 🔑 영역 주입 — **프로젝트 판정보다 먼저 한다.**
#    영역과 프로젝트는 다른 축이다. `tr_scope` 는 project marker·env·profile을 보므로
#    `~/projects` 밖에서도 판정된다 — 오히려 거기서야말로 판정이 필요하다.
#
#    ⛔ 예전엔 이게 프로젝트 판정 **뒤**에 있어서, `~` 에서 뜬 세션은 영역 규칙을
#    통째로 못 받았다. 세션의 7/8 이 `~` 에서 뜨므로(실측 2026-08-06)
#    **회사 머신에서 work 가드가 사실상 상시 미주입**이었다. 조용한 실패였다 —
#    영역이 없어도 세션은 멀쩡히 돌기 때문에 아무도 모른다.
scope="$(tr_scope)"
sf="${CLAUDE_PLUGIN_ROOT}/scopes/${scope}.md"
if [ -r "$sf" ] && { [ "$source_kind" = "compact" ] || [ "$source_kind" = "clear" ]; }; then
  printf '<!-- 영역 판정: %s (롤오버 최소 주입) -->\n\n' "$scope"
  case "$scope" in
    work)
      printf '회사 자산은 사내 저장소·로컬에만 둔다. 개인 GitHub·외부 MCP·Artifact로 반출 금지. secret 평문 금지.\n'
    ;;
    *)
      printf '정책·가드는 전역과 영역 규칙의 합집합이다. 상세는 `scopes/%s.md`를 필요할 때 읽어라.\n' "$scope"
    ;;
  esac
  printf '\n'
elif [ -r "$sf" ]; then
  printf '<!-- 영역 판정: %s (project marker·env·profile 기준) -->\n\n' "$scope"
  cat "$sf"
  printf '\n'
else
  # ⛔ 조용히 넘어가지 않는다. `opensource` 는 판정은 되는데 규칙 파일이 아직 없다 —
  #    아무 말도 안 하면 "규칙이 없다"와 "규칙을 못 찾았다"가 구분되지 않는다.
  printf '<!-- 영역 판정: %s -->\n\n' "$scope"
  printf '⚠️ 영역이 **%s** 로 판정됐는데 `scopes/%s.md` 가 없다.\n' "$scope" "$scope"
  printf '전역 정책만으로 진행하되, **영역 규칙이 비어 있다는 걸 알고** 판단해라.\n\n'
fi

# ── 🔑 직전 세션이 **기록 없이 끊겼나** (preClear 대체 — `session-end.sh` 가 남긴다)
#    `/clear` 를 막을 방법이 없으니 사후에 잡는다. 영역 주입 다음, 프로젝트 판정 **앞**에
#    둔다 — cwd 와 무관하게 떠야 하는 알림이다(`~` 에서 뜬 세션이 대부분이다).
ukey="$(tmux display-message -p '#S' 2>/dev/null || echo default)"
ufile="$(tr_state)/unrecorded/$ukey"
if [ -r "$ufile" ]; then
  printf '\n⚠️ **직전 세션이 기록 없이 끊겼다.** 유저에게 알려라.\n\n'
  sed 's/^/    /' "$ufile" 2>/dev/null
  printf '\n파일을 고쳤는데 `state/`·`exec/` 가 갱신되지 않은 채 세션이 끝났다.\n'
  printf '`/clear` 앞에 도는 훅이 없어 **막지는 못한다** — 대신 흔적을 남긴 것이다.\n'
  printf '위 `transcript` 를 읽어 **무엇이 빠졌는지 확인하고 기록에 반영해라.**\n'
  printf '(유저가 넘어가라고 하면 넘어간다. 다만 **말은 하고** 넘어간다)\n\n'
  rm -f "$ufile" 2>/dev/null || true
fi

# ── flake 덤프 — kit-verify 가 hook-test 간헐 실패의 현장 env 를 떠뒀으면 알린다.
#    (state/hook-test-flake.md — 재현이 안 되니 현장을 놓치면 안 된다. cwd 무관하게 띄운다.)
_fd="$(tr_state)/flake-dump"
if [ -d "$_fd" ]; then
  _fn=$(find "$_fd" -maxdepth 1 -type f 2>/dev/null | wc -l)
  if [ "${_fn:-0}" -gt 0 ]; then
    printf '\n🔬 **hook-test flake 덤프 %s건** — 재현 안 되던 실패의 현장 env 가 잡혔다.\n' "$_fn"
    printf '읽고 원인 분석 후 `state/hook-test-flake.md` 에 반영해라: `%s/`\n' "$_fd"
    printf '(정리했으면 그 파일들을 지운다 — 안 지우면 매 세션 뜬다)\n\n'
  fi
fi

name="$(tr_project)" || exit 0

# ── 안전망(A): cwd 가 ~/projects 밖이면 프로젝트를 모른다. 여기서 조용히 빠지면
#    롤오버 직후 이어갈 작업이 통째로 안 보인다(2026-08-06 실측) → **포인터는 준다.**
#
# 🔑 2026-08-07: 포인터만으로는 **인계가 안 됐다.** 예전 주석은 *"어느 프로젝트인지
#    찍지 않는다 — 고르는 건 모델·유저 몫"* 이었는데, 실제로는 아무도 못 골랐다.
#    유저가 이어가려던 건 `handoff-repo` 였고 모델은 그걸 몰랐다. 목록 3줄은
#    **인계가 아니라 색인**이다.
#
#    찍을 근거는 이미 있었다 — `tr_all_state` 가 **mtime 내림차순**으로 준다.
#    롤오버는 `state/` 를 갱신한 **직후** `/clear` 다(실측: 15:00 갱신 → 15:02 clear)
#    → **가장 최근 갱신본이 이어갈 것**이다.
#
#    ⚠️ 확률이지 확정이 아니다(병렬 세션이 다른 프로젝트를 더 최근에 건드릴 수 있다).
#    그래서 **근거인 갱신 시각을 같이 찍고**, 나머지는 목록으로 남겨 고를 수 있게 둔다.
#    오판 비용은 파일 하나 잘못 읽는 것뿐이고, 침묵의 비용은 인계 실패 전체다.
if [ -z "$name" ]; then
  # 🔑 전역 mtime 이 아니라 **이 세션(tmux명)의 프로젝트**를 먼저 집는다. (2026-08-20, tr_resume_state)
  mapfile -t pend < <(tr_resume_state "$ukey")
  if [ "${#pend[@]}" -gt 0 ]; then
    top="${pend[0]}"
    printf '\n## 미결 작업 %s건 (cwd 가 프로젝트 밖 — `%s`)\n\n' "${#pend[@]}" "$PWD"
    if [ "$source_kind" = "clear" ] || [ "$source_kind" = "resume" ] || [ "$source_kind" = "compact" ]; then
      printf '### 🔑 이어갈 것 → `%s`\n\n' "$top"
      printf '이 세션(`%s`)이 이어가던 것으로 본다 (최근 갱신 %s).\n\n' \
        "$ukey" "$(date -r "$DOCS_ROOT/$top" '+%m-%d %H:%M' 2>/dev/null || echo '?')"
      title="$(awk '/^# / { sub(/^# +/, ""); print; exit }' "$DOCS_ROOT/$top" 2>/dev/null)"
      stage="$(awk -F'|' '$2 ~ /단계/ { gsub(/^[[:space:]]+|[[:space:]]+$/, "", $3); print $3; exit }' "$DOCS_ROOT/$top" 2>/dev/null)"
      printf '제목: %s · 단계: %s\n\n' "${title:-확인 필요}" "${stage:-확인 필요}"
      if [ "${#pend[@]}" -gt 1 ]; then
        printf '나머지 미결 %s건 — 이게 아니면 `~/projects/_docs/*/state/` 목록에서 고른다.\n\n' \
          "$((${#pend[@]} - 1))"
      fi
      printf '**「진입」을 다시 하지 말고 위 단계부터 이어간다.** 전문은 파일을 읽어라.\n'
    else
      printf -- '- **`%s`** ← 가장 최근 갱신\n' "$top"
      [ "${#pend[@]}" -le 1 ] || printf -- '- 그 외 %s건 — 경로 목록은 필요할 때 조회\n' "$((${#pend[@]} - 1))"
      printf '\n어느 것을 이어갈지 **유저에게 확인하거나** 요청에서 판단해 파일을 읽어라.\n'
    fi
    printf '`cd ~/projects/%s` 하면 그 다음 턴부터 훅이 전문을 주입한다.\n' "${top%%/*}"
  fi
  exit 0
fi

# ── 심링크 자가치유. 실파일은 _docs/ 에 있으니 링크는 사람 편의용이다.
link="$PROJECTS/$name/_local-docs"
docs="$DOCS_ROOT/$name"
if [ -d "$docs" ] && [ ! -e "$link" ] && [ ! -L "$link" ]; then
  ln -s "../_docs/$name" "$link" 2>/dev/null && \
    printf '🔧 `%s/_local-docs` 심링크가 없어 다시 만들었다.\n\n' "$name"
elif [ -L "$link" ] && [ ! -e "$link" ]; then
  ln -sfn "../_docs/$name" "$link" 2>/dev/null && \
    printf '🔧 `%s/_local-docs` 심링크가 깨져 있어 고쳤다.\n\n' "$name"
fi

# ── 마무리 안 된 작업
if [ -d "$docs/state" ]; then
  n=$(find "$docs/state" -maxdepth 1 -name '*.md' -type f 2>/dev/null | wc -l)
  if [ "$n" -gt 0 ]; then
    if [ "$source_kind" = "clear" ] || [ "$source_kind" = "compact" ]; then
      # 🔑 롤오버 직후다. (compact 도 같다 — 2026-08-07: auto-compact 는 유저를 안 거쳐서
      #    오히려 맥락이 더 얇다. clear 만 챙기고 compact 를 뺀 건 구멍이었다)
      #    목록만 알리지 말고 **바로 이어갈 수 있게** 한다.
      #    별도 인계 문서가 필요 없는 이유 — Stop 훅이 state/ 를 최신으로 강제한다.
      printf '\n## 이어가는 작업 (롤오버 직후)\n\n'
      mapfile -t files < <(find "$docs/state" -maxdepth 1 -name '*.md' -type f -printf '%T@ %p\n' \
        2>/dev/null | sort -rn | cut -d' ' -f2-)
      top="${files[0]}"
      title="$(awk '/^# / { sub(/^# +/, ""); print; exit }' "$top" 2>/dev/null)"
      stage="$(awk -F'|' '$2 ~ /단계/ { gsub(/^[[:space:]]+|[[:space:]]+$/, "", $3); print $3; exit }' "$top" 2>/dev/null)"
      printf -- '- 🔑 `state/%s` — %s · 단계 %s · 갱신 %s\n' \
        "$(basename "$top")" "${title:-제목 확인 필요}" "${stage:-확인 필요}" \
        "$(date -r "$top" '+%m-%d %H:%M' 2>/dev/null || echo '?')"
      if [ "${#files[@]}" -gt 1 ]; then
        printf -- '- 그 외 %s건 — `state/` 목록에서 고른다\n' "$((${#files[@]} - 1))"
      fi
      printf '\n**「진입」을 다시 하지 말고 위 단계부터 이어간다.** 전문은 선택한 파일을 직접 읽어라.\n'
    else
      printf '\n📌 `%s` 에 마무리되지 않은 작업 %s건이 있다 (`state/`).\n' "$name" "$n"
    fi
  fi
fi

exit 0
}

# SessionStart 전체 예산: 일반 5KB, clear·compact 2KB. 다른 SessionStart 훅과 합쳐도 10KB 아래다.
cap_output() {
  local data="$1" limit="$2" marker=$'⚠️ SessionStart 주입 상한에 걸렸다. 상세는 파일을 직접 읽어라.\n'
  local total kept="" line candidate bytes marker_bytes
  total="$(printf '%s\n' "$data" | wc -c)"
  if [ "$total" -le "$limit" ]; then
    printf '%s\n' "$data"
    return 0
  fi
  marker_bytes="$(printf '%s' "$marker" | wc -c)"
  while IFS= read -r line || [ -n "$line" ]; do
    candidate="${kept}${line}"$'\n'
    bytes="$(printf '%s' "$candidate" | wc -c)"
    [ $((bytes + marker_bytes)) -le "$limit" ] || break
    kept="$candidate"
  done <<< "$data"
  printf '%s%s' "$kept" "$marker"
}

generated="$(generate)"
limit=5000
{ [ "$source_kind" = "compact" ] || [ "$source_kind" = "clear" ]; } && limit=2000
[ -n "$generated" ] && cap_output "$generated" "$limit"
exit 0
