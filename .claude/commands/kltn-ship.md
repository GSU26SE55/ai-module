Tạo Pull Request và cập nhật Jira. Chỉ chạy sau khi `/kltn-reviewcode` PASS và `/kltn-test` PASS.

Ticket ID: `$ARGUMENTS`

**Bước 1 — Xác định branch hiện tại**
```bash
git branch --show-current
```

- Nếu đang đứng ở nhánh `feature/KAN-XX-...` → ghi nhớ `$BRANCH_NAME`, tiếp tục Bước 2.
- Nếu đang đứng ở `main` → liệt kê toàn bộ branch để xác định đúng feature branch:
  ```bash
  git branch
  ```
  Sau đó `git checkout feature/KAN-XX-...` trước khi tiếp tục.

**Bước 2 — Xác định role**
Đọc CLAUDE.local.md. Nếu có **Dev Role** → dùng Dev Role. Nếu chỉ có Role → dùng Role đó.
- BE → `.claude/skills/dev/be/ship/SKILL.md`
- FE → `.claude/skills/dev/fe/ship/SKILL.md`
- AI → `.claude/skills/dev/ai/ship/SKILL.md`

**Bước 3 — Kiểm tra cuối**
```bash
git status
git log main...HEAD --oneline
```

**Bước 4 — Cập nhật status và commit logs**
Dùng Edit tool cập nhật `logs/$ARGUMENTS/plan.md`:
- `Status: TESTING` → `Status: SHIPPED`
  *(SHIPPED = PR đã tạo + test pass, đang chờ reviewer approve)*
- `Cập nhật lần cuối` → ngày hôm nay

```bash
git add logs/$ARGUMENTS/
git commit -m "docs($ARGUMENTS): thêm plan, review, test log"
```

**Bước 5 — Push branch**
```bash
git push origin HEAD
```

**Bước 6 — Tạo PR theo role**
Đọc skill file của role (từ Bước 2) → tạo PR với đúng template.

Sau khi PR được tạo thành công, ghi nhớ `$PR_NUMBER` và `$PR_URL` từ output của `gh pr create`.

Dùng Edit tool cập nhật `logs/$ARGUMENTS/plan.md` — thêm dòng PR vào phần header:
```
PR: #$PR_NUMBER — $PR_URL
```

```bash
git add logs/$ARGUMENTS/plan.md
git commit -m "docs($ARGUMENTS): gắn PR #$PR_NUMBER vào plan"
git push origin HEAD
```

**Bước 7 — Cập nhật Jira**
Chuyển ticket `$ARGUMENTS` sang **IN REVIEW**.
Thêm comment (tiếng Việt):
"Đã tạo PR #$PR_NUMBER. Link: $PR_URL. Đang chờ reviewer approve."
