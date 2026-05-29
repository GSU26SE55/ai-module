# Skill: /kltn-ship (BE)

## Kích hoạt
`/kltn-ship [issue-number]` — tạo PR sau khi `/kltn-reviewcode` PASS và `/kltn-test` PASS.

---

## Quy trình

1. **Kiểm tra cuối**
   ```bash
   git status && git log dev...HEAD --oneline
   ```
   Không có: `.env`, migration chưa apply, file build artifact

2. **Commit logs**
   ```bash
   git add logs/GH-$ISSUE_NUMBER/
   git commit -m "docs(#$ISSUE_NUMBER): thêm plan, review, test log"
   ```

3. **Push branch**
   ```bash
   git push origin feature/GH-$ISSUE_NUMBER-ten-tinh-nang || { echo "❌ Push thất bại — chạy: gh auth status"; exit 1; }
   ```

4. **Tạo PR**
   ```bash
   gh pr create \
     --base dev \
     --title "feat(#$ISSUE_NUMBER): [tóm tắt ngắn gọn]" \
     --body "$(cat <<'PREOF'
   ## Closes #ISSUE_NUMBER

   ## Thay đổi
   -

   ## Test
   - [ ] API test (Swagger/Postman)
   - [ ] Migration apply thành công
   - [ ] Không break endpoint cũ
   PREOF
   )" \
   || { echo "❌ Tạo PR thất bại — chạy: gh auth status"; exit 1; }
   ```
   > Sau khi tạo xong, thay `#ISSUE_NUMBER` trong PR body bằng số issue thực tế.

5. **Cập nhật GitHub Issue → Sprint Board tự động sync**
   ```bash
   # Chuyển ticket sang cột "In Review" trên Sprint Board
   gh issue edit $ISSUE_NUMBER \
     --remove-label "status: implementing" \
     --add-label "status: reviewing"

   # Comment thông báo PR đã tạo (lấy $PR_NUMBER từ output gh pr create ở bước 4)
   gh issue comment $ISSUE_NUMBER --body "## 👀 PR đã tạo — chờ review

   **PR:** #$PR_NUMBER
   **Reviewer:** ping người review để xem PR trên GitHub và approve

   - reviewcode: ✅ PASS
   - test: ✅ PASS

   Sau khi được APPROVE, author chạy \`/kltn-complete $ISSUE_NUMBER\` để merge."
   ```
   > Sau bước này, ticket tự động chuyển từ **In Progress → In Review** trên Sprint Board.

---

## Không được
- Merge PR của chính mình
- Force push sau khi PR đã mở
- Ship khi chưa chạy `/kltn-test` PASS
