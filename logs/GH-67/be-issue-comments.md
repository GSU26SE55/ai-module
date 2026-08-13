# Nội dung comment cho 5 issue backend + 1 issue mới

> Soạn 2026-08-01. Mọi số liệu dưới đây đo trực tiếp trên artifact đang có trong
> `models/weights/`, không phải ước lượng. Copy từng khối vào đúng issue.

---

## 🆕 ISSUE MỚI — tạo trước, vì #777 phụ thuộc vào nó

**Repo:** `GSU26SE55/backend`
**Title:** `[BatteryService][AI-Module] SOH worker không gửi pack_config — model LFP không bao giờ được dùng`
**Labels:** `status: init`, `role: BE`, `priority: P1: Critical (4h)`, `type: fix`

### Tóm tắt

SOH worker gọi AI mà không kèm `pack_config`. AI mặc định rơi về bộ artifact NASA/NMC
(`soh_mamba_v1.6.pth`), nên toàn bộ phần chemistry-aware của AI-module đang là code chết
trong production: ngưỡng điện áp LFP, chuẩn hoá dòng theo C-rate, và model LFP
`soh_mamba_v2.0-lfp.pth` train riêng trên dataset Severson.

Pin thật của hệ thống là **LFP 4S**, đang được chấm bằng model train trên **NASA NMC 18650**.

### Bằng chứng

- AI chọn artifact tại `src/services/inference.py:70` `_resolve_artifacts(chemistry)` —
  `chemistry` khác `"LFP"` đều trả về bộ NASA.
- Không có issue nào ở repo `backend` nhắc tới `pack_config` / `chemistry` / `LFP` (0 kết quả).
- Issue #777 mô tả worker gửi 4 cột "cho **model v1.6**" — xác nhận đang dùng bộ NASA.
- Contract đã hỗ trợ sẵn từ GH-65/GH-67: `PackConfig { n_series, chemistry, capacity_ah }`
  có trong `protos/ai_service.proto`, cho cả `PredictRequest` lẫn `PrescribeRequest`.

### Khác biệt khi gửi đúng `chemistry`

Đo trên cùng một payload pack LFP 4S:

| | không `pack_config` | `chemistry="LFP"` |
|---|---|---|
| Artifact dùng | NASA v1.6 | **LFP v2.0-lfp** |
| SOH | 88.21% | **100.00%** |
| Ngưỡng điện áp cảnh báo | NMC (3.0/3.2/4.15/4.2 V) | **LFP (2.5/2.8/3.65/3.8 V)** |
| `cycle_count` chia cho | 200 | **2300** |
| Chuẩn hoá dòng theo `capacity_ah` | không | **có** |

Lệch **11.79 điểm SOH** trên cùng một dữ liệu.

### ❓ Câu hỏi cần BE xác nhận trước khi implement

**`SensorReading.Voltage` là điện áp _pack_ hay _per-cell_?**

AI reject mọi giá trị per-cell ngoài `[2.0, 4.5] V`. Issue #777 cho thấy prediction vẫn
chạy ra số (67.33), nên dữ liệu hiện tại phải đang là **per-cell**. Nhưng BMS pin 4S thường
báo điện áp pack (~12.8 V).

- Nếu **per-cell** → gửi `n_series = 1`
- Nếu **pack** → gửi `n_series = 4`

Gửi sai `n_series` sẽ chia điện áp lệch 4 lần **mà không có lỗi nào được raise** — SOH sai
âm thầm.

### Acceptance criteria

- [ ] Worker gửi `pack_config { n_series, chemistry="LFP", capacity_ah }` ở cả `Predict` và `Prescribe`.
- [ ] `n_series` khớp với đơn vị của `SensorReading.Voltage` (xác nhận câu hỏi trên).
- [ ] Test assert `metadata.model_version == "2.0-lfp"` và `metadata.chemistry == "LFP"` trong response.
- [ ] Giá trị `capacity_ah` lấy từ cấu hình asset, không hardcode.

### Phụ thuộc

Phải làm **cùng lúc** với #777: model LFP **từ chối payload 4 cột** (xem comment ở #777).
Gửi `pack_config` mà vẫn 4 cột sẽ lỗi ngay.

---

## #777 — SOH worker discards cycle count and SOC inputs

> ⚠️ Comment này **đính chính một giả định trong issue**. Sửa theo mô tả hiện tại sẽ làm SOH
> **tệ đi**, không tốt lên.

### `cycle_count` và `soc_percent` không cùng bản chất — phải tách

**`cycle_count`: gửi đi là cải thiện thật ✅** — hiện AI phải thay bằng 0, mất hẳn tín hiệu tuổi pin.

**`soc_percent`: gửi SOC thật là SAI cho tới khi kèm `chemistry="LFP"` ❌**

### Vì sao

Model NASA `v1.6` được train với `soc_mode = window` — SOC tính **cục bộ trong cửa sổ 30 dòng**,
nên mọi window đều bắt đầu ở 100%, dải chỉ `[0.94, 1.00]`. SOC thật của pin trải `[0.00, 1.00]`.
Vùng dưới 0.94 là vùng model **chưa từng thấy khi train**.

Đo lại trên cùng một window (artifact `models/weights/soh_mamba_v1.6.pth`):

| Cách gửi | SOH |
|---|---|
| 4 cột (BE hiện tại) | 65.85 |
| 6 cột, **SOC thật = 20%** (như issue đề xuất) | **60.93** |
| 6 cột, SOC thật = 50% | 65.99 |
| 6 cột, SOC thật = 90% | 64.84 |
| 6 cột, SOC **khớp ngữ nghĩa lúc train** | **66.46** |

Giá trị đúng theo ngữ nghĩa train là **66.46**. Bản 4 cột (65.85) **gần nó hơn** bản SOC thật
(60.93). Con số 26.87 điểm mà issue đo được là **mức lệch do sai ngữ nghĩa**, không phải mức
cải thiện.

### Đường đi đúng

Gửi `pack_config { chemistry: "LFP", ... }` → AI chuyển sang model `v2.0-lfp`, vốn được train
với `soc_mode = cycle` (SOC trải suốt đoạn xả). **Lúc đó SOC thật mới đúng ngữ nghĩa.**

| | NASA v1.6 | LFP v2.0 |
|---|---|---|
| `soc_mode` lúc train | `window` | **`cycle`** |
| SOC thật BE gửi có đúng không | ❌ | ✅ |
| Payload 6 cột | tuỳ chọn | **bắt buộc** |
| `cycle_count` chia cho | 200 | **2300** |

Model LFP **từ chối payload 4 cột** (`src/services/inference.py:190`) — vì cửa sổ 30 dòng
không thể dựng lại SOC toàn chu kỳ, nên AI báo lỗi rõ ràng thay vì đoán bừa.

### Đề xuất

Gộp issue này với issue mới **"BE gửi `pack_config`"** — hai việc không tách được:

1. BE gửi `pack_config { n_series, chemistry: "LFP", capacity_ah }`
2. **Cùng lúc** chuyển sang payload 6 cột (`voltage, current, temperature, time, cycle_count, soc_percent`)

Làm riêng lẻ bước nào cũng hỏng: gửi `pack_config` mà 4 cột → lỗi; gửi 6 cột mà không
`pack_config` → SOH lệch âm thầm.

**Không cần retrain model nào.**

---

## #783 — SOH prescribe runs before dedup and open alerts duplicate hourly

Xác nhận đây là lỗi **phía BE**, AI-module không có gì phải sửa. Bổ sung một điểm để tránh
đi nhầm hướng:

### Idempotency cache của AI KHÔNG cứu được ca này

AI có cache idempotency (GH-84) tại `src/services/prescription/observability.py:44`, nhưng
key được tính từ `battery_id + readings + enrich + agentic + ticket_history + pack_config`.

**`readings` thay đổi mỗi tick** (cửa sổ 30 dòng trượt theo thời gian) → key luôn khác →
**cache luôn miss**. Nên 8 lần gọi Prescribe mỗi tick vẫn chạy đủ RAG + LLM, tốn chi phí thật.

Cache chỉ chặn được retry trùng lặp trong TTL với **cùng y hệt** readings — không phải ca này.

### Hệ quả chi phí

`enrich=true` đi qua RAG + LLM (vài giây, có gọi mạng). `enrich=false` là rule-based
(~54ms, không mạng). Nếu worker chỉ cần đánh giá để tạo alert, cân nhắc `enrich=false` cho
đường tự động và chỉ dùng `enrich=true` khi kỹ thuật viên bấm xem chi tiết —
`docs/overall.md` §10 khuyến nghị đúng như vậy.

### Fix vẫn phải ở BE

Kiểm tra alert chưa resolve **trước** khi gọi Prescribe. AI không giữ trạng thái alert nên
không thể dedup hộ.

---

## #780 — Ai MinReadings configuration violates the exact 30-row model contract

Xác nhận lỗi **phía BE config**, AI-module không sửa gì.

### Ràng buộc đúng 30 là cố ý, không nới được

`WINDOW_SIZE = 30` (`src/core/config.py:21`) là hằng số kiến trúc, không phải tham số điều
chỉnh được:

- Model được train trên đúng cửa sổ 30 bước; 29 hay 31 là phân bố khác hẳn.
- 57 đặc trưng phổ/thống kê tính trên đúng 30 mẫu — đổi độ dài là đổi toàn bộ phổ FFT.
- `.claude/rules/tech/ai.md` quy định window=30 phải nhất quán train ↔ inference.

Nên AI reject `!= 30` bằng `422` (REST) / `INVALID_ARGUMENT` (gRPC) là **đúng thiết kế**,
không nên nới thành khoảng.

### Đề xuất

Tách `Ai:MinReadings` thành 2 option riêng như issue đã nêu:

- `Ai:WindowSize` — **cố định 30**, hoặc bỏ hẳn và hardcode, vì nó là hằng số contract
- `Ai:MinHistoryReadings` — ngưỡng lịch sử tối thiểu trước khi bắt đầu gọi AI (tự do đặt)

Thêm validate lúc startup để cấu hình sai chết ngay thay vì gửi payload sai rồi nhận null
suốt.

---

## #805 — Critical P1/P2 risk is ignored when classification remains Normal

Xác nhận đây là lỗi **phía BE**, và quan trọng: **AI trả `Normal` + `P1` là hợp lệ, không
phải bug AI.**

### `classification` và `risk.priority` là 2 taxonomy độc lập

`docs/overall.md` §8.2 và §8.3 ghi rõ:

- `classification` (`Normal`/`Degrading`/`Failed`) — suy **thuần từ `soh_percent`**
- `anomaly.anomaly_status` (`Normal`/`Warning`/`Anomaly`) — suy **thuần từ IsolationForest score**
- `risk.priority` (`P1`/`P2`/`P3`/`None`) — suy từ **mức nghiêm trọng kỹ thuật**: `health_stage`,
  `anomaly_status`, và **cảnh báo critical**

Ba nhóm này **không map 1-1**. Ca trong issue (SOH 95, score 0, nhiệt độ 50°C) đúng là:
pin còn khoẻ về dung lượng (`Normal`) nhưng đang có sự cố nhiệt (`TEMP_CRITICAL` →
`risk = Critical`, `priority = P1`). Cả hai đều đúng.

### Lưu ý thêm khi implement

`docs/overall.md` §8.3 cảnh báo: **`priority` không tỉ lệ thuận với `action_code`**. Mọi
`soh_percent` rơi vào 80–85% đều kèm `SOH_CRITICAL` nên được gán `P1`, **kể cả khi**
`action_code` chỉ là `SCHEDULE_REPLACEMENT`.

Nên khi map sang alert: đọc `action_code` để biết **hành động**, đọc `priority` để biết
**mức khẩn**. Đừng suy cái này ra cái kia.

Và nhớ `risk.priority` chỉ là **tín hiệu Urgency** — Priority ticket thật vẫn do BE tính
theo ma trận Impact × Urgency lúc Manager triage (`.claude/rules/design.md`).

---

## #778 — Prescription feedback loop is disconnected

Xác nhận: phần map `prescription_id` là **việc BE**. Nhưng có một điểm cần chốt trước.

### gRPC hiện KHÔNG có RPC feedback

`protos/ai_service.proto` chỉ có 4 RPC: `Predict`, `Prescribe`, `Health`, `PredictStream`.
Endpoint feedback **chỉ tồn tại ở REST**: `POST /prescribe/feedback`.
`docs/overall.md` §9.3 đã ghi nhận khoảng trống này từ trước.

### Hai lựa chọn

**A. BE gọi REST riêng cho bước feedback**
- AI không phải làm gì
- BE giữ thêm 1 HTTP client bên cạnh gRPC chỉ cho 1 endpoint

**B. AI thêm RPC `SubmitFeedback`**
- BE thuần gRPC
- Chi phí AI: thêm 2 message + 1 RPC vào proto (chỉ **thêm** field number mới, không đổi số
  cũ), regen stub, servicer gọi chung `submit_prescription_feedback()` với REST, cộng test
  parity 2 transport

**Cần chốt phương án trước khi BE bắt tay vào.** Nếu feedback là đường ghi vào bộ nhớ RAG
dùng lâu dài thì nên chọn B; nếu chỉ phục vụ demo thì A đủ.

### Lưu ý về `prescription_id`

`prescription_id` **chỉ được set khi `enrich=true`** và ghi history thành công; các trường
hợp còn lại trả `""`. BE phải coi `""` là "không có bản ghi để gửi feedback" chứ không phải lỗi.
