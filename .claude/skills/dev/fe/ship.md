# Skill: /kltn-ship (FE)

## Kích hoạt
`/kltn-ship KAN-XX` — tạo PR sau khi `/kltn-reviewcode` PASS và `/kltn-test` PASS.

---

## Quy trình

1. **Kiểm tra cuối**
   ```bash
   git status && git log main...HEAD --oneline
   ```
   Không có: `.env`, `node_modules`, file build (`.next/`, `dist/`, `.expo/`)

2. **Commit logs**
   ```bash
   git add logs/KAN-XX/
   git commit -m "docs(KAN-XX): thêm plan, review, test log"
   ```

3. **Push branch**
   ```bash
   git push origin feature/KAN-XX-ten-tinh-nang
   ```

4. **Tạo PR**
   ```bash
   gh pr create \
     --title "feat(KAN-XX): [tóm tắt]" \
     --body "## Ticket\nKAN-XX\n\n## Thay đổi\n- \n\n## Test\n- [ ] Chạy được trên browser/device\n- [ ] Không break trang/screen khác\n- [ ] Responsive (nếu là Web)"
   ```

5. **Cập nhật Jira** — chuyển sang IN REVIEW, paste link PR vào comment

---

## Không được
- Merge PR của chính mình
- Force push sau khi PR đã mở
- Ship khi chưa chạy `/kltn-test` PASS
