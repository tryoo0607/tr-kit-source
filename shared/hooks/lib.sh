#!/usr/bin/env bash
# 훅 공용 — 프로젝트 판정과 경로 계산.
#
# 🔑 심링크에 의존하지 않는다. `~/projects/_docs/<project>/` 를 **계산**한다.
#    심링크가 깨져도 시스템은 안 멈추고, 사람이 `ls` 로 못 볼 뿐이다.

PROJECTS="$HOME/projects"
DOCS_ROOT="$PROJECTS/_docs"

# cwd 로 프로젝트 이름을 판정. ~/projects 밖이면 빈 문자열.
tr_project() {
  local cwd="${1:-$PWD}"
  case "$cwd" in
    "$PROJECTS"/*) ;;
    *) return 0 ;;
  esac
  local rest="${cwd#"$PROJECTS"/}"
  local first="${rest%%/*}"
  case "$first" in
    _docs|_assets|"") return 0 ;;
  esac
  printf '%s' "$first"
}

# 세션 원격 상태 디렉토리 — **경로 규칙을 한 곳에 둔다.**
# 🔑 2026-08-07 `hook-test` 첫 실행이 잡은 불일치: `inject-state` 만 `$HOME/.local/state` 를
#    하드코딩하고 나머지는 `XDG_STATE_HOME` 을 존중했다. XDG_STATE_HOME 을 쓰는 환경에선
#    **statusline 이 쓴 값을 훅이 못 읽는다** → 넛지가 조용히 죽는다(2026-08-06 과 같은 병).
<!-- if:claude -->
# 기존 session의 flags를 잃지 않기 위해 역사적 디렉터리 이름만 유지한다.
# `claude-remote` host binary에 대한 runtime 의존은 없다.
tr_state() { printf '%s/claude-remote' "${XDG_STATE_HOME:-$HOME/.local/state}"; }
<!-- /if -->
<!-- if:codex -->
tr_state() { printf '%s/codex-remote' "${XDG_STATE_HOME:-$HOME/.local/state}"; }  # 확인 필요: codex 세션상태 경로
<!-- /if -->

# 그 프로젝트의 기록 디렉토리 (없어도 경로는 낸다)
tr_docs() {
  local name; name="$(tr_project "${1:-$PWD}")"
  [ -n "$name" ] || return 0
  printf '%s/%s' "$DOCS_ROOT" "$name"
}

# 🔑 cwd 가 ~/projects 밖일 때의 안전망 — 전 프로젝트 미결 state 를 최신순으로.
#    출력: `<project>/state/<file.md>` 한 줄씩 (DOCS_ROOT 기준 상대경로).
#
#    왜 필요한가: 세션은 대개 `~` 에서 뜬다(실측 2026-08-06, sessions.log 8건 중 7건).
#    그러면 tr_project 가 빈 문자열이라 훅이 **조용히 exit** 하고, 롤오버 직후
#    이어갈 작업이 주입되지 않는다. cwd 를 못 믿을 때도 최소한 **포인터는 준다**.
tr_all_state() {
  [ -d "$DOCS_ROOT" ] || return 0
  find "$DOCS_ROOT" -mindepth 3 -maxdepth 3 -path '*/state/*.md' -type f \
    -printf '%T@ %p\n' 2>/dev/null | sort -rn | cut -d' ' -f2- | while read -r f; do
      printf '%s\n' "${f#"$DOCS_ROOT"/}"
    done
}

# 한 프로젝트의 미결 state 를 최신순으로 (DOCS_ROOT 기준 상대경로). tr_all_state 의 단일-프로젝트판.
_tr_proj_state() {
  local dir="$DOCS_ROOT/${1:-}/state"
  [ -n "${1:-}" ] && [ -d "$dir" ] || return 0
  find "$dir" -maxdepth 1 -name '*.md' -type f -printf '%T@ %p\n' 2>/dev/null \
    | sort -rn | cut -d' ' -f2- | while read -r f; do printf '%s\n' "${f#"$DOCS_ROOT"/}"; done
}

# 🔑 롤오버 재개용 state 해소 — cwd 가 ~/projects 밖일 때 **전역 mtime 로또 대신** 이 세션의 것을 집는다.
#    (2026-08-20: harness-engineering 세션이 cwd=`~` 라 clear 후 재개가 매번 전역 최신
#     mtime(딴 프로젝트, 그날은 camera)을 집어 엉뚱한 걸 인계했다 — cases/hooks/resume-picks-global-mtime.md)
#
#    인자 = **raw tmux 세션명**(`#S`). 3단으로 좁힌다:
#      ① 세션명(prefix 벗긴 canonical) == 프로젝트 디렉토리   예) <세션prefix>camera → camera
#      ② 이 세션이 마지막으로 고친 프로젝트   (mark-changed 가 raw 세션명으로 남긴 breadcrumb)
#      ③ 전역 mtime 폴백(tr_all_state) — breadcrumb 도 없을 때만
#    출력 형식은 tr_all_state 와 같다: `<project>/state/<file.md>` 최신순.
tr_resume_state() {
  local rkey="${1:-}" out proj canon bc
  if [ -n "$rkey" ]; then
    # ① 세션명 == 프로젝트 (session-check 와 같은 prefix 규칙으로 canonical 화)
<!-- if:claude -->
    canon="${rkey#claude-}"
<!-- /if -->
<!-- if:codex -->
    canon="${rkey#codex-}"   # 확인 필요: codex tmux prefix
<!-- /if -->
    out="$(_tr_proj_state "$canon")"
    [ -n "$out" ] && { printf '%s\n' "$out"; return 0; }
    # ② 마지막으로 고친 프로젝트 breadcrumb (tmux명 키 — /clear 를 넘어 산다)
    bc="$(tr_state)/last-project/$rkey"
    if [ -r "$bc" ]; then
      proj="$(tr -d '[:space:]' < "$bc" 2>/dev/null || true)"
      out="$(_tr_proj_state "$proj")"
      [ -n "$out" ] && { printf '%s\n' "$out"; return 0; }
    fi
  fi
  # ③ 폴백
  tr_all_state
}

# runtime profile의 scalar를 읽는다. profile이 없거나 key가 없으면 조용히 실패한다.
tr_profile_get() {
  local key="${1:-}" runtime="${CLAUDE_PLUGIN_ROOT:-}/profile/resolver.py"
  [ -n "$key" ] && [ -r "$runtime" ] || return 1
  python3 "$runtime" get "$key" 2>/dev/null
}

# 영역(scope) 판정 — 명시적 project/env/profile 순서. 값: work | personal | unknown
# 특정 회사 alias, 계정명, GitHub owner, 머신 이름을 추론 규칙으로 쓰지 않는다.
tr_scope() {
  local cwd="${1:-$PWD}" root="" project="" value=""
  root="$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || true)"
  if [ -z "$root" ]; then
    project="$(tr_project "$cwd")"
    [ -z "$project" ] || root="$PROJECTS/$project"
  fi
  if [ -n "$root" ] && [ -r "$root/.tr-scope" ]; then
    value="$(tr -d '[:space:]' < "$root/.tr-scope" 2>/dev/null || true)"
  fi
  [ -n "$value" ] || value="${TR_KIT_SCOPE:-}"
  [ -n "$value" ] || value="$(tr_profile_get public.scope.default || true)"
  case "$value" in
    work|personal) printf '%s' "$value" ;;
    *) printf 'unknown' ;;
  esac
}
