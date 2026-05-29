# Skill: /kltn-ship (AI)

## Kích hoạt
`/kltn-ship [issue-number]` — tạo PR sau khi `/kltn-reviewcode` PASS và `/kltn-test` PASS.

---

## Quy trình

1. **Kiểm tra cuối**
   ```bash
   git status && git log dev...HEAD --oneline
   ```
   Không có: model weight files lớn (`.pt`, `.pth` > 50MB → dùng Git LFS hoặc link download), raw dataset, notebook checkpoint

   Phải có: `models/weights/scaler.pkl` đã được commit (file nhỏ, bắt buộc commit cùng code)

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
     --title "feat(#$ISSUE_NUMBER): [tóm tắt ngắn gọn]" \
     --body "$(cat <<'PREOF'
   ## Closes #ISSUE_NUMBER

   ## Thay đổi
   -

   ## Kết quả model
   | Metric | Giá trị | Target |
   |--------|---------|--------|
   | MAE    |         | < 2%   |
   | RMSE   |         | < 3%   |
   | F1     |         | > 0.80 |

   ## Test
   - [ ] FastAPI endpoint chạy được (uvicorn)
   - [ ] Kết quả reproducible (chạy lại ra cùng số)
   - [ ] scaler.pkl được commit tại models/weights/
   - [ ] BE có thể gọi endpoint thành công (CORS OK)
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
   - pytest + coverage: ✅ PASS
   - inference latency < 100ms: ✅ PASS

   Sau khi được APPROVE, author chạy \`/kltn-complete $ISSUE_NUMBER\` để merge."
   ```
   > Sau bước này, ticket tự động chuyển từ **In Progress → In Review** trên Sprint Board.

---

## Không được
- Commit model weights lớn vào Git (dùng link Hugging Face hoặc Git LFS)
- Ship mà không có kết quả metric rõ ràng trong PR description
- Merge PR của chính mình
