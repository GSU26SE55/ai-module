# Skill: /kltn-implement (Mobile)

> Kế thừa từ `fe/implement` — override phần platform-specific cho React Native / Expo.
> Quy trình chung (Bước 0 → 2.5 → 3) giữ nguyên, chỉ thay Bước 4 và Bước 5.

## Kích hoạt
`/kltn-implement [issue-number]` — khi issue label là `platform: mobile` hoặc body đề cập Expo/React Native.

---

## Quy trình

### Bước 0 — Kiểm tra CLAUDE.local.md
```bash
cat .claude/CLAUDE.local.md 2>/dev/null || { echo "❌ CLAUDE.local.md chưa tồn tại — tạo file này trước (xem /kltn-setup)"; exit 1; }
```
Xác nhận file có đủ 4 trường: **Tên**, **MSSV**, **Role chính**, **Role phụ**.

### Bước 1 — Đọc GitHub Issue
```bash
gh issue view $ISSUE_NUMBER --json number,title,body,labels,milestone,assignees

gh api repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/issues/$ISSUE_NUMBER/sub_issues \
  --jq '.[] | {number: .number, title: .title, body: .body, state: .state}'
```
Ghi nhớ: `$ISSUE_NUMBER`, `$ISSUE_TITLE`, `$SPRINT`, output mong đợi (screen / component / API call).

### Bước 2 — Kiểm tra plan hiện tại
```bash
cat logs/GH-$ISSUE_NUMBER/plan.md 2>/dev/null
```
- **Tồn tại** → hiện nội dung, hỏi [1] dùng plan cũ hay [2] ghi đè.
- **Chưa tồn tại** → lập plan và ghi vào `logs/GH-$ISSUE_NUMBER/plan.md`:

```markdown
# Plan — GH-[number]: [Tên issue]

## Metadata
- **Status:** PLANNING
- **Role:** Mobile | **Ngày:** YYYY-MM-DD
- **Issue:** #[number] — [GitHub URL]
- **Sprint:** [milestone]

## Mục tiêu
[Issue yêu cầu làm gì, output là màn hình nào / component nào]

## Scope
- Trong scope: ...
- Ngoài scope: ...

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| app/(customer)/screen.tsx | create/modify | ... |

## Approach
[Stack navigation, state management, API calls]

## Edge Cases
- Offline / network error: ...
- Empty state: ...

## Success Criteria
| Tiêu chí | Cách verify |
|----------|------------|
| [Outcome cụ thể] | [Bước kiểm tra trên device/simulator] |

## Steps
- [ ] Bước 1: [...]
- [ ] Bước 2: [...]

## Câu hỏi đã giải đáp
[Context cho reviewer]
```

> **DỪNG LẠI — chờ user xác nhận trước khi code.**

### Bước 2.5 — Chọn executor

Hỏi user:
> **"Ai sẽ thực thi plan này?"**
> 1. **Claude** — tiếp tục Bước 3
> 2. **Codex** — in description rồi dừng

**Nếu chọn Codex:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 CODEX DESCRIPTION — GH-$ISSUE_NUMBER (Mobile)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👉 Thực hiện theo thứ tự:
   1. Mở terminal
   2. cd vào đúng thư mục repo:
        cd ~/Documents/GSU26SE55/mobile
   3. Copy TOÀN BỘ đoạn bên dưới, paste vào Codex CLI và nhấn Enter

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✂️  COPY TỪ ĐÂY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are implementing GitHub Issue #$ISSUE_NUMBER for a Mobile (React Native / Expo) project.

Follow ALL coding conventions in .codex/skills/fe/ and the mobile CLAUDE.md
(Expo Router, expo-secure-store, TanStack Query hooks, service layer, src/lib/axios.ts only).

Branch to create: feat/GH-$ISSUE_NUMBER-$SLUG

== IMPLEMENTATION PLAN ==
[toàn bộ nội dung logs/GH-$ISSUE_NUMBER/plan.md]
== END OF PLAN ==

Rules:
- Follow the Steps section in order.
- Do NOT commit or push — stop after implementation.
- If a step fails, stop and report the error clearly.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✂️  COPY ĐẾN ĐÂY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

> Dừng sau khi in. Chờ user chạy Codex xong rồi tiếp tục `/kltn-reviewcode $ISSUE_NUMBER`.

### Bước 3 — Tạo branch
```bash
SLUG=$(gh issue view $ISSUE_NUMBER --json title -q '.title' \
  | tr '[:upper:]' '[:lower:]' \
  | tr -cs 'a-z0-9' '-' \
  | tr -s '-' \
  | cut -d'-' -f1-5 \
  | sed 's/-$//')

git checkout -b feat/GH-$ISSUE_NUMBER-$SLUG
```

### Bước 4 — Implement theo cấu trúc Mobile

```
app/                           ← Expo Router — file-based routing
├── _layout.tsx                ← Providers: QueryClient, AuthProvider, ThemeProvider
├── index.tsx                  ← Redirect theo role
├── (auth)/
│   └── login.tsx
└── (customer)/
    ├── dashboard.tsx
    ├── batteries/
    │   └── [id].tsx
    ├── tickets/
    │   ├── index.tsx
    │   ├── [id].tsx
    │   └── create.tsx
    └── notifications.tsx

src/
├── shared/
│   └── enums/                 ← enums dùng cross-feature (ticket, session)
│       ├── session.enum.ts    ← UserRole
│       └── ticket.enum.ts     ← TicketStatusEnum, TicketPriorityEnum, ...
├── features/
│   └── {feature}/
│       ├── enums/             ← enums chỉ dùng trong feature này
│       ├── hooks/             ← useQuery / useMutation (TanStack Query)
│       ├── services/          ← Axios API calls qua axiosInstance
│       ├── types/             ← import + re-export từ enums/ — KHÔNG define inline
│       └── components/        ← UI components của feature
├── lib/
│   ├── axios.ts               ← Axios instance + interceptors (KHÔNG tạo instance mới)
│   ├── secureStore.ts         ← expo-secure-store wrapper
│   └── endpoints.ts           ← ENDPOINTS — KHÔNG hardcode URL trong service
└── stores/
    └── sessionStore.ts        ← Zustand: user, setSession, clearSession
```

**Enum placement rule:**
- Enum dùng **cross-feature** (ticket states, user roles) → `src/shared/enums/`
- Enum chỉ dùng **trong 1 feature** → `src/features/{feature}/enums/`
- `types/*.ts` chỉ được **import + re-export** từ `enums/` — KHÔNG define `as const` object trong types file

**Enum pattern chuẩn:**
```ts
// src/shared/enums/ticket.enum.ts (hoặc features/{feature}/enums/*.enum.ts)
export const TicketStatusEnum = {
  New: 'New',
  Open: 'Open',
  // ...
} as const;
export type TicketStatusEnum = (typeof TicketStatusEnum)[keyof typeof TicketStatusEnum];

// src/features/tickets/types/ticket.types.ts
export { TicketStatusEnum } from '../../../shared/enums/ticket.enum';
import type { TicketStatusEnum } from '../../../shared/enums/ticket.enum';
// DTO definitions dùng TicketStatusEnum bình thường...
```

**Quy tắc bắt buộc:**
- Token: `expo-secure-store` — **KHÔNG** dùng `AsyncStorage` cho token
- API calls: luôn qua `src/features/{feature}/services/` → TanStack Query hook — **KHÔNG** fetch trong component
- Axios: chỉ import từ `src/lib/axios.ts` — **KHÔNG** tạo instance mới
- Zustand store structure nhất quán với Web (`sessionStore.ts`)
- Navigation: Expo Router `<Link>` và `router.push()` — **KHÔNG** dùng React Navigation trực tiếp
- **KHÔNG** eject khỏi Expo managed workflow
- **KHÔNG** thêm package mới nếu stack hiện tại đủ — hỏi Leader trước

### Bước 5 — Tự kiểm tra trước commit

- [ ] Không còn `console.log`
- [ ] Loading + error state đã xử lý
- [ ] Token lưu bằng `expo-secure-store`, không phải `AsyncStorage`
- [ ] Không hardcode URL / token
- [ ] Không tạo Axios instance mới
- [ ] Expo Router navigation đúng pattern
- [ ] Zod schema validate đúng shape (nếu có form)
- [ ] Không thêm package ngoài stack hiện tại

Sau khi checklist pass → cập nhật `plan.md`: `Status: IN_PROGRESS → REVIEWING`.

> ⛔ **KHÔNG commit, KHÔNG push** — chỉ được thực hiện khi chạy `/kltn-ship $ISSUE_NUMBER`.

---

## Sau khi implement xong

```
/kltn-reviewcode  →  /kltn-test  →  /kltn-ship $ISSUE_NUMBER
```

`/kltn-test` với Mobile sẽ chạy:
```bash
npx tsc --noEmit
npx expo lint
```

---

## Stack Mobile
React Native · Expo (managed workflow) · Expo Router · TanStack Query v5 · Zustand · Axios · expo-secure-store · React Hook Form + Zod
