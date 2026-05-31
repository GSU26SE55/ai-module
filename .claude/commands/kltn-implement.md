Implement GitHub Issue đã có plan. Chạy SAU khi `/kltn-plan` đã approve.

Issue number: `$ARGUMENTS`

---

**Bước 0 — Kiểm tra plan**

Đọc `logs/GH-$ARGUMENTS/plan.md`:

- **Nếu chưa tồn tại** → **DỪNG**. Trả lời:
  ```
  Chưa có plan cho GH-$ARGUMENTS.
  Chạy /kltn-plan $ARGUMENTS trước — command này đọc issue, hỏi rõ scope/approach, tạo plan và chờ approve.
  /kltn-implement chỉ dùng để implement sau khi plan đã approved.
  ```

- **Nếu tồn tại** → đọc `Status`:

  | Status | Hành động |
  |--------|-----------|
  | `PLANNING` | Hiện plan + Steps. Hỏi **[1] Execute** hoặc **[2] Chat about** (thảo luận điểm nào trong plan trước khi chạy). |
  | `IN_PROGRESS` | Tìm `- [ ]` đầu tiên chưa done. Tóm tắt "Xong X/Y bước. Tiếp tục Bước Z." Hỏi tiếp tục không. |
  | `REVIEWING` | "Chạy `/kltn-reviewcode` để tiếp tục." Dừng. |
  | `TESTING` | "Chạy `/kltn-test $ARGUMENTS` để tiếp tục." Dừng. |
  | `SHIPPED` | "Đang chờ PR review." Dừng. |
  | `MERGED` | "Task đã done." Dừng. |

  **Dừng sau mỗi status — chờ user chỉ dẫn.**

  > Nếu user chọn **[2] Chat about** → hỏi user muốn thảo luận điểm nào trong plan, giải đáp, rồi hỏi lại có muốn Execute không. Không bắt đầu implement cho đến khi user chọn Execute.

---

**Bước 1 — Xác định role và đọc skill**

Đọc `CLAUDE.local.md`. Dùng **Dev Role** nếu có, ngược lại dùng Role:
- BE → `.claude/skills/dev/be/implement/SKILL.md`
- FE → `.claude/skills/dev/fe/implement/SKILL.md`
- AI → `.claude/skills/dev/ai/implement/SKILL.md`

> Nếu skill file không tồn tại → tiếp tục implement theo `plan.md`, không dừng.

---

**Bước 2 — Bắt đầu implement (khi user chọn Execute)**

- Cập nhật `plan.md`: `Status: PLANNING → IN_PROGRESS`, `Ngày` → hôm nay.
- Tạo branch theo format: `feat/GH-$ARGUMENTS-slug-ngan`
  - Slug lấy từ title issue: viết thường, chỉ dùng `a-z`, `0-9`, dấu gạch ngang, tối đa 5 từ.
  - Ví dụ: issue "Add Battery CRUD API" → `feat/GH-42-add-battery-crud-api`

Thực hiện từng Step trong `plan.md` theo thứ tự:

> Sau mỗi bước hoàn thành:
> `- [ ] Bước N: ...` → `- [x] Bước N: ... — YYYY-MM-DD`
> Cập nhật `Ngày` trong Metadata.

Không bỏ qua bước. Không đánh dấu done khi chưa thực sự xong.

> Nếu một bước thất bại (compile error, test fail, blocker…) → **dừng ngay**, báo lỗi cụ thể cho user, không tự ý skip hoặc workaround mà không hỏi.

> ⛔ **KHÔNG chạy `git commit` hay `git push` trong `/kltn-implement`.**
> Toàn bộ git operations (commit → push → PR) chỉ được thực hiện khi chạy `/kltn-ship $ARGUMENTS`.
