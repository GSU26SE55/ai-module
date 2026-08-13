# AI ↔ BE Integration — Anomaly Event → Prescribe → Auto Ticket (GH-23)

> Contract cho luồng: `BatteryService` phát `BatteryAnomalyDetectedEvent` → `TicketService` consumer gọi AI module → map response thành ticket tự động.
> Cơ chế gRPC chung (channel setup, error codes, streaming, benchmark) đã có ở **`docs/grpc-integration-be.md`** — tài liệu này **không lặp lại**, chỉ tập trung vào phần riêng của luồng auto-ticket.

## 1. Khi nào BE gọi AI module

`BatteryService` → TimescaleDB đủ 1 window 30 timestep mới (hoặc theo chu kỳ polling hiện có) → `TicketService`/consumer gọi AI module **một lần duy nhất** qua RPC `Prescribe` (KHÔNG gọi `Predict` riêng trước).

**Lý do gọi 1 lần** (đã ghi trong `docs/grpc-integration-be.md` §0, khuyến nghị GH-87): `Prescribe` chạy `Predict` nội bộ và trả kèm đủ `prediction`/`anomaly`/`risk` (nested). Gọi `Predict` rồi gọi thêm `Prescribe` trên cùng window sẽ chạy MC Dropout 2 lần độc lập — `health_stage`/`anomaly_status` có thể lệch nhau giữa 2 response (stage flip gần ngưỡng 80/85/90). Dùng `Prescribe` làm nguồn duy nhất tránh vấn đề này.

```
BatteryAnomalyDetectedEvent { batteryId, readings (30×window) }
        │
        ▼
TicketService consumer → gRPC Prescribe(battery_id, readings, pack_config?, enrich=false)
        │
        ▼
PrescribeResponse.risk.action_code
   "MONITOR"                                          → bỏ qua, KHÔNG tạo ticket
   "SCHEDULE_MAINTENANCE"/"REPLACE_IMMEDIATELY"      → tạo ticket, map các field bên dưới
```

> ⚠️ **BREAKING — ngưỡng health_stage đổi (2026-08-09).** Trước đây có 4 stage
> (90/85/80). Nay chỉ còn **2**, chia tại đúng ngưỡng EOL 80%:
>
> | SOH | `health_stage` | `action_code` từ SOH | Priority |
> |---|---|---|---|
> | ≥ 80% | `Healthy` | `MONITOR` | `None` |
> | < 80% | `End Of Life` | `REPLACE_IMMEDIATELY` | `P1` |
>
> Ảnh hưởng phía BE — cần chỉnh:
> 1. **`SCHEDULE_REPLACEMENT` không bao giờ được gửi nữa.** Nó chỉ sinh ra từ
>    stage `Maintenance Required` (SOH 80-85%), stage này đã bị bỏ. Enum BE giữ
>    được, nhưng nhánh xử lý sẽ không bao giờ chạy.
> 2. **`Maintenance Required` và `Degrading` biến mất khỏi `health_stage`.**
>    Code BE so sánh chuỗi với 2 giá trị này sẽ luôn false.
> 3. **`stage_probabilities` từ 4 key xuống 2 key** (`Healthy`, `End Of Life`).
>    Ai iterate/hiển thị map này phải chịu được số key thay đổi.
> 4. **`SOH_LOW` và `SOH_CRITICAL` không còn xuất hiện trong `evidence.warnings`.**
>    Pin 80-90% giờ không sinh cảnh báo SOH nào ⇒ **không tự tạo ticket nữa**.
> 5. **`P2` giờ chỉ đến từ `anomaly_status = "Anomaly"`**, không còn từ SOH band.
>
> **Lý do:** pin trên 80% SOH vẫn còn nguyên tuổi thọ danh định (80% chính là
> mốc EOL toàn ngành). Các tầng phụ phía trên gắn nhãn "Degrading" cho một quả
> pin giữa đời và mở ticket bảo trì P3 cho nó — over-alerting.
>
> **Thay thế cho lead time đặt hàng:** dùng số, không dùng ticket —
> `prediction.cycles_to_maintenance` (số chu kỳ còn lại tới 85%, mốc nhìn trước
> để lên kế hoạch) và `prediction.rul_cycles_estimate` (tới EOL 80%).

> ⚠️ **KHÔNG** dùng `anomaly.anomaly_status` làm điều kiện tạo ticket. `anomaly_status` (Normal/Warning/Anomaly) chỉ đo IsolationForest có thấy **hình dạng sóng cảm biến** bất thường không — độc lập với mức độ nghiêm trọng SOH (`health_stage`). Một pin xuống cấp đều đặn tới End-Of-Life vẫn có thể cho `anomaly_status = "Normal"` (sensor pattern hoàn toàn "mượt") trong khi `risk.action_code = "REPLACE_IMMEDIATELY"` — verify thật bằng dữ liệu held-out B0048 (SOH 57.9%): `anomaly_status="Normal"`, `action_code="REPLACE_IMMEDIATELY"`, `priority="P1"`. Gate đúng theo `risk.action_code` (hoặc tương đương `risk.priority != "None"`), KHÔNG theo `anomaly_status`.

## 2. Request — `Prescribe(PrescribeRequest)`

- `battery_id`, `readings` (30 timestep, 4 hoặc 6 field — xem `docs/grpc-integration-be.md` §4.1)
- `pack_config` — bắt buộc gửi nếu pin nhiều cell (GH-65/67: `n_series`, `chemistry`, `capacity_ah`); bỏ trống = pin 1 cell mặc định
- **`enrich = false`** — path auto-ticket dùng rule-based (<100ms, cùng hot-path budget với `Predict`), KHÔNG dùng `enrich=true` (LLM/RAG, có thể mất vài giây). `enrich=true` là tính năng riêng cho tương tác thủ công (vd nút "AI gợi ý chi tiết" trên UI kỹ thuật viên), không thuộc luồng event-driven này.
- Không cần field định danh event (không có `anomaly_event_id`) — xem mục 5 (Idempotency).

## 3. Response — field cần cho việc tạo ticket

| `PrescribeResponse` field | Ý nghĩa | Dùng để |
|---|---|---|
| `risk.action_code` | `MONITOR`/`SCHEDULE_MAINTENANCE`/`REPLACE_IMMEDIATELY` (`SCHEDULE_REPLACEMENT` đã retired, không gửi nữa) | **Quyết định có tạo ticket hay không** — `MONITOR` → không tạo, còn lại → tạo. Loại hành động đề xuất |
| `risk.priority` | `"P1"`/`"P2"`/`"P3"`/`"None"` | **Tín hiệu urgency gợi ý** — xem mục 4, KHÔNG gán thẳng làm Priority ticket |
| `risk.risk_level` | `"Critical"`/`"High"`/`"Medium"`/`"Low"` | Hiển thị mức độ nghiêm trọng trên ticket |
| `anomaly.anomaly_status` | `"Normal"` / `"Warning"` / `"Anomaly"` | **KHÔNG dùng để quyết định tạo ticket** (chỉ đo bất thường sensor pattern qua IsolationForest, độc lập với SOH severity — xem cảnh báo ở mục 1). Chỉ tham khảo/hiển thị thêm |
| `action_steps` | Danh sách bước bảo trì cụ thể | Nội dung maintenance log ban đầu của ticket |
| `human_verification_required` | `bool` | Ticket cần kỹ thuật viên xác nhận trước khi đóng |
| `ppe_required` | Danh sách PPE cần thiết | Cảnh báo an toàn hiển thị trên ticket |
| `safety_warnings` | Cảnh báo an toàn bổ sung | Cảnh báo an toàn hiển thị trên ticket |
| `escalation_conditions` | Điều kiện nên escalate | Tham khảo, không tự động escalate |
| `prediction.soh_percent`, `prediction.health_stage` | Context SOH tại thời điểm tạo ticket | Hiển thị/lưu vào ticket description |
| `blocked` | `true` nếu LLM output bị chặn (chỉ liên quan `enrich=true`) | Không phát sinh ở path `enrich=false` — luôn `false` |

`prescription`, `maintenance_docs`, `safety_docs`, `llm_provider`, `enriched` chỉ có ý nghĩa khi `enrich=true` — path auto-ticket (`enrich=false`) không dùng các field này (rỗng/`enriched=false`).

## 4. Semantics `priority` — ĐỌC KỸ trước khi map sang ticket

`risk.priority` (P1/P2/P3/None) được AI tính **thuần từ severity kỹ thuật của pin** (`health_stage`, `anomaly_status`, cảnh báo critical — xem `src/models/anomaly_detector.py`). AI module **không biết** `ImpactScope` (Site / SingleAsset / MultiSite) của pin — đó là dữ liệu chỉ BE có.

Theo Priority Policy hiện có (`.claude/rules/design.md`): **Priority ticket = ma trận Impact × Urgency**, chốt khi Manager triage, và **không role nào khác được đổi** sau đó.

→ **`risk.priority` phải được BE hiểu là tín hiệu Urgency gợi ý**, KHÔNG phải Priority cuối cùng của ticket:

```
risk.priority (AI, chỉ dựa severity pin)  +  ImpactScope (BE, biết Site/Asset)
                              │
                              ▼
                  Priority Matrix (Impact × Urgency) — phía BE
                              │
                              ▼
                    Priority thật của ticket (P1/P2/P3)
```

Ticket tự động tạo từ event này vẫn cần qua bước xác định Priority theo đúng quy trình Manager triage / Priority Matrix hiện có — GH-23 (AI side) chỉ đảm bảo AI cấp đủ tín hiệu urgency, không tự quyết Priority thay BE.

## 5. Idempotency — GH-84 (đã implement)

Nếu cùng 1 bất thường bắn event trùng/burst (retry MassTransit, nhiều reading liên tiếp cùng trạng thái), `Prescribe` tự động dedup: key = hash(`battery_id`, `readings`, `enrich`, `agentic`, `ticket_history`), TTL 10 phút, tối đa 256 entry (LRU). Lần gọi thứ 2 trở đi trong TTL với cùng input (kể cả cùng `ticket_history`) trả nguyên response đã sinh trước đó (field `cached=true`), không chạy lại inference/RAG/LLM — BE **không cần** tự dedup theo event ID trừ khi muốn dedup ở cửa sổ thời gian khác 10 phút. Response `blocked=true` không bao giờ được cache — luôn đánh giá lại.

Ngoài ra, `enrich=true` có thêm rate-limit: tối đa 2 lượt LLM đồng thời + budget/giờ (env `LLM_HOURLY_BUDGET`, default 60) — vượt giới hạn thì tự động trả về rule-based (giống hệt trường hợp không có LLM API key), không lỗi 5xx. Counters (tổng request, tỉ lệ cache hit, tỉ lệ enrich thành công, budget còn lại...) xem tại `GET /health` (REST), field `prescription_metrics`.

## 6. Ví dụ payload

**Request** (gRPC `PrescribeRequest`, pin 4S LFP 12V):
```
battery_id: "B-IOT-001"
readings: [ <30 rows, mỗi row 4-6 giá trị> ]
pack_config: { n_series: 4, chemistry: "LFP", capacity_ah: 2.5 }
enrich: false
```

**Response** (rút gọn, trường hợp bất thường):
```json
{
  "battery_id": "B-IOT-001",
  "anomaly": { "anomaly_status": "Anomaly", "anomaly_score": -0.32, "anomaly_confidence": 0.71 },
  "risk": { "risk_level": "High", "priority": "P2", "action_code": "SCHEDULE_MAINTENANCE", "reasons": ["..."] },
  "prediction": { "soh_percent": 74.2, "health_stage": "Maintenance Required", "...": "..." },
  "action_steps": ["Kiểm tra kết nối cell 3", "Đo lại điện áp từng cell"],
  "human_verification_required": true,
  "ppe_required": ["Găng tay cách điện"],
  "safety_warnings": [],
  "escalation_conditions": ["SOH < 70% trong lần đo tiếp theo"],
  "enriched": false,
  "prescription": ""
}
```

**Ticket gợi ý tạo (BE tự quyết định field cuối):**
```
priority_urgency_signal: "P2"        # input cho Priority Matrix, KHÔNG gán thẳng Priority
severity: "High"
maintenance_log: ["Kiểm tra kết nối cell 3", "Đo lại điện áp từng cell"]
requires_human_verification: true
safety_notes: ["PPE: Găng tay cách điện"]
```

## 7. Latency

Path `enrich=false` phải đạt SLA batch `< 500ms` theo `.claude/rules/tech/ai.md`.

**Benchmark thật (`scripts/benchmark_grpc.py --real-weights`, artifacts v1.6, 2026-07-21, n=50):**

| RPC | avg | p95 |
|-----|-----|-----|
| `Prescribe` (rule path, `enrich=false`) | 54.1ms | 72.4ms |

→ Đạt cả SLA batch (<500ms) lẫn SLA P1 hot-path (<100ms) — không cần tối ưu thêm cho luồng auto-ticket này. Số liệu tổng hợp với `Predict`/`PredictStream` xem `docs/grpc-integration-be.md` §6.

## 8. Ngoài scope của GH-23

- Code .NET phía `TicketService`/`BatteryService` (repo BE riêng).
- LLM/RAG enrichment (`enrich=true`) trong luồng auto-ticket.
- Logic ma trận Impact × Urgency (thuộc BE).

## 9. `ticket_history` — GH-105 (đã implement, chỉ ảnh hưởng `enrich=true`)

`PrescribeRequest.ticket_history` (`repeated string`) đã có sẵn trong contract từ trước nhưng chỉ mới được AI module sử dụng từ GH-105. Field này **không ảnh hưởng** luồng auto-ticket `enrich=false` ở mục 1–7 (dedup key có gồm `ticket_history` để tránh cache sai, nhưng nội dung thống kê không được dùng khi `enrich=false`) — chỉ có ý nghĩa khi BE/UI gọi `enrich=true` (tính năng "AI gợi ý chi tiết" thủ công, xem mục 2).

- **Định dạng:** mỗi phần tử trong list là 1 dòng tóm tắt ngắn cho 1 lần sửa chữa/bảo trì trước đó của **cùng battery_id**, ví dụ: `"2026-06-10: Replaced BMS fuse after overvoltage alert, resolved"`. Không cần structured JSON — free text ngắn gọn là đủ, AI chỉ nối các dòng lại làm context cho LLM.
- **Thứ tự:** giả định **oldest → newest** (cũ nhất trước). AI chỉ lấy **5 phần tử cuối cùng** của list (gần nhất) — gửi nhiều hơn 5 không sao, phần dư bị cắt phía AI, không cần BE tự giới hạn.
- **Rỗng/không gửi:** hợp lệ — response giữ nguyên như trước khi có `ticket_history` (không có lỗi, không có đoạn "past repairs" nào trong context LLM).
- ⚠️ Giả định thứ tự "oldest → newest" ở trên **chưa được BE xác nhận chính thức** — nếu BE gửi theo chiều ngược lại (newest → oldest), báo AI team để đổi `ticket_history[-N:]` thành `ticket_history[:N]` trong `src/services/prescription/diagnosis.py`.
