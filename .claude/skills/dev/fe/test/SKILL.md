---
name: kltn-test (FE)
description: Kiểm tra chất lượng code FE — type check và lint, ghi kết quả vào logs/GH-[number]/test.md
argument-hint: [GH-[number]]
allowed-tools: Bash, Read, Write
---

# Skill: /kltn-test (FE)

## Kích hoạt
`/kltn-test GH-[number]` — chạy type check và lint cho FE, ghi kết quả vào `logs/GH-[number]/test.md`.

---

## Bước 1 — Chạy kiểm tra

```bash
# Type check
npx tsc --noEmit

# Lint (CI-level: không được có warning)
npx eslint . --max-warnings=0

# Build (đảm bảo production build không lỗi)
npm run build
```

Chạy từ root của FE repo. Tất cả 3 lệnh phải PASS trước khi `/kltn-ship`.

---

## Bước 2 — Ghi kết quả vào logs/GH-[number]/test.md

```markdown
# Test Report — GH-[number]

## Kết quả: PASS ✅ / FAIL ❌

## Ngày chạy: YYYY-MM-DD

## Kiểm tra
| Bước | Lệnh | Kết quả |
|------|------|---------|
| Type check | `tsc --noEmit` | PASS / FAIL |
| Lint | `eslint --max-warnings=0` | PASS / FAIL |
| Build | `npm run build` | PASS / FAIL |

## Lỗi (nếu có)
- [Mô tả lỗi + file:line + cách fix]
```

---

## Không được
- Bỏ qua lint error bằng `// eslint-disable` để qua CI — phải fix thực sự
- `/kltn-ship` khi bất kỳ bước nào FAIL
