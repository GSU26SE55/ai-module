Tạo Pull Request và cập nhật Jira. Chỉ chạy sau khi `/kltn-reviewcode` PASS và `/kltn-test` PASS.

Ticket ID: `$ARGUMENTS`

**Bước 1 — Kiểm tra cuối**
```bash
git status
git log main...HEAD --oneline
```

**Bước 2 — Push branch**
```bash
git push origin HEAD
```

**Bước 3 — Tạo PR theo role**
Đọc `.claude/skills/dev/[role]/ship.md` → tạo PR với đúng template.

**Bước 4 — Cập nhật Jira**
Chuyển ticket `$ARGUMENTS` sang IN REVIEW, paste link PR vào comment.
