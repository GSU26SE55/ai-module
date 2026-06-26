#!/bin/bash
# Hook: SessionStart — bơm context dự án vào đầu mỗi session
# In ra: role cá nhân (CLAUDE.local.md) + sprint hiện tại + nhắc nơi ghi lesson.
# Mục đích: Claude luôn khởi động đúng ngữ cảnh thay vì phải đi tìm.

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
LOCAL_MD="$PROJECT_DIR/.claude/CLAUDE.local.md"

CTX="📋 Context dự án GSU26SE55 — Solar Lithium-ion Battery Maintenance."

# Role cá nhân từ CLAUDE.local.md (không commit)
if [[ -f "$LOCAL_MD" ]]; then
  ROLE_MAIN=$(grep -iE "Role chính" "$LOCAL_MD" | head -1 | sed 's/\*\*//g')
  ROLE_SUB=$(grep -iE "Role phụ" "$LOCAL_MD" | head -1 | sed 's/\*\*//g')
  [[ -n "$ROLE_MAIN" ]] && CTX="$CTX
- $ROLE_MAIN"
  [[ -n "$ROLE_SUB" ]] && CTX="$CTX
- $ROLE_SUB"
else
  CTX="$CTX
- ⚠️ Chưa có CLAUDE.local.md — khai báo role trước khi dùng skills/dev/."
fi

# Nhắc workflow + nơi ghi lesson
CTX="$CTX
- Workflow: /kltn-plan → /kltn-implement → /kltn-reviewcode → /kltn-test → /kltn-ship → /kltn-complete.
- Lesson rút ra trong session: ghi vào AUTO-MEMORY private (~/.claude/.../memory/), KHÔNG ghi thẳng .claude/memory.md (file đó commit cho cả team)."

jq -n --arg ctx "$CTX" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$ctx}}'
exit 0
