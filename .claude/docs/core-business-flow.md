# GSU26SE55 — Core Business Flow

**Quy trình nghiệp vụ cốt lõi** theo 4 role · Scope: SE-only · ITIL Ticket & SLA Management

---

## Vai trò trong hệ thống

| Role | Màu | Mô tả |
|------|-----|-------|
| Admin | 🔴 | Setup/Config — tạo account, cấu hình Battery Type + ThresholdConfig per Type, SLA rules, quản lý Battery Asset |
| Customer | 🟣 | Tạo ticket (+ ảnh/video), theo dõi tiến trình, rate service |
| Manager | 🔵 | Xem xét priority tự động → điều chỉnh nếu cần → assign Staff theo tầng → approve (kiểm tra Wiki) → escalate |
| Staff | 🟢 | Xử lý ticket, ghi maintenance log, tạo/cập nhật Wiki, escalate chủ động tại 2/3 SLA |
| System | 🟡 | Dependency check, auto alert, priority tự động, SLA timer |

---

## 1. Tổng quan 6 Phase

Quy trình tổng thể chia làm 6 phase. Mỗi phase có 1 role "owner" chính, role khác tham gia phụ.

| # | Phase | Mô tả | Owner |
|---|-------|-------|-------|
| ① | Setup & Configuration | Tạo account, tạo Battery Type (LFP/NMC…), cấu hình ThresholdConfig per Type, set ngưỡng cảnh báo, định nghĩa SLA rules P1/P2/P3 + Staff tier, quản lý Battery Asset (serial, warranty, owner) | ADMIN |
| ② | Monitoring & Detection | Customer theo dõi pin real-time. System auto-check ngưỡng, chạy Dependency Check (pin hỏng ảnh hưởng pin khác?), sinh cảnh báo và tính priority tự động khi có ảnh hưởng | CUSTOMER + SYSTEM |
| ③ | Ticket Creation | Customer tạo ticket thủ công (+ ảnh/video), HOẶC system auto-tạo từ alert critical có ảnh hưởng | CUSTOMER / SYSTEM |
| ④ | Triage & Assignment | Manager xem xét priority tự động + ảnh/thông số Customer → điều chỉnh nếu cần → assign Staff đúng tầng. SLA timer bắt đầu | MANAGER |
| ⑤ | Resolution | Staff xử lý theo băng chuyền: cập nhật status, tra Wiki, ghi log, tạo/cập nhật Wiki, liên hệ customer, mark Resolved hoặc escalate chủ động tại 2/3 SLA | STAFF |
| ⑥ | Verification & Closure | Manager review maintenance log + kiểm tra Wiki → approve. Customer đánh giá (rate/reopen). Ticket chính thức Closed | MANAGER + CUSTOMER |

---

## 2. Swimlane End-to-End

Mỗi lane là 1 role. Mũi tên cắt ngang lane = handoff giữa các role.

```mermaid
flowchart TB
    Start([🔔 Bắt đầu chu kỳ vận hành])

    subgraph ADMIN["🔴 ADMIN LANE — Setup 1 lần"]
        direction LR
        A1[Tạo accounts<br/>Manager/Staff/Customer]
        A2[Cấu hình Battery Type<br/>+ ThresholdConfig per Type<br/>LFP · NMC · ...]
        A3[Định nghĩa SLA rules<br/>P1/P2/P3 + Staff tier]
        A4[Quản lý Battery Asset<br/>serial · warranty · owner]
        A1 --> A2 --> A3 --> A4
    end

    subgraph CUSTOMER["🟣 CUSTOMER LANE — Mobile App"]
        direction LR
        C1[Mở app<br/>xem pin real-time]
        C2{Phát hiện<br/>bất thường?}
        C3[Tạo ticket<br/>mô tả + ảnh]
        C4[Theo dõi tiến trình<br/>+ reply Staff]
        C5{Resolved OK?}
        C6[Rate & Close]
        C7[Reopen]
        C1 --> C2
        C2 -->|Có| C3
        C2 -->|Không| C1
        C4 --> C5
        C5 -->|OK| C6
        C5 -->|Chưa OK| C7
    end

    subgraph SYSTEM["🟡 SYSTEM LANE — Backend"]
        direction LR
        S1[Check ngưỡng<br/>từng chu kỳ]
        S2{Vượt<br/>ngưỡng?}
        S3[Phân tích Dependency<br/>pin hỏng ảnh hưởng<br/>pin khác không?]
        SD{Có ảnh hưởng<br/>lan sang pin khác?}
        S3a[Bỏ qua — ghi log<br/>không tạo ticket]
        S3b[Tạo Alert + tính Priority<br/>P1/P2/P3 tự động<br/>dựa trên classification<br/>+ mức độ ảnh hưởng]
        S7{Alert trùng<br/>trong cửa sổ thời gian?}
        S8[Merge vào ticket/alert cũ]
        S4[Start SLA timer<br/>khi ticket assigned]
        S9[Pause/Resume SLA<br/>khi chờ Customer/Parts]
        S5{SLA 2/3 hoặc breach?}
        S6[Cảnh báo Manager<br/>+ Staff]
        S1 --> S2
        S2 -->|Có| S3 --> SD
        SD -->|Không ảnh hưởng| S3a
        SD -->|Có ảnh hưởng| S3b --> S7
        S7 -->|Có| S8
        S7 -->|Không| C2
        S2 -->|Không| S1
        S4 --> S9 --> S5
        S5 -->|Có| S6
    end

    subgraph MANAGER["🔵 MANAGER LANE — Web App"]
        direction LR
        M1[Nhận ticket vào queue<br/>kèm priority đã tính sẵn]
        M2[Xem xét priority<br/>dựa trên ảnh + thông số<br/>Customer cung cấp]
        M2b{Điều chỉnh<br/>priority?}
        M2c[Giữ nguyên hoặc<br/>điều chỉnh P1/P2/P3]
        M3[Assign Staff theo tầng<br/>P1→Tier1 · P2→Tier2 · P3→Tier3]
        M4{Staff mark<br/>Resolved?}
        M5[Review + kiểm tra Wiki<br/>& Approve]
        M6[Reject<br/>gửi lại Staff]
        M7{Cần escalate?}
        M8[Reassign tầng Staff<br/>cao hơn]
        M9[Xem activity timeline<br/>và SLA history]
        M1 --> M2 --> M2b
        M2b -->|Cần chỉnh| M2c --> M3
        M2b -->|Giữ nguyên| M3
        M4 -->|Yes| M9 --> M5
        M4 -->|Staff escalate / breach| M7
        M7 -->|Yes| M8
    end

    subgraph STAFF["🟢 STAFF LANE — Web App"]
        direction LR
        T1[Nhận notification<br/>ticket mới]
        T2[Update status<br/>In Progress]
        T3[Comment với Customer<br/>nếu cần thông tin]
        T8[Dùng Knowledge Base<br/>solution template]
        T4[Ghi Maintenance Log<br/>+ tạo/cập nhật Wiki]
        T5{Xử lý được<br/>trong SLA còn lại?}
        T6[Mark Resolved]
        T7[Request Escalation<br/>tại 2/3 SLA]
        T1 --> T2 --> T3 --> T8 --> T4 --> T5
        T5 -->|Được| T6
        T5 -->|Không / đến 2/3 SLA| T7
    end

    Start --> A1
    A4 -.setup xong.-> C1
    A4 -.-> S1
    C3 --> M1
    M3 --> T1
    M3 --> S4
    T6 --> M4
    T7 --> M7
    M5 --> C4
    M6 --> T2
    C7 --> M1
    M8 --> T1
```

---

## 3. Sequence Diagram — Tương tác role theo thời gian

Góc nhìn khác: ai gọi ai, gọi thứ tự nào. Hữu ích khi thiết kế API contract.

```mermaid
sequenceDiagram
    autonumber
    actor Admin as 🔴 Admin
    actor Customer as 🟣 Customer
    participant Mobile as 📱 Mobile App
    participant Backend as ⚙️ Backend API
    participant DB as 🗄️ DB (TimescaleDB)
    actor Manager as 🔵 Manager
    actor Staff as 🟢 Staff
    participant Notif as 📨 Notification Service

    Note over Admin,Backend: Phase 1 — Setup (1 lần)
    Admin->>Backend: POST /users (tạo Manager/Staff/Customer)
    Admin->>Backend: POST /battery-types + /thresholds
    Admin->>Backend: POST /battery-assets (serial, customerId, warranty)
    Admin->>Backend: POST /sla-rules (P1/P2/P3 + escalation)

    Note over Customer,DB: Phase 2 — Monitoring & Alert
    Customer->>Mobile: Mở app
    Mobile->>Backend: GET /battery/realtime?assetId={id}
    Backend->>DB: query latest metrics
    DB-->>Backend: V, I, T, SOC
    Backend-->>Mobile: data
    Mobile-->>Customer: hiển thị chart

    Backend->>Backend: scheduled check ngưỡng
    Backend->>Backend: deduplicate/correlate alert
    Backend->>Notif: push alert nếu vượt ngưỡng
    Notif-->>Customer: 🔔 cảnh báo

    Note over Customer,Manager: Phase 3–4 — Create & Assign
    Backend->>Backend: Dependency check — pin hỏng có ảnh hưởng pin khác?
    alt Không ảnh hưởng → không tạo ticket
        Backend->>DB: ghi log anomaly, bỏ qua
    else Có ảnh hưởng → tạo ticket + tính priority tự động
        Backend->>Backend: tính priority (P1/P2/P3) từ classification + dependency
        Customer->>Mobile: Tạo ticket thủ công (hoặc system auto-create)
        Mobile->>Backend: POST /tickets (assetId, category, description, files, priority_suggested)
        Backend->>DB: lưu ticket (status=OPEN, priority=auto-calculated)
        Backend->>DB: ghi Activity Timeline
        Backend->>Notif: notify Manager
        Notif-->>Manager: ticket mới + priority gợi ý
    end

    Manager->>Backend: GET /tickets?status=NEW
    Manager->>Backend: GET /tickets/{id} — xem ảnh + thông số Customer cung cấp
    Manager->>Backend: PUT /tickets/{id}/assign (staffId, priority_confirmed)
    Note right of Manager: Manager chỉ xem xét điều chỉnh priority<br/>dựa trên ảnh/thông số Customer — không tự định priority từ đầu
    Backend->>DB: update priority + start SLA timer
    Backend->>DB: ghi Activity Timeline
    Backend->>Notif: notify Staff
    Notif-->>Staff: ticket được giao

    Note over Staff,Customer: Phase 5 — Resolution
    Staff->>Backend: PUT /tickets/{id}/status=IN_PROGRESS
    Staff->>Backend: GET /knowledge-base?category={category}
    Staff->>Backend: POST /tickets/{id}/comments
    Backend->>Notif: notify Customer
    Notif-->>Customer: reply từ Staff

    alt Chờ Customer hoặc chờ linh kiện
        Staff->>Backend: PUT /tickets/{id}/hold (WAITING_CUSTOMER / WAITING_PARTS)
        Backend->>DB: pause SLA timer + ghi lý do
    else Có thể xử lý tiếp
        Staff->>Backend: PUT /tickets/{id}/resume
        Backend->>DB: resume SLA timer
    end

    Staff->>Backend: POST /tickets/{id}/maintenance-log
    Staff->>Backend: POST /wiki-articles (tạo hoặc cập nhật Wiki)
    Staff->>Backend: PUT /tickets/{id}/status=RESOLVED

    Note over Manager,Customer: Phase 6 — Verify & Close
    Backend->>Notif: notify Manager approve
    Manager->>Backend: GET /wiki-articles?ticketId={id} — kiểm tra Wiki
    Manager->>Backend: PUT /tickets/{id}/approve
    Backend->>Notif: notify Customer
    Customer->>Mobile: xem ticket resolved
    alt Customer đồng ý
        Customer->>Backend: POST /tickets/{id}/rate
        Backend->>DB: status=CLOSED + save CSAT
    else Customer chưa OK
        Customer->>Backend: PUT /tickets/{id}/reopen
        Backend->>DB: status=OPEN + increment reopenCount
        Backend->>Notif: notify Manager
    end
```

---

## 4. Ticket State Machine

Vòng đời 1 ticket. Mỗi state có role được phép chuyển trạng thái.

```mermaid
stateDiagram-v2
    [*] --> NEW : Customer tạo thủ công
    [*] --> OPEN : System auto-create từ alert<br/>(priority đã tính sẵn, bỏ qua NEW)

    NEW --> OPEN : Manager tiếp nhận<br/>(thêm vào queue)
    OPEN --> ASSIGNED : Manager xem xét priority<br/>+ assign Staff<br/>→ start SLA timer

    ASSIGNED --> IN_PROGRESS : Staff nhận & bắt đầu
    IN_PROGRESS --> IN_PROGRESS : Staff ghi log,<br/>comment Customer

    IN_PROGRESS --> WAITING_CUSTOMER : Staff cần thêm thông tin<br/>→ pause SLA có kiểm soát
    WAITING_CUSTOMER --> IN_PROGRESS : Customer comment/phản hồi<br/>→ System auto-resume SLA
    IN_PROGRESS --> WAITING_PARTS : Cần linh kiện/on-site<br/>→ pause SLA có lý do
    WAITING_PARTS --> IN_PROGRESS : Có linh kiện / tới lịch xử lý<br/>→ Staff resume thủ công

    IN_PROGRESS --> RESOLVED : Staff mark resolved
    IN_PROGRESS --> ESCALATED : Staff request escalate<br/>HOẶC System auto tại 2/3 SLA<br/>HOẶC SLA breach (P1/P2)

    ESCALATED --> ASSIGNED : Manager reassign<br/>tầng Staff cao hơn
    ESCALATED --> INCIDENT : Nhiều ticket liên quan<br/>hoặc rủi ro an toàn
    ESCALATED --> CLOSED_REJECTED : Manager reject ngoài scope

    INCIDENT --> ASSIGNED : Incident được điều phối<br/>về staff/lead staff

    RESOLVED --> CLOSED_PENDING_RATE : Manager approve<br/>(kiểm tra Wiki) · chờ Customer rate
    CLOSED_PENDING_RATE --> CLOSED : Customer rate<br/>hoặc auto-close sau 7 ngày
    RESOLVED --> IN_PROGRESS : Manager reject<br/>gửi lại Staff
    CLOSED_PENDING_RATE --> OPEN : Customer reopen<br/>(trong 7 ngày)

    CLOSED --> [*]
    CLOSED_REJECTED --> [*]

    note right of ASSIGNED
        SLA Timer:
        P1 Critical: 4h
        P2 High: 24h
        P3 Normal: 72h
    end note

    note right of WAITING_CUSTOMER
        SLA pause phải có lý do,
        thời điểm pause/resume,
        và người thực hiện.
        WAITING_CUSTOMER: auto-resume khi Customer comment.
        WAITING_PARTS/ONSITE: Staff resume thủ công.
    end note

    note right of ESCALATED
        Trigger:
        (1) Staff request escalate (thiếu skill/scope)
        (2) System auto tại 2/3 SLA (chưa có solution)
        (3) SLA breach 100% — P1/P2 auto, P3 xử lý theo chuẩn P2
        (4) Ticket reopen ≥ 2 lần
        Sau escalate: Staff cũ bị block hoàn toàn
        Staff mới (tầng trên) chịu trách nhiệm đóng ticket
    end note

    note right of INCIDENT
        Incident = 1 ticket "parent"
        điều phối nhiều ticket con
        liên quan cùng nguyên nhân.
        Manager link child tickets thủ công.
        Khi parent CLOSED → option
        auto-close toàn bộ child còn mở.
        Actor: Manager declare, Admin aware.
    end note
```

---

## 5. SLA Escalation Flow

3 track priority độc lập. Manager gán P1/P2/P3 khi triage — priority **không thay đổi** trong suốt vòng đời ticket. Staff escalate chủ động tại **2/3 SLA** — không chờ breach. Breach SLA → escalate thêm *nhân lực*, không phải đổi deadline.

> **Lưu ý:** Mũi tên `E2 → P1` và `E3 → P2` thể hiện *luồng xử lý tiếp theo* được áp chuẩn SLA cao hơn — **không có nghĩa là hệ thống tự động đổi priority**. Ticket vẫn ở trạng thái **ESCALATED**; chính **Manager** mới là người quyết định reassign senior Staff theo tầng. System chỉ auto-notify và auto-change status → ESCALATED.

```mermaid
flowchart LR
    Start([Ticket ASSIGNED<br/>SLA timer start])

    Start --> P1{P1 Critical<br/>4 giờ}
    P1 -->|Staff xử lý xong| OK1[✅ RESOLVED]
    P1 -->|80% SLA| W1[⚠️ Warning<br/>notify Staff + Manager]
    W1 --> P1
    P1 -->|Breach 100%| E1[🔺 Auto-escalate<br/>Manager + Senior Staff]

    Start --> P2{P2 High<br/>24 giờ}
    P2 -->|Staff xử lý xong| OK2[✅ RESOLVED]
    P2 -->|80% SLA| W2[⚠️ Warning<br/>notify Staff]
    W2 --> P2
    P2 -->|Breach 100%| E2[🔺 Escalate<br/>Manager reassign senior]

    Start --> P3{P3 Normal<br/>72 giờ}
    P3 -->|Staff xử lý xong| OK3[✅ RESOLVED]
    P3 -->|80% SLA| W3[⚠️ Reminder<br/>notify Staff]
    W3 --> P3
    P3 -->|Breach 100%| E3[🔺 Escalate — xử lý<br/>theo chuẩn P2<br/>Manager reassign senior]

    E1 --> Critical[🚨 Incident flag<br/>notify Admin nếu rủi ro an toàn]
    E2 --> P1
    E3 --> P2
```

---

## 6. Admin — Chi tiết Flow

Admin chỉ hoạt động mạnh ở **Phase 1 (Setup)** và **giám sát định kỳ**. Không tham gia daily operation. ThresholdConfig được định nghĩa riêng cho từng Battery Type — thay đổi ảnh hưởng toàn bộ asset cùng loại, Admin phải xác nhận.

| | |
|---|---|
| **Entry** | Login Web App với tài khoản super-admin |
| **Task chính** | User CRUD · Battery Type + ThresholdConfig per Type · Battery Asset · SLA rules · Audit log |
| **Tần suất** | Setup 1 lần + cập nhật khi có yêu cầu |
| **Quyền đặc biệt** | Disable account · Reset password · Restore DB · Incident visibility |

```mermaid
flowchart TD
    Start([Admin mở Web App]) --> L1[Nhập email + password]
    L1 --> L2{Credential OK?}
    L2 -->|Sai| L3[Hiện lỗi<br/>+ đếm số lần sai] --> L1
    L2 -->|Đúng| L4{2FA enabled?}
    L4 -->|Có| L5[Nhập OTP]
    L4 -->|Không| Dashboard
    L5 --> L6{OTP OK?}
    L6 -->|Sai| L5
    L6 -->|Đúng| Dashboard[Admin Dashboard]

    Dashboard --> T1[👥 User Management]
    Dashboard --> T2[🔋 Battery Config]
    Dashboard --> T6[🧾 Battery Asset]
    Dashboard --> T3[📋 SLA Rules]
    Dashboard --> T4[📊 Audit Log]
    Dashboard --> T5[⚙️ System Settings]

    T1 --> U1{Hành động}
    U1 -->|Tạo mới| U2[Chọn role<br/>Manager/Staff/Customer]
    U2 --> U3[Điền info<br/>email, SĐT, tên]
    U3 --> U4{Validate email<br/>unique?}
    U4 -->|Trùng| U3
    U4 -->|OK| U5[Generate password<br/>+ gửi email invite]
    U5 --> U6[Log audit event]
    U1 -->|Edit| U7[Sửa info / role]
    U1 -->|Disable| U8[Confirm + revoke token]
    U1 -->|Reset PWD| U9[Gửi link reset]

    T2 --> B1[Chọn loại pin<br/>LFP / NMC / ...]
    B1 --> B1b{Loại pin đã có?}
    B1b -->|Chưa| B1c[Tạo mới Battery Type<br/>tên + specs chung]
    B1b -->|Có rồi| B2
    B1c --> B2[Mở ThresholdConfig<br/>của loại pin này]
    B2 --> B3[Cấu hình ngưỡng cảnh báo<br/>theo từng thông số]
    B3 --> B4[V_min · V_max<br/>T_max · SOC_warning<br/>I_max · SOH_threshold...]
    B4 --> B5{Customer đang<br/>dùng loại pin này?}
    B5 -->|Có| B6[Warning:<br/>thay đổi sẽ affect N assets]
    B6 --> B7[Confirm → save ThresholdConfig]
    B5 -->|Không| B7

    T6 --> BA1[Create Battery Asset<br/>serial + battery type + size/vị trí]
    BA1 --> BA2[Link Customer<br/>owner/current user]
    BA2 --> BA3[Set install date<br/>warranty + nguồn đọc: IoT / BMS]
    BA3 --> BA4[View asset history<br/>alerts / tickets / sensor readings]

    T3 --> SR1[Set response time per priority<br/>+ Staff tier tương ứng]
    SR1 --> SR2[P1: 4h → Staff Tier 1<br/>P2: 24h → Staff Tier 2<br/>P3: 72h → Staff Tier 3]
    SR2 --> SR3[Set escalation threshold<br/>Escalate chủ động tại 2/3 SLA<br/>Breach 100% → auto-escalate]
    SR3 --> SR4[Set priority mapping<br/>anomaly type → priority<br/>dependency → nâng priority]

    T4 --> AL1[Filter by user/action/date]
    AL1 --> AL2[Xem chi tiết event]
    AL2 --> AL3[Export CSV nếu cần audit]

    T5 --> SY1[Email template]
    T5 --> SY2[Notification config]
    T5 --> SY3[Backup manual trigger]
    T5 --> SY4[Restore DB<br/>⚠️ destructive]
```

---

## 7. Manager — Chi tiết Flow

Manager là "điều phối viên" — hoạt động liên tục trong Phase 4 (Triage) và Phase 6 (Verify). Priority đã được System tính tự động — Manager xem xét ảnh/thông số Customer để xác nhận hoặc điều chỉnh, sau đó assign Staff đúng tầng. Approve phải kiểm tra Wiki.

| | |
|---|---|
| **Entry** | Login Web App khi có ticket mới hoặc kiểm tra định kỳ |
| **Task chính** | Xem xét priority tự động → Điều chỉnh nếu cần → Assign Staff theo tầng → Review Wiki + Approve resolution |
| **Căn cứ xem xét** | Thông số sensor của cục pin đó · Ảnh/video Customer gửi · Dependency report từ System |
| **Giới hạn** | Không tự đặt priority từ đầu — chỉ điều chỉnh từ priority đã tính · Không xử lý ticket trực tiếp |

```mermaid
flowchart TD
    Start([Manager login]) --> Dash[Manager Dashboard]

    Dash --> KPI[Xem KPI<br/>Open: X · Overdue: Y<br/>SLA breach: Z%]

    KPI --> Action{Có ticket<br/>cần xử lý?}
    Action -->|Không| Idle[Xem report<br/>hoặc chờ notification]
    Action -->|Có| Queue[Mở Ticket Queue<br/>ORDER BY priority · createdAt]

    Queue --> Pick[Mở ticket — xem priority<br/>đã tính tự động từ System]

    Pick --> Review1[Xem thông số sensor<br/>của cục pin đó<br/>V · I · T · SOC · SOH<br/>chart lịch sử bất thường]
    Review1 --> Review2[Xem ảnh / video<br/>Customer đã đính kèm<br/>+ mô tả sự cố]
    Review2 --> Review3[Xem Dependency report<br/>pin hỏng ảnh hưởng<br/>bao nhiêu pin khác?]

    Review3 --> PriorityCheck{Priority tự động<br/>có phù hợp không?}
    PriorityCheck -->|Phù hợp| Assign
    PriorityCheck -->|Cần điều chỉnh| AdjPriority[Điều chỉnh priority<br/>+ ghi lý do bắt buộc<br/>vào Activity Timeline]
    AdjPriority --> Assign

    Assign[Assign Staff theo tầng SLA] --> AC0[P1 → Staff Tier 1<br/>tổng thể hệ thống<br/>P2 → Staff Tier 2<br/>chuyên theo module<br/>P3 → Staff Tier 3<br/>chuyên sâu lĩnh vực]
    AC0 --> AC1{Staff tầng phù hợp<br/>còn capacity?}
    AC1 -->|Không| AC2[Xem workload<br/>toàn bộ Staff cùng tầng]
    AC2 --> AC3[Chọn Staff load thấp nhất<br/>trong tầng phù hợp]
    AC1 -->|Có| AC4[Xem skill match<br/>với loại pin / module]
    AC3 --> AC5[Confirm assign]
    AC4 --> AC5
    AC5 --> Notify[System: start SLA timer<br/>+ push notify Staff]

    Notify --> Wait{Chờ Staff xử lý}

    Wait -->|Staff mark RESOLVED| Verify[Review Maintenance Log<br/>+ Wiki đã tạo chưa?]
    Wait -->|Staff escalate chủ động<br/>tại 2/3 SLA| Escalate
    Wait -->|SLA breach| Escalate
    Wait -->|Reopen nhiều lần| Escalate

    Verify --> Check{Chất lượng xử lý OK?<br/>Wiki đã có?}
    Check -->|OK + có Wiki| Approve[Approve<br/>→ status CLOSED_PENDING_RATE]
    Check -->|Chưa ổn / thiếu Wiki| Reject[Reject<br/>→ gửi lại Staff IN_PROGRESS<br/>kèm note yêu cầu bổ sung]

    Reject --> Wait

    Escalate[🔺 Escalation Decision] --> ED1{Ticket đang ở<br/>Staff tầng nào?}
    ED1 -->|Tier 1 — P1 chưa resolve| ED6[🚨 Critical incident<br/>Notify Admin + toàn team]
    ED1 -->|Tier 2 — P2| ED5[Reassign Staff Tier 1<br/>nâng xử lý tổng thể]
    ED1 -->|Tier 3 — P3| ED4[Reassign Staff Tier 2<br/>chuyên module phù hợp]
    ED4 --> Notify
    ED5 --> Notify

    Approve --> End{Customer rate?}
    End -->|Rate good| Closed[CLOSED]
    End -->|Reopen| Queue
    End -->|No action 7 ngày| Closed

    Dash --> Report[📊 Reports]
    Report --> R1[Staff Performance theo tầng]
    Report --> R2[SLA Compliance]
    Report --> R3[Customer Satisfaction]
    Report --> R4[Export PDF/Excel]
```

---

## 8. Staff — Chi tiết Flow

Staff xử lý ticket theo mô hình băng chuyền — nhiều ticket song song. Nhiệm vụ: đọc thông tin → tra Wiki → đưa ra solution → ghi log → **tạo/cập nhật Wiki** → mark Resolved hoặc escalate chủ động. **Bắt buộc escalate tại 2/3 SLA** nếu chưa có solution — không chờ breach.

| | |
|---|---|
| **Entry** | Login Web App · nhận push notification ticket mới |
| **Task chính** | Đọc ticket → Tra Wiki → Đưa ra solution → Ghi log → Tạo/cập nhật Wiki → Resolved hoặc Escalate |
| **Tần suất** | Continuous — xử lý nhiều ticket song song (băng chuyền) |
| **Giới hạn** | Không đổi priority · Không approve resolution · Escalate sớm hơn là muộn hơn · Wiki bắt buộc trước Resolved |

> **Nguyên tắc escalate chủ động:** Mốc cứng tại **2/3 SLA** (P1: ~2h40 · P2: 16h · P3: 48h) mà chưa hoàn thành → bắt buộc escalate ngay. Ghi lý do + % SLA đã dùng.

```mermaid
flowchart TD
    Start([Staff login]) --> Dash[Staff Dashboard<br/>SLA countdown hiển thị<br/>real-time trên mỗi ticket]
    Dash --> MyT[My Tickets<br/>sắp xếp theo SLA còn lại]

    MyT --> N1{Ticket nào<br/>ưu tiên?}
    N1 -->|P1 / SLA ít nhất| Accept[Mở ticket — P1 hoặc<br/>ticket gần hết SLA nhất]
    N1 -->|Xem đang làm| N2[Tiếp tục ticket<br/>đang IN_PROGRESS]

    Accept --> Read[Đọc toàn bộ thông tin ticket<br/>mô tả Customer + ảnh<br/>battery asset + lịch sử alert]
    Read --> SLACheck{Còn bao nhiêu<br/>% SLA?}
    SLACheck -->|"> 2/3 SLA còn"| Proceed[Tiến hành xử lý<br/>trong zone an toàn]
    SLACheck -->|"< 1/2 SLA còn<br/>chưa rõ hướng"| EarlyEsc[⚡ Escalate sớm<br/>không chờ tới breach]

    Proceed --> KB{Wiki có trường hợp<br/>tương tự không?}
    KB -->|Có| WikiSol[Đọc Wiki solution<br/>áp dụng hướng xử lý đã ghi]
    KB -->|Không| ManualDiag[Phân tích từ dữ liệu ticket<br/>battery history + alert gốc]

    WikiSol --> CanSolve{Đủ cơ sở đưa ra<br/>solution không?}
    ManualDiag --> CanSolve

    CanSolve -->|Có| WriteSol[Viết solution vào ticket<br/>hướng xử lý cụ thể]
    CanSolve -->|Không / Vượt skill| EscDecide

    WriteSol --> LogEntry[Ghi Maintenance Log<br/>nguyên nhân + solution đề xuất]
    LogEntry --> WikiCheck{Wiki đã có<br/>trường hợp này chưa?}
    WikiCheck -->|Đã có| WikiUpdate[Bổ sung vào Wiki hiện có<br/>gắn mã Ticket]
    WikiCheck -->|Chưa có| WikiCreate[Tạo Wiki mới<br/>B1→B2→B3 · ảnh đính kèm<br/>mã lỗi gắn mã Ticket]
    WikiUpdate --> Resolve
    WikiCreate --> Resolve
    Resolve[Mark RESOLVED<br/>+ tóm tắt xử lý] --> WaitApprove{Manager review<br/>+ kiểm tra Wiki}
    WaitApprove -->|Approve| Done[✅ CLOSED_PENDING_RATE]
    WaitApprove -->|Reject — thiếu Wiki<br/>hoặc solution chưa rõ| Read

    EscDecide{Còn trong<br/>window 1/2 → 2/3 SLA?}
    EscDecide -->|Còn thời gian — thử tiếp| Proceed
    EscDecide -->|Đã qua 2/3 SLA<br/>hoặc không tự tin| Escalate

    EarlyEsc --> Escalate
    Escalate[🔺 Request Escalation] --> EscReason[Ghi lý do bắt buộc<br/>— thiếu skill / vượt scope<br/>— đã qua 2/3 SLA chưa có solution<br/>— % SLA đã dùng: X%]
    EscReason --> EscSend[Submit → Manager nhận<br/>ticket vào queue của Manager]
    EscSend --> BackDash[Back to Dashboard<br/>xử lý ticket tiếp theo]

    MyT --> SLAMon[🕐 SLA Monitor — real-time<br/>tất cả ticket đang mở<br/>màu: xanh / vàng / đỏ]
    SLAMon --> Threshold{"Ticket nào đang<br/>ở vùng 1/2 → 2/3 SLA?"}
    Threshold -->|Có và chưa có solution| EscDecide
    Threshold -->|Tất cả trong zone an toàn| MyT
```

---

## 9. Customer — Chi tiết Flow

Customer sử dụng Mobile App — hành vi chia làm 3 loại: **monitoring daily**, **react-to-alert**, và **ticket management**.

| | |
|---|---|
| **Entry** | Mobile App (iOS/Android) · Push notification |
| **Task chính** | Xem pin · Nhận cảnh báo · Tạo/theo dõi ticket · Rate service |
| **Tần suất** | Daily check + khi có alert |
| **Self-service** | Xem history · Export data · Cài đặt notification · Quản lý thiết bị pin |

```mermaid
flowchart TD
    Start([Mở Mobile App]) --> First{Lần đầu?}

    First -->|Có| Reg[Đăng ký<br/>email/SĐT]
    Reg --> OTP[Nhập OTP]
    OTP --> Link[Link thiết bị pin<br/>scan QR / serial]
    Link --> Home

    First -->|Không| Login[Login<br/>email + password]
    Login --> LC{OK?}
    LC -->|Sai| Login
    LC -->|Đúng| Home[Home Dashboard]

    Home --> Asset[Chọn Battery Asset<br/>nếu có nhiều thiết bị]
    Asset --> Mon[📊 Daily Monitoring]
    Mon --> View[Xem real-time<br/>V · I · T · SOC %]
    View --> Health{Trạng thái?}
    Health -->|Normal 🟢| Idle[Idle, đóng app]
    Health -->|Warning 🟡| CheckChart[Xem chart<br/>7d/30d]
    Health -->|Critical 🔴| AlertFlow

    CheckChart --> Decide{Có cần báo?}
    Decide -->|Không| Idle
    Decide -->|Có| CreateT

    Home --> Alert[🔔 Push notification]
    Alert --> AlertFlow[Mở alert<br/>xem lý do + ngưỡng vượt<br/>+ thông số cục pin]
    AlertFlow --> AS{System đã<br/>tạo ticket chưa?}
    AS -->|Đã tạo tự động| GoTrack[Vào xem ticket<br/>đang được xử lý]
    AS -->|Chưa — chỉ cảnh báo<br/>thông tin, chưa ảnh hưởng| InfoOnly[Đọc thông tin<br/>theo dõi tiếp]
    GoTrack --> Track
    InfoOnly --> Idle

    CreateT[Tạo Ticket thủ công] --> CT0[Chọn battery asset<br/>đúng serial/thiết bị]
    CT0 --> CT1[Chọn loại sự cố<br/>Charging · Overheat · No power ...]
    CT1 --> CT2[Mô tả chi tiết hiện tượng]
    CT2 --> CT3[Upload ảnh/video<br/>tối đa 5 files<br/>⚠️ ảnh giúp Manager xem xét chính xác hơn]
    CT3 --> CT4[Xem priority gợi ý<br/>do System tính tự động<br/>Customer không tự chọn priority]
    CT4 --> CT5[Submit]
    CT5 --> CT6[Nhận ticket ID<br/>+ thời gian phản hồi dự kiến<br/>theo priority]

    CT6 --> Track

    Home --> MyT[📋 My Tickets]
    MyT --> Track[Xem tiến trình<br/>OPEN → IN_PROGRESS → RESOLVED]

    Track --> TS{Status hiện tại?}
    TS -->|Staff hỏi| Reply[Trả lời comment<br/>+ ảnh bổ sung]
    TS -->|WAITING_CUSTOMER| Reply
    TS -->|IN_PROGRESS lâu| ChaseCheck{Quá SLA?}
    TS -->|RESOLVED/PENDING RATE| ReviewRes

    Home --> WaitPush[🔔 Push: Staff cần thông tin<br/>từ bạn · ticket đang chờ]
    WaitPush --> OpenTicket[Mở ticket từ notification<br/>xem comment Staff]
    OpenTicket --> Reply

    ChaseCheck -->|Có| Chase[Nhắc qua comment<br/>hoặc liên hệ hotline]
    ChaseCheck -->|Chưa| Track

    Reply --> Track
    Chase --> Track

    ReviewRes[Review kết quả xử lý<br/>đọc maintenance log] --> Verdict{Hài lòng?}
    Verdict -->|Có| Rate[Rate 1-5 sao<br/>+ comment]
    Rate --> Closed[✅ Ticket CLOSED]
    Verdict -->|Không| ReopenCheck{Trong 7 ngày?}
    ReopenCheck -->|Có| Reopen[Reopen<br/>mô tả vấn đề còn]
    ReopenCheck -->|Không| NewTicket[Tạo ticket mới]
    Reopen --> Track
    NewTicket --> CreateT
    Verdict -->|Không action 7d| Auto[System auto-close]

    Home --> Profile[👤 Profile]
    Profile --> P1[Sửa thông tin]
    Profile --> P2[Đổi mật khẩu]
    Profile --> P3[Notification settings<br/>- Push on/off<br/>- Email digest<br/>- Alert threshold cá nhân]
    Profile --> P4[My Battery Assets<br/>serial, warranty, history]
```

---

## 10. Business Rules

| Rule | Mô tả |
|------|-------|
| BR-01 | Ticket phải gắn với Battery Asset (assetId bắt buộc) |
| BR-02 | Alert critical có thể auto-create ticket nếu chưa có ticket đang mở cho cùng asset và có ảnh hưởng lan sang pin khác |
| BR-03 | Dedup alert: cùng asset + anomaly type + time window → append vào ticket hiện tại, không tạo mới |
| BR-04 | SLA pause phải có lý do hợp lệ (WAITING_CUSTOMER / WAITING_PARTS / WAITING_ONSITE_SCHEDULE) và ghi timeline |
| BR-05 | Staff chỉ mark RESOLVED; Manager mới approve → CLOSED_PENDING_RATE |
| BR-06 | Customer chỉ được reopen trong 7 ngày sau resolved/closed pending |
| BR-07 | Reopen ≥ 2 lần → System auto-cảnh báo Manager để review hoặc escalate senior |
| BR-08 | Mọi thay đổi quan trọng (assign, status, priority, pause SLA, approve, reject, reopen) phải lưu actor + timestamp + reason |
| BR-09 | ThresholdConfig gắn theo Battery Type — thay đổi ngưỡng ảnh hưởng toàn bộ asset cùng loại, Admin phải xác nhận trước khi save |
| BR-10 | Manager assign Staff đúng tầng: P1→Tier 1, P2→Tier 2, P3→Tier 3. Escalate = chuyển lên tầng cao hơn |
| BR-11 | Wiki là quy trình mềm (không enforce cứng). Nếu lỗi đã có Wiki → Staff link ticket vào Wiki sẵn có; nếu chưa có → khuyến khích tạo Wiki mới. Manager có thể reject nếu thiếu hướng dẫn, không bắt buộc mỗi ticket phải tạo Wiki mới |
| BR-12 | Tầng nào nhận ticket thì tầng đó đóng. System auto-trigger ESCALATED tại 2/3 SLA nếu chưa RESOLVED. Sau escalate, Staff cũ bị block hoàn toàn — Staff mới (tầng trên) chịu trách nhiệm đóng ticket. Không có ngoại lệ |

### Priority & SLA

| Priority | SLA | Trigger | Staff tier | Breach action |
|----------|-----|---------|------------|---------------|
| P1 Critical | 4h | Rủi ro an toàn, mất điện, nguy cơ hư hại | Tier 1 (tổng thể) | Manager reassign Senior + notify Admin → Critical Incident nếu vẫn fail |
| P2 High | 24h | Suy giảm hiệu năng rõ rệt, lỗi sạc/xả | Tier 2 (theo module) | Manager reassign Tier 1 (priority giữ P2) |
| P3 Normal | 72h | Bất thường nhẹ, câu hỏi vận hành | Tier 3 (chuyên sâu) | Escalate xử lý theo chuẩn P2 — Manager reassign senior |

> **Priority do System tính tự động** từ classification + dependency. Manager **xem xét và có thể điều chỉnh 1 lần** khi triage (OPEN → ASSIGNED) — phải ghi lý do vào Activity Timeline. Sau đó **không thay đổi** trong toàn bộ vòng đời ticket. Breach SLA → escalate thêm *nhân lực/cấp bậc*, không phải đổi deadline hay priority. Giữ priority cố định đảm bảo audit trail chính xác và SLA report không bị skew.

### Entity bổ sung nên có trong SRS

| Entity | Mục đích | Trường dữ liệu chính |
|--------|----------|----------------------|
| BatteryType | Loại pin (LFP, NMC…) — căn cứ để áp ThresholdConfig | typeId, name, chemistry, nominalVoltage, nominalCapacity |
| ThresholdConfig | Ngưỡng cảnh báo gắn theo Battery Type, do Admin cấu hình | configId, batteryTypeId, voltageMin, voltageMax, tempMax, socWarning, iMax, sohThreshold |
| BatteryAsset | Đại diện một bộ pin cụ thể của Customer | assetId, serialNumber, batteryTypeId, customerId, installDate, warrantyStatus, location, size, dataSource |
| Alert | Lưu cảnh báo sinh ra từ dữ liệu pin | alertId, assetId, anomalyType, severity, thresholdValue, actualValue, detectedAt, status |
| TicketActivity | Lưu timeline thao tác trên ticket | activityId, ticketId, actorId, actionType, oldValue, newValue, reason, createdAt |
| SlaTimer | Theo dõi deadline, pause/resume và breach | ticketId, priority, startedAt, dueAt, pausedAt, totalPausedMinutes, breachAt, status |
| WikiArticle | Ghi lại quy trình xử lý sau mỗi ticket — Staff bắt buộc tạo/cập nhật khi resolve | wikiId, wikiCode, ticketId, category, anomalyType, steps (B1→B2→B3), imageUrls, createdBy, updatedAt, occurrenceCount |
| CustomerFeedback | Lưu rating và đánh giá sau xử lý | feedbackId, ticketId, rating, comment, createdAt |

---

*Project GSU26SE55 · Core Business Flow · SRS-ready · SE-only scope*
