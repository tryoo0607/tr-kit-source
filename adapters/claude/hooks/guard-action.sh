#!/usr/bin/env bash
# guard-action — PreToolUse(+PostToolUse). **안전 가드를 규율에서 훅으로 옮긴다.**
#
# 왜: `CLAUDE.md` 에 *"되돌리기 어렵거나 외부로 나가는 액션은 실행 전 확인"* 이 있는데
#     이건 **모델이 지키는 L3 정책**이었다. 기록 강제(`require-record`)·컨텍스트 넛지는
#     이미 훅으로 내려왔는데 **안전 가드만 규율로 남아 있었다** — kit 의 방법론과 어긋난다.
#
# 🔑 구멍이 이론이 아니라 실재였다: `permissions.defaultMode` 가 **`auto`** 다.
#    자기승인 모드라 **내장 권한 프롬프트가 안 뜬다.** 규율이 미끄러지면 그냥 나간다.
#
# ⚠️ **cry-wolf 를 피하는 게 설계의 절반이다.** 매번 물으면 유저가 반사적으로 승인하고
#    가드는 죽는다(컨텍스트 넛지가 겪은 병과 같다). 그래서 3층으로 나눈다:
#
#   ⛔ deny  **정당한 용도가 아예 없는 것.** 실제 사고 이력이 있는 것만 여기 온다
#   ⚠️ ask   되돌리기 어려운 것 — **항상** 묻는다 (force push · rm -rf · cycle)
#   ⚠️ ask   그냥 외부로 나가는 것 — **세션·repo 당 한 번만** 묻는다
#
# ⛔ **deny 를 함부로 늘리지 마라.** 2026-08-08 에 `claude-remote cycle` 을 deny 로 넣었다가
#    같은 날 내렸다 — 유저는 **remote-control 세션**이라 셸을 직접 칠 길이 없어서
#    "사람이 직접"이 곧 "아무도 못 함"이 됐다. **가드가 정상 작업을 막으면 고장이다.**
#    판별: *"유저가 승인해도 하면 안 되나?"* 에 예여야 deny. 아니면 ask.
#
# 세션당 1회로 줄인 근거: 정책에 *"이미 승인·지시된 건 진행"* 이 있다. 훅은 승인 여부를
#   모르지만 **PostToolUse 가 도는 건 도구가 실제로 실행됐다는 뜻**(= 유저가 승인) 이다.
#   그래서 같은 파일이 PostToolUse 도 받아 표식을 남긴다. deny 하면 표식이 안 생긴다.
set -uo pipefail
. "${CLAUDE_PLUGIN_ROOT:?}/hooks/lib.sh" 2>/dev/null || exit 0

input="$(cat 2>/dev/null || true)"
command -v jq >/dev/null 2>&1 || exit 0   # 판정할 수 없으면 막지 않는다(가드가 작업을 멈추면 안 된다)

ev="$(printf '%s' "$input"  | jq -r '.hook_event_name // ""' 2>/dev/null || true)"
tool="$(printf '%s' "$input"| jq -r '.tool_name // ""'       2>/dev/null || true)"
cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // ""'   2>/dev/null || true)"
fp="$(printf '%s' "$input"  | jq -r '.tool_input.file_path // ""' 2>/dev/null || true)"
mode="$(printf '%s' "$input"| jq -r '.permission_mode // ""'  2>/dev/null || true)"
sid="$(printf '%s' "$input" | jq -r '.session_id // ""'       2>/dev/null || true)"

# 승인 표식 키 — repo 단위. 같은 repo 로 두 번째 push 부터는 같은 결정이다.
#
# ⚠️ 전체 경로가 아니라 **repo 이름**으로 잡는다. 같은 이름의 repo 두 개를 한 세션에서
#    다루면 두 번째가 안 물어보게 되는데, 그 대가로 표식이 사람이 읽을 수 있는 이름이 되고
#    `hook-test` 가 존재를 단언할 수 있게 된다. 이름 충돌은 실사용에서 나온 적이 없다.
push_key() {
  local root name
  root="$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null || printf '%s' "$PWD")"
  name="$(printf '%s' "${root##*/}" | tr -c 'A-Za-z0-9' '-')"
  printf '%s/tr-push-ok-%s-%s' "${TMPDIR:-/tmp}" "${sid:-nosid}" "$name"
}

# ── PostToolUse: 실행됐다 = 유저가 통과시켰다. 같은 repo 는 다시 묻지 않는다.
if [ "$ev" = "PostToolUse" ]; then
  case "$cmd" in *"git push"*|*"git"*" push "*) : > "$(push_key)" 2>/dev/null || true ;; esac
  exit 0
fi

emit() {  # $1=allow|deny|ask  $2=사유
  jq -n --arg d "$1" --arg r "$2" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:$d,permissionDecisionReason:$r}}'
  exit 0
}

# ══ 1층 ⛔ deny — 부활 좌표를 손으로 건드리지 않는다 ═══════════════════════════
#
# `sessions.log`·`snapshot` 은 `claude-remote restore` 가 대화를 되살리는 좌표다.
# 2026-08-06 에 훅을 손으로 테스트하다 `session_id=t` 가 박혀 **스냅샷까지 오염**됐다
# (cases/hooks/sessions-log-poisoned.md). 쓰레기 한 줄이 세션을 잃게 만든다.
# 읽기는 자유다. **쓰기만** 막는다 — 갱신은 훅과 `claude-remote` 가 한다.
guard_state_write() {
  local target="$1"
  case "$target" in
    *claude-remote/sessions.log*|*claude-remote/snapshot*) ;;
    *) return 0 ;;
  esac
  emit deny '⛔ `claude-remote` 부활 좌표(sessions.log·snapshot)를 직접 쓰려 했다. 훅이 막았다.

여기가 오염되면 `restore` 가 **없는 대화를 되살리려다 세션을 잃는다** (2026-08-06 실측, cases/hooks/sessions-log-poisoned.md).
갱신은 `session-check` 훅과 `claude-remote snapshot` 이 한다 — 손으로 쓰지 마라.
훅 동작을 확인하려면 `setup/tools/hook-test` 를 써라(샌드박스라 안전하다).

**유저에게 이 사실을 알리고**, 정말 필요하면 유저가 직접 하도록 둬라.'
}

case "$tool" in
  Write|Edit|NotebookEdit) [ -n "$fp" ] && guard_state_write "$fp" ;;
esac

[ "$tool" = "Bash" ] || exit 0
[ -n "$cmd" ] || exit 0

# Bash 로 우회하는 경로도 같이 막는다 — 단, 읽기(grep·cat·tail·stat)는 통과시킨다.
#
# 🔑 **변경 동사는 경로와 같은 구간에 있어야 한다** (파이프·세미콜론·개행 앞까지).
#    2026-08-10 실측 오탐: `mkdir -p "$SB/bin"; …; stat -c %y …/claude-remote/snapshot`
#    처럼 **읽기만 하는 복합 명령**이 막혔다 — 명령 **전체**에서 동사를 찾았기 때문이다.
#    방금 만든 규칙("가드가 정상 작업을 막으면 고장이다")에 내가 먼저 걸렸다.
#
# ⚠️ 남는 한계: **heredoc 안의 문자열도 명령문으로 보인다.** 이 훅의 테스트 픽스처처럼
#    `> …/sessions.log` 라는 **텍스트**를 파일에 쓰려 하면 막힌다. 파싱으로 풀 문제가 아니라
#    **Write/Edit 도구를 쓰면 통과한다**(경로로 판정하므로). 그게 탈출구다.
_P='claude-remote/(sessions\.log|snapshot)'
_S='[^|;&[:cntrl:]]*'
case "$cmd" in
  *claude-remote/sessions.log*|*claude-remote/snapshot*)
    if printf '%s' "$cmd" | grep -qE \
        ">>?[[:space:]]*${_S}${_P}|(tee|rm|mv|cp|truncate|dd|ln|install)[[:space:]]${_S}${_P}|sed[[:space:]]+(-i|--in-place)${_S}${_P}"
    then
      guard_state_write "claude-remote/sessions.log"
    fi ;;
esac

# ══ 2층 ⚠️ ask — cycle/restart 는 남의 세션을 끊을 수 있다 ═════════════════════
#
# ⚠️ **처음엔 `deny` 로 넣었다가 같은 날 내렸다.** 근거가 인계 요청서의
#    *"권한 분류기에 막힐 수 있다 → 사람이 직접"* 이었는데, 그건 **분류기 동작 관찰**이지
#    유저가 정한 정책이 아니었다. 관찰을 규칙으로 승격시킨 게 잘못이다.
#
# 🔑 결정적으로: 유저는 **remote-control 세션**으로 일한다(Termux·mosh). 거기엔
#    `!` 로 셸을 치는 길이 없다 → `deny` 는 "사람이 직접"이 아니라 **아무도 못 돌림**이 된다.
#    가드가 유저의 정상 작업을 못 하게 만들면 그건 가드가 아니라 고장이다.
#
# 진짜 위험은 *"모델이 하면 안 됨"* 이 아니라 **"busy 세션이 있는데 돌리면 남의 작업이 끊김"** 이다.
# 그건 물어보면 되는 종류다 — 대신 **사전 점검 결과를 먼저 내놓게** 사유문에 박는다.
case "$cmd" in
  *"claude-remote cycle"*|*"claude-remote restart"*|*"claude-remote kill"*)
    emit ask '⚠️ **전 세션을 재시작한다 — 지금 이 세션도 포함이다.**

`busy` 세션이 하나라도 있으면 **하던 작업이 끊긴다.** 그리고 너는 죽는 순간 결과를 확인할 수 없다.

**아직 안 했으면 사전 점검 2종을 먼저 돌려 결과를 유저에게 보여주고 나서 다시 시도해라:**
  ① 살아있는 세션 중 `busy` 가 이 세션뿐인지 (`~/.claude/sessions/*.json` + `/proc`)
  ② `claude-remote snapshot` 후 부활 좌표가 전부 실재하는지 (**FAIL 0**)

점검을 이미 통과했으면 그 결과를 요약해 보여주고 진행해라.' ;;
esac

# ══ 2층 ⚠️ ask (항상) — force push 는 남의 작업을 덮는다 ════════════════════════
#
# 여러 checkout·사람·자동화가 같은 branch를 갱신할 수 있으므로 force push 전에
# remote-only commit을 확인한다. 저장소나 머신의 고유 이름은 guard 근거가 아니다.
case "$cmd" in
  *"git push"*|*"git "*" push "*)
    case "$cmd" in
      *" --force"*|*" -f "*|*" -f"|*"--force-with-lease"*|*" +"*)
        emit ask '⚠️ **force push 다 — 원격 히스토리를 덮는다.**

다른 checkout·사람·자동화가 원격에 먼저 올린 commit이 있으면 force push가 그 작업을 지울 수 있다.

먼저 `git fetch && git log --oneline HEAD..@{u}` 로 **덮게 될 커밋이 무엇인지 확인해서 유저에게 보여줘라.**' ;;
    esac ;;
esac

# ══ 2층 ⚠️ ask (항상) — 워킹트리를 날리는 git ═════════════════════════════════
#
# 🔑 **`permissions.allow` 에 `Bash(git:*)` 를 넣은 것의 대가다** (2026-08-10).
#    `cd X && git …` 조합이 프롬프트 대부분을 만들고 있어서 git 을 통째로 열었는데,
#    그러면 워킹트리를 지우는 verb 까지 무프롬프트가 된다. **넓게 열고 여기서 좁힌다** —
#    그게 이 kit 이 택한 구조다(allowlist 는 넓게, 훅은 날카롭게).
#
# ⚠️ reflog 로 못 살리는 것만 고른다. `git reset --soft`·`rebase` 는 커밋이 남아서 뺐다.
#
# ⚠️ 문자열 매칭이면 안 된다. `git -C <path> clean` 처럼 **플래그가 사이에 낀다**(오늘 실측).
#    반대로 `git commit -m "restore …"` 는 잡으면 안 된다 → **verb 가 git 바로 뒤**여야 한다.
#    그래서 `-C <path>` · `-c <cfg>` 쌍만 건너뛰고 그 다음 토큰을 본다.
#
# ⚠️ **dry-run 은 묻지 않는다.** 2026-08-10 실측: `git clean -nd` 에 확인이 떴다.
#    아무것도 안 지우는데 물은 것도 문제지만, 더 나쁜 건 **아래 안내문이 바로 그 dry-run 을
#    시킨다**는 점이다 — 시킨 걸 또 막으면 유저는 확인창을 두 번 넘겨야 한다. 자기모순이다.
_dry=0
case "$cmd" in
  *" --dry-run"*) _dry=1 ;;
  *) printf '%s' "$cmd" | grep -qE 'clean([[:space:]]+-[a-zA-Z]*n[a-zA-Z]*)+' && _dry=1 ;;
esac
if [ "$_dry" != 1 ] && printf '%s' "$cmd" | grep -qE \
    'git([[:space:]]+-[cC][[:space:]]+[^[:space:]]+)*[[:space:]]+(clean([[:space:]]|$)|restore([[:space:]]|$)|reset[[:space:]]+--hard|checkout[[:space:]]+--([[:space:]]|$)|branch[[:space:]]+-D)'
then
    emit ask '⚠️ **워킹트리·브랜치를 되돌릴 수 없게 지우는 git 이다.**

`git clean`(추적 안 되는 파일) · `restore`/`checkout --`(수정분) 은 **reflog 로도 못 살린다.**

**무엇이 지워지는지 먼저 보여줘라** — `git status --short` 또는 `git clean -nd`(dry-run) 결과를 내고 확인받아라.'
fi

# ══ 2층 ⚠️ ask (항상) — 되돌릴 수 없는 삭제 ════════════════════════════════════
#
# 보호 대상은 **다시 만들 수 없는 것**뿐이다. 빌드 산출물·캐시 삭제까지 물으면 cry-wolf 다.
# 🔑 **판정을 뒤집었다 (2026-08-10).** 예전엔 "이 경로를 향하면 ask" 였다 —
#    보호 목록에 없는 건 전부 조용히 통과했고, `rm -rf "$DIR"` 처럼 **변수가 안 풀린** 경우도
#    통과했다. 그게 세상에서 사고가 나는 모양이다($DIR 이 비면 `rm -rf /` 가 된다).
#
#    이제 **재귀 강제 삭제는 기본이 ask** 이고, 확실히 재생성 가능한 것만 통과한다.
#    cry-wolf 가 아닌 이유: `rm -rf` 는 드물다(트랜스크립트 3936건 중 손에 꼽는다).
#    자주 하는 건 빌드 산출물 삭제고 그건 아래 목록이 통과시킨다.
if printf '%s' "$cmd" | grep -qE '(^|[|;&[:space:]])rm[[:space:]]+(-[a-zA-Z]*[rR][a-zA-Z]*[[:space:]]+-[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*[[:space:]]+-[a-zA-Z]*[rR]|-[a-zA-Z]*[rR][a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*[rR]|--recursive|--force)'; then
  # 통과시키는 것 = **지워도 다시 만들어지는 것**뿐이다. 하나라도 이 밖이면 묻는다.
  safe=1
  for tgt in $(printf '%s' "$cmd" | sed 's/.*rm[[:space:]]*//' | tr '|;&' '\n' | head -1); do
    case "$tgt" in
      -*) continue ;;                                   # 플래그
      *node_modules*|*/dist|*/dist/|*/build|*/build/|*/target|*/target/|\
      *.next*|*__pycache__*|*/.pytest_cache*|*/coverage*|*/.venv*|\
      /tmp/*|*/tmp/*|*.egg-info*|*/vendor/*) ;;         # 재생성 가능
      *) safe=0; break ;;
    esac
  done
  if [ "$safe" != 1 ]; then
    emit ask '⚠️ **재귀 강제 삭제다 (`rm -r -f`). 되돌릴 수 없다.**

훅은 **재생성 가능한 것**(node_modules · dist · build · target · __pycache__ · /tmp …)만 조용히 통과시킨다. 이건 그 밖이라 묻는다.

**실행 전에 이걸 먼저 해라:**
  ① 변수·글롭이 있으면 **전개 결과를 찍어라** — `echo` 로 확인. 빈 변수 하나가 `rm -rf /` 를 만든다
  ② `ls -d <대상>` 으로 **무엇이 몇 개 지워지는지** 세어 유저에게 보여라
  ③ 그러고 나서 확인받아라

특히 `~/projects/_docs`(작업 기록 전부) · `~/.claude`(세션·플러그인) · `claude-remote` 상태는 **백업이 로컬뿐이거나 아예 없다.**'
  fi
fi

# ══ 3층 ⚠️ ask (세션·repo 당 1회) — 외부로 나가는 액션 ═════════════════════════
#
# ⚠️ 자기승인 모드에서만 건다. `default`·`plan` 은 **내장 권한 프롬프트가 이미 묻는다** —
#    거기서 또 물으면 질문이 두 번 뜨고, 두 번 뜨는 질문은 읽히지 않는다.
case "$mode" in
  auto|dontAsk|bypassPermissions|acceptEdits) ;;
  *) exit 0 ;;
esac

outbound=""
case "$cmd" in
  *"git push"*|*"git "*" push "*)        outbound="git push" ;;
  *"gh repo create"*)                     outbound="gh repo create" ;;
  *"gh release create"*)                  outbound="gh release create" ;;
  *"npm publish"*|*"docker push"*|*"helm push"*) outbound="레지스트리 publish" ;;
esac
[ -n "$outbound" ] || exit 0

# 같은 repo 로 이미 한 번 나갔으면 같은 결정이다 — 다시 묻지 않는다.
[ -e "$(push_key)" ] && exit 0

extra=''
[ "$(tr_scope)" = "work" ] && extra='

⛔ **영역이 `work` 다.** 회사 자산은 개인 GitHub 에 올리지 않는다 — private 여도 개인 계정이면 반출이다(`scopes/work.md`). 나가는 내용이 회사 것인지 **먼저 확인해라.**'

emit ask "⚠️ **외부로 나가는 액션이다 (\`$outbound\`).** 전역 정책상 실행 전 확인 대상이다.

**무엇이 어디로 나가는지 한 줄로 요약해서 유저에게 보여줘라** — 대상 remote 와 커밋 범위.
(이 repo 에서 이번 세션 첫 건일 때만 묻는다. 통과하면 다음부터는 조용하다)$extra"
