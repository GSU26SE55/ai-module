# Prescription Feedback Contract — BE (.NET) gọi AI Module

> GH-83 · Contract: `src/schemas/prescribe.py` (REST-only, repo `ai-module`)
> Liên quan: GH-79/81/82 (prescription layer), GH-23 (Phase 3 — tích hợp ITIL, chưa làm)

Prescription layer (GH-20+) giờ có "long-term memory": mỗi lần `POST /prescribe/` chạy với
`enrich=true`, AI module lưu lại prescription cuối cùng đã trả về. Khi technician xác nhận
kết quả đó tốt (`accepted`), lần sau AI gặp case tương tự sẽ dùng nó làm few-shot context
cho LLM. BE là nơi biết được technician đã làm gì với prescription (qua maintenance log/ticket
resolution), nên BE gọi endpoint feedback này để đóng vòng lặp.

**REST-only trong scope GH-83** — không có RPC gRPC tương ứng (feedback không nằm trên
hot-path, tần suất thấp — 1 lần / ticket CLOSED). Có thể thêm gRPC parity sau nếu BE cần.

---

## 1. `prescription_id` — lấy từ đâu

`POST /prescribe/` (đã có, xem `docs/grpc-integration-be.md` §2 cho REST/gRPC parity) trả thêm field:

```json
{
  "...": "...",
  "enriched": true,
  "llm_provider": "deepseek",
  "prescription_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

- Chỉ có giá trị khi request gửi `enrich: true` **và** AI module ghi history thành công.
- `enrich: false` (rule-path, P1 hot-path) → `prescription_id: ""` luôn — **không có record để feedback**, đừng gọi endpoint feedback với chuỗi rỗng.
- BE nên lưu `prescription_id` cùng ticket/maintenance log để map lại khi ticket đóng.

## 2. Khi nào BE gọi feedback

Gọi `POST /prescribe/feedback` khi ticket chuyển sang `CLOSED` (hoặc `CLOSED_REJECTED`) và có `prescription_id` đã lưu từ bước tạo ticket:

| Trạng thái xử lý của technician | `status` gửi lên |
|---|---|
| Làm đúng theo `action_steps` AI gợi ý, ticket resolve bình thường | `accepted` |
| Có sửa lại `action_steps` trước khi thực hiện (ghi trong maintenance log) | `edited` |
| Technician bỏ qua/không dùng gợi ý AI, tự xử lý khác | `rejected` |

> Chỉ case `accepted` được dùng làm few-shot context cho lần sau — `edited`/`rejected` bị loại (xem `docs/adr/0004-prescription-long-term-memory.md`).

## 3. Request / Response

```
POST /prescribe/feedback
Content-Type: application/json
```

```json
{
  "prescription_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "accepted",
  "edited_steps": null,
  "note": null
}
```

| Field | Type | Bắt buộc | Ghi chú |
|---|---|---|---|
| `prescription_id` | string | có | Lấy từ response `/prescribe/` |
| `status` | `"accepted"` \| `"edited"` \| `"rejected"` | có | Giá trị khác → `422` |
| `edited_steps` | string[] \| null | không | Chỉ có ý nghĩa khi `status="edited"` — các bước technician đã sửa |
| `note` | string \| null | không | Ghi chú tự do (vd lý do reject) |

**Response thành công (200):**
```json
{ "success": true }
```

**Response lỗi:**

| HTTP status | Khi nào |
|---|---|
| `404` | `prescription_id` không tồn tại (hết trong FIFO cap N=500, sai id, hoặc history store không sẵn sàng) |
| `422` | `status` không thuộc 3 giá trị hợp lệ, hoặc thiếu `prescription_id` |

## 4. Ví dụ .NET

```csharp
public record PrescriptionFeedbackRequest(
    string PrescriptionId,
    string Status,          // "accepted" | "edited" | "rejected"
    List<string>? EditedSteps = null,
    string? Note = null);

// Gọi khi ticket → CLOSED, map maintenance log outcome vào Status như bảng §2
var resp = await httpClient.PostAsJsonAsync(
    "http://ai-module:8000/prescribe/feedback",
    new PrescriptionFeedbackRequest(ticket.PrescriptionId, "accepted"));

if (resp.StatusCode == HttpStatusCode.NotFound)
{
    // prescription_id không còn trong history (đã bị FIFO evict, hoặc sai) — không phải lỗi nghiêm trọng, log và bỏ qua.
}
```

## 5. Lưu ý

- Đây là contract độc lập với ITIL flow thật (GH-23 — auto-tạo ticket từ `BatteryAnomalyDetectedEvent` — chưa làm). Hiện tại BE tự quyết định thời điểm gọi feedback dựa trên ticket lifecycle sẵn có.
- Gọi feedback là **best-effort từ phía BE** — nếu AI module lỗi/404, không cần retry mạnh tay; record lịch sử chỉ ảnh hưởng chất lượng gợi ý tương lai, không ảnh hưởng ticket hiện tại.
- Không gọi feedback nhiều lần với status khác nhau cho cùng 1 `prescription_id` trừ khi thực sự cần sửa lại — mỗi lần gọi ghi đè `feedback_status` trước đó.
