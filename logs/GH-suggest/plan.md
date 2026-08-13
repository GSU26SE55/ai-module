# Plan — Gợi ý Staff + Gợi ý KB cho ticket (AI đề xuất, người quyết)

## Metadata
- **Status:** PLANNING | **Role:** AI (+ BE phase 2) | **Ngày:** 2026-08-08
- **Issue:** chưa tạo — cần `/kltn-task` trước khi implement
- **Khuôn mẫu:** `VerifyTicket` (RPC đã chạy, cùng mô hình human-in-the-loop)

## Mục tiêu

Hai luồng phụ, cùng nguyên tắc **AI gợi ý — người quyết định**:

1. **Gợi ý Staff** — Manager triage ticket, AI xếp hạng nhân viên phù hợp theo
   skill ↔ loại lỗi + tier + tải hiện tại. Manager chọn, có thể chọn người ngoài
   danh sách. AI KHÔNG tự assign.
2. **Gợi ý KB** — Staff đã được phân công mở ticket, AI xếp hạng bài viết KB phù
   hợp để tham khảo khi sửa chữa. Staff bấm áp dụng thì mới tạo `TicketKbReference`.
   AI KHÔNG tự gắn.

## Vì sao đặt ở ai-module

`VerifyTicket` đã chứng minh khuôn này chạy trong dự án: BE gom dữ liệu của mình →
đẩy sang AI qua gRPC → AI chấm điểm + trả lý do tiếng Việt → BE/người quyết.
Giữ mọi logic mang danh "AI" ở một chỗ thay vì rải sang BE.

**Deterministic, KHÔNG dùng LLM** — theo đúng tiền lệ `src/services/verify.py`:
> *"Thiết kế deterministic (heuristic) — KHÔNG bắt buộc LLM/network, để chạy ổn
> định trong môi trường capstone và test được."*

Lý do giữ nguyên nguyên tắc đó ở đây:
- Hội đồng KLTN sẽ hỏi "vì sao chọn người này" → công thức điểm trả lời được,
  LLM thì không.
- Không phụ thuộc mạng/rate-limit → gợi ý luôn hiện.
- Test được, reproducible.

## Ranh giới dữ liệu

ai-module KHÔNG đọc được DB của TicketService (khác service, khác DB). Giải như
`VerifyTicket` làm với `repeated DuplicateCandidate`: **BE query rồi gửi kèm
candidates vào request**. AI chỉ chấm điểm trên dữ liệu được đưa.

---

## Scope

**Trong scope (phase 1 — repo ai-module):**
- 2 RPC mới + 2 endpoint REST tương ứng (parity bắt buộc)
- 2 service chấm điểm deterministic
- Unit test ≥ 85% coverage

**Trong scope (phase 2 — repo backend, PR riêng):**
- 2 gRPC client + 2 query handler + 2 endpoint
- Authz + query gom candidates
- Unit test ≥ 80% coverage

**Trong scope (phase 0 — repo backend, LÀM TRƯỚC):**
- Giữ structured data của AI thay vì bóp thành text nhét vào Description
  (xem §"Phase 0" bên dưới) — chốt 2026-08-08 theo yêu cầu "tối ưu, cứ thêm field nếu cần thiết"

**Ngoài scope:**
- Không tự động assign staff / tự động gắn KB
- Không sửa `KbSuggestionService` hiện có (đang phục vụ chat, có test riêng)
- Không đụng `KbReferenceTypeEnum` (không tạo bản ghi tự động nên không cần giá trị mới)

---

## Phase 0 — Giữ structured data của AI (backend, làm TRƯỚC)

### Vấn đề

AI trả structured data đầy đủ, và bridge `AiPrescriptionResult` **đã map đúng hết**
(kể cả `SopReferences`, `EscalationConditions`, `Blocked`, `PrescriptionId`).
Mất mát xảy ra ở **2 chỗ SAU bridge**:

```
AiPrescriptionResult (đầy đủ, structured)
   ↓  ❌ BuildPrescriptionText() — bóp thành 1 string
BatteryAnomalyDetectedV2Event.AiPrescription : string
   ↓
saga.AiPrescription : string  (cột ai_prescription)
   ↓  ❌ SendCreateTicketActivity — nối vào Description
Ticket.Description   ← lẫn với mô tả lỗi
```

Cái gì sống sót tới Ticket:

| Field | Số phận |
|---|---|
| `Prescription` | ⚠️ text trong Description |
| `ActionSteps[]` | ⚠️ text `- bước...` |
| `PpeRequired[]` | ⚠️ text `PPE: a, b` |
| `SopReferences[]` | ❌ mất tại `BuildPrescriptionText` |
| `EscalationConditions[]` | ❌ mất |
| `SafetyWarnings[]` | ❌ mất |
| `HumanVerificationRequired` | ❌ mất |
| `Blocked` | ❌ mất |
| `maintenance_docs[]` / `safety_docs[]` | ❌ mất **ngay tại bridge** (client không map) |

> ⚠️ `maintenance_docs`/`safety_docs` mất SỚM HƠN: `AiPrescriptionGrpcClient` không map
> chúng vào `AiPrescriptionResult`. Muốn có KB refs của AI phải sửa cả bridge.

### Giải pháp — entity mới `TicketAiSuggestion`

KHÔNG thêm cột rời rạc vào `Ticket` (sẽ thành ~8 cột chỉ dùng cho ticket auto,
null với mọi ticket Customer tạo). Dùng 1 entity 1-1 với Ticket:

```csharp
public class TicketAiSuggestion : AuditableEntity
{
    public Guid TicketId { get; set; }              // FK, unique
    public Ticket? Ticket { get; set; }

    public string? PrescriptionId { get; set; }     // để gửi feedback về AI
    public string Prescription { get; set; } = "";
    public List<string> ActionSteps { get; set; } = new();
    public List<string> PpeRequired { get; set; } = new();
    public List<string> SopReferences { get; set; } = new();
    public List<string> EscalationConditions { get; set; } = new();
    public List<string> SafetyWarnings { get; set; } = new();
    public List<string> KbDocRefs { get; set; } = new();   // source của maintenance/safety docs

    public bool HumanVerificationRequired { get; set; }
    public bool Blocked { get; set; }
    public bool Enriched { get; set; }
    public string LlmProvider { get; set; } = "none";
}
```

`List<string>` map JSONB — theo đúng pattern `KnowledgeBaseArticle.Tags` và
`StaffAccount.SkillCodes` đang dùng.

### Backward-compat — BẮT BUỘC

`BatteryAnomalyDetectedV2Event` đã có `AiPrescription` + `AiActionSteps` ở **cuối
constructor, nullable**, có comment ghi rõ lý do: consumer/saga cũ + threshold engine
(không set) vẫn deserialize được.

Field mới PHẢI theo đúng quy ước đó: **nullable, thêm vào CUỐI**, không đổi thứ tự
field cũ. Cùng nguyên tắc với proto (chỉ thêm, không sửa số cũ).

**Giữ nguyên `AiPrescription` text** — không xoá. Lý do:
1. Description vẫn cần đoạn text để Manager đọc nhanh + để AI dò trùng ticket
   (`SendCreateTicketActivity` có comment: description tiếng Việt là để Jaccard
   match được với ticket Customer viết tay).
2. Xoá là breaking change với saga đang chạy.

Structured data là **bổ sung**, không thay thế.

### Files — Phase 0

| File | Action | Ghi chú |
|------|--------|---------|
| `AiPrescriptionResult.cs` | modify | +`MaintenanceDocs`, `SafetyDocs` (nullable, cuối ctor) |
| `AiPrescriptionGrpcClient.cs` | modify | map `maintenance_docs`/`safety_docs` từ proto |
| `AiPrescriptionHttpClient.cs` | modify | map tương ứng (parity) |
| `BatteryAnomalyDetectedV2Event.cs` | modify | +field nullable ở CUỐI |
| `SohPredictionBackgroundService.cs` | modify | truyền structured, GIỮ `BuildPrescriptionText` |
| `CreateTicketFromAlertCommand.cs` | modify | +field nullable ở CUỐI |
| `AlertTicketSagaState.cs` + Configuration | modify | +cột lưu structured |
| `SendCreateTicketActivity.cs` | modify | forward structured, GIỮ nối Description |
| `TicketAiSuggestion.cs` | create | entity mới |
| `TicketAiSuggestionConfiguration.cs` | create | JSONB + unique index TicketId |
| `TicketDbContext.cs` | modify | +DbSet |
| `TicketAutoCreateFromAlertCommandHandler.cs` | modify | ghi `TicketAiSuggestion` cùng transaction |
| `StaffAccount.cs` + Configuration | modify | **+cột `Role`** (xem §BE gom candidates) |
| `AccountSyncConsumer.cs` | modify | gán `staff.Role = @event.Role` (đã có sẵn giá trị) |
| Migration | create | `AddTicketAiSuggestionAndStaffRole` |

### Đã xác minh (2026-08-08)

| Giả định | Kết quả |
|---|---|
| `AiPrescriptionResult` map đủ SopReferences/EscalationConditions | ✅ đúng (gRPC dòng 65/73, HTTP dòng 93/100) |
| `MaintenanceDocs`/`SafetyDocs` KHÔNG được map | ✅ đúng — **cả 2 client đều thiếu** |
| Proto có sẵn `maintenance_docs=12`, `safety_docs=13` | ✅ có sẵn, không cần sửa proto cho Phase 0 |
| `JsonValueConverter<List<string>>` tồn tại | ✅ `Persistence/Converters/JsonValueConverter.cs` |
| Pattern JSONB list | ✅ `Tags` + `SkillCodes` đều dùng `.HasColumnType("jsonb")` |
| `Ticket` chưa có nav tới AI suggestion | ✅ không có gì để đụng |
| `V2Event` field nullable ở cuối | ✅ `AiPrescription`, `AiActionSteps` đã theo pattern này |

> ✅ **Phase 0 KHÔNG cần sửa proto** — `maintenance_docs`/`safety_docs` đã có sẵn
> trong `PrescribeResponse`. Chỉ cần sửa client BE map chúng. Giảm rủi ro đáng kể.

### Rủi ro Phase 0

Đây là phần **sửa vào đường ống đang chạy** — rủi ro cao hơn hẳn Phase 1/2 (vốn chỉ
thêm mới). Vỡ thì vỡ cả luồng tạo ticket từ alert.

Giảm rủi ro:
- Field mới **nullable toàn bộ** → saga cũ / threshold engine không set vẫn chạy
- **Giữ nguyên** `AiPrescription` text và phần nối Description → luồng cũ không đổi hành vi
- Ghi `TicketAiSuggestion` **best-effort**: lỗi ghi KHÔNG được làm fail việc tạo ticket
- Test rollback migration bắt buộc (checklist §14 be.md)

---

## Files — Phase 1 (ai-module)

| File | Action | Ghi chú |
|------|--------|---------|
| `protos/ai_service.proto` | modify | +2 rpc, +6 message. CHỈ THÊM field number mới |
| `src/schemas/suggest.py` | create | Pydantic — dùng chung REST + gRPC validate |
| `src/services/suggest_staff.py` | create | Chấm điểm staff |
| `src/services/suggest_kb.py` | create | Chấm điểm KB |
| `src/routers/suggest.py` | create | POST /suggest/staff, POST /suggest/kb |
| `main.py` | modify | +1 include_router |
| `src/grpc_server.py` | modify | +2 servicer method |
| `src/grpc_gen/*` | regen | `python scripts/gen_proto.py` |
| `tests/test_suggest_staff.py` | create | |
| `tests/test_suggest_kb.py` | create | |
| `tests/test_grpc_server.py` | modify | +parity test REST↔gRPC |

## Files — Phase 2 (backend)

| File | Action | Ghi chú |
|------|--------|---------|
| `TicketService.Application/Interfaces/Services/IAiStaffSuggestClient.cs` | create | |
| `TicketService.Application/Interfaces/Services/IAiKbSuggestClient.cs` | create | |
| `TicketService.Infrastructure/Implements/Services/AiStaffSuggestGrpcClient.cs` | create | Khuôn `AiTicketVerifyGrpcClient` |
| `TicketService.Infrastructure/Implements/Services/AiKbSuggestGrpcClient.cs` | create | |
| `.../CQRS/Query/Suggestions/TicketStaffSuggestionsQuery.cs` + Handler | create | Manager/Admin |
| `.../CQRS/Query/Suggestions/TicketKbSuggestionsQuery.cs` + Handler | create | Staff được assign |
| `.../DTOs/Response/Suggestions/*.cs` | create | |
| `TicketService.Api/Controllers/...` | modify | +2 endpoint |
| `.../DependencyInjection/ManageDependencyInjection.cs` | modify | +2 DI |

---

## Proto (thêm mới — không sửa số cũ)

```protobuf
service AiService {
  // ... rpc hiện có, giữ nguyên ...

  // Gợi ý staff phù hợp để xử lý ticket. BE gửi kèm danh sách ứng viên
  // (ai-module không đọc được bảng staff). Human-in-the-loop: Manager quyết.
  rpc SuggestStaff(SuggestStaffRequest) returns (SuggestStaffResponse);

  // Gợi ý KB article để staff tham khảo khi sửa chữa. BE gửi kèm ứng viên.
  // Human-in-the-loop: Staff bấm áp dụng thì mới tạo TicketKbReference.
  rpc SuggestKb(SuggestKbRequest) returns (SuggestKbResponse);
}

message StaffCandidate {
  string staff_id = 1;
  string full_name = 2;
  int32  skill_tier = 3;              // StaffSkillTierEnum 1..3
  repeated string skill_codes = 4;    // free-text, so khớp OrdinalIgnoreCase+Trim
  int32  active_tickets = 5;          // BE đếm sẵn
  int32  max_concurrent = 6;
}

message SuggestStaffRequest {
  int32  category = 1;                 // TicketCategoryEnum
  int32  priority = 2;                 // TicketPriorityEnum; 0 = chưa có
  string description = 3;              // Title + Description (đã gồm AI prescription)
  repeated StaffCandidate candidates = 4;
  int32  top_n = 5;                    // 0 → mặc định 5
}

message StaffSuggestion {
  string staff_id = 1;
  string full_name = 2;
  double score = 3;                    // [0..1]
  string reason = 4;                   // tiếng Việt, cho Manager đọc
  bool   tier_ok = 5;                  // false = không đủ tier (đã bị loại)
}

message SuggestStaffResponse {
  repeated StaffSuggestion suggestions = 1;
  string note = 2;                     // "" hoặc lý do danh sách rỗng
}

message KbCandidate {
  string kb_id = 1;
  string code = 2;
  string title = 3;
  repeated string tags = 4;
  int32  category = 5;                 // TicketCategoryEnum
  int32  helpful_count = 6;
}

message SuggestKbRequest {
  int32  category = 1;
  string description = 2;              // Title + Description ticket
  repeated KbCandidate candidates = 3;
  int32  top_n = 4;                    // 0 → mặc định 5
}

message KbSuggestion {
  string kb_id = 1;
  string code = 2;
  string title = 3;
  double score = 4;
  string reason = 5;
}

message SuggestKbResponse {
  repeated KbSuggestion suggestions = 1;
  string note = 2;
}
```

---

## Thuật toán — Gợi ý Staff

### Bước 1: Lọc cứng (loại khỏi danh sách)

Phải khớp **chính xác** điều kiện mà `TicketAssignCommandHandler` validate, nếu
không Manager bấm chọn sẽ nhận 403 → tính năng phản tác dụng.

| Điều kiện | Nguồn |
|---|---|
| Tier đủ theo priority | `AssignmentRoleHelper.ValidatePrimaryHandlerTier` |
| `active_tickets < max_concurrent` | BE đếm sẵn |

> BE đã lọc sẵn `Status==Active`, `IsAvailable==true`, và loại Manager trước khi gửi.

**Priority = 0 (chưa có)** → bỏ lọc tier, `tier_ok=true` cho tất cả. KHÔNG để rơi
vào nhánh `_ => false` làm danh sách rỗng.

### Bước 2: Bảng ánh xạ skill ↔ loại lỗi

| Category | Ưu tiên | Chấp nhận |
|---|---|---|
| `Charging` (1) | `charging` | `battery`, `general` |
| `Overheat` (2) | `incident` | `battery`, `general` |
| `NoPower` (3) | `battery` | `charging`, `general` |
| `Performance` (4) | `battery` | `firmware`, `general` |
| `Other` (5) | — | `general` |
| `Repair` (6) | `battery` | `general` |

> `skill_codes` là **string tự do** (`StaffSkill.SkillCode` không có enum/validation).
> Hiện chỉ 5 giá trị vì đến từ seed, nhưng Admin nhập tay có thể ra `"Battery"`,
> `"pin"`, `"battery "`. **Bắt buộc normalize**: lowercase + trim trước khi so.

### Bước 3: Chấm điểm (thang 100 → chia 100 ra [0..1])

```
skill:  khớp ưu tiên +50 | chỉ khớp phụ +25 | chỉ có 'general' +10 | không khớp +0
tier:   đúng mức yêu cầu +15 | vượt 1 bậc +8 | vượt ≥2 bậc +0
tải:    (1 - active/max) × 10
```

Tier vượt nhiều bậc **không cộng thêm** — tránh dồn hết P3 cho Tier 3 rồi khi có
P1 thì không còn ai.

### Bước 4: Sắp xếp & trả về

- Sort giảm dần theo score; hòa thì ưu tiên người tải thấp hơn
- Cắt `top_n` (mặc định 5, clamp 1..10)
- `reason` ghép từ các yếu tố đã cộng điểm, ví dụ:
  `"Khớp kỹ năng 'charging'; Tier 2 đạt yêu cầu P2; đang xử lý 3/8 ticket"`
- Danh sách rỗng → `note` giải thích ("không ai đủ tier P1" / "tất cả đã đầy tải")

---

## Thuật toán — Gợi ý KB

### Lọc cứng
BE chỉ gửi bài `Status == Published` và `!IsDeleted`. Không đưa Draft/PendingReview
cho staff — chưa qua duyệt.

### Chấm điểm (thang 100)

```
cùng category      +40
khớp tags          +30  (mỗi tag khớp +10, tối đa 30)
khớp từ khóa title +20  (tỉ lệ token khớp × 20)
độ hữu ích         +10  (helpful_count / max_helpful trong tập ứng viên)
```

**KHÔNG lọc cứng theo category** (khác `KbSuggestionService` hiện tại) — chỉ cộng
điểm. Lý do: ticket auto `SohDegradation` → category `Performance`, nếu lọc cứng
thì bài an toàn nhiệt/PPE không bao giờ nổi lên dù rất cần khi xử lý pin nóng.

### Nguồn từ khóa

Nhờ Phase 0, BE gửi **structured data** thay vì text bóp phẳng:

- `description` = Title + Description (mô tả lỗi thuần, KHÔNG còn cần đoạn AI)
- `ai_action_steps[]`, `ai_sop_references[]` — từ `TicketAiSuggestion`

Ghép nguồn từ khóa theo thứ tự ưu tiên: `sop_references` > `action_steps` > `description`.
Chính xác hơn hẳn so với đoán từ text đã ghép chuỗi.

**Bonus `+15` khi `sop_references` khớp KB code/title** — đây là KB mà AI đã thực sự
retrieve được qua RAG, tín hiệu mạnh nhất trong tất cả.

> Ticket do Customer tạo không có `TicketAiSuggestion` → 2 field này rỗng, chỉ dùng
> `description`. Vẫn chạy, chỉ kém chính xác hơn — chấp nhận được.

Proto `SuggestKbRequest` bổ sung:
```protobuf
repeated string ai_action_steps = 5;
repeated string ai_sop_references = 6;
```

Chuẩn hóa tiếng Việt dùng lại `_strip_accents` / `_norm` / `_tokens` / `_jaccard`
từ `src/services/verify.py` — **tách sang `src/services/text_utils.py`** để 2 chỗ
dùng chung, không copy-paste.

---

## Authz — Phase 2 (BE)

| Endpoint | Ai được gọi |
|---|---|
| `GET /api/v1/tickets/{id}/staff-suggestions` | Admin, Manager |
| `GET /api/v1/tickets/{id}/kb-suggestions` | Admin, Manager, **Staff được assign** |

Staff = PrimaryHandler **hoặc Supporter** (nới so với `AddTicketKbReferenceCommandHandler`
vốn chỉ cho PrimaryHandler). Lý do: Supporter cũng đang sửa chữa và đã có
`CanViewInternal = true`. **Xem thì nới, ghi vẫn giữ nguyên chỉ PrimaryHandler.**

Dùng lại pattern lấy `PrimaryHandlerStaffId` từ `TicketAssignments` như các handler
hiện có.

---

## BE gom candidates

**Staff:** query `StaffAccounts` (`Status==Active`, `IsAvailable`, `!IsDeleted`)
+ đếm ticket active **gom 1 truy vấn** `GroupBy(StaffId)` trên `TicketAssignment`
join `Ticket` — KHÔNG đếm từng người (N+1).

> ⚠️ **`StaffAccount` KHÔNG có field Role.** `AccountSyncConsumer.cs:30-32` tạo
> `StaffAccount` cho **cả Staff, Manager VÀ Admin** (`isStaff` gồm 3 role). Seed
> cũng có `manager.demo` với `SkillCodes=["management"]`.
> ⇒ Không thể lọc Manager bằng cột nào trên bảng này.
>
> **Cách loại (chốt):** loại theo `SkillCodes` chứa `"management"` là **KHÔNG đủ tin cậy**
> (free-text, Admin nhập tay). Dùng cách chắc chắn: gọi AuthService lấy danh sách
> AccountId có role Staff, HOẶC thêm cột `Role` vào `StaffAccount` + map trong
> `AccountSyncConsumer` (đã có sẵn `@event.Role`).
> → **Chọn thêm cột `Role`**: rẻ hơn 1 vòng gọi service, và `AccountSyncConsumer`
> đã có sẵn giá trị chỉ việc gán. Gộp vào migration Phase 0.

> ⚠️ **Đếm workload phải loại `AssignmentRoleEnum.PreviousPrimaryHandler = 3`** —
> đây là người đã BỊ chuyển giao, không còn xử lý ticket. Đếm cả họ sẽ khiến staff
> bị coi là đầy tải oan. Chỉ đếm `PrimaryHandler` (+ `Supporter` nếu tính hỗ trợ).

> Tái dùng danh sách `ActiveStatuses` ở `CreateTicketFromAlertConsumer.cs:30-42`.
> Lưu ý mảng đó đang có `TicketStatusEnum.Open` **lặp 2 lần** (dòng 34 và 41) —
> vô hại với `Contains` nhưng nên tách thành hằng số dùng chung thay vì copy lần 3.

**KB:** query `KnowledgeBaseArticles` (`Published`, `!IsDeleted`). Chỉ `Select` các
cột cần (`Id/Code/Title/Tags/Category/HelpfulCount`) — **KHÔNG kéo `Content`**
(`JsonDocument`, nặng).

## Fail-safe

Khuôn `AiTicketVerifyGrpcClient`: catch `RpcException`/`Exception` → trả `null` →
endpoint trả danh sách rỗng + `note`. **Không bao giờ chặn luồng triage/sửa chữa.**

---

## Steps — Phase 0 (backend, làm TRƯỚC)

- [ ] B0.1: `AiPrescriptionResult` +`MaintenanceDocs`/`SafetyDocs` (nullable, cuối ctor)
- [ ] B0.2: Map `maintenance_docs`/`safety_docs` ở gRPC client + HTTP client (parity)
- [ ] B0.3: `BatteryAnomalyDetectedV2Event` +field nullable ở CUỐI; giữ `AiPrescription`
- [ ] B0.4: `SohPredictionBackgroundService` truyền structured; GIỮ `BuildPrescriptionText`
- [ ] B0.5: `CreateTicketFromAlertCommand` + `AlertTicketSagaState` + Configuration
- [ ] B0.6: `SendCreateTicketActivity` forward structured; GIỮ nối Description
- [ ] B0.7: Entity `TicketAiSuggestion` + Configuration (JSONB, unique TicketId) + DbSet
- [ ] B0.8: `TicketAutoCreateFromAlertCommandHandler` ghi best-effort (lỗi KHÔNG fail ticket)
- [ ] B0.9: `StaffAccount.Role` + Configuration + `AccountSyncConsumer` gán giá trị
- [ ] B0.10: Migration `AddTicketAiSuggestionAndStaffRole` + **test rollback** (§14 be.md)
       — cột `Role` NOT NULL cần `defaultValue` hoặc backfill (§14: populate trước constraint)
- [ ] B0.11: Test — saga cũ không set field mới vẫn chạy; ticket Customer không có suggestion

## Steps — Phase 1 (ai-module)

- [ ] B1: Tách `text_utils.py` từ `verify.py` (normalize/token/jaccard), giữ verify chạy nguyên
- [ ] B2: `schemas/suggest.py` — Pydantic request/response
- [ ] B3: `services/suggest_staff.py` — lọc + chấm điểm + reason
- [ ] B4: `services/suggest_kb.py` — chấm điểm + reason
- [ ] B5: `routers/suggest.py` + đăng ký ở `main.py`
- [ ] B6: Sửa `protos/ai_service.proto` + `python scripts/gen_proto.py`
- [ ] B7: 2 servicer method trong `grpc_server.py` (validate qua Pydantic của REST)
- [ ] B8: Test — unit + parity REST↔gRPC. `pytest --cov=src` ≥ 85%

## Steps — Phase 2 (backend, PR riêng)

- [ ] B9: 2 interface + 2 gRPC client + DI
- [ ] B10: 2 Query + Handler (authz + gom candidates)
- [ ] B11: 2 endpoint controller
- [ ] B12: Test `dotnet test` ≥ 80%

## Thứ tự merge

**3 PR, merge tuần tự:**

1. **Phase 0** (backend) — giữ structured data. Độc lập, tự nó có giá trị.
2. **Phase 1** (ai-module) — proto + 2 RPC. Proto là hợp đồng nên phải trước BE consumer.
3. **Phase 2** (backend) — client + endpoint. Cần cả (1) và (2) đã merge.

Phase 0 đi trước vì Phase 1 thiết kế `SuggestKbRequest` dựa trên structured data
mà Phase 0 tạo ra.

---

## Rủi ro

| Rủi ro | Xử lý |
|---|---|
| Proto là hợp đồng chung — sửa sai khó lùi | Chỉ THÊM field number mới, không đụng số cũ |
| ai-module sập → không có gợi ý | Fail-safe trả rỗng, không chặn nghiệp vụ |
| `skill_codes` free-text, Admin nhập lệch | Normalize lowercase+trim; cân nhắc chốt danh mục sau |
| Gợi ý chứa người mà assign sẽ từ chối | Lọc cứng khớp đúng `TicketAssignCommandHandler` |
| Chất lượng KB phụ thuộc format text AI | Ghi rõ ở trên; sửa gốc là issue riêng |
