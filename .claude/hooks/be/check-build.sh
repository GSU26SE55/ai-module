#!/bin/bash
# Hook: Check dotnet build after editing .cs files

normalize_path() { echo "$1" | tr '\\' '/'; }

INPUT=$(cat)
FILE_PATH=$(normalize_path "$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')")

if [[ "$FILE_PATH" != *.cs ]]; then exit 0; fi

# Find nearest .csproj — PREV_DIR prevents infinite loop at Windows drive root
DIR=$(dirname "$FILE_PATH")
PREV_DIR=""
while [[ "$DIR" != "/" && "$DIR" != "." && "$DIR" != "$PREV_DIR" ]]; do
  CSPROJ=$(find "$DIR" -maxdepth 1 -name "*.csproj" -print -quit 2>/dev/null)
  if [[ -n "$CSPROJ" ]]; then break; fi
  PREV_DIR="$DIR"
  DIR=$(dirname "$DIR")
done

if [[ -z "$CSPROJ" ]]; then exit 0; fi

BUILD_OUTPUT=$(dotnet build "$CSPROJ" --nologo -v q 2>&1)
BUILD_EXIT=$?

if [[ $BUILD_EXIT -ne 0 ]]; then
  ERRORS=$(echo "$BUILD_OUTPUT" | grep -E "error CS|error :" | head -10)
  echo "Build errors in $(basename "$CSPROJ"):" >&2
  echo "$ERRORS" >&2
  echo "Fix these errors before continuing." >&2
  exit 2
fi

exit 0
