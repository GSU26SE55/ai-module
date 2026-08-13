# Hướng dẫn test thủ công trên Swagger — AI ↔ BE

> **Mọi ID và số đo dưới đây lấy trực tiếp từ DB đang chạy** và đã được tôi gọi thử — dán vào Swagger là chạy.
> Dữ liệu đổi thì lấy lại bằng SQL ở [§8](#8-lấy-lại-dữ-liệu-khi-db-đổi).

---

## 0. Địa chỉ Swagger (đã kiểm, cả 4 đều mở)

| Service | URL | Auth |
|---|---|---|
| **AI module** | http://localhost:4015/docs | **không cần** |
| BatteryService | http://localhost:4006/swagger/index.html | Bearer |
| TicketService | http://localhost:4007/swagger/index.html | Bearer |
| ApiGateway | http://localhost:4001/swagger/index.html | Bearer |

**Lấy token:** `POST /api/auth/login` → copy `data.tokens.accessToken` → nút **Authorize** → dán `Bearer <token>`

| Role | Email | Mật khẩu | Dùng cho |
|---|---|---|---|
| Admin | `admin@yourdomain.com` | `Admin123@` | §5, §6 |
| **Manager** | `manager.demo@solarbattery.local` | `Password123@` | **§7 (Admin sẽ bị 403)** |

---

## 1. Bảng pin thật — chọn đúng pin cho đúng phép thử

| Serial | asset_id | Chemistry | Pack | `pack_config` phải gửi | Số đo | Prediction |
|---|---|---|---|---|---|---|
| BAT-2026-002 | `2810f7d9-a11e-4ab0-85d0-d4e68cce8443` | **LiFePO4** | 12V/100Ah | `n_series:4, chemistry:"LFP", capacity_ah:100` | 31.114 | 1024 |
| BAT-2026-003 | `5e2116ec-4d54-4bc6-a2e8-543a86c48934` | **Nmc** | 48V/200Ah | `n_series:13, chemistry:"NMC", capacity_ah:200` | 19.968 | 1021 |
| BAT-2026-007 | `6f9ee6a1-dd0d-45fb-8831-df7be623aac8` | **Nca** | 24V/150Ah | `n_series:7, chemistry:"NMC", capacity_ah:150` | 6.546 | 642 |
| BAT-2026-008 | `125840ea-278b-49b5-8519-05a563865439` | LiFePO4 | 12V/100Ah | như BAT-2026-002 | 6.195 | 1022 |

> `n_series` = điện áp pack ÷ điện áp 1 cell (LFP 3.2V · NMC 3.7V · NCA 3.6V), làm tròn.
> Gửi sai `n_series` thì điện áp per-cell rơi ngoài dải → **422**.

---

## 2. ⭐ Phép thử quan trọng nhất — cùng số đo, khác `chemistry`, lệch 60 điểm SOH

Đây là lỗi nặng nhất đã sửa trong đợt này. **Dán đúng payload dưới đây 3 lần**, mỗi lần đổi `pack_config`.

> 🚨 **Payload dưới đây hiện KHÔNG chạy được nữa — kiểm chứng lại 2026-08-11.** Cả 3 lần đều trả
> **422**: *"window trải 2060s (34 phút), vượt trần 1500s (25 phút)"*. Guard giới hạn độ trải của
> window được thêm **sau** khi bài hướng dẫn này được viết, nên các con số kỳ vọng bên dưới
> (38.25% / 98.29%) **không tái lập được** — không liên quan đến việc đổi model v2.0-lfp → v2.1-lfp.
> Cần sinh lại bộ readings có 30 mẫu nằm gọn trong 25 phút rồi đo lại toàn bộ mục này.

Vào **http://localhost:4015/docs** → `POST /predict/` → Try it out.

### Lần 1 — KHÔNG có `pack_config`

```json
{ "battery_id": "BAT-2026-002", "readings": [[12.580, -1.720, 27.05, 0.0, 245, 16.88], [12.570, -1.770, 27.04, 5.1, 245, 16.88], [12.550, 0.370, 27.72, 1042.1, 245, 16.88], [12.540, 0.670, 27.61, 1047.1, 245, 16.88], [12.520, 0.670, 29.21, 1896.1, 245, 16.88], [12.540, 0.480, 29.25, 1911.8, 245, 16.88], [12.540, 0.210, 29.59, 1917.1, 245, 16.88], [12.550, 0.100, 29.15, 1922.6, 245, 16.88], [12.560, -0.310, 29.33, 1941.7, 245, 16.88], [12.560, -0.550, 29.39, 1947.4, 245, 16.88], [12.570, -0.840, 29.34, 1952.9, 245, 16.88], [12.560, -0.910, 29.30, 1958.0, 245, 16.88], [12.570, -1.360, 29.36, 1974.3, 245, 16.87], [12.570, -1.610, 29.63, 1979.4, 245, 16.87], [12.580, -1.850, 29.16, 1984.5, 245, 16.87], [12.580, -1.720, 29.34, 1989.5, 245, 16.87], [12.590, -2.110, 29.41, 1994.6, 245, 16.86], [12.600, -2.140, 29.74, 1999.6, 245, 16.86], [12.600, -2.040, 29.17, 2004.7, 245, 16.86], [12.610, -2.430, 29.60, 2009.8, 245, 16.86], [12.600, -2.310, 29.23, 2014.8, 245, 16.85], [12.600, -2.350, 29.34, 2019.8, 245, 16.85], [12.600, -2.590, 29.89, 2024.9, 245, 16.85], [12.600, -2.530, 29.38, 2029.9, 245, 16.84], [12.590, -2.630, 29.37, 2035.0, 245, 16.84], [12.590, -2.540, 29.30, 2040.0, 245, 16.83], [12.580, -2.330, 29.58, 2045.1, 245, 16.83], [12.580, -2.220, 29.44, 2050.1, 245, 16.83], [12.590, -2.300, 29.46, 2055.2, 245, 16.82], [12.580, -2.110, 29.14, 2060.3, 245, 16.82]] }
```

→ **422** · *"per-cell value 12.580 V outside allowed range"* + gợi ý gửi `n_series`. **Đúng** — AI chặn.

### Lần 2 — có `pack_config` nhưng THIẾU `chemistry`

Vẫn payload trên, thêm:
```json
"pack_config": { "n_series": 4, "capacity_ah": 100 }
```

→ **200** · `soh_percent ≈ 38.25` · `health_stage: "End Of Life"` · `model_version: "1.6"`

### Lần 3 — `pack_config` ĐẦY ĐỦ

```json
"pack_config": { "n_series": 4, "chemistry": "LFP", "capacity_ah": 100 }
```

→ **200** · `soh_percent ≈ 98.29` · `health_stage: "Healthy"` · `model_version: "2.1-lfp"`

| | Lần 2 (thiếu chemistry) | Lần 3 (đúng) |
|---|---|---|
| SOH | **38.25%** | **98.29%** |
| Kết luận | End Of Life | Healthy |
| Model | 1.6 (NASA) | 2.1-lfp |

**Lệch 60 điểm SOH. Một bên bảo pin sắp chết, bên kia bảo pin khoẻ — và KHÔNG có lỗi nào báo ra.**
Đó là lý do `chemistry` là trường bắt buộc trên thực tế dù schema cho phép bỏ trống.

---

## 3. AI module — 7 endpoint (http://localhost:4015/docs)

### 3.1 `GET /health`

Phải thấy đủ 5 field MỚI (thiếu = đang chạy image cũ):
```
lfp_loaded = true · soc_mode = "window" · lfp_soc_mode = "cycle"
long_model_version = "2.2" · prescription_metrics = { 7 counter }
```

### 3.2 `POST /predict/` — xem §2

### 3.3 `POST /predict/long` ⭐ MỚI — SOH chuỗi dài

Cần **31..4096** dòng, chỉ **4 cột**. Dùng payload NMC thật (30 dòng thì bị 422 — xem §4):

```json
{
  "battery_id": "BAT-2026-003",
  "readings": [[41.310, -3.200, 28.32, 0.0], [41.310, -3.310, 28.36, 5.4], [41.310, -3.550, 28.96, 10.5], [41.330, -3.670, 29.75, 1047.5], [41.310, -3.260, 30.71, 1911.3], [41.320, -3.590, 31.10, 1916.5], [41.330, -3.780, 31.61, 1932.8], [41.340, -3.780, 31.28, 1938.2], [41.330, -3.560, 30.94, 1943.5], [41.320, -3.260, 30.71, 1964.0], [41.310, -3.570, 31.19, 1969.0], [41.310, -3.520, 30.86, 1974.0], [41.310, -3.220, 30.27, 1979.1], [41.310, -3.410, 30.48, 1984.1], [41.310, -3.340, 30.86, 1989.3], [41.320, -3.450, 30.83, 1994.5], [41.320, -3.230, 30.53, 1999.6], [41.330, -3.360, 30.55, 2004.6], [41.340, -3.780, 30.80, 2009.7], [41.340, -3.690, 30.61, 2014.8], [41.330, -3.660, 30.95, 2019.9], [41.330, -3.510, 30.40, 2025.0], [41.320, -3.410, 30.51, 2030.0], [41.330, -3.660, 30.91, 2035.1], [41.310, -3.240, 30.34, 2040.2], [41.310, -3.440, 30.59, 2045.2], [41.300, -3.230, 29.84, 2050.3], [41.310, -3.450, 30.14, 2055.4], [41.310, -3.240, 30.24, 2060.4], [41.320, -3.730, 30.74, 2065.7]],
  "pack_config": { "n_series": 13, "chemistry": "NMC", "capacity_ah": 200 }
}
```

> ⚠️ Payload này đúng **30 dòng** nên sẽ trả **422** — đó là chủ ý, để bạn thấy ranh giới.
> Muốn 200: lấy nhiều dòng hơn bằng SQL ở §8, hoặc gọi qua BE (§6.2) tiện hơn.

**Khi thành công:** `model_version: "2.2"` — **khác** `"1.6"`. Hai bộ trọng số riêng, **đừng so hai số SOH với nhau**.
Đường này cố ý không có anomaly/risk/confidence ⇒ **không dùng để quyết định tạo ticket**.

### 3.4 `POST /predict/feedback` ⭐ MỚI — phản hồi phân loại

```json
{ "battery_id": "BAT-2026-002", "classification": "Degrading", "verdict": "correct" }
```

- `classification` = nhãn AI **đã đưa ra**: `Normal` | `Degrading` | `Failed`
- `verdict` = đánh giá của bạn: `correct` | `false_positive` | `false_negative`

Gọi 2 lần → `total` phải **tăng 1**. `precision` = `null` khi chưa đủ mẫu (**khác** `0.0` nghĩa là "đã chấm và sai hết").

### 3.5 `POST /prescribe/`

```json
{
  "battery_id": "BAT-2026-002",
  "readings": [[12.580, -1.720, 27.05, 0.0, 245, 16.88], [12.570, -1.770, 27.04, 5.1, 245, 16.88], [12.550, 0.370, 27.72, 1042.1, 245, 16.88], [12.540, 0.670, 27.61, 1047.1, 245, 16.88], [12.520, 0.670, 29.21, 1896.1, 245, 16.88], [12.540, 0.480, 29.25, 1911.8, 245, 16.88], [12.540, 0.210, 29.59, 1917.1, 245, 16.88], [12.550, 0.100, 29.15, 1922.6, 245, 16.88], [12.560, -0.310, 29.33, 1941.7, 245, 16.88], [12.560, -0.550, 29.39, 1947.4, 245, 16.88], [12.570, -0.840, 29.34, 1952.9, 245, 16.88], [12.560, -0.910, 29.30, 1958.0, 245, 16.88], [12.570, -1.360, 29.36, 1974.3, 245, 16.87], [12.570, -1.610, 29.63, 1979.4, 245, 16.87], [12.580, -1.850, 29.16, 1984.5, 245, 16.87], [12.580, -1.720, 29.34, 1989.5, 245, 16.87], [12.590, -2.110, 29.41, 1994.6, 245, 16.86], [12.600, -2.140, 29.74, 1999.6, 245, 16.86], [12.600, -2.040, 29.17, 2004.7, 245, 16.86], [12.610, -2.430, 29.60, 2009.8, 245, 16.86], [12.600, -2.310, 29.23, 2014.8, 245, 16.85], [12.600, -2.350, 29.34, 2019.8, 245, 16.85], [12.600, -2.590, 29.89, 2024.9, 245, 16.85], [12.600, -2.530, 29.38, 2029.9, 245, 16.84], [12.590, -2.630, 29.37, 2035.0, 245, 16.84], [12.590, -2.540, 29.30, 2040.0, 245, 16.83], [12.580, -2.330, 29.58, 2045.1, 245, 16.83], [12.580, -2.220, 29.44, 2050.1, 245, 16.83], [12.590, -2.300, 29.46, 2055.2, 245, 16.82], [12.580, -2.110, 29.14, 2060.3, 245, 16.82]],
  "pack_config": { "n_series": 4, "chemistry": "LFP", "capacity_ah": 100 },
  "enrich": true
}
```

Xem 3 field mới: `escalation_conditions`, `blocked`, `cached`.
`enrich: true` để lấy `prescription_id` (dùng cho §3.6). Không có LLM key vẫn chạy, chỉ là `enriched: false`.

### 3.6 `POST /prescribe/feedback`

```json
{ "prescription_id": "<id từ §3.5>", "status": "accepted" }
```
`status`: `accepted` | `edited` | `rejected`. ID sai → **404**.

### 3.7 `POST /verify-ticket/`

```json
{
  "title": "Pin nóng bất thường",
  "description": "Pin bốc khói, nhiệt độ tăng cao đột ngột lúc 3h sáng",
  "category": 1,
  "candidates": []
}
```
→ `verdict`: `legitimate` | `suspicious` + `score` + `reason` tiếng Việt.

---

## 4. Đường LỖI — chứng minh AI không nuốt dữ liệu rác

| Gọi gì | Phải trả |
|---|---|
| `/predict/` chỉ **1 dòng** readings | **422** |
| `/predict/long` đúng **30 dòng** (payload §3.3) | **422** — 30 dòng thuộc `/predict` |
| `/predict/feedback` với `verdict: "maybe"` | **422** |
| `/predict/feedback` với `classification: "Broken"` | **422** |
| `/predict/` payload §2 không có `pack_config` | **422** |

> Bất kỳ dòng nào trả **200** hoặc **500** thay vì 422 ⇒ **có lỗi thật**.

---

## 5. BatteryService — đọc dữ liệu AI (:4006, cần Authorize)

### 5.1 `GET /api/v1/soh-predictions` — 12 field mới

```
batteryAssetId = 2810f7d9-a11e-4ab0-85d0-d4e68cce8443
pageNumber = 1 · pageSize = 5
```

> ⚠️ **`batteryAssetId` là bắt buộc.** Bỏ trống → trả **list rỗng kèm 200**, trông như API hỏng nhưng thực ra là gọi thiếu tham số.

Kiểm đủ 12 field: `healthStage` `stageConfidence` `isBorderline` `sohStd` `rulCyclesEstimate`
`aiPriority` `riskLevel` `actionCode` `sohTrend` `degradationRatePerCycle` `cyclesToMaintenance` `isTemperatureOod`

Pin này là LiFePO4 nên `modelVersion` phải là **`2.1-lfp`**.

---

## 6. BatteryService — endpoint MỚI

### 6.1 `GET /api/v1/soh-predictions/long` ⭐

```
batteryAssetId = 2810f7d9-a11e-4ab0-85d0-d4e68cce8443
limit = 300
```
→ **200**, `modelVersion: "2.2"`. BE tự lấy 300 số đo nên **không phải dán payload**.
**409** = pin chưa đủ 31 số đo · **503** = AI không phản hồi.

### 6.2 `GET /api/v1/soh-predictions/batch` ⭐

```
limit = 10
```
→ **200**. **Đọc `isComplete` TRƯỚC khi nhìn `items`.**

> ⚠️ Pin không có trong `items` = **chưa được chấm**, KHÔNG phải "pin bình thường".
> Bidi stream không có lỗi theo từng message: một cửa sổ sai làm đứt cả lượt.

### 6.3 `POST /api/alerts/{id}/ai-prescription` ⭐

```
id = 4fde106b-1345-4830-bfd1-f68b023fd66a     (pin BAT-2026-002 — đã thử, trả 200)
agentic = false
```
→ **200**. Đã chạy thật, kết quả: `actionSteps` 4 bước · `escalationConditions` 1 · `blocked=false` · `cached=true` · có `prescriptionId`.

> `agentic=true` bật chain 2 lượt LLM (chậm hơn). Luồng tự động luôn để `false`.

**Nếu gặp 409 "Cửa sổ thiếu cycle_count" — KHÔNG phải lỗi.** Pin LiFePO4 dùng bộ trọng số
`soc_mode="cycle"`, bắt buộc payload 6 cột. Chỉ cần **một** số đo trong cửa sổ 30 thiếu
`cycle_count` là BE dừng trước khi gọi AI — vì gửi đi cầm chắc bị từ chối, chỉ tốn thêm một
lượt gRPC và một lượt HTTP fallback rồi vẫn về tay không.

Ví dụ alert `752b2b0e-46d3-43b5-9a37-ead47c95bec4` trả 409 đúng vì lý do này (59/60 số đo có
`cycle_count`). Tìm alert khác dùng SQL ở §8, hoặc thử lần lượt:

```bash
T=$(curl -s -X POST http://localhost:4001/api/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"admin@yourdomain.com","password":"Admin123@"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["tokens"]["accessToken"])')

for A in $(docker exec solar-postgres psql -U postgres -d battery_db -tAc \
  "SELECT id FROM alerts WHERE battery_asset_id IS NOT NULL AND NOT is_deleted LIMIT 15;" | tr -d ' '); do
  C=$(curl -s -o /dev/null -w '%{http_code}' -m 90 -X POST -H "Authorization: Bearer $T" \
      "http://localhost:4006/api/alerts/$A/ai-prescription?agentic=false")
  [ "$C" = "200" ] && { echo "dùng alert này: $A"; break; }
done
```

### 6.4 `POST /api/alerts/{id}/prescription-feedback` ⭐

**Phải chạy §6.3 trước** để alert có `AiPrescriptionId`, rồi dùng **cùng id**:
```
id = 4fde106b-1345-4830-bfd1-f68b023fd66a
```
```json
{ "status": "accepted" }
```
→ **200**, `data` = `prescriptionId` vừa được phản hồi.

| Mã | Khi nào |
|---|---|
| **400** | `status` không thuộc `accepted`/`edited`/`rejected`, hoặc `status="edited"` mà thiếu `editedSteps` → `listErrors` chỉ rõ field |
| **409** | Alert chưa từng được kê đơn (chưa có `AiPrescriptionId`) |
| **410** | AI không còn giữ `prescriptionId` đó — thử lại vô ích |
| **503** | Không nối được AI — thử lại sau |

> **Sửa 2026-08-06:** trước đây lỗi validate trả **502** *"Upstream service không phản hồi hợp lệ"*
> thay vì 400 — do `ValidateAsync()` không gán `StatusCode`, để mặc định `0`, khiến Kestrel ghi ra dòng
> status `HTTP/1.1 0`. Nếu bạn còn thấy 502 ở đây thì container `batteryservice` đang chạy bản cũ,
> rebuild lại.

**Thử nhanh nhánh 400:**
```json
{ "status": "maybe" }
```
→ `400` + `listErrors: [{"field":"Status","detail":"Chỉ nhận: accepted, edited, rejected."}]`

> Alert `fc9f6003-35e1-480a-9805-9383ec260821` **đã có** prescription sẵn — dùng nó nếu muốn bỏ qua §6.3.

### 6.5 `POST /api/v1/anomaly-classifications/{id}/feedback`

```
id = 032dacb2-edc3-4d32-800b-83787a8f4c4d     (chưa có staff_feedback)
```
```json
{ "feedback": 1 }
```
`feedback`: `1` Correct · `2` FalsePositive · `3` FalseNegative → **200**.

**Chứng minh AI thật sự nhận được:** gọi §3.4 trước và sau, `total` phải **tăng 2** (1 của bạn + 1 của §3.4).

---

## 7. TicketService — AI verify (:4007, cần token **Manager**)

### `POST /api/admin/tickets/{id}/re-verify`

**Trạng thái ticket thật hiện tại:**

| id | code | status | ai_verify_status | Gọi sẽ ra |
|---|---|---|---|---|
| `5582164e-bdb6-4b2a-95cf-1f07a6ce0e24` | TKT-2602-0002 | 4 InProgress | 2 Legitimate | **400** — đã có verdict |
| `dcd82c06-cb51-4b3b-9e10-42d676983961` | TKT-2602-0001 | 9 Escalated | 2 Legitimate | **400** — đã có verdict |
| `b73bd649-fb82-47a3-8bf2-d4d8c90c1f96` | TKT-2602-0005 | 11 Closed | 1 Pending | **409** — ticket đã đóng |

**Cả ba đều KHÔNG ra 200** — đó là guard đúng, không phải lỗi. Ba điều kiện phải khớp cả ba:
`origin=1` · `ai_verify_status ∈ {1,4}` · `status ∉ {10,11,12}`

**Đưa 1 ticket về Pending để test được:**
```bash
docker exec solar-postgres psql -U postgres -d ticket_db -c \
 "UPDATE tickets SET ai_verify_status=1, ai_verify_score=NULL, ai_verify_reason=NULL
  WHERE id='dcd82c06-cb51-4b3b-9e10-42d676983961';"
```

Gọi lại → **200**. Kiểm DB:
```bash
docker exec solar-postgres psql -U postgres -d ticket_db -c \
 "SELECT code, ai_verify_status, ai_verify_score, ai_verify_reason
  FROM tickets WHERE id='dcd82c06-cb51-4b3b-9e10-42d676983961';"
```
`ai_verify_status` phải rời **1** → **2 (Legitimate)** hoặc **3 (Suspicious)**, kèm score và lý do tiếng Việt.

---

## 8. Lấy lại dữ liệu khi DB đổi

```bash
# Pin + pack_config (n_series tự tính)
docker exec solar-postgres psql -U postgres -d battery_db -c "
SELECT a.serial_number, a.id, bt.chemistry, bt.nominal_voltage, bt.nominal_capacity_ah,
  round(bt.nominal_voltage / CASE bt.chemistry WHEN 1 THEN 3.2 WHEN 3 THEN 3.6 ELSE 3.7 END) AS n_series
FROM battery_assets a JOIN battery_types bt ON bt.id=a.battery_type_id WHERE NOT a.is_deleted;"

# Số đo thật 6 cột (pin LFP) — đổi asset_id và LIMIT tuỳ ý
docker exec solar-postgres psql -U postgres -d battery_db -tAc "
SELECT json_agg(row ORDER BY t)::text FROM (
  SELECT json_build_array(round(voltage,3), round(current,3), round(temperature,2),
    round(EXTRACT(EPOCH FROM (time - MIN(time) OVER ()))::numeric,1), cycle_count, round(soc_percent,2)) AS row, time AS t
  FROM (SELECT * FROM sensor_readings WHERE battery_asset_id='2810f7d9-a11e-4ab0-85d0-d4e68cce8443'
    AND (sensor_source_code IS NULL OR sensor_source_code='' OR sensor_source_code='primary')
    AND cycle_count IS NOT NULL ORDER BY time DESC LIMIT 30) x) y;"

# Alert chưa có prescription
docker exec solar-postgres psql -U postgres -d battery_db -tAc "
SELECT id FROM alerts WHERE ai_prescription_id IS NULL AND battery_asset_id IS NOT NULL
  AND NOT is_deleted LIMIT 3;"

# Classification chưa có feedback
docker exec solar-postgres psql -U postgres -d battery_db -tAc "
SELECT id FROM anomaly_classifications WHERE staff_feedback IS NULL AND NOT is_deleted LIMIT 3;"

# Ticket đủ điều kiện re-verify
docker exec solar-postgres psql -U postgres -d ticket_db -tAc "
SELECT id, code, status, ai_verify_status FROM tickets
WHERE origin=1 AND ai_verify_status IN (1,4) AND status NOT IN (10,11,12) AND NOT is_deleted;"
```

---

## 9. Ba câu SQL kiểm nhanh sau khi test

```bash
# (a) Đúng model cho đúng chemistry — PHẢI thấy CẢ 1.6 LẪN 2.1-lfp
docker exec solar-postgres psql -U postgres -d battery_db -c \
 "SELECT model_version, count(*) FROM soh_predictions WHERE health_stage IS NOT NULL GROUP BY model_version;"

# (b) Job nền vẫn gọi AI
docker logs solar-batteryservice --since 15m | grep -o "SohPrediction tick[^\"]*" | tail -1

# (c) Hai container AI dùng chung store (kê ở HTTP, đọc ở gRPC)
cd ~/Documents/capstone/backend && bash tools/e2e-ai-integration.sh | grep -A 2 "7b\."
```

Chỉ thấy `1.6` ở (a) nghĩa là **mọi pin đang bị chấm bằng weight sai** — xem §2.

---

## 10. Chạy tự động thay vì bấm tay

```bash
cd ~/Documents/capstone/backend
bash tools/e2e-ai-integration.sh     # 44 check, cả hai chiều AI↔BE
loopctl verify                       # 5 tầng: build → unit → integration → e2e → e2e-ai
```
