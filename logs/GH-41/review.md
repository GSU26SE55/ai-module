# BÁO CÁO CODE REVIEW — feat/GH-41-grpc-predictstream-streaming — 2026-07-02

## Scope: AI
## Effort: Standard

## TÓM TẮT
`PredictStream` bidi streaming implement bằng sync generator, tái dùng 100% đường unary qua helper chung `_predict_one` (đã refactor trong review — bỏ duplication). Diff chỉ 2 file gRPC + logs. Không có Critical.

## PHÂN TÍCH

### Files trong diff (vs dev)
| File | Action |
|------|--------|
| `src/grpc_server.py` | modify — thêm `_predict_one` helper + `PredictStream` generator |
| `tests/test_grpc_server.py` | modify — thay test UNIMPLEMENTED bằng `TestPredictStream` (6 tests) |
| `logs/GH-41/plan.md` | tracking |

### Kết quả checklist

✅ Pass: **Không duplicate logic** — phát hiện trong review: body PredictStream ban đầu copy nguyên body Predict → đã extract `_predict_one(request, context)` dùng chung cho cả unary lẫn stream. Giờ 1 message stream ≡ 1 call unary theo đúng nghĩa đen (cùng code path). 34/34 gRPC tests PASS sau refactor.

✅ Pass: **In-order + backpressure đúng thiết kế** — generator xử lý tuần tự trong 1 handler thread → thứ tự bảo đảm (test 5 windows map battery_id đúng vị trí); backpressure từ HTTP/2 flow control trên `request_iterator`, không cần code thêm (docstring ghi rõ).

✅ Pass: **Error semantics nhất quán với unary** — window sai shape → `_validate` abort `INVALID_ARGUMENT` (test verify client nhận đúng 2 responses trước khi error); lỗi pipeline → `INTERNAL` + log. Docstring nêu rõ giới hạn bidi gRPC (không có per-message error channel) — cần chuyển vào handoff cho BE.

✅ Pass: **Edge cases có test thật qua channel**: stream rỗng → 0 responses status OK; client cancel giữa stream vô hạn → server vẫn phục vụ Health sau đó; parity stream vs unary → message bằng nhau tuyệt đối (patch dict cố định).

✅ Pass: **Thread-safety** — nhiều stream đồng thời chia sẻ `_MC_LOCK` sẵn có trong `run_inference`, giống unary; không thêm shared state mới.

✅ Pass: **Scope kỷ luật** — không đổi proto (RPC khai báo từ GH-39), không đụng unary/Prescribe/Health/FastAPI/model; đúng 2 file trong plan.

✅ Pass: **Checklist ML** — không có training/preprocess code → seed/scaler/leakage N/A; không thêm framework.

✅ Pass: **Tests + lint** — gRPC suites 34/34 PASS (17 server + 17 contract); full suite 175 pass; ruff sạch.

🟡 Warning: client gửi stream vô hạn sẽ giữ 1 worker thread của ThreadPool (max_workers=10) — chấp nhận được cho scope nội bộ capstone; nếu BE mở nhiều stream dài, cân nhắc tăng `MAX_WORKERS` hoặc thêm idle timeout ở #42 (benchmark sẽ lộ ra nếu là vấn đề thật).

🟡 Warning: flaky pre-existing `test_rule_path_under_100ms` giờ fail cả isolate 2/3 lần trên máy dev (105–119ms) — KHÔNG liên quan diff (test_prescription không import grpc_server), nhưng nên mở ticket riêng mark flaky/nới threshold trước khi nó chặn PR khác.

## RỦI RO & LƯU Ý
- BE cần biết semantics: window lỗi giữa stream → stream chết sau k−1 responses; client nên reconnect + resume. Ghi vào handoff + #42 (client demo).
- Blocker weights v1.3/v2.2 vẫn còn (chuỗi #25 retrain đang chờ) — smoke weights thật cho streaming dời sang #42 như unary.

## KẾT LUẬN
**PASS** — Độ tự tin: **Cao**
