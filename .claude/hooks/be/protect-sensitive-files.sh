#!/bin/bash
# Hook: Block editing sensitive files that contain secrets

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ -z "$FILE_PATH" ]]; then exit 0; fi

BASENAME=$(basename "$FILE_PATH")

if echo "$BASENAME" | grep -qiE '^\.env($|\.)'; then
  echo "BLOCKED: Cannot edit .env files — they may contain secrets." >&2
  exit 2
fi

if echo "$BASENAME" | grep -qiE 'credentials|secrets|\.key$|\.pem$|\.pfx$'; then
  echo "BLOCKED: Cannot edit credential/key files." >&2
  exit 2
fi

exit 0