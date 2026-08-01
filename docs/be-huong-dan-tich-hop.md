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
**pack LFP 4S 12.8V**. `pack_config` là cầu nối giữa hai thứ đó.

```protobuf
PackConfig {
  int32  n_series    = 1;   // số cell nối tiếp, vd 4
  string chemistry   = 2;   // "LFP" | "NMC" | bỏ trống
  double capacity_ah = 3;   // dung lượng thật của pack, vd 2.5
}
```

Mỗi field làm một việc **khác nhau**, không thay thế nhau được:

| Field | AI làm gì với nó | Không gửi thì sao |
|-------|------------------|-------------------|
| `n_series` | Chia `voltage` ra per-cell **trước** mọi xử lý | Pack 12.8V bị coi là cell 12.8V → **reject 422** vì ngoài khoảng [2.0, 4.5] V |
| `capacity_ah` | Quy `current` về C-rate tương đương cell 2 Ah | Dòng lớn của pack bị reject, hoặc bắn cảnh báo quá dòng giả |
| `chemistry` | Chọn **ngưỡng cảnh báo điện áp** + **bộ model** | Dùng ngưỡng NMC cho pin LFP → cảnh báo giả liên tục, và **bỏ sót sạc quá áp thật** |

### `chemistry` quan trọng đến mức nào — số đo thật

Cùng một payload pack LFP 4S, chỉ khác `chemistry`:

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

> *"per-cell value 13.280 V outside allowed range [2.0, 4.5] V — if this is a multi-cell pack
> (e.g. 12.8V ~ 4S LFP), send pack_config.n_series"*

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
