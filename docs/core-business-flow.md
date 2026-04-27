# GSU26SE55 — Core Business Flow

**Quy trình nghiệp vụ cốt lõi** theo 4 role · Scope: SE-only · ITIL Ticket & SLA Management

---

## Vai trò trong hệ thống

| Role | Màu | Mô tả |
|------|-----|-------|
| Admin | 🔴 | Setup/Config — tạo account, cấu hình pin, SLA rules |
| Customer | 🟣 | Tạo ticket, theo dõi tiến trình |
| Manager | 🔵 | Assign, approve, escalate |
| Staff | 🟢 | Xử lý ticket, ghi maintenance log |
| System | 🟡 | Auto alert / SLA timer |

---

## 1. Tổng quan 6 Phase

Quy trình tổng thể chia làm 6 phase. Mỗi phase có 1 role "owner" chính, role khác tham gia phụ.

| # | Phase | Mô tả | Owner |
|---|-------|-------|-------|
| ① | Setup & Configuration | Tạo account, cấu hình loại pin, set ngưỡng cảnh báo, định nghĩa SLA rules P1/P2/P3 | ADMIN |
| ② | Monitoring & Detection | Customer theo dõi pin. System auto-check ngưỡng (mỗi pin có ngưỡng riêng), sinh cảnh báo khi bất thường. IoT data sẽ được tích hợp ở giai đoạn sau | CUSTOMER + SYSTEM |
| ③ | Ticket Creation | Customer tạo ticket thủ công, gắn với pin cụ thể. System có thể auto-tạo ticket từ alert khi tích hợp IoT | CUSTOMER / SYSTEM |
| ④ | Triage & Assignment | Manager review ticket, set priority, assign cho Staff phù hợp. SLA timer bắt đầu | MANAGER |
| ⑤ | Resolution | Staff xử lý: cập nhật status, ghi log, liên hệ customer, mark Resolved hoặc Request Escalation | STAFF |
| ⑥ | Verification & Closure | Manager approve, Customer đánh giá (rate/reopen). Ticket chính thức Closed | MANAGER + CUSTOMER |

---

## 2. Swimlane End-to-End

Mỗi lane là 1 role. Mũi tên cắt ngang lane = handoff giữa các role. Đây là flow chính của hệ thống.

```mermaid
flowchart TB
    Start([🔔 Bắt đầu chu kỳ vận hành])

    subgraph ADMIN["🔴 ADMIN LANE — Setup 1 lần"]
        direction LR
        A1[Tạo accounts<br/>Manager/Staff/Customer]
        A2[Cấu hình pin<br/>thông số kỹ thuật + ngưỡng cảnh báo]
        A3[Định nghĩa SLA rules<br/>P1/P2/P3]
        A1 --> A2 --> A3
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
        S3[Auto-tạo alert<br/>+ push Customer]
        S4[Start SLA timer<br/>khi ticket assigned]
        S5{SLA breach<br/>sắp xảy ra?}
        S6[Cảnh báo Manager<br/>+ Staff]
        S1 --> S2
        S2 -->|Có| S3
        S2 -->|Không| S1
        S4 --> S5
        S5 -->|Có| S6
    end

    subgraph MANAGER["🔵 MANAGER LANE — Web App"]
        direction LR
        M1[Nhận ticket<br/>vào queue]
        M2[Đánh giá priority<br/>P1/P2/P3]
        M3[Assign cho Staff<br/>phù hợp]
        M4{Staff mark<br/>Resolved?}
        M5[Review & Approve]
        M6[Reject<br/>gửi lại Staff]
        M7{Cần escalate?}
        M8[Reassign Senior<br/>hoặc Escalate L3]
        M1 --> M2 --> M3
        M4 -->|Yes| M5
        M4 -->|No sau SLA| M7
        M7 -->|Yes| M8
    end

    subgraph STAFF["🟢 STAFF LANE — Web App"]
        direction LR
        T1[Nhận notification<br/>ticket mới]
        T2[Update status<br/>In Progress]
        T3[Comment với Customer<br/>nếu cần thông tin]
        T4[Ghi Maintenance Log]
        T5{Xử lý được?}
        T6[Mark Resolved]
        T7[Request Escalation<br/>gửi Manager]
        T1 --> T2 --> T3 --> T4 --> T5
        T5 -->|Được| T6
        T5 -->|Không| T7
    end

    Start --> A1
    A3 -.setup xong.-> C1
    A3 -.-> S1
    C3 --> M1
    C3 --> C4
    S3 --> C2
    S6 -.SLA breach.-> M7
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
    Admin->>Backend: POST /users (tạo Manager/Staff/Customer · gửi email invite)
    Admin->>Backend: POST /batteries (đăng ký pin — tên, serial, thông số KT, ngưỡng)
    Admin->>Backend: PUT /batteries/{id}/assign (gán pin cho Customer)
    Admin->>Backend: POST /sla-rules (P1/P2/P3)

    Note over Customer,Mobile: Phase 1.5 — Customer kích hoạt / reset password
    Customer->>Mobile: Mở app · nhập OTP từ email Admin
    Mobile->>Backend: POST /auth/activate (otp, newPassword)
    Backend-->>Mobile: JWT token
    Note over Customer,Mobile: (Nếu quên mật khẩu sau này)
    Customer->>Mobile: Nhập email → nhận link reset
    Mobile->>Backend: POST /auth/forgot-password (email)
    Mobile->>Backend: POST /auth/reset-password (token, newPassword)

    Note over Customer,DB: Phase 2 — Monitoring & Alert
    Customer->>Mobile: Chọn pin từ card list
    Mobile->>Backend: GET /batteries/{id}/realtime
    Backend->>DB: query latest metrics
    DB-->>Backend: V, I, T, SOC
    Backend-->>Mobile: data
    Mobile-->>Customer: hiển thị chart

    Backend->>Backend: scheduled check ngưỡng
    Backend->>Notif: push alert nếu vượt ngưỡng
    Notif-->>Customer: 🔔 cảnh báo

    Note over Customer,Manager: Phase 3–4 — Create & Assign
    Customer->>Mobile: Tạo ticket
    Mobile->>Backend: POST /tickets
    Backend->>DB: lưu ticket (status=NEW)
    Backend->>Notif: notify Manager
    Notif-->>Manager: ticket mới

    Manager->>Backend: GET /tickets?status=NEW
    Manager->>Backend: PUT /tickets/{id}/status=OPEN (tiếp nhận)
    Backend->>DB: update status=OPEN
    Manager->>Backend: PUT /tickets/{id}/assign (staffId, priority)
    Backend->>DB: update status=ASSIGNED + start SLA timer
    Backend->>Notif: notify Staff
    Notif-->>Staff: ticket được giao

    Note over Staff,Customer: Phase 5 — Resolution
    Staff->>Backend: PUT /tickets/{id}/status=IN_PROGRESS
    Staff->>Backend: POST /tickets/{id}/comments
    Backend->>Notif: notify Customer
    Notif-->>Customer: reply từ Staff

    Staff->>Backend: POST /tickets/{id}/maintenance-log
    Staff->>Backend: PUT /tickets/{id}/status=RESOLVED

    Note over Manager,Customer: Phase 6 — Verify & Close
    Backend->>Notif: notify Manager approve
    Manager->>Backend: PUT /tickets/{id}/approve
    Backend->>Notif: notify Customer
    Customer->>Mobile: xem ticket resolved
    alt Customer đồng ý
        Customer->>Backend: POST /tickets/{id}/rate
        Backend->>DB: status=CLOSED
    else Customer chưa OK
        Customer->>Backend: PUT /tickets/{id}/reopen
        Backend->>DB: status=OPEN
        Backend->>Notif: notify Manager
    end
```

---

## 4. Ticket State Machine

Vòng đời 1 ticket. Mỗi state có role được phép chuyển trạng thái.

```mermaid
stateDiagram-v2
    [*] --> NEW : Customer tạo / System auto-create

    NEW --> OPEN : Manager tiếp nhận<br/>(thêm vào queue)
    OPEN --> ASSIGNED : Manager assign Staff<br/>+ set priority<br/>→ start SLA timer

    ASSIGNED --> IN_PROGRESS : Staff nhận & bắt đầu
    IN_PROGRESS --> IN_PROGRESS : Staff ghi log,<br/>comment Customer

    IN_PROGRESS --> RESOLVED : Staff mark resolved
    IN_PROGRESS --> ESCALATED : Staff request escalate<br/>HOẶC SLA breach

    ESCALATED --> ASSIGNED : Manager reassign<br/>senior staff
    ESCALATED --> CLOSED_REJECTED : Manager reject ngoài scope

    RESOLVED --> CLOSED_PENDING_RATE : Manager approve
    CLOSED_PENDING_RATE --> CLOSED : Customer rate / auto 7 ngày
    CLOSED_PENDING_RATE --> OPEN : Customer reopen (trong 7 ngày)
    RESOLVED --> IN_PROGRESS : Manager reject<br/>gửi lại Staff

    CLOSED --> [*]
    CLOSED_REJECTED --> [*]

    note right of ASSIGNED
        SLA Timer bắt đầu khi ASSIGNED.
        P1: 4h · P2: 24h · P3: 72h
        Hiệu lực = tổng time - time ở ESCALATED
    end note

    note right of ESCALATED
        Trigger:
        (1) Staff không xử lý nổi
        (2) SLA sắp breach (80%)
        (3) SLA đã breach
        → SLA timer PAUSE khi vào ESCALATED
        → RESUME khi reassign về ASSIGNED
    end note
```

---

## 5. SLA Escalation Flow

3 track priority độc lập. Manager gán P1/P2/P3 khi triage — priority **không thay đổi** trong suốt vòng đời ticket. Breach SLA → escalate thêm *nhân lực*, không phải đổi deadline.

```mermaid
flowchart TB
    Start([Ticket ASSIGNED · Manager gán Priority · SLA timer bắt đầu])

    Start --> track1 & track2 & track3

    subgraph track1["🔴 P1 — Critical · SLA: 4 giờ"]
        direction LR
        P1a[Staff xử lý] -->|Resolved| P1ok[✅ RESOLVED]
        P1a -->|80% ≈ 3.2h| P1w[⚠️ Warn Staff + Manager]
        P1w --> P1a
        P1a -->|Breach 100%| P1b[🔺 Manager reassign Senior<br/>+ notify Admin]
        P1b -->|Resolved| P1ok
        P1b -->|Vẫn fail| P1cr[🚨 Critical Incident<br/>All-hands · gắn cờ]
    end

    subgraph track2["🟡 P2 — High · SLA: 24 giờ"]
        direction LR
        P2a[Staff xử lý] -->|Resolved| P2ok[✅ RESOLVED]
        P2a -->|80% ≈ 19h| P2w[⚠️ Warn Staff]
        P2w --> P2a
        P2a -->|Breach 100%| P2b[🔺 Manager reassign<br/>Senior nếu cần]
        P2b -->|Resolved| P2ok
        P2b -->|Vẫn fail| P2cr[🔺 Escalate → P1 resources]
    end

    subgraph track3["🟢 P3 — Standard · SLA: 72 giờ"]
        direction LR
        P3a[Staff xử lý] -->|Resolved| P3ok[✅ RESOLVED]
        P3a -->|80% ≈ 58h| P3w[⚠️ Warn Staff]
        P3w --> P3a
        P3a -->|Breach 100%| P3b[🔺 Manager review<br/>+ bàn giao nếu cần]
        P3b -->|Resolved| P3ok
        P3b -->|Vẫn fail| P3cr[Escalate → P2 resources]
    end
```

---

## 6. Admin — Chi tiết Flow

Admin chỉ hoạt động mạnh ở **Phase 1 (Setup)** và **giám sát định kỳ**. Không tham gia daily operation.

| | |
|---|---|
| **Entry** | Login Web App với tài khoản super-admin |
| **Task chính** | User CRUD · Battery config · SLA rules · Audit log |
| **Tần suất** | Setup 1 lần + cập nhật khi có yêu cầu |
| **Quyền đặc biệt** | Disable account · Reset password · Restore DB |

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
    Dashboard --> T2[🔋 Quản lý Pin]
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

    T2 --> B1[Thêm pin mới]
    B1 --> B2[Nhập thông tin<br/>tên, serial, vị trí lắp đặt]
    B2 --> B3[Nhập thông số kỹ thuật<br/>capacity, voltage range]
    B3 --> B4[Set ngưỡng cảnh báo riêng<br/>V_min, V_max, T_max, SOC_warning]
    B4 --> B5{Gán cho Customer<br/>ngay?}
    B5 -->|Có| B6[Chọn Customer]
    B5 -->|Lưu trước| B7[Lưu pin vào hệ thống]
    B6 --> B7
    T2 --> B8[Sửa thông số / ngưỡng pin]
    T2 --> B9[Deactivate pin]

    T3 --> SR1[Set response time<br/>per level]
    SR1 --> SR2["P1: 4h (Critical)<br/>P2: 24h (High)<br/>P3: 72h (Standard)"]
    SR2 --> SR3[Set escalation rules<br/>auto-escalate khi breach %]
    SR3 --> SR4[Set priority mapping<br/>anomaly type → level]

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

Manager là "điều phối viên" — hoạt động liên tục trong Phase 4 (Triage) và Phase 6 (Verify). Quyết định priority, staff assignment, và escalation.

| | |
|---|---|
| **Entry** | Login Web App khi có ticket mới hoặc kiểm tra định kỳ |
| **Task chính** | Triage ticket · Assign Staff · Approve resolution · Handle escalation |
| **Tần suất** | Daily — check dashboard mỗi 2–4h |
| **Quyền đặc biệt** | Reassign · Approve/Reject · Escalate L2→L3 · Export report |

```mermaid
flowchart TD
    Start([Manager login]) --> Dash[Manager Dashboard]

    Dash --> KPI[Xem KPI<br/>Open: X · Overdue: Y<br/>SLA breach: Z%]
    KPI --> Action{Có ticket<br/>cần xử lý?}
    Action -->|Không| Idle[Xem report<br/>hoặc chờ notification]
    Action -->|Có| Queue[Mở Ticket Queue]

    Queue --> Filter[Filter<br/>status=OPEN ORDER BY<br/>priority, createdAt]
    Filter --> Pick[Pick ticket đầu tiên]
    Pick --> Review[Đọc mô tả Customer<br/>+ xem battery history<br/>+ xem alert gốc]

    Review --> Priority{Đánh giá<br/>Priority}
    Priority -->|Critical / Safety| SetP1[Set P1 — Critical<br/>SLA 4h + notify Admin]
    Priority -->|Degradation đáng kể| SetP2[Set P2 — High<br/>SLA 24h]
    Priority -->|Bất thường nhẹ| SetP3[Set P3 — Standard<br/>SLA 72h]

    SetP1 --> Assign
    SetP2 --> Assign
    SetP3 --> Assign

    Assign[Chọn Staff assign] --> AC1{Staff còn capacity?}
    AC1 -->|Không| AC2[Xem workload<br/>tất cả Staff]
    AC2 --> AC3[Chọn Staff load thấp nhất]
    AC1 -->|Có| AC4[Xem skill match<br/>theo loại sự cố]
    AC3 --> AC5[Confirm assign]
    AC4 --> AC5
    AC5 --> Notify[System: start SLA timer<br/>+ push notify Staff]

    Notify --> Wait{Chờ Staff xử lý}
    Wait -->|Staff mark RESOLVED| Verify[Review Maintenance Log<br/>+ lịch sử comment]
    Wait -->|SLA warning 80%| Warn[Nhắc Staff<br/>qua comment]
    Wait -->|SLA breach| Escalate

    Verify --> Check{Chất lượng xử lý OK?}
    Check -->|OK| Approve[Approve<br/>→ status CLOSED_PENDING_RATE]
    Check -->|Chưa ổn| Reject[Reject<br/>→ gửi lại Staff IN_PROGRESS<br/>kèm note]

    Warn --> Wait
    Reject --> Wait

    Escalate[🔺 Escalation Decision] --> ED3{Priority hiện tại}
    ED3 -->|P1| ED4[🚨 Critical Incident<br/>Notify Admin + All-hands]
    ED3 -->|P2| ED5[Escalate Tier-2<br/>Reassign Senior Staff + notify Admin]
    ED3 -->|P3| ED6[Manager review<br/>Reassign nếu cần]
    ED4 --> Wait
    ED5 --> Wait
    ED6 --> Wait

    Approve --> End{Customer rate?}
    End -->|Rate good| Closed[CLOSED]
    End -->|Reopen| Queue
    End -->|No action 7 ngày| Closed

    Dash --> Report[📊 Reports]
    Report --> R1[Staff Performance]
    Report --> R2[SLA Compliance]
    Report --> R3[Export PDF/Excel]
```

---

## 8. Staff — Chi tiết Flow

Staff là người trực tiếp xử lý ticket — hoạt động chính ở Phase 5 (Resolution). Cần document kỹ mỗi bước vì sẽ được Manager review.

| | |
|---|---|
| **Entry** | Login Web App · nhận push notification ticket mới |
| **Task chính** | Diagnose · Liên hệ Customer · Apply solution · Ghi log |
| **Tần suất** | Continuous — xử lý multiple tickets song song |
| **Giới hạn** | Không đổi priority · Không approve · Phải escalate khi vượt skill |

```mermaid
flowchart TD
    Start([Staff login]) --> Dash[Staff Dashboard]
    Dash --> MyT[My Tickets]

    MyT --> N1{Có ticket mới?}
    N1 -->|Không| N2[Xem ticket đang làm]
    N1 -->|Có| Accept[Mở ticket detail]

    Accept --> Read[Đọc mô tả +<br/>xem ảnh từ Customer]
    Read --> Ctx[Xem context<br/>battery history 7d<br/>+ alert gốc]
    Ctx --> Start2[Update status<br/>IN_PROGRESS]

    Start2 --> Diag{Đủ info<br/>để chẩn đoán?}

    Diag -->|Thiếu info| Ask[Comment hỏi Customer<br/>ví dụ: thời điểm, hiện tượng cụ thể]
    Ask --> WaitR{Customer reply?}
    WaitR -->|Timeout 24h| Remind[Nhắc Customer lần 2]
    WaitR -->|Reply| Read
    Remind -->|Reply| Read
    Remind -->|Vẫn không reply 24h| NoReply[Escalate / đóng ticket<br/>Customer không phản hồi]
    NoReply --> EscSend

    Diag -->|Đủ info| Hypo[Đưa giả thuyết nguyên nhân]
    Hypo --> Solve{Có thể xử lý<br/>remote không?}

    Solve -->|Remote OK| Remote[Hướng dẫn Customer<br/>qua comment/video]
    Remote --> Check1{Customer confirm<br/>đã OK?}
    Check1 -->|Có| LogRemote[Ghi Maintenance Log<br/>loại: Remote Support]
    Check1 -->|Không| Hypo

    Solve -->|Cần on-site| OnSite[Lên lịch on-site<br/>+ thông báo Customer]
    OnSite --> Visit[Tới hiện trường]
    Visit --> Exec[Thực hiện bảo trì<br/>thay linh kiện nếu cần]
    Exec --> LogOnSite[Ghi Maintenance Log<br/>loại: On-site<br/>+ upload ảnh before/after]

    Solve -->|Không xử lý nổi| Escalate[Request Escalation]
    Escalate --> EscReason[Ghi lý do<br/>- Thiếu skill<br/>- Cần lead support<br/>- Ngoài scope]
    EscReason --> EscSend[Submit → chuyển Manager]
    EscSend --> WaitMgr{Manager reassign?}
    WaitMgr -->|Ticket chuyển đi| BackDash[Back to Dashboard]

    LogRemote --> Resolve
    LogOnSite --> Resolve

    Resolve[Mark RESOLVED<br/>+ summary xử lý] --> WaitApprove{Manager approve?}
    WaitApprove -->|Approve| Done[✅ Ticket CLOSED]
    WaitApprove -->|Reject + Manager note| RejNote[Đọc lý do reject<br/>của Manager]
    RejNote --> Diag

    Start2 --> SLA[Check SLA countdown<br/>ở banner]
    SLA --> SLAWarn{80% SLA?}
    SLAWarn -->|Có| Urgent[⚠️ Ưu tiên xử lý<br/>notify Manager]
    Urgent --> Diag
    SLAWarn -->|Chưa| Diag
```

---

## 9. Customer — Chi tiết Flow

Customer sử dụng Mobile App — hành vi chia làm 3 loại: **monitoring daily**, **react-to-alert**, và **ticket management**.

| | |
|---|---|
| **Entry** | Mobile App (iOS/Android) · Push notification |
| **Task chính** | Xem pin · Nhận cảnh báo · Tạo/theo dõi ticket · Rate service |
| **Tần suất** | Daily check + khi có alert |
| **Self-service** | Xem history · Export data · Cài đặt notification |

```mermaid
flowchart TD
    Start([Mở Mobile App]) --> First{Lần đầu /<br/>chưa kích hoạt?}

    First -->|Chưa kích hoạt| Act[Nhập OTP từ email<br/>Admin gửi]
    Act --> SetPwd[Đặt mật khẩu]
    SetPwd --> Home

    First -->|Đã có| Login[Login<br/>email + password]
    Login --> LC{OK?}
    LC -->|Sai| ForgotQ{Quên mật khẩu?}
    ForgotQ -->|Không| Login
    ForgotQ -->|Có| ForgotPwd[Nhập email<br/>nhận link reset]
    ForgotPwd --> ResetLink[Mở link trong email<br/>đặt mật khẩu mới]
    ResetLink --> Login
    LC -->|Đúng| Home[Home Dashboard<br/>Card list các pin<br/>được Admin gán]
    Home --> PickBatt{Chọn pin}
    PickBatt --> BattScreen[Battery Screen]

    BattScreen --> Mon[📊 Daily Monitoring]
    Mon --> View[Xem real-time<br/>V · I · T · SOC %]
    View --> Health{Trạng thái?}
    Health -->|Normal 🟢| Idle[Idle, đóng app]
    Health -->|Warning 🟡| CheckChart[Xem chart<br/>7d/30d]
    Health -->|Critical 🔴| AlertFlow

    CheckChart --> Decide{Có cần báo?}
    Decide -->|Không| Idle
    Decide -->|Có| CreateT

    BattScreen --> Alert[🔔 Push notification]
    Alert --> AlertFlow[Mở ticket alert<br/>xem lý do + ngưỡng vượt]
    AlertFlow --> AS{Hành động}
    AS -->|Đóng alert| Idle
    AS -->|Tạo ticket| CreateT
    AS -->|Đã tự xử lý| Dismiss[Mark as resolved<br/>by self]
    Dismiss --> Home

    CreateT[Tạo Ticket] --> CT1[Chọn loại sự cố<br/>Charging · Overheat · No power ...]
    CT1 --> CT2[Mô tả chi tiết]
    CT2 --> CT3[Upload ảnh/video<br/>tối đa 5 files]
    CT3 --> CT4[Xem priority gợi ý<br/>do system tính]
    CT4 --> CT5[Submit]
    CT5 --> CT6[Nhận ticket ID<br/>+ est. response time]
    CT6 --> Track

    BattScreen --> MyT[📋 My Tickets]
    MyT --> Track[Xem tiến trình<br/>OPEN → IN_PROGRESS → RESOLVED]

    Track --> TS{Status hiện tại?}
    TS -->|Staff hỏi| Reply[Trả lời comment<br/>+ ảnh bổ sung]
    TS -->|IN_PROGRESS lâu| ChaseCheck{Quá SLA?}
    TS -->|RESOLVED| ReviewRes

    ChaseCheck -->|Có| Chase[Nhắc qua comment<br/>hoặc liên hệ hotline]
    ChaseCheck -->|Chưa| Track

    Reply --> Track
    Chase --> Track

    ReviewRes[Review kết quả xử lý<br/>đọc maintenance log] --> Verdict{Hài lòng?}
    Verdict -->|Có| Rate[Rate 1-5 sao<br/>+ comment]
    Rate --> Closed[✅ Ticket CLOSED]
    Verdict -->|Không| Reopen[Reopen<br/>mô tả vấn đề còn]
    Reopen --> Track
    Verdict -->|Không action 7d| Auto[System auto-close]

    BattScreen --> Profile[👤 Profile]
    Profile --> P1[Sửa thông tin]
    Profile --> P2[Đổi mật khẩu]
    Profile --> P3[Notification settings<br/>- Push on/off<br/>- Email digest<br/>- Alert threshold cá nhân]
```

---

*Project GSU26SE55 · Core Business Flow · Generated for SE-only scope*
