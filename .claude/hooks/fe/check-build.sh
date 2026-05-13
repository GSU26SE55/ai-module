#!/bin/bash
# Hook: After editing .ts/.tsx files, run TypeScript type check

normalize_path() { echo "$1" | tr '\\' '/'; }

INPUT=$(cat)
FILE_PATH=$(normalize_path "$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')")

if [[ "$FILE_PATH" != *.ts && "$FILE_PATH" != *.tsx ]]; then exit 0; fi

if echo "$FILE_PATH" | grep -qE '/(node_modules|dist|build|\.next|shared/components/ui)/'; then exit 0; fi

# Tìm thư mục chứa tsconfig.json từ file đang edit lên trên
# PREV_DIR prevents infinite loop at Windows drive root (/c, /d, etc.)
DIR=$(dirname "$FILE_PATH")
TSCONFIG_DIR=""
PREV_DIR=""

while [[ "$DIR" != "/" && "$DIR" != "$HOME" && "$DIR" != "$PREV_DIR" ]]; do
  if [[ -f "$DIR/tsconfig.json" ]]; then
    TSCONFIG_DIR="$DIR"
    break
  fi
  PREV_DIR="$DIR"
  DIR=$(dirname "$DIR")
done

# Fallback: thử project dir
if [[ -z "$TSCONFIG_DIR" && -f "$CLAUDE_PROJECT_DIR/tsconfig.json" ]]; then
  TSCONFIG_DIR="$CLAUDE_PROJECT_DIR"
fi

# Không tìm thấy tsconfig → bỏ qua
if [[ -z "$TSCONFIG_DIR" ]]; then exit 0; fi

# node_modules chưa install → bỏ qua
if [[ ! -d "$TSCONFIG_DIR/node_modules" ]]; then exit 0; fi

cd "$TSCONFIG_DIR" || exit 0

OUTPUT=$(npx tsc --noEmit 2>&1)
EXIT_CODE=$?

if [[ $EXIT_CODE -ne 0 ]]; then
  echo "TypeScript type check FAILED in $TSCONFIG_DIR:" >&2
  echo "$OUTPUT" >&2
  exit 2
fi

exit 0
