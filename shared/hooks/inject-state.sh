#!/usr/bin/env bash
# inject-state — UserPromptSubmit. 진행 중인 작업 상태를 컨텍스트에 주입.
#
# 왜: 이게 "읽고 시작하라"는 규율(L4)을 **불필요하게** 만든다. 규율은 잊히지만
#     주입은 매 턴 일어난다. 폐기한 `/tr:do` 도 이게 대체한다.
#
# 사양: UserPromptSubmit 의 plain stdout 은 그대로 컨텍스트에 추가된다.
#       ⚠️ 크기 제한은 문서화돼 있지 않다 → **상한을 우리가 건다**(아래 MAX).
#       전문이 아니라 헤더+미결만 넣는다. 전문이 필요하면 모델이 파일을 읽으면 된다.
#
# 원칙: 프롬프트를 절대 막지 않는다. 문제가 있으면 조용히 빠진다(exit 0).
set -uo pipefail
# shellcheck source=lib.sh
. "${CLAUDE_PLUGIN_ROOT:?}/hooks/lib.sh" 2>/dev/null || exit 0

TOTAL_MAX_BYTES=2000    # UserPromptSubmit 전체 출력 상한(규약·알림·state 합계)
MAX_STATE_POINTERS=3    # 전문은 주입하지 않고 최신 포인터만

input="$(cat 2>/dev/null || true)"
rkey="$(tmux display-message -p '#S' 2>/dev/null || echo default)"
project="$(tr_project 2>/dev/null || true)"
lifecycle_core="${CLAUDE_PLUGIN_ROOT:?}/hooks/core/decision.py"
lifecycle_adapter="${CLAUDE_PLUGIN_ROOT:?}/hooks/lifecycle-adapter.py"

generate() {

# ── target transport → normalized event → core decision → target output.
# adapter 경로는 build에서 target별 파일로 고정된다. runtime target 선택은 없다.
if command -v python3 >/dev/null 2>&1 && [ -r "$lifecycle_core" ] && [ -r "$lifecycle_adapter" ]; then
  context_event="$(printf '%s' "$input" | TR_SESSION_KEY="$rkey" TR_PROJECT="$project" python3 "$lifecycle_adapter" context-event 2>/dev/null || true)"
  if [ -n "$context_event" ]; then
    context_result="$(printf '%s' "$context_event" | python3 "$lifecycle_core" 2>/dev/null || true)"
    [ -z "$context_result" ] || printf '%s' "$context_result" | \
      TR_SESSION_KEY="$rkey" TR_PROJECT="$project" python3 "$lifecycle_adapter" render-context 2>/dev/null || true
  fi
fi

<!-- if:claude -->
# ── 알림: 배포 안 됨 (플러그인 캐시가 repo 보다 뒤처짐)
# 🔑 왜: kit-doctor 가 이미 아는 정보인데 **물어봐야만** 알려준다. 그래서 릴리스를 여러 번
#    쪼개 돌리게 된다(2026-08-06: 사이클 5회). 안 물어봐도 오게 만든다.
#
#    ⚠️ sha 가 다른 것만으로는 오탐이다 — 셸 채널(setup/)만 바뀐 커밋이 섞인다.
#       **그 플러그인 폴더가 실제로 바뀌었는지**까지 봐야 한다(kit-doctor [5]와 같은 판정).
#    비용을 아끼려고 **kit repo 안에서 작업할 때만** 검사한다.
kit_repo="$PROJECTS/tr-claude"
case "$PWD/" in
  "$kit_repo"/*)
    if command -v jq >/dev/null 2>&1 && [ -r "$HOME/.claude/plugins/installed_plugins.json" ]; then
      head_sha="$(git -C "$kit_repo" rev-parse HEAD 2>/dev/null || true)"
      cache_sha="$(jq -r '.plugins["tr-claude@tr-claude"][0].gitCommitSha // empty' \
                     "$HOME/.claude/plugins/installed_plugins.json" 2>/dev/null || true)"
      if [ -n "$head_sha" ] && [ -n "$cache_sha" ] && [ "$head_sha" != "$cache_sha" ] \
         && git -C "$kit_repo" cat-file -e "$cache_sha^{commit}" 2>/dev/null \
         && ! git -C "$kit_repo" diff --quiet "$cache_sha" HEAD -- plugins/tr-claude 2>/dev/null; then
        printf '⚠️ **플러그인 캐시가 뒤처졌다** — 캐시 `%s` ≠ repo `%s`. 유저에게 알려라.\n' \
          "${cache_sha:0:7}" "${head_sha:0:7}"
        printf '고친 훅·스킬이 아직 안 돈다. `plugin update` 후 `claude-remote cycle -y`.\n'
        printf '(이번 턴에 또 고칠 거면 **한 번에 묶어서** 배포하라 — 사이클은 전 세션을 재시작한다)\n\n'
      fi
    fi
  ;;
esac

<!-- /if -->
# ── 🔑 단계·가정·불확실 표기 (매 턴)
# 왜 여기냐: 이건 결정 #22(응답 규약 = 단계별 필수 항목)인데 {{AGENT_FILE}} 에만 있어서
#   **세션 시작에 한 번 읽고 잊혔다**(2026-08-06 실사용 감사에서 확인).
#   결과는 어차피 보이지만 **가정과 불확실은 안 보인다** — 그게 유저가 끼어들 지점이다.
#   매 턴 반복되는 지시라야 안 잊힌다.
# ── 🔑 응답 레지스터 (매 턴)
# 왜 여기냐: 이건 결정 #22(응답 규약 = 단계별 필수 항목)인데 {{AGENT_FILE}} 에만 있어서
#   **세션 시작에 한 번 읽고 잊혔다**(2026-08-06 실사용 감사에서 확인).
#   결과는 어차피 보이지만 **가정과 불확실은 안 보인다** — 그게 유저가 끼어들 지점이다.
#
# 🔑 2026-08-07: 규약이 **한 종류로 고정**이라 상황별 조절 손잡이가 없었다(실측: 매 턴 주입
#   5,482 bytes 중 94%가 이 규약). 3종으로 분리하고 **세션별로** 고른다.
#   키 규약은 session-end 와 같다 — `/clear` 를 넘어 살아남아야 하므로 tmux 이름이다.
reg="default"
rf="$(tr_state)/register/$rkey"
[ -r "$rf" ] && reg="$(tr -d '[:space:]' < "$rf")"
case "$reg" in brief|deep|default) ;; *) reg="default" ;; esac

# ── 모드 인라인 디렉티브 — register(간결도)와 **직교**하는 자세 플래그 둘. 파싱은 아래.
#    키는 register 와 같은 tmux 세션명(/clear 를 넘어 산다).
#    chat = 논의-우선(티키타카) · asap = 물어본 것만 즉시 직답. 둘은 반대 방향이라 보통 하나만 켠다.
ckf="$(tr_state)/chat/$rkey"
chat_now=0; [ -e "$ckf" ] && chat_now=1
akf="$(tr_state)/asap/$rkey"
asap_now=0; [ -e "$akf" ] && asap_now=1

# ── 롤오버 재개 요약 — /clear·compact 직후 첫 턴이면 「재개 요약」을 띄우라 지시(one-shot)
#    session-check.sh(SessionStart)가 플래그를 남긴다. 여기서 소비하고 지운다.
#    유저가 "인계가 됐는지 모르겠다"던 지점 — 첫 응답에 눈에 보이는 확인을 준다.
rovf="$(tr_state)/rollover/$rkey"
if [ -e "$rovf" ]; then
  rm -f "$rovf" 2>/dev/null || true
  printf '🔧 **롤오버(/clear·compact) 직후 첫 턴이다.** 이어받은 작업을 **「재개 요약」 밴드(📋 재개)** 로\n'
  printf '한 번 요약해 보여주고 시작하라 — 유저가 인계됐는지 확인하는 자리다.\n'
  printf '아래 주입된 state(진행 중인 작업)에서 뽑는다: 이어가는 작업(제목·profile·단계) / 직전까지 / 남은 것 / 다음 한 걸음.\n\n'
fi

# ── Codex 독립 세션 인계: 이전 session_id가 남긴 marker는 같은 세션이 소비하지 않는다.
# 새 session_id가 오고 이어갈 state가 있을 때만 core가 resume.inject를 반환한다.
if command -v python3 >/dev/null 2>&1 && command -v jq >/dev/null 2>&1 \
   && [ -r "$lifecycle_core" ] && [ -r "$lifecycle_adapter" ]; then
  mapfile -t _resume_candidates < <(tr_resume_state "$rkey")
  _state_available=0; [ "${#_resume_candidates[@]}" -gt 0 ] && _state_available=1
  resume_event="$(printf '%s' "$input" | TR_SESSION_KEY="$rkey" TR_STATE_AVAILABLE="$_state_available" \
    python3 "$lifecycle_adapter" resume-event 2>/dev/null || true)"
  if [ -n "$resume_event" ]; then
    resume_result="$(printf '%s' "$resume_event" | python3 "$lifecycle_core" 2>/dev/null || true)"
    resume_action="$(printf '%s' "$resume_result" | jq -r '.action // "none"' 2>/dev/null || true)"
    if [ "$resume_action" = "resume.inject" ]; then
      _resume_project="$(printf '%s' "$resume_result" | jq -r '.data.project // ""' 2>/dev/null || true)"
      if [ -n "$_resume_project" ]; then
        mapfile -t _resume_candidates < <(_tr_proj_state "$_resume_project")
      fi
      _top="${_resume_candidates[0]}"
      printf '📋 **`/clear` 후 이전 작업을 이어받았다.**\n'
      printf '먼저 `%s/%s` 하나만 읽고, 전체 transcript·roadmap은 필요한 절만 조회한다.\n' "$DOCS_ROOT" "$_top"
      printf '첫 응답에 이어가는 작업·직전까지·남은 것·다음 검증을 **재개 요약**으로 보여준다.\n\n'
      printf '%s' "$input" | TR_SESSION_KEY="$rkey" python3 "$lifecycle_adapter" ack-resume 2>/dev/null || true
    fi
  fi
fi

# ── ==tldr== 인라인 디렉티브 (== 또는 -- 감싸개)  ※ "인라인 디렉티브" = kit 공식 용어(2026-08-20 확정)
# 🔑 왜: "간결히 답해줘"가 잦은데, 슬래시(/{{KIT_REPO}}:register)는 맨 앞에만 오고 접두어가 길다.
#   인라인 디렉티브가 편하다. 단 이건 argv 가 아니라 **산문 grep** 이라 오탐을 구조로 막는다:
#     ① 코드펜스(``` ```)·인라인 코드 안은 무시   ② **첫 비어있지 않은 줄**의 지시일 때만
#   → 붙여넣은 코드/주석 속 --tldr-- 는 절대 안 터진다.
if command -v jq >/dev/null 2>&1; then
  prompt="$(printf '%s' "$input" | jq -r '.prompt // ""' 2>/dev/null || true)"
  if [ -n "$prompt" ]; then
    # 코드펜스 블록 제거 + 인라인 코드 제거
    stripped="$(printf '%s\n' "$prompt" | awk '
      /^[[:space:]]*```/ { infence = !infence; next }
      !infence { print }
    ' | sed 's/`[^`]*`//g')"
    fl="$(printf '%s\n' "$stripped" | grep -m1 -v '^[[:space:]]*$' || true)"   # 첫 비어있지 않은 줄
    if printf '%s' "$fl" | grep -qiE '(--|==)tldr([[:space:]]+(on|off))?(--|==)'; then
      if printf '%s' "$fl" | grep -qiE '(--|==)tldr[[:space:]]+on(--|==)'; then
        mkdir -p "$(dirname "$rf")" && printf brief > "$rf"; reg="brief"
        printf '🔧 `==tldr on==` — 이 세션 응답을 **brief 로 전환**했다(지속). 유저에게 한 줄로 확인하라.\n\n'
      elif printf '%s' "$fl" | grep -qiE '(--|==)tldr[[:space:]]+off(--|==)'; then
        mkdir -p "$(dirname "$rf")" && printf default > "$rf"; reg="default"
        printf '🔧 `==tldr off==` — brief 를 **해제**(default)했다. 유저에게 한 줄로 확인하라.\n\n'
      else
        reg="brief"   # 단발 — 이번 턴만. 세션 register($rf)는 안 건드린다
        printf '🔧 `==tldr==` — **이번 턴만** brief 로 답하라(세션 register 는 안 바꾼다).\n\n'
      fi
    fi

    # ── ==chat== 논의-우선 인라인 디렉티브 (tldr 와 같은 `==`·`--` 감싸개, 같은 오탐방어)
    # 🔑 왜: "바로 손대지 말고 논의부터"(티키타카)가 잦다. register(간결도)와 **직교**하는
    #   자세라 별도 플래그다. 토큰 = chat 또는 논의. on/off = 세션 지속, 맨몸 = 이번 턴만.
    if printf '%s' "$fl" | grep -qiE '(--|==)(chat|논의)([[:space:]]+(on|off))?(--|==)'; then
      if printf '%s' "$fl" | grep -qiE '(--|==)(chat|논의)[[:space:]]+on(--|==)'; then
        mkdir -p "$(dirname "$ckf")" && : > "$ckf"; chat_now=1
        printf '🔧 `==chat on==` — 이 세션을 **논의-우선 모드로 전환**했다(지속). 유저에게 한 줄로 확인하라.\n\n'
      elif printf '%s' "$fl" | grep -qiE '(--|==)(chat|논의)[[:space:]]+off(--|==)'; then
        rm -f "$ckf" 2>/dev/null || true; chat_now=0
        printf '🔧 `==chat off==` — 논의-우선 모드를 **해제**했다. 유저에게 한 줄로 확인하라.\n\n'
      else
        chat_now=1   # 단발 — 이번 턴만. 세션 플래그($ckf)는 안 건드린다
        printf '🔧 `==chat==` — **이번 턴만** 논의-우선.\n\n'
      fi
    fi

    # ── ==asap== 즉시-직답 인라인 디렉티브. 토큰 = asap 또는 즉답. chat 과 반대 축이다.
    if printf '%s' "$fl" | grep -qiE '(--|==)(asap|즉답)([[:space:]]+(on|off))?(--|==)'; then
      if printf '%s' "$fl" | grep -qiE '(--|==)(asap|즉답)[[:space:]]+on(--|==)'; then
        mkdir -p "$(dirname "$akf")" && : > "$akf"; asap_now=1
        printf '🔧 `==asap on==` — 이 세션을 **즉답 모드로 전환**했다(지속). 유저에게 한 줄로 확인하라.\n\n'
      elif printf '%s' "$fl" | grep -qiE '(--|==)(asap|즉답)[[:space:]]+off(--|==)'; then
        rm -f "$akf" 2>/dev/null || true; asap_now=0
        printf '🔧 `==asap off==` — 즉답 모드를 **해제**했다. 유저에게 한 줄로 확인하라.\n\n'
      else
        asap_now=1   # 단발 — 이번 턴만. 세션 플래그($akf)는 안 건드린다
        printf '🔧 `==asap==` — **이번 턴만** 즉답.\n\n'
      fi
    fi
  fi
fi

# 전문 register(5~11KB)는 cold reference다. 매 턴에는 행동을 보존하는 최소 요약만 넣는다.
printf '<!-- 훅: 응답 규약 요약 (%s) -->\n' "$reg"
case "$reg" in
  brief)
    printf '백본 턴이면 `────` 단계 블록으로 시작하고, 가정·확신없음은 있을 때만 쓴다. 휘발성 턴은 생략한다.\n'
    printf '표·결론 중심으로 짧게 쓰되 안전·근거 규칙은 유지한다. 실질 완료 턴만 핵심 결과를 먼저 요약한다. 상세는 `registers/brief.md`.\n\n'
  ;;
  deep)
    printf '백본 턴이면 `────` 단계 블록으로 시작한다. 스테이지는 진입·정의·계획·수행·점검·마무리 6종뿐이다.\n'
    printf '가정·확신없음은 있을 때만 드러낸다. 실질 완료 턴은 `▓` 요약 밴드로 핵심/부가를 나눈다.\n'
    printf '판정은 근거와 대안, 버린 이유까지 편다. 훅 알림은 `═` 블록, 롤오버 첫 턴은 재개 요약. 상세는 `registers/deep.md`.\n\n'
  ;;
  *)
    printf '백본 턴이면 `────` 단계 블록으로 시작한다. 스테이지는 진입·정의·계획·수행·점검·마무리 6종뿐이다.\n'
    printf '가정·확신없음은 있을 때만 쓴다. 실질 완료 턴만 `▓` 요약 밴드, 훅 알림은 `═` 블록으로 낸다.\n'
    printf '롤오버 첫 턴은 재개 요약을 한 번 보인다. 블록 사이 한 줄을 띄운다. 상세는 `registers/default.md`.\n\n'
  ;;
esac

# ── 모드가 켜져 있으면 **매 턴 상기**(register 처럼 상시). 지속 플래그든 이번 턴 단발이든 같다.
if [ "$chat_now" = 1 ]; then
  printf '🗣️ **논의-우선 모드(chat).** 바로 편집·실행하지 마라 — **선택지·트레이드오프를 먼저 펼치고**\n'
  printf '유저와 방향을 맞춘 뒤 진행한다. 요청이 명백한 실행 지시여도, 접근이 갈리면 먼저 짚는다. (해제: `==chat off==`)\n\n'
fi
if [ "$asap_now" = 1 ]; then
  printf '⚡ **즉답 모드(asap).** 물어본 것에 **즉시 직답만** — 단계블록·요약밴드·첨언·제안·사족 전부 빼라.\n'
  printf 'tldr(요약·재구성)와 달리 **재구성도 말고** 질문에 바로 답만 준다. (해제: `==asap off==`)\n\n'
fi

# ── 🔑 형식 드리프트 상기 — `format-drift`(Stop)가 남긴 표식을 여기서 소비한다.
#    상시 주입(위 규약)은 15턴쯤 지나면 배경이 된다. 이건 **어긋난 직후 한 번만** 뜨므로
#    배경화되지 않는다. 상시 안내 ≠ 강제 라는 게 회사 세션 보고의 핵심 진단이었다.
if command -v jq >/dev/null 2>&1; then
  _sid="$(printf '%s' "$input" | jq -r '.session_id // ""' 2>/dev/null || true)"
  _ff="$(tr_state)/format-drift/${_sid:-none}"
  if [ -n "${_sid:-}" ] && [ -r "$_ff" ]; then
    printf '⚠️ **직전 턴이 단계 블록 없이 시작했다.** 파일을 고친 턴이었으니 백본 턴이다.\n\n'
    printf '    실제 첫 줄: `%s`\n\n' "$(head -c 120 "$_ff" 2>/dev/null | tr -d '\n')"
    printf '이번 턴은 **`────` 블록부터** 낸다. 그리고 `완료`·`확인` 같은 걸 지어내지 마라 —\n'
    printf '**스테이지는 6종뿐**이고, 일이 끝났으면 그건 **📦「마무리」** 다.\n\n'
    rm -f "$_ff" 2>/dev/null || true
  fi
fi

docs="$(tr_docs)" || exit 0

# ── 안전망(A): cwd 가 프로젝트 밖이면 전문 대신 **포인터만**. 조용히 빠지지 않는다.
#    매 턴 반복되므로 짧게 — 전문은 cd 하거나 파일을 읽으면 된다.
if [ -z "$docs" ]; then
  # 🔑 전역 mtime 이 아니라 **이 세션(tmux명)의 프로젝트**를 먼저 집는다 — 재개 로또를 없앤다.
  #    (2026-08-20: cwd=`~` 세션이 clear 후 딴 프로젝트를 인계받던 버그. tr_resume_state 참고)
  mapfile -t pend < <(tr_resume_state "$rkey")
  [ "${#pend[@]}" -gt 0 ] || exit 0
  # 🔑 목록만 내지 않는다 — **이 세션이 이어갈 것을 지목**한다(tr_resume_state 가 최우선순으로 준다).
  printf '<!-- 훅: cwd 가 ~/projects 밖이라 프로젝트를 특정 못 함 -->\n'
  printf '미결 작업 %s건. **이어갈 것 → `%s`** (가장 최근 갱신)\n' "${#pend[@]}" "${pend[0]}"
  if [ "${#pend[@]}" -gt 1 ]; then
    printf '나머지 %s건 — 필요할 때 `~/projects/_docs/*/state/` 목록을 조회한다.\n' "$((${#pend[@]} - 1))"
  fi
  printf '이어가는 요청이면 해당 파일을 읽어라. `cd ~/projects/%s` 하면 전문이 주입된다.\n' \
    "${pend[0]%%/*}"
  exit 0
fi

[ -d "$docs/state" ] || exit 0

mapfile -t files < <(find "$docs/state" -maxdepth 1 -name '*.md' -type f -printf '%T@ %p\n' \
  2>/dev/null | sort -rn | cut -d' ' -f2-)
[ "${#files[@]}" -gt 0 ] || exit 0

out="📌 미결 state ${#files[@]}건 — 본문은 필요할 때 직접 읽어라."$'\n'
limit="${#files[@]}"; [ "$limit" -gt "$MAX_STATE_POINTERS" ] && limit="$MAX_STATE_POINTERS"
for ((i=0; i<limit; i++)); do
  out+="- \`state/$(basename "${files[$i]}")\`"$'\n'
done
if [ "${#files[@]}" -gt "$MAX_STATE_POINTERS" ]; then
  out+="- 외 $((${#files[@]} - MAX_STATE_POINTERS))건 — \`state/\` 목록에서 고른다"$'\n'
fi

printf '%s\n' "$out"
printf '이 작업을 이어간다면 「진입」을 다시 하지 말고 해당 단계부터 진행한다. 마무리하면 `exec/` 로 옮긴다.\n'
exit 0
}

# 줄 경계를 보존해 UTF-8을 깨뜨리지 않으면서 전체 주입 예산을 강제한다.
cap_output() {
  local data="$1" limit="$2" marker=$'⚠️ 훅 출력이 2KB 상한에 걸렸다. 상세는 해당 파일을 직접 읽어라.\n'
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
[ -n "$generated" ] && cap_output "$generated" "$TOTAL_MAX_BYTES"
exit 0
