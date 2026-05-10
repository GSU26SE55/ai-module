#!/bin/bash
# Hook: After creating new entity, remind to add DbSet and run migration

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ "$FILE_PATH" != *.cs ]] || [[ ! -f "$FILE_PATH" ]]; then exit 0; fi

if ! echo "$FILE_PATH" | grep -q '/Entities/'; then exit 0; fi
if ! grep -q 'AuditableEntity' "$FILE_PATH"; then exit 0; fi

ENTITY_NAME=$(grep -oE 'public class [A-Za-z0-9]+' "$FILE_PATH" | head -1 | sed 's/public class //')
if [[ -z "$ENTITY_NAME" ]]; then exit 0; fi
ENTITY_NAME=$(echo "$ENTITY_NAME" | tr -d '"\\/')

SERVICE_DIR=$(echo "$FILE_PATH" | grep -oE '.*/services/[^/]+')
if [[ -z "$SERVICE_DIR" ]]; then exit 0; fi

DB_CONTEXT=$(find "$SERVICE_DIR" -name "ApplicationDbContext.cs" 2>/dev/null | head -1)
if [[ -z "$DB_CONTEXT" ]]; then exit 0; fi

if grep -q "DbSet<$ENTITY_NAME>" "$DB_CONTEXT"; then exit 0; fi

MSG="🆕 NEW ENTITY: $ENTITY_NAME detected. Next steps:"
MSG="$MSG\n1. Add DbSet<$ENTITY_NAME> to ApplicationDbContext.cs"
MSG="$MSG\n2. Add IGenericRepository<$ENTITY_NAME> to IServiceUnitOfWork"
MSG="$MSG\n3. Initialize GenericRepository<$ENTITY_NAME> in UnitOfWork constructor"
MSG="$MSG\n4. Run: dotnet ef migrations add Add$ENTITY_NAME"

echo "{\"hookSpecificOutput\":{\"hookEventName\":\"PostToolUse\",\"additionalContext\":\"$MSG\"}}"
exit 0
