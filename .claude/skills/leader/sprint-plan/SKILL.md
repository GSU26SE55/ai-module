# Skill: /kltn-sprint

## Mô tả
Lên kế hoạch sprint: fetch GitHub Issues từ 4 sub-repos, phân công cho từng thành viên theo role, tạo issues mới nếu cần, xuất kế hoạch sprint trong conversation.

## Kích hoạt
Khi leader gõ `/kltn-sprint` hoặc "lên kế hoạch sprint", "phân công sprint", "plan sprint [N]".

---

## Mapping role → repo (cố định)

| Role | Repo |
|------|------|
| BE | `GSU26SE55/backend` |
| FE | `GSU26SE55/frontend` |
| Mobile | `GSU26SE55/mobile` |
| AI | `GSU26SE55/ai-module` |

---

## Quy trình thực hiện

### Bước 1 — Xác định sprint hiện tại

Nếu không có argument → hỏi Leader sprint nào đang cần plan (ví dụ: "Sprint 3").
Ghi nhớ `$SPRINT_NAME` = "Sprint N".

---

### Bước 2 — Fetch GitHub Issues từ tất cả repos

```bash
for REPO in backend frontend mobile ai-module; do
  echo "=== GSU26SE55/$REPO ==="
  gh issue list \
    --repo "GSU26SE55/$REPO" \
    --milestone "$SPRINT_NAME" \
    --state open \
    --json number,title,labels,assignees,createdAt \
    --limit 50
done
```

---

### Bước 3 — Phân tích và đề xuất

Từ danh sách issues:
1. Phân loại theo role dựa trên label `role: *`
2. Xem assignees → ai đang nhận task nào
3. Ước lượng workload cân bằng dựa trên số lượng + priority
4. Phát hiện task thiếu assignee hoặc thiếu label

Phân nhóm theo thành viên:
- **BE tasks** (backend repo) → Nguyễn Phúc Duy, Bùi Phước Thắng, Mai Hồng Thái
- **FE tasks** (frontend repo) → Trần Minh Trí, Nguyễn Nhật Minh
- **AI tasks** (ai-module repo) → Nguyễn Phúc Duy (BE Dev / AI Dev)
- **Mobile tasks** (mobile repo) → phân đều nếu cần

---

### Bước 4 — Tạo issues mới (nếu cần)

```bash
# BE task → backend repo
gh issue create \
  --repo "GSU26SE55/backend" \
  --title "[BE] Tên task ngắn gọn" \
  --body "$(cat <<'EOF'
## Mô tả
[Mô tả task — issue này cần làm gì, output là gì]

## Scope
**Trong scope:**
- ...

**Ngoài scope:**
- ...

## Endpoints
| Method | Path | Mục đích | Auth |
|--------|------|----------|------|
| GET | `/api/...` | ... | Admin/Manager/Staff |

## Approach
[Hướng xử lý: entity, CQRS command/query, service liên quan]

## Steps
- [ ] Bước 1: ...
- [ ] Bước 2: ...
- [ ] Bước 3: `dotnet test` + build → PASS

## Edge Cases
- ...

## Acceptance Criteria
- [ ] ...

## Technical Notes
- Stack: ASP.NET Core · EF Core · PostgreSQL · MediatR
- Luôn filter `.Where(x => !x.IsDeleted)` trong mọi query
- Enum values bắt đầu từ 1, không phải 0

---
> Plan chi tiết: `logs/GH-ISSUE_NUMBER/plan.md`
EOF
)" \
  --label "status: init,role: BE,type: feat,priority: P3: Standard (72h)" \
  --milestone "$SPRINT_NAME" \
  --assignee "github-username"

# FE task → frontend repo
gh issue create \
  --repo "GSU26SE55/frontend" \
  --title "[FE] Tên task ngắn gọn" \
  --body "$(cat <<'EOF'
## Mô tả
[Mô tả task — issue này cần làm gì, output là gì]

## Scope
**Trong scope:**
- ...

**Ngoài scope:**
- ...

## Endpoints
| Method | Path | Request Body | Response |
|--------|------|-------------|----------|
| GET | `/api/...` | — | `CommonResponse<...>` |

## Approach
[Hướng xử lý: component, state management, hooks, API calls]

## Steps
- [ ] Bước 1: Tạo types + schemas
- [ ] Bước 2: Tạo service + hooks
- [ ] Bước 3: Tạo components + pages
- [ ] Bước 4: Wire vào router
- [ ] Bước 5: `tsc --noEmit` + `eslint --max-warnings=0` + `npm run build` → PASS

## Edge Cases
- ...

## Acceptance Criteria
- [ ] ...

## Technical Notes
- Stack: React · TanStack Query · Zod · shadcn/ui
- Không gọi API trong component — luôn qua services/ → hook
- Không dùng localStorage cho token

---
> Plan chi tiết: `logs/GH-ISSUE_NUMBER/plan.md`
EOF
)" \
  --label "status: init,role: FE,type: feat,priority: P3: Standard (72h)" \
  --milestone "$SPRINT_NAME" \
  --assignee "github-username"

# AI task → ai-module repo
gh issue create \
  --repo "GSU26SE55/ai-module" \
  --title "[AI] Tên task ngắn gọn" \
  --body "$(cat <<'EOF'
## Mô tả
[Mô tả task — issue này cần làm gì, output là gì]

## Scope
**Trong scope:**
- ...

**Ngoài scope:**
- ...

## Endpoints
| Method | Path | Mục đích |
|--------|------|----------|
| POST | `/api/...` | ... |

## Approach
[Hướng xử lý, data flow, model/architecture liên quan]

## Steps
- [ ] Bước 1: ...
- [ ] Bước 2: ...
- [ ] Bước 3: `pytest --cov=src` + build → PASS

## Edge Cases
- ...

## Acceptance Criteria
- [ ] ...

## Technical Notes
- Stack: Python 3.11 · PyTorch · FastAPI · scikit-learn
- Seed: `random_seed = 42` bắt buộc
- Inference latency target: < 100ms

---
> Plan chi tiết: `logs/GH-ISSUE_NUMBER/plan.md`
EOF
)" \
  --label "status: init,role: AI,type: feat,priority: P3: Standard (72h)" \
  --milestone "$SPRINT_NAME" \
  --assignee "github-username"

# Mobile task → mobile repo
gh issue create \
  --repo "GSU26SE55/mobile" \
  --title "[Mobile] Tên task ngắn gọn" \
  --body "$(cat <<'EOF'
## Mô tả
[Mô tả task — issue này cần làm gì, output là gì]

## Scope
**Trong scope:**
- ...

**Ngoài scope:**
- ...

## Endpoints
| Method | Path | Request Body | Response |
|--------|------|-------------|----------|
| GET | `/api/...` | — | `CommonResponse<...>` |

## Approach
[Hướng xử lý: screen, navigation, hooks, API calls]

## Steps
- [ ] Bước 1: Tạo types + schemas
- [ ] Bước 2: Tạo service + hooks
- [ ] Bước 3: Tạo components + screens
- [ ] Bước 4: Wire vào Expo Router
- [ ] Bước 5: `tsc --noEmit` + build → PASS

## Edge Cases
- ...

## Acceptance Criteria
- [ ] ...

## Technical Notes
- Stack: React Native · Expo · TanStack Query · Zustand
- Không dùng AsyncStorage cho token — dùng expo-secure-store
- Không gọi API trong component — luôn qua services/ → hook

---
> Plan chi tiết: `logs/GH-ISSUE_NUMBER/plan.md`
EOF
)" \
  --label "status: init,role: Mobile,type: feat,priority: P3: Standard (72h)" \
  --milestone "$SPRINT_NAME" \
  --assignee "github-username"
```

> **Label bắt buộc khi tạo issue:**
> - `status: init` — task được giao, chưa bắt đầu
> - `role: BE` / `role: FE` / `role: Mobile` / `role: AI`
> - `type: feat` / `type: fix` / `type: refactor` / `type: test` / `type: docs`
> - `priority: P1: Critical (4h)` / `priority: P2: High (24h)` / `priority: P3: Standard (72h)`

> Issues được tạo tự động xuất hiện trên Sprint Board nhờ `add-to-project.yml` workflow trong mỗi sub-repo.

---

### Bước 5 — Xuất kế hoạch sprint trong conversation

```
## KẾ HOẠCH SPRINT [N] — YYYY-MM-DD

### Tổng quan
- Tổng tasks: X | BE: X | FE: X | Mobile: X | AI: X
- Milestone due: [date]

### Phân công

| Issue | Repo | Tên | Role | Priority | Assignee |
|-------|------|-----|------|----------|----------|
| #12 (backend) | backend | ... | BE | P2 | Duy |
| #8 (frontend) | frontend | ... | FE | P3 | Minh |

### Cân bằng workload
| Thành viên | Số task | P1 | P2 | P3 |
|------------|---------|----|----|-----|
| Duy        | 3       | 0  | 1  | 2  |
| Thắng      | 2       | 0  | 2  | 0  |

### Cần chú ý
- Task #XXX chưa có assignee
- [Rủi ro hoặc dependency giữa tasks]
```

---

### Bước 6 — Hướng dẫn dev bắt đầu

```
Các thành viên:
1. Vào GitHub Project GSU26SE55 → tab "My items" → xem issue được assign
2. cd vào repo tương ứng (backend / frontend / mobile / ai-module)
3. Chạy: /kltn-plan [issue-number]      ← đọc issue, hỏi nếu chưa rõ, tạo plan, chờ approve
   Sau đó: /kltn-implement [issue-number] ← bắt đầu code
   Ví dụ: /kltn-plan 12 → /kltn-implement 12
```

---

## Nguyên tắc

- **Không tự assign mà không hỏi** — Đây là đề xuất, leader xác nhận trước khi tạo issue.
- **Cân bằng workload** — Không để 1 người carry cả sprint.
- **Kế hoạch xuất trong conversation** — Không lưu file; dev dùng `gh issue list` để xem lại.
