#!/bin/bash
# Hook: Block dangerous shell commands

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [[ -z "$COMMAND" ]]; then exit 0; fi

if echo "$COMMAND" | grep -qE 'rm\s+(-rf|-fr)\s+(/|\.|\*|src|services|shared)'; then
  echo "BLOCKED: Destructive rm -rf command detected." >&2
  exit 2
fi

# Block staging .env files (git add .env, git add -A khi .env chưa có trong .gitignore)
if echo "$COMMAND" | grep -qE 'git\s+add\s+.*\.env[^.]'; then
  echo "BLOCKED: Attempting to stage .env file — may contain secrets. Add to .gitignore first." >&2
  exit 2
fi

if echo "$COMMAND" | grep -qiE 'database\s+drop|DROP\s+DATABASE|DROP\s+TABLE'; then
  echo "BLOCKED: Database drop command detected." >&2
  exit 2
fi

if echo "$COMMAND" | grep -qE 'git\s+push' && \
   echo "$COMMAND" | grep -qE '(--force|-f)\b' && \
   echo "$COMMAND" | grep -qE '\b(main|master)\b'; then
  echo "BLOCKED: Force push to main/master is not allowed." >&2
  exit 2
fi

if echo "$COMMAND" | grep -qE 'git\s+reset\s+--hard'; then
  echo "BLOCKED: git reset --hard can lose uncommitted work. Use git stash first." >&2
  exit 2
fi

if echo "$COMMAND" | grep -qE 'git\s+clean\s+-[a-z]*f'; then
  echo "BLOCKED: git clean -f can delete untracked files permanently." >&2
  exit 2
fi

exit 0
