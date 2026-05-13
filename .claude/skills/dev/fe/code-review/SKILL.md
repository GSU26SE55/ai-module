# Skill: /kltn-reviewcode (FE)

## Kích hoạt
`/kltn-reviewcode` — review code FE trước khi ship.

---

## ACTION-FIRST RULE

**Đọc diff thực sự TRƯỚC khi viết bất cứ điều gì.**

```bash
git diff main...HEAD
# hoặc nếu đã stage: git diff --staged
```

Không nhận xét từ memory hay đọc lướt. Tool calls trước, text output sau.

---

## Effort Scaling

| Level | Khi nào | Làm gì |
|-------|---------|--------|
| **Quick** | 1 component nhỏ, ít thay đổi | Chỉ check Critical items + 2–3 Warning |
| **Standard** | 1 ticket / 1 feature | Full checklist, phân tích từng vấn đề |
| **Deep** | PR nhiều file, cross-feature | Full checklist + import isolation + route tree |
| **Exhaustive** | Cuối sprint / refactor lớn | Full + regression risk + responsive check |

---

## Xác định issue number

```bash
git branch --show-current | grep -oE 'GH-[0-9]+'
# feature/GH-34-login-page → TICKET_ID = GH-34
```

Nếu không xác định được → hỏi user trước khi tiếp tục.

---

## Checklist

### Architecture
- [ ] Không có business logic trong component (chỉ UI + state)?
- [ ] API call qua `services/` layer → hook TanStack Query, không fetch trực tiếp trong component?
- [ ] File mới đặt đúng chỗ: `features/<tên>/` cho code của feature, `shared/` chỉ khi dùng ≥ 2 feature?
- [ ] `features/<A>` không import trực tiếp từ `features/<B>`?
- [ ] Zustand (`sessionStore`) chỉ cho auth session — không dùng cho server state?
- [ ] Không tạo Axios instance mới — dùng `shared/lib/axios.ts`?

### Code Quality
- [ ] Component đặt tên PascalCase?
- [ ] Không hardcode URL, token, config (dùng `.env`)?
- [ ] Loading và error state được xử lý?
- [ ] Không có `console.log` còn sót lại?

### Error Handling
- [ ] `queryKey` dùng `QUERY_KEY` factory từ `shared/utils/queryKeys.ts` — không dùng inline array?
- [ ] `invalidateQueries` dùng `KEY` root (broad) hoặc `QUERY_KEY` factory (narrow) — không hardcode string?
- [ ] Mutation non-form có `onError: (error) => handleErrorApi({ error })`?
- [ ] Form submit dùng `try-catch` + `handleErrorApi({ error, setError })` thay vì chỉ toast?
- [ ] Không tự toast.error trong hook — delegate cho `handleErrorApi`?

### UI / UX
- [ ] UI primitive dùng từ `shared/components/ui` (shadcn generated components)?
- [ ] Không tự custom Button/Input/Form/Dialog/Table/Badge/Skeleton nếu shadcn đã có?
- [ ] Primitive mới được thêm bằng `npx shadcn@latest add <component>`?
- [ ] Responsive trên mobile viewport (Web)?
- [ ] Expo Router navigation đúng pattern (Mobile)?

### Auth & Security
- [ ] Route mới đã khai báo trong `router/index.tsx`?
- [ ] Page cần auth đã wrap `ProtectedRoute`?
- [ ] Page có role restriction đã wrap `RoleRoute` (Admin / Manager / Staff)?
- [ ] Token không lưu trong `localStorage` plain text?
- [ ] Không render sensitive data ra UI không cần thiết?

---

## Adversarial Self-Review

Trước khi nộp báo cáo:

1. **Đã đọc diff chưa?** — Không được nhận xét từ memory
2. **Mỗi Critical có file:line cụ thể không?** — "Component có vấn đề" không đủ
3. **Cross-feature import đã check chưa?** — Lỗi này thường ẩn, không thấy khi lướt nhanh
4. **Auth wrap đã check chưa?** — Route thiếu ProtectedRoute là security issue nghiêm trọng
5. **Kết luận PASS/FAIL nhất quán với phân tích không?** — Có Critical → phải FAIL

---

## Định dạng báo cáo

Sau khi review xong, **bắt buộc ghi file** (dùng Write tool):

```
logs/GH-[number]/review.md
```
(TICKET_ID đã xác định ở trên, ví dụ: `logs/GH-34/review.md`)

Nếu folder chưa tồn tại → tạo mới. Nội dung file:

```markdown
## BÁO CÁO CODE REVIEW — [branch] — [YYYY-MM-DD]
### Scope: FE (Web / Mobile)
### Effort: [Quick / Standard / Deep / Exhaustive]

### TÓM TẮT
[1–2 câu về trạng thái tổng thể]

### PHÂN TÍCH
🔴 Critical: [file:line] — vấn đề — cách fix
🟡 Warning:  [file:line] — vấn đề — gợi ý
✅ Pass: [tiêu chí đạt]

### RỦI RO & LƯU Ý
- ...

### KẾT LUẬN
[PASS / FAIL] — Độ tự tin: [Cao / Trung bình / Thấp]
```

---

## Common Anti-Patterns

### Claim PASS vì "trông đúng cấu trúc"

**SAI:**
```
Nhìn file structure có folder features/, hooks/, services/ → "Đúng cấu trúc" → ✅ PASS
```
_Vấn đề:_ Không check nội dung — có thể gọi API trực tiếp trong component, cross-feature import, không có auth wrap.

**ĐÚNG** — Đọc diff từng file, ghi lỗi cụ thể:
```
git diff main...HEAD -- src/features/admin/pages/UserManagementPage.tsx
# → import { useTickets } from '../../manager/hooks/useTickets'  ← cross-feature import!
# 🔴 Critical: src/features/admin/pages/UserManagementPage.tsx:3
#    — admin import từ manager feature — vi phạm feature isolation
#    — Fix: move useTickets sang shared/ nếu dùng cross-feature, hoặc tạo useAdminTickets trong admin/
```

---

### Bỏ qua auth wrap vì "ticket không yêu cầu"

**SAI:**
```
Ticket: "Thêm màn hình báo cáo"
Review: ✅ Pass: tất cả
KẾT LUẬN: PASS
```

**ĐÚNG** — Auth là bắt buộc với mọi page mới:
```
🔴 Critical: src/router/index.tsx — route /admin/reports chưa wrap ProtectedRoute
   Fix: bọc <ProtectedRoute><ReportsPage /></ProtectedRoute>
KẾT LUẬN: FAIL
```
