#!/bin/bash
# Hook: PreToolUse (Bash) — quét secret trong diff staged trước khi git commit.
# BLOCK commit nếu phát hiện connection string / API key / JWT / password hardcode.
# Bổ sung cho protect-sensitive-files.sh (chỉ chặn EDIT .env) — đây bắt secret nằm trong code thường.

INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Chỉ xử lý lệnh git commit
echo "$CMD" | grep -qE '\bgit\b.*\bcommit\b' || exit 0

# Lấy diff đã staged (chỉ dòng thêm vào)
DIFF=$(git diff --cached --diff-filter=ACM 2>/dev/null | grep -E '^\+' | grep -vE '^\+\+\+')
[[ -z "$DIFF" ]] && exit 0

HITS=""
check() { echo "$DIFF" | grep -iqE "$1" && HITS="$HITS
  • $2"; }

check 'aws_secret_access_key|AKIA[0-9A-Z]{16}'                  "AWS key"
check 'sk-[a-zA-Z0-9]{20,}'                                     "API key (sk-...)"
check '(password|passwd|pwd)\s*[:=]\s*[\"'"'"'][^\"'"'"']{4,}'  "Hardcoded password"
check 'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.'            "JWT token"
check '(Server|Host|Data Source)=.*(Password|Pwd)='            "DB connection string"
check 'private_key|-----BEGIN [A-Z ]*PRIVATE KEY-----'         "Private key"
check '(api[_-]?key|secret|token)\s*[:=]\s*[\"'"'"'][A-Za-z0-9_-]{16,}' "Generic secret/token"

if [[ -n "$HITS" ]]; then
  REASON="🔒 Phát hiện secret trong diff staged — commit bị chặn:$HITS

Kiểm tra lại, chuyển sang biến môi trường / appsettings.local, rồi: git restore --staged <file>. Nếu chắc chắn false positive, commit thủ công ngoài Claude."
  jq -n --arg r "$REASON" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
fi

exit 0
