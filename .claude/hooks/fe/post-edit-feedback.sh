#!/bin/bash
# Hook: After editing .ts/.tsx files, check for FE anti-patterns

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ "$FILE_PATH" != *.ts && "$FILE_PATH" != *.tsx ]]; then exit 0; fi

if echo "$FILE_PATH" | grep -qE '/(node_modules|dist|build|\.next|shared/components/ui)/'; then exit 0; fi

if [[ ! -f "$FILE_PATH" ]]; then exit 0; fi

WARNINGS=""

# console.log còn sót lại — bỏ qua dòng comment thuần và inline comment
CONSOLE_HITS=$(grep -E 'console\.(log|warn|error|debug)\(' "$FILE_PATH" \
  | grep -vE '^\s*(//|/?\*)' \
  | grep -vE '//.*console\.(log|warn|error|debug)')
if [[ -n "$CONSOLE_HITS" ]]; then
  WARNINGS="${WARNINGS}⚠️ console.log found in '$FILE_PATH' — remove before shipping.\n"
fi

# Hardcode API URL — bỏ qua: localhost, test/spec file, dòng comment, VITE_ env usage
if ! echo "$FILE_PATH" | grep -qE '\.(test|spec)\.(ts|tsx)$'; then
  if grep -E '"https?://[^"]*"' "$FILE_PATH" | grep -qvE 'localhost|127\.0\.0\.1|0\.0\.0\.0|^\s*(//|/?\*)|import\.meta\.env\.VITE_'; then
    WARNINGS="${WARNINGS}⚠️ Hardcoded URL in '$FILE_PATH'. Use env.VITE_API_BASE_URL instead.\n"
  fi
fi

# Token trong localStorage — critical
if grep -qE "localStorage\.(setItem|getItem)\s*\(\s*['\"][^'\"]*[Tt]oken" "$FILE_PATH"; then
  WARNINGS="${WARNINGS}🔴 CRITICAL: Token stored in localStorage in '$FILE_PATH'. Use js-cookie via sessionStore instead.\n"
fi

# Gọi axios/fetch trực tiếp trong component hoặc page (không qua services/)
if echo "$FILE_PATH" | grep -qE '/(pages|components)/'; then
  if grep -qE '(axios\.(get|post|put|patch|delete)\s*\(|fetch\s*\()' "$FILE_PATH"; then
    WARNINGS="${WARNINGS}⚠️ Direct API call in component '$FILE_PATH'. Move to features/<name>/services/ → useQuery/useMutation hook.\n"
  fi
fi

# Cross-feature import (features/A import từ features/B)
# Bắt cả relative path ('../features/...') lẫn path alias ('@/features/...' hoặc '~/features/...')
FEATURE_NAME=$(echo "$FILE_PATH" | grep -oE 'features/[^/]+' | head -1 | cut -d'/' -f2)
if [[ -n "$FEATURE_NAME" ]]; then
  CROSS=$(grep -oE "from\s+['\"](@|~|\.\.?)?/?[^'\"]*features/[a-zA-Z0-9_-]+" "$FILE_PATH" 2>/dev/null \
    | grep -v "features/$FEATURE_NAME" | head -1)
  if [[ -n "$CROSS" ]]; then
    TARGET=$(echo "$CROSS" | grep -oE 'features/[a-zA-Z0-9_-]+')
    WARNINGS="${WARNINGS}⚠️ Cross-feature import in '$FILE_PATH' (→ $TARGET). Use shared/ instead. Note: ESLint no-restricted-imports is the authoritative guard.\n"
  fi
fi

# Tạo Axios instance mới thay vì dùng shared/lib/axios.ts
if grep -qE 'axios\.create\s*\(' "$FILE_PATH"; then
  if ! echo "$FILE_PATH" | grep -q 'shared/lib/axios'; then
    WARNINGS="${WARNINGS}⚠️ New Axios instance created in '$FILE_PATH'. Use shared/lib/axios.ts — do not create new instances.\n"
  fi
fi

if [[ -n "$WARNINGS" ]]; then
  echo -e "$WARNINGS"
fi

exit 0
