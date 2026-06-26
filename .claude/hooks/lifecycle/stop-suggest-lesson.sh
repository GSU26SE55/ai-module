#!/bin/bash
# Hook: Stop — nhắc ghi lesson vào AUTO-MEMORY private (không phải .claude/memory.md).
# Throttle: Stop chạy mỗi lượt trả lời → chỉ nhắc 1 lần mỗi session, và chỉ khi
# session đã đủ dài (>= EDIT_THRESHOLD edit) để tránh phiền với câu hỏi ngắn.

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "default"')

EDIT_THRESHOLD=8
EDIT_FILE="/tmp/kltn-edits-$SESSION_ID"
NUDGED_FILE="/tmp/kltn-lesson-nudged-$SESSION_ID"

# Đã nhắc rồi trong session này → im lặng
[[ -f "$NUDGED_FILE" ]] && exit 0

# Session quá ngắn (ít edit) → chưa cần nhắc
EDIT_COUNT=0
[[ -f "$EDIT_FILE" ]] && EDIT_COUNT=$(cat "$EDIT_FILE" 2>/dev/null || echo 0)
[[ "$EDIT_COUNT" -lt "$EDIT_THRESHOLD" ]] && exit 0

# Đánh dấu đã nhắc + nhắc 1 lần
touch "$NUDGED_FILE"
MSG="💡 Session đã làm $EDIT_COUNT lần edit. Có fact/quyết định/cạm bẫy mới đáng ghi không?
→ Ghi vào AUTO-MEMORY private (~/.claude/projects/.../memory/) theo format frontmatter + thêm 1 dòng vào MEMORY.md.
→ KHÔNG ghi thẳng .claude/memory.md (file đó commit cho cả team — chỉ promote lên đó khi lesson đã verify)."

jq -n --arg msg "$MSG" '{hookSpecificOutput:{hookEventName:"Stop",additionalContext:$msg}}'
exit 0
