# Skill: /kltn-ship (FE)

## Kích hoạt
`/kltn-ship [issue-number]` — tạo PR sau khi `/kltn-reviewcode` PASS.

---

## Quy trình

1. **Kiểm tra gate trước khi ship**

   Bắt buộc xác nhận đủ 2 điều kiện:
   - `logs/GH-$ISSUE_NUMBER/review.md` tồn tại và kết luận **PASS**
   - `logs/GH-$ISSUE_NUMBER/test.md` tồn tại và kết quả **PASS** (tsc + eslint + build)

   ```bash
   cat logs/GH-$ISSUE_NUMBER/review.md | grep -i "kết luận"
   cat logs/GH-$ISSUE_NUMBER/test.md   | grep -i "kết quả"
   ```

   Nếu thiếu file hoặc FAIL → chạy lại `/kltn-reviewcode` / `/kltn-test` trước.

2. **Kiểm tra cuối**
   ```bash
   git status && git log dev...HEAD --oneline
   ```
   Không có: `.env`, `node_modules`, file build (`dist/`, `.expo/`)

3. **Commit logs** (bao gồm cả test.md)
   ```bash
   git add logs/GH-$ISSUE_NUMBER/
   git commit -m "docs(#$ISSUE_NUMBER): thêm plan, review, test log"
   ```

4. **Push branch**
   ```bash
   git push origin feature/GH-$ISSUE_NUMBER-ten-tinh-nang || { echo "❌ Push thất bại — chạy: gh auth status"; exit 1; }
   ```

5. **Tạo PR**
   ```bash
   gh pr create \
     --title "feat(#$ISSUE_NUMBER): [tóm tắt ngắn gọn]" \
     --body "$(cat <<'PREOF'
   ## Closes #ISSUE_NUMBER

   ## Thay đổi
   -

   ## Quality gates
   - [x] /kltn-reviewcode PASS
   - [x] tsc --noEmit PASS
   - [x] eslint --max-warnings=0 PASS
   - [x] npm run build PASS

   ## Checklist
   - [ ] Chạy được trên browser/device
   - [ ] Không break trang/screen khác
   - [ ] Responsive (nếu là Web)
   PREOF
   )" \
   || { echo "❌ Tạo PR thất bại — chạy: gh auth status"; exit 1; }
   ```
   > Sau khi tạo xong, thay `#ISSUE_NUMBER` trong PR body bằng số issue thực tế.

6. **Cập nhật GitHub Issue → Sprint Board tự động sync**
   ```bash
   # Chuyển ticket sang cột "In Review" trên Sprint Board
   gh issue edit $ISSUE_NUMBER \
     --remove-label "status: implementing" \
     --add-label "status: reviewing"

   # Comment thông báo PR đã tạo (lấy $PR_NUMBER từ output gh pr create ở bước 5)
   gh issue comment $ISSUE_NUMBER --body "## 👀 PR đã tạo — chờ review

   **PR:** #$PR_NUMBER
   **Reviewer:** ping @[tên reviewer] để chạy \`/kltn-reviewpr $ISSUE_NUMBER\`

   - reviewcode: ✅ PASS
   - tsc --noEmit: ✅ PASS
   - eslint: ✅ PASS
   - build: ✅ PASS"
   ```
   > Sau bước này, ticket tự động chuyển từ **In Progress → In Review** trên Sprint Board.

---

## Không được
- Merge PR của chính mình
- Force push sau khi PR đã mở
- Ship khi `/kltn-reviewcode` hoặc `/kltn-test` chưa PASS
