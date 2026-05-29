# Skill: /kltn-debug (FE)

## Kích hoạt
`/kltn-debug [issue-number]` — fix bug từ issue được tạo bởi log sheet.

---

## ACTION-FIRST RULE

**Đọc issue body thực sự TRƯỚC khi viết bất cứ điều gì.**

```bash
gh issue view $ISSUE_NUMBER --json number,title,body,labels
```

Tool calls trước, text output sau. Không đoán lỗi từ title.

---

## Phân tích lỗi FE

### 1. Đọc mô tả lỗi

Từ body issue, xác định:
- **Error message / console error:** `TypeError`, `Cannot read properties of undefined`, `401 Unauthorized`...
- **Component / page** bị lỗi
- **Steps to reproduce:** thao tác nào trigger lỗi
- **Expected vs Actual behavior**

### 2. Trace nguyên nhân theo layer

```
Page/Component → Hook (TanStack Query) → Service → Axios → API
```

Đọc component liên quan, sau đó hook, sau đó service nếu cần.

### 3. Common root causes FE

| Triệu chứng | Nguyên nhân thường gặp |
|------------|----------------------|
| `Cannot read properties of undefined` | Data từ API chưa có nhưng đã access — thiếu optional chaining `?.` hoặc loading guard |
| White screen / crash | Exception không được catch trong component — thiếu ErrorBoundary hoặc conditional render |
| 401 sau khi refresh | Token refresh race condition — `isRefreshing` flag bị reset sớm |
| Form submit không có lỗi dưới input | Dùng `onError` thay vì `try-catch + handleErrorApi({ error, setError })` |
| Query không update sau mutation | `invalidateQueries` dùng sai key — check `KEY` vs `QUERY_KEY` |
| Cross-feature import lỗi runtime | `features/A` import từ `features/B` — vi phạm isolation |
| Token còn hạn nhưng bị logout | `decodeToken` fail silent — thiếu try-catch khi decode JWT |
| Route không load | Route chưa khai báo trong `router/index.tsx` hoặc thiếu `ProtectedRoute` wrap |
| Loading vô hạn | `isHydrating` không reset về `false` trong AuthContext |

### 4. Verify trước khi fix

```bash
# Type check — không lỗi
npx tsc --noEmit

# Lint — không warning
npx eslint [file-đã-sửa] --max-warnings=0
```

---

## Checklist fix

- [ ] Fix đúng hypothesis — không sửa code không liên quan
- [ ] Optional chaining đủ: `data?.field` thay vì `data.field` khi data có thể undefined
- [ ] Loading state được guard trước khi render data
- [ ] Không tạo Axios instance mới — dùng `shared/lib/axios.ts`
- [ ] Không dùng `localStorage` cho token
- [ ] `tsc --noEmit` — không lỗi sau khi fix
- [ ] `eslint --max-warnings=0` — không warning sau khi fix

---

## Commit message

```
fix(#$ISSUE_NUMBER): [mô tả ngắn — ví dụ: optional chaining BatteryCard undefined data]
```
