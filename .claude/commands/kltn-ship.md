Tạo Pull Request và cập nhật Jira. Chỉ chạy sau khi `/kltn-reviewcode` PASS và `/kltn-test` PASS.

Ticket ID: `$ARGUMENTS`

**Bước 1 — Xác định role**
Đọc CLAUDE.local.md. Nếu có **Dev Role** → dùng Dev Role. Nếu chỉ có Role → dùng Role đó.
- BE → `.claude/skills/dev/be/ship/SKILL.md`
- FE → `.claude/skills/dev/fe/ship/SKILL.md`
- AI → `.claude/skills/dev/ai/ship/SKILL.md`

**Bước 2 — Kiểm tra cuối**
```bash
git status
git log main...HEAD --oneline
```

**Bước 3 — Cập nhật status và commit logs**
Dùng Edit tool cập nhật `logs/$ARGUMENTS/plan.md`:
- `Status: TESTING` → `Status: SHIPPED`
- `Cập nhật lần cuối` → ngày hôm nay

```bash
git add logs/$ARGUMENTS/
git commit -m "docs($ARGUMENTS): thêm plan, review, test log"
```

**Bước 4 — Push branch**
```bash
git push origin HEAD
```

**Bước 5 — Tạo PR theo role**
Đọc skill file của role (từ Bước 1) → tạo PR với đúng template.

**Bước 6 — Cập nhật Jira**
Chuyển ticket `$ARGUMENTS` sang IN REVIEW, paste link PR vào comment.
