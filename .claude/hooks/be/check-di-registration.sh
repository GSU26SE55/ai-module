#!/bin/bash
# Hook: After creating new interface, check DI registration

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ "$FILE_PATH" != *.cs ]] || [[ ! -f "$FILE_PATH" ]]; then exit 0; fi

if ! echo "$FILE_PATH" | grep -qE '/(Interfaces|Services)/'; then exit 0; fi

INTERFACE=$(grep -oP 'public interface \K[A-Z]\w+' "$FILE_PATH" | head -1)
if [[ -z "$INTERFACE" ]]; then exit 0; fi

SERVICE_DIR=$(echo "$FILE_PATH" | grep -oP '.*/services/[^/]+' || echo "$FILE_PATH" | grep -oP '.*/shared/[^/]+')
if [[ -z "$SERVICE_DIR" ]]; then exit 0; fi

DI_FILE=$(find "$SERVICE_DIR" -name "ManageDependencyInjection.cs" -o -name "DependencyInjection.cs" 2>/dev/null | head -1)

if [[ -z "$DI_FILE" ]]; then
  echo "{\"hookSpecificOutput\":{\"hookEventName\":\"PostToolUse\",\"additionalContext\":\"💡 Created interface $INTERFACE — remember to register it in ManageDependencyInjection.cs\"}}"
  exit 0
fi

if ! grep -q "$INTERFACE" "$DI_FILE"; then
  echo "{\"hookSpecificOutput\":{\"hookEventName\":\"PostToolUse\",\"additionalContext\":\"💡 Interface $INTERFACE not found in $(basename "$DI_FILE"). Add: services.AddScoped<$INTERFACE, ImplementationClass>();\"}}"
fi

exit 0
