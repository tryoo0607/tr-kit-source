#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FIXTURES="$ROOT/tests/fixtures"
SB="$(mktemp -d "${TMPDIR:-/tmp}/tr-lifecycle-smoke.XXXXXX")" || exit 1
trap 'rm -rf "$SB"' EXIT

mkdir -p "$SB/home/projects/demo" "$SB/home/projects/_docs/demo/state" \
  "$SB/home/.codex/sessions/2026/09/03" "$SB/home/.claude/projects/demo" \
  "$SB/state" "$SB/tmp" "$SB/bin"
printf '# demo state\n\n| profile | 고치기 |\n|---|---|\n| 단계 | **수행** |\n' \
  > "$SB/home/projects/_docs/demo/state/task.md"
cat > "$SB/bin/tmux" <<'SH'
#!/bin/sh
printf 'codex-demo\n'
SH
chmod +x "$SB/bin/tmux"

pass=0
fail=0

check() {
  local name="$1" condition="$2"
  shift 2
  if "$@"; then
    printf '  ✅ %s\n' "$name"
    pass=$((pass + 1))
  else
    printf '  ❌ %s — %s\n' "$name" "$condition"
    fail=$((fail + 1))
  fi
}

run_hook() {
  local plugin="$1" hook="$2" payload="$3"
  (
    cd "$SB/home/projects/demo" || exit 1
    printf '%s\n' "$payload" | HOME="$SB/home" XDG_STATE_HOME="$SB/state" TMPDIR="$SB/tmp" \
      CLAUDE_PLUGIN_ROOT="$plugin" PATH="$SB/bin:$PATH" env -u TMUX \
      bash "$plugin/hooks/$hook" 2>&1
  )
}

codex="$ROOT/out/codex/plugins/tr-codex"
claude="$ROOT/out/claude/plugins/tr-claude"

echo '── lifecycle smoke'

rollout60="$SB/home/.codex/sessions/2026/09/03/rollout-old-60.jsonl"
cp "$FIXTURES/codex-context-60.jsonl" "$rollout60"
payload60="$(printf '{"session_id":"old-60","prompt":"continue","transcript_path":"%s"}' "$rollout60")"
out="$(run_hook "$codex" inject-state.sh "$payload60")"
check 'Codex 60% 준비' '준비 알림 없음' grep -q 'Codex 컨텍스트 60%.*독립 인계 준비' <<< "$out"
out2="$(run_hook "$codex" inject-state.sh "$payload60")"
check 'Codex 준비 단발' '같은 세션에 준비 알림 반복' bash -c '! grep -q "Codex 컨텍스트 60%" <<< "$1"' _ "$out2"

rollout75="$SB/home/.codex/sessions/2026/09/03/rollout-old-75.jsonl"
cp "$FIXTURES/codex-context-75.jsonl" "$rollout75"
payload75="$(printf '{"session_id":"old-75","prompt":"handoff","transcript_path":"%s"}' "$rollout75")"
out="$(run_hook "$codex" inject-state.sh "$payload75")"
check 'Codex 75% 독립 인계' '독립 세션 안내 없음' \
  bash -c 'grep -q "Codex 컨텍스트 75%" <<< "$1" && grep -q "resume/fork" <<< "$1"' _ "$out"

out="$(run_hook "$codex" inject-state.sh '{"session_id":"new-session","prompt":"continue"}')"
check '새 세션 state 자동 선택' 'pending handoff가 task.md를 고르지 못함' \
  bash -c 'grep -q "새 독립 세션이 이전 인계를 이어받았다" <<< "$1" && grep -q "demo/state/task.md" <<< "$1"' _ "$out"
out2="$(run_hook "$codex" inject-state.sh '{"session_id":"new-session","prompt":"continue"}')"
check '재개 지시 단발' '같은 새 세션에서 재개 지시 반복' \
  bash -c '! grep -q "새 독립 세션이 이전 인계를 이어받았다" <<< "$1"' _ "$out2"

readonly_payload='{"session_id":"mark-read","tool_name":"Bash","tool_input":{"command":"jq '\''select(.a > 1)'\'' data.json"}}'
run_hook "$codex" mark-changed.sh "$readonly_payload" >/dev/null
check 'quoted 비교는 조회' 'jq 비교가 변경으로 오탐' test ! -e "$SB/tmp/tr-changed-mark-read"

record_payload='{"session_id":"mark-record","tool_name":"Bash","tool_input":{"command":"sed -i s/old/new/ ~/projects/_docs/demo/state/task.md"}}'
run_hook "$codex" mark-changed.sh "$record_payload" >/dev/null
check 'Bash 기록 변경은 제외' '_docs 기록 자체가 작업 변경으로 오탐' test ! -e "$SB/tmp/tr-changed-mark-record"

write_payload='{"session_id":"mark-write","tool_name":"Bash","tool_input":{"command":"printf value > output.txt"}}'
run_hook "$codex" mark-changed.sh "$write_payload" >/dev/null
check '출력 redirection은 변경' '실제 파일 쓰기를 놓침' test -e "$SB/tmp/tr-changed-mark-write"

set +e
out="$(run_hook "$codex" require-record.sh '{"session_id":"mark-write"}')"
rc=$?
set -e
check '미기록 Stop 차단' "exit $rc" test "$rc" -eq 2
sleep 0.02
touch "$SB/home/projects/_docs/demo/state/task.md"
run_hook "$codex" require-record.sh '{"session_id":"mark-write"}' >/dev/null
check '기록 후 Stop 통과' '변경 마크가 남음' test ! -e "$SB/tmp/tr-changed-mark-write"

: > "$SB/tmp/tr-changed-compact"
set +e
out="$(run_hook "$codex" pre-compact.sh '{"session_id":"compact","compaction_trigger":"auto"}')"
rc=$?
set -e
check 'auto-compact 1회 차단' "exit $rc" test "$rc" -eq 2
check 'Codex compact 인계 문구' 'target adapter 문구 없음' grep -q '새 독립 세션' <<< "$out"
out2="$(run_hook "$codex" pre-compact.sh '{"session_id":"compact","compaction_trigger":"auto"}')"
check 'auto-compact 2회차 통과' '두 번째에도 차단됨' test "$?" -eq 0
check 'auto-compact 2회차 경고' '통과 경고 없음' grep -q '기록 없이 Codex auto-compact' <<< "$out2"

claude_tx="$SB/home/.claude/projects/demo/claude-session.jsonl"
printf '%s\n' '{"type":"assistant","message":{"usage":{"input_tokens":10000,"cache_creation_input_tokens":20000,"cache_read_input_tokens":120000}}}' > "$claude_tx"
claude_payload="$(printf '{"session_id":"claude-session","prompt":"continue","transcript_path":"%s"}' "$claude_tx")"
out="$(run_hook "$claude" inject-state.sh "$claude_payload")"
check 'Claude 잔여 토큰 인계' '고정 백분율 대신 잔여 토큰 안내가 없음' \
  bash -c 'grep -q "잔여 50,000토큰" <<< "$1" && grep -q "/clear" <<< "$1"' _ "$out"

bytes="$(printf '%s' "$out" | wc -c)"
check '주입 2KB 상한' "출력 ${bytes}B" test "$bytes" -le 2000

scope="$(HOME="$SB/home" CLAUDE_PLUGIN_ROOT="$codex" bash -c '. "$1/hooks/lib.sh"; tr_scope "$2"' _ "$codex" "$SB/home/projects/demo")"
check 'scope 기본 unknown' "scope=$scope" test "$scope" = unknown
printf 'work\n' > "$SB/home/projects/demo/.tr-scope"
scope="$(HOME="$SB/home" CLAUDE_PLUGIN_ROOT="$codex" bash -c '. "$1/hooks/lib.sh"; tr_scope "$2"' _ "$codex" "$SB/home/projects/demo")"
check 'project scope 명시 우선' "scope=$scope" test "$scope" = work
rm "$SB/home/projects/demo/.tr-scope"
scope="$(HOME="$SB/home" TR_KIT_SCOPE=personal CLAUDE_PLUGIN_ROOT="$codex" bash -c '. "$1/hooks/lib.sh"; tr_scope "$2"' _ "$codex" "$SB/home/projects/demo")"
check 'environment scope fallback' "scope=$scope" test "$scope" = personal

out="$(run_hook "$codex" handoff-inbox.sh '{}')"
check 'handoff 미설정 no-op' '미설정인데 출력 발생' test -z "$out"

if [ "$fail" -eq 0 ]; then
  printf '✅ lifecycle smoke %d 통과\n' "$pass"
  exit 0
fi
printf '❌ %d 실패 / %d\n' "$fail" "$((pass + fail))"
exit 1
