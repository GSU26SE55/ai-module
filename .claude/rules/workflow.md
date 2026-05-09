# Workflow

## Vòng đời một Sprint — 3 phase

```
[LEADER]  /kltn-sprint  →  kế hoạch sprint
[DEV]     /kltn-task KAN-XX  →  plan  →  viết plan.md  →  chờ user review  →  code  →  /kltn-reviewcode  →  /kltn-test  →  /kltn-ship KAN-XX
[LEADER]  /kltn-team hoặc /kltn-member [tên]
```

---

## Phase 1 — Init (đầu sprint, leader chạy 1 lần)

`/kltn-sprint` → xuất kế hoạch + phân công trong conversation.

---

## Phase 2 — Execute (dev, hàng ngày)

Luồng chuẩn (áp dụng cho MỌI ticket, không phân biệt size):
```
/kltn-task KAN-XX  →  viết plan.md  →  chờ user approve  →  code  →  /kltn-reviewcode  →  /kltn-test  →  /kltn-ship KAN-XX
```

**Bước Plan (bắt buộc với MỌI ticket):**
Sau khi đọc ticket, viết file `logs/KAN-XX/plan.md` trước khi làm bất cứ điều gì khác:

Nội dung plan.md phải có:
```markdown
# Plan — KAN-XX: [Tên ticket]

## Mục tiêu
[Mô tả ngắn gọn ticket cần làm gì]

## Các file sẽ tạo/sửa
| File | Hành động | Mô tả |
|------|-----------|-------|
| path/to/file.ts | create/modify | ... |

## Approach
[Mô tả cách implement: thuật toán, data flow, API design]

## Dependencies & Edge Cases
- Dependency: ...
- Edge case: ...

## Ước tính
- Size: Small / Medium / Large
- Thời gian: X giờ
```

| Size | Thời gian ước tính | Hành động sau khi approve |
|------|--------------------|--------------------------|
| Small | < 2 giờ | Code luôn |
| Medium | 2 – 4 giờ | Code luôn |
| Large | > 4 giờ | Code luôn sau khi user xác nhận plan |

> **TUYỆT ĐỐI KHÔNG CODE khi chưa có file `logs/KAN-XX/plan.md` được user xác nhận (reply "ok", "approve", "tiến hành", hoặc tương đương). Không có ngoại lệ.**

---

## Definition of Done (DoD)

Một ticket được coi là **Done** khi đủ cả 3 điều kiện:
1. Code đã được `/kltn-reviewcode` **PASS**
2. `/kltn-test` xuất báo cáo **PASS**
3. PR đã được ít nhất **1 người approve** và **merged vào main**

---

## Phase 3 — Review (leader, cuối sprint hoặc khi cần)

- Cả team: `/kltn-team`
- Từng người: `/kltn-member [tên]`

---

## Quy tắc

| Tình huống | Làm gì |
|------------|--------|
| Cần biết task của sprint | `/kltn-sprint` hoặc fetch Jira |
| Không chắc scope ticket | Hỏi leader, không tự expand |

---

## Test Coverage Targets

| Layer | Tool | Minimum coverage | CI fail nếu |
|-------|------|-----------------|-------------|
| BE (unit + integration) | `dotnet test --collect:"XPlat Code Coverage"` | ≥ 80% line coverage | < 80% |
| FE (component + hook) | `npm run test -- --coverage` | ≥ 70% line coverage | < 70% |
| AI (training + inference) | `pytest --cov=src --cov-report=term` | ≥ 85% line coverage | < 85% |

**Test bắt buộc cho mỗi ticket:**
- BE: Unit test cho CommandHandler + QueryHandler (mock UnitOfWork)
- BE: Integration test cho endpoint (TestServer + real DB / in-memory)
- FE: Unit test cho hook (`useQuery`, `useMutation`) + component render
- AI: Unit test cho `preprocess`, `train`, `infer` functions + latency benchmark

**Chạy local trước `/kltn-ship`:**
```bash
# BE
dotnet test --no-build --verbosity minimal

# FE
npm run test -- --watchAll=false --coverage

# AI
pytest tests/ -v --cov=src
```

---

## Git

- Branch: `feature/KAN-XX-slug-ngan`
- 1 ticket = 1 branch, commit thường xuyên
- Không merge thẳng main — luôn qua PR
- Commit message: `type(KAN-XX): mô tả` (type: feat / fix / refactor / test)
