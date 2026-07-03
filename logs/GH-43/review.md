# BÁO CÁO CODE REVIEW — feat/GH-43-warmup-stages-cli — 2026-07-03

## Scope: AI
## Effort: Quick (1 flag CLI, diff nhỏ)

## TÓM TẮT
Flag `--warmup-stages` opt-in cho ablation warmup ngắn — diff tối giản đúng plan (1 parse function + 1 add_argument + 1 dòng wire), baseline 5-stage giữ nguyên tuyệt đối. Trong review phát hiện và **đã fix**: parse thiếu guard số ≤ 0. Không có Critical còn lại.

## PHÂN TÍCH

### Files trong diff (vs dev)
| File | Action |
|------|--------|
| `scripts/train.py` | modify — `_parse_warmup_stages` + argparse + `stages=args.warmup_stages` |
| `tests/test_train_long.py` | modify — class `TestWarmupStagesCli` 4 tests |
| `logs/GH-43/plan.md` | tracking |

### Kết quả checklist

✅ Pass: **Baseline không đổi** — default `None` → `train_long` fallback `WARMUP_STAGES` (5-stage); có test riêng verify (`test_cli_default_keeps_five_stage_baseline`). `WARMUP_STAGES` trong config không đụng — các run khác không bị âm thầm đổi hành vi.

✅ Pass: **Không đụng thân `train_long`** — hàm đã tham số hoá `stages` sẵn (tự append `seq_len`, lọc stage > seq_len); diff chỉ là đường dẫn CLI. `train()` window-30 + RUL nguyên vẹn.

✅ Pass (fix trong review): **Input validation đầy đủ** — parse reject: chuỗi không phải int (`ArgumentTypeError` message rõ), chuỗi rỗng, và **số ≤ 0** (guard thêm trong review — trước đó `--warmup-stages 0,4096` sẽ lọt vào training loop với stage L=0). Có test cho cả 4 case; verify CLI thật in error đúng format argparse.

✅ Pass: **Reproducibility** — seed 42 toàn cục của train.py không đụng; flag không ảnh hưởng randomness (chỉ đổi danh sách stage lengths).

✅ Pass: **Tests** — `test_train_long.py` 7/7 PASS (parse valid/invalid, CLI forward qua mock, default None); smoke thật với stages custom đã có sẵn từ GH-10 (`test_train_long_smoke` stages=[16,32] — chạy trọn warmup loop 2 stage). Full suite 181 pass; ruff sạch.

✅ Pass: **Help text đủ thông tin** — nêu default, ví dụ, và semantics (stage > seq_len bị drop, seq_len luôn append).

🟡 Warning: acceptance cuối (ablation Kaggle 5-stage vs 2-stage: speedup ~50-60%, MAE hồi quy <0.1%) **chưa verify được local** — cần GPU + data thật; đã ghi rõ trong plan là user chạy sau khi merge, kết quả post lên issue #43. PR nên ghi chú criterion này pending.

## RỦI RO & LƯU Ý
- Nếu ablation 2-stage cho MAE hồi quy > 0.1%: không cần revert code — flag là opt-in, chỉ cần không dùng `--warmup-stages` (baseline còn nguyên).
- Flaky pre-existing `test_rule_path_under_100ms` vẫn là fail duy nhất trong full suite (116.3ms) — ticket riêng vẫn nên mở.

## KẾT LUẬN
**PASS** — Độ tự tin: **Cao**
