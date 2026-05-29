# Skill: /kltn-ship (Mobile)

> Kế thừa từ `fe/ship` — thay quality gate build bằng lệnh Expo, PR checklist Mobile-specific.

## Kích hoạt
`/kltn-ship [issue-number]` — tạo PR sau khi `/kltn-reviewcode` PASS.

---

## Quy trình

### 1. Kiểm tra gate trước khi ship

```bash
cat logs/GH-$ISSUE_NUMBER/review.md | grep -i "kết luận"
cat logs/GH-$ISSUE_NUMBER/test.md   | grep -i "kết quả"
```

Bắt buộc:
- `review.md` kết luận **PASS**
- `test.md` kết quả **PASS** (tsc + expo lint)

Nếu thiếu file hoặc FAIL → chạy lại trước.

### 2. Kiểm tra cuối

```bash
git status && git log dev...HEAD --oneline
```

Không có: `.env`, `node_modules`, `.expo/`, `android/`, `ios/` build artifacts.

### 3. Commit logs

```bash
git add logs/GH-$ISSUE_NUMBER/
git commit -m "docs(#$ISSUE_NUMBER): thêm plan, review, test log"
```

### 4. Push branch

```bash
git push origin feature/GH-$ISSUE_NUMBER-ten-tinh-nang || { echo "❌ Push thất bại — chạy: gh auth status"; exit 1; }
```

### 5. Tạo PR

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
- [x] expo lint PASS

## Checklist
- [ ] Chạy được trên iOS simulator
- [ ] Chạy được trên Android emulator
- [ ] Không break screen khác
- [ ] Token lưu đúng (expo-secure-store)
- [ ] Navigation đúng Expo Router pattern
PREOF
)" \
|| { echo "❌ Tạo PR thất bại — chạy: gh auth status"; exit 1; }
```

> Sau khi tạo xong, thay `#ISSUE_NUMBER` trong PR body bằng số issue thực tế.

### 6. Cập nhật GitHub Issue

```bash
gh issue edit $ISSUE_NUMBER \
  --remove-label "status: implementing" \
  --add-label "status: reviewing"

gh issue comment $ISSUE_NUMBER --body "## 👀 PR đã tạo — chờ review

**PR:** #$PR_NUMBER

- reviewcode: ✅ PASS
- tsc --noEmit: ✅ PASS
- expo lint: ✅ PASS

Sau khi được APPROVE, author chạy \`/kltn-complete $ISSUE_NUMBER\` để merge."
```

---

## Không được
- Merge PR của chính mình
- Force push sau khi PR đã mở
- Ship khi `/kltn-reviewcode` hoặc `/kltn-test` chưa PASS
- Commit file `android/` hoặc `ios/` từ EAS local build
