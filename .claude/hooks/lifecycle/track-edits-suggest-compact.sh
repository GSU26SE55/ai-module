#!/bin/bash
# Hook: PostToolUse (Edit|Write) — đếm số edit trong session + cảnh báo /compact khi dài.
# Counter này cũng được stop-suggest-lesson.sh dùng để quyết định có nhắc lesson không.

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "default"')

EDIT_FILE="/tmp/kltn-edits-$SESSION_ID"
COMPACT_NUDGED="/tmp/kltn-compact-nudged-$SESSION_ID"
COMPACT_THRESHOLD=40

# Tăng counter
COUNT=0
[[ -f "$EDIT_FILE" ]] && COUNT=$(cat "$EDIT_FILE" 2>/dev/null || echo 0)
COUNT=$((COUNT + 1))
echo "$COUNT" > "$EDIT_FILE"

# Cảnh báo /compact 1 lần khi vượt ngưỡng
if [[ "$COUNT" -ge "$COMPACT_THRESHOLD" && ! -f "$COMPACT_NUDGED" ]]; then
  touch "$COMPACT_NUDGED"
  MSG="🧹 Session đã $COUNT lần edit — context đang phình. Cân nhắc /compact để giữ token (RTK) & độ chính xác."
  jq -n --arg msg "$MSG" '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:$msg}}'
fi

exit 0
