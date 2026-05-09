#!/bin/bash
# Hook: After editing .cs files, check for common anti-patterns

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ "$FILE_PATH" != *.cs ]]; then exit 0; fi

WARNINGS=""

# Entity phải extends AuditableEntity
if echo "$FILE_PATH" | grep -q "/Entities/"; then
  if [[ -f "$FILE_PATH" ]]; then
    if ! grep -q "AuditableEntity" "$FILE_PATH"; then
      WARNINGS="${WARNINGS}⚠️ Entity '$FILE_PATH' does not extend AuditableEntity.\n"
    fi
  fi
fi

# CommandHandler phải dùng UnitOfWork — QueryHandler là read-only, không cần
if echo "$FILE_PATH" | grep -q "Handler" && ! echo "$FILE_PATH" | grep -qE "Query|Get"; then
  if [[ -f "$FILE_PATH" ]]; then
    if ! grep -q "UnitOfWork" "$FILE_PATH"; then
      WARNINGS="${WARNINGS}⚠️ CommandHandler '$FILE_PATH' does not inject UnitOfWork.\n"
    fi
  fi
fi

# Không await UpdateAsync/DeleteAsync (void methods)
if [[ -f "$FILE_PATH" ]]; then
  if grep -qE 'await\s+.*\.(UpdateAsync|DeleteAsync)\(' "$FILE_PATH"; then
    WARNINGS="${WARNINGS}⚠️ Found 'await UpdateAsync/DeleteAsync' in '$FILE_PATH'. These are void — remove await.\n"
  fi
fi

# Controller không nên có business logic
if echo "$FILE_PATH" | grep -q "Controller"; then
  if [[ -f "$FILE_PATH" ]]; then
    LINE_COUNT=$(wc -l < "$FILE_PATH")
    METHOD_COUNT=$(grep -c "public async Task<IActionResult>" "$FILE_PATH" 2>/dev/null || echo 0)
    if [[ $METHOD_COUNT -gt 0 ]]; then
      AVG=$((LINE_COUNT / METHOD_COUNT))
      if [[ $AVG -gt 20 ]]; then
        WARNINGS="${WARNINGS}💡 Controller '$FILE_PATH': avg $AVG lines/method. Controllers should only call _mediator.Send().\n"
      fi
    fi
  fi
fi

if [[ -n "$WARNINGS" ]]; then
  echo -e "$WARNINGS"
fi

exit 0
