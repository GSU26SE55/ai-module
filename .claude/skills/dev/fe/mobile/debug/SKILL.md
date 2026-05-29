# Skill: /kltn-debug (Mobile)

> Kế thừa từ `fe/debug` — override root causes và checklist cho React Native / Expo.

## Kích hoạt
`/kltn-debug [issue-number]` — fix bug từ issue phía Mobile.

---

## ACTION-FIRST RULE

```bash
gh issue view $ISSUE_NUMBER --json number,title,body,labels
```

Tool calls trước, text output sau.

---

## Phân tích lỗi Mobile

### 1. Đọc mô tả lỗi

Từ body issue xác định:
- Error message (JS error, native crash, network error)
- Screen / component bị lỗi
- Steps to reproduce
- Device / simulator (iOS / Android)

### 2. Trace theo layer

```
Screen (app/) → Component → Hook (TanStack Query) → Service → Axios → API
```

### 3. Common root causes Mobile

| Triệu chứng | Nguyên nhân thường gặp |
|------------|----------------------|
| `Cannot read properties of undefined` | Data từ API chưa có — thiếu optional chaining `?.` hoặc loading guard |
| White screen / crash | Exception không catch — thiếu ErrorBoundary hoặc conditional render |
| Không giữ login sau khi tắt app | Token lưu `AsyncStorage` thay vì `expo-secure-store` — bị clear khi app update |
| Token bị mất sau update app | `expo-secure-store` key không nhất quán giữa các version |
| 401 sau khi refresh | Token refresh race condition — `isRefreshing` flag bị reset sớm |
| Query không update sau mutation | `invalidateQueries` dùng sai key |
| Navigation không hoạt động | Dùng React Navigation API thay vì Expo Router `router.push()` |
| Screen không load | Route không đúng Expo Router file convention |
| Loading vô hạn | `isHydrating` không reset về `false` trong AuthProvider |
| Crash trên Android nhưng không crash iOS | Native module không được include trong Expo managed — cần `expo-modules-core` |

### 4. Verify trước khi fix

```bash
npx tsc --noEmit
npx expo lint
```

---

## Checklist fix

- [ ] Fix đúng hypothesis — không sửa code không liên quan
- [ ] Token dùng `expo-secure-store`, không phải `AsyncStorage`
- [ ] Optional chaining đủ: `data?.field`
- [ ] Loading state guard trước khi render data
- [ ] Không tạo Axios instance mới
- [ ] Navigation dùng Expo Router
- [ ] `tsc --noEmit` PASS sau khi fix
- [ ] `expo lint` PASS sau khi fix

---

## Commit message

```
fix(#$ISSUE_NUMBER): [mô tả ngắn — ví dụ: secure-store token persistence crash]
```
