#!/bin/bash
# Hook: Run ruff lint + format check after editing .py files

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ "$FILE_PATH" != *.py ]]; then exit 0; fi
if [[ ! -f "$FILE_PATH" ]]; then exit 0; fi

# Locate ruff — check PATH first, then Python user bin locations
RUFF_CMD=""
if command -v ruff &>/dev/null; then
  RUFF_CMD="ruff"
else
  for candidate in \
    "$HOME/Library/Python/3.9/bin/ruff" \
    "$HOME/Library/Python/3.10/bin/ruff" \
    "$HOME/Library/Python/3.11/bin/ruff" \
    "$HOME/.local/bin/ruff"; do
    if [[ -x "$candidate" ]]; then
      RUFF_CMD="$candidate"
      break
    fi
  done
fi

if [[ -z "$RUFF_CMD" ]]; then
  echo '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"⚠️ ruff not installed — linting skipped. Run: pip install ruff"}}'
  exit 0
fi

LINT_OUTPUT=$("$RUFF_CMD" check "$FILE_PATH" 2>&1)
LINT_EXIT=$?

FORMAT_OUTPUT=$("$RUFF_CMD" format --check "$FILE_PATH" 2>&1)
FORMAT_EXIT=$?

if [[ $LINT_EXIT -ne 0 ]]; then
  echo "ruff lint errors in $(basename "$FILE_PATH"):" >&2
  echo "$LINT_OUTPUT" | head -15 >&2
  echo "Fix with: $RUFF_CMD check --fix $FILE_PATH" >&2
  exit 2
fi

if [[ $FORMAT_EXIT -ne 0 ]]; then
  echo "ruff format issue in $(basename "$FILE_PATH") — run: $RUFF_CMD format $FILE_PATH" >&2
  exit 2
fi

exit 0
