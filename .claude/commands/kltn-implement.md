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
  | `PLANNING` | Hiện plan + Steps. Hỏi **[1] Execute** hoặc **[2] Chat about**. |
  | `IN_PROGRESS` | Tìm `- [ ]` đầu tiên chưa done. Tóm tắt "Xong X/Y bước. Tiếp tục Bước Z." Hỏi tiếp tục không. |
  | `REVIEWING` | "Chạy `/kltn-reviewcode` để tiếp tục." Dừng. |
  | `TESTING` | "Chạy `/kltn-test $ARGUMENTS` để tiếp tục." Dừng. |
  | `SHIPPED` | "Đang chờ PR review." Dừng. |
  | `MERGED` | "Task đã done." Dừng. |

  **Dừng sau mỗi status — chờ user chỉ dẫn.**

---

**Bước 1 — Xác định role**

Đọc `CLAUDE.local.md`. Dùng **Dev Role** nếu có, ngược lại dùng Role:
- BE → `rules/tech/be.md`
- FE → `rules/tech/fe.md`
- AI → `rules/tech/ai.md`

---

**Bước 2 — Bắt đầu implement (khi user chọn Execute)**

- Cập nhật `plan.md`: `Status: PLANNING → IN_PROGRESS`, `Ngày` → hôm nay.
- Tạo branch `feature/GH-$ARGUMENTS-slug-ngan` (slug từ title issue, viết thường, dấu gạch ngang).

Thực hiện từng Step trong `plan.md` theo thứ tự:

> Sau mỗi bước hoàn thành:
> `- [ ] Bước N: ...` → `- [x] Bước N: ... — YYYY-MM-DD`
> Cập nhật `Ngày` trong Metadata.

Không bỏ qua bước. Không đánh dấu done khi chưa thực sự xong.

> ⛔ **KHÔNG chạy `git commit` hay `git push` trong `/kltn-implement`.**
> Toàn bộ git operations (commit → push → PR) chỉ được thực hiện khi chạy `/kltn-ship $ARGUMENTS`.
