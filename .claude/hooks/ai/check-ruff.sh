#!/bin/bash
# Hook: Run ruff lint + format check after editing .py files

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ "$FILE_PATH" != *.py ]]; then exit 0; fi
if [[ ! -f "$FILE_PATH" ]]; then exit 0; fi

# Check ruff is installed — warn only, do not block editing
if ! command -v ruff &>/dev/null; then
  echo '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"⚠️ ruff not installed — linting skipped. Run: pip install ruff"}}'
  exit 0
fi

LINT_OUTPUT=$(ruff check "$FILE_PATH" 2>&1)
LINT_EXIT=$?

FORMAT_OUTPUT=$(ruff format --check "$FILE_PATH" 2>&1)
FORMAT_EXIT=$?

if [[ $LINT_EXIT -ne 0 ]]; then
  echo "ruff lint errors in $(basename "$FILE_PATH"):" >&2
  echo "$LINT_OUTPUT" | head -15 >&2
  echo "Fix with: ruff check --fix $FILE_PATH" >&2
  exit 2
fi

if [[ $FORMAT_EXIT -ne 0 ]]; then
  echo "ruff format issue in $(basename "$FILE_PATH") — run: ruff format $FILE_PATH" >&2
  exit 2
fi

exit 0
