Làm việc trên Jira ticket được chỉ định.

**Bước 0 — Kiểm tra plan hiện tại (quan trọng khi mở conversation mới)**

Trước tiên, dùng Read tool đọc `logs/$ARGUMENTS/plan.md`:


- **Nếu file tồn tại** → đọc trường `Status` trong `## Metadata`, sau đó: 

  | Status | Hành động |
  |--------|-----------|
  | `PLANNING` | Hiện lại plan + danh sách Steps. Hỏi user có approve không. Nếu approve → đổi Status → `IN_PROGRESS`, cập nhật `Cập nhật lần cuối`, bắt đầu từ Bước 1 trong Steps. |
  | `IN_PROGRESS` | Đọc `## Steps`, tìm bước đầu tiên chưa hoàn thành (`- [ ]`). Tóm tắt: "Đã xong X/Y bước. Tiếp tục Bước Z: [mô tả]". Hỏi user có tiếp tục không. |
  | `REVIEWING` | Thông báo: "Ticket đang chờ review — chạy `/kltn-reviewcode` để tiếp tục." Dừng lại. |
  | `TESTING` | Thông báo: "Review đã PASS — chạy `/kltn-test $ARGUMENTS` để tiếp tục." Dừng lại. |
  | `SHIPPED` | Thông báo: "Ticket đã ship, đang chờ PR review." Dừng lại. |
  | `MERGED` | Thông báo: "Ticket đã done và merged vào main." Dừng lại. |

  **Dừng sau mỗi status — không tự tiếp tục. Chờ user chỉ dẫn.**

- **Nếu file chưa tồn tại** → tiếp tục Bước 1 bên dưới.

---

**Bước 1 — Xác định role của bạn**
Đọc CLAUDE.local.md. Nếu có **Dev Role** → dùng Dev Role. Nếu chỉ có Role → dùng Role đó.
- BE → `.claude/skills/dev/be/task/SKILL.md`
- FE → `.claude/skills/dev/fe/task/SKILL.md`
- AI → `.claude/skills/dev/ai/task/SKILL.md`

**Bước 2 — Đọc context**
Fetch Jira ticket: `$ARGUMENTS`

**Bước 3 — Lập Implementation Plan & viết plan.md (bắt buộc)**
Viết file `logs/$ARGUMENTS/plan.md` với nội dung:

```markdown
# Plan — KAN-XX: [Tên ticket]

## Metadata
- **Status:** PLANNING
- **Ngày tạo:** YYYY-MM-DD
- **Cập nhật lần cuối:** YYYY-MM-DD

## Mục tiêu
[Ticket yêu cầu làm gì, output mong đợi là gì]

## Các file sẽ tạo/sửa
| File | Hành động | Mô tả |
|------|-----------|-------|
| path/to/file | create/modify | ... |

## Approach
[Mô tả cách implement: thuật toán, data flow, API design]

## Dependencies & Edge Cases
- Dependency: ...
- Edge case: ...

## Ước tính
- Size: Small / Medium / Large
- Thời gian: X giờ

## Steps
- [ ] Bước 1: [mô tả bước đầu tiên]
- [ ] Bước 2: [mô tả bước tiếp theo]
- [ ] Bước 3: [...]
```

> Steps được chia từ "Các file sẽ tạo/sửa" — mỗi bước là 1 đơn vị logic có thể hoàn thành độc lập (VD: tạo entity, tạo handler, tạo controller, viết test...).

**DỪNG LẠI** — chờ user xác nhận ("ok", "approve", "tiến hành") trước khi code.

Khi user xác nhận → dùng Edit tool cập nhật plan.md:
- `Status: PLANNING` → `Status: IN_PROGRESS`
- `Cập nhật lần cuối` → ngày hôm nay

**Bước 4 — Thực hiện theo đúng skill file của role**
Tạo branch, implement từng bước trong `## Steps` theo thứ tự:

> Sau khi hoàn thành mỗi bước → dùng Edit tool trong plan.md:
> `- [ ] Bước N: ...` → `- [x] Bước N: ... — YYYY-MM-DD`
> `Cập nhật lần cuối` → ngày hôm nay

Không bỏ qua bước nào. Không đánh dấu done khi chưa thực sự xong.
