# Kế hoạch kết nối hoàn chỉnh AI Module ↔ Backend

> **Ngày khảo sát:** 2026-08-06 (khảo sát lại toàn bộ — bản trước ngày 2026-08-05 đã lỗi thời sau khi `dev` merge branch 693)
>
> **Trạng thái repo tại thời điểm khảo sát:**
>
> | Repo | Branch | HEAD | Working tree |
> |---|---|---|---|
> | `capstone/ai-module` | `dev` | `f2cad71` — *fix: tem and chemiustry* | sạch |
> | `capstone/backend` | `dev` | `c482b23d` — *Merge PR #1073 from push-noti-test* | sạch |
>
> **Phương pháp:** đọc source hai repo · gọi thật vào container đang chạy (REST `:4015`, gRPC `ai-module-grpc:50051`) · đọc log container · đối chiếu proto bằng `diff` · truy vết Git bằng `reflog`/`show`.
>
> **Nguyên tắc:** mọi con số, đường dẫn, mã lỗi trong tài liệu đều lấy từ kiểm chứng thực tế. Chỗ nào chưa kiểm chứng được thì ghi rõ — xem [§7.5](#75-️-giới-hạn-khảo-sát--những-gì-chưa-kiểm-chứng-được).

---

## Mục lục

- [0. Tóm tắt điều hành](#0-tóm-tắt-điều-hành)
- [1. Hiện trạng đã kiểm chứng](#1-hiện-trạng-đã-kiểm-chứng)
- [2. Bốn nguyên nhân gốc](#2-bốn-nguyên-nhân-gốc)
- [3. Việc phải làm — repo `ai-module`](#3-việc-phải-làm--repo-ai-module)
- [4. Việc phải làm — repo `backend`](#4-việc-phải-làm--repo-backend)
- [5. Thứ tự thi hành](#5-thứ-tự-thi-hành)
- [6. Checklist kiểm chứng](#6-checklist-kiểm-chứng)
- [7. Rủi ro, bẫy và giới hạn khảo sát](#7-rủi-ro-bẫy-và-giới-hạn-khảo-sát)
- [8. Những phần đã đúng — không được đụng vào](#8-những-phần-đã-đúng--không-được-đụng-vào)
- [9. Việc đã hoàn thành từ bản kế hoạch trước](#9-việc-đã-hoàn-thành-từ-bản-kế-hoạch-trước)
- [Phụ lục A — Đối chiếu 3 bản proto](#phụ-lục-a--đối-chiếu-3-bản-proto)
- [Phụ lục B — Đối chiếu container vs `dev`](#phụ-lục-b--đối-chiếu-container-đang-chạy-vs-dev)
- [Phụ lục C — Lệnh thu thập bằng chứng](#phụ-lục-c--lệnh-thu-thập-bằng-chứng)

---

## 0. Tóm tắt điều hành

### 0.1. Ba tầng đang hỏng cùng lúc

```
┌── TẦNG HẠ TẦNG ────────────────────────────────────────────────────┐
│  solar-postgres · solar-redis · solar-rabbitmq  →  Exited (255)     │
│  ⇒ solar-batteryservice / solar-ticketservice CRASH LOOP (exit 133) │
│    "SocketException: Name or service not known" — 38 lần restart    │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌── TẦNG ẢNH (IMAGE) ────────────────────────────────────────────────┐
│  Image AI build lúc 2026-08-05 11:50 (VN) từ commit 41660e3         │
│  Merge branch 693 xảy ra lúc 14:13 — SAU khi build 2 giờ 23 phút    │
│  ⇒ Container chỉ có 4 RPC. KHÔNG có VerifyTicket, KHÔNG SubmitFeedback │
│  ⇒ AI verify của TicketService ĐANG HỎNG ÂM THẦM ngay lúc này        │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌── TẦNG CẤU HÌNH & HỢP ĐỒNG ────────────────────────────────────────┐
│  docker-compose.override.yml  → BatteryService trỏ về host, không ai nghe │
│  2 bản proto BE lạc hậu       → thiếu SubmitFeedback/cached/lfp_loaded    │
│  soc_percent lệch ngữ nghĩa   → 4 pin non-LFP bị sai số ÂM THẦM           │
└─────────────────────────────────────────────────────────────────────┘
```

### 0.2. Danh sách việc

| # | Repo | Việc | Mức |
|---|---|---|---|
| **C1** | *hạ tầng* | Khởi động lại `solar-postgres` / `solar-redis` / `solar-rabbitmq` — BE không boot nổi nếu thiếu | 🔴 P0 |
| **C2** | *deploy* | **Rebuild image AI từ `dev` hiện tại** — container đang thiếu `VerifyTicket` + `SubmitFeedback` | 🔴 P0 |
| **B1** | backend | Xoá `docker-compose.override.yml` (đã commit vào Git) | 🔴 P1 |
| **B2** | backend | Đồng bộ 2 bản `Protos/ai_service.proto` từ ai-module | 🔴 P1 |
| **B3** | backend | Sửa ngữ nghĩa `soc_percent` cho pin non-LFP — sai số ~27 điểm SOH, **không báo lỗi** | 🔴 P1 |
| **A1** | ai-module | Chạy `make lint` + `make test` + `make benchmark` trên `dev` sau merge — **chưa ai chạy** | 🔴 P1 |
| **B4** | backend | Chuyển feedback từ HTTP sang gRPC `SubmitFeedback` (tuỳ chọn) | 🟠 P2 |
| **B5** | backend | Thêm `healthcheck` cho 2 container AI | 🟡 P3 |
| **B6** | backend | Điền LLM API key nếu muốn prescription do LLM sinh | 🟡 P3 |

### 0.3. Thay đổi lớn so với bản kế hoạch ngày 05/08

| | Bản 05/08 | Bây giờ |
|---|---|---|
| `dev` có `VerifyTicket`? | ❌ chưa merge | ✅ **đã merge** (`3e22ced`) |
| Container có `VerifyTicket`? | ✅ có (build từ branch 693) | ❌ **không** (build từ `41660e3`) |
| `dev` có LFP? | ✅ | ✅ |
| Container có LFP? | ❌ | ✅ |
| `.dockerignore` | ❌ chưa có | ✅ đã thêm |
| RPC `SubmitFeedback` | không tồn tại | ✅ **mới có trên `dev`** |
| Rủi ro chính | rebuild sẽ làm hỏng verify | **verify ĐÃ hỏng rồi** — phải rebuild để cứu |

> ⚠️ **Rủi ro tôi cảnh báo trong bản trước đã thật sự xảy ra.** Bản 05/08 §7.1 viết: *"rebuild image AI từ `dev` khi chưa merge verify → `VerifyTicket` biến mất, hỏng nhưng không có dấu hiệu nào"*. Image đã được build lúc 11:50 ngày 05/08, merge diễn ra lúc 14:13 cùng ngày. Chỉ khác chi tiết thời điểm — hậu quả đúng như dự đoán.

---

## 1. Hiện trạng đã kiểm chứng

### 1.1. 🔴 Hạ tầng sập → hai service BE crash loop

```
$ docker ps -a --format "{{.Names}}\t{{.Status}}"
solar-postgres         Exited (255) 29 minutes ago
solar-redis            Exited (255) 29 minutes ago
solar-rabbitmq         Exited (255) 29 minutes ago
solar-batteryservice   Restarting (133)     ← 38 lần restart
solar-ticketservice    Restarting (133)     ← 38 lần restart
solar-ai-module-http   Up 29 minutes
solar-ai-module-grpc   Up 29 minutes
```

Stack trace của `solar-ticketservice`:
```
Unhandled exception. System.Net.Sockets.SocketException (00000005, 0xFFFDFFFF): Name or service not known
   at System.Net.Dns.GetHostAddresses(...)
   at Npgsql.Internal.NpgsqlConnector.Connect(NpgsqlTimeout timeout)
   ...
   at Program.<Main>$(String[] args) in /src/services/TicketService/src/TicketService.Api/Program.cs:line 97
```

Không resolve được hostname PostgreSQL vì container `solar-postgres` không chạy. `Program.cs:97` gọi `GetPendingMigrations()` lúc khởi động → không có DB thì ném exception ngay, không retry.

**Nguyên nhân sập:** log của cả 3 container đều **không có lỗi fatal** — dòng cuối là hoạt động bình thường (`checkpoint complete`, `Background saving terminated with success`, `alarm_handler: system_memory_high_watermark`) lúc `2026-08-05 14:50 UTC`. Exit `255` không kèm lỗi là dấu hiệu điển hình của **Docker Desktop bị tắt/restart**, không phải lỗi ứng dụng.

> Đây **không phải** vấn đề AI. Nhưng nó chặn mọi việc kiểm chứng phía BE, nên phải sửa trước (C1).

### 1.2. 🔴 Container AI thiếu 2 RPC — AI verify của TicketService đang hỏng

**Đã probe trực tiếp vào container đang chạy:**
```
$ docker exec solar-ai-module-grpc grep -n 'rpc ' /app/protos/ai_service.proto
20:  rpc Predict(...)
22:  rpc Prescribe(...)
24:  rpc Health(...)
26:  rpc PredictStream(...)
          ← CHỈ CÓ 4. Không có VerifyTicket. Không có SubmitFeedback.

$ docker exec solar-ai-module-http ls /app/src/routers/
__init__.py  __pycache__  health.py  predict.py  prescribe.py
          ← KHÔNG có verify.py

$ curl -o /dev/null -w "HTTP %{http_code}" -X POST localhost:4015/verify-ticket/ ...
HTTP 404
```
Gọi qua stub Python cũng xác nhận: `AttributeError: 'AiServiceStub' object has no attribute 'VerifyTicket'`.

**Mốc thời gian giải thích vì sao:**

| Thời điểm (VN) | Sự kiện |
|---|---|
| 05/08 **11:50** | Build image `backend-ai-module-grpc` — từ commit `41660e3` |
| 05/08 **11:51** | Tạo container `solar-ai-module-grpc` |
| 05/08 **14:13** | Commit `3e22ced` — *merge branch 693* (thêm `VerifyTicket`) |
| 05/08 **16:08** | Commit `f2cad71` — *fix: tem and chemiustry* (thêm `SubmitFeedback` + sửa LFP) |
| 06/08 **09:32** | `git pull origin dev` về máy — code mới về, **image vẫn cũ** |

→ Image đi **sau `dev` 2 commit**. `docker ps` hiện "Up 29 minutes" chỉ vì Docker Desktop khởi động lại, **không phải** vì image được build lại.

**Hậu quả với TicketService:** `AiTicketVerifyGrpcClient.VerifyAsync()` gọi `VerifyTicket` → server trả `UNIMPLEMENTED` → `catch (RpcException)` → **`return null`, chỉ ghi `LogWarning`** → `TicketVerifyRunner` set `AiVerifyStatus = Skipped`. Ticket vẫn tạo bình thường. **Không ai thấy có gì sai.**

### 1.3. 🔴 BatteryService vẫn bị ép trỏ sai địa chỉ

File `backend/docker-compose.override.yml` **vẫn còn nguyên**, nội dung không đổi:

```yaml
# TEMPORARY test override — points batteryservice at the natively-run ai-module
# via Docker Desktop's native host.docker.internal (192.168.65.254). ai-module has
# no Dockerfile to build as a container, so it runs on the host for this test.
# Created by connectivity test; deleted afterward. Does NOT touch committed compose/.env.
services:
  batteryservice:
    environment:
      Ai__Enabled: "true"
      Ai__GrpcAddress: "http://host.docker.internal:50051"
      Ai__HttpBaseUrl: "http://host.docker.internal:8000"
      Ai__IntervalMinutes: "1"
      Ai__MinReadings: "30"
```

Ba tiền đề của file đều **đã sai**:
1. *"ai-module has no Dockerfile"* → **đã có** Dockerfile từ `41660e3` (05/08)
2. *"it runs on the host"* → đã kiểm tra bằng `lsof`, host **không có gì** listen ở `:8000` hay `:50051`
3. *"deleted afterward"* → **chưa xoá**, và file **đã được Git theo dõi** (`git ls-files --error-unmatch` trả về đường dẫn)

Docker Compose **tự động nạp** file tên `docker-compose.override.yml`, không cần cờ nào.

**Xác nhận `.env` không đè lên default:** file `backend/.env` chỉ có 2 dòng liên quan AI, cả hai đều rỗng:
```
299:AI_DEEPSEEK_API_KEY=
300:AI_GEMINI_API_KEY=
```
Không có `AI_GRPC_ADDRESS` / `AI_HTTP_BASE_URL` / `AI_ENABLED` → chỉ cần xoá override là các giá trị mặc định trong `docker-compose.yml` có hiệu lực ngay:
```yaml
Ai__GrpcAddress: ${AI_GRPC_ADDRESS:-http://ai-module-grpc:50051}
Ai__HttpBaseUrl: ${AI_HTTP_BASE_URL:-http://ai-module-http:8000}
```

### 1.4. 🔴 Ngữ nghĩa `soc_percent` lệch nhau — sai số âm thầm

Đây là **phát hiện mới**, chưa có trong bản kế hoạch trước.

`protos/ai_service.proto` trên `dev` đã ghi rõ (dòng 41–52):

```
⚠️ soc_percent semantics depend on WHICH ARTIFACT SET scores the request,
   because each set was trained on a different definition:

   pack_config.chemistry = "LFP"  -> LFP artifacts (soc_mode="cycle").
       Send SOC scoped to the DISCHARGE: ~100% at the start of the discharge,
       falling through it (~9% at the end). This is what a real battery SOC
       looks like across one discharge, so BE's own SOC works.

   anything else (NASA/NMC default, soc_mode="window")
       Send WINDOW-LOCAL SOC: ~100% at the FIRST ROW OF THIS WINDOW,
       decreasing across the 30 rows only. Feeding full-discharge SOC here
       is out of the training distribution.

Getting it wrong shifts predicted SOH with no error raised. If unsure for
the non-LFP path, send 4 columns and let the server derive it.
```

**Nhưng BE gửi một kiểu duy nhất cho cả hai chemistry.** `SohPredictionBackgroundService.BuildReadings()`:

```csharp
rows.Add(includeDerived
    ? new[] { (double)r.Voltage, (double)r.Current, (double)r.Temperature,
              seconds, r.CycleCount!.Value, (double)r.SocPercent }   // ← SOC thô từ DB
    : new[] { (double)r.Voltage, (double)r.Current, (double)r.Temperature, seconds });
```

`r.SocPercent` là SOC thật của pin, lấy từ toàn bộ lịch sử sạc/xả — tức **discharge-scoped**.

| Chemistry | Số asset | BE gửi | AI mong đợi | Kết quả |
|---|---|---|---|---|
| LiFePO4 → `"LFP"` | 6 | SOC thật (discharge-scoped) | `soc_mode="cycle"` = discharge-scoped | ✅ **ĐÚNG** |
| Nmc / Nca → `"NMC"` | 4 | SOC thật (discharge-scoped) | `soc_mode="window"` = window-local | ⚠️ **SAI, không báo lỗi** |

*(Số asset lấy từ lần đo 2026-08-05 — hiện chưa truy vấn lại được vì PostgreSQL đang tắt, xem §7.5)*

**Mức nghiêm trọng:** chính comment của BE trong `BuildReadings()` đã đo được độ nhạy của tham số này:

> *"Đo được cùng seed cùng model: 4 cột ra SOH 67.33, 6 cột (cycle=150, SOC=20) ra 40.46 — **lệch 26.87 điểm**."*

Và AI **không validate** `soc_percent` (proto ghi: *"Both are used AS-IS, with no re-derivation and no validation — so a wrong soc_percent is a SILENT failure, not an INVALID_ARGUMENT"*).

→ Xem [B3](#b3--sửa-ngữ-nghĩa-soc_percent-cho-pin-non-lfp) để biết cách sửa.

### 1.5. 🟠 Ba bản proto vẫn lệch nhau

```
Hạng mục                        AI(dev)  BatteryService  TicketService
rpc VerifyTicket                   ✅          ❌              ✅
rpc SubmitFeedback                 ✅          ❌              ❌
PrescribeResponse.cached = 27      ✅          ❌              ❌
HealthResponse.lfp_loaded = 6      ✅          ❌              ❌
HealthResponse.lfp_model_version=7 ✅          ❌              ❌
```

Ngoài ra bản BE còn thiếu **toàn bộ khối comment 20 dòng về ngữ nghĩa `soc_percent`** (§1.4) và ghi sai chú thích `soh_confidence`:
```diff
- double soh_confidence = 2;   // MC Dropout, exp(-soh_std/5) in (0,1]     ← AI (đúng)
+ double soh_confidence = 2;   // MC Dropout uncertainty [0,1]             ← BE (cũ)
```

**Đánh giá tương thích wire:** các thiếu sót đều là *additive* → **không gãy kết nối**, BE chỉ âm thầm bỏ qua field mới. Nhưng mất khả năng:
- Kiểm tra `lfp_loaded` trước khi bơm traffic (quan trọng: 6/10 asset là LFP)
- Biết response đến từ cache (`cached`)
- Gửi feedback qua gRPC (`SubmitFeedback`)
- Đọc được cảnh báo về `soc_percent` (nguyên nhân trực tiếp của lỗi ở §1.4)

### 1.6. ✅ Bản thân AI module chạy tốt — đã gọi thật

| Kiểm thử trên container đang chạy | Kết quả |
|---|---|
| `GET localhost:4015/health` | `200` |
| → `model_version` | `"1.6"` |
| → `scaler_loaded` / `mamba_loaded` / `isolation_forest_loaded` | `true` / `true` / `true` |
| → `lfp_loaded` | **`true`** ✅ |
| → `lfp_model_version` | `"2.2-lfp"` ✅ |
| → `prescription_metrics` | có đủ 7 counter ✅ |
| gRPC `Health` @ `ai-module-grpc:50051` | OK · `lfp_loaded=True` |
| gRPC `Predict` (30×4) | OK · `soh=26.31` |
| gRPC `VerifyTicket` | ❌ **không tồn tại** trong stub |
| gRPC `SubmitFeedback` | ❌ **không tồn tại** trong stub |
| REST `POST /verify-ticket/` | ❌ `HTTP 404` |

`prescription_metrics` đầy đủ:
```json
{
  "prescribe_total": 0,          "enrich_success_rate": 0.0,
  "cache_hit_rate": 0.0,         "blocked_total": 0,
  "budget_exhausted_total": 0,   "fallback_tier_counts": {},
  "llm_budget_remaining": 60
}
```
`prescribe_total: 0` → **chưa có request `/prescribe` nào** kể từ khi container khởi động lại, khớp với việc BatteryService đang crash loop.

### 1.7. ✅ Những gì `dev` đã có thêm (mới so với bản trước)

Commit `3e22ced` (*merge branch 693*) — merge sạch, **không mất gì của `dev`**:
- `src/routers/verify.py`, `src/schemas/verify.py`, `src/services/verify.py` (153 dòng), `tests/test_verify.py` (132 dòng)
- `.dockerignore` (50 dòng) — có comment cảnh báo **không được** ignore `models/weights/` và `models/embeddings/` ✅
- Đã kiểm tra: `models/weights/*lfp*` còn đủ 4 file · `src/services/prescription/observability.py` còn · `PrescribeResponse.cached` còn · `/health` còn đủ field LFP

Commit `f2cad71` (*fix: tem and chemiustry*) — sửa 2 lỗi thật của luồng LFP:

**(a) Dải điện áp per-cell theo chemistry** — `src/core/config.py`:
```python
VOLTAGE_CELL_RANGE = (2.0, 4.5)                        # chung (NMC sạc đầy 4.2 V)
VOLTAGE_CELL_RANGE_BY_CHEMISTRY = { "LFP": (2.0, 3.8) }  # LFP tối đa vật lý 3.65 V
```
> Lý do trong comment: *"pack 8S/24V ở 26.4 V: gửi nhầm `n_series=6` ra 4.40 V/cell vẫn LỌT vì 4.40 < 4.5, dù giá trị đó bất khả thi với LFP."*
>
> ⚠️ Comment cũng nói rõ giới hạn: **chỉ chặn được chiều "chia thiếu"**. Chiều "chia thừa" (`n_series` quá lớn → 2.6–2.9 V) **không chặn được** vì đó là điện áp xả sâu hợp lệ. Cách chắc chắn duy nhất là đối chiếu `evidence.feature_summary.voltage.mean` một lần lúc tích hợp — **LFP phải ra ~3.2–3.3 V**.

**(b) Cụm nhiệt độ train riêng cho LFP**:
```python
TEMPERATURE_TRAIN_CLUSTERS     = (4.0, 24.0, 44.0)   # NASA
LFP_TEMPERATURE_TRAIN_CLUSTERS = (30.0,)             # Severson 2019 — 1 buồng duy nhất
```
> *"Dùng nhầm cụm NASA cho request LFP làm mọi giá trị 26–39 °C bị gắn cờ OOD sai (đo được: 30 °C → khoảng cách 6.0 > ngưỡng 5.0), tức gần như MỌI request từ pin solar ngoài trời đều bị báo 'ngoài phân bố'."*

Đã xác nhận cả hai hằng số **được nối vào** `src/services/inference.py` (dòng 20, 24, 63, 101), không phải khai suông.

**(c) RPC `SubmitFeedback` mới** — mirror của `POST /prescribe/feedback`:
```protobuf
message SubmitFeedbackRequest {
  string prescription_id = 1;        // lấy từ PrescribeResponse.prescription_id
  string status = 2;                 // "accepted" | "edited" | "rejected" → sai giá trị = INVALID_ARGUMENT
  repeated string edited_steps = 3;  // rỗng nếu status != "edited"
  string note = 4;                   // "" nếu không có
}
message SubmitFeedbackResponse { bool success = 1; }  // prescription_id sai → NOT_FOUND
```
Servicer đã implement tại `src/grpc_server.py:373`. Stub `src/grpc_gen/` **đã đồng bộ** với proto (đã verify bằng cách decode serialized descriptor).

**(d) Docs đã cập nhật:**
- `docs/grpc-integration-be.md` — có cả `VerifyTicket` và `SubmitFeedback`
- `docs/be-huong-dan-tich-hop.md` — có `VerifyTicket`

---

## 2. Bốn nguyên nhân gốc

| # | Nguyên nhân | Hệ quả | Sửa ở |
|---|---|---|---|
| **RC-1** | Container hạ tầng (`postgres`/`redis`/`rabbitmq`) tắt lúc Docker Desktop restart, không tự lên lại | BatteryService + TicketService crash loop 38 lần | C1 |
| **RC-2** | Image AI build **trước** merge 693 2 giờ 23 phút, chưa build lại sau khi pull | Container thiếu `VerifyTicket` + `SubmitFeedback` → AI verify hỏng âm thầm | C2 |
| **RC-3** | `docker-compose.override.yml` — file test tạm **đã commit vào Git**, chưa xoá | BatteryService trỏ về host, cả gRPC lẫn HTTP fallback đều fail | B1 |
| **RC-4** | Hợp đồng `soc_percent` phụ thuộc chemistry, nhưng BE gửi một kiểu duy nhất | 4 pin non-LFP nhận SOH sai ~27 điểm, **không có lỗi nào được ném** | B2 + B3 |

---

## 3. Việc phải làm — repo `ai-module`

> **Tin tốt:** phần lớn việc trong bản kế hoạch trước (merge branch 693, regen stub, viết docs, thêm `.dockerignore`) **đã hoàn thành**. Xem [§9](#9-việc-đã-hoàn-thành-từ-bản-kế-hoạch-trước). Chỉ còn lại một việc bắt buộc.

### A1 🔴 Chạy đủ bộ kiểm thử trên `dev` sau merge

**Chưa ai chạy `dev` end-to-end sau khi merge.** Container đang chạy code **cũ hơn `dev` 2 commit**, nên việc nó "chạy tốt" (§1.6) **không chứng minh** `dev` chạy được.

Đặc biệt đáng lo vì `f2cad71` (*"fix: tem and chemiustry"*) sửa vào **đường nóng của inference**: `config.py`, `schemas/predict.py`, `services/inference.py`, `models/anomaly_detector.py`, `grpc_server.py` — 517 dòng thêm, 53 dòng xoá.

```bash
cd /Users/alex/Documents/capstone/ai-module

# Tạo môi trường (nếu chưa có). Máy đã có python3.11 tại ~/.local/bin
make setup-dev
#   nếu `python3.11` không nằm trong PATH:
#   make setup-dev PY311=/Users/alex/.local/bin/python3.11

make lint         # ruff check src/ scripts/ tests/
make test         # pytest tests/ -v --cov=src --cov-report=term  → Quality Gate ≥ 85%
make benchmark    # python scripts/benchmark_grpc.py --real-weights
```

**Test cần soi kỹ nhất** (đều bị `3e22ced` hoặc `f2cad71` chạm vào):

| File test | Thay đổi | Vì sao quan trọng |
|---|---|---|
| `tests/test_grpc_contract.py` | +10 rồi +3 | Enforce proto ↔ stub đồng bộ — nơi dễ vỡ nhất |
| `tests/test_grpc_server.py` | +93 | Enforce parity field-by-field REST ↔ gRPC; phải phủ được `SubmitFeedback` mới |
| `tests/test_verify.py` | mới, 132 dòng | Nếu fail nghĩa là merge làm hỏng verify |
| `tests/test_schemas.py` | +53 | Phủ `VOLTAGE_CELL_RANGE_BY_CHEMISTRY` |
| `tests/test_models.py` | +41 | Phủ `LFP_TEMPERATURE_TRAIN_CLUSTERS` |
| `tests/test_observability.py` | không đổi | **Phải còn tồn tại** — nếu biến mất là dấu hiệu merge sai chiều |
| `tests/test_kb_manifest.py` | không đổi | Validate manifest RAG ↔ `knowledge/` sau khi 2 file `.bin` bị resolve conflict |

**Nếu `make test` FAIL → DỪNG, không rebuild image.** Container hiện tại tuy thiếu verify nhưng ít nhất `Predict`/`Prescribe` vẫn chạy đúng; đẩy một bản hỏng lên còn tệ hơn.

**Về benchmark:** đo hôm 05/08 trên container (Docker Desktop / macOS) cho warm latency `73.88 – 205.20 ms`, vượt SLA P1 `<100ms` khá thường xuyên. Con số `54.1ms avg / 72.4ms p95` trong `docs/ai-be-integration.md` §7 đo trên môi trường khác. **Phải benchmark trên đúng môi trường deploy**, không lấy số máy dev. Nếu không đạt thì mở ticket riêng — **không** chặn việc kết nối lại, vì hiện tại đang là 0 prediction, còn tệ hơn nhiều.

### A2 🟡 Đối chiếu `feature_summary.voltage.mean` một lần cho pin LFP

Không phải sửa code — là một bước **xác minh tích hợp** mà chính comment trong `config.py` yêu cầu:

> *"Chiều 'chia thừa' (`n_series` quá lớn → 2.6-2.9 V) KHÔNG chặn được vì đó là điện áp xả sâu hợp lệ. Cách chắc chắn duy nhất là đối chiếu `evidence.feature_summary.voltage.mean` một lần lúc tích hợp: LFP phải ra ~3.2-3.3 V."*

Sau khi hệ thống chạy lại, lấy 1 response `/predict` của một pin LFP thật và kiểm tra `evidence.feature_summary.voltage.mean`:
- `~3.2–3.3 V` → `n_series` đúng ✅
- `~2.6–2.9 V` → `n_series` **quá lớn**, đang chia thừa ⚠️
- `~4.0–4.4 V` → `n_series` **quá nhỏ** (bản mới sẽ reject, nhưng vẫn nên biết) ⚠️

---

## 4. Việc phải làm — repo `backend`

### C1 🔴 Khởi động lại hạ tầng (làm trước tất cả)

```bash
cd /Users/alex/Documents/capstone/backend
docker compose up -d postgres redis rabbitmq
# đợi healthcheck xanh
docker compose ps postgres redis rabbitmq
```

Chỉ khi 3 container này `healthy` thì `batteryservice`/`ticketservice` mới boot được (`Program.cs` gọi `GetPendingMigrations()` ngay lúc khởi động, không có DB là ném exception).

> ⚠️ Lưu ý có các container `iot-rabbitmq`, `iot-redis`, `tempo-redis` đang chạy — nếu `solar-*` không lên được do **xung đột cổng** thì phải tắt bớt stack khác, hoặc đổi port mapping. Log hiện tại **không cho thấy** xung đột cổng (3 container đều thoát sạch, không lỗi), nhưng đây là thứ cần kiểm tra đầu tiên nếu `up` thất bại.

### C2 🔴 Rebuild image AI từ `dev` hiện tại

```bash
cd /Users/alex/Documents/capstone/backend
docker compose build --no-cache ai-module-grpc ai-module-http
docker compose up -d ai-module-grpc ai-module-http
```

**Chỉ làm sau khi [A1](#a1--chạy-đủ-bộ-kiểm-thử-trên-dev-sau-merge) PASS.**

- `context: ../ai-module` → phải chạy từ thư mục `backend/`, và `ai-module/` phải nằm cạnh nó ✅ (đã đúng)
- Dùng `--no-cache` cho lần này để chắc chắn lớp `COPY . .` được làm lại — build cache có thể còn giữ lớp cũ
- `.dockerignore` đã có, `.venv` sẽ **không** chui vào image ✅

### B1 🔴 Xoá `docker-compose.override.yml`

```bash
cd /Users/alex/Documents/capstone/backend
git rm docker-compose.override.yml
git commit -m "fix: xoa docker-compose.override.yml — file test tam lam BatteryService mat ket noi AI"
docker compose up -d batteryservice
```

**Chỉ cần xoá, không phải sửa gì thêm** — đã kiểm chứng đủ 3 điều kiện ở §1.3.

> ⚠️ **Đừng thay thế bằng cách thêm vào `.gitignore`.** Hai lý do: (a) file đã được Git theo dõi, `.gitignore` không áp dụng cho file đã tracked; (b) quan trọng hơn — Docker Compose vẫn nạp file đó **từ đĩa** bất kể Git nghĩ gì. Bắt buộc `git rm`.

> **Nếu vẫn cần chạy AI native trên host để debug:** đừng dùng lại tên `docker-compose.override.yml`. Đặt tên khác (ví dụ `docker-compose.local-ai.yml`) và gọi tường minh:
> ```bash
> docker compose -f docker-compose.yml -f docker-compose.local-ai.yml up -d batteryservice
> ```
> Cách này không bị nạp ngầm, và nên đưa file đó vào `.gitignore` ngay từ đầu.

### B2 🔴 Đồng bộ 2 bản `Protos/ai_service.proto`

```bash
cd /Users/alex/Documents/capstone
cp ai-module/protos/ai_service.proto \
   backend/services/BatteryService/src/BatteryService.Infrastructure/Protos/ai_service.proto
cp ai-module/protos/ai_service.proto \
   backend/services/TicketService/src/TicketService.Infrastructure/Protos/ai_service.proto

cd backend && dotnet build
```

**Không cần chạy `protoc` tay** — cả hai `.csproj` đã khai (dòng 40 mỗi file):
```xml
<Protobuf Include="Protos\ai_service.proto" GrpcServices="Client" />
```
Grpc.Tools sinh lại C# lúc `dotnet build`, namespace `AiModule.V1`.

**Đây không chỉ là việc dọn dẹp** — nó là điều kiện để làm B3:

| Thứ BE nhận được | Vì sao cần |
|---|---|
| **Khối comment 20 dòng về `soc_percent`** | Chính là tài liệu của lỗi ở §1.4. Không có nó, người sửa B3 không biết phải sửa gì |
| `HealthResponse.lfp_loaded` + `lfp_model_version` | 6/10 asset là LFP → cần kiểm tra AI đã nạp weight LFP chưa **trước** khi bơm traffic |
| `PrescribeResponse.cached` | Biết response từ cache (TTL 10 phút) hay chạy mới — cần khi debug burst event |
| `rpc SubmitFeedback` | Điều kiện để làm B4 |
| Chú thích `soh_confidence` đúng (`exp(-soh_std/5)`) | Bản BE đang ghi `[0,1]` — sai kể từ merge 693 |

> Chép **cùng một file** cho cả hai service dù BatteryService không dùng `VerifyTicket`. `GrpcServices="Client"` chỉ sinh client stub nên không tốn gì, mà một nguồn duy nhất thì dễ bảo trì hơn hai bản cắt gọt khác nhau.

> **Quy tắc từ nay:** mọi thay đổi contract **phải** bắt đầu ở `ai-module/protos/ai_service.proto`, chỉ **thêm** field number mới, rồi mới copy sang BE. Không bao giờ sửa trực tiếp bản trong `backend/`. Đây là rule đã ghi trong [`.claude/rules/tech/ai.md`](../.claude/rules/tech/ai.md) — việc TicketService tự thêm `VerifyTicket` vào bản riêng chính là thứ đã dẫn tới tình trạng lệch hiện nay.

### B3 🔴 Sửa ngữ nghĩa `soc_percent` cho pin non-LFP

Vấn đề đã mô tả ở §1.4. Sửa ở `SohPredictionBackgroundService.BuildReadings()`.

**Ba phương án, theo thứ tự khuyến nghị:**

**Phương án 1 — gửi 4 cột cho non-LFP, 6 cột cho LFP** *(khuyến nghị)*

Chính proto đề xuất: *"If unsure for the non-LFP path, send 4 columns and let the server derive it."*

```
chemistry == "LFP"  → 6 cột, SocPercent thật (đúng soc_mode="cycle")
ngược lại           → 4 cột, để AI tự tính SOC window-local (đúng soc_mode="window")
```
- ✅ Đúng hợp đồng cho **cả hai** artifact set
- ✅ Thay đổi nhỏ, chỉ thêm 1 điều kiện vào `BuildReadings` (cần truyền `packConfig.Chemistry` vào — hiện hàm này `static` và chỉ nhận `window`)
- ⚠️ Đánh đổi: pin non-LFP mất `cycle_count` thật, AI dùng `cycle_count = 0`. Cần cân nhắc — nhưng **có `cycle_count` đúng mà `soc_percent` sai thì tệ hơn** là không có cả hai, vì sai số của `soc_percent` không hề bị phát hiện.

**Phương án 2 — tự quy đổi SOC sang window-local cho non-LFP**

Chuẩn hoá lại SOC trong cửa sổ: `soc_window[i] = 100 × (soc[i] − soc[29]) / (soc[0] − soc[29])`, hoặc dùng Coulomb counting cục bộ giống AI làm.
- ✅ Giữ được `cycle_count` thật cho non-LFP
- ⚠️ Phải khớp **chính xác** công thức của AI (`compute_soc_percent` trong `src/features/extractor.py`) — lệch một chút là lại sai âm thầm. Rủi ro cao hơn phương án 1.

**Phương án 3 — giữ nguyên, chấp nhận sai số**
- ❌ Không khuyến nghị. Sai số ~27 điểm SOH ở ngưỡng EOL 80% là đủ để lật kết luận Healthy ↔ Failed.

> **Trước khi sửa, hãy đo:** chạy `/predict` cùng một cửa sổ non-LFP theo cả hai cách (4 cột vs 6 cột) rồi so `soh_percent`. Nếu chênh lệch nhỏ thì độ ưu tiên hạ xuống; nếu lớn như con số 26.87 điểm mà BE đã đo thì đây là P1 thật sự.

> **Cần AI team xác nhận:** proto nói `soc_mode` là thuộc tính của **bộ artifact**, không phải của request. Nên nếu sau này bộ NASA/NMC được train lại với `soc_mode="cycle"` thì logic này phải đổi theo. Đề nghị AI team expose `soc_mode` trong `HealthResponse` để BE tự phát hiện thay vì hardcode theo chemistry.

### B4 🟠 Chuyển feedback sang gRPC `SubmitFeedback` *(tuỳ chọn)*

Hiện `IAiPrescriptionFeedbackClient` chỉ có đường HTTP (`AiPrescriptionHttpClient.SubmitFeedbackAsync` → `POST /prescribe/feedback`). Comment trong code ghi:

> *"GH-778 — gửi phản hồi kỹ thuật viên về AI. **Chỉ có ở đường HTTP**: `ai_service.proto` không khai RPC nào cho feedback."*

**Nhận định đó nay đã lỗi thời** — `f2cad71` đã thêm `rpc SubmitFeedback`.

**Có nên chuyển không?** Cân nhắc:
- ✅ Nhất quán transport (gRPC primary + HTTP fallback như `Predict`/`Prescribe`)
- ✅ Ánh xạ lỗi rõ hơn: `NOT_FOUND` thay vì phải parse HTTP 404
- ⚠️ Đường HTTP **hiện đang hoạt động đúng**, kể cả phân biệt `NotFound` (không retry) vs `Unavailable` (có retry) — code này đã tốt
- ⚠️ Cần thêm `FallbackAiPrescriptionFeedbackClient` mới nếu muốn giữ pattern fallback

→ **Không gấp.** Làm khi có dịp refactor, hoặc bỏ qua và chỉ cập nhật lại comment cho khỏi hiểu nhầm.

### B5 🟡 Thêm `healthcheck` cho 2 container AI

**Hiện trạng:** hai service AI **không có** khối `healthcheck:`, nên `depends_on` chỉ dùng được `condition: service_started`:
```yaml
ai-module-grpc:  { condition: service_started }
ai-module-http:  { condition: service_started }
```
AI phải nạp torch + tối đa 8 bộ artifact lúc startup → BE có thể gọi trước khi model sẵn sàng.

**Mức nghiêm trọng: thấp.** Không gây chết — BatteryService retry theo `Ai__IntervalMinutes`, hai fallback client đều bắt lỗi trả `null`. Nhưng sinh log rác lúc khởi động cả stack, và làm mờ chẩn đoán khi có sự cố thật.

```yaml
ai-module-http:
  healthcheck:
    test: ["CMD-SHELL", "python -c \"import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)\""]
    interval: 15s
    timeout: 5s
    retries: 10
    start_period: 60s     # đủ cho torch + nạp artifact lần đầu
```
Rồi đổi `depends_on` của `batteryservice` thành `condition: service_healthy`.

> Dùng `python` chứ **không phải `curl`** — image base là `python:3.11-slim`, Dockerfile chỉ `pip install --upgrade pip`, **không** `apt-get install curl`.

> **`ai-module-grpc` khó hơn** — image không có `grpc_health_probe`, và AI module không implement `grpc.health.v1.Health` chuẩn (chỉ có `AiService.Health` riêng). Có thể để `service_started` như hiện tại. **Đừng** thêm dependency mới chỉ vì việc này.

### B6 🟡 LLM API key *(tuỳ chọn — ảnh hưởng chất lượng, không phải kết nối)*

`.env` đang có `AI_DEEPSEEK_API_KEY=` và `AI_GEMINI_API_KEY=` (rỗng).

`SohPredictionBackgroundService` gọi `PrescribeAsync(..., enrich: true, ...)` khi có Alert P1/P2. Không key → AI trả rule-based (`enriched=false`, `llm_provider="none"`) — **vẫn có `action_steps` đầy đủ, không lỗi**.

Ba điểm đã kiểm chứng:
1. **RAG index đã commit sẵn** — `models/embeddings/chroma.sqlite3` (1.4 MB) + 2 collection + `manifest.json`, cùng `knowledge/maintenance/` và `knowledge/safety/`. Chỉ thiếu mỗi API key.
2. **Vòng feedback vẫn hoạt động dù không có LLM.** `orchestrator.py:423-425`: `prescription_id` được ghi khi `enrich=True`, **kể cả khi LLM fallback về rule-based**. Nên `SubmitPrescriptionFeedbackCommand` không bị chết.
3. **Env var AI thực sự đọc:** `DEEPSEEK_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `*_MODEL`, `LLM_PROVIDER_CHAIN`, `SAFETY_LLM_JUDGE`, `LLM_HOURLY_BUDGET` (default 60, đọc ở `observability.py:94`). Compose hiện truyền 2 key đầu — đủ dùng.

---

## 5. Thứ tự thi hành

```
┌─ 1. [hạ tầng] docker compose up -d postgres redis rabbitmq          (C1)
│                └─ đợi cả 3 healthy. ❌ không lên được → DỪNG, xử lý xung đột port
│
├─ 2. [ai-module] make setup-dev && make lint && make test            (A1)
│                └─ ❌ FAIL → DỪNG. Không rebuild image.
│                └─ make benchmark (ghi lại số, không chặn nếu chưa đạt)
│
├─ 3. [backend]  git rm docker-compose.override.yml + commit          (B1)
│
├─ 4. [backend]  cp proto × 2 → dotnet build                          (B2)
│                └─ ❌ build FAIL → DỪNG
│
├─ 5. [deploy]   docker compose build --no-cache ai-module-grpc ai-module-http
│                docker compose up -d ai-module-grpc ai-module-http    (C2)
│
├─ 6. [deploy]   docker compose up -d batteryservice ticketservice
│
├─ 7. [verify]   Chạy toàn bộ checklist §6
│                └─ đặc biệt [4] VerifyTicket và [8] ai_verify_status
│
└─ 8. [backend]  Sửa soc_percent cho non-LFP                          (B3)
                 └─ đo trước/sau bằng /predict trên cùng một cửa sổ
```

**Vì sao thứ tự này:**
- **C1 trước mọi thứ** — không có DB thì BE không boot, không kiểm chứng được gì
- **A1 trước C2** — đừng đẩy code chưa test lên. Container hiện tại tuy thiếu verify nhưng `Predict`/`Prescribe` vẫn đúng
- **B2 trước B3** — phải có comment về `soc_percent` trong proto BE thì người sửa mới hiểu vấn đề
- **B3 sau cùng** — cần hệ thống chạy được để đo trước/sau

### ✅ Nếu cần cứu nhanh, làm tối thiểu

Muốn khôi phục prediction ngay mà chưa kịp làm hết:
```bash
docker compose up -d postgres redis rabbitmq     # C1
git rm docker-compose.override.yml               # B1
docker compose up -d batteryservice
```
- ✅ BatteryService nối lại AI ngay (image cũ vẫn có `Predict`/`Prescribe` + LFP)
- ❌ AI verify của TicketService **vẫn hỏng** cho tới khi rebuild (C2)
- ⚠️ 4 pin non-LFP vẫn nhận SOH lệch do `soc_percent` (B3)

---

## 6. Checklist kiểm chứng

### 6.1. Hạ tầng

```bash
# [0] Ba container hạ tầng phải healthy
docker compose ps postgres redis rabbitmq
docker ps --format "{{.Names}}\t{{.Status}}" | grep -E "batteryservice|ticketservice"
```
❌ Không được còn `Restarting (133)`.

### 6.2. AI module

```bash
# [1] Health đầy đủ
curl -s localhost:4015/health | python3 -m json.tool
```
Phải có **đủ**: `lfp_loaded: true`, `lfp_model_version: "2.2-lfp"`, `prescription_metrics: {...}`
❌ `lfp_loaded: false` → artifact LFP không vào image. Kiểm tra `.dockerignore` có lỡ loại `models/weights/` không.

```bash
# [2] Đủ 6 RPC — ĐÂY LÀ KIỂM TRA QUAN TRỌNG NHẤT
docker exec solar-ai-module-grpc grep -c 'rpc ' /app/protos/ai_service.proto
```
Phải trả **`6`**. Nếu ra `4` nghĩa là image vẫn cũ, C2 chưa có tác dụng.

```bash
# [3] Router REST đủ 4 file
docker exec solar-ai-module-http ls /app/src/routers/
```
Phải có `verify.py`.

```bash
# [4] Gọi thật 2 RPC mới
docker exec solar-ai-module-http python -c "
import grpc
from src.grpc_gen import ai_service_pb2 as pb, ai_service_pb2_grpc as pbg
st = pbg.AiServiceStub(grpc.insecure_channel('ai-module-grpc:50051'))
h = st.Health(pb.HealthRequest(), timeout=10)
print('lfp_loaded =', h.lfp_loaded, '| ver =', h.lfp_model_version)
v = st.VerifyTicket(pb.VerifyTicketRequest(
        title='Pin nong bat thuong',
        description='Pin boc khoi, nhiet do tang cao dot ngot luc 3h sang',
        category=1), timeout=10)
print('VerifyTicket ->', v.verdict, v.score)
try:
    st.SubmitFeedback(pb.SubmitFeedbackRequest(prescription_id='khong-ton-tai', status='accepted'), timeout=10)
    print('SubmitFeedback -> SAI: le ra phai NOT_FOUND')
except grpc.RpcError as e:
    print('SubmitFeedback ->', e.code().name, '(dung neu la NOT_FOUND)')"
```

```bash
# [5] REST verify-ticket
curl -s -X POST localhost:4015/verify-ticket/ -H 'Content-Type: application/json' \
  -d '{"title":"Pin nong","description":"Pin boc khoi nhiet do cao","category":1,"candidates":[]}'
```
Phải trả JSON có `verdict`, **không** phải `404`.

```bash
# [6] LFP đi đúng model — kiểm tra âm tính
#     Tạm đổi tên artifact LFP rồi restart:
#       mv models/weights/soh_mamba_v2.2-lfp.pth models/weights/_tam.pth
#     Request chemistry="LFP" PHẢI trả 500/UNKNOWN với thông điệp
#       "refusing to score LFP data with the NASA/NMC model"
#     Nếu vẫn trả 200 → code LFP chưa vào image.
#     ⚠️ NHỚ ĐỔI TÊN LẠI sau khi test.
```

### 6.3. BatteryService

```bash
# [7] Log sạch
docker logs solar-batteryservice --since 10m 2>&1 | grep -i "AI\|prediction" | tail -20
```
❌ Không được còn: `Error connecting to subchannel` · `falling back to HTTP` · `HTTP AI fallback also failed`

```bash
# [8] BẰNG CHỨNG CỨNG — prediction mới sinh ra
docker exec solar-postgres psql -U postgres -d battery_db \
  -c "SELECT count(*) total, max(predicted_at) newest FROM soh_predictions;"
```
`newest` phải nhảy khỏi mốc cũ **`2026-08-02 07:20:34.601192+00`** (đo ngày 05/08, tổng 7622 dòng). Chờ ít nhất `Ai__IntervalMinutes` sau khi service lên.

```bash
# [9] Đối chiếu voltage.mean cho pin LFP (A2)
#     Lấy 1 response /predict của pin LFP, kiểm tra
#     evidence.feature_summary.voltage.mean  →  phải ~3.2-3.3 V
```

### 6.4. TicketService

```bash
# [10] AI verify đã ra kết quả chưa
docker exec solar-postgres psql -U postgres -d ticket_db \
  -c "SELECT ai_verify_status, count(*) FROM tickets GROUP BY 1 ORDER BY 1;"
```
Phải xuất hiện `2` (Legitimate) và/hoặc `3` (Suspicious). Đo ngày 05/08 chỉ có `1 (Pending) = 14` và `4 (Skipped) = 7`, **không có** `2`/`3` nào.

> ⚠️ **Ticket `Pending` cũ KHÔNG tự chạy lại.** Đã đọc code xác nhận:
> - `TicketVerifyRunner.RunAsync()` return sớm nếu `AiVerifyStatus != Pending`
> - `TicketVerifyOnCreatedConsumer` chỉ consume `TicketCreatedEvent` — tức chỉ khi có ticket **mới**
>
> Xử lý số tồn bằng API re-verify:
> ```
> POST /api/admin/tickets/{id:guid}/re-verify     [Authorize(Roles = "Manager")]
> ```
> **Giới hạn đã kiểm chứng** (`TicketReVerifyCommandHandler`): chỉ nhận ticket có `Origin == TicketOriginEnum.ManualByCustomer` (= 1) **và** status hiện tại là `Skipped` hoặc `Pending`. Handler tự reset về `Pending`, xoá kết quả cũ, rồi gọi `RunAsync` **đồng bộ**.
> → **Ticket `AutoFromAlert` (=2) và `CreatedByStaff` (=3) KHÔNG re-verify được.**

### 6.5. Đối chiếu proto

```bash
cd /Users/alex/Documents/capstone
diff -u ai-module/protos/ai_service.proto \
        backend/services/BatteryService/src/BatteryService.Infrastructure/Protos/ai_service.proto \
  && echo "BatteryService proto: KHỚP"
diff -u ai-module/protos/ai_service.proto \
        backend/services/TicketService/src/TicketService.Infrastructure/Protos/ai_service.proto \
  && echo "TicketService proto: KHỚP"
```
Cả hai **phải** in ra "KHỚP" (diff rỗng).

### 6.6. Bảng tổng kết

| # | Hạng mục | Hiện tại | Sau khi làm |
|---|---|---|---|
| 1 | `postgres`/`redis`/`rabbitmq` | Exited (255) | Up (healthy) |
| 2 | `batteryservice`/`ticketservice` | Restarting (133) ×38 | Up |
| 3 | Số RPC trong container AI | **4** | **6** |
| 4 | `/app/src/routers/verify.py` | không có | có |
| 5 | `POST /verify-ticket/` | HTTP 404 | HTTP 200 |
| 6 | gRPC `VerifyTicket` | UNIMPLEMENTED | trả `verdict` |
| 7 | gRPC `SubmitFeedback` | UNIMPLEMENTED | trả `NOT_FOUND` cho id sai |
| 8 | `/health` → `lfp_loaded` | `true` ✅ | `true` (giữ nguyên) |
| 9 | `docker-compose.override.yml` | còn | đã xoá |
| 10 | `soh_predictions.max(predicted_at)` | `2026-08-02 07:20:34` | thời điểm hiện tại |
| 11 | `tickets.ai_verify_status` | chỉ `1` và `4` | có thêm `2`/`3` |
| 12 | `diff` proto × 2 | khác nhau | rỗng |
| 13 | `soc_percent` cho non-LFP | sai ngữ nghĩa (âm thầm) | đúng theo `soc_mode` |
| 14 | `make test` | **chưa ai chạy trên `dev`** | PASS, coverage ≥ 85% |

---

## 7. Rủi ro, bẫy và giới hạn khảo sát

### 7.1. 🔴 Rebuild rồi vẫn thấy 4 RPC → build cache

`docker compose build` có thể tái dùng lớp `COPY . .` cũ nếu Docker cho rằng context không đổi. Triệu chứng: chạy xong bước C2 nhưng kiểm tra `[2]` vẫn ra `4`.

**Xử lý:** dùng `--no-cache` (đã ghi trong C2). Nếu vẫn vậy, kiểm tra `docker image ls` xem image có được tạo lại không (`CreatedSince`), và chắc chắn `docker compose up -d` đã **tái tạo container** chứ không chỉ khởi động lại cái cũ — thêm `--force-recreate` nếu cần.

### 7.2. 🔴 Sai số `soc_percent` không có triệu chứng

Đây là loại lỗi nguy hiểm nhất trong tài liệu này: **không log, không exception, không metric nào bất thường**. SOH vẫn trả về, confidence vẫn bình thường, chỉ có con số là sai.

Cách duy nhất phát hiện: **so sánh chủ động** — chạy cùng một cửa sổ non-LFP theo cả hai cách (4 cột vs 6 cột) rồi đối chiếu. Đừng chờ nó tự lộ ra.

### 7.3. 🟠 Latency có thể không đạt SLA `<100ms`

Đo ngày 05/08 trên container: warm `73.88 – 205.20 ms`, cold `397.07 ms`; `Prescribe` rule-path `49.51 ms`. Theo [`.claude/rules/tech/ai.md`](../.claude/rules/tech/ai.md), `<100ms` là điều kiện merge AI module.

Cần benchmark trên **môi trường deploy thật** (Linux server), không lấy số Docker Desktop/macOS. Nếu không đạt → ticket riêng, **không chặn** việc kết nối lại.

### 7.4. 🟡 Bẫy nhỏ khác

| Bẫy | Chi tiết |
|---|---|
| **Thêm vào `.gitignore` thay vì `git rm`** | Không có tác dụng — file đã tracked, và Compose vẫn nạp từ đĩa. §B1 |
| **Python 3.11 bắt buộc** | `torch 2.3.1` không hỗ trợ 3.12+. `python3` mặc định trên máy là **3.14.5** (sẽ hỏng). Nhưng `python3.11` **CÓ sẵn** tại `/Users/alex/.local/bin/python3.11` → không cần cài. Nếu không trong `PATH`: `make setup-dev PY311=/Users/alex/.local/bin/python3.11` |
| **`grpcio` và `grpcio-tools` phải cùng version** | Đang pin `1.81.1` cả hai (`requirements.txt:31-32`), có comment: *"protobuf runtime phải khớp version codegen của grpcio-tools"* |
| **Build context trỏ ra ngoài repo** | `context: ../ai-module` — phải chạy `docker compose build` từ thư mục `backend/` |
| **Xung đột port với stack IoT** | Đang có `iot-rabbitmq`, `iot-redis`, `tempo-redis` chạy song song. Nếu `solar-*` không lên được, kiểm tra port trước tiên |
| **`make benchmark` cần gRPC server đang chạy** | `scripts/benchmark_grpc.py --real-weights` — bật `make grpc` ở terminal khác trước |
| **Thư mục rỗng thừa** | `ai-module/ai-module/` — vô hại, nên dọn |

### 7.5. ⚠️ Giới hạn khảo sát — những gì CHƯA kiểm chứng được

Ghi rõ để không ai hiểu nhầm là đã xong:

| Hạng mục | Vì sao chưa kiểm chứng |
|---|---|
| **Số liệu DB hiện tại** | `solar-postgres` đang **Exited (255)** → không truy vấn được. Mọi con số DB trong tài liệu này (7622 prediction · mốc `2026-08-02 07:20:34` · 14 Pending / 7 Skipped · 6 LFP + 3 NMC + 1 NCA · 120765/120776 reading có `cycle_count`) là **đo ngày 2026-08-05**, cần đo lại sau C1 |
| **`dev` có boot được không** | Máy chưa có `.venv`; container chạy code cũ hơn `dev` 2 commit. **Chưa ai chạy `dev` end-to-end** → A1 là bắt buộc |
| **`make test` trên `dev`** | Cùng lý do trên |
| **Artifact LFP nạp được thật không** | Không đọc được nội dung `.pkl`/`.pth` khi thiếu `torch`/`sklearn`. Chỉ xác minh được tên file khớp config + kích thước hợp lý. *(Nhưng container đang chạy báo `lfp_loaded: true` — bằng chứng gián tiếp rất mạnh là bộ artifact hợp lệ)* |
| **Mức sai số thật của `soc_percent`** | Con số 26.87 điểm là BE tự đo (ghi trong comment), điều kiện khác với luồng non-LFP. Cần đo lại đúng ngữ cảnh trước khi chốt độ ưu tiên B3 |
| **Luồng verify end-to-end** | Ticket mới nhất từ `2026-08-01`; không tạo ticket mới vì đó là ghi dữ liệu vào hệ thống đang chạy |
| **Vì sao hạ tầng exit 255** | Log không có lỗi fatal. Suy đoán mạnh nhất là Docker Desktop restart, nhưng **chưa xác nhận** được |
| **Độ chính xác model LFP** | Ngoài phạm vi — thuộc GH-67 |

### 7.6. 📌 Việc chưa có người phụ trách

| Việc | Cần ai quyết |
|---|---|
| Chọn phương án B3 (1, 2 hay 3) | AI team + BE team cùng chốt |
| Có expose `soc_mode` trong `HealthResponse` không | AI team |
| Có chuyển feedback sang gRPC không (B4) | BE team |
| Ngưỡng SLA latency trên môi trường deploy thật | Leader |

---

## 8. Những phần đã đúng — không được đụng vào

Đã đối chiếu từng dòng giữa hai repo. Các hạng mục sau **khớp chính xác**; sửa vào chỉ làm hỏng:

| # | Hạng mục | Bằng chứng |
|---|---|---|
| 1 | REST path `/predict/`, `/prescribe/`, `/prescribe/feedback` | Khớp router AI từng ký tự, **kể cả dấu `/` cuối**. `AiPrescriptionHttpClient` có comment nhấn mạnh |
| 2 | `WINDOW_SIZE = 30` | Hardcode hai phía. BE để `AiOptions.WindowSize` là `const` (không cấu hình được) và validate `MinReadings >= 30` **lúc khởi động** để cấu hình sai làm service không lên, thay vì lên rồi câm lặng |
| 3 | Quy tắc 4 cột / 6 cột "tất cả hoặc không" | `BuildReadings()` khớp đúng `validate_readings_shape()`. *(Riêng **giá trị** `soc_percent` thì sai — §1.4. Còn **cấu trúc** thì đúng.)* |
| 4 | Cột `time` = giây tương đối từ đầu window | BE dựng row **sau khi** chốt window để `time` bắt đầu từ 0 — đúng hợp đồng, có comment giải thích |
| 5 | `pack_config` | `n_series = round(nominal_voltage / cell_nominal)`; `LiFePO4→"LFP"`, `Nmc/Nca/Lco→"NMC"`, `Other→null`; truyền `capacity_ah` |
| 6 | `risk.priority` là tín hiệu Urgency | BE **không** gán thẳng làm Priority ticket — đúng Priority Policy (Impact × Urgency) |
| 7 | Phân biệt `404` vs `Unavailable` khi feedback | `AiFeedbackOutcome.NotFound` (không retry) vs `Unavailable` (có retry) — xử lý rất đúng |
| 8 | gRPC `:8081` của BatteryService | Kestrel bind listener HTTP/2 riêng cho `BatteryInternal`; compose `expose: "8081"`; `TicketAi__BatteryGrpcAddress` trỏ đúng |
| 9 | Stub `src/grpc_gen/` của AI | Đồng bộ đúng với proto — verify bằng decode serialized descriptor (`SubmitFeedback`/`VerifyTicket`/`cached`/`lfp_loaded` đều có) |
| 10 | Luồng auto-ticket | `AlertTicketSagaStateMachine` subscribe cả V1 và V2; `BatteryAnomalyDetectedV2Event` mang sẵn `AiPrescription` + `AiActionSteps` (nullable, đặt **cuối** constructor để backward-compat) |
| 11 | API Gateway **không** route AI | Đúng thiết kế — AI chỉ nội bộ `solar-net`, insecure/no-TLS, không expose `50051` ra host |
| 12 | Fail-safe của `AiOptions.Enabled` | Default `false` — local/non-docker không có ai-module thì job no-op, threshold rule vẫn chạy |
| 13 | `.dockerignore` mới thêm | Có comment cảnh báo **không được** ignore `models/weights/` và `models/embeddings/`, và loại đúng `.venv/` (thủ phạm ~2GB) |
| 14 | `TicketAi__*` của TicketService | Trỏ đúng `ai-module-grpc:50051` — **không** bị override làm hỏng như BatteryService |

---

## 9. Việc đã hoàn thành từ bản kế hoạch trước

Ghi lại để tránh làm trùng:

| Mã cũ | Việc | Trạng thái | Bằng chứng |
|---|---|---|---|
| A1 | Merge `feat/GH-693-verify-ticket` → `dev` | ✅ **Xong** | Commit `3e22ced` (05/08 14:13) |
| A2 | `make proto` — regen gRPC stub | ✅ **Xong** | Stub chứa `VerifyTicket` + `SubmitFeedback`, decode descriptor xác nhận |
| A4 | LFP artifacts | ✅ Đã có sẵn | 4 file trong `models/weights/`; container báo `lfp_loaded: true` |
| A5 | Viết docs cho `VerifyTicket` | ✅ **Xong** | `docs/grpc-integration-be.md` + `docs/be-huong-dan-tich-hop.md` |
| A6 | Thêm `.dockerignore` | ✅ **Xong** | 50 dòng, có cảnh báo bảo vệ `models/` |
| — | Thêm RPC `SubmitFeedback` | ✅ **Mới, ngoài kế hoạch** | Commit `f2cad71` |
| — | Dải điện áp per-cell theo chemistry | ✅ **Mới, ngoài kế hoạch** | `VOLTAGE_CELL_RANGE_BY_CHEMISTRY` |
| — | Cụm nhiệt độ train riêng cho LFP | ✅ **Mới, ngoài kế hoạch** | `LFP_TEMPERATURE_TRAIN_CLUSTERS = (30.0,)` |
| B1 | Xoá `docker-compose.override.yml` | ❌ **Chưa làm** | File vẫn còn, vẫn tracked |
| B2 | Đồng bộ proto | ❌ **Chưa làm** | Cả 2 bản BE vẫn thiếu 5 hạng mục |
| B3 | Healthcheck cho container AI | ❌ Chưa làm | → nay là B5 |
| B4 | LLM API key | ❌ Chưa làm | → nay là B6 |

**Đánh giá:** phía `ai-module` đã làm rất tốt và còn vượt kế hoạch. Toàn bộ phần còn nợ nằm ở **phía `backend`** và **khâu deploy** (rebuild image).

---

## Phụ lục A — Đối chiếu 3 bản proto

| Thành phần | `ai-module/protos/` (dev `f2cad71`) | `BatteryService/Protos/` | `TicketService/Protos/` |
|---|:---:|:---:|:---:|
| `rpc Predict` | ✅ | ✅ | ✅ |
| `rpc Prescribe` | ✅ | ✅ | ✅ |
| `rpc Health` | ✅ | ✅ | ✅ |
| `rpc PredictStream` | ✅ | ✅ | ✅ |
| `rpc VerifyTicket` | ✅ | ❌ | ✅ |
| `rpc SubmitFeedback` | ✅ | ❌ | ❌ |
| `PrescribeResponse.cached = 27` | ✅ | ❌ | ❌ |
| `HealthResponse.lfp_loaded = 6` | ✅ | ❌ | ❌ |
| `HealthResponse.lfp_model_version = 7` | ✅ | ❌ | ❌ |
| Comment ngữ nghĩa `soc_percent` (20 dòng) | ✅ | ❌ | ❌ |
| Chú thích `soh_confidence` | `exp(-soh_std/5) in (0,1]` | `[0,1]` (cũ) | `[0,1]` (cũ) |
| `message SubmitFeedbackRequest/Response` | ✅ | ❌ | ❌ |
| `message VerifyTicketRequest/Response` | ✅ | ❌ | ✅ |
| `message TicketSensorSnapshot` | ✅ | ❌ | ✅ |
| `message DuplicateCandidate` | ✅ | ❌ | ✅ |

**Tương thích wire:** hai bản BE chỉ **thiếu field additive** → không gãy kết nối, BE âm thầm bỏ qua field mới. Nhưng mất khả năng kiểm tra LFP readiness, đọc `cached`, gọi `SubmitFeedback`, và **đọc được cảnh báo về `soc_percent`**.

**Sau khi làm B2:** cả 3 cột phải ✅ ở mọi dòng, hai lệnh `diff` ở §6.5 phải rỗng.

---

## Phụ lục B — Đối chiếu container đang chạy vs `dev`

| Thành phần | Container (image `41660e3`, build 05/08 11:50) | Repo `dev` (`f2cad71`) |
|---|---|---|
| Số RPC gRPC | **4** | **6** |
| `rpc VerifyTicket` | ❌ | ✅ |
| `rpc SubmitFeedback` | ❌ | ✅ |
| `POST /verify-ticket/` | ❌ HTTP 404 | ✅ |
| `src/routers/verify.py` | ❌ | ✅ |
| `src/services/verify.py` (153 dòng) | ❌ | ✅ |
| `src/schemas/verify.py` (43 dòng) | ❌ | ✅ |
| `tests/test_verify.py` (132 dòng) | ❌ | ✅ |
| Artifact LFP (4 file) | ✅ | ✅ |
| `/health` → `lfp_loaded`, `lfp_model_version` | ✅ | ✅ |
| `/health` → `prescription_metrics` | ✅ | ✅ |
| `PrescribeResponse.cached` | ✅ | ✅ |
| `VOLTAGE_CELL_RANGE_BY_CHEMISTRY` | ❌ | ✅ |
| `LFP_TEMPERATURE_TRAIN_CLUSTERS` | ❌ | ✅ |
| `.dockerignore` | ❌ | ✅ |
| Công thức `soh_confidence` | `exp(-std/5)` | `exp(-std/5)` |

**Kết luận:** container đi sau `dev` **2 commit** (`3e22ced` + `f2cad71`). Sau C2 thì cột trái phải giống hệt cột phải.

---

## Phụ lục C — Lệnh thu thập bằng chứng

Ghi lại để tái lập / kiểm chứng độc lập:

```bash
# ── Trạng thái container ──────────────────────────────────────────────
docker ps -a --format "{{.Names}}\t{{.Status}}"
docker inspect solar-batteryservice --format '{{.State.ExitCode}} restarts={{.RestartCount}}'
docker inspect solar-ai-module-grpc --format 'container created={{.Created}}'
docker image inspect backend-ai-module-grpc:latest --format 'image created={{.Created}}'
docker inspect solar-batteryservice --format '{{range .Config.Env}}{{println .}}{{end}}' | grep "^Ai__"
docker inspect solar-ticketservice  --format '{{range .Config.Env}}{{println .}}{{end}}' | grep "TicketAi__"

# ── Vì sao BE crash ───────────────────────────────────────────────────
docker logs solar-ticketservice --tail 30 2>&1 | tail -30
docker logs solar-postgres --tail 8 2>&1 | tail -8

# ── Code thực sự bên trong container ──────────────────────────────────
docker exec solar-ai-module-grpc grep -n 'rpc ' /app/protos/ai_service.proto
docker exec solar-ai-module-http ls /app/src/routers/
docker exec solar-ai-module-grpc grep -c 'VOLTAGE_CELL_RANGE_BY_CHEMISTRY' /app/src/core/config.py

# ── Gọi thật AI ───────────────────────────────────────────────────────
curl -s localhost:4015/health | python3 -m json.tool
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST localhost:4015/verify-ticket/ \
  -H 'Content-Type: application/json' -d '{"title":"t","description":"d","category":1,"candidates":[]}'

docker exec solar-ai-module-http python -c "
import grpc
from src.grpc_gen import ai_service_pb2 as pb, ai_service_pb2_grpc as pbg
st = pbg.AiServiceStub(grpc.insecure_channel('ai-module-grpc:50051'))
print(st.Health(pb.HealthRequest(), timeout=10))"

# ── Probe RPC chưa biết có tồn tại không (raw, không cần stub) ─────────
docker exec solar-ai-module-http python -c "
import grpc
ch = grpc.insecure_channel('ai-module-grpc:50051')
call = ch.unary_unary('/aimodule.v1.AiService/VerifyTicket',
                      request_serializer=lambda x: x, response_deserializer=lambda x: x)
try:    call(b'', timeout=10); print('implemented')
except grpc.RpcError as e: print(e.code().name, e.details())"

# ── Kiểm tra stub có đồng bộ proto không ──────────────────────────────
python3 -c "
import re
src=open('src/grpc_gen/ai_service_pb2.py').read()
blob=eval(re.search(r\"AddSerializedFile\((b'.*?')\)\", src, re.S).group(1))
for k in [b'SubmitFeedback',b'VerifyTicket',b'cached',b'lfp_loaded']:
    print(k.decode(),'->',k in blob)"

# ── Truy vết Git ──────────────────────────────────────────────────────
git reflog -8
git show -s --format="%ci %s" 3e22ced
git show -s --format="%ci %s" f2cad71
git show --stat 3e22ced | head -30
git show f2cad71 -- src/core/config.py src/schemas/predict.py

# ── Đối chiếu proto ───────────────────────────────────────────────────
cd /Users/alex/Documents/capstone
diff -u ai-module/protos/ai_service.proto \
        backend/services/BatteryService/src/BatteryService.Infrastructure/Protos/ai_service.proto
diff -u ai-module/protos/ai_service.proto \
        backend/services/TicketService/src/TicketService.Infrastructure/Protos/ai_service.proto

# ── Bằng chứng DB (cần postgres đang chạy) ────────────────────────────
docker exec solar-postgres psql -U postgres -lqt | cut -d'|' -f1
docker exec solar-postgres psql -U postgres -d battery_db \
  -c "SELECT count(*), max(predicted_at) FROM soh_predictions;"
docker exec solar-postgres psql -U postgres -d battery_db \
  -c "SELECT bt.chemistry, count(a.id) FROM battery_assets a
      JOIN battery_types bt ON bt.id=a.battery_type_id GROUP BY 1;"
docker exec solar-postgres psql -U postgres -d ticket_db \
  -c "SELECT ai_verify_status, count(*) FROM tickets GROUP BY 1;"

# ── File override có bị Git theo dõi không ────────────────────────────
cd backend && git ls-files --error-unmatch docker-compose.override.yml
```

---

## Ghi chú cuối

Tài liệu này mô tả hiện trạng tại **2026-08-06**, và **chưa có thay đổi code hay cấu hình nào được thực hiện**. Toàn bộ khảo sát là read-only: đọc file, gọi API, đọc log, truy vết Git.

Bản trước (2026-08-05) đã lỗi thời hoàn toàn sau khi `dev` merge branch 693 — **tài liệu loại này hết hạn rất nhanh**. Sau khi thi hành xong §5 và §6, hãy cập nhật lại file này hoặc đóng nó lại và ghi kết quả vào `logs/GH-xxx/`, để lần sau không ai đọc nhầm hiện trạng cũ thành hiện trạng mới.
