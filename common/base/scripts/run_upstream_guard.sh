#!/bin/sh
# Linux/GNU timeout launcher. Root/catalog are explicit; never executes tool input.
# Pre failures block. Post failures report incomplete inspection; fresh gates
# remain mandatory and do not consume a cached post receipt.
event=PreToolUse
blocked() {
    if [ "$event" != PreToolUse ]; then
        printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"upstream-guard post inspection unavailable; effects were not undone. Fresh assembly/transfer gate required."}}\n' "$event"
        exit 0
    fi
    printf '%s\n' 'upstream-guard unavailable: launcher or response failed; operation blocked' >&2
    exit 2
}
[ "$#" -eq 5 ] || blocked
case "$1" in codex|claude) product="$1" ;; *) blocked ;; esac
case "$5" in PreToolUse|PostToolUse|PostToolUseFailure) event="$5" ;; *) blocked ;; esac
case "$2" in /*) ;; *) blocked ;; esac
case "$3" in /*) ;; *) blocked ;; esac
case "$4" in /*) ;; *) blocked ;; esac
source_root=$(CDPATH='' cd -- "$(dirname -- "$0")/../../.." && pwd -P) || blocked
output=$(/usr/bin/timeout --kill-after=1s 2s /usr/bin/python3 -B \
    "$source_root/adapters/$product/scripts/upstream_guard.py" \
    --root "$2" --catalog "$3" --scope "$4" --event "$event" 2>/dev/null)
[ "$?" -eq 0 ] || blocked
# Only the expected event's no-decision/feedback/Pre-deny shape is accepted.
validated=$(printf '%s' "$output" | /usr/bin/timeout --kill-after=1s 1s /usr/bin/python3 -c '
import json, sys
event = sys.argv[1]
value = json.load(sys.stdin)
if value != {}:
    if not isinstance(value, dict) or list(value) != ["hookSpecificOutput"]:
        raise ValueError("invalid top-level response")
    h = value["hookSpecificOutput"]
    if not isinstance(h, dict) or h.get("hookEventName") != event:
        raise ValueError("unexpected event")
    if sorted(h) == ["additionalContext", "hookEventName"]:
        if not isinstance(h["additionalContext"], str) or not h["additionalContext"]:
            raise ValueError("feedback required")
    elif event == "PreToolUse" and sorted(h) == ["hookEventName", "permissionDecision", "permissionDecisionReason"]:
        if h["permissionDecision"] != "deny" or not isinstance(h["permissionDecisionReason"], str) or not h["permissionDecisionReason"]:
            raise ValueError("only explicit Pre deny supported")
    else:
        raise ValueError("unsupported response fields")
print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
' "$event" 2>/dev/null) || blocked
printf '%s\n' "$validated"
