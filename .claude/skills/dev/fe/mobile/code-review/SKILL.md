# Skill: /kltn-reviewcode (Mobile)

> Kế thừa từ `fe/code-review` — override checklist platform-specific cho React Native / Expo.

## Kích hoạt
`/kltn-reviewcode` — khi đang ở repo Mobile (Expo).

---

## ACTION-FIRST RULE

**Đọc diff thực sự TRƯỚC khi viết bất cứ điều gì.**

```bash
git diff dev...HEAD
```

Tool calls trước, text output sau.

---

## Effort Scaling

| Level | Khi nào | Làm gì |
|-------|---------|--------|
| **Quick** | 1 component nhỏ | Chỉ Critical + 2–3 Warning |
| **Standard** | 1 ticket / 1 screen | Full checklist |
| **Deep** | PR nhiều screen, cross-feature | Full + navigation tree + store isolation |
| **Exhaustive** | Cuối sprint / refactor | Full + regression risk |

---

## Xác định issue number

```bash
git branch --show-current | grep -oE 'GH-[0-9]+'
```

---

## Checklist

### Architecture
- [ ] Không có API call trực tiếp trong component — phải qua `services/` → TanStack Query hook?
- [ ] File mới đặt đúng `src/features/{feature}/` — không để logic tại `app/`?
- [ ] `features/<A>` không import trực tiếp từ `features/<B>`?
- [ ] Zustand (`sessionStore`) chỉ cho auth session — không cho server state?
- [ ] Không tạo Axios instance mới — chỉ dùng `src/lib/axios.ts`?

### Mobile-Specific
- [ ] Token dùng `expo-secure-store` — **KHÔNG** dùng `AsyncStorage` hay `localStorage`?
- [ ] Navigation dùng Expo Router (`<Link>`, `router.push()`) — không dùng React Navigation trực tiếp?
- [ ] Không eject khỏi Expo managed workflow (không có `android/`, `ios/` folder thêm vào)?
- [ ] Package mới (nếu có) đã được Leader approve?
- [ ] `app/_layout.tsx` có đủ Providers (QueryClient, AuthProvider)?

### Code Quality
- [ ] Component đặt tên PascalCase?
- [ ] Không hardcode URL, token, config?
- [ ] Loading và error state được xử lý?
- [ ] Không có `console.log` còn sót lại?
- [ ] Zod schema validate đúng shape khi có form?

### Error Handling
- [ ] `queryKey` dùng factory — không dùng inline string?
- [ ] Mutation có `onError` handler?
- [ ] Network error được handle (offline case)?

### Auth & Security
- [ ] Screen cần auth đã kiểm tra session từ `sessionStore`?
- [ ] Token không bị expose ra log hay UI?
- [ ] `secureStore.ts` wrapper được dùng thay vì gọi `expo-secure-store` trực tiếp trong component?

---

## Adversarial Self-Review

1. Đã đọc diff chưa?
2. Mỗi Critical có file:line cụ thể không?
3. Token storage đã check chưa? (`AsyncStorage` là security issue)
4. Navigation pattern đúng Expo Router chưa?
5. Kết luận PASS/FAIL nhất quán với phân tích không?

---

## Định dạng báo cáo

Ghi bắt buộc vào `logs/GH-[number]/review.md`:

```markdown
## BÁO CÁO CODE REVIEW — [branch] — [YYYY-MM-DD]
### Scope: Mobile (React Native / Expo)
### Effort: [Quick / Standard / Deep / Exhaustive]

### TÓM TẮT
[1–2 câu tổng thể]

### PHÂN TÍCH
🔴 Critical: [file:line] — vấn đề — cách fix
🟡 Warning:  [file:line] — vấn đề — gợi ý
✅ Pass: [tiêu chí đạt]

### RỦI RO & LƯU Ý
- ...

### KẾT LUẬN
[PASS / FAIL] — Độ tự tin: [Cao / Trung bình / Thấp]
```
