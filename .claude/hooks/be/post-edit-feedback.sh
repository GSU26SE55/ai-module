#!/bin/bash
# Hook: After editing .cs files, check for common anti-patterns

normalize_path() { echo "$1" | tr '\\' '/'; }

INPUT=$(cat)
FILE_PATH=$(normalize_path "$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')")

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
  if grep -vE '^\s*//' "$FILE_PATH" | grep -qE 'await\s+[^;]*\.(UpdateAsync|DeleteAsync)\s*\('; then
    WARNINGS="${WARNINGS}⚠️ Found 'await UpdateAsync/DeleteAsync' in '$FILE_PATH'. These are VOID — remove await.\n"
  fi
fi

# Không await GetAllAsync — phương thức này là SYNC, trả IQueryable trực tiếp
# Tên "Async" là legacy từ SharedKernel, dễ nhầm
if [[ -f "$FILE_PATH" ]]; then
  if grep -vE '^\s*//' "$FILE_PATH" | grep -qE 'await\s+[^;]*\.GetAllAsync\s*\('; then
    WARNINGS="${WARNINGS}⚠️ Found 'await GetAllAsync()' in '$FILE_PATH'. GetAllAsync là SYNC (trả IQueryable) — bỏ await.\n"
  fi
fi

# QueryHandler phải filter IsDeleted — dự án không dùng global query filter
# Kiểm tra cụ thể: GetAllAsync() có được chain với .Where(x => !x.IsDeleted) không
if echo "$FILE_PATH" | grep -qE "(Query|Get).*Handler"; then
  if [[ -f "$FILE_PATH" ]]; then
    if grep -q "GetAllAsync()" "$FILE_PATH"; then
      if ! grep -qE '\.Where\([^)]*!.*IsDeleted|\.Where\([^)]*IsDeleted\s*==\s*false' "$FILE_PATH"; then
        WARNINGS="${WARNINGS}⚠️ QueryHandler '$FILE_PATH' dùng GetAllAsync() nhưng không có .Where(x => !x.IsDeleted). Thêm filter trước khi query.\n"
      fi
    fi
  fi
fi

# Controller không nên có business logic — chỉ gọi _mediator.Send()
if echo "$FILE_PATH" | grep -q "Controller"; then
  if [[ -f "$FILE_PATH" ]]; then
    # Đếm số dòng chứa logic thực sự (ngoài attribute, signature, curly brace, blank line)
    LOGIC_LINES=$(grep -vE '^\s*(\[|//|{|}|public|private|using|namespace|$)' "$FILE_PATH" | wc -l)
    METHOD_COUNT=$(grep -c "public async Task<IActionResult>" "$FILE_PATH" 2>/dev/null || echo 0)
    if [[ $METHOD_COUNT -gt 0 ]]; then
      AVG=$((LOGIC_LINES / METHOD_COUNT))
      if [[ $AVG -gt 5 ]]; then
        WARNINGS="${WARNINGS}💡 Controller '$FILE_PATH': ~$AVG logic lines/method. Controller chỉ nên gọi _mediator.Send() — di chuyển logic vào CommandHandler.\n"
      fi
    fi
  fi
fi

if [[ -n "$WARNINGS" ]]; then
  printf "%b" "$WARNINGS"
fi

exit 0
