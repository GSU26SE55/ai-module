# Hướng dẫn tích hợp cho BE — Gửi gì cho AI, nhận lại gì

> **Đối tượng:** BE dev (.NET) lần đầu nối vào AI module.
> **Cập nhật:** 2026-07-31 — sau GH-67 Mức 2 (chemistry-aware artifact selection).
>
> Tài liệu này giải thích **nguyên lý**: gửi cái gì, vì sao phải gửi thế, và đọc kết quả ra sao.
> Hai tài liệu còn lại đi sâu vào chi tiết và **không lặp lại ở đây**:
> - `docs/grpc-integration-be.md` — cơ chế gRPC (gen client C#, streaming, mã lỗi, benchmark)
> - `docs/ai-be-integration.md` — luồng `BatteryAnomalyDetectedEvent` → ticket tự động, cách map sang Priority

---

## 1. Mô hình tư duy: AI biết gì và KHÔNG biết gì

AI module là một hàm **thuần, không trạng thái**: đưa vào 30 điểm đo liên tiếp của **một** viên pin,
trả ra tình trạng sức khoẻ + khuyến nghị bảo trì.

| AI **biết** | AI **KHÔNG biết** |
|---|---|
| Dạng sóng điện áp/dòng/nhiệt trong 30 bước bạn gửi | Pin này thuộc Site nào, khách hàng nào |
| SOH %, giai đoạn sức khoẻ, mức bất thường | `ImpactScope` (Site / SingleAsset / MultiSite) |
| Hành động bảo trì nên làm, PPE, bước LOTO | Ticket đang mở hay đã đóng, SLA còn bao lâu |

→ Hệ quả quan trọng: **`risk.priority` của AI KHÔNG phải Priority của ticket.** Nó chỉ là tín hiệu
*urgency kỹ thuật*. Priority thật = ma trận Impact × Urgency, do BE tính lúc Manager triage.
Chi tiết ở `docs/ai-be-integration.md` §4.

**Gọi RPC nào?** Chỉ cần **`Prescribe`** cho mọi use-case tạo/enrich ticket. `Prescribe` chạy
`Predict` bên trong và trả kèm đủ `prediction`/`anomaly`/`risk`. Đừng gọi cả hai trên cùng một
window — mỗi lần gọi chạy MC Dropout độc lập nên 2 response có thể lệch nhau gần ngưỡng.

---

## 2. Gửi cái gì — cấu trúc `readings`

Một request = **đúng 30 dòng**, mỗi dòng là một thời điểm đo. Sai số dòng → `INVALID_ARGUMENT`.

### Dạng 6 cột — **BE luôn dùng dạng này**

```
[ voltage, current, temperature, time, cycle_count, soc_percent ]
```

| Cột | Đơn vị | Ý nghĩa | Ghi chú |
|-----|--------|---------|---------|
| `voltage` | V | Điện áp **đo được** (của pack nếu là pack) | Kèm `pack_config.n_series` để AI chia ra per-cell |
| `current` | A | Dòng điện. **Âm = đang xả** | Kèm `pack_config.capacity_ah` để AI quy về C-rate |
| `temperature` | °C | Nhiệt độ pin | |
| `time` | **giây** | Thời gian trôi trong chu kỳ, bắt đầu từ 0 | KHÔNG phải timestamp tuyệt đối |
| `cycle_count` | số | Số chu kỳ sạc/xả pin đã trải qua | **Hằng số** trên cả 30 dòng |
| `soc_percent` | 0–100 | **SOC thật** của pin tại thời điểm đó | Từ lịch sử đầy đủ mà BE có |

### Vì sao BẮT BUỘC 6 cột (không phải 4)

`cycle_count` và `soc_percent` là hai kênh đầu vào của model. Nếu BE không gửi, AI phải tự ước
lượng **chỉ từ 30 điểm** trong tay — và ước lượng đó *khác hẳn* cái model học lúc train.

Cụ thể với `soc_percent`: model LFP được train với SOC trải suốt cả chu kỳ xả (~100% → ~9%).
Nếu tự tính từ 30 điểm, AI chỉ ra được "đã rút bao nhiêu điện *trong 30 bước này*" — luôn bắt đầu
từ 100%, gần như hằng số. Model chưa bao giờ thấy dữ liệu như vậy.

→ Vì thế **payload thiếu cột với pin LFP sẽ bị từ chối**, kèm thông báo:

```
LFP artifacts were trained with soc_mode='cycle' (soc spans the full discharge),
but this payload has 4 columns so soc_percent has to be estimated window-locally —
which the model never saw. Send the 6-column payload ... with the battery's real SOC.
```

Đây là chủ ý: thà báo lỗi còn hơn trả về con số sai mà không ai biết.

---

## 3. `pack_config` — khai báo pin của bạn là loại gì

Model gốc được train trên **cell đơn 18650 NMC 2.0 Ah** (dataset NASA). Pin thật của dự án là
**pack LFP 8S 24V 30Ah** (pin thật của dự án). `pack_config` là cầu nối giữa hai thứ đó.

```protobuf
PackConfig {
  int32  n_series    = 1;   // số cell nối tiếp — pin dự án là 8 (24V / 3.2V)
  string chemistry   = 2;   // "LFP" | "NMC" | bỏ trống
  double capacity_ah = 3;   // dung lượng thật của pack — pin dự án là 30.0 (Ah)
                            // ⚠️ Ah càng lớn thì trần dòng càng thấp: AI quy dòng về
                            // C-rate (current × cell_danh_dinh / capacity_ah) rồi chặn ở ±5.
                            // cell_danh_dinh phụ thuộc chemistry: LFP 1.1 Ah · NASA 2.0 Ah.
                            // Với 30 Ah + chemistry="LFP" ⇒ trần = 5 × 30/1.1 = 136 A.
                            // KHÔNG khai chemistry ⇒ trần chỉ 75 A (5 × 30/2.0).
                            // Tải vượt trần bị 422 / INVALID_ARGUMENT, không có prediction.
}
```

Mỗi field làm một việc **khác nhau**, không thay thế nhau được:

| Field | AI làm gì với nó | Không gửi thì sao |
|-------|------------------|-------------------|
| `n_series` | Chia `voltage` ra per-cell **trước** mọi xử lý | Pack 25.6V bị coi là cell 25.6V → **reject 422** vì ngoài khoảng [2.0, 4.5] V |
| `capacity_ah` | Quy `current` về C-rate tương đương cell 2 Ah | Dòng lớn của pack bị reject, hoặc bắn cảnh báo quá dòng giả |
| `chemistry` | Chọn **ngưỡng cảnh báo điện áp** + **bộ model** | Dùng ngưỡng NMC cho pin LFP → cảnh báo giả liên tục, và **bỏ sót sạc quá áp thật** |

### `chemistry` quan trọng đến mức nào — số đo thật

Cùng một payload pack LFP 8S, chỉ khác `chemistry`:

```
khong co chemistry   -> model 1.6      SOH = 87.72%   Degrading
chemistry = "LFP"    -> model 2.0-lfp  SOH = 100.00%  Healthy
```

Lệch **12 điểm SOH** và khác hẳn kết luận. Gửi thiếu `chemistry` không báo lỗi — nó chỉ **âm thầm
trả kết quả của model sai**. Đây là lỗi tốn kém nhất có thể mắc khi tích hợp.

> LFP xả quanh 3.0–3.3 V/cell, sạc đầy 3.65 V/cell. NMC xả quanh 3.2–4.15 V, sạc đầy 4.2 V.
> Dùng nhầm profile thì ngưỡng cảnh báo lệch cả hai đầu.

---

## 4. Ví dụ payload (C#)

```csharp
var request = new PrescribeRequest
{
    BatteryId = "PACK-A1",
    Enrich    = false,                      // luồng auto-ticket: rule-based, nhanh
    PackConfig = new PackConfig
    {
        NSeries    = 4,
        Chemistry  = "LFP",
        CapacityAh = 2.5,
    },
};

// 30 dòng, mỗi dòng 6 số — THỨ TỰ CỘT KHÔNG ĐƯỢC SAI
foreach (var s in last30Samples)
{
    var r = new Reading();
    r.Values.AddRange(new[]
    {
        s.PackVoltage,      // V   — điện áp pack, AI tự chia cho NSeries
        s.Current,          // A   — âm khi xả
        s.Temperature,      // °C
        s.SecondsInCycle,   // s   — tính từ đầu chu kỳ, KHÔNG phải unix timestamp
        s.CycleCount,       // giống nhau ở cả 30 dòng
        s.SocPercent,       // 0-100, SOC thật
    });
    request.Readings.Add(r);
}

var res = await client.PrescribeAsync(request);
```

> Nếu sợ nhầm thứ tự cột, dùng `reading_objects` (`ReadingFields`) — cùng dữ liệu nhưng đặt tên
> field rõ ràng nên không thể đảo nhầm. Gửi cả hai thì `reading_objects` thắng.

---

## 5. Nhận lại gì — đọc `PrescribeResponse`

### Quyết định có tạo ticket hay không: dùng `risk.action_code`

```
MONITOR                  -> KHONG tao ticket
SCHEDULE_MAINTENANCE     -> tao ticket
SCHEDULE_REPLACEMENT     -> tao ticket
REPLACE_IMMEDIATELY      -> tao ticket
```

⚠️ **Đừng gate theo `anomaly.anomaly_status`.** Nó chỉ đo "dạng sóng cảm biến có bất thường
không", độc lập với mức nghiêm trọng SOH. Một viên pin xuống cấp đều đặn tới End-Of-Life vẫn cho
`anomaly_status = "Normal"` trong khi `action_code = "REPLACE_IMMEDIATELY"`.

### Các field dùng để dựng ticket

| Field | Dùng làm gì |
|-------|-------------|
| `action_steps[]` | Nội dung maintenance log ban đầu |
| `ppe_required[]` | Cảnh báo an toàn hiển thị trên ticket |
| `safety_warnings[]` | Cảnh báo bổ sung |
| `human_verification_required` | Ticket phải có kỹ thuật viên xác nhận trước khi đóng |
| `prediction.soh_percent`, `prediction.health_stage` | Ngữ cảnh SOH lưu vào mô tả ticket |
| `risk.risk_level` | Mức nghiêm trọng hiển thị |
| `risk.priority` | **Chỉ là gợi ý urgency** — xem §1 |

### Khi kết quả "chưa chắc chắn"

`prediction.is_borderline = true` nghĩa là các mẫu MC Dropout không đồng thuận về giai đoạn sức
khoẻ (rơi gần ngưỡng 80/85/90). Nên hiển thị "kết quả chưa chắc chắn" thay vì coi `health_stage`
là nhãn chắc nịch.

### `enrich` — khi nào bật

| | `enrich=false` (mặc định) | `enrich=true` |
|---|---|---|
| Cách chạy | Rule-based, không gọi mạng | RAG + LLM |
| Thời gian | ~60–75ms | Vài giây |
| Dùng cho | **Luồng auto-ticket** | Nút "AI gợi ý chi tiết" cho kỹ thuật viên bấm tay |

---

## 6. Setup

```bash
# AI module — chạy gRPC
python -m src.grpc_server          # mặc định port 50051, đổi bằng env GRPC_PORT
```

BE lấy `protos/ai_service.proto` từ repo `ai-module`, gen client C# (chi tiết ở
`docs/grpc-integration-be.md` §1), rồi:

```csharp
// Channel tạo 1 lần, đăng ký DI singleton — KHÔNG tạo mới mỗi request
var channel = GrpcChannel.ForAddress("http://ai-module:50051");
var client  = new AiService.AiServiceClient(channel);
```

gRPC ở đây **không có TLS/auth** — chỉ dùng trong docker network nội bộ, **không expose port 50051
ra ngoài**.

### Kiểm tra trước khi bơm traffic

```csharp
var h = await client.HealthAsync(new HealthRequest());
// status="ok"  model_version="1.6"        <- bo NASA/NMC
// lfp_loaded=true  lfp_model_version="2.0-lfp"   <- bo LFP
```

**Nếu `lfp_loaded = false` mà bạn định gửi `chemistry="LFP"` → mọi request sẽ lỗi.** Bộ LFP là
tuỳ chọn khi deploy: thiếu nó server vẫn khởi động bình thường (để deploy chỉ-NASA vẫn chạy được),
nhưng request LFP sẽ fail thay vì bị chấm điểm sai. Kiểm tra field này trước.

### Độ trễ (đo 2026-07-31, weight thật, máy dev CPU)

| Bộ artifact | avg | p95 |
|---|---|---|
| NASA (`chemistry` bỏ trống) | 51.0 ms | 64.0 ms |
| LFP (`chemistry="LFP"`) | 58.7 ms | 73.4 ms |

Đều dưới SLA P1 (<100ms). Máy deploy có thể khác — chạy `python scripts/benchmark_grpc.py
--real-weights` trên môi trường thật để xác nhận.

---

## 7. Những chỗ dễ vấp (đã đo, không phải suy đoán)

**a) Quên `pack_config` khi gửi điện áp pack** → reject ngay, nhưng thông báo chỉ rõ cách sửa:

> *"per-cell value 25.600 V outside allowed range [2.0, 4.5] V — if this is a multi-cell pack
> (e.g. 25.6V ~ 8S LFP), send pack_config.n_series"*

**b) `evidence.feature_summary` là giá trị PER-CELL, không phải cái bạn gửi lên.** Nó đã bị chia
cho `n_series` và quy C-rate rồi. Đừng hiểu nhầm là echo lại input.

**c) Một số lỗi input đang trả `INTERNAL` thay vì `INVALID_ARGUMENT`.** Ví dụ payload thiếu cột
với pin LFP:

```
code = INTERNAL
detail = inference failed: LFP artifacts were trained with soc_mode='cycle'...
```

Về contract thì đây phải là `INVALID_ARGUMENT` (lỗi của client, client sửa được). Đây là lệch
đã biết, **chưa sửa** vì đổi mã lỗi ảnh hưởng cách BE bắt exception. **Trước mắt: đừng chỉ dựa vào
status code — đọc thêm `details` để phân biệt lỗi payload với lỗi server thật.**

**d) `PrescribeResponse` không có `metadata`.** Nghĩa là qua đường `Prescribe`, BE **không biết**
call vừa rồi dùng bộ NASA hay LFP. Chỉ `Predict` mới có `metadata.model_version`/`chemistry`.
Nếu cần audit, tạm thời đối chiếu bằng `Health` (`lfp_loaded`) + chính `pack_config` mình gửi.

**e) `cycle_count` lớn trên đường NASA sẽ bị kẹp.** Bộ NASA chuẩn hoá theo mốc 200 chu kỳ, bộ LFP
theo 2300. Gửi `cycle_count=900` mà không có `chemistry="LFP"` sẽ thấy log cảnh báo và giá trị bị
kẹp về 1.0 — thêm một lý do nữa để luôn gửi `chemistry`.

**f) Gọi lại y hệt trong thời gian ngắn sẽ trả cache.** Response có `cached=true`. Khoá cache gồm
cả `pack_config`, nên đổi `chemistry`/`n_series`/`capacity_ah` là chạy tính lại, không dùng lại
kết quả cũ.

---

## 8. Checklist trước khi nối thật

- [ ] `Health` trả `status="ok"` **và** `lfp_loaded=true` (nếu dùng pin LFP)
- [ ] Mỗi request đúng **30 dòng**, mỗi dòng **6 cột**, đúng thứ tự
- [ ] `time` tính bằng **giây kể từ đầu chu kỳ**, không phải unix timestamp
- [ ] `current` **âm khi xả**
- [ ] `cycle_count` **giống nhau ở cả 30 dòng**
- [ ] `soc_percent` là **SOC thật**, không phải ước lượng
- [ ] Có `pack_config` với đủ `n_series` + `chemistry` + `capacity_ah`
- [ ] Dùng `Prescribe` (không gọi thêm `Predict` trên cùng window)
- [ ] `enrich=false` cho luồng auto-ticket
- [ ] Gate tạo ticket theo `risk.action_code`, **không** theo `anomaly_status`
- [ ] Hiểu `risk.priority` chỉ là urgency gợi ý, Priority thật do BE tính
- [ ] Channel là singleton, không tạo mới mỗi request
- [ ] Port 50051 **không** expose ra ngoài docker network


---

## 9. `VerifyTicket` — chấm điểm ticket khách tự tạo

RPC thứ 5 (`rpc VerifyTicket`, REST `POST /verify-ticket/`), TicketService dùng để gắn nhãn
ticket do khách tự khai là **hợp lệ** hay **đáng nghi**, đồng thời dò trùng với ticket đang mở.

Ba điều quan trọng nhất:

1. **AI chỉ gắn nhãn, KHÔNG tự chặn ticket.** Quyết định cuối là của Manager.
2. **Rule-based, không gọi mạng** — cùng input luôn ra cùng output, không tốn chi phí LLM.
3. **Lỗi RPC không được chặn việc tạo ticket** — bắt lỗi → `ai_verify_status = 4 (Skipped)`,
   ticket vẫn tạo bình thường.

Đặc tả đầy đủ (request/response từng field, công thức chấm điểm, mapping enum, bẫy
`category` phải đồng bộ hai phía): xem [`grpc-integration-be.md` §7](grpc-integration-be.md).

---

## 10. ⚠️ Cửa sổ phải liền mạch về thời gian (GH-67)

AI **từ chối** window trải quá **1500 giây (25 phút)** → `422` (REST) / `INVALID_ARGUMENT` (gRPC).

### Vì sao

30 bản ghi liên tiếp trong DB **không** đảm bảo liên tiếp về thời gian. Khi IoT
mất kết nối, BE vẫn lấy được 30 dòng "kề nhau" nhưng chúng trải qua hàng giờ.

Ca thật đo trên pin LFP 8S (2026-08-06) — IoT mất kết nối 76 phút giữa cửa sổ:

| | |
|---|---|
| Nhịp bình thường | ~17 s/dòng → cửa sổ ~8 phút |
| Cửa sổ dính khoảng trống | **94 phút** |
| AI trả về | SOH **81.84%** · `Maintenance Required` · **`SCHEDULE_REPLACEMENT`** |
| Thực tế | Pin hoàn toàn khoẻ, 111 cửa sổ còn lại đều `Healthy` |
| `soh_confidence` | **0.799 — CAO NHẤT cả file** (trung vị 0.425) |

Dòng cuối là lý do phải **từ chối hẳn** thay vì trả kèm cảnh báo: cửa sổ hỏng
kiểu này lại cho confidence *cao nhất*, nên BE **không thể lọc bằng confidence**.

Độ nhạy đo được (giãn đều khoảng lấy mẫu):

| Khoảng/dòng | Độ dài cửa sổ | SOH |
|---|---|---|
| 17 s | 8 phút | 100.00% ✅ |
| 30 s | 14 phút | 100.00% ✅ |
| 60 s | 29 phút | 95.50% ❌ |
| 120 s | 58 phút | 82.85% ❌ |

### BE cần làm gì

- Trước khi gọi AI, kiểm tra `readings[29].time - readings[0].time <= 1500`.
  Vượt thì **bỏ qua cửa sổ**, đợi đủ 30 bản ghi liền mạch — đây là tình huống
  bình thường sau khi IoT mất kết nối, **không phải lỗi cần tạo ticket**.
- Cột `time` phải **không giảm** — sắp xếp theo thời gian trước khi gửi.
- Suy ra ràng buộc nhịp lấy mẫu: **≤ 50 s/dòng** (30 dòng × 50 s = 1500 s).
  Nhịp hiện tại 17 s/dòng thoải mái đạt.

> Khoảng trống **đơn lẻ** không bị chặn riêng: đã đo 15 mẫu + trống 1400 s +
> 15 mẫu (cửa sổ dài 1429 s) vẫn ra SOH 100.00%. Chỉ **độ dài cửa sổ** mới quyết định.


---

## 11. RUL và cờ `INSUFFICIENT_DISCHARGE` (GH-67)

### 10.1 `rul_cycles_estimate` — đã sửa hệ số cho LFP

Trước đây mọi chemistry đều dùng tốc độ suy giảm **0.15 %/chu kỳ** — số của cell
NASA 18650 NMC 2 Ah, loại chết sau ~150 chu kỳ. Đo trên pin LFP 8S/30Ah thật:

| | Trước | Sau |
|---|---|---|
| `degradation_rate_per_cycle` | 0.15 | **0.0087** |
| `rul_cycles_estimate` | **133** | **2298** |
| `cycles_to_maintenance` | **100** | **1724** |

Cả hai con số cũ đều nói về một quả pin **mới tinh** (`cycle_count = 0`, SOH 100%).
BE mà dùng `cycles_to_maintenance` để lên lịch bảo trì thì gọi thợ sớm **~17 lần**.

0.0087 suy từ bộ Severson mà model LFP được train: EOL 80% ở ~2300 chu kỳ
⇒ `20 điểm SOH / 2300`. Chỉ áp dụng khi gửi `chemistry = "LFP"`; không khai
chemistry thì vẫn là 0.15 (đường NASA, không đổi).

> ⚠️ Nếu sau này có datasheet cycle life của chính pack đang dùng, con số đó sát
> hơn Severson (cell 1.1 Ah bị ép sạc nhanh trong lab). Sửa
> `DEGRADATION_RATE_BY_CHEMISTRY["LFP"] = 20 / cycle_life` bên repo ai-module.

### 10.2 Cờ `INSUFFICIENT_DISCHARGE` — `severity: "info"`

Xuất hiện khi cửa sổ **không có mẫu xả nào** (dòng chưa bao giờ dưới −0.1 A).

SOH nghĩa là *"xả ra được bao nhiêu Ah so với danh định"*, nên cửa sổ không có
mẫu xả thì con số SOH chỉ là nội suy từ điện áp nghỉ. Đo trên dump IoT thật (pin
đứng im 17 giờ, 0 mẫu xả): **mọi cửa sổ đều ra đúng 100.00%**, kể cả khi ép điện
áp xuống 23.9 V / SOC 8%.

**BE cần làm gì:** đây **KHÔNG phải lỗi, KHÔNG tạo ticket.**

| Trường | Có cờ này |
|---|---|
| `health_stage` | `Healthy` — không đổi |
| `anomaly_status` | `Normal` — không đổi |
| `recommended_action` | `MONITOR` — không đổi |
| `risk.risk_level` | `Low` — không đổi |

`severity = "info"` là cố ý: chỉ `warning`/`critical` mới đẩy risk lên. Đã có test
khoá điều này.

Chỉ dùng nó cho 2 việc:
1. **Đừng vẽ đồ thị suy giảm SOH** từ các cửa sổ có cờ này — chúng luôn ~100%
2. **Đừng hoảng** khi pin bắt đầu có tải thật rồi SOH tụt từ 100% xuống 94% — đó
   là lần đầu tiên đo được thật, không phải pin đột ngột hỏng

Cờ biến mất ngay khi cửa sổ có mẫu xả.


---

## 12. Trần dòng đã được sửa: 75 A → 136 A cho LFP (GH-67)

AI quy dòng pack về C-rate của **cell danh định** rồi chặn ở `±5`. Cell danh định
phải là của **đúng bộ artifact** — trước đây luôn dùng 2.0 Ah (cell NASA) kể cả
cho request LFP, trong khi bộ LFP train trên cell Severson **1.1 Ah**.

Bằng chứng từ chính hai scaler — hai bộ có thang dòng khác hẳn:

```
NASA: cột current fit trên [-4.039,  0.030] A / 2.0 Ah -> C-rate [-2.02, 0.02]
LFP : cột current fit trên [-4.708, -0.100] A / 1.1 Ah -> C-rate [-4.28,-0.09]
```

Hệ quả trên pack LFP 30 Ah: xả **1C (30 A)** bị quy thành 2.00 A, model đọc thành
**1.82C** — sai hệ số 1.82× trên toàn bộ cột dòng.

### Trần dòng cho pack LFP 30 Ah, sau khi sửa

| Dòng pack | C-rate thật | `chemistry="LFP"` | Không khai chemistry |
|---|---|---|---|
| 30 A | 1.00C | ✅ | ✅ |
| 75 A | 2.50C | ✅ | ✅ |
| **100 A** | 3.33C | ✅ | ❌ **chặn** |
| 136 A | 4.53C | ✅ | ❌ chặn |
| 140 A | 4.67C | ❌ chặn | ❌ chặn |

BMS JK rated 100–200 A: tải 100 A trước đây **bị từ chối thẳng**, giờ qua được —
**miễn là BE gửi `chemistry = "LFP"`**. Đây là thêm một lý do nữa để không bỏ sót
`pack_config` (xem issue #1005).

> Câu hỏi "tải đỉnh có vượt 75 A không" tôi hỏi trước đây bớt gấp: trần thật là
> **136 A**. Chỉ cần trả lời nếu tải đỉnh có thể vượt 136 A.
---

## 13. `SubmitFeedback` — khép vòng học của AI

RPC `SubmitFeedback` (REST tương đương `POST /prescribe/feedback`). Kỹ thuật viên nói lại
prescription vừa nhận là **đúng / phải sửa / sai**, AI dùng các ca `accepted` làm few-shot
context cho những ca tương tự sau này.

```
prescription_id  ← lấy từ PrescribeResponse.prescription_id
status           ← "accepted" | "edited" | "rejected"   (giá trị khác → INVALID_ARGUMENT)
edited_steps     ← các bước sau khi KTV sửa; để rỗng nếu status != "edited"
note             ← ghi chú tự do, "" nếu không có
```

**Bốn điểm dễ vấp:**

1. **`prescription_id` chỉ có khi `enrich=true`.** Đường rule-based (`enrich=false`) không
   sinh gì để học nên trả `""`. BE phải coi `""` là "không có gì để phản hồi", đừng gửi lên.
2. **`prescription_id` KHÔNG mất khi LLM fallback.** Chỉ cần `enrich=true` là AI đã ghi bản
   ghi lịch sử, kể cả khi không có API key và prescription cuối là rule-based. Nên vòng phản
   hồi vẫn chạy được ở môi trường chưa cắm LLM.
3. **`prescription_id` sai/hết hạn → `NOT_FOUND`, KHÔNG phải lỗi hạ tầng.** Retry vô ích.
   Phân biệt với `UNAVAILABLE` (AI sập — cái này mới đáng retry).
4. **`success=false` không bao giờ xảy ra.** Thất bại luôn đi bằng status code, nên đừng viết
   nhánh xử lý `success == false`; nó là code chết.

> Trước GH-778, cả hai client Battery đều **bỏ** `prescription_id` khi map response ⇒ id chết
> ngay tại ranh giới bridge và vòng học không bao giờ khép lại. Nếu thêm client mới, nhớ
> mang field này qua.

---

## 14. `PredictLong` — SOH từ chuỗi dài (GH-10)

RPC `PredictLong` (REST `POST /predict/long`). Nhận **31..4096** timestep thay vì đúng 30.

**Khác `Predict` ở ba điểm, đọc kỹ trước khi dùng:**

| | `Predict` | `PredictLong` |
|---|---|---|
| Độ dài | đúng 30 | 31..4096 |
| MC-dropout | có → `soh_confidence`, `soh_std`, `health_stage` | **không có** |
| IsolationForest | có → `anomaly`, `risk`, `warnings` | **không có** |
| Artifact | `MODEL_VERSION` | `long_model_version` (khác hẳn) |

Bỏ anomaly là **có chủ ý**: IsolationForest được fit trên phân bố feature của window=30;
chấm một chuỗi 4096 bước bằng nó là ngoài phân bố — ra một con số trông hợp lệ nhưng vô nghĩa.

**Dùng cho:** biểu đồ/phân tích lịch sử dài.
**KHÔNG dùng cho:** luồng tạo ticket — luồng đó vẫn phải là `Prescribe` (xem §1).

Chỉ cần 4 cột `[voltage, current, temperature, time]`; `cycle_count`/`soc_percent` gửi thừa
sẽ bị bỏ qua (model long tự sinh IC-curve + discharge-progress), nên **đường này không dính
bẫy `soc_mode`** ở §13.

`pack_config` vẫn áp dụng y hệt `Predict`: `n_series` chia điện áp, `capacity_ah` quy đổi
C-rate. Riêng `chemistry` **không** chọn artifact ở đường này — model long chỉ có một bộ (NASA).

> **`long_loaded=false` không phải lỗi.** Model long nạp **lười** ở lần gọi đầu tiên, nên
> `Health` trả `false` nghĩa là "chưa ai gọi", không phải "thiếu artifact".

---

## 15. `soc_mode` — đọc từ `Health`, ĐỪNG hardcode theo chemistry

`Health` trả thêm hai field:

```
soc_mode      ← của bộ mặc định (NASA/NMC):  "window" | "cycle" | "unknown"
lfp_soc_mode  ← của bộ LFP:  "" (chưa nạp) | "window" | "cycle" | "unknown"
```

Ý nghĩa:

| Giá trị | Nghĩa là caller phải gửi `soc_percent` kiểu nào |
|---|---|
| `"cycle"` | SOC scope theo **cả chu kỳ xả**: ~100% đầu chu kỳ → ~9% cuối. Đây đúng là SOC thật của pin, nên số đo của BE dùng được thẳng. |
| `"window"` | SOC **window-local**: ~100% ở **hàng đầu của chính window này**, giảm dần qua 30 hàng. Không chắc thì **gửi 4 cột** và để AI tự tính. |
| `"unknown"` | Artifact khai một giá trị build này không hiểu → **đừng gửi 6 cột**, gửi 4 cột. |

**Vì sao phải đọc từ server:** `soc_mode` là thuộc tính của **bộ artifact**, không phải của
chemistry. Suy ra từ chemistry sẽ hỏng âm thầm đúng vào ngày một bộ được retrain với định
nghĩa kia. Mà `soc_percent` sai thì `Predict` **không bao giờ báo lỗi** — nó chỉ dịch SOH đi.

> Đo được: cùng seed cùng model, 4 cột ra SOH 67.33 · 6 cột (cycle=150, SOC=20) ra 40.46 —
> **lệch 26.87 điểm**. Không có exception nào ở giữa.
