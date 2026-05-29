# Workflow

## Vòng đời một Sprint — 3 phase

```
[LEADER]  /kltn-sprint  →  tạo GitHub Issues (label: status:init) + phân công
[DEV]     /kltn-plan 123        →  đọc issue → plan.md → approve → post plan lên issue + label:implementing
[DEV]     /kltn-implement 123  →  đọc plan.md đã approved → code
          → /kltn-reviewcode → /kltn-test → /kltn-ship 123  →  PR + handoff + label:reviewing
[REVIEWER] review PR trực tiếp trên GitHub  →  approve / request changes
[DEV]     /kltn-complete 123  →  merge PR + label:done + close issue
[LEADER]  /kltn-team hoặc /kltn-member [tên]
```

---

## Phase 1 — Init (đầu sprint, leader chạy 1 lần)

`/kltn-sprint` → tạo GitHub Issues với label `status: init` + phân công assignee + thêm vào milestone → xuất kế hoạch trong conversation.

---

## Phase 2 — Execute (dev, hàng ngày)

Luồng chuẩn (áp dụng cho MỌI task, không phân biệt size):
```
/kltn-plan 123       →  đọc GitHub Issue #123  →  phân tích gap
               →  hỏi nếu chưa rõ scope/approach
               →  viết plan.md  →  chờ user approve
               →  post plan lên issue + label: init → implementing

/kltn-implement 123  →  đọc plan.md đã approved  →  code từng bước
               →  /kltn-reviewcode  →  /kltn-test
               →  /kltn-ship 123  →  PR + handoff + label: implementing → reviewing
               →  reviewer approve trên GitHub
               →  /kltn-complete 123  →  merge PR + label: done
```

**Bước Plan (bắt buộc với MỌI task):**
Sau khi đọc issue, viết file `logs/GH-123/plan.md` trước khi làm bất cứ điều gì khác.

Nội dung plan.md phải có:
```markdown
# Plan — GH-123: [Tên issue]

## Metadata
- Status: PLANNING | Role: BE/FE/AI | Ngày: YYYY-MM-DD
- Issue: #123 — [URL]

## Mục tiêu
[Mô tả ngắn gọn issue cần làm gì]

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| path/to/file | create/modify | ... |

## Approach
[Data flow / API design]

## Steps
- [ ] Bước 1: ...
```

> **TUYỆT ĐỐI KHÔNG CODE khi chưa có file `logs/GH-[number]/plan.md` được user xác nhận (reply "ok", "approve", "tiến hành", hoặc tương đương). Không có ngoại lệ.**

---

## Definition of Done (DoD)

Một ticket được coi là **Done** khi đủ cả 3 điều kiện:
1. Code đã được `/kltn-reviewcode` **PASS**
2. `/kltn-test` xuất báo cáo **PASS**
3. PR đã được ít nhất **1 người approve** và **merged vào dev**

---

## Nguyên tắc viết code

**Simplicity First — Chỉ viết code được yêu cầu:**
- Implement đúng những gì issue mô tả — không thêm feature "phòng hờ"
- Không thêm abstraction, interface, hoặc layer nếu issue không yêu cầu
- Không thêm error handling cho cases chưa xảy ra trong scope
- Tự hỏi: "Senior dev có nghĩ cái này overcomplicated không?" — nếu có, đơn giản lại

**Surgical Changes — Chỉ touch những gì cần thiết:**
- Chỉ sửa files được liệt kê trong `plan.md`
- Không refactor code lân cận trừ khi changes của bạn làm nó obsolete
- Không rename biến, format lại file, hoặc xóa dead code ngoài scope task
- Không thay đổi code style của người khác khi đang làm task khác

---

## Phase 3 — Review (leader, cuối sprint hoặc khi cần)

- Cả team: `/kltn-team`
- Từng người: `/kltn-member [tên]`

---

## Quy tắc

| Tình huống | Làm gì |
|------------|--------|
| Cần biết task của sprint | `/kltn-sprint` hoặc `gh issue list --milestone "Sprint N"` |
| Không chắc scope task | Hỏi leader, không tự expand |
| Muốn xem issue detail | `gh issue view [number]` |

---

## Quality Gates trước `/kltn-ship`

| Layer | Kiểm tra | Tiêu chí PASS | CI fail nếu |
|-------|----------|--------------|-------------|
| BE (unit + integration) | `dotnet test --collect:"XPlat Code Coverage"` | ≥ 80% line coverage | < 80% |
| FE | `tsc --noEmit` + `eslint --max-warnings=0` + `npm run build` | Build & lint không lỗi | bất kỳ lỗi nào |
| AI (training + inference) | `pytest --cov=src --cov-report=term` | ≥ 85% line coverage | < 85% |

**Bắt buộc cho mỗi ticket:**
- BE: Unit test cho CommandHandler + QueryHandler (mock UnitOfWork) + Integration test endpoint
- FE: Type check sạch + lint 0 warning + build thành công
- AI: Unit test cho `preprocess`, `train`, `infer` functions + latency benchmark

**Chạy local trước `/kltn-ship`:**
```bash
# BE
dotnet test --no-build --verbosity minimal

# FE — không có test suite, chỉ build + lint
npx tsc --noEmit
npx eslint . --max-warnings=0
npm run build

# AI
pytest tests/ -v --cov=src
```

---

## Git

- Branch: `feature/GH-[number]-slug-ngan` (ví dụ: `feature/GH-42-battery-crud`)
- 1 issue = 1 branch, commit thường xuyên
- Không merge thẳng dev — luôn qua PR
- Commit message: `type(#[number]): mô tả` (ví dụ: `feat(#42): add Battery CRUD`)
- PR body **phải có** `Closes #[number]` để GitHub tự close issue khi merge

## Label Tracking (toàn bộ lifecycle của issue)

Mỗi issue có nhiều labels đồng thời. Nhóm `status:` tracking tiến độ và tự động sync lên Sprint Board:

| Label | Cột Sprint Board | Ý nghĩa | Ai set |
|-------|-----------------|---------|--------|
| `status: init` | **Plan** | Issue đã tạo, được giao, chưa bắt đầu | Leader (khi tạo issue) |
| `status: implementing` | **In Progress** | Dev đang implement | `/kltn-implement` (sau plan approve) |
| `status: reviewing` | **In Review** | PR đã tạo, đang chờ reviewer | `/kltn-ship` |
| `status: done` | **Completed** | Merged, hoàn tất | `/kltn-complete` |

Các label khác luôn đi kèm:
- **Role:** `role: BE` / `role: FE` / `role: Mobile` / `role: AI`
- **Priority:** `priority: P1: Critical (4h)` / `priority: P2: High (24h)` / `priority: P3: Standard (72h)`
- **Type:** `type: feat` / `type: fix` / `type: refactor` / `type: test` / `type: docs`
