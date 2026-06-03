Tạo Pull Request, tạo handoff file, và cập nhật GitHub Issue. Chỉ chạy sau khi `/kltn-reviewcode` PASS và `/kltn-test` PASS.

Issue number: `$ARGUMENTS`

**Bước 1 — Xác định branch hiện tại**
```bash
git branch --show-current
```

- Nếu đang đứng ở nhánh `feat/GH-$ARGUMENTS-...` hoặc `fix/GH-$ARGUMENTS-...` → ghi nhớ `$BRANCH_NAME`, tiếp tục Bước 2.
- Nếu đang đứng ở `dev` → liệt kê toàn bộ branch để xác định đúng branch:
  ```bash
  git branch | grep "GH-$ARGUMENTS"
  ```
  Sau đó checkout branch tìm được trước khi tiếp tục.

**Bước 2 — Xác định role**
Đọc CLAUDE.local.md. Nếu có **Dev Role** → dùng Dev Role. Nếu chỉ có Role → dùng Role đó.
- BE → `.claude/skills/dev/be/ship/SKILL.md`
- FE → `.claude/skills/dev/fe/ship/SKILL.md`
- AI → `.claude/skills/dev/ai/ship/SKILL.md`

**Bước 3 — Kiểm tra cuối**
```bash
git status
git log dev...HEAD --oneline
```

**Bước 4 — Cập nhật status và commit logs**
Dùng Edit tool cập nhật `logs/GH-$ARGUMENTS/plan.md`:
- `Status: TESTING` → `Status: SHIPPED`
  *(SHIPPED = PR đã tạo + test pass, đang chờ reviewer approve)*
- `Cập nhật lần cuối` → ngày hôm nay

```bash
git add logs/GH-$ARGUMENTS/
git commit -m "docs(#$ARGUMENTS): thêm plan, review, test log"
```

**Bước 5 — Push branch**
```bash
git push origin HEAD
```

**Bước 6 — Tạo PR theo role**
Đọc skill file của role (từ Bước 2) → tạo PR với đúng template.

Body PR **bắt buộc có dòng** `Closes #$ARGUMENTS` để GitHub tự close issue khi merge.

Sau khi PR được tạo thành công, ghi nhớ `$PR_NUMBER` và `$PR_URL` từ output của `gh pr create`.

Dùng Edit tool cập nhật `logs/GH-$ARGUMENTS/plan.md` — thêm dòng PR vào phần header:
```
PR: #$PR_NUMBER — $PR_URL
```

**Bước 7 — Tạo handoff file**
Dùng Write tool tạo `logs/GH-$ARGUMENTS/handoff.md`:

```markdown
# HANDOFF — GH-[number]: [Tên issue]

## Thông tin
- **Người thực hiện:** [tên từ CLAUDE.local.md]
- **Ngày ship:** YYYY-MM-DD
- **Status:** SHIPPED ⏳ (chờ reviewer approve)
- **Issue:** #[number]
- **PR:** #$PR_NUMBER — $PR_URL
- **Branch:** $BRANCH_NAME

## Tiến độ Steps
[Copy nguyên ## Steps từ plan.md — tất cả phải [x]]

## Những gì đã làm
[Tóm tắt từ danh sách Files trong plan.md]

## Kết quả
- reviewcode: PASS
- test: PASS
- PR: tạo thành công — chờ reviewer approve

## Ghi chú
[Thông tin kỹ thuật quan trọng: migration đã chạy, breaking change, cần update config...]
```

**Bước 8 — Commit handoff và push lên branch**

```bash
git add logs/GH-$ARGUMENTS/
git commit -m "docs(#$ARGUMENTS): gắn PR #$PR_NUMBER vào plan + thêm handoff"
git push origin HEAD
```

**Bước 9 — Cập nhật GitHub Issue**

```bash
# Chuyển label status: implementing → status: reviewing
gh issue edit $ARGUMENTS \
  --remove-label "status: implementing" \
  --add-label "status: reviewing"

# Comment thông báo PR đã tạo
gh issue comment $ARGUMENTS --body "## 👀 PR đã tạo — chờ review

**PR:** #$PR_NUMBER — $PR_URL
**Reviewer:** ping người review để xem PR trên GitHub và approve

- reviewcode: ✅ PASS
- test: ✅ PASS

Sau khi được APPROVE, author chạy \`/kltn-complete $ARGUMENTS\` để merge."
```

---

Sau bước này, nhắc user:
```
Ship xong. PR #$PR_NUMBER đang chờ reviewer approve trên GitHub.
Sau khi được approve, chạy /kltn-complete $ARGUMENTS để merge.
```
