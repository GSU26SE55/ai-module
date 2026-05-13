# Skill: /kltn-implement (AI)

## Kích hoạt
`/kltn-implement [issue-number]` — làm việc trên GitHub Issue phía AI/ML module.

---

## Quy trình

### Bước 0 — Kiểm tra CLAUDE.local.md
```bash
cat .claude/CLAUDE.local.md 2>/dev/null || { echo "❌ CLAUDE.local.md chưa tồn tại — tạo file này trước (xem /kltn-setup)"; exit 1; }
```
Xác nhận file có đủ 4 trường: **Tên**, **MSSV**, **Role chính**, **Role phụ**.
Nếu thiếu → dừng lại và yêu cầu tạo/bổ sung trước khi tiếp tục.

### Bước 1 — Đọc GitHub Issue
```bash
gh issue view $ISSUE_NUMBER --json number,title,body,labels,milestone,assignees
```
Từ output ghi nhớ:
- `$ISSUE_NUMBER` — số issue (ví dụ: `12`)
- `$ISSUE_TITLE` — title của issue
- `$SPRINT` — milestone name
- Loại task: training / evaluation / API endpoint / data processing?

### Bước 2 — Lập Implementation Plan & viết plan.md

Phân tích issue và viết file plan tại `logs/GH-$ISSUE_NUMBER/plan.md`:

```markdown
# Plan — GH-[number]: [Tên issue]

## Metadata
- **Status:** PLANNING
- **Role:** AI | **Ngày:** YYYY-MM-DD
- **Issue:** #[number] — [GitHub URL]
- **Sprint:** [milestone]

## Mục tiêu
[Training / evaluation / API endpoint / data processing?]

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| models/xxx.py | create/modify | ... |

## Approach
[Thuật toán, data flow, model architecture]

## Steps
- [ ] Bước 1: [...]
- [ ] Bước 2: [...]
- [ ] Bước 3: [...]
```

> **DỪNG LẠI — chờ user xác nhận ("ok", "approve", "tiến hành") trước khi code. Không có ngoại lệ, dù issue nhỏ đến đâu.**

### Bước 2.5 — Chọn executor

Sau khi plan được approve, hỏi user:

> **"Ai sẽ thực thi plan này?"**
> 1. **Claude** — Claude Code tự implement (tiếp tục Bước 3 bên dưới)
> 2. **Codex** — Trigger Codex CLI thực thi plan (Claude dừng lại sau bước này)

**Nếu user chọn Option 2 — Codex:**
```bash
codex "Execute the implementation plan in logs/GH-$ISSUE_NUMBER/plan.md.
Follow the coding conventions in .codex/skills/ai/ for all patterns (FastAPI endpoints, model inference, data preprocessing).
Branch: feature/GH-$ISSUE_NUMBER-$(gh issue view $ISSUE_NUMBER --json title -q '.title' | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | cut -c1-30)
Do not commit or push — stop after implementation."
```

Claude dừng lại sau khi chạy lệnh trên. Codex sẽ tự đọc plan và thực thi.

**Nếu user chọn Option 1 — Claude:** tiếp tục Bước 3 bên dưới.

---

### Bước 3 — Tạo branch
```bash
git checkout -b feature/GH-$ISSUE_NUMBER-slug-ngan
```

### Bước 4 — Implement theo đúng cấu trúc
- `data/` — script xử lý dataset (NASA/CALCE/MIT), window_size=30, seed=42
- `models/` — định nghĩa model (PyTorch), lưu `scaler.pkl` cùng model weights
- `train/` — training script, seed=42, không dùng test set
- `api/` — FastAPI endpoint phục vụ BE gọi

### Bước 5 — Tự kiểm tra trước commit
- `random_seed = 42` ở đầu mọi script (train, preprocess)
- Không có data leakage (test set không ảnh hưởng training)
- `scaler.pkl` được lưu tại `models/weights/scaler.pkl` sau khi train
- Inference dùng scaler đã lưu — không tạo scaler mới
- Inference latency < 100ms (benchmark xem `rules/tech/ai.md`)

> ⛔ **KHÔNG commit, KHÔNG push** trong bước này.
> Commit + push + tạo PR chỉ được thực hiện khi chạy `/kltn-ship $ISSUE_NUMBER`.

---

## Không được
- Train model mà không set `random_seed = 42` (kết quả không reproducible)
- Dùng test data trong quá trình training (data leakage)
- Fit scaler trên val/test set — chỉ fit trên train, lưu lại `scaler.pkl`
- Overpromise accuracy — target: MAE < 2% SOH, F1 > 0.80 anomaly
- Thêm model thứ 3+ mà chưa có approval (focus: LSTM/CNN-LSTM + 1 anomaly model)

---

## Stack AI
Python 3.11 · PyTorch · scikit-learn · FastAPI · NASA Ames Dataset (ưu tiên)
