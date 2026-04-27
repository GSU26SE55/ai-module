# Skill: /kltn-ship (AI)

## Kích hoạt
`/kltn-ship KAN-XX` — tạo PR sau khi `/kltn-reviewcode` PASS và `/kltn-test` PASS.

---

## Quy trình

1. **Kiểm tra cuối**
   ```bash
   git status && git log main...HEAD --oneline
   ```
   Không có: model weight files lớn (`.pt`, `.pth` > 50MB → dùng Git LFS hoặc link download), raw dataset, notebook checkpoint

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
     --body "## Ticket\nKAN-XX\n\n## Thay đổi\n- \n\n## Kết quả model\n| Metric | Giá trị |\n|--------|--------|\n| MAE    |        |\n| RMSE   |        |\n\n## Test\n- [ ] FastAPI endpoint chạy được\n- [ ] Kết quả reproducible (chạy lại ra cùng số)\n- [ ] BE có thể gọi endpoint thành công"
   ```

5. **Cập nhật Jira** — chuyển sang IN REVIEW, paste link PR + tóm tắt metric vào comment

---

## Không được
- Commit model weights lớn vào Git (dùng link Hugging Face hoặc Git LFS)
- Ship mà không có kết quả metric rõ ràng trong PR description
- Merge PR của chính mình
