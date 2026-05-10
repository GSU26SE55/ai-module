#!/bin/bash
# Hook: Validate C# namespace matches folder path

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ "$FILE_PATH" != *.cs ]] || [[ ! -f "$FILE_PATH" ]]; then exit 0; fi

# Skip generated files
if echo "$FILE_PATH" | grep -qE '\.Designer\.cs$|\.g\.cs$|Migrations/'; then exit 0; fi

NS_LINE=$(grep -m1 -E '^(global )?namespace ' "$FILE_PATH")
DECLARED_NS=$(echo "$NS_LINE" | sed 's/^global //;s/namespace //;s/[;{]//g' | tr -d '[:space:]')

if [[ -z "$DECLARED_NS" ]]; then exit 0; fi

# Derive expected namespace from path: .../src/ServiceName.Layer/Folder/Sub/File.cs
REL_PATH=$(echo "$FILE_PATH" | sed -n 's|.*/src/||p')
if [[ -z "$REL_PATH" ]]; then
  REL_PATH=$(echo "$FILE_PATH" | sed -n 's|.*/shared/||p')
fi

if [[ -z "$REL_PATH" ]]; then exit 0; fi

EXPECTED_NS=$(dirname "$REL_PATH" | tr '/' '.')

if [[ "$EXPECTED_NS" == "." ]]; then exit 0; fi

if [[ "$DECLARED_NS" != "$EXPECTED_NS" ]]; then
  echo "{\"hookSpecificOutput\":{\"hookEventName\":\"PostToolUse\",\"additionalContext\":\"⚠️ NAMESPACE MISMATCH in $(basename "$FILE_PATH"): declared '$DECLARED_NS' but expected '$EXPECTED_NS'. Fix namespace to match folder path.\"}}"
fi

exit 0
