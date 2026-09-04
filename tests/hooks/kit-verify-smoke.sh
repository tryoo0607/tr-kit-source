#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SB="$(mktemp -d "${TMPDIR:-/tmp}/tr-kit-verify-smoke.XXXXXX")" || exit 1
trap 'rm -rf "$SB"' EXIT

source_repo="$SB/source-worktree"
other_repo="$SB/generated-target"
mkdir -p "$source_repo/tools" "$source_repo/recipes" "$source_repo/core/contracts" "$other_repo"
printf 'schema_version = 1\n' > "$source_repo/recipes/_schema.toml"
printf 'schema_version = 1\n' > "$source_repo/core/contracts/pack-v1.toml"
printf '# fixture build contract\n' > "$source_repo/tools/build.py"
cat > "$source_repo/tools/validate.py" <<'PY'
#!/usr/bin/env python3
import os
from pathlib import Path

with Path(os.environ["VERIFY_LOG"]).open("a") as stream:
    stream.write("hook\n")
PY

for repo in "$source_repo" "$other_repo"; do
  git -C "$repo" init -q
  git -C "$repo" config user.name test
  git -C "$repo" config user.email test@example.com
  git -C "$repo" add .
  git -C "$repo" commit -qm initial --allow-empty
done

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
  local sid="$1" cwd="$2"
  (
    cd "$other_repo" || exit 1
    printf '{"session_id":"%s","cwd":"%s"}\n' "$sid" "$cwd" |
      HOME="$SB/home" TMPDIR="$SB/tmp" VERIFY_LOG="$SB/verify.log" \
      CLAUDE_PLUGIN_ROOT="$ROOT/out/codex/plugins/tr-codex" \
      bash "$ROOT/out/codex/plugins/tr-codex/hooks/kit-verify.sh" 2>&1
  )
}

mkdir -p "$SB/home/projects" "$SB/tmp"
rm -f "$SB/verify.log"

echo '── kit verify smoke'

run_hook clean "$source_repo" >/dev/null
check 'clean source 첫 관찰은 기준선만 기록' 'validator가 불필요하게 실행됨' \
  test ! -e "$SB/verify.log"

printf 'changed\n' > "$source_repo/change.txt"
run_hook dirty "$source_repo" >/dev/null
check 'payload cwd의 dirty source 검증' 'source validator가 실행되지 않음' \
  grep -qx hook "$SB/verify.log"

run_hook dirty "$source_repo" >/dev/null
check '같은 dirty 상태는 한 번만 검증' '변화가 없는데 validator가 반복 실행됨' \
  test "$(wc -l < "$SB/verify.log")" -eq 1

printf 'changed again\n' > "$source_repo/change.txt"
run_hook dirty "$source_repo" >/dev/null
check 'dirty 내용이 달라지면 재검증' '새 변경을 놓침' \
  test "$(wc -l < "$SB/verify.log")" -eq 2

rm -f "$SB/verify.log"
run_hook target "$other_repo" >/dev/null
check '생성 target은 source로 오인하지 않음' 'target에서 validator가 실행됨' \
  test ! -e "$SB/verify.log"

cat > "$source_repo/tools/validate.py" <<'PY'
#!/usr/bin/env python3
raise SystemExit("fixture failure")
PY
set +e
out="$(run_hook failure "$source_repo")"
rc=$?
set -e
check 'validator 실패는 Stop 차단' "exit $rc" test "$rc" -eq 2
check 'validator 실패 원인 노출' '실패 출력이 사라짐' grep -q 'fixture failure' <<< "$out"

if [ "$fail" -eq 0 ]; then
  printf '✅ kit verify smoke %d 통과\n' "$pass"
  exit 0
fi
printf '❌ %d 실패 / %d\n' "$fail" "$((pass + fail))"
exit 1
