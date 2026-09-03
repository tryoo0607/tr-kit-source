#!/usr/bin/env bash
# format-drift — Stop. **백본 턴인데 단계 블록이 없으면 다음 턴에 상기시킨다.**
#
# 왜: 회사 세션 실측 보고(2026-08-11) — 20+턴 연속 수정 세션에서 응답 형식이 무너졌다.
#   ① 여러 턴이 블록 없이 평문으로 시작   ② 정의에 없는 `완료` 를 유사-스테이지로 발명
#   ③ 「마무리」를 안 쓰고 평문으로 때움
#
# 🔑 진단이 정확했다: **기록은 훅이 강제하는데(`require-record`) 형식은 안내문뿐**이다.
#    매 턴 5.8KB 를 주입해도 15턴쯤 지나면 배경이 된다. 이 kit 의 방법론은
#    *"규율이 실패한 자리를 훅으로 옮긴다"* 인데 **형식만 규율로 남아 있었다.**
#
# ⚠️ **훅은 "백본 턴인지"를 판정할 수 없다.** 휘발성 턴(단순 조회·잡담)은 블록을 생략하는 게
#    맞으므로, 순진하게 검사하면 오탐이 쏟아진다 → 가드가 아니라 소음이 된다.
#    그래서 **계산 가능한 프록시**를 쓴다: `tr-changed-<sid>` 마크가 있는 턴,
#    즉 **파일을 실제로 고친 턴**만 본다. 그건 휘발성일 수 없다.
#
# ⚠️ 막지 않는다(exit 0). 형식은 되돌릴 수 없는 것도, 밖으로 나가는 것도 아니다.
#    대신 **다음 턴 맨 위에 한 번** 상기시킨다 — event-driven 이라 상시 주입과 달리 배경화되지 않는다.
set -uo pipefail
. "${CLAUDE_PLUGIN_ROOT:?}/hooks/lib.sh" 2>/dev/null || exit 0

input="$(cat 2>/dev/null || true)"
command -v jq >/dev/null 2>&1 || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

sid="$(printf '%s' "$input" | jq -r '.session_id // ""' 2>/dev/null || true)"
tr_path="$(printf '%s' "$input" | jq -r '.transcript_path // ""' 2>/dev/null || true)"
[ -n "$sid" ] || exit 0

# ⚠️ 이 훅은 `require-record` **앞에** 배선한다 — 그쪽이 성공 시 마크를 지우기 때문이다.
[ -e "${TMPDIR:-/tmp}/tr-changed-${sid}" ] || exit 0
[ -r "$tr_path" ] || exit 0

verdict="$(python3 - "$tr_path" <<'PY' 2>/dev/null || true
import json, os, sys

path = sys.argv[1]
try:
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        if size > 1_000_000:          # 트랜스크립트는 수십 MB 까지 간다 → 꼬리만 읽는다
            f.seek(size - 1_000_000)
        lines = f.read().decode("utf-8", "ignore").split("\n")
except Exception:
    print("SKIP"); raise SystemExit

# 🔑 **진짜 유저 프롬프트는 `message.content` 가 문자열**이다(실측 2026-08-11).
#    도구 결과도 type=="user" 로 들어오는데 그쪽은 리스트(tool_result)다. 그걸로 턴을 자른다.
start = -1
for i, ln in enumerate(lines):
    try:
        d = json.loads(ln)
    except Exception:
        continue
    if d.get("type") == "user" and isinstance((d.get("message") or {}).get("content"), str):
        start = i
if start < 0:
    print("SKIP"); raise SystemExit

first = None
for ln in lines[start + 1:]:
    try:
        d = json.loads(ln)
    except Exception:
        continue
    if d.get("type") != "assistant":
        continue
    for b in (d.get("message") or {}).get("content") or []:
        if isinstance(b, dict) and b.get("type") == "text" and (b.get("text") or "").strip():
            first = b["text"].lstrip()
            break
    if first:
        break

if first is None:
    print("SKIP")
elif first[:1] in ("─", "═"):     # `═` 알림 블록이 위에 오는 것도 정본이다
    print("OK")
else:
    print("DRIFT|" + first.split("\n")[0][:60])
PY
)"

flag="$(tr_state)/format-drift/$sid"
case "$verdict" in
  DRIFT*)
    mkdir -p "$(dirname "$flag")" 2>/dev/null || true
    printf '%s\n' "${verdict#DRIFT|}" > "$flag" 2>/dev/null || true
    ;;
  *) rm -f "$flag" 2>/dev/null || true ;;
esac
exit 0
