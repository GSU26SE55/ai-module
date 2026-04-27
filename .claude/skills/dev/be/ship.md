# Skill: /kltn-ship (BE)

## Kích hoạt
`/kltn-ship KAN-XX` — tạo PR sau khi `/kltn-reviewcode` PASS và `/kltn-test` PASS.

---

## Quy trình

1. **Kiểm tra cuối**
   ```bash
   git status && git log main...HEAD --oneline
   ```
   Không có: `.env`, migration chưa apply, file build artifact

2. **Push branch**
   ```bash
   git push origin feature/KAN-XX-ten-tinh-nang
   ```

3. **Tạo PR**
   ```bash
   gh pr create \
     --title "feat(KAN-XX): [tóm tắt]" \
     --body "## Ticket\nKAN-XX\n\n## Thay đổi\n- \n\n## Test\n- [ ] API test (Swagger/Postman)\n- [ ] Migration apply thành công\n- [ ] Không break endpoint cũ"
   ```

4. **Cập nhật Jira** — chuyển sang IN REVIEW, paste link PR vào comment

---

## Không được
- Merge PR của chính mình
- Force push sau khi PR đã mở
- Ship khi chưa chạy `/kltn-test` PASS
