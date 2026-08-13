Fix bug từ issue được tạo bởi log sheet. Tự động detect branch, đọc lỗi, tìm nguyên nhân, fix và push.

Issue number: `$ARGUMENTS`

---

**Bước 0 — Xác định role**

Đọc CLAUDE.local.md. Nếu có **Dev Role** → dùng Dev Role. Nếu chỉ có Role → dùng Role đó.
- BE → `.claude/skills/dev/be/debug/SKILL.md`
- FE → `.claude/skills/dev/fe/debug/SKILL.md`
- AI → `.claude/skills/dev/ai/debug/SKILL.md`

Đọc skill file tương ứng — dùng checklist và common root causes trong đó để phân tích lỗi (Bước 4).

---

**Bước 1 — Đọc issue**

```bash
gh issue view $ARGUMENTS --json number,title,body,labels,assignees
```

Đọc kỹ:
- **Title + Body:** mô tả lỗi, stack trace, steps to reproduce, expected vs actual behavior
- **Labels:** xác định role (`role: BE` / `role: FE` / `role: AI`)

---

**Bước 2 — Xác định và checkout branch**

```bash
git branch --show-current
```

Kiểm tra branch hiện tại:
- Nếu đang đứng ở `feat/GH-$ARGUMENTS-...` hoặc `fix/GH-$ARGUMENTS-...` → dùng luôn, ghi nhớ `$BRANCH_NAME`
- Nếu không → tìm branch liên quan đến issue:

```bash
git branch -a | grep "GH-$ARGUMENTS"
```

  - **Tìm thấy** → checkout:
    ```bash
    git fetch origin
    BRANCH=$(git branch -a | grep "GH-$ARGUMENTS" | head -1 | sed 's|remotes/origin/||' | xargs)
    git checkout $BRANCH
    git pull origin $BRANCH
    ```
  - **Không tìm thấy** → tạo branch mới từ dev:
    ```bash
    git fetch origin
    git checkout dev
    git pull origin dev
    git checkout -b fix/GH-$ARGUMENTS-ten-loi-ngan
    ```
    Ghi nhớ `$BRANCH_NAME` = branch vừa tạo.

---

**Bước 3 — Kiểm tra PR hiện có**

```bash
gh pr list --search "GH-$ARGUMENTS in:title OR #$ARGUMENTS in:title" \
  --json number,title,url,state,headRefName
```

Ghi nhớ:
- Nếu **có PR** (`state: OPEN`) → `$HAS_PR = true`, `$PR_NUMBER` = số PR
- Nếu **không có PR** → `$HAS_PR = false`

---

**Bước 4 — Phân tích lỗi**

Đọc kỹ body của issue, sau đó truy tìm nguyên nhân:

**4a. Xác định vị trí lỗi**

Dựa vào stack trace / mô tả trong issue, xác định file và function liên quan. Đọc code tại đó.

**4b. Reproduce mentally**

Trace qua logic: input → xử lý → output — tìm điểm nào cho kết quả sai so với expected.

**4c. Đặt hypothesis**

Liệt kê nguyên nhân khả năng (tối đa 3), ưu tiên từ đơn giản nhất:
```
Hypothesis 1: [mô tả]
Hypothesis 2: [mô tả]
Hypothesis 3: [mô tả]
```

Chọn hypothesis cao nhất để fix trước. Nếu chưa đủ thông tin để chọn → hỏi user trước khi tiếp tục.

---

**Bước 5 — Fix**

Chỉ sửa những gì cần thiết để fix lỗi:
- Không refactor code lân cận
- Không thêm feature ngoài scope bug fix
- Không đổi naming convention hay style

Sau khi fix xong, verify lại:
- BE: `dotnet build` — không lỗi
- FE: `npx tsc --noEmit` — không lỗi
- AI: `python -c "import src"` hoặc `pytest tests/ -x -q`

---

**Bước 6 — Commit**

```bash
git add [files đã sửa]
git commit -m "fix(#$ARGUMENTS): [mô tả ngắn fix gì]"
```

---

**Bước 7 — Push và cập nhật issue**

**Nếu `$HAS_PR = true`** (branch đã có PR mở):
```bash
git push origin $BRANCH_NAME
```

Sau đó comment lên PR:
```bash
gh pr comment $PR_NUMBER --body "## 🔧 Bug fix pushed

**Issue:** #$ARGUMENTS
**Fix:** [tóm tắt nguyên nhân và cách fix]
**Commit:** [commit hash ngắn]"
```

Nhắc user:
```
Fix đã push lên PR #$PR_NUMBER. Reviewer xem commit mới trên PR để verify.
```

---

**Nếu `$HAS_PR = false`** (branch chưa có PR):
```bash
git push origin $BRANCH_NAME
```

Tạo PR:
```bash
gh pr create \
  --title "fix(#$ARGUMENTS): [tóm tắt lỗi]" \
  --body "$(cat <<'PREOF'
## Closes #ARGUMENTS

## Lỗi
[Mô tả lỗi từ issue]

## Nguyên nhân
[Root cause]

## Fix
[Cách fix]
PREOF
)"
```

Cập nhật label:
```bash
gh issue edit $ARGUMENTS \
  --remove-label "status: implementing" \
  --add-label "status: reviewing"
```

Nhắc user:
```
PR đã tạo. Reviewer xem PR trên GitHub và approve.
Sau khi approve, chạy /kltn-complete $ARGUMENTS để merge.
```
