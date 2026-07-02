# BÁO CÁO CODE REVIEW — feat/GH-42-grpc-test-benchmark-demo — 2026-07-02

## Scope: AI
## Effort: Standard

## TÓM TẮT
Ticket QA/handoff: +3 test, 2 script tooling (benchmark + demo), doc BE integration, README + rules. Đúng cam kết **không đụng `src/`** — diff tracked chỉ gồm tests + docs + README + rules; 2 script và doc là file mới. Không có Critical.

## PHÂN TÍCH

### Files trong diff (vs dev)
| File | Action |
|------|--------|
| `tests/test_grpc_server.py` | modify — +37 dòng, 3 test mới |
| `scripts/benchmark_grpc.py` | create |
| `scripts/grpc_client_demo.py` | create |
| `docs/grpc-integration-be.md` | create |
| `README.md` | modify — section Serving (+18 dòng) |
| `.claude/rules/tech/ai.md` | modify — mục Serving Hybrid (+22 dòng, có marker leader) |
| `logs/GH-42/plan.md` | tracking |

### Kết quả checklist

✅ Pass: **`src/` không đụng** — server/pipeline/proto giữ nguyên 100%, đúng scope ticket test+docs.

✅ Pass: **Test concurrent streams đúng thiết kế** — 2 stream đan xen qua ThreadPoolExecutor client-side trên server thật (server pool 2 workers = đúng capacity cho 2 stream đồng thời); assert từng client nhận đúng battery_ids của mình theo thứ tự. Bổ khuyết đúng lỗ hổng test của GH-41 (chưa có test song song).

✅ Pass: **Prescribe qua channel thật** — phủ full request path (serialize → server → pipeline dummy → response) thay vì chỉ direct-servicer như GH-40.

✅ Pass: **Benchmark script thiết kế hợp lý** — seed 42; threshold 2 tầng đúng tiền lệ GH-10 (overhead <50ms luôn enforce — phần gRPC sở hữu; absolute <100ms chỉ `--real-weights` trên deploy env); exit code phản ánh kết quả (CI dùng được); `--real-weights` fail sớm với message artifact-not-found rõ ràng (đã verify). Kết quả dummy: overhead 27.7ms PASS.

✅ Pass: **Demo client robust** — verify cả 2 path thật: không server → message thân thiện + exit 1 (bug UTF-8 console Windows được phát hiện và fix ngay khi chạy thử — `sys.stdout.reconfigure`); có server → đủ 4 RPC. Data synthetic có range vật lý hợp lý (V 3.5–4.2, T 24–30°C).

✅ Pass: **Doc BE đúng góc nhìn consumer** — csproj snippet, ví dụ C# unary + stream, 7 semantics (đặc biệt: 4 features sau GH-25, stream abort k−1, insecure nội bộ), trạng thái artifacts ghi trung thực (v1.3/v2.2 chưa có, retrain #25), benchmark tham khảo có ghi rõ điều kiện đo.

✅ Pass: **Checklist ML** — không training code → seed/scaler/leakage N/A (benchmark/demo vẫn set seed 42 đúng rule); không thêm framework.

✅ Pass: **Tests + lint** — 19 test gRPC server PASS, full suite 177 pass, ruff sạch trên mọi file mới/sửa.

🟡 Warning: `install_dummy_models()` trong benchmark_grpc.py trùng logic `make_dummy_loader()` của tests — chấp nhận được (script không nên import từ `tests/`; demo server tạm trong verify đã import từ scripts, đúng chiều). Nếu sau này thêm script thứ 3 cần dummy models → cân nhắc chuyển vào `scripts/create_dummy_artifacts.py`.

🟡 Warning: link doc trong comment issue #42 trỏ vào branch `feat/GH-42-*` — sau khi merge + xóa branch link sẽ chết; PR body (/kltn-ship) nên dùng link tương đối hoặc link dev.

🟡 Warning: `.claude/rules/tech/ai.md` sẽ bị ghi đè nếu leader sync trước khi đưa thay đổi vào workflow-ai — đã có marker comment trong file + note trên issue; cần leader xác nhận trước khi PR merge quá lâu.

## RỦI RO & LƯU Ý
- Benchmark số thật + smoke 2 transport vẫn chờ artifacts v1.3/v2.2 (retrain #25) — mọi công cụ đã sẵn (`--real-weights`).
- Flaky pre-existing `test_rule_path_under_100ms` vẫn đó (113.9ms lần chạy cuối) — nhắc lại đề xuất mở ticket mark flaky/nới threshold.

## KẾT LUẬN
**PASS** — Độ tự tin: **Cao**
