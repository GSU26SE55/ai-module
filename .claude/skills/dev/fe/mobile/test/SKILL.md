---
name: kltn-test (Mobile)
description: Kiểm tra chất lượng code Mobile — type check và lint, ghi kết quả vào logs/GH-[number]/test.md
argument-hint: [GH-[number]]
allowed-tools: Bash, Read, Write
---

# Skill: /kltn-test (Mobile)

> Kế thừa từ `fe/test` — thay `npm run build` và `eslint` bằng lệnh Expo tương đương.

## Kích hoạt
`/kltn-test GH-[number]` — chạy type check và lint cho Mobile, ghi kết quả vào `logs/GH-[number]/test.md`.

---

## Bước 1 — Chạy kiểm tra

```bash
# Type check
npx tsc --noEmit

# Lint (Expo lint — dựa trên ESLint config của Expo)
npx expo lint
```

Chạy từ root của Mobile repo. Cả 2 lệnh phải PASS trước khi `/kltn-ship`.

> Không có bước `npm run build` — Expo managed workflow không build local; CI/EAS xử lý build.

---

## Bước 2 — Ghi kết quả vào logs/GH-[number]/test.md

```markdown
# Test Report — GH-[number]

## Kết quả: PASS ✅ / FAIL ❌

## Ngày chạy: YYYY-MM-DD
## Platform: Mobile (React Native / Expo)

## Kiểm tra
| Bước | Lệnh | Kết quả |
|------|------|---------|
| Type check | `tsc --noEmit` | PASS / FAIL |
| Lint | `expo lint` | PASS / FAIL |

## Lỗi (nếu có)
- [Mô tả lỗi + file:line + cách fix]
```

---

## Không được
- Bỏ qua lint error bằng `// eslint-disable` để qua CI — phải fix thực sự
- `/kltn-ship` khi bất kỳ bước nào FAIL
