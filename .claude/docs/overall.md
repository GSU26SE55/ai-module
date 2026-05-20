# OVERALL — Roadmap Backend GSU26SE55 (Full Detail Edition)

> **Document type:** Master backlog & technical specification
> **Scope:** Toàn bộ backend còn lại để cover Core Business Flow (4 role · 6 phase · ticket state machine · SLA escalation · BR-01..BR-08 + 4 entity bổ sung).
> **Source of truth:** `core-business-flow.html` + `.claude/CLAUDE.md` + `.claude/rules/*` + `.claude/memory.md`.
> **Audience:** Leader + 3 BE Dev (Duy, Thắng, Thái) + 2 FE Dev (Trí, Minh) — phần liên quan API contract.
> **Cập nhật:** 2026-05-12 · Branch hiện tại: `feat/retrytimeout` (PR #47 chờ merge).

---

## Mục lục

- [Phần I — Bối cảnh](#phần-i--bối-cảnh)
  - [0. Trạng thái codebase hiện tại](#0-trạng-thái-codebase-hiện-tại)
  - [0bis. Stack & infra hiện hữu](#0bis-stack--infra-hiện-hữu)
- [Phần II — Microservices nghiệp vụ phải xây](#phần-ii--microservices-nghiệp-vụ-phải-xây)
  - [1. BatteryService](#1-batteryservice--p0)
  - [2. TicketService](#2-ticketservice--p0)
  - [3. NotificationService](#3-notificationservice--p1)
  - [4. KnowledgeBase module](#4-knowledgebase-module-trong-ticketservice--p2)
  - [5. Reporting endpoints](#5-reporting-endpoints--p2)
- [Phần III — Hạ tầng & cross-cutting](#phần-iii--hạ-tầng--cross-cutting)
  - [6. TimescaleDB integration](#6-timescaledb-integration--p1)
  - [6bis. FileStorage metadata foundation](#6bis-filestorage-metadata-foundation--p1)
  - [7. Mở rộng AuthService cho profile + skill](#7-mở-rộng-authservice-cho-profile--skill--p1)
  - [8. Cross-cutting concerns](#8-cross-cutting-concerns--p1)
  - [9. Observability](#9-observability--hoàn-thiện-p2)
  - [10. API Gateway hoàn thiện](#10-api-gateway-hoàn-thiện--p1)
- [Phần IV — Quality & operations](#phần-iv--quality--operations)
  - [11. Test strategy](#11-test-strategy-coverage--80-p1)
  - [12. Seed data & migration](#12-seed-data--migration-strategy-p1)
  - [13. Performance & caching](#13-performance--caching-strategy)
  - [14. Security checklist](#14-security-checklist)
  - [15. Email/Notification template catalog](#15-emailnotification-template-catalog)
- [Phần V — Lập kế hoạch](#phần-v--lập-kế-hoạch)
  - [16. Scaffold workflow](#16-scaffold-workflow-cho-từng-service)
  - [17. Sprint backlog 8 sprint](#17-sprint-backlog--8-sprint-chi-tiết)
  - [18. Definition of Done](#18-definition-of-done)
- [Phần VI — Phụ lục](#phần-vi--phụ-lục)
  - [20. Permission matrix](#20-permission-matrix-đầy-đủ)
  - [21. Error code catalog](#21-error-code-catalog)
  - [22. JWT claim structure](#22-jwt-claim-structure)
  - [23. Risk register](#23-risk-register)
  - [24. Checklist 6 phase business flow](#24-checklist-theo-6-phase-business-flow)
  - [25. Câu hỏi cần thống nhất](#25-câu-hỏi-cần-thống-nhất-trước-khi-bắt-đầu)
  - [26. Glossary & references](#26-glossary--references)
  - [27. Troubleshooting playbook](#27-troubleshooting-playbook)
  - [28. Tóm tắt files/paths tạo mới](#28-tóm-tắt-filespaths-cần-tạo)
- [Phần VII — Bổ sung sau review](#phần-vii--bổ-sung-sau-review-gap-analysis)
  - [30. AI Module integration](#30-ai-module-integration--p0)
  - [31. Site](#31-site-entities--p0)
  - [32. Ticket relationships](#32-ticket-relationships--parent-child-merge-watch--p0)
  - [33. SLA pause limits & advanced](#33-sla-pause-limits--advanced--p0)
  - [34. Real-time updates (SSE)](#34-real-time-updates-sse--push-channel--p0)
  - [35. Bulk operations + QR onboarding](#35-bulk-operations--qr-onboarding--p1)
  - [36. Comment / MaintenanceLog advanced](#36-comment--maintenancelog-advanced--p1)
  - [37. Alert silence/snooze + escalation](#37-alert-silence--snooze--ack-escalation--p1)
  - [38. Edge case business rules matrix](#38-edge-case-business-rules-matrix--p0)
  - [39. GDPR & compliance](#39-gdpr--compliance--p1)
  - [40. Operational documents](#40-operational-documents-adr--dr--runbook--p1)
  - [41. Maintenance schedule (preventive)](#41-preventive-maintenance-schedule--p2)
  - [42. Parts inventory](#42-parts-inventory--p2)
  - [43. Public KB + self-help](#43-public-knowledge-base--customer-self-help--p2)
  - [44. Mobile deep linking + Staff field](#44-mobile-deep-linking--staff-field-features--p1)
  - [45. Webhook outbound + public API](#45-webhook-outbound--public-api--p2)
  - [46. Advanced testing & chaos](#46-advanced-testing--chaos-engineering--p2)
  - [47. Security hardening additional](#47-security-hardening-additional--p1)
  - [48. AI feedback loop & analytics](#48-ai-feedback-loop--analytics--p1)
  - [49. Notification advanced](#49-notification-advanced-digest--batching--p1)
  - [50. Updated sprint backlog impact](#50-updated-sprint-backlog-impact)
- [Phần VIII — Bổ sung lần 2 (Final completeness)](#phần-viii--bổ-sung-lần-2-final-completeness)
  - [52. IoT Gateway & Device Management](#52-iot-gateway--device-management--p0)
  - [53. Solar Energy Business Metrics](#53-solar-energy-business-metrics--p0)
  - [54. Production Deployment (K8s + Helm)](#54-production-deployment-k8s--helm--p1)
  - [55. Mobile/Web App Management](#55-mobileweb-app-management--p1)
  - [56. Demo & Presentation Deliverables](#56-demo--presentation-deliverables--p0)
  - [57. AI advanced (deployment, retrain, batching)](#57-ai-advanced--deployment-retrain-batching--p1)
  - [58. Edge cases extension (EC-21..EC-30)](#58-edge-cases-extension-ec-21ec-30--p0)
  - [59. GDPR + security additional](#59-gdpr--security-additional--p1)
  - [60. Internal admin tools](#60-internal-admin-tools--p2)
  - [61. Search functionality](#61-search-functionality--p1)
  - [62. Media pipeline + accessibility](#62-media-pipeline--accessibility--p2)
  - [63. Customer success metrics](#63-customer-success-metrics--p2)
  - [64. Status page + maintenance broadcast](#64-status-page--maintenance-broadcast--p1)
  - [65. Documentation auto-generation](#65-documentation-auto-generation--p2)
  - [66. Final completeness checklist](#66-final-completeness-checklist)

---

# Phần I — Bối cảnh

## 0. Trạng thái codebase hiện tại

### 0.1. Đã có (DONE)

| Module | Trạng thái | Chi tiết |
|--------|-----------|----------|
| **`AuthService`** | ✅ Production-ready + profile extension | Account/Role/Permission/Session/RefreshToken/AuditLog/LoginAttempt/OTP/Outbox + Admin CRUD + Google OAuth helper + `AccountProfile`/`StaffProfile`/`StaffSkill` extension tables + uploaded/Google avatar flow |
| **`ApiGateway`** | ✅ Hoạt động | Route tới AuthService, port 4001 |
| **`EmailService`** | ✅ Consumer-only | Subscribe SendOtpRegisterEvent, SendAdminInviteEvent, SendPasswordResetOtpEvent, SendEmailChangeOtpEvent |
| **`SmsService`** | ✅ Consumer-only | Subscribe SendPhoneOtpEvent |
| **`FileStorageService`** | ✅ Metadata foundation ready | MinIO backend, signed URLs, `UploadedFile` metadata table, upload response trả `fileId`, metadata/presigned/download/delete theo `fileId` |
| **`SharedKernels`** | ✅ Done | `BaseEntity`, `AuditableEntity`, `IHardDeleteEntity`, `IGenericRepository`, `IUnitOfWork` |
| **`SharedInfrastructure`** | ✅ Mature | Middleware (Global exception, CorrelationId, RequestLogging, SecurityHeaders, IdempotencyKey), Behaviors (Validation, Logging), Caching (Redis), Bus (MassTransit + retry/timeout + correlation filters), **Idempotency (Redis inbox + key store)**, Metrics, Swagger extensions, EnvFileLoader |
| **`SharedContracts`** | ✅ Done | `CommonResponse<T>`, `PaginationResponse<T>`, `PaginationRequest`, `IntegrationEvent` root, `IValidatable`, `ICacheService`, `IMessageProducerService`, các email/OTP events |
| **Docker compose** | ✅ Done | `timescale/timescaledb:latest-pg16`, postgres-init tạo logical DB riêng (`auth_db`, `file_storage_db`), redis:7, rabbitmq:3-management, minio, prometheus, grafana, loki, alertmanager |
| **CI/CD** | ✅ Done | GitHub Actions: detect-changes (matrix per service), build/unit-test/integration-test, dotnet format, Trivy filesystem scan, PR title validation (semantic), PR size warning, project rules check |
| **Pre-commit** | ✅ Done | `.pre-commit-config.yaml` với dotnet format, secret-scan |
| **Hooks Claude** | ✅ Done | `.claude/hooks/be/*.sh`: block-dangerous, protect-sensitive, check-build, post-edit-feedback, validate-namespace, check-di-registration, check-dbcontext-update |

### 0.2. CHƯA có — Roadmap (phần chính document này)

| Service / Module | Priority | Section | Effort ước tính |
|------------------|----------|---------|-----------------|
| `BatteryService` (4 dự án, 30+ files CQRS) | 🔴 P0 | §1 | 3 sprint |
| `TicketService` (4 dự án, 50+ files CQRS, state machine) | 🔴 P0 | §2 | 4 sprint |
| `NotificationService` (4 dự án, consumers + Expo push) | 🟠 P1 | §3 | 2 sprint |
| KnowledgeBase (module nội bộ TicketService) | 🟡 P2 | §4 | 0.5 sprint |
| Reporting endpoints (mỗi service expose) | 🟡 P2 | §5 | 1 sprint |
| TimescaleDB extension + hypertable | 🟠 P1 | §6 | 0.5 sprint |
| FileStorage metadata (`UploadedFile`) | ✅ Done | §6bis | Completed 13/5/2026 |
| AuthService profile expansion (avatar, phone, skill) | ✅ Done | §7 | Completed 13/5/2026 |
| Outbox cho Battery/Ticket + saga | 🟠 P1 | §8.1 | 1 sprint |
| Distributed tracing (OpenTelemetry → Tempo/Jaeger) | 🟡 P2 | §8.4 | 0.5 sprint |
| Gateway JWT validate + claim forwarding | 🟠 P1 | §10 | 0.5 sprint |
| Grafana business dashboards | 🟡 P2 | §9 | 0.5 sprint |
| Test coverage ≥ 80% | 🟠 P1 | §11 | Ongoing |
| Seed data scripts | 🟠 P1 | §12 | 0.5 sprint |

---

### 0.3. Đã hoàn tất trong lượt cập nhật 13/5/2026

- [x] Docker Compose dùng `timescale/timescaledb:latest-pg16`.
- [x] Docker Compose có `postgres-init` tạo database riêng cho từng service: `auth_db` và `file_storage_db`.
- [x] `AuthService` chỉ trỏ `ConnectionStrings__AuthDb` vào database Auth riêng.
- [x] `FileStorageService` chỉ trỏ `ConnectionStrings__FileStorageDb` vào database FileStorage riêng.
- [x] Bỏ fallback nguy hiểm `FileStorageService` → `AuthDb`; thiếu `FileStorageDb` thì fail rõ ràng.
- [x] `FileStorageService` metadata foundation: Domain project, `UploadedFile`, `FilePurposeEnum`, `FileStatusEnum`, EF configuration, migration `AddUploadedFileMetadata`.
- [x] `FileStorageService` upload flow tạo metadata sau khi upload object thành công và response có `fileId`.
- [x] `FileStorageService` có endpoint metadata/presigned/download/delete theo `fileId`.
- [x] `AuthService` profile extension: `AccountProfile`, `StaffProfile`, `StaffSkill`, migration `AddAccountProfileExtensionTables`.
- [x] `AuthService` avatar flow: uploaded avatar dùng `AvatarFileId`, Google avatar dùng `ExternalAvatarUrl`, FE dùng `displayAvatarUrl`.
- [x] Validate kỹ thuật đã chạy: `docker compose --env-file .env.Docker config --quiet`, `sh -n docker/postgres/create-service-databases.sh`, `dotnet build FileStorageService.Infrastructure`.

---

## 0bis. Stack & infra hiện hữu

### 0bis.1. Phiên bản công nghệ
- .NET 8 LTS, C# 12
- EF Core 8, PostgreSQL 16 qua `timescale/timescaledb:latest-pg16` trong Docker Compose (xem §6)
- Redis 7 (cache + inbox + idempotency)
- RabbitMQ 3 (MassTransit)
- MinIO (S3-compatible) cho FileStorage
- Polly (đã wrap trong SharedInfrastructure cho retry/timeout)
- MediatR, FluentValidation thay thế bằng custom `IValidatable<T>` pattern
- Serilog → Loki
- Prometheus-net cho metrics
- OpenAPI/Swashbuckle

### 0bis.2. Patterns đã thiết lập
| Pattern | Vị trí | Áp dụng cho service mới |
|---------|--------|-------------------------|
| Clean Architecture 4 layer | Đã có ở AuthService | **Bắt buộc** copy cho Battery/Ticket/Notification |
| CQRS + MediatR | Đã có | **Bắt buộc** |
| Custom `IValidatable<T>` (không dùng FluentValidation) | `SharedContracts/Interfaces/IValidatable.cs` | **Bắt buộc** — pipeline đã chạy qua ValidationBehavior |
| `CommonResponse<T>` wrapper | `SharedContracts/Common/Responses` | **Bắt buộc** |
| Soft delete qua `AuditableEntityInterceptor` | SharedInfrastructure | **Bắt buộc** — KHÔNG dùng global query filter, luôn `.Where(x => !x.IsDeleted)` |
| Repository + UnitOfWork (`GetAllAsync` sync trả `IQueryable`) | `SharedKernels` | **Bắt buộc** — tên `GetAllAsync` legacy, **KHÔNG** await |
| Outbox pattern | AuthService có `OutboxMessage` entity | Copy cho Battery/Ticket |
| Inbox idempotency consumer | `SharedInfrastructure/Idempotency` | Bắt buộc cho mọi consumer |
| Correlation ID middleware + bus filter | SharedInfrastructure | Tự động — chỉ cần đăng ký DI |
| Redis caching wrapper | `SharedInfrastructure/Caching` | Inject `ICacheService` |
| Response wrapper `CommonResponse<T>` với `IsSuccess=true` mặc định | SharedContracts | Bắt buộc |
| JWT claims (`UserId`, `Role`, `FullName`, `Email`) | AuthService phát hành | Service downstream chỉ validate qua middleware từ gateway hoặc tự validate JWT |

### 0bis.3. Quy ước route tổng (cập nhật cho gateway aggregation)
```
/api/v1/auth/*               → AuthService          (port 5001)
/api/battery-assets/*     → BatteryService       (port 5002)
/api/battery-types/*      → BatteryService
/api/thresholds/*         → BatteryService
/api/sensor-readings/*    → BatteryService
/api/alerts/*             → BatteryService
/api/v1/tickets/*            → TicketService        (port 5003)
/api/v1/comments/*           → TicketService
/api/v1/maintenance-logs/*   → TicketService
/api/v1/knowledge-base/*     → TicketService (module)
/api/v1/notifications/*      → NotificationService  (port 5004)
/api/v1/device-tokens/*      → NotificationService
/api/v1/notification-preferences/* → NotificationService
/api/v1/files/*              → FileStorageService   (port 5005)
/api/v1/reports/*            → Aggregated (Battery/Ticket reports)
```

> **Gateway port:** giữ nguyên `4001`. Downstream services chạy port `5001-5005`.

---

# Phần II — Microservices nghiệp vụ phải xây

## 1. BatteryService — P0

### 1.1. Trách nhiệm (Single Responsibility)
1. CRUD `BatteryType`, `ThresholdConfig`, `BatteryAsset`.
2. Ingest và lưu `SensorReading` (TimescaleDB hypertable).
3. Background detection: scan readings → so sánh threshold → generate `Alert`.
4. Dedup alert theo cửa sổ thời gian (BR-03).
5. Publish `BatteryAnomalyDetectedEvent` cho TicketService.
6. Expose realtime + history queries cho Mobile/Web.
7. Provide battery health analytics endpoints.

### 1.2. Cấu trúc thư mục đầy đủ

```
services/BatteryService/
├── BatteryService.slnx
├── src/
│   ├── BatteryService.Api/
│   │   ├── BatteryService.Api.csproj
│   │   ├── Program.cs
│   │   ├── appsettings.json
│   │   ├── appsettings.Development.json
│   │   ├── appsettings.Docker.json
│   │   ├── Dockerfile
│   │   └── Controllers/
│   │       ├── BatteryAssetsController.cs
│   │       ├── BatteryTypesController.cs
│   │       ├── ThresholdConfigsController.cs
│   │       ├── SensorReadingsController.cs
│   │       ├── AlertsController.cs
│   │       ├── DashboardController.cs
│   │       └── HealthController.cs
│   ├── BatteryService.Application/
│   │   ├── BatteryService.Application.csproj
│   │   ├── CQRS/
│   │   │   ├── Command/
│   │   │   │   ├── BatteryAsset/
│   │   │   │   │   ├── BatteryAssetCreateCommand.cs
│   │   │   │   │   ├── BatteryAssetUpdateCommand.cs
│   │   │   │   │   ├── BatteryAssetDeleteCommand.cs
│   │   │   │   │   ├── BatteryAssetRestoreCommand.cs
│   │   │   │   │   └── BatteryAssetTransferOwnerCommand.cs
│   │   │   │   ├── BatteryType/...
│   │   │   │   ├── ThresholdConfig/
│   │   │   │   │   └── ThresholdConfigUpsertCommand.cs
│   │   │   │   ├── SensorReading/
│   │   │   │   │   └── SensorReadingBatchIngestCommand.cs
│   │   │   │   └── Alert/
│   │   │   │       ├── AlertCreateCommand.cs (internal — system)
│   │   │   │       ├── AlertAcknowledgeCommand.cs
│   │   │   │       └── AlertResolveCommand.cs
│   │   │   ├── Query/
│   │   │   │   ├── BatteryAsset/
│   │   │   │   │   ├── BatteryAssetGetListQuery.cs
│   │   │   │   │   ├── BatteryAssetGetByIdQuery.cs
│   │   │   │   │   ├── BatteryAssetRealtimeQuery.cs
│   │   │   │   │   └── MyBatteryAssetsQuery.cs (Customer)
│   │   │   │   ├── BatteryType/...
│   │   │   │   ├── ThresholdConfig/
│   │   │   │   │   └── ThresholdConfigGetByTypeQuery.cs
│   │   │   │   ├── SensorReading/
│   │   │   │   │   ├── SensorReadingGetHistoryQuery.cs
│   │   │   │   │   └── SensorReadingGetLatestQuery.cs
│   │   │   │   ├── Alert/
│   │   │   │   │   ├── AlertGetListQuery.cs
│   │   │   │   │   ├── AlertGetByIdQuery.cs
│   │   │   │   │   └── ActiveAlertsByAssetQuery.cs
│   │   │   │   └── Dashboard/
│   │   │   │       └── BatteryDashboardStatsQuery.cs
│   │   │   └── Handler/  (mirror command/query structure)
│   │   ├── DTOs/
│   │   │   └── Response/
│   │   │       ├── BatteryAsset/
│   │   │       │   ├── BatteryAssetDto.cs
│   │   │       │   ├── BatteryAssetResponse.cs
│   │   │       │   ├── BatteryAssetListResponse.cs
│   │   │       │   └── BatteryAssetRealtimeDto.cs
│   │   │       ├── BatteryType/...
│   │   │       ├── ThresholdConfig/...
│   │   │       ├── SensorReading/...
│   │   │       └── Alert/...
│   │   ├── Consumers/
│   │   │   ├── AccountActivatedConsumer.cs       (link Customer to asset)
│   │   │   ├── AccountDeletedConsumer.cs         (reassign or soft delete)
│   │   │   └── AccountStatusChangedConsumer.cs
│   │   ├── Interfaces/
│   │   │   ├── Repositories/
│   │   │   │   └── IBatteryUnitOfWork.cs
│   │   │   └── Services/
│   │   │       ├── IAlertDeduplicationService.cs
│   │   │       └── IAnomalyDetector.cs
│   │   ├── Services/
│   │   │   ├── AlertDeduplicationService.cs
│   │   │   └── ThresholdAnomalyDetector.cs
│   │   └── Configuration/
│   │       └── BatteryServiceOptions.cs           (dedup window, scan interval)
│   ├── BatteryService.Domain/
│   │   ├── BatteryService.Domain.csproj
│   │   ├── Entities/
│   │   │   ├── BatteryAsset.cs
│   │   │   ├── BatteryType.cs
│   │   │   ├── ThresholdConfig.cs
│   │   │   ├── SensorReading.cs
│   │   │   ├── Alert.cs
│   │   │   ├── AlertHistory.cs
│   │   │   └── OutboxMessage.cs
│   │   └── Enums/
│   │       ├── BatteryStatusEnum.cs
│   │       ├── WarrantyStatusEnum.cs
│   │       ├── AnomalyTypeEnum.cs
│   │       ├── AlertSeverityEnum.cs
│   │       ├── AlertStatusEnum.cs
│   │       └── BatteryChemistryEnum.cs
│   └── BatteryService.Infrastructure/
│       ├── BatteryService.Infrastructure.csproj
│       ├── Persistence/
│       │   ├── ApplicationDbContext.cs
│       │   ├── Configurations/
│       │   │   ├── BatteryAssetConfiguration.cs
│       │   │   ├── BatteryTypeConfiguration.cs
│       │   │   ├── ThresholdConfigConfiguration.cs
│       │   │   ├── SensorReadingConfiguration.cs
│       │   │   ├── AlertConfiguration.cs
│       │   │   └── AlertHistoryConfiguration.cs
│       │   ├── Repositories/
│       │   │   ├── BatteryAssetRepository.cs (custom queries nếu cần)
│       │   │   ├── SensorReadingRepository.cs (batch insert raw SQL)
│       │   │   ├── AlertRepository.cs
│       │   │   └── BatteryUnitOfWork.cs
│       │   └── Migrations/
│       ├── BackgroundJobs/
│       │   ├── ThresholdCheckBackgroundService.cs
│       │   ├── AlertEscalationBackgroundService.cs
│       │   ├── AlertAutoResolveBackgroundService.cs
│       │   └── OutboxRelayBackgroundService.cs
│       ├── ExternalServices/
│       │   └── (optional: IoT MQTT bridge nếu cần)
│       └── DependencyInjection/
│           └── ManageDependencyInjection.cs
└── tests/
    ├── BatteryService.UnitTests/
    │   ├── BatteryService.UnitTests.csproj
    │   ├── Application/
    │   │   ├── CQRS/Commands/*HandlerTests.cs
    │   │   ├── CQRS/Queries/*HandlerTests.cs
    │   │   └── Services/
    │   │       ├── AlertDeduplicationServiceTests.cs
    │   │       └── ThresholdAnomalyDetectorTests.cs
    │   ├── Domain/
    │   │   └── EntityTests.cs
    │   └── Fixtures/
    │       └── MockUnitOfWorkFactory.cs
    └── BatteryService.IntegrationTests/
        ├── BatteryService.IntegrationTests.csproj
        ├── Controllers/
        │   ├── BatteryAssetsControllerTests.cs
        │   ├── SensorReadingsControllerTests.cs
        │   └── AlertsControllerTests.cs
        ├── BackgroundJobs/
        │   └── ThresholdCheckBackgroundServiceTests.cs
        ├── Consumers/
        │   └── AccountActivatedConsumerTests.cs
        └── Fixtures/
            ├── PostgresTimescaleFixture.cs  (TestContainers)
            └── WebApplicationFactoryFixture.cs
```

### 1.3. Entity detail — đầy đủ field & validation

#### 1.3.1. `BatteryAsset` (kế thừa `AuditableEntity`)

| Field | Type | Constraint | Index | Note |
|-------|------|-----------|-------|------|
| `Id` | `Guid` | PK | clustered | từ `AuditableEntity` |
| `SerialNumber` | `string(64)` | NOT NULL, UNIQUE | btree unique | Auto-generate hoặc nhập tay |
| `BatteryTypeId` | `Guid` | FK → BatteryType.Id, NOT NULL | btree | — |
| `CustomerId` | `Guid` | NOT NULL | btree | userId Customer (AuthService) |
| `InstallDate` | `DateTime` | NOT NULL | — | UTC |
| `WarrantyEndDate` | `DateTime?` | nullable | — | — |
| `WarrantyStatus` | `WarrantyStatusEnum` | NOT NULL default `Active` | — | 1=Active, 2=Expired, 3=Void |
| `Location` | `string(255)?` | nullable | — | Free text hoặc GPS |
| `Latitude` | `decimal(9,6)?` | nullable | — | optional |
| `Longitude` | `decimal(9,6)?` | nullable | — | optional |
| `Status` | `BatteryStatusEnum` | NOT NULL default `Active` | btree filter | 1=Active, 2=Inactive, 3=Decommissioned |
| `Notes` | `string(1000)?` | nullable | — | — |
| `LastSensorReadingAt` | `DateTime?` | nullable | btree | Cache để query nhanh "stale device" |
| `CreatedAt`, `CreatedBy`, `UpdatedAt`, `UpdatedBy`, `IsDeleted`, `DeletedAt` | — | từ `AuditableEntity` | — | — |

**Composite index:** `(CustomerId, IsDeleted, Status)` cho query "my batteries".

**Validation rules `BatteryAssetCreateCommand`:**
- `SerialNumber`: required, 5–64 chars, regex `^[A-Z0-9-]+$`, unique (check AnyAsync).
- `BatteryTypeId`: required, must exist + !IsDeleted.
- `CustomerId`: required, must exist (call AuthService API hoặc cache local).
- `InstallDate`: required, ≤ today, ≥ 5 năm trước.
- `WarrantyEndDate`: optional, > InstallDate.

#### 1.3.2. `BatteryType` (kế thừa `AuditableEntity`)

| Field | Type | Constraint | Note |
|-------|------|-----------|------|
| `Id` | `Guid` | PK | — |
| `Name` | `string(100)` | NOT NULL, UNIQUE | "Lithium-ion 12V 100Ah" |
| `Manufacturer` | `string(100)?` | — | — |
| `NominalCapacityAh` | `decimal(10,2)` | NOT NULL, > 0 | — |
| `NominalVoltage` | `decimal(6,2)` | NOT NULL, > 0 | — |
| `Chemistry` | `BatteryChemistryEnum` | NOT NULL | 1=LiFePO4, 2=NMC, 3=NCA, 4=LCO |
| `MaxCycleCount` | `int` | NOT NULL default 2000 | — |
| `Description` | `string(500)?` | — | — |

#### 1.3.3. `ThresholdConfig` (kế thừa `AuditableEntity`)

| Field | Type | Constraint | Note |
|-------|------|-----------|------|
| `Id` | `Guid` | PK | — |
| `BatteryTypeId` | `Guid` | FK, NOT NULL | One-active-config per type |
| `VoltageMin` | `decimal(6,2)` | NOT NULL | — |
| `VoltageMax` | `decimal(6,2)` | NOT NULL, > VoltageMin | — |
| `TemperatureMax` | `decimal(5,2)` | NOT NULL | °C |
| `TemperatureMin` | `decimal(5,2)` | NOT NULL | °C |
| `SocWarningThreshold` | `decimal(5,2)` | NOT NULL, 0–100 | % |
| `SocCriticalThreshold` | `decimal(5,2)` | NOT NULL, 0–100 | % |
| `CurrentMaxCharge` | `decimal(8,2)?` | nullable | A |
| `CurrentMaxDischarge` | `decimal(8,2)?` | nullable | A |
| `SohWarningThreshold` | `decimal(5,2)?` | nullable, 0–100 | %, vd 85 → cảnh báo pin xuống cấp |
| `SohCriticalThreshold` | `decimal(5,2)?` | nullable, 0–100 | %, vd 75 → EOL sắp tới |
| `InternalResistanceMaxMilliohm` | `decimal(8,2)?` | nullable, > 0 | mΩ — early aging indicator |
| `CellVoltageDeltaMaxMv` | `decimal(8,2)?` | nullable, ≥ 0 | mV, vd 100 — pack imbalance threshold |
| `EffectiveFromUtc` | `DateTime` | NOT NULL | — |
| `IsActive` | `bool` | NOT NULL default true | Chỉ 1 record active per type |

**Validation:**
- `SocCriticalThreshold < SocWarningThreshold`.
- `TemperatureMin < TemperatureMax`.
- Nếu cả 2 SOH threshold không null: `SohCriticalThreshold < SohWarningThreshold`.

#### 1.3.4. `SensorReading` (KHÔNG kế thừa `AuditableEntity` — time-series append-only)

| Field | Type | Constraint | Index |
|-------|------|-----------|-------|
| `Time` | `DateTime` | NOT NULL | TimescaleDB hypertable column |
| `BatteryAssetId` | `Guid` | NOT NULL | btree composite |
| `Voltage` | `decimal(6,2)` | NOT NULL | — |
| `Current` | `decimal(8,2)` | NOT NULL | — |
| `Temperature` | `decimal(5,2)` | NOT NULL | °C — đo trên thân/BMS pin |
| `SocPercent` | `decimal(5,2)` | NOT NULL, 0–100 | — |
| `CycleCount` | `int?` | nullable | — |
| `SohPercent` | `decimal(5,2)?` | nullable, 0–100 | **Target chính của AI module** |
| `ChargingState` | `ChargingStateEnum?` | nullable | 1=Idle, 2=Charging, 3=Discharging, 4=Float, 5=Bypass |
| `InternalResistanceMilliohm` | `decimal(8,2)?` | nullable, > 0 | mΩ — early aging indicator |
| `CellVoltageDeltaMv` | `decimal(8,2)?` | nullable, ≥ 0 | mV — chênh lệch Vmax-Vmin giữa các cell |
| `BmsErrorCode` | `string(64)?` | nullable | Mã lỗi BMS raw (vd `0x0A`, `OverCurrent,CellImbalance`) |
| `SourceDeviceId` | `string(64)?` | — | IoT gateway ID |

**Compound index:** `(BatteryAssetId, Time DESC)` cho realtime/history queries.
**Hypertable interval:** 1 day chunks.
**Retention policy:** 90 ngày raw, 1 năm 1h-aggregate, 5 năm 1d-aggregate.

**Lưu ý:** 5 field SOH/ChargingState/IR/CellDelta/BmsErrorCode đều **nullable** — backfill data cũ không cần. BMS có thì gửi, không có thì để null.

#### 1.3.5. `Alert` (kế thừa `AuditableEntity`)

| Field | Type | Constraint | Note |
|-------|------|-----------|------|
| `Id` | `Guid` | PK | — |
| `BatteryAssetId` | `Guid?` | FK, **nullable** | btree — alert per-pin |
| `SiteId` | `Guid?` | FK, **nullable** | btree — alert per-site (ambient/incident) |
| `EnvironmentalIncidentId` | `Guid?` | FK, **nullable** | Link tới incident nếu alert được tạo từ smoke/water |
| `AnomalyType` | `AnomalyTypeEnum` | NOT NULL | 1–14 (xem §1.3.6, mở rộng từ 7 → 14) |
| `Severity` | `AlertSeverityEnum` | NOT NULL | 1=Info, 2=Warning, 3=Critical |
| `ThresholdValue` | `decimal(10,4)?` | nullable | NULL cho incident-based alert (smoke/water không có threshold) |
| `ActualValue` | `decimal(10,4)?` | nullable | NULL như trên |
| `Unit` | `string(10)?` | nullable | V/A/°C/%/RH (nullable cho incident) |
| `DetectedAt` | `DateTime` | NOT NULL | UTC |
| `Status` | `AlertStatusEnum` | NOT NULL | 1=Open, 2=Acknowledged, 3=Merged, 4=Resolved |
| `MergedIntoAlertId` | `Guid?` | self-FK, nullable | BR-03 dedup |
| `TicketId` | `Guid?` | nullable | Link tới ticket nếu auto-created |
| `AcknowledgedByUserId` | `Guid?` | — | — |
| `AcknowledgedAt` | `DateTime?` | — | — |
| `ResolvedAt` | `DateTime?` | — | — |
| `DedupWindowEndUtc` | `DateTime` | NOT NULL | `DetectedAt + DedupWindowMinutes` |

**Check constraint:** `BatteryAssetId IS NOT NULL OR SiteId IS NOT NULL` — alert phải có ít nhất 1 chủ thể.

**Composite index:** `(BatteryAssetId, AnomalyType, Status, DedupWindowEndUtc) WHERE BatteryAssetId IS NOT NULL` cho dedup query per-pin.
**Composite index:** `(SiteId, AnomalyType, Status, DedupWindowEndUtc) WHERE SiteId IS NOT NULL` cho dedup query per-site.

#### 1.3.6. Enum values
```csharp
public enum BatteryStatusEnum { Active = 1, Inactive = 2, Decommissioned = 3 }
public enum WarrantyStatusEnum { Active = 1, Expired = 2, Void = 3 }
public enum BatteryChemistryEnum { LiFePO4 = 1, NMC = 2, NCA = 3, LCO = 4 }

// Sensor reading context
public enum ChargingStateEnum
{
    Idle = 1, Charging = 2, Discharging = 3, Float = 4, Bypass = 5
}

// Anomaly classification - mở rộng 7 → 14 giá trị
public enum AnomalyTypeEnum {
    // Pin-level cũ (1-7)
    Overheat = 1, Overvoltage = 2, Undervoltage = 3,
    LowSoc = 4, RapidDischarge = 5, AbnormalCharging = 6, DeviceOffline = 7,
    // Pin-level mới (8-10) - degradation / aging
    SohDegradation = 8,
    HighInternalResistance = 9,
    CellImbalance = 10,
    // Site-level (11-14) - ambient + incident
    HighAmbientTemp = 11,
    HighHumidity = 12,
    HighTempHumidityCombo = 13,
    EnvironmentalIncident = 14
}

public enum AlertSeverityEnum { Info = 1, Warning = 2, Critical = 3 }
public enum AlertStatusEnum { Open = 1, Acknowledged = 2, Merged = 3, Resolved = 4 }

// Ambient reading source - phân biệt từ IoT thật vs Weather API
public enum AmbientReadingSourceEnum { IotSensor = 1, WeatherApi = 2 }

// Environmental incident (smoke, water leak, ...)
public enum IncidentTypeEnum
{
    SmokeDetected = 1,
    WaterLeak = 2
    // Mở rộng tương lai: PowerLoss = 3, DoorOpen = 4, ...
}
public enum IncidentSeverityEnum { Warning = 1, High = 2, Critical = 3 }
public enum IncidentStatusEnum
{
    Detected = 1,         // mới phát hiện, chưa ack
    Acknowledged = 2,     // staff/manager đã thấy
    Resolved = 3,         // xử lý xong
    FalseAlarm = 4        // không phải sự cố thật
}
```

#### 1.3.7. `AmbientReading` (KHÔNG kế thừa `AuditableEntity` — time-series append-only)

Chuỗi đo định kỳ điều kiện môi trường tại Site. Có thể đến từ cảm biến IoT thật hoặc từ Weather API (OpenMeteo).

| Field | Type | Constraint | Index | Note |
|-------|------|-----------|-------|------|
| `Time` | `DateTime` | NOT NULL | TimescaleDB hypertable column | UTC |
| `SiteId` | `Guid` | NOT NULL, FK → Site.Id | btree composite | Bắt buộc |
| `AmbientTemperature` | `decimal(5,2)` | NOT NULL | — | °C — nhiệt độ MÔI TRƯỜNG (≠ Temperature của pin) |
| `Humidity` | `decimal(5,2)?` | nullable, 0–100 | — | % RH |
| `SolarIrradiance` | `decimal(8,2)?` | nullable, ≥ 0 | — | W/m² (`shortwave_radiation` từ OpenMeteo hoặc pyranometer) |
| `Source` | `AmbientReadingSourceEnum` | NOT NULL | btree | 1=IotSensor, 2=WeatherApi |
| `SourceDeviceId` | `string(64)?` | nullable | — | DeviceId IoT, hoặc "openmeteo" |

**PK composite:** `(Time, SiteId)` (giống `sensor_readings`).
**Hypertable interval:** 7 day chunks.
**Index:** `(SiteId, Time DESC)`.
**Retention:** 90 ngày raw, 1 năm 1h-aggregate (Sprint sau).

**Query rule cho consumer (AnomalyDetector):**
Để lấy ambient cho 1 BatteryAsset → lookup theo Site: dùng latest reading của Site.

#### 1.3.8. `AmbientThresholdConfig` (per Site, kế thừa `AuditableEntity`)

Tách riêng khỏi `ThresholdConfig` (vốn per BatteryType) vì threshold môi trường là đặc tính của địa điểm.

| Field | Type | Constraint | Note |
|-------|------|-----------|------|
| `Id` | `Guid` | PK | — |
| `SiteId` | `Guid` | FK, NOT NULL | One-active-config per site |
| `AmbientTempMax` | `decimal(5,2)?` | nullable | °C, vd 40 — vượt → HighAmbientTemp anomaly |
| `AmbientTempMin` | `decimal(5,2)?` | nullable | °C, vd 5 — lạnh quá pin xả chậm |
| `HumidityMax` | `decimal(5,2)?` | nullable, 0–100 | %RH, vd 85 — vượt → HighHumidity anomaly |
| `HumidityComboTempMax` | `decimal(5,2)?` | nullable | °C, vd 35 — trigger COMBO nếu cả 2 vượt |
| `HumidityComboHumidityMax` | `decimal(5,2)?` | nullable, 0–100 | %RH, vd 80 — pair với ComboTempMax |
| `EffectiveFromUtc` | `DateTime` | NOT NULL | — |
| `IsActive` | `bool` | NOT NULL default true | — |

**Unique:** `(SiteId) WHERE IsActive = true AND IsDeleted = false`.

**Validation:**
- Nếu cả `AmbientTempMin` và `AmbientTempMax` không null: `Min < Max`.
- Nếu set combo: cả `HumidityComboTempMax` và `HumidityComboHumidityMax` đều phải có giá trị.

#### 1.3.9. `EnvironmentalIncident` (event-driven, kế thừa `AuditableEntity`)

Sự kiện an toàn (smoke/water leak/...) với lifecycle Detected → Resolved. KHÔNG phải time-series (mỗi event = 1 record với start/end time).

| Field | Type | Constraint | Note |
|-------|------|-----------|------|
| `Id` | `Guid` | PK | — |
| `SiteId` | `Guid` | FK, NOT NULL | btree |
| `IncidentType` | `IncidentTypeEnum` | NOT NULL | 1=SmokeDetected, 2=WaterLeak |
| `Severity` | `IncidentSeverityEnum` | NOT NULL | 1=Warning, 2=High, 3=Critical |
| `Status` | `IncidentStatusEnum` | NOT NULL default `Detected` | 1=Detected, 2=Acknowledged, 3=Resolved, 4=FalseAlarm |
| `DetectedAt` | `DateTime` | NOT NULL | UTC |
| `AcknowledgedAt` | `DateTime?` | — | — |
| `AcknowledgedByUserId` | `Guid?` | — | UserId từ AuthService |
| `ResolvedAt` | `DateTime?` | — | — |
| `ResolvedByUserId` | `Guid?` | — | — |
| `Description` | `string(1000)?` | nullable | Note thêm khi report (ví dụ vị trí cảm biến cụ thể) |
| `SourceDeviceId` | `string(64)?` | nullable | DeviceId IoT báo về |

**Index:** `(SiteId, Status, DetectedAt DESC)`, `(IncidentType, Status)`.

**Flow event-driven:**
1. IoT cảm biến phát hiện → POST `/api/environmental-incidents` (ApiKey).
2. Handler tạo record với `Status=Detected`.
3. Handler tạo Alert kèm theo (`SiteId`, `EnvironmentalIncidentId`, `AnomalyType=EnvironmentalIncident`).
4. Publish `EnvironmentalIncidentDetectedEvent` → NotificationService push notification Critical.
5. Staff/Manager gọi `PATCH /{id}/acknowledge` → `Status=Acknowledged`, `AcknowledgedAt`.
6. Khi xử lý xong: `PATCH /{id}/resolve` → `Status=Resolved`, đóng Alert liên kết.
7. Nếu false-positive: `PATCH /{id}/false-alarm` → `Status=FalseAlarm`, đóng Alert.

### 1.4. CQRS — Command catalog đầy đủ

#### Commands & response wrapper

| Command | Payload chính | Auth | Response |
|---------|---------------|------|----------|
| `BatteryAssetCreateCommand` | SerialNumber, BatteryTypeId, CustomerId, InstallDate, ... | Admin | `BatteryAssetCreateResponse : CommonResponse<BatteryAssetDto>` |
| `BatteryAssetUpdateCommand` | Id, ... | Admin | `BatteryAssetUpdateResponse : CommonResponse<BatteryAssetDto>` |
| `BatteryAssetDeleteCommand` | Id | Admin | `CommonResponse<object>` |
| `BatteryAssetRestoreCommand` | Id | Admin | — |
| `BatteryAssetTransferOwnerCommand` | Id, NewCustomerId, Reason | Admin | — |
| `BatteryTypeCreateCommand` | Name, Manufacturer, Capacity, Voltage, Chemistry, MaxCycle | Admin | — |
| `BatteryTypeUpdateCommand` | Id, ... | Admin | — |
| `BatteryTypeDeleteCommand` | Id | Admin | — |
| `ThresholdConfigUpsertCommand` | BatteryTypeId, all threshold values, EffectiveFromUtc | Admin | — |
| `SensorReadingBatchIngestCommand` | List<SensorReadingItem> (BatteryAssetId, Time, V, I, T, SOC, SOH?, ChargingState?, IR?, CellDelta?, BmsErrorCode?) | ApiKey (`SensorIngest`) | `CommonResponse<BatchIngestResult>` |
| `AlertAcknowledgeCommand` | Id, Note? | Customer (own), Staff | — |
| `AlertResolveCommand` | Id, ResolutionNote | Staff, Manager | — |
| `AmbientReadingBatchIngestCommand` | List<AmbientReadingItem> (SiteId, Time, AmbientTemp, Humidity?, SolarIrradiance?) | ApiKey (`EnvironmentalIngest`) | `CommonResponse<BatchIngestResult>` |
| `UpsertAmbientThresholdConfigCommand` | SiteId, TempMax?, TempMin?, HumidityMax?, ComboTemp?, ComboHumidity?, EffectiveFromUtc | Admin | `CommonResponse<AmbientThresholdConfigDto>` |
| `ReportEnvironmentalIncidentCommand` | SiteId, IncidentType, Severity, DetectedAt, Description?, SourceDeviceId? | ApiKey (`EnvironmentalIngest`) | `CommonResponse<EnvironmentalIncidentDto>` |
| `AcknowledgeEnvironmentalIncidentCommand` | Id | Admin, Manager, Staff | — |
| `ResolveEnvironmentalIncidentCommand` | Id, ResolutionNote? | Admin, Manager, Staff | — |
| `MarkFalseAlarmEnvironmentalIncidentCommand` | Id, Reason | Admin, Manager | — |

#### Sample command class

```csharp
public class BatteryAssetCreateCommand
    : IRequest<BatteryAssetCreateResponse>,
      IValidatable<BatteryAssetCreateResponse>
{
    public string SerialNumber { get; set; } = string.Empty;
    public Guid BatteryTypeId { get; set; }
    public Guid CustomerId { get; set; }
    public DateTime InstallDate { get; set; }
    public DateTime? WarrantyEndDate { get; set; }
    public string? Location { get; set; }
    public decimal? Latitude { get; set; }
    public decimal? Longitude { get; set; }
    public string? Notes { get; set; }

    public Task<BatteryAssetCreateResponse> ValidateAsync()
    {
        var r = new BatteryAssetCreateResponse();

        if (string.IsNullOrWhiteSpace(SerialNumber))
            r.ListErrors.Add(new Errors { Field = nameof(SerialNumber), Detail = "Required" });
        else if (!Regex.IsMatch(SerialNumber, "^[A-Z0-9-]+$"))
            r.ListErrors.Add(new Errors { Field = nameof(SerialNumber), Detail = "Invalid format" });
        else if (SerialNumber.Length is < 5 or > 64)
            r.ListErrors.Add(new Errors { Field = nameof(SerialNumber), Detail = "Length 5-64" });

        if (BatteryTypeId == Guid.Empty)
            r.ListErrors.Add(new Errors { Field = nameof(BatteryTypeId), Detail = "Required" });

        if (CustomerId == Guid.Empty)
            r.ListErrors.Add(new Errors { Field = nameof(CustomerId), Detail = "Required" });

        if (InstallDate == default)
            r.ListErrors.Add(new Errors { Field = nameof(InstallDate), Detail = "Required" });
        else if (InstallDate > DateTime.UtcNow)
            r.ListErrors.Add(new Errors { Field = nameof(InstallDate), Detail = "Must be in past" });
        else if (InstallDate < DateTime.UtcNow.AddYears(-5))
            r.ListErrors.Add(new Errors { Field = nameof(InstallDate), Detail = "Too old (max 5 years)" });

        if (WarrantyEndDate.HasValue && WarrantyEndDate <= InstallDate)
            r.ListErrors.Add(new Errors { Field = nameof(WarrantyEndDate), Detail = "Must be after install date" });

        if (r.ListErrors.Count > 0) r.IsSuccess = false;
        return Task.FromResult(r);
    }
}
```

### 1.5. Query catalog

| Query | Params | Auth | Cache strategy |
|-------|--------|------|----------------|
| `BatteryAssetGetListQuery` | Pagination + status + customerId + batteryTypeId + search | Admin/Manager | None |
| `BatteryAssetGetByIdQuery` | Id | Admin/Manager (any) — Customer (own) | Redis 60s |
| `BatteryAssetRealtimeQuery` | Id | Customer (own) — Staff | No cache (realtime) |
| `MyBatteryAssetsQuery` | (CustomerId từ JWT) | Customer | Redis 30s |
| `SensorReadingGetHistoryQuery` | AssetId, From, To, Granularity (1m/1h/1d) | Customer (own) — Staff/Manager | Redis 60s for >1h granularity |
| `SensorReadingGetLatestQuery` | AssetId | — | No cache |
| `AlertGetListQuery` | Pagination + severity + status + assetId + dateRange | Customer (own assets) — Manager/Staff | None |
| `AlertGetByIdQuery` | Id | — | Redis 60s |
| `ActiveAlertsByAssetQuery` | AssetId | — | Redis 30s |
| `BatteryDashboardStatsQuery` | (none — admin/manager view) | Admin/Manager | Redis 60s |
| `ThresholdConfigGetByTypeQuery` | BatteryTypeId | Admin/Manager | Redis 600s |
| `AmbientReadingHistoryQuery` | SiteId, From, To | Admin/Manager/Staff/Customer (own site) | Redis 60s |
| `AmbientReadingLatestQuery` | SiteId | — same — | Redis 30s |
| `AmbientThresholdConfigBySiteQuery` | SiteId | Admin/Manager | Redis 600s |
| `AmbientThresholdConfigGetListQuery` | Pagination + SiteId? + IsActive? | Admin/Manager | None |
| `EnvironmentalIncidentGetListQuery` | Pagination + SiteId? + Type? + Status? + DateRange | Admin/Manager/Staff/Customer (own site) | None |
| `EnvironmentalIncidentGetByIdQuery` | Id | — same — | Redis 60s |
| `ActiveEnvironmentalIncidentsBySiteQuery` | SiteId | — same — | Redis 30s |

### 1.6. Background services — chi tiết

#### `ThresholdCheckBackgroundService`
```csharp
// Pseudo-code
while (!ct.IsCancellationRequested) {
    var since = DateTime.UtcNow.AddSeconds(-_options.ScanIntervalSeconds * 2);
    var readings = await _uow.SensorReadings
        .GetAllAsync()
        .Where(r => r.Time >= since)
        .Include(r => r.BatteryAsset)
        .ThenInclude(a => a.BatteryType)
        .ToListAsync(ct);

    foreach (var reading in readings) {
        var threshold = await _thresholdCache.GetForType(reading.BatteryAsset.BatteryTypeId);
        var anomalies = _detector.Detect(reading, threshold);
        foreach (var anomaly in anomalies) {
            await _mediator.Send(new AlertCreateCommand {
                BatteryAssetId = reading.BatteryAssetId,
                AnomalyType = anomaly.Type,
                Severity = anomaly.Severity,
                ThresholdValue = anomaly.Threshold,
                ActualValue = anomaly.Actual,
                Unit = anomaly.Unit,
                DetectedAt = reading.Time
            }, ct);
        }
    }
    await Task.Delay(TimeSpan.FromSeconds(_options.ScanIntervalSeconds), ct);
}
```

**Config:**
- `ScanIntervalSeconds`: default 30.
- `DedupWindowMinutes`: default 30.
- `CriticalAutoCreateTicket`: default true.

#### `AlertEscalationBackgroundService`
- Mỗi 1 phút: query Alert `Severity=Critical AND Status=Open AND DetectedAt < now - 5min`.
- Publish `BatteryAnomalyDetectedEvent` → TicketService consume → auto-create ticket (BR-02).

#### `AlertAutoResolveBackgroundService`
- Mỗi 5 phút: nếu Alert có `Status=Open` và `AnomalyType` không còn vượt ngưỡng trong N phút gần nhất → auto-resolve.

#### `OutboxRelayBackgroundService`
- Mỗi 5 giây: scan `OutboxMessage` `IsProcessed=false`, publish lên RabbitMQ, mark processed.

#### `WeatherSyncBackgroundService`

Pull dữ liệu thời tiết từ OpenMeteo cho mỗi Site (lat/lon đã set), insert vào `AmbientReading` với `Source=WeatherApi`.

```csharp
// Pseudo-code
public class WeatherSyncBackgroundService : BackgroundService
{
    private readonly IServiceScopeFactory _scopeFactory;   // KHÔNG inject UoW (Scoped) trực tiếp
    private readonly WeatherSyncOptions _options;

    protected override async Task ExecuteAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            using var scope = _scopeFactory.CreateScope();
            var uow = scope.ServiceProvider.GetRequiredService<IBatteryUnitOfWork>();
            var weatherClient = scope.ServiceProvider.GetRequiredService<IOpenMeteoClient>();

            var sites = await uow.Sites.GetAllAsync()
                .Where(s => !s.IsDeleted && s.Status == SiteStatusEnum.Active
                    && s.Latitude != null && s.Longitude != null)
                .ToListAsync(ct);

            foreach (var site in sites)
            {
                // Dedup: skip nếu reading WeatherApi gần nhất < DedupMinutes
                var cutoff = DateTime.UtcNow.AddMinutes(-_options.DedupMinutes);
                var hasRecent = await uow.AmbientReadings.GetAllAsync()
                    .AnyAsync(r => r.SiteId == site.Id
                                && r.Source == AmbientReadingSourceEnum.WeatherApi
                                && r.Time >= cutoff, ct);
                if (hasRecent) continue;

                try
                {
                    var snapshot = await weatherClient.GetCurrentAsync(site.Latitude!.Value, site.Longitude!.Value, ct);
                    if (snapshot is null) continue;

                    await uow.AmbientReadings.AddAsync(new AmbientReading
                    {
                        Time = snapshot.ObservedAtUtc,
                        SiteId = site.Id,
                        AmbientTemperature = snapshot.Temperature,
                        Humidity = snapshot.Humidity,
                        SolarIrradiance = snapshot.ShortwaveRadiation,
                        Source = AmbientReadingSourceEnum.WeatherApi,
                        SourceDeviceId = "openmeteo"
                    });
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Weather sync failed for site {SiteId}", site.Id);
                    // Không throw — 1 site fail không chặn site khác
                }
            }

            await uow.SaveChangesAsync(ct);
            await Task.Delay(TimeSpan.FromMinutes(_options.SyncIntervalMinutes), ct);
        }
    }
}
```

**Config (`Weather:` section trong appsettings):**
- `OpenMeteoBaseUrl`: `https://api.open-meteo.com/v1/forecast`.
- `SyncIntervalMinutes`: default 15.
- `DedupMinutes`: default 10 — site đã có reading WeatherApi trong N phút → skip.
- `TimeoutSeconds`: 10 — HTTP timeout.

**Rate limit:** OpenMeteo free tier 10,000 calls/day. 1 site/15min = 96 calls/day → 100 sites OK.

#### `ThresholdAnomalyDetector` (extend cho 14 anomaly types)

Đã có trong Sprint 3 plan. Update logic:

| Anomaly | Input source | Threshold source | Severity quy ước |
|---------|-------------|------------------|------------------|
| `Overheat` | SensorReading.Temperature | ThresholdConfig.TemperatureMax | Critical nếu > +5°C ngưỡng, ngược lại Warning |
| `Overvoltage` / `Undervoltage` | Voltage | VoltageMax / VoltageMin | Critical |
| `LowSoc` | SocPercent | SocCritical / SocWarning | Critical / Warning |
| `RapidDischarge` / `AbnormalCharging` | Current | CurrentMaxDischarge / CurrentMaxCharge | Critical |
| `DeviceOffline` | LastSensorReadingAt | > 10 phút không có reading | Warning |
| `SohDegradation` | SensorReading.SohPercent | SohWarning / SohCritical | Critical / Warning |
| `HighInternalResistance` | SensorReading.InternalResistanceMilliohm | ThresholdConfig.InternalResistanceMaxMilliohm | Warning |
| `CellImbalance` | SensorReading.CellVoltageDeltaMv | ThresholdConfig.CellVoltageDeltaMaxMv | Warning |
| `HighAmbientTemp` | AmbientReading.AmbientTemperature | AmbientThresholdConfig.AmbientTempMax | Warning |
| `HighHumidity` | AmbientReading.Humidity | AmbientThresholdConfig.HumidityMax | Warning |
| `HighTempHumidityCombo` | Cả 2 cùng vượt ngưỡng combo | HumidityComboTempMax + HumidityComboHumidityMax | High (severity 2 = nguy hiểm hơn Warning) |
| `EnvironmentalIncident` | Trigger từ `EnvironmentalIncident.Detected` event | n/a | Critical (smoke/water đều Critical) |

### 1.7. Integration events

#### Publish
```csharp
public record BatteryAssetCreatedEvent : IntegrationEvent {
    public Guid AssetId { get; init; }
    public Guid CustomerId { get; init; }
    public string SerialNumber { get; init; } = string.Empty;
    public Guid BatteryTypeId { get; init; }
}

public record BatteryAnomalyDetectedEvent : IntegrationEvent {
    public Guid AlertId { get; init; }
    public Guid BatteryAssetId { get; init; }
    public Guid CustomerId { get; init; }
    public AnomalyTypeEnum AnomalyType { get; init; }
    public AlertSeverityEnum Severity { get; init; }
    public decimal ThresholdValue { get; init; }
    public decimal ActualValue { get; init; }
    public string Unit { get; init; } = string.Empty;
    public DateTime DetectedAt { get; init; }
    public string AssetSerialNumber { get; init; } = string.Empty;  // denormalize for ticket service
}

public record BatteryAssetTransferredEvent : IntegrationEvent {
    public Guid AssetId { get; init; }
    public Guid OldCustomerId { get; init; }
    public Guid NewCustomerId { get; init; }
    public string Reason { get; init; } = string.Empty;
}

// Tách khỏi BatteryAnomalyDetectedEvent vì payload khác (site-level, không có assetSerial).
// NotificationService consume cả 2 nhưng template + routing khác.
public record EnvironmentalIncidentDetectedEvent : IntegrationEvent {
    public Guid IncidentId { get; init; }
    public Guid SiteId { get; init; }
    public Guid CustomerId { get; init; }           // chủ Site, lookup khi publish
    public IncidentTypeEnum IncidentType { get; init; }
    public IncidentSeverityEnum Severity { get; init; }
    public DateTime DetectedAt { get; init; }
    public string SiteName { get; init; } = string.Empty;   // denormalize cho notification template
    public string? Description { get; init; }
}

public record EnvironmentalIncidentResolvedEvent : IntegrationEvent {
    public Guid IncidentId { get; init; }
    public Guid SiteId { get; init; }
    public DateTime ResolvedAt { get; init; }
    public Guid ResolvedByUserId { get; init; }
    public bool WasFalseAlarm { get; init; }
}
```

#### Consume
- `AccountActivatedConsumer`: cache customer info nếu cần.
- `AccountDeletedConsumer`: soft delete asset hoặc transfer to "Inactive" placeholder.
- `AccountStatusChangedConsumer`: update local cache.

### 1.8. REST API contract

#### Endpoint list đầy đủ
```
# BatteryAsset
POST   /api/battery-assets                            (Admin)
GET    /api/battery-assets?customerId=&status=&page=  (Admin/Manager)
GET    /api/battery-assets/{id}                       (Admin/Manager — Customer own)
PUT    /api/battery-assets/{id}                       (Admin)
DELETE /api/battery-assets/{id}                       (Admin)
PATCH  /api/battery-assets/{id}/restore               (Admin)
PUT    /api/battery-assets/{id}/transfer-owner        (Admin)
GET    /api/battery-assets/me                         (Customer — own list)
GET    /api/battery-assets/{id}/realtime              (Customer own — Staff/Manager)
GET    /api/battery-assets/{id}/history?from=&to=&granularity= (Customer own — Staff/Manager)
GET    /api/battery-assets/{id}/alerts                (— same auth as above —)

# BatteryType
POST   /api/battery-types                             (Admin)
GET    /api/battery-types                             (Admin/Manager)
GET    /api/battery-types/{id}                        (Admin/Manager)
PUT    /api/battery-types/{id}                        (Admin)
DELETE /api/battery-types/{id}                        (Admin)

# Threshold
GET    /api/thresholds                                (Admin/Manager)
GET    /api/thresholds/by-type/{batteryTypeId}        (Admin/Manager/internal)
PUT    /api/thresholds/by-type/{batteryTypeId}        (Admin) — upsert

# Sensor Reading
POST   /api/sensor-readings/batch                     (ApiKey `SensorIngest` — IoT gateway)
GET    /api/sensor-readings?assetId=&from=&to=        (Customer own — Staff/Manager)
GET    /api/sensor-readings/latest?assetId=           (— same —)

# Alert
GET    /api/alerts?severity=&status=&assetId=&siteId=&page=   (Customer own — Staff/Manager)
GET    /api/alerts/{id}                               (— same —)
PATCH  /api/alerts/{id}/acknowledge                   (Customer own — Staff)
PATCH  /api/alerts/{id}/resolve                       (Staff/Manager)

# Ambient Reading (NEW)
POST   /api/ambient-readings/batch                    (ApiKey `EnvironmentalIngest` — IoT)
GET    /api/ambient-readings?siteId=&from=&to=  (— same auth as alerts —)
GET    /api/ambient-readings/latest?siteId=     (— same —)

# Ambient Threshold (NEW)
GET    /api/ambient-thresholds                        (Admin/Manager)
GET    /api/ambient-thresholds/by-site/{siteId}       (Admin/Manager)
PUT    /api/ambient-thresholds/by-site/{siteId}       (Admin) — upsert

# Environmental Incident (NEW)
POST   /api/environmental-incidents                   (ApiKey `EnvironmentalIngest` — IoT cảm biến smoke/water)
GET    /api/environmental-incidents?siteId=&type=&status=&from=&to=&page=  (— same auth —)
GET    /api/environmental-incidents/{id}              (— same —)
PATCH  /api/environmental-incidents/{id}/acknowledge  (Admin/Manager/Staff)
PATCH  /api/environmental-incidents/{id}/resolve      (Admin/Manager/Staff)
PATCH  /api/environmental-incidents/{id}/false-alarm  (Admin/Manager)

# Dashboard
GET    /api/battery/dashboard/stats                   (Admin/Manager)

# Health
GET    /api/battery/health                            (Internal — for k8s probes)
```

**ApiKey policy update:**
- Tách thành 2 key trong `appsettings.json`:
  - `ApiKeys:SensorIngest` — chỉ cho `/api/sensor-readings/batch`
  - `ApiKeys:EnvironmentalIngest` — cho `/api/ambient-readings/batch` + `/api/environmental-incidents`
- Lý do: nếu IoT gateway smoke detector bị compromise, attacker không thể giả mạo sensor reading (và ngược lại). Mỗi key có scope giới hạn.

#### Sample request/response

**POST /api/battery-assets**
```json
// Request
{
  "serialNumber": "BAT-2026-001",
  "batteryTypeId": "9c4d6f2e-...",
  "customerId": "7a2b1c8d-...",
  "installDate": "2026-01-15T00:00:00Z",
  "warrantyEndDate": "2031-01-15T00:00:00Z",
  "location": "Khu A, Solar Farm 1",
  "latitude": 10.776,
  "longitude": 106.701
}

// Response 200 OK
{
  "isSuccess": true,
  "message": null,
  "listErrors": [],
  "data": {
    "id": "5e8f...",
    "serialNumber": "BAT-2026-001",
    "batteryType": { "id": "9c4d...", "name": "LiFePO4 12V 100Ah" },
    "customerId": "7a2b...",
    "status": 1,
    "warrantyStatus": 1,
    "installDate": "2026-01-15T00:00:00Z",
    "createdAt": "2026-05-12T08:30:00Z"
  }
}
```

**GET /api/battery-assets/{id}/realtime**
```json
{
  "isSuccess": true,
  "data": {
    "assetId": "5e8f...",
    "time": "2026-05-12T10:15:30Z",
    "voltage": 12.6,
    "current": -5.2,
    "temperature": 35.4,
    "socPercent": 78.5,
    "status": "Normal",
    "activeAlerts": 0
  }
}
```

### 1.9. Test catalog (BatteryService) — bắt buộc trước ship

#### Unit tests — core (pin)
- `BatteryAssetCreateCommandHandlerTests`: 6 cases (success, missing serial, duplicate serial, invalid type, customer not exist, install date future)
- `BatteryAssetCreateCommandValidationTests`: 8 cases (each field validation)
- `AlertCreateCommandHandlerTests`: 4 cases (new alert, dedup merge into existing, critical → publish event, info severity → no event)
- `AlertDeduplicationServiceTests`: 5 cases (within window same type → merge, outside window → new, different anomaly → new, status not Open → new, multiple recent → merge to most recent)
- `ThresholdAnomalyDetectorTests`: 14 cases (1 per AnomalyTypeEnum value, gồm 7 cũ + 7 mới SOH/IR/Imbalance/Ambient/Combo/Incident/DeviceOffline)
- `BatteryAssetGetListQueryHandlerTests`: filtering, paging, soft-delete exclusion

#### Unit tests — environmental + extended battery health
- `AmbientReadingBatchIngestCommandHandlerTests`: 4 cases (success, invalid site, dedup with WeatherApi source, mix IoT + API ok)
- `UpsertAmbientThresholdConfigCommandHandlerTests`: 5 cases (create new, update existing, invalid combo, min > max, missing site)
- `ReportEnvironmentalIncidentCommandHandlerTests`: 4 cases (success → alert created + event published, missing site, duplicate within 1 min same type → merge, critical severity → publish notification)
- `AcknowledgeEnvironmentalIncidentCommandHandlerTests`: 3 cases (success, already resolved, false alarm)
- `ResolveEnvironmentalIncidentCommandHandlerTests`: 3 cases (success closes linked alert, already false-alarm 409, missing user 401)
- `OpenMeteoClientTests`: 4 cases (success parse, 4xx error returns null, timeout returns null, malformed JSON returns null) — dùng `HttpMessageHandler` stub
- `WeatherSyncBackgroundServiceTests`: 4 cases (site with lat/lon → insert reading, site missing lat/lon → skip, dedup window → skip, OpenMeteo fail → continue next site)
- `SensorReadingNewFieldsValidationTests`: 5 cases (SOH out of range, IR ≤ 0, CellDelta < 0, BmsErrorCode too long, ChargingState invalid enum)

#### Integration tests (TestContainers postgres + timescaledb image)
- POST asset → query list returns it
- POST sensor batch → background scan detects anomaly → alert created → event published (assert via MassTransit TestHarness)
- DELETE asset → soft delete (IsDeleted=true), list excludes
- Auth: Customer A cannot GET asset of Customer B
- **NEW:** POST ambient batch → query latest returns insert
- **NEW:** POST sensor batch với SOH < threshold → detector tạo `SohDegradation` alert
- **NEW:** Ambient reading vượt cả temp + humidity combo → tạo alert `HighTempHumidityCombo` Severity=High
- **NEW:** POST `/api/environmental-incidents` (smoke) → record incident + alert Critical + publish `EnvironmentalIncidentDetectedEvent`
- **NEW:** PATCH `/false-alarm` đóng cả incident và alert liên kết
- **NEW:** Migration rollback bao gồm ambient_readings + ambient_threshold_configs + environmental_incidents

### 1.10. External integrations

#### OpenMeteo (weather data)

| Item | Value |
|------|-------|
| Base URL | `https://api.open-meteo.com/v1/forecast` |
| Auth | None (free tier) |
| Rate limit | 10,000 calls/day |
| Cost | Free |
| Variables used | `temperature_2m`, `relative_humidity_2m`, `shortwave_radiation` |

**Client interface (trong Application layer):**
```csharp
public interface IOpenMeteoClient
{
    Task<WeatherSnapshot?> GetCurrentAsync(decimal latitude, decimal longitude, CancellationToken ct);
}

public record WeatherSnapshot(
    DateTime ObservedAtUtc,
    decimal Temperature,                // °C
    decimal? Humidity,                  // % RH
    decimal? ShortwaveRadiation);       // W/m² ~ solar irradiance proxy
```

**Implementation:** `OpenMeteoClient` dùng `HttpClient` injected qua `IHttpClientFactory`. Polly retry policy 3 lần exponential backoff. Timeout 10s. Mọi error → log warning + return null (không throw để không chặn WeatherSync).

**Sample call:**
```
GET https://api.open-meteo.com/v1/forecast?latitude=10.776&longitude=106.701&current=temperature_2m,relative_humidity_2m,shortwave_radiation&timezone=UTC
```

**DI registration** (`ManageDependencyInjection.cs` BatteryService.Infrastructure):
```csharp
services.AddHttpClient<IOpenMeteoClient, OpenMeteoClient>(client =>
{
    client.BaseAddress = new Uri(configuration["Weather:OpenMeteoBaseUrl"]!);
    client.Timeout = TimeSpan.FromSeconds(10);
}).AddPolicyHandler(GetRetryPolicy());

services.AddHostedService<WeatherSyncBackgroundService>();
services.Configure<WeatherSyncOptions>(configuration.GetSection("Weather"));
```

---

## 2. TicketService — P0

### 2.1. Trách nhiệm
1. CRUD ticket với state machine 12+ trạng thái.
2. Quản lý SLA timer (start/pause/resume/breach) — BR-04.
3. Quản lý Activity timeline (BR-08).
4. Auto-create từ `BatteryAnomalyDetectedEvent` (BR-02), tránh trùng (BR-02 cụ thể: chỉ tạo nếu chưa có ticket OPEN/ASSIGNED/IN_PROGRESS cho cùng asset+anomaly).
5. Manager approval workflow (BR-05).
6. Reopen policy 7 ngày (BR-06) + escalate khi ≥ 2 reopen (BR-07).
7. KnowledgeBase module (xem §4).
8. Maintenance log + attachment.
9. Comment với Internal/External visibility.

### 2.2. Cấu trúc thư mục
(tương tự BatteryService, tham khảo §1.2)
```
services/TicketService/
├── src/
│   ├── TicketService.Api/Controllers/
│   │   ├── TicketsController.cs
│   │   ├── TicketCommentsController.cs
│   │   ├── MaintenanceLogsController.cs
│   │   ├── KnowledgeBaseController.cs        ← §4
│   │   ├── ManagerWorkflowController.cs      ← queue, workload
│   │   ├── StaffWorkflowController.cs        ← my tickets
│   │   ├── ReportsController.cs              ← §5
│   │   └── HealthController.cs
│   ├── TicketService.Application/
│   │   ├── CQRS/Command/Ticket/...
│   │   ├── CQRS/Command/Comment/...
│   │   ├── CQRS/Command/MaintenanceLog/...
│   │   ├── CQRS/Command/KnowledgeBase/...
│   │   ├── CQRS/Query/...
│   │   ├── StateMachine/
│   │   │   ├── ITicketStateMachine.cs
│   │   │   ├── TicketStateMachine.cs
│   │   │   ├── TransitionRequest.cs
│   │   │   └── TransitionResult.cs
│   │   ├── Services/
│   │   │   ├── ISlaCalculator.cs
│   │   │   ├── SlaCalculator.cs
│   │   │   ├── IPriorityAdvisor.cs           ← gợi ý priority cho Manager
│   │   │   ├── PriorityAdvisor.cs
│   │   │   ├── IStaffAssignmentService.cs    ← workload + skill match
│   │   │   └── StaffAssignmentService.cs
│   │   └── Consumers/
│   │       ├── BatteryAnomalyDetectedConsumer.cs
│   │       └── AccountStatusChangedConsumer.cs
│   ├── TicketService.Domain/Entities/
│   │   ├── Ticket.cs
│   │   ├── TicketActivity.cs
│   │   ├── TicketComment.cs
│   │   ├── MaintenanceLog.cs
│   │   ├── SlaTimer.cs
│   │   ├── SlaPauseEvent.cs
│   │   ├── TicketAttachment.cs
│   │   ├── KnowledgeBaseArticle.cs           ← §4
│   │   ├── CustomerAccount.cs                ← read-model cache từ AuthService (validate CustomerId, tránh circular HTTP call)
│   │   ├── StaffAccount.cs                   ← read-model cache từ AuthService (validate AssignedStaffId, skill + availability)
│   │   └── OutboxMessage.cs
│   ├── TicketService.Domain/Enums/
│   │   ├── TicketStatusEnum.cs
│   │   ├── TicketPriorityEnum.cs
│   │   ├── TicketCategoryEnum.cs
│   │   ├── TicketOriginEnum.cs
│   │   ├── EscalationReasonEnum.cs
│   │   ├── PauseReasonEnum.cs
│   │   ├── ActivityActionEnum.cs
│   │   ├── ActorRoleEnum.cs
│   │   ├── MaintenanceLogTypeEnum.cs
│   │   ├── SlaTimerStatusEnum.cs
│   │   └── KbArticleStatusEnum.cs
│   └── TicketService.Infrastructure/
│       ├── Persistence/...
│       ├── BackgroundJobs/
│       │   ├── SlaTimerBackgroundService.cs
│       │   ├── AutoCloseBackgroundService.cs
│       │   ├── EscalationBackgroundService.cs
│       │   └── OutboxRelayBackgroundService.cs
│       └── Consumers/...
└── tests/...
```

### 2.3. Entity detail

#### 2.3.1. `Ticket` (kế thừa `AuditableEntity`)

| Field | Type | Constraint | Note |
|-------|------|-----------|------|
| `Id` | `Guid` | PK | — |
| `Code` | `string(20)` | NOT NULL, UNIQUE | "TKT-2605-0001" (auto-gen YYMM-NNNN reset hàng tháng) |
| `BatteryAssetId` | `Guid` | NOT NULL | BR-01 mandatory |
| `CustomerId` | `Guid` | NOT NULL | Owner |
| `AssignedStaffId` | `Guid?` | nullable | Set khi Manager assign |
| `Title` | `string(200)` | NOT NULL | — |
| `Description` | `string(4000)` | NOT NULL | — |
| `Category` | `TicketCategoryEnum` | NOT NULL | 1=Charging, 2=Overheat, 3=NoPower, 4=Performance, 5=Other |
| `Priority` | `TicketPriorityEnum?` | nullable until ASSIGNED | 1=P1Critical, 2=P2High, 3=P3Normal |
| `Status` | `TicketStatusEnum` | NOT NULL default `NEW` | xem §2.4 |
| `Origin` | `TicketOriginEnum` | NOT NULL | 1=ManualByCustomer, 2=AutoFromAlert, 3=CreatedByStaff |
| `OriginAlertId` | `Guid?` | nullable | Link với Alert nếu auto |
| `ReopenCount` | `int` | NOT NULL default 0 | BR-07 escalate khi ≥ 2 |
| `ResolutionSummary` | `string(2000)?` | nullable | Staff điền khi mark RESOLVED |
| `ResolvedAt` | `DateTime?` | nullable | — |
| `ResolvedByStaffId` | `Guid?` | nullable | — |
| `ApprovedAt` | `DateTime?` | nullable | Manager approve |
| `ApprovedByManagerId` | `Guid?` | — | — |
| `RejectionReason` | `string(1000)?` | — | — |
| `ClosedAt` | `DateTime?` | — | — |
| `Rating` | `int?` (1–5) | — | Customer rate |
| `RatingComment` | `string(1000)?` | — | — |
| `RatedAt` | `DateTime?` | — | — |
| `EscalatedAt` | `DateTime?` | — | — |
| `EscalationReason` | `EscalationReasonEnum?` | — | 1=SkillGap, 2=PartsRequired, 3=SafetyConcern, 4=SlaBreach, 5=CustomerComplaint |
| `IsIncident` | `bool` | NOT NULL default false | Critical flag |

**Indexes:**
- `(CustomerId, Status, IsDeleted)` — Customer "my tickets"
- `(AssignedStaffId, Status)` — Staff "my queue"
- `(Status, Priority, CreatedAt)` — Manager queue
- `(BatteryAssetId, Status)` — dedup auto-create

#### 2.3.2. `SlaTimer` (one-to-one với Ticket)

| Field | Type | Note |
|-------|------|------|
| `Id` | `Guid` | PK |
| `TicketId` | `Guid` | FK, UNIQUE |
| `Priority` | `TicketPriorityEnum` | Snapshot lúc start, cố định |
| `StartedAt` | `DateTime` | Khi Status sang ASSIGNED |
| `DueAt` | `DateTime` | StartedAt + SLA hours, sẽ recalc khi resume từ pause |
| `OriginalDueAt` | `DateTime` | Snapshot lúc start, immutable |
| `TotalPausedMinutes` | `int` | Tổng pause |
| `CurrentPauseStartedAt` | `DateTime?` | Đang pause |
| `WarningSentAt` | `DateTime?` | Khi 80% — chỉ gửi 1 lần |
| `BreachAt` | `DateTime?` | Khi vượt DueAt |
| `Status` | `SlaTimerStatusEnum` | 1=Running, 2=Paused, 3=Met, 4=Breached |

**SLA hours mapping:**
- P1 Critical = 4
- P2 High = 24
- P3 Normal = 72

#### 2.3.3. `SlaPauseEvent` (audit pause/resume)

| Field | Type | Note |
|-------|------|------|
| `Id` | `Guid` | PK |
| `SlaTimerId` | `Guid` | FK |
| `Reason` | `PauseReasonEnum` | 1=WaitingCustomer, 2=WaitingParts, 3=WaitingOnsiteSchedule |
| `Note` | `string(500)` | free text |
| `PausedAt` | `DateTime` | — |
| `PausedByUserId` | `Guid` | — |
| `ResumedAt` | `DateTime?` | — |
| `ResumedByUserId` | `Guid?` | — |
| `DurationMinutes` | `int?` | computed when resumed |

#### 2.3.4. `TicketActivity` (BR-08)

| Field | Type | Note |
|-------|------|------|
| `Id` | `Guid` | — |
| `TicketId` | `Guid` | FK, indexed |
| `ActorUserId` | `Guid` | — |
| `ActorRole` | `ActorRoleEnum` | 1=Admin, 2=Manager, 3=Staff, 4=Customer, 5=System |
| `ActorDisplayName` | `string(200)` | denormalize |
| `Action` | `ActivityActionEnum` | xem enum bên dưới |
| `OldValue` | `string(2000)?` | JSON |
| `NewValue` | `string(2000)?` | JSON |
| `Reason` | `string(1000)?` | — |
| `CreatedAt` | `DateTime` | indexed DESC |

```csharp
public enum ActivityActionEnum {
    Created = 1, StatusChanged = 2, PriorityAssigned = 3,
    StaffAssigned = 4, StaffReassigned = 5,
    Commented = 6, MaintenanceLogged = 7, AttachmentAdded = 8,
    SlaPaused = 9, SlaResumed = 10, SlaWarning = 11, SlaBreached = 12,
    EscalationRequested = 13, Escalated = 14, IncidentDeclared = 15,
    Resolved = 16, Approved = 17, Rejected = 18,
    Rated = 19, Reopened = 20, Closed = 21, AutoClosed = 22
}
```

#### 2.3.5. `TicketComment`

| Field | Type | Note |
|-------|------|------|
| `Id` | `Guid` | — |
| `TicketId` | `Guid` | FK |
| `AuthorUserId` | `Guid` | — |
| `AuthorRole` | `ActorRoleEnum` | — |
| `AuthorDisplayName` | `string(200)` | denormalize |
| `Body` | `string(4000)` | Markdown — sanitize XSS |
| `IsInternal` | `bool` | default false; Internal=true thì Customer không thấy |
| `AttachmentFileIds` | `string` | JSON array of Guid |

#### 2.3.6. `MaintenanceLog`

| Field | Type | Note |
|-------|------|------|
| `Id` | `Guid` | — |
| `TicketId` | `Guid` | FK |
| `StaffId` | `Guid` | — |
| `LogType` | `MaintenanceLogTypeEnum` | 1=RemoteSupport, 2=OnSite, 3=PartReplacement, 4=Inspection |
| `Summary` | `string(2000)` | required |
| `DiagnosisDetails` | `string(4000)?` | — |
| `ActionsTaken` | `string(4000)?` | — |
| `StartedAt` | `DateTime` | — |
| `CompletedAt` | `DateTime?` | — |
| `PartsUsed` | `string(2000)?` | JSON |
| `AttachmentFileIds` | `string` | JSON |
| `BeforePhotosFileIds` | `string` | JSON |
| `AfterPhotosFileIds` | `string` | JSON |

#### 2.3.7. `TicketAttachment`

| Field | Type | Note |
|-------|------|------|
| `Id` | `Guid` | — |
| `TicketId` | `Guid` | FK |
| `UploadedByUserId` | `Guid` | — |
| `FileId` | `Guid` | reference FileStorageService |
| `FileName` | `string(255)` | — |
| `ContentType` | `string(100)` | — |
| `SizeBytes` | `long` | — |
| `Source` | `enum` | 1=CustomerSubmission, 2=StaffWork, 3=MaintenanceLog |

### 2.4. State Machine — đầy đủ matrix

#### 2.4.1. States
```csharp
public enum TicketStatusEnum {
    New = 1,
    Open = 2,
    Assigned = 3,
    InProgress = 4,
    WaitingCustomer = 5,
    WaitingParts = 6,
    WaitingOnsiteSchedule = 7,
    Resolved = 8,
    Escalated = 9,
    ClosedPendingRate = 10,
    Closed = 11,
    ClosedRejected = 12,
    Incident = 13
}
```

#### 2.4.2. Transition matrix

| From → To | Actor allowed | Required fields | Side effects |
|-----------|---------------|-----------------|--------------|
| `*` → `New` | System (initial) | — | Activity Created |
| `New` → `Open` | Manager / System | — | Activity StatusChanged |
| `Open` → `Assigned` | Manager | `Priority`, `AssignedStaffId` | Start SlaTimer, publish TicketAssignedEvent, Activity StaffAssigned + PriorityAssigned |
| `Assigned` → `InProgress` | AssignedStaff | — | Activity StatusChanged |
| `InProgress` → `WaitingCustomer` | Staff | `Reason`, `Note` | Pause SlaTimer, create SlaPauseEvent |
| `InProgress` → `WaitingParts` | Staff | `Reason`, `Note` | Same as above |
| `InProgress` → `WaitingOnsiteSchedule` | Staff | `Reason`, `Note` | Same |
| `Waiting*` → `InProgress` | Staff / System (customer reply) | — | Resume SlaTimer, update SlaPauseEvent.ResumedAt |
| `InProgress` → `Resolved` | Staff | `ResolutionSummary` | Publish TicketResolvedEvent, notify Manager |
| `InProgress` → `Escalated` | Staff | `EscalationReason` | Activity EscalationRequested, notify Manager |
| `Assigned` → `Escalated` | System (SLA breach P1/P2) | (auto) | Activity Escalated by System |
| `Escalated` → `Assigned` | Manager | `AssignedStaffId` (new senior) | Activity StaffReassigned |
| `Escalated` → `Incident` | Manager | `Reason` | Set IsIncident=true, broadcast IncidentDeclaredEvent |
| `Escalated` → `ClosedRejected` | Manager | `RejectionReason` | Activity Rejected, publish TicketClosedEvent |
| `Incident` → `Assigned` | Manager | `AssignedStaffId` | Activity |
| `Resolved` → `ClosedPendingRate` | Manager | — | Approve, set ApprovedAt, publish TicketApprovedEvent |
| `Resolved` → `InProgress` | Manager | `RejectionReason` | Reject, Activity Rejected |
| `ClosedPendingRate` → `Closed` | Customer | `Rating` (1-5), `RatingComment?` | Set ClosedAt, publish TicketClosedEvent |
| `ClosedPendingRate` → `Closed` | System (auto, 7 days) | — | AutoClosed activity |
| `ClosedPendingRate` → `Open` | Customer (within 7d) | `ReopenReason` | ReopenCount++, BR-07 check, Activity Reopened |
| `Closed` → `Open` | ❌ NOT ALLOWED | — | Must create new ticket |

#### 2.4.3. State machine class skeleton
```csharp
public interface ITicketStateMachine {
    TransitionResult CanTransition(Ticket ticket, TicketStatusEnum target, ActorRoleEnum actorRole, Guid actorUserId);
    Task<TransitionResult> ExecuteAsync(Ticket ticket, TicketStatusEnum target, TransitionContext ctx, CancellationToken ct);
}

public sealed class TransitionContext {
    public ActorRoleEnum ActorRole { get; init; }
    public Guid ActorUserId { get; init; }
    public string ActorDisplayName { get; init; } = string.Empty;
    public Dictionary<string, object?> Payload { get; init; } = new();
}

public sealed class TransitionResult {
    public bool IsAllowed { get; init; }
    public string? Reason { get; init; }
    public List<DomainEvent> RaisedEvents { get; init; } = new();
}
```

### 2.5. CQRS — đầy đủ command + query

#### Commands (16 commands)
1. `TicketCreateCommand` (Customer)
2. `TicketAutoCreateFromAlertCommand` (System — gọi nội bộ từ consumer)
3. `TicketAssignCommand` (Manager): StaffId, Priority
4. `TicketReassignCommand` (Manager): NewStaffId, Reason
5. `TicketStartCommand` (Staff): → InProgress
6. `TicketHoldCommand` (Staff): Reason, Note → Waiting*
7. `TicketResumeCommand` (Staff)
8. `TicketResolveCommand` (Staff): ResolutionSummary
9. `TicketApproveCommand` (Manager)
10. `TicketRejectCommand` (Manager): RejectionReason
11. `TicketEscalateRequestCommand` (Staff): EscalationReason
12. `TicketEscalateForceCommand` (Manager): for manual escalation
13. `TicketDeclareIncidentCommand` (Manager)
14. `TicketRateCommand` (Customer): Rating, Comment
15. `TicketReopenCommand` (Customer): Reason
16. `TicketCloseCommand` (System: auto-close 7d)

Plus comment/log/attachment commands:
- `CommentAddCommand` (Customer/Staff/Manager)
- `MaintenanceLogAddCommand` (Staff)
- `MaintenanceLogUpdateCommand` (Staff)
- `AttachmentUploadCommand` (Customer/Staff)

#### Queries (15 queries)
1. `TicketGetListQuery` — Admin/Manager: full filter
2. `TicketGetByIdQuery` — with includes (activities, comments, sla, logs)
3. `MyTicketsAsCustomerQuery`
4. `MyTicketsAsStaffQuery`
5. `ManagerQueueQuery` (status=Open, priority sort)
6. `TicketActivityTimelineQuery`
7. `SlaStatusQuery` — countdown + pauseHistory
8. `StaffWorkloadQuery` (Manager: list Staff with active count)
9. `TicketDashboardStatsQuery` (Admin/Manager: open, overdue, breach rate, avg resolve time)
10. `TicketCommentsQuery` (filter internal/external by role)
11. `MaintenanceLogsByTicketQuery`
12. `TicketSearchQuery` (full-text Title + Description + Code)
13. `OverdueTicketsQuery` (Manager view)
14. `EscalatedTicketsQuery`
15. `IncidentsQuery`

### 2.6. Background services

#### `SlaTimerBackgroundService` (frequency: 60s)
```csharp
foreach (var timer in await _uow.SlaTimers.GetAllAsync()
    .Where(t => t.Status == SlaTimerStatusEnum.Running)
    .ToListAsync()) {

    var now = DateTime.UtcNow;
    var remaining = timer.DueAt - now;
    var totalMinutes = (timer.DueAt - timer.StartedAt).TotalMinutes - timer.TotalPausedMinutes;
    var remainingPercent = remaining.TotalMinutes / totalMinutes;

    // 80% threshold warning
    if (remainingPercent <= 0.2 && timer.WarningSentAt == null) {
        timer.WarningSentAt = now;
        await _outbox.AddEvent(new SlaWarningEvent { TicketId = timer.TicketId, Priority = timer.Priority });
        await _activity.LogAsync(timer.TicketId, ActivityActionEnum.SlaWarning);
    }

    // breach
    if (remaining <= TimeSpan.Zero && timer.Status == SlaTimerStatusEnum.Running) {
        timer.BreachAt = now;
        timer.Status = SlaTimerStatusEnum.Breached;
        await _outbox.AddEvent(new SlaBreachedEvent { TicketId = timer.TicketId, Priority = timer.Priority });
        await _activity.LogAsync(timer.TicketId, ActivityActionEnum.SlaBreached);

        // Per design.md: P1/P2 breach → auto escalate (state change), P3 → only log
        if (timer.Priority is TicketPriorityEnum.P1Critical or TicketPriorityEnum.P2High) {
            var ticket = await _uow.Tickets.GetByIdAsync(timer.TicketId);
            ticket.Status = TicketStatusEnum.Escalated;
            ticket.EscalatedAt = now;
            ticket.EscalationReason = EscalationReasonEnum.SlaBreach;
            _uow.Tickets.UpdateAsync(ticket);
        }
    }
}
await _uow.CommitTransactionAsync();
```

#### `AutoCloseBackgroundService` (frequency: hourly)
- Scan tickets `Status=ClosedPendingRate AND ApprovedAt < now - 7d` → set Closed, log AutoClosed.

#### `EscalationBackgroundService` (event-driven, không scheduled)
- Subscribe `SlaBreachedEvent` internal → trigger escalation flow.

#### `OutboxRelayBackgroundService` (5s)
- Standard outbox relay.

### 2.7. Integration events

#### Publish (10 events)
1. `TicketCreatedEvent`
2. `TicketAssignedEvent`
3. `TicketStatusChangedEvent` (generic)
4. `TicketResolvedEvent`
5. `TicketApprovedEvent`
6. `TicketRejectedEvent`
7. `TicketReopenedEvent`
8. `TicketClosedEvent`
9. `TicketEscalatedEvent`
10. `IncidentDeclaredEvent`
11. `SlaWarningEvent`
12. `SlaBreachedEvent`

Sample:
```csharp
public record TicketAssignedEvent : IntegrationEvent {
    public Guid TicketId { get; init; }
    public string TicketCode { get; init; } = string.Empty;
    public Guid CustomerId { get; init; }
    public Guid AssignedStaffId { get; init; }
    public TicketPriorityEnum Priority { get; init; }
    public DateTime SlaDueAt { get; init; }
}
```

#### Read-model: `CustomerAccount` và `StaffAccount` trong TicketService

> **Lý do tồn tại:** TicketService cần validate `CustomerId` (tạo ticket) và `AssignedStaffId` (assign) mà **không được gọi HTTP ngược lại AuthService** (circular dependency). Giải pháp: duy trì local read-model bằng cách consume event từ AuthService.

| Entity | Field chính | Sync từ event |
|--------|-------------|---------------|
| `CustomerAccount` | `AccountId (PK)`, `FullName`, `Email`, `Status`, `IsDeleted` | `AccountActivatedEvent`, `AccountStatusChangedEvent`, `AccountDeletedEvent` |
| `StaffAccount` | `AccountId (PK)`, `FullName`, `Email`, `Status`, `IsAvailable`, `MaxConcurrentTickets`, `Skills (jsonb)` | `AccountActivatedEvent`, `AccountStatusChangedEvent`, `StaffProfileUpdatedEvent`, `StaffSkillsUpdatedEvent` |

**Rule:**
- `TicketCreateCommand` validate `CustomerId` → query local `CustomerAccount` table.
- `TicketAssignCommand` validate `AssignedStaffId` → query local `StaffAccount` table, check `IsAvailable = true` và `active ticket count < MaxConcurrentTickets`.
- Consumers: thêm `AccountActivatedConsumer`, `AccountStatusChangedConsumer`, `StaffProfileUpdatedConsumer`, `StaffSkillsUpdatedConsumer` vào TicketService.Application/Consumers/.
- Eventual consistency chấp nhận được: delay vài giây giữa AuthService update và TicketService read-model không ảnh hưởng business flow.

#### Consume (2 events)
1. `BatteryAnomalyDetectedConsumer`:
   ```csharp
   public async Task Consume(ConsumeContext<BatteryAnomalyDetectedEvent> ctx) {
       var evt = ctx.Message;
       // BR-02: chỉ auto-create nếu chưa có ticket đang mở cho cùng asset + cùng AnomalyType.
       // Chiến lược dedup DUY NHẤT: match theo (BatteryAssetId + Category + active status).
       // KHÔNG dùng OriginAlertId vì alert có thể bị dedup/merge ở BatteryService trước khi event gửi đi.
       // MapAnomalyToCategory() ánh xạ AnomalyType → TicketCategoryEnum để so sánh.
       var category = MapAnomalyToCategory(evt.AnomalyType);
       var existing = await _uow.Tickets.GetAllAsync()
           .Where(t => t.BatteryAssetId == evt.BatteryAssetId
                    && t.Category == category
                    && t.Status >= TicketStatusEnum.Open
                    && t.Status <= TicketStatusEnum.WaitingOnsiteSchedule
                    && !t.IsDeleted)
           .AnyAsync();
       if (existing) return; // dedup — BR-02

       var ticket = new Ticket {
           Code = _codeGen.Next(),
           BatteryAssetId = evt.BatteryAssetId,
           CustomerId = evt.CustomerId,
           Title = $"[{evt.Severity}] {evt.AnomalyType} detected on {evt.AssetSerialNumber}",
           Description = $"Auto-detected: {evt.AnomalyType} (threshold {evt.ThresholdValue}{evt.Unit}, actual {evt.ActualValue}{evt.Unit})",
           Category = MapAnomalyToCategory(evt.AnomalyType),
           Status = TicketStatusEnum.Open,
           Origin = TicketOriginEnum.AutoFromAlert,
           OriginAlertId = evt.AlertId
       };
       await _uow.Tickets.AddAsync(ticket);
       await _activity.LogAsync(ticket.Id, ActivityActionEnum.Created, actorRole: ActorRoleEnum.System);
       await _outbox.AddEvent(new TicketCreatedEvent { ... });
       await _uow.CommitTransactionAsync();
   }
   ```
2. `AccountStatusChangedConsumer` (Customer disabled → suspend tickets)

### 2.8. REST API contract

#### Endpoints
```
# Customer-facing
POST   /api/v1/tickets                                   (Customer)
GET    /api/v1/tickets/me                                (Customer)
PUT    /api/v1/tickets/{id}/rate                         (Customer — own)
PUT    /api/v1/tickets/{id}/reopen                       (Customer — own, within 7d)

# Common read
GET    /api/v1/tickets/{id}                              (Admin/Manager any; Customer own; Staff assigned)
GET    /api/v1/tickets/{id}/activities                   (— same —)
GET    /api/v1/tickets/{id}/comments                     (filter IsInternal by role)
GET    /api/v1/tickets/{id}/maintenance-logs             (— same —)
GET    /api/v1/tickets/{id}/sla                          (— same —)

# Manager
GET    /api/v1/manager/queue                             (Manager)
PUT    /api/v1/tickets/{id}/assign                       (Manager)
PUT    /api/v1/tickets/{id}/reassign                     (Manager)
PUT    /api/v1/tickets/{id}/approve                      (Manager)
PUT    /api/v1/tickets/{id}/reject                       (Manager)
PUT    /api/v1/tickets/{id}/escalate                     (Manager)
PUT    /api/v1/tickets/{id}/declare-incident             (Manager)
GET    /api/v1/manager/staff-workload                    (Manager)
GET    /api/v1/manager/tickets?filter=overdue            (Manager)
GET    /api/v1/manager/tickets?filter=escalated          (Manager)
GET    /api/v1/manager/tickets?filter=incidents          (Manager)

# Staff
GET    /api/v1/staff/my-tickets                          (Staff)
PUT    /api/v1/tickets/{id}/start                        (Staff — assigned)
PUT    /api/v1/tickets/{id}/hold                         (Staff — assigned)
PUT    /api/v1/tickets/{id}/resume                       (Staff — assigned)
PUT    /api/v1/tickets/{id}/resolve                      (Staff — assigned)
PUT    /api/v1/tickets/{id}/request-escalation           (Staff — assigned)

# Comments
POST   /api/v1/tickets/{id}/comments                     (Customer/Staff/Manager)
GET    /api/v1/tickets/{id}/comments                     (filter)

# Maintenance log
POST   /api/v1/tickets/{id}/maintenance-logs             (Staff)
PUT    /api/v1/maintenance-logs/{id}                     (Staff — own)
GET    /api/v1/maintenance-logs/{id}                     (Customer own ticket; Staff/Manager)

# Attachment
POST   /api/v1/tickets/{id}/attachments                  (Customer/Staff)
DELETE /api/v1/attachments/{id}                          (uploader / Admin)

# Dashboard
GET    /api/v1/ticket/dashboard/stats                    (Admin/Manager)
GET    /api/v1/ticket/dashboard/sla-trend                (Admin/Manager)

# Health
GET    /api/v1/ticket/health
```

#### Sample request — assign
```json
PUT /api/v1/tickets/{id}/assign
{
  "assignedStaffId": "6f4b...",
  "priority": 2,                  // P2 High
  "note": "Forwarded to Staff Long for routine check."
}
```
Response includes computed `slaDueAt`.

### 2.9. Test catalog

#### Unit tests (must-have)
- `TicketStateMachineTests`: full matrix 30+ transitions (every cell of §2.4.2)
- `TicketCreateCommandHandlerTests`: 8 cases
- `TicketAssignCommandHandlerTests`: 6 cases (valid, missing priority, staff inactive, ticket not in Open, double assign)
- `TicketResolveCommandHandlerTests`: 4 cases
- `TicketReopenCommandHandlerTests`: 5 cases (within 7d ok, >7d rejected, reopen count++, escalate on 2nd reopen, escalate on 3rd+)
- `SlaCalculatorTests`: 8 cases (compute due, pause/resume, total paused, breach detection)
- `BatteryAnomalyDetectedConsumerTests`: 4 cases (auto-create, dedup existing, dedup deleted ticket skip, mapping anomaly→category)

#### Integration tests
- POST create → GET list returns
- Assign → SLA timer starts → 80% warning event → breach event (use time mocking)
- Auto-create from event via MassTransit TestHarness
- Reopen flow end-to-end

---

## 3. NotificationService — P1

### 3.1. Trách nhiệm
1. Centralize notification orchestration.
2. Consume tất cả integration events từ Battery/Ticket/Auth → quyết định ai nhận, channel nào.
3. Push qua Expo (Mobile), email qua EmailService bus, SMS qua SmsService bus, in-app stored.
4. Customer preference + quiet hours + severity filter.
5. Device token management.
6. Notification history endpoint cho Mobile/Web.

### 3.2. Cấu trúc
```
services/NotificationService/
├── src/
│   ├── NotificationService.Api/Controllers/
│   │   ├── NotificationsController.cs        (list, mark read)
│   │   ├── PreferencesController.cs
│   │   ├── DeviceTokensController.cs
│   │   └── HealthController.cs
│   ├── NotificationService.Application/
│   │   ├── Consumers/
│   │   │   ├── TicketCreatedConsumer.cs
│   │   │   ├── TicketAssignedConsumer.cs
│   │   │   ├── TicketStatusChangedConsumer.cs
│   │   │   ├── TicketResolvedConsumer.cs
│   │   │   ├── TicketApprovedConsumer.cs
│   │   │   ├── TicketClosedConsumer.cs
│   │   │   ├── TicketEscalatedConsumer.cs
│   │   │   ├── IncidentDeclaredConsumer.cs
│   │   │   ├── SlaWarningConsumer.cs
│   │   │   ├── SlaBreachedConsumer.cs
│   │   │   ├── BatteryAnomalyDetectedConsumer.cs
│   │   │   ├── AccountActivatedConsumer.cs
│   │   │   └── AccountInvitedConsumer.cs
│   │   ├── Templates/
│   │   │   ├── ITemplateRenderer.cs
│   │   │   ├── HandlebarsTemplateRenderer.cs
│   │   │   └── Templates/                     (embedded .hbs files)
│   │   ├── Services/
│   │   │   ├── INotificationDispatcher.cs
│   │   │   ├── NotificationDispatcher.cs
│   │   │   ├── IUserResolver.cs               (resolve roleId → userIds — call AuthService)
│   │   │   └── UserResolver.cs
│   │   └── CQRS/...
│   ├── NotificationService.Domain/Entities/
│   │   ├── Notification.cs
│   │   ├── DeviceToken.cs
│   │   ├── NotificationPreference.cs
│   │   └── NotificationTemplate.cs
│   └── NotificationService.Infrastructure/
│       ├── Channels/
│       │   ├── INotificationChannel.cs
│       │   ├── ExpoPushChannel.cs              (HTTP + Polly retry)
│       │   ├── EmailBusChannel.cs              (publish to EmailService)
│       │   ├── SmsBusChannel.cs                (publish to SmsService)
│       │   └── InAppChannel.cs                 (store in DB)
│       └── Persistence/...
└── tests/...
```

### 3.3. Entities

#### `Notification`
| Field | Type | Note |
|-------|------|------|
| `Id` | `Guid` | — |
| `UserId` | `Guid` | recipient |
| `Type` | `NotificationTypeEnum` | xem enum |
| `Title` | `string(200)` | localized |
| `Body` | `string(1000)` | — |
| `Data` | `jsonb` | deep-link payload `{ ticketId, alertId, ... }` |
| `Channel` | `NotificationChannelEnum` | 1=Push, 2=Email, 3=Sms, 4=InApp |
| `Status` | `NotificationStatusEnum` | 1=Pending, 2=Sent, 3=Failed, 4=Read |
| `ReadAt` | `DateTime?` | — |
| `SentAt` | `DateTime?` | — |
| `FailureReason` | `string?` | — |
| `CreatedAt` | `DateTime` | indexed DESC |

```csharp
public enum NotificationTypeEnum {
    TicketCreated = 1, TicketAssigned = 2, TicketStatusChanged = 3,
    TicketResolved = 4, TicketApproved = 5, TicketClosed = 6,
    TicketEscalated = 7, IncidentDeclared = 8,
    SlaWarning = 9, SlaBreached = 10,
    BatteryAlertInfo = 11, BatteryAlertWarning = 12, BatteryAlertCritical = 13,
    AccountActivated = 14, AccountInvited = 15
}
```

#### `DeviceToken`
| Field | Type |
|-------|------|
| `Id` | Guid |
| `UserId` | Guid (indexed) |
| `ExpoPushToken` | string(255) UNIQUE |
| `Platform` | enum (iOS=1, Android=2) |
| `AppVersion` | string |
| `LastSeenAt` | DateTime |

#### `NotificationPreference`
| Field | Type | Default |
|-------|------|---------|
| `UserId` | Guid (PK) | — |
| `PushEnabled` | bool | true |
| `EmailDigestEnabled` | bool | true |
| `SmsCriticalEnabled` | bool | true (P1 only) |
| `MinSeverityForPush` | enum | Warning |
| `QuietHoursStart` | TimeOnly? | null |
| `QuietHoursEnd` | TimeOnly? | null |
| `TimeZone` | string | "Asia/Ho_Chi_Minh" |

### 3.4. Notification routing logic (`NotificationDispatcher`)

```
INPUT: NotificationTypeEnum + targetUserIds + payload
1. For each targetUserId:
   a. Load preference (cache 5min).
   b. Check quiet hours → if yes, defer push to in-app only.
   c. For each channel candidate by type mapping (e.g., Critical → Push+Email+Sms):
      - If channel disabled in preference → skip.
      - Render template.
      - Create Notification record (Status=Pending).
      - Invoke channel.SendAsync().
      - On success → update Status=Sent, SentAt.
      - On failure (3 retries via Polly) → Status=Failed, log.
```

**Type → Channel matrix:**
| NotificationType | InApp | Push | Email | SMS |
|-----------------|-------|------|-------|-----|
| TicketCreated (to Manager) | ✅ | ✅ | digest | — |
| TicketAssigned (to Staff) | ✅ | ✅ | ✅ | — |
| TicketAssigned (to Customer) | ✅ | ✅ | ✅ | — |
| SlaWarning (Staff + Manager) | ✅ | ✅ | — | — |
| SlaBreached P1 (Manager + Admin) | ✅ | ✅ | ✅ | ✅ |
| SlaBreached P2 (Manager) | ✅ | ✅ | ✅ | — |
| SlaBreached P3 (Manager) | ✅ | — | digest | — |
| BatteryAlertCritical (Customer) | ✅ | ✅ | ✅ | ✅ (if enabled) |
| BatteryAlertWarning (Customer) | ✅ | ✅ | — | — |
| BatteryAlertInfo | ✅ | — (chỉ in-app) | — | — |
| IncidentDeclared (broadcast Manager/Admin/LeadStaff) | ✅ | ✅ | ✅ | ✅ |

### 3.5. Endpoints
```
GET    /api/v1/notifications?status=&type=&page=         (mine)
GET    /api/v1/notifications/unread-count                (mine)
PUT    /api/v1/notifications/{id}/read                   (mine)
PUT    /api/v1/notifications/read-all                    (mine)
GET    /api/v1/notification-preferences                  (mine)
PUT    /api/v1/notification-preferences                  (mine)
POST   /api/v1/device-tokens                             (Mobile register)
DELETE /api/v1/device-tokens/{token}
```

### 3.6. Expo Push integration

```csharp
public class ExpoPushChannel : INotificationChannel {
    private readonly HttpClient _http;  // Polly retry via SharedInfrastructure
    private const string ExpoUrl = "https://exp.host/--/api/v2/push/send";

    public async Task<ChannelResult> SendAsync(SendRequest req, CancellationToken ct) {
        var payload = new {
            to = req.ExpoToken,
            title = req.Title,
            body = req.Body,
            data = req.Data,
            sound = "default",
            priority = req.IsCritical ? "high" : "normal",
            channelId = req.IsCritical ? "alerts-critical" : "alerts-default"
        };
        var resp = await _http.PostAsJsonAsync(ExpoUrl, payload, ct);
        // Parse Expo receipt; if DeviceNotRegistered → mark token invalid
        ...
    }
}
```

**Polly policy:** retry 3 lần exponential backoff (đã có sẵn pattern trong SharedInfrastructure).

---

## 4. KnowledgeBase module trong TicketService — P2

### 4.1. Mục đích
- Staff tìm hướng xử lý nhanh cho lỗi lặp lại.
- Manager soạn solution template.

### 4.2. Entity `KnowledgeBaseArticle`

| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | — |
| `Category` | `TicketCategoryEnum` | Match với ticket category để suggest |
| `Title` | string(200) | — |
| `Symptoms` | string(2000) | Markdown |
| `DiagnosisSteps` | string(4000) | Markdown checklist |
| `SolutionSteps` | string(4000) | Markdown steps |
| `RecommendedParts` | string? | JSON |
| `Tags` | string[] | Postgres array |
| `Status` | enum | 1=Draft, 2=Published, 3=Archived |
| `Version` | int | Bump khi update |
| `ViewCount` | int | Analytics |
| `HelpfulCount` | int | Staff vote helpful |
| `CreatedByUserId` | Guid | — |

### 4.3. Endpoints
```
GET    /api/v1/knowledge-base?category=&q=&tag=&page=    (Staff/Manager/Admin)
GET    /api/v1/knowledge-base/{id}                       (mọi role internal)
POST   /api/v1/knowledge-base                            (Manager/Admin) — Status=Draft
PUT    /api/v1/knowledge-base/{id}
PUT    /api/v1/knowledge-base/{id}/publish               (Manager/Admin)
PUT    /api/v1/knowledge-base/{id}/archive
DELETE /api/v1/knowledge-base/{id}                       (Admin)
POST   /api/v1/knowledge-base/{id}/helpful               (Staff vote)
GET    /api/v1/knowledge-base/suggest?ticketId={id}      (Staff — gợi ý theo ticket category + symptom match)
```

### 4.4. Suggest logic
```sql
SELECT id, title, helpful_count
FROM kb_articles
WHERE status = 2  -- Published
  AND category = :ticketCategory
ORDER BY helpful_count DESC, view_count DESC
LIMIT 5;
```
Future: ElasticSearch full-text trên Symptoms (out of scope capstone).

---

## 5. Reporting endpoints — P2

### 5.1. Quyết định kiến trúc
- KHÔNG tạo ReportingService riêng. Mỗi service tự expose `/api/v1/reports/*` endpoint.
- ApiGateway aggregate dashboard.

### 5.2. Reports

#### TicketService reports

| Report | Endpoint | Output |
|--------|----------|--------|
| SLA Compliance by Staff | `GET /api/v1/reports/sla-by-staff?from=&to=` | Array<{staffId, name, totalAssigned, met, breached, complianceRate}> |
| SLA Compliance by Priority | `GET /api/v1/reports/sla-by-priority?from=&to=` | {P1: ..., P2: ..., P3: ...} |
| Ticket Volume Trend | `GET /api/v1/reports/ticket-volume?granularity=day&from=&to=` | TimeSeries |
| Top Reopen Issues | `GET /api/v1/reports/top-reopen-issues?limit=10` | Array<{category, count, avgReopenCount}> |
| Staff Performance | `GET /api/v1/reports/staff-performance?from=&to=` | Array<{staffId, ticketsResolved, avgResolveHours, avgRating, slaCompliance}> |
| CSAT | `GET /api/v1/reports/csat?from=&to=` | {avgRating, ratingDistribution, totalRated} |
| Resolution Time Distribution | `GET /api/v1/reports/resolution-time-histogram` | Buckets |
| Category Breakdown | `GET /api/v1/reports/category-breakdown?from=&to=` | Array<{category, count}> |

#### BatteryService reports

| Report | Endpoint | Output |
|--------|----------|--------|
| Battery Health by Type | `GET /api/v1/reports/battery-health-by-type` | Array<{typeId, name, totalAssets, withActiveAlerts, healthScore}> |
| Alert Volume | `GET /api/v1/reports/alert-volume?granularity=day` | TimeSeries |
| Top Anomaly Types | `GET /api/v1/reports/top-anomalies?from=&to=&limit=10` | Array<{anomalyType, count, criticalCount}> |
| Asset Lifecycle | `GET /api/v1/reports/asset-lifecycle` | Array<{assetId, ageDays, cycleCount, alertsTotal}> |
| Warranty Expiry | `GET /api/v1/reports/warranty-expiring?within=90d` | Array<BatteryAsset> |

### 5.3. Export
- Mỗi report có optional `?format=csv` hoặc `?format=xlsx` → return file download.
- Sử dụng `ClosedXML` cho xlsx (lightweight, no Excel install required).

---

# Phần III — Hạ tầng & cross-cutting

## 6. TimescaleDB integration — P1

### 6.1. Đổi Postgres image
TimescaleDB vẫn là PostgreSQL 16 có thêm extension. Việc đổi image không biến toàn bộ database thành time-series database:

- AuthService, TicketService, NotificationService vẫn dùng table PostgreSQL thường.
- Chỉ các bảng time-series như `sensor_readings`, `iot_device_heartbeats`, `analytics_events` mới gọi `create_hypertable(...)`.
- Test đổi image phải chạy trên branch riêng và verify AuthService migrations/build không bị ảnh hưởng trước khi merge.

```yaml
# docker-compose.yml
postgres:
  image: timescale/timescaledb:latest-pg16
  # giữ nguyên rest of config (port 5433, volume, env vars)
```

### 6.2. Migration đầu tiên BatteryService
```csharp
public partial class InitialBatterySchema : Migration {
    protected override void Up(MigrationBuilder mb) {
        // Standard tables
        mb.CreateTable("battery_types", ...);
        mb.CreateTable("threshold_configs", ...);
        mb.CreateTable("battery_assets", ...);
        mb.CreateTable("alerts", ...);

        // SensorReading hypertable
        mb.Sql("CREATE EXTENSION IF NOT EXISTS timescaledb;");
        mb.CreateTable("sensor_readings", t => new {
            Time = t.Column<DateTime>("time", nullable: false),
            BatteryAssetId = t.Column<Guid>("battery_asset_id", nullable: false),
            Voltage = t.Column<decimal>("voltage", precision: 6, scale: 2, nullable: false),
            Current = t.Column<decimal>("current", precision: 8, scale: 2, nullable: false),
            Temperature = t.Column<decimal>("temperature", precision: 5, scale: 2, nullable: false),
            SocPercent = t.Column<decimal>("soc_percent", precision: 5, scale: 2, nullable: false),
            CycleCount = t.Column<int>("cycle_count", nullable: true),
            SourceDeviceId = t.Column<string>("source_device_id", maxLength: 64, nullable: true)
        });
        mb.Sql("SELECT create_hypertable('sensor_readings', 'time', if_not_exists => TRUE);");
        mb.Sql("CREATE INDEX idx_sr_asset_time ON sensor_readings (battery_asset_id, time DESC);");

        // Retention policy (90 days raw)
        mb.Sql("SELECT add_retention_policy('sensor_readings', INTERVAL '90 days');");
    }

    protected override void Down(MigrationBuilder mb) {
        mb.Sql("SELECT remove_retention_policy('sensor_readings', if_exists => TRUE);");
        mb.DropTable("sensor_readings");
        mb.DropTable("alerts");
        mb.DropTable("battery_assets");
        mb.DropTable("threshold_configs");
        mb.DropTable("battery_types");
    }
}
```

### 6.3. Continuous aggregates (Sprint sau)
```sql
CREATE MATERIALIZED VIEW sensor_readings_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    battery_asset_id,
    AVG(voltage) AS avg_voltage, MIN(voltage) AS min_voltage, MAX(voltage) AS max_voltage,
    AVG(current) AS avg_current,
    MAX(temperature) AS max_temperature, AVG(temperature) AS avg_temperature,
    AVG(soc_percent) AS avg_soc, MIN(soc_percent) AS min_soc
FROM sensor_readings
GROUP BY bucket, battery_asset_id;

SELECT add_continuous_aggregate_policy('sensor_readings_hourly',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '30 minutes');
```

### 6.4. Query strategy
- `granularity=1m` → query raw `sensor_readings`
- `granularity=1h` → query `sensor_readings_hourly`
- `granularity=1d` → manual aggregate hoặc continuous aggregate `_daily`

---

## 6bis. FileStorage metadata foundation — P1

### 6bis.1. Lý do

FileStorageService hiện tại upload trực tiếp lên MinIO/S3 và trả `objectKey`. Cách này đủ cho demo upload/download đơn giản nhưng chưa đủ cho business flow:

- `AccountProfile.AvatarFileId`
- `TicketAttachment.FileId`
- `MaintenanceLog.BeforePhotosFileIds`
- `IotFirmwareRelease.FileId`

Các service trên cần tham chiếu file bằng `fileId` ổn định, không nên lưu raw `objectKey` của object storage.

### 6bis.2. Quyết định

Bổ sung metadata DB cho FileStorageService:

- Thêm `FileStorageService.Domain` nếu service hiện tại chưa có Domain project.
- Thêm entity `UploadedFile` kế thừa `AuditableEntity`.
- Thêm enum `FilePurposeEnum` và `FileStatusEnum`.
- Thêm `ApplicationDbContext`, EF configuration, migration `AddUploadedFileMetadata`.
- Upload flow: upload binary lên object storage trước, tạo `UploadedFile` metadata sau khi upload thành công, response trả `fileId`.

### 6bis.3. Entity `UploadedFile`

| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | `fileId` trả về cho Auth/Ticket/MaintenanceLog |
| `BucketName` | string(100) | MinIO/S3 bucket |
| `ObjectKey` | string(500) | đường dẫn object storage, internal detail |
| `OriginalFileName` | string(255) | tên file client upload |
| `ContentType` | string(100) | whitelist theo purpose |
| `SizeBytes` | long | validate max size |
| `Purpose` | FilePurposeEnum | Avatar, TicketAttachment, MaintenancePhoto, KbImage, Firmware, Other |
| `UploadedByUserId` | Guid? | null nếu system/internal |
| `Status` | FileStatusEnum | Uploaded, Processing, Ready, Quarantined, Deleted |
| `ChecksumSha256` | string(64)? | integrity/dedup sau này |
| `DeletedAt` | DateTime? | soft delete/cleanup |
| `CreatedAt`, `CreatedBy`, `UpdatedAt`, `UpdatedBy`, `IsDeleted` | — | từ `AuditableEntity` |

```csharp
public enum FilePurposeEnum
{
    Other = 0,
    Avatar = 1,
    TicketAttachment = 2,
    MaintenancePhoto = 3,
    KbImage = 4,
    Firmware = 5
}

public enum FileStatusEnum
{
    Uploaded = 1,
    Processing = 2,
    Ready = 3,
    Quarantined = 4,
    Deleted = 5
}
```

### 6bis.4. Migration

```csharp
public partial class AddUploadedFileMetadata : Migration
{
    protected override void Up(MigrationBuilder mb)
    {
        mb.CreateTable("uploaded_files", t => new
        {
            Id = t.Column<Guid>("id", nullable: false),
            BucketName = t.Column<string>("bucket_name", maxLength: 100, nullable: false),
            ObjectKey = t.Column<string>("object_key", maxLength: 500, nullable: false),
            OriginalFileName = t.Column<string>("original_file_name", maxLength: 255, nullable: false),
            ContentType = t.Column<string>("content_type", maxLength: 100, nullable: false),
            SizeBytes = t.Column<long>("size_bytes", nullable: false),
            Purpose = t.Column<int>("purpose", nullable: false),
            UploadedByUserId = t.Column<Guid>("uploaded_by_user_id", nullable: true),
            Status = t.Column<int>("status", nullable: false, defaultValue: 3),
            ChecksumSha256 = t.Column<string>("checksum_sha256", maxLength: 64, nullable: true),
            DeletedAt = t.Column<DateTime>("deleted_at", nullable: true),
            CreatedAt = t.Column<DateTime>("created_at", nullable: false),
            CreatedBy = t.Column<Guid>("created_by", nullable: true),
            UpdatedAt = t.Column<DateTime>("updated_at", nullable: true),
            UpdatedBy = t.Column<Guid>("updated_by", nullable: true),
            IsDeleted = t.Column<bool>("is_deleted", nullable: false, defaultValue: false)
        }, constraints: table =>
        {
            table.PrimaryKey("pk_uploaded_files", x => x.Id);
        });

        mb.CreateIndex("ix_uploaded_files_object_key", "uploaded_files", "object_key", unique: true);
        mb.CreateIndex("ix_uploaded_files_uploaded_by_purpose", "uploaded_files", new[] { "uploaded_by_user_id", "purpose", "is_deleted" });
        mb.CreateIndex("ix_uploaded_files_status_created", "uploaded_files", new[] { "status", "created_at" });
    }

    protected override void Down(MigrationBuilder mb)
    {
        mb.DropTable("uploaded_files");
    }
}
```

### 6bis.5. API contract update

```
POST   /api/v1/files/upload                             (multipart)
GET    /api/v1/files/{id}/metadata
GET    /api/v1/files/{id}/presigned-url?variant=original
GET    /api/v1/files/{id}/download
DELETE /api/v1/files/{id}                               (soft delete metadata + delete object or schedule cleanup)
```

Upload request:
```http
POST /api/v1/files/upload
Content-Type: multipart/form-data

file=<avatar.png>
purpose=Avatar
```

Upload response:
```json
{
  "isSuccess": true,
  "statusCode": 201,
  "message": "Upload file thành công.",
  "data": {
    "fileId": "6c9f6e5d-bf26-49e0-a2f4-7e1d2e3a5c90",
    "objectKey": "avatars/6c9f6e5dbf2649e0a2f47e1d2e3a5c90.png",
    "fileName": "avatar.png",
    "contentType": "image/png",
    "sizeBytes": 123456,
    "purpose": "Avatar",
    "status": "Ready",
    "publicUrl": null
  },
  "listErrors": []
}
```

`objectKey` có thể trả cho debug/backward compatibility, nhưng service khác không được lưu `objectKey` làm foreign reference. Chỉ lưu `fileId`.

### 6bis.6. Validation theo purpose

| Purpose | Max size | Content type |
|---------|----------|--------------|
| Avatar | 5MB | image/png, image/jpeg, image/webp |
| TicketAttachment | 10MB | image/png, image/jpeg, application/pdf |
| MaintenancePhoto | 10MB | image/png, image/jpeg |
| KbImage | 5MB | image/png, image/jpeg, image/webp |
| Firmware | configurable | application/octet-stream, application/x-binary |

### 6bis.7. Sprint 1 scope

Sprint 1 chỉ cần metadata foundation:

- `UploadedFile` entity + enum + migration.
- Upload trả `fileId`.
- Get metadata by `fileId`.
- Get presigned URL by `fileId`.
- Delete by `fileId`.
- Chưa cần resize, EXIF strip, virus scan, variants. Các phần đó nằm ở §62.

---

## 7. Mở rộng AuthService cho profile + skill — P1

### 7.1. Quyết định
KHÔNG tách UserService trong scope capstone, nhưng cũng KHÔNG nhét staff-specific fields trực tiếp vào bảng `Account`.

AuthService vẫn là owner của identity/profile metadata. `Account` giữ vai trò bảng identity chung cho toàn hệ thống; các thông tin mở rộng được tách thành extension tables:

- `AccountProfile`: thông tin hồ sơ chung cho mọi role.
- `StaffProfile`: thông tin phục vụ phân công công việc cho role Staff.
- `StaffSkill`: skill matrix dạng normalized để query/filter Staff theo kỹ năng.

### 7.2. Entity bổ sung

#### `AccountProfile` (1-1 với `Account`)
| Field | Type | Note |
|-------|------|------|
| `AccountId` | Guid | PK/FK → `accounts.id` |
| `AvatarFileId` | Guid? | file nội bộ user upload, reference FileStorageService `UploadedFile.Id` |
| `ExternalAvatarUrl` | string(1000)? | avatar từ provider ngoài như Google `picture` |
| `AvatarSource` | enum | 0=None, 1=Uploaded, 2=Google |
| `Address` | string(500)? | profile chung |
| `BirthDate` | DateOnly? | phục vụ compliance/minor policy sau này |
| `TimeZone` | string(64) | default `Asia/Ho_Chi_Minh` |
| `CreatedAt`, `UpdatedAt` | DateTime | audit nhẹ |

#### `StaffProfile` (1-1 với `Account`, chỉ role Staff)
| Field | Type | Note |
|-------|------|------|
| `AccountId` | Guid | PK/FK → `accounts.id` |
| `EmployeeCode` | string(20) | UNIQUE, mã nhân viên |
| `Department` | string(100)? | bộ phận |
| `MaxConcurrentTickets` | int | default 10, TicketService dùng để validate assign |
| `IsAvailable` | bool | Manager có thể tạm ẩn Staff khỏi assignment queue |
| `Notes` | string(500)? | ghi chú nội bộ |
| `CreatedAt`, `UpdatedAt` | DateTime | audit nhẹ |

#### `StaffSkill` (nhiều skill cho 1 Staff)
| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | PK |
| `StaffAccountId` | Guid | FK → `staff_profiles.account_id` |
| `SkillCode` | string(50) | ví dụ `LiFePO4`, `NMC`, `OnSite`, `BMS` |
| `SkillLevel` | int | 1=Basic, 2=Intermediate, 3=Advanced |
| `CertifiedUntil` | DateTime? | optional |

**Constraint:** unique `(StaffAccountId, SkillCode)`.

#### Avatar source rule
```csharp
public enum AvatarSourceEnum
{
    None = 0,
    Uploaded = 1,
    Google = 2
}
```

`AvatarFileId` chỉ dùng cho file do user upload vào FileStorageService. Không lưu Google avatar URL vào `AvatarFileId`.

Rule resolve avatar cho FE:
1. Nếu `AvatarFileId != null` và file còn usable → `displayAvatarUrl` = presigned/public URL từ FileStorageService.
2. Nếu không có uploaded avatar nhưng `ExternalAvatarUrl != null` → `displayAvatarUrl` = Google/external URL.
3. Nếu cả hai null → `displayAvatarUrl = null`, FE hiển thị initials/default avatar.

Google login chỉ cập nhật `ExternalAvatarUrl` khi user chưa upload avatar nội bộ. Không được ghi đè avatar do user tự upload.

### 7.3. Migration
```csharp
public partial class AddAccountProfileExtensionTables : Migration {
    protected override void Up(MigrationBuilder mb) {
        mb.CreateTable("account_profiles", t => new {
            AccountId = t.Column<Guid>("account_id", nullable: false),
            AvatarFileId = t.Column<Guid>("avatar_file_id", nullable: true),
            ExternalAvatarUrl = t.Column<string>("external_avatar_url", maxLength: 1000, nullable: true),
            AvatarSource = t.Column<int>("avatar_source", nullable: false, defaultValue: 0),
            Address = t.Column<string>("address", maxLength: 500, nullable: true),
            BirthDate = t.Column<DateOnly>("birth_date", nullable: true),
            TimeZone = t.Column<string>("time_zone", maxLength: 64, nullable: false, defaultValue: "Asia/Ho_Chi_Minh"),
            CreatedAt = t.Column<DateTime>("created_at", nullable: false),
            UpdatedAt = t.Column<DateTime>("updated_at", nullable: true)
        }, constraints: table => {
            table.PrimaryKey("pk_account_profiles", x => x.AccountId);
            table.ForeignKey("fk_account_profiles_accounts", x => x.AccountId, "accounts", "id", onDelete: ReferentialAction.Cascade);
        });

        mb.CreateTable("staff_profiles", t => new {
            AccountId = t.Column<Guid>("account_id", nullable: false),
            EmployeeCode = t.Column<string>("employee_code", maxLength: 20, nullable: false),
            Department = t.Column<string>("department", maxLength: 100, nullable: true),
            MaxConcurrentTickets = t.Column<int>("max_concurrent_tickets", nullable: false, defaultValue: 10),
            IsAvailable = t.Column<bool>("is_available", nullable: false, defaultValue: true),
            Notes = t.Column<string>("notes", maxLength: 500, nullable: true),
            CreatedAt = t.Column<DateTime>("created_at", nullable: false),
            UpdatedAt = t.Column<DateTime>("updated_at", nullable: true)
        }, constraints: table => {
            table.PrimaryKey("pk_staff_profiles", x => x.AccountId);
            table.ForeignKey("fk_staff_profiles_accounts", x => x.AccountId, "accounts", "id", onDelete: ReferentialAction.Cascade);
        });
        mb.CreateIndex("ix_staff_profiles_employee_code", "staff_profiles", "employee_code", unique: true);

        mb.CreateTable("staff_skills", t => new {
            Id = t.Column<Guid>("id", nullable: false),
            StaffAccountId = t.Column<Guid>("staff_account_id", nullable: false),
            SkillCode = t.Column<string>("skill_code", maxLength: 50, nullable: false),
            SkillLevel = t.Column<int>("skill_level", nullable: false),
            CertifiedUntil = t.Column<DateTime>("certified_until", nullable: true)
        }, constraints: table => {
            table.PrimaryKey("pk_staff_skills", x => x.Id);
            table.ForeignKey("fk_staff_skills_staff_profiles", x => x.StaffAccountId, "staff_profiles", "account_id", onDelete: ReferentialAction.Cascade);
        });
        mb.CreateIndex("ix_staff_skills_staff_skill", "staff_skills", new[] { "staff_account_id", "skill_code" }, unique: true);
    }
    protected override void Down(MigrationBuilder mb) {
        mb.DropTable("staff_skills");
        mb.DropTable("staff_profiles");
        mb.DropTable("account_profiles");
    }
}
```

### 7.4. New endpoints
```
GET    /api/v1/auth/staff?skill=LiFePO4                  (Manager — for assignment)
GET    /api/v1/auth/staff/{id}/assignment-profile        (internal — TicketService validate staff active/skill/capacity)
PUT    /api/v1/auth/admin/staff/{id}/profile             (Admin/Manager — update StaffProfile)
POST   /api/v1/auth/admin/staff/{id}/skills              (Admin/Manager — add/update skill)
DELETE /api/v1/auth/admin/staff/{id}/skills/{skillCode}  (Admin/Manager)
GET    /api/v1/auth/me                                   (mọi role — profile response cho FE)
PUT    /api/v1/auth/me/profile                           (mọi role update profile)
POST   /api/v1/auth/me/avatar                            (mọi role — body `{ "avatarFileId": "..." }`)
```

**Lưu ý luồng assign:** AuthService chỉ trả staff metadata (`IsAvailable`, `MaxConcurrentTickets`, skills). TicketService vẫn là nơi đếm workload thực tế vì ticket active thuộc DB của TicketService.

### 7.5. New integration event
- `AccountProfileUpdatedEvent`
- `StaffProfileUpdatedEvent`
- `StaffSkillsUpdatedEvent` → TicketService có thể invalidate/cache lại skill matrix.

### 7.6. Avatar upload & Google avatar flow

#### User upload avatar nội bộ
```
FE/Mobile
  └─ POST /api/v1/files/upload (purpose=avatar, multipart file)
        └─ FileStorageService upload MinIO/S3 + tạo UploadedFile metadata
              └─ response { fileId, objectKey, contentType, sizeBytes, status }
  └─ POST /api/v1/auth/me/avatar { "avatarFileId": fileId }
        └─ AuthService update AccountProfile.AvatarFileId, AvatarSource=Uploaded
```

AuthService không xử lý multipart stream. FileStorageService là service duy nhất quản lý binary file, metadata, signed URL, cleanup, resize/scan sau này.

Không xóa avatar cũ ngay khi user đổi avatar. Chỉ đổi `AvatarFileId`; file cũ để cleanup job xử lý sau để tránh lỗi khi client/cache còn dùng URL cũ.

#### Google login avatar
Google ID token/profile trả về `picture` URL. AuthService lưu URL này vào `AccountProfile.ExternalAvatarUrl`, không upload vào FileStorageService ở Sprint 1.

Pseudo-flow:
```csharp
var googleUser = await _googleOAuthHelper.ValidateAsync(idToken, ct);
// googleUser.Picture = "https://lh3.googleusercontent.com/..."

if (newAccount)
{
    await _unitOfWork.Accounts.AddAsync(account);
    await _unitOfWork.AccountProfiles.AddAsync(new AccountProfile
    {
        AccountId = account.Id,
        ExternalAvatarUrl = googleUser.Picture,
        AvatarSource = string.IsNullOrWhiteSpace(googleUser.Picture)
            ? AvatarSourceEnum.None
            : AvatarSourceEnum.Google,
        TimeZone = "Asia/Ho_Chi_Minh"
    });
}
else if (profile.AvatarFileId == null && !string.IsNullOrWhiteSpace(googleUser.Picture))
{
    profile.ExternalAvatarUrl = googleUser.Picture;
    profile.AvatarSource = AvatarSourceEnum.Google;
}
```

Nếu sau này muốn hệ thống tự quản lý cả avatar Google, có thể thêm background/command tải ảnh từ Google về FileStorageService. Việc đó phải có SSRF guard, content-type validation, file-size limit, và không nằm trong Sprint 1.

#### Profile response cho FE

FE chỉ cần dùng `data.profile.displayAvatarUrl` để render avatar. Backend resolve theo priority Uploaded → Google → null.

Customer login Google, chưa upload avatar:
```json
{
  "isSuccess": true,
  "statusCode": 200,
  "message": "Lấy thông tin profile thành công.",
  "data": {
    "id": "9f0c1b4e-2b2a-4f43-83de-89e12c9b6f2a",
    "email": "nguyenvana@gmail.com",
    "phoneNumber": null,
    "fullName": "Nguyen Van A",
    "status": 1,
    "emailConfirmed": true,
    "phoneConfirmed": false,
    "twoFactorEnabled": false,
    "roles": ["Customer"],
    "profile": {
      "avatarFileId": null,
      "externalAvatarUrl": "https://lh3.googleusercontent.com/a/ACg8ocK...",
      "avatarSource": "Google",
      "displayAvatarUrl": "https://lh3.googleusercontent.com/a/ACg8ocK...",
      "address": null,
      "birthDate": null,
      "timeZone": "Asia/Ho_Chi_Minh"
    },
    "staffProfile": null,
    "lastLoginAt": "2026-05-13T09:30:00Z",
    "createdAt": "2026-05-13T09:30:00Z",
    "updatedAt": null
  },
  "listErrors": []
}
```

User đã upload avatar nội bộ:
```json
{
  "isSuccess": true,
  "statusCode": 200,
  "message": "Lấy thông tin profile thành công.",
  "data": {
    "id": "9f0c1b4e-2b2a-4f43-83de-89e12c9b6f2a",
    "email": "nguyenvana@gmail.com",
    "phoneNumber": "0901234567",
    "fullName": "Nguyen Van A",
    "status": 1,
    "emailConfirmed": true,
    "phoneConfirmed": true,
    "twoFactorEnabled": false,
    "roles": ["Customer"],
    "profile": {
      "avatarFileId": "6c9f6e5d-bf26-49e0-a2f4-7e1d2e3a5c90",
      "externalAvatarUrl": "https://lh3.googleusercontent.com/a/ACg8ocK...",
      "avatarSource": "Uploaded",
      "displayAvatarUrl": "https://minio-or-cdn.example.com/avatars/6c9f6e5d.png?signature=...",
      "address": "Quận 7, TP.HCM",
      "birthDate": "2002-04-20",
      "timeZone": "Asia/Ho_Chi_Minh"
    },
    "staffProfile": null,
    "lastLoginAt": "2026-05-13T09:30:00Z",
    "createdAt": "2026-05-01T08:00:00Z",
    "updatedAt": "2026-05-13T09:40:00Z"
  },
  "listErrors": []
}
```

Staff profile:
```json
{
  "isSuccess": true,
  "statusCode": 200,
  "message": "Lấy thông tin profile thành công.",
  "data": {
    "id": "2b6e47c2-f3c0-4de7-9e1d-3d90f1b5c12a",
    "email": "staff1@gsu26se55.com",
    "phoneNumber": "0912345678",
    "fullName": "Pham Huu Long",
    "status": 1,
    "emailConfirmed": true,
    "phoneConfirmed": true,
    "twoFactorEnabled": false,
    "roles": ["Staff"],
    "profile": {
      "avatarFileId": null,
      "externalAvatarUrl": null,
      "avatarSource": "None",
      "displayAvatarUrl": null,
      "address": "Thu Duc, TP.HCM",
      "birthDate": "1998-10-12",
      "timeZone": "Asia/Ho_Chi_Minh"
    },
    "staffProfile": {
      "employeeCode": "STF001",
      "department": "Maintenance",
      "maxConcurrentTickets": 10,
      "isAvailable": true,
      "skills": [
        {
          "skillCode": "LiFePO4",
          "skillLevel": 3,
          "skillLevelName": "Advanced",
          "certifiedUntil": "2027-01-01T00:00:00Z"
        },
        {
          "skillCode": "OnSite",
          "skillLevel": 2,
          "skillLevelName": "Intermediate",
          "certifiedUntil": null
        }
      ]
    },
    "lastLoginAt": "2026-05-13T09:30:00Z",
    "createdAt": "2026-05-01T08:00:00Z",
    "updatedAt": "2026-05-12T10:00:00Z"
  },
  "listErrors": []
}
```

---

## 8. Cross-cutting concerns — P1

### 8.1. Outbox pattern cho mọi service publish event

#### Pattern (đã có trong AuthService — copy structure)
1. Entity `OutboxMessage`:
   ```csharp
   public class OutboxMessage {
       public Guid Id { get; set; }
       public string EventType { get; set; } = string.Empty;  // typeof(T).FullName
       public string Payload { get; set; } = string.Empty;     // JSON
       public DateTime OccurredOnUtc { get; set; }
       public DateTime? ProcessedOnUtc { get; set; }
       public int RetryCount { get; set; }
       public string? Error { get; set; }
       public string CorrelationId { get; set; } = string.Empty;
   }
   ```
2. Trong handler — thay vì publish trực tiếp:
   ```csharp
   await _uow.OutboxMessages.AddAsync(new OutboxMessage {
       EventType = typeof(BatteryAnomalyDetectedEvent).FullName!,
       Payload = JsonSerializer.Serialize(evt),
       OccurredOnUtc = DateTime.UtcNow,
       CorrelationId = _correlation.Get()
   });
   await _uow.CommitTransactionAsync();  // atomic với business changes
   ```
3. `OutboxRelayBackgroundService` (5s tick):
   - Lấy 100 message chưa processed.
   - Deserialize → publish qua MassTransit.
   - Mark `ProcessedOnUtc = now`.
   - Exception → tăng `RetryCount`, ghi `Error`, retry exponential backoff đến max 5 lần → dead letter queue.

### 8.2. Inbox idempotency cho consumer

`SharedInfrastructure/Idempotency` đã có `RedisInboxStore`. Mỗi consumer:
```csharp
public class BatteryAnomalyDetectedConsumer : IConsumer<BatteryAnomalyDetectedEvent> {
    private readonly IInboxStore _inbox;

    public async Task Consume(ConsumeContext<BatteryAnomalyDetectedEvent> ctx) {
        var msgId = ctx.MessageId.ToString();
        if (await _inbox.AlreadyProcessed(msgId)) return;  // dedup

        await ProcessAsync(ctx.Message);
        await _inbox.MarkProcessed(msgId, ttl: TimeSpan.FromDays(7));
    }
}
```

### 8.3. Compensating actions (saga light)
- Trường hợp: TicketCreate thành công nhưng publish event thất bại → Outbox đảm bảo eventually consistent.
- Trường hợp: Alert→Ticket creation fail → consumer retry 3 lần → DLQ → manual reprocess via admin endpoint `POST /api/v1/admin/dlq/reprocess/{messageId}`.

### 8.4. Distributed tracing (OpenTelemetry)

```csharp
// Program.cs từng service
builder.Services.AddOpenTelemetry()
    .WithTracing(t => t
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddEntityFrameworkCoreInstrumentation()
        .AddSource("MassTransit")
        .AddOtlpExporter(o => o.Endpoint = new Uri("http://tempo:4317")));
```

Add Tempo to docker-compose:
```yaml
tempo:
  image: grafana/tempo:latest
  command: ["-config.file=/etc/tempo.yaml"]
  volumes: ["./monitoring/tempo.yaml:/etc/tempo.yaml"]
  ports: ["3200:3200"]
```

### 8.5. Correlation ID propagation
- Đã có middleware + bus filter trong SharedInfrastructure.
- Mọi log thông qua Serilog enricher tự động append `CorrelationId`.

### 8.6. Idempotency-Key cho POST mutating
Middleware `IdempotencyKeyMiddleware` đã có. Apply cho:
- `POST /api/v1/tickets` (Customer mobile có thể retry)
- `POST /api/v1/tickets/{id}/comments`
- `POST /api/sensor-readings/batch`
- `POST /api/v1/notifications/mark-read-bulk`

Header: `Idempotency-Key: <uuid>` → server lưu response 24h trong Redis.

---

## 9. Observability — hoàn thiện P2

### 9.1. Đã có
- Prometheus scrape `/metrics` (chưa wire cho service mới).
- Grafana có default dashboard.
- Loki nhận log Serilog.
- AlertManager + RabbitMQ Prometheus plugin.

### 9.2. Cần thêm

#### Metrics business
Mỗi service đăng ký custom counter:
```csharp
// SharedInfrastructure/Metrics/AppMetrics.cs đã có. Thêm:
public static readonly Counter TicketsCreated = Metrics
    .CreateCounter("tickets_created_total", "Total tickets created", "priority", "category", "origin");

public static readonly Counter SlaBreaches = Metrics
    .CreateCounter("sla_breaches_total", "Total SLA breaches", "priority");

public static readonly Histogram TicketResolutionMinutes = Metrics
    .CreateHistogram("ticket_resolution_minutes", "Time to resolve ticket",
        new HistogramConfiguration {
            LabelNames = new[] { "priority", "category" },
            Buckets = new[] { 30.0, 60, 120, 240, 480, 1440, 2880, 4320 }
        });

public static readonly Counter AlertsDetected = Metrics
    .CreateCounter("battery_alerts_detected_total", "Total alerts", "severity", "anomaly_type");

public static readonly Counter NotificationsSent = Metrics
    .CreateCounter("notifications_sent_total", "Total notifications", "channel", "status");
```

#### Dashboards Grafana
1. **SLA Operations** (panel list):
   - Queue size (open tickets) — gauge per priority
   - Breach rate last 1h/24h
   - Avg resolution time per priority
   - Reopen rate trend
   - Staff workload heatmap

2. **Battery Health**:
   - Active alerts count by severity
   - Top anomaly types pie
   - Asset count by status
   - Sensor ingest rate (msgs/s)

3. **System Health**:
   - Request rate per service
   - Error rate per service
   - P95/P99 latency
   - RabbitMQ queue depth + DLQ count
   - DB connection pool usage
   - Outbox lag (unprocessed count)

#### Alert rules (`alertmanager.yaml`)
```yaml
groups:
  - name: business
    rules:
      - alert: SlaBreachRateHigh
        expr: rate(sla_breaches_total[15m]) > 0.1
        for: 5m
        annotations:
          summary: "SLA breach rate > 10% trong 15 phút"

      - alert: OutboxLagging
        expr: outbox_unprocessed_count > 100
        for: 5m

      - alert: ServiceDown
        expr: up{job=~"battery|ticket|notification"} == 0
        for: 1m
```

### 9.3. Structured logging convention
```csharp
_logger.LogInformation("Ticket {TicketId} assigned to Staff {StaffId} with priority {Priority} by Manager {ManagerId}",
    ticket.Id, staffId, priority, currentUserId);
```
- Luôn dùng structured (named placeholders), không string interpolation.
- Loki query: `{service="ticket"} | json | TicketId="..."`.

---

## 10. API Gateway hoàn thiện — P1

### 10.1. JWT validation tại gateway
- Validate signature + expiry tại gateway.
- Inject claims vào header cho downstream:
  - `X-User-Id: {userId}`
  - `X-User-Role: {role}`
  - `X-User-Email: {email}`
- Downstream service dùng `CurrentUserService` (đã có trong SharedInfrastructure) đọc header thay vì decode JWT lại.

### 10.2. Rate limiting
Tận dụng built-in .NET 8:
```csharp
services.AddRateLimiter(opts => {
    opts.AddFixedWindowLimiter("auth", o => { o.PermitLimit = 10; o.Window = TimeSpan.FromMinutes(1); });
    opts.AddSlidingWindowLimiter("api", o => { o.PermitLimit = 100; o.Window = TimeSpan.FromMinutes(1); o.SegmentsPerWindow = 6; });
});
```
- `/api/v1/auth/login`: 5 req/min per IP
- `/api/v1/auth/forgot-password`: 3 req/hour per IP
- `/api/v1/tickets` POST: 30 req/min per user
- `/api/sensor-readings/batch`: 1000 req/min per ApiKey

### 10.3. CORS
```csharp
services.AddCors(opts => opts.AddPolicy("frontend", p => p
    .WithOrigins("http://localhost:5173", "https://app.gsu26se55.com")
    .AllowAnyHeader().AllowAnyMethod().AllowCredentials()));
```

### 10.4. Aggregate Swagger
Gateway expose `/swagger` aggregate từ N service:
- `/swagger/auth/v1/swagger.json`
- `/swagger/battery/v1/swagger.json`
- ...

### 10.5. Health & readiness
```
GET /health/live              → 200 if process alive
GET /health/ready             → 200 if DB + Redis + RabbitMQ reachable
GET /health/startup           → 200 after migrations done
```
Map vào k8s probes.

---

# Phần IV — Quality & operations

## 11. Test strategy (coverage ≥ 80%) — P1

### 11.1. Pyramid
```
        E2E (15%)
       ──────────
      Integration (35%)
     ─────────────────
    Unit (50%)
   ───────────────────
```

### 11.2. Unit test stack
- xUnit + Moq + FluentAssertions
- Bộ test mỗi handler:
  - `success` case
  - `validation failure` (mỗi field)
  - `business rule violation` (entity not found, soft deleted, status conflict)
  - `concurrent edit conflict` nếu có

### 11.3. Integration test stack
- `Microsoft.AspNetCore.Mvc.Testing.WebApplicationFactory`
- TestContainers: postgres + redis + rabbitmq
- TimescaleDB cần image `timescale/timescaledb:latest-pg16` trong fixture
- MassTransit `TestHarness` cho event/consumer

### 11.4. Sample test
```csharp
public class TicketAssignCommandHandlerTests {
    [Fact]
    public async Task Should_Start_Sla_Timer_With_P1_4hours() {
        // arrange
        var uow = MockUowFactory.WithTicket(status: TicketStatusEnum.Open);
        var handler = new TicketAssignCommandHandler(uow.Object, ...);
        var cmd = new TicketAssignCommand { TicketId = TicketId, AssignedStaffId = StaffId, Priority = TicketPriorityEnum.P1Critical };

        // act
        var resp = await handler.Handle(cmd, default);

        // assert
        resp.IsSuccess.Should().BeTrue();
        uow.Verify(x => x.SlaTimers.AddAsync(It.Is<SlaTimer>(t =>
            t.Priority == TicketPriorityEnum.P1Critical &&
            (t.DueAt - t.StartedAt).TotalHours == 4)));
    }

    [Fact]
    public async Task Should_Reject_Assign_When_Ticket_Not_Open() {
        var uow = MockUowFactory.WithTicket(status: TicketStatusEnum.Resolved);
        var handler = new TicketAssignCommandHandler(uow.Object, ...);
        var resp = await handler.Handle(new TicketAssignCommand { ... }, default);
        resp.IsSuccess.Should().BeFalse();
        resp.Message.Should().Contain("Open");
    }
}
```

### 11.5. State machine test pattern
```csharp
[Theory]
[InlineData(TicketStatusEnum.Open, TicketStatusEnum.Assigned, ActorRoleEnum.Manager, true)]
[InlineData(TicketStatusEnum.Open, TicketStatusEnum.Assigned, ActorRoleEnum.Staff, false)]   // wrong actor
[InlineData(TicketStatusEnum.Closed, TicketStatusEnum.Open, ActorRoleEnum.Customer, false)]  // can't reopen closed
[InlineData(TicketStatusEnum.ClosedPendingRate, TicketStatusEnum.Open, ActorRoleEnum.Customer, true)]
// ... all 30+ transitions
public void CanTransition_Matrix(TicketStatusEnum from, TicketStatusEnum to, ActorRoleEnum actor, bool expected) {
    var ticket = new Ticket { Status = from };
    var result = _stateMachine.CanTransition(ticket, to, actor, Guid.NewGuid());
    result.IsAllowed.Should().Be(expected);
}
```

### 11.6. CI coverage gate
GitHub Actions step:
```yaml
- name: Coverage gate
  run: |
    dotnet tool install -g dotnet-reportgenerator-globaltool
    reportgenerator -reports:"**/coverage.cobertura.xml" -targetdir:"coverage" -reporttypes:"Cobertura"
    THRESHOLD=80
    PCT=$(grep -oP 'line-rate="\K[0-9.]+' coverage/Cobertura.xml | head -1 | awk '{print $1*100}')
    [ "$(echo "$PCT < $THRESHOLD" | bc)" = 1 ] && exit 1 || exit 0
```

---

## 12. Seed data & migration strategy — P1

### 12.1. Seed data scope (script `tools/seed.sh`)

**Accounts (AuthService):**
- 1 Admin: `admin@gsu26se55.com` / `Admin@123`
- 2 Manager: `manager1@`, `manager2@`
- 3 Staff: `staff1@`, `staff2@`, `staff3@` với skills khác nhau
- 5 Customer: `customer1@`...`customer5@`

**Battery (BatteryService):**
- 3 BatteryType: LiFePO4 12V 100Ah / LiFePO4 24V 200Ah / NMC 48V 50Ah
- 3 ThresholdConfig (1 per type)
- 10 BatteryAsset gắn với 5 Customer (mỗi customer 2 asset)
- 10000 SensorReading (last 7 days, 1 reading/10min, có chèn ~5 anomaly events)

**Ticket (TicketService):**
- 5 KnowledgeBaseArticle (1 per category)
- 12 Ticket trong các state khác nhau:
  - 2 NEW, 2 OPEN, 2 ASSIGNED, 2 IN_PROGRESS, 1 RESOLVED, 1 CLOSED_PENDING_RATE, 1 CLOSED (rated), 1 ESCALATED

**Notification (NotificationService):**
- 50 Notification history mẫu

### 12.2. Migration ordering
1. FileStorageService AddUploadedFileMetadata (nếu Sprint 1 dùng avatar `fileId`)
2. AuthService (đã done) + AddAccountProfileExtensionTables
3. BatteryService InitialBatterySchema (+ TimescaleDB extension)
4. TicketService InitialTicketSchema
5. NotificationService InitialNotificationSchema

### 12.3. Migration checklist (theo `be.md §14`)
- [ ] Tên migration mô tả rõ
- [ ] Có `Down()` method
- [ ] NOT NULL columns: có `defaultValue` hoặc seed trước
- [ ] Test rollback: `database update <prev> && database update`
- [ ] Không có DROP TABLE/TRUNCATE raw

### 12.4. Production migration deploy strategy
- Run migrations as init container trong k8s (separate from app pod).
- App pod chỉ start sau khi migration thành công.
- Rollback plan: keep N-1 migration scripts handy.

---

## 13. Performance & caching strategy

### 13.1. Cache TTL chuẩn

| Data | TTL | Invalidation |
|------|-----|--------------|
| BatteryAsset detail | 60s | On update event |
| BatteryAsset list (per customer) | 30s | On asset CUD |
| Battery realtime | 0 (no cache) | — |
| Sensor history granularity≥1h | 60s | — |
| Active alerts per asset | 30s | On alert CUD |
| Ticket detail | 30s | On status change |
| Manager queue | 15s | — |
| KB article | 5min | On publish/update |
| Threshold config | 10min | On update |
| User profile | 5min | On update |
| Notification preference | 5min | On update |
| Permission claims | 10min | On role change |

### 13.2. Database
- Connection pool: `Maximum Pool Size=100` per service (default 100, sufficient).
- Pgbouncer optional cho production scale.
- Index strategy: theo §1.3, §2.3 (mỗi entity rõ index).

### 13.3. Pagination defaults
- `PageSize` default 20, max 100.
- `OrderBy` default `CreatedAt DESC`.
- Pagination response wrapper:
  ```csharp
  public class PaginationResponse<T> {
      public int Page { get; set; }
      public int PageSize { get; set; }
      public int TotalCount { get; set; }
      public int TotalPages { get; set; }
      public IEnumerable<T> Items { get; set; } = [];
  }
  ```

### 13.4. Performance SLA per endpoint

| Endpoint | P50 | P95 | P99 |
|----------|-----|-----|-----|
| GET realtime | 50ms | 150ms | 300ms |
| POST ticket | 100ms | 300ms | 500ms |
| GET ticket detail (with includes) | 80ms | 200ms | 400ms |
| Manager queue list | 100ms | 300ms | 500ms |
| Sensor batch ingest (100 readings) | 200ms | 500ms | 1000ms |

---

## 14. Security checklist

### 14.1. AuthN/AuthZ
- [x] JWT signed HS256 (config secret ≥ 32 bytes)
- [x] RefreshToken rotation trên mỗi refresh
- [x] Permission-based authorization (đã có `HasPermissionAttribute`)
- [ ] Gateway validate JWT (xem §10.1)
- [ ] Permission claim cache 10min (xem §13.1)

### 14.2. Input validation
- [x] `IValidatable<T>` pipeline cho mọi command
- [ ] HTML sanitize cho TicketComment.Body (dùng `HtmlSanitizer` package)
- [ ] File upload size limit 10MB, content-type whitelist (image/png, image/jpeg, application/pdf)

### 14.3. Secrets
- [x] `.env` không commit
- [x] Pre-commit hook secret-scan
- [ ] Production: dùng Azure Key Vault / AWS Secrets Manager (out of scope capstone, dùng env)

### 14.4. CORS
- Whitelist origins (xem §10.3), no `*` for prod.

### 14.5. Rate limiting
- Xem §10.2.

### 14.6. Audit
- AuditLog đã có trong AuthService cho login/role change.
- TicketActivity đã có cho ticket changes.
- Battery asset CUD → cũng cần audit (CreatedBy/UpdatedBy đã có qua AuditableEntity).

### 14.7. OWASP top 10 quick check
- **A01 Broken access:** permission attribute mọi endpoint + ownership check
- **A02 Crypto:** Argon2id password hash (đã có)
- **A03 Injection:** EF Core parameterized, không string-concat SQL
- **A04 Insecure design:** state machine validate transition, không tin client
- **A05 Misconfig:** SecurityHeadersMiddleware đã có (X-Frame-Options, CSP)
- **A07 AuthN failures:** rate limit login, login attempt tracking đã có
- **A08 Software integrity:** dependabot đã có (PR #45 ví dụ)
- **A09 Logging:** Serilog + CorrelationId

---

## 15. Email/Notification template catalog

### 15.1. Email templates

| Template | When | Recipient | Subject |
|----------|------|-----------|---------|
| `welcome-customer.hbs` | AccountActivatedEvent | Customer | "Chào mừng đến với Solar Battery Monitor" |
| `admin-invite.hbs` | SendAdminInviteEvent (đã có) | Staff/Manager invited | "Lời mời tham gia hệ thống" |
| `password-reset.hbs` | SendPasswordResetOtpEvent | Mọi role | "Đặt lại mật khẩu" |
| `battery-alert-critical.hbs` | BatteryAnomalyDetectedEvent (Critical) | Customer | "🔴 Cảnh báo nghiêm trọng: {AnomalyType}" |
| `ticket-created.hbs` | TicketCreatedEvent | Manager | "[TKT-{Code}] Ticket mới: {Title}" |
| `ticket-assigned-staff.hbs` | TicketAssignedEvent | Staff | "[TKT-{Code}] Bạn được giao ticket" |
| `ticket-assigned-customer.hbs` | TicketAssignedEvent | Customer | "[TKT-{Code}] Ticket của bạn đang được xử lý" |
| `ticket-resolved.hbs` | TicketResolvedEvent | Manager | "[TKT-{Code}] Staff đã đánh dấu RESOLVED" |
| `ticket-approved.hbs` | TicketApprovedEvent | Customer | "[TKT-{Code}] Ticket đã được giải quyết" |
| `sla-warning.hbs` | SlaWarningEvent | Staff + Manager | "[TKT-{Code}] SLA 80% — còn {Hours}h" |
| `sla-breach.hbs` | SlaBreachedEvent | Manager (+ Admin nếu P1) | "[TKT-{Code}] SLA BREACH" |
| `incident-declared.hbs` | IncidentDeclaredEvent | Admin/Manager/LeadStaff | "🚨 INCIDENT: {Title}" |

### 15.2. Push notification templates (Expo)

| Type | Title | Body | Data |
|------|-------|------|------|
| BatteryAlertCritical | 🔴 Pin {Serial} cảnh báo nghiêm trọng | {AnomalyType} — {Actual}{Unit} (ngưỡng {Threshold}) | `{ "screen": "AlertDetail", "alertId": "..." }` |
| TicketAssigned (Staff) | Ticket mới: {Code} | {Title} — Priority {Priority} | `{ "screen": "TicketDetail", "ticketId": "..." }` |
| SlaWarning | ⚠️ SLA {Code} còn {Hours}h | {Title} | — |

### 15.3. Localization
- Bộ template Tiếng Việt làm chính cho capstone.
- Future: thêm English bằng cách parallel folder `Templates/en/`.

---

# Phần V — Lập kế hoạch

## 16. Scaffold workflow cho từng service

### 16.1. BatteryService (sprint 2)
```bash
# Tay: tạo solution structure (4 csproj + .slnx) — tham khảo AuthService

# Domain + scaffold đầu
/scaffold-crud BatteryService BatteryType
/scaffold-crud BatteryService ThresholdConfig
/scaffold-crud BatteryService BatteryAsset
/scaffold-entity BatteryService SensorReading        # custom hypertable migration
/scaffold-crud BatteryService Alert

# Events
/scaffold-integration-event BatteryAssetCreatedEvent
/scaffold-integration-event BatteryAnomalyDetectedEvent
/scaffold-integration-event BatteryAssetTransferredEvent

# Consumers
/scaffold-consumer BatteryService AccountActivatedEvent
/scaffold-consumer BatteryService AccountDeletedEvent
/scaffold-consumer BatteryService AccountStatusChangedEvent

# Custom CQRS (không có scaffold sẵn)
/scaffold-cqrs-command BatteryService Alert Acknowledge
/scaffold-cqrs-command BatteryService Alert Resolve
/scaffold-cqrs-command BatteryService SensorReading BatchIngest
/scaffold-cqrs-command BatteryService BatteryAsset TransferOwner

/scaffold-cqrs-query BatteryService BatteryAsset Realtime
/scaffold-cqrs-query BatteryService BatteryAsset MyBatteries
/scaffold-cqrs-query BatteryService SensorReading GetHistory
/scaffold-cqrs-query BatteryService Dashboard Stats

# Tests
/scaffold-unit-tests BatteryService BatteryAsset
/scaffold-unit-tests BatteryService Alert
/scaffold-unit-tests BatteryService SensorReading

# Migration
/run-migration BatteryService InitialBatterySchema

# Background services: làm tay
# - ThresholdCheckBackgroundService
# - AlertEscalationBackgroundService
# - AlertAutoResolveBackgroundService
# - OutboxRelayBackgroundService
```

### 16.2. TicketService (sprint 3-4)
```bash
/scaffold-crud TicketService Ticket
/scaffold-crud TicketService TicketComment
/scaffold-crud TicketService MaintenanceLog
/scaffold-crud TicketService KnowledgeBaseArticle
/scaffold-entity TicketService TicketActivity
/scaffold-entity TicketService SlaTimer
/scaffold-entity TicketService SlaPauseEvent
/scaffold-entity TicketService TicketAttachment

# 12+ commands cho state machine
/scaffold-cqrs-command TicketService Ticket Assign
/scaffold-cqrs-command TicketService Ticket Reassign
/scaffold-cqrs-command TicketService Ticket Start
/scaffold-cqrs-command TicketService Ticket Hold
/scaffold-cqrs-command TicketService Ticket Resume
/scaffold-cqrs-command TicketService Ticket Resolve
/scaffold-cqrs-command TicketService Ticket Approve
/scaffold-cqrs-command TicketService Ticket Reject
/scaffold-cqrs-command TicketService Ticket RequestEscalation
/scaffold-cqrs-command TicketService Ticket Escalate
/scaffold-cqrs-command TicketService Ticket DeclareIncident
/scaffold-cqrs-command TicketService Ticket Rate
/scaffold-cqrs-command TicketService Ticket Reopen

# Queries
/scaffold-cqrs-query TicketService Ticket GetList
/scaffold-cqrs-query TicketService Ticket GetById
/scaffold-cqrs-query TicketService Ticket MyAsCustomer
/scaffold-cqrs-query TicketService Ticket MyAsStaff
/scaffold-cqrs-query TicketService Ticket ManagerQueue
/scaffold-cqrs-query TicketService Ticket ActivityTimeline
/scaffold-cqrs-query TicketService Sla GetStatus
/scaffold-cqrs-query TicketService Staff Workload

# Consumer auto-create
/scaffold-consumer TicketService BatteryAnomalyDetectedEvent
/scaffold-consumer TicketService AccountStatusChangedEvent

# Events publish
/scaffold-integration-event TicketCreatedEvent
/scaffold-integration-event TicketAssignedEvent
/scaffold-integration-event TicketStatusChangedEvent
/scaffold-integration-event TicketResolvedEvent
/scaffold-integration-event TicketApprovedEvent
/scaffold-integration-event TicketClosedEvent
/scaffold-integration-event TicketEscalatedEvent
/scaffold-integration-event IncidentDeclaredEvent
/scaffold-integration-event SlaWarningEvent
/scaffold-integration-event SlaBreachedEvent

# Tests
/scaffold-unit-tests TicketService Ticket
/scaffold-unit-tests TicketService SlaTimer
/scaffold-unit-tests TicketService TicketActivity
# Manual: TicketStateMachineTests (matrix test)

# Migrations
/run-migration TicketService InitialTicketSchema

# Background services: làm tay
# - SlaTimerBackgroundService
# - AutoCloseBackgroundService
# - EscalationBackgroundService
# - OutboxRelayBackgroundService
```

### 16.3. NotificationService (sprint 5)
```bash
/scaffold-crud NotificationService Notification
/scaffold-crud NotificationService DeviceToken
/scaffold-crud NotificationService NotificationPreference
/scaffold-crud NotificationService NotificationTemplate

# Consumers cho tất cả events
/scaffold-consumer NotificationService TicketCreatedEvent
/scaffold-consumer NotificationService TicketAssignedEvent
/scaffold-consumer NotificationService TicketStatusChangedEvent
/scaffold-consumer NotificationService TicketResolvedEvent
/scaffold-consumer NotificationService TicketApprovedEvent
/scaffold-consumer NotificationService TicketClosedEvent
/scaffold-consumer NotificationService TicketEscalatedEvent
/scaffold-consumer NotificationService IncidentDeclaredEvent
/scaffold-consumer NotificationService SlaWarningEvent
/scaffold-consumer NotificationService SlaBreachedEvent
/scaffold-consumer NotificationService BatteryAnomalyDetectedEvent
/scaffold-consumer NotificationService AccountActivatedEvent
/scaffold-consumer NotificationService SendAdminInviteEvent

# Tests
/scaffold-unit-tests NotificationService Notification

# Migration
/run-migration NotificationService InitialNotificationSchema
```

---

## 17. Sprint backlog — 8 sprint chi tiết + Sprint 5B tách riêng

### Sprint 1 (Hiện tại: 11/5–24/5/2026)
**Goal:** Stabilize foundations + close AuditLog/Permission.
**Tasks:**
- [x] AuthService AuditLog + Permission + LoginAttempt (DONE — merged #46)
- [x] Apply Polly retry/timeout cross-service (PR #47 chờ merge)
- [x] **Decision:** đổi postgres image sang `timescale/timescaledb:latest-pg16` — compose config validated
- [x] Docker Compose tách logical database theo service:
  - [x] `AuthService` dùng `auth_db` qua `ConnectionStrings__AuthDb`.
  - [x] `FileStorageService` dùng `file_storage_db` qua `ConnectionStrings__FileStorageDb`.
  - [x] `postgres-init` tạo DB idempotent, chạy được cả khi volume Postgres đã tồn tại.
- [x] FileStorageService metadata foundation (§6bis):
  - [x] Thêm `FileStorageService.Domain` nếu service hiện tại chưa có Domain project.
  - [x] Thêm entity `UploadedFile : AuditableEntity`.
  - [x] Thêm enum `FilePurposeEnum`, `FileStatusEnum`.
  - [x] Thêm `ApplicationDbContext` + EF configuration cho `uploaded_files`.
  - [x] Tạo migration `AddUploadedFileMetadata`.
  - [x] Update upload flow: upload object thành công → tạo `UploadedFile` metadata → response trả `fileId`.
  - [x] Update endpoint metadata/presigned/download/delete để dùng `fileId`.
- [x] **Decision:** giữ `Account` sạch, thêm extension tables `AccountProfile`, `StaffProfile`, `StaffSkill` trong AuthService → migration `AddAccountProfileExtensionTables`
- [x] AuthService: hỗ trợ avatar 2 nguồn (`AvatarFileId` nội bộ, `ExternalAvatarUrl` từ Google) và trả `displayAvatarUrl` cho FE
- [ ] Update CLAUDE.md memory + tài liệu API contract initial cho FE team (controller XML docs đã cập nhật, file doc riêng còn pending) — #64
- [ ] Migration rollback test cho `AddUploadedFileMetadata` và `AddAccountProfileExtensionTables` — #64

### Sprint 2 (25/5–7/6/2026)
**Goal:** BatteryService MVP (no anomaly detection yet).
**Tasks:**
- [x] Tạo solution skeleton `services/BatteryService/`
- [x] Migration: `InitialBatterySchema` (BatteryType, ThresholdConfig, BatteryAsset, Alert)
- [x] Migration: SensorReading table + TimescaleDB hypertable SQL
- [x] Migration: `CustomerAccount` read-model cache cho Auth account sync
- [x] CQRS BatteryType CRUD (4 commands + 2 queries)
- [x] CQRS BatteryAsset CRUD + TransferOwner (5 commands + 4 queries)
- [x] CQRS ThresholdConfig Upsert + Get
- [x] Consumer `AccountActivatedConsumer` + `AccountDeletedConsumer` + `AccountStatusChangedConsumer`
- [x] Validate `CustomerId` qua local `CustomerAccount` read-model khi tạo Site/BatteryAsset và TransferOwner
- [x] Unit tests + focused integration tests cho BatteryService critical paths
- [x] Coverage ≥ 80% report/enforcement (đạt 95.8% line coverage trên Application + Infrastructure, exclude Migrations/Factory/Seeders/DTO/Mapping; `services/BatteryService/scripts/check-coverage.sh` enforce threshold)
- [x] Migration rollback test trên TimescaleDB (script `services/BatteryService/scripts/test-migration-rollback.sh` — apply/rollback/re-apply cycle PASS, hypertable metadata auto-cleaned)
- [x] Update docker-compose + ApiGateway route
- [x] Seed BatteryType + 3 sample asset + sample customer/site/group
- [x] Site entities/CRUD + asset link/filter/dashboard MVP

### Sprint 3 (8/6–21/6/2026)
**Goal:** BatteryService anomaly engine + alert pipeline + Tier 1 extended battery health (SOH).
**Tasks:**
- [x] `SensorReadingBatchIngestCommand` + endpoint với ApiKey auth (done early in Sprint 2)
- [x] **Migration** `ExtendSensorReadingTierOne`: thêm `SohPercent`, `ChargingState` vào `sensor_readings` (nullable, không backfill) — #75
- [x] **Migration** `ExtendThresholdConfigSoh`: thêm `SohWarningThreshold`, `SohCriticalThreshold` vào `threshold_configs` — #75
- [x] Update `SensorReadingItem` + validation (SOH 0-100, ChargingState enum) — #80
- [x] Update `UpsertThresholdConfigCommand` validation (SOH critical < warning) — #80
- [x] `ThresholdAnomalyDetector` service + unit tests (**8 anomaly types**: 7 cũ + `SohDegradation`) — #76
- [x] `AlertDeduplicationService` + unit tests (BR-03) — #76
- [x] `ThresholdCheckBackgroundService` (30s tick) — #77
- [x] `AlertEscalationBackgroundService` (publish event) — #77
- [x] `OutboxRelayBackgroundService` + Outbox entity — #78
- [x] Publish `BatteryAnomalyDetectedEvent` — #78
- [x] Realtime + History query endpoint — #79
- [x] Extend `BatteryAssetRealtimeDto` thêm `SohPercent` + `ChargingState` — #79
- [x] Seed sensor data với pre-built anomaly scenarios (gồm SOH degradation scenario) — #81
- [x] Integration test end-to-end: ingest → detect → publish event (TestHarness) — #82

### Sprint 4 (22/6–5/7/2026)
**Goal:** TicketService foundation only — service skeleton, schema, state machine, basic lifecycle commands/queries. Không phát triển song song BatteryService advanced monitoring trong sprint này.
**Tasks:**
- [ ] Tạo solution skeleton `services/TicketService/` — #83
- [ ] Entities + migration `InitialTicketSchema` (Ticket, SlaTimer, SlaPauseEvent, TicketActivity, TicketComment, MaintenanceLog, TicketAttachment, OutboxMessage) — #83
- [ ] `TicketStateMachine` class + 30+ transition unit tests — #84
- [ ] Commands: Create, Assign, Start, Hold, Resume, Resolve, Approve, Reject (8 commands) — #85
- [ ] Queries: GetById, GetList, MyAsCustomer, MyAsStaff, ManagerQueue, ActivityTimeline (6) — #86
- [ ] Code generation utility (TKT-YYMM-NNNN) — #87
- [ ] Outbox + relay service — #88
- [ ] Coverage ≥ 80% — #88

### Sprint 5 (6/7–19/7/2026)
**Goal:** TicketService workflow integration — SLA, pause/resume, auto-create from Battery anomaly, maintenance log/comment/attachment.
**Tasks:**
- [ ] `SlaCalculator` service + unit tests — #94
- [ ] `SlaTimerBackgroundService` (60s tick — warning + breach) — #94
- [ ] Pause/Resume commands (3 commands cho 3 Waiting* states) — #95
- [ ] `EscalationBackgroundService` event-driven — #96
- [ ] Reopen + Rate commands (Customer flow) — #97
- [ ] `AutoCloseBackgroundService` (7d auto-close) — #98
- [ ] Incident commands — #98
- [ ] All events publish (SlaWarning, SlaBreached, Escalated, Incident, etc.) — #99
- [ ] Coverage ≥ 80% + integration test SLA breach end-to-end with time mocking — #99
- [ ] Consumer `BatteryAnomalyDetectedConsumer` → auto-create ticket + dedup BR-02 — #142
- [ ] MaintenanceLog + comments + attachments workflow trong TicketService — #143

### Sprint 5B (20/7–26/7/2026)
**Goal:** BatteryService advanced monitoring riêng — ambient/environmental/tier-2 sensor health. Sprint này tách khỏi TicketService để tránh phát triển song song hai domain lớn.
**Tasks:**
- [ ] Entity `AmbientReading` (hypertable) + `AmbientThresholdConfig` (per Site, regular table) — #89
- [ ] Migration `AddAmbientMonitoring`: tạo bảng + hypertable + index — #89
- [ ] `IOpenMeteoClient` interface + `OpenMeteoClient` HTTP impl (Polly retry, 10s timeout) — #90
- [ ] `WeatherSyncBackgroundService` (15min interval, dedup 10min, per-site lat/lon) — #90
- [ ] `BatchIngestAmbientReadingsCommand` + endpoint (ApiKey `EnvironmentalIngest`) — #91
- [ ] `GetAmbientReadingHistoryQuery` + `GetLatestAmbientReadingQuery` + endpoints — #91
- [ ] `UpsertAmbientThresholdConfigCommand` + 2 query (by-site, list) + endpoints — #92
- [ ] Extend `ThresholdAnomalyDetector` thêm 3 type: `HighAmbientTemp`, `HighHumidity`, `HighTempHumidityCombo` — #93
- [ ] Update `appsettings.json`: tách `ApiKeys:SensorIngest` và `ApiKeys:EnvironmentalIngest`, thêm `Weather:*` config — #92
- [ ] Unit tests OpenMeteoClient (HttpMessageHandler stub) + WeatherSyncBackgroundService (mock client) + 3 anomaly types mới — #93
- [ ] Integration test: ingest ambient → query latest, combo threshold → alert — #93
- [ ] Entity `EnvironmentalIncident` (regular table với lifecycle) — #100
- [ ] Migration `AddEnvironmentalIncidentAndAlertSiteLevel`: tạo bảng `environmental_incidents` + relax `alerts.battery_asset_id` thành nullable + thêm `alerts.site_id` + `alerts.environmental_incident_id` + check constraint + index — #100
- [ ] Migration `ExtendSensorReadingTierTwo`: thêm `InternalResistanceMilliohm`, `CellVoltageDeltaMv` vào `sensor_readings` — #101
- [ ] Migration `ExtendThresholdConfigTierTwo`: thêm `InternalResistanceMaxMilliohm`, `CellVoltageDeltaMaxMv` vào `threshold_configs` — #101
- [ ] `ReportEnvironmentalIncidentCommand` (ApiKey `EnvironmentalIngest`) — tạo incident + alert + publish event — #102
- [ ] `AcknowledgeEnvironmentalIncidentCommand` + `ResolveEnvironmentalIncidentCommand` + `MarkFalseAlarmEnvironmentalIncidentCommand` — #102
- [ ] `GetEnvironmentalIncidentsQuery` (list + filter) + `GetEnvironmentalIncidentByIdQuery` + `ActiveEnvironmentalIncidentsBySiteQuery` — #103
- [ ] Endpoints `/api/environmental-incidents` (6 endpoint) — #103
- [ ] Integration event `EnvironmentalIncidentDetectedEvent` + `EnvironmentalIncidentResolvedEvent` — #104
- [ ] Extend Alert table — handler tạo alert cho cả site-level (chỉnh `AlertCreateCommandHandler` + dedup logic) — #104
- [ ] Extend `ThresholdAnomalyDetector` thêm 3 type: `HighInternalResistance`, `CellImbalance`, `EnvironmentalIncident` — #105
- [ ] Update `SensorReadingItem` + validation (IR > 0, CellDelta ≥ 0) — #105
- [ ] Unit tests cho mọi command/handler + Tier 2 anomaly types — #105
- [ ] Integration test: report smoke incident → alert critical tạo → event publish → false-alarm flow đóng cả 2 — #105
- [ ] Coverage ≥ 80% maintain — #105

### Sprint 6 (27/7–9/8/2026)
**Goal:** NotificationService + KnowledgeBase + Environmental notification routing.
**Tasks:**
- [ ] Tạo solution `services/NotificationService/` — #106
- [ ] **15 consumers** cho mọi events (13 cũ + `EnvironmentalIncidentDetectedConsumer` + `EnvironmentalIncidentResolvedConsumer`) — #107
- [ ] `ExpoPushChannel` + integration test (sandbox token) — #108
- [ ] `EmailBusChannel`, `SmsBusChannel`, `InAppChannel` — #108
- [ ] `NotificationDispatcher` + preference + quiet hours — #109
- [ ] DeviceToken endpoints — #110
- [ ] KnowledgeBase module trong TicketService (CRUD + suggest endpoint) — #112
- [ ] Email templates **14 file `.hbs`** (12 cũ + `environmental-incident-detected.hbs` + `environmental-incident-resolved.hbs`) — #111
- [ ] Push template: `EnvironmentalIncidentCritical` (smoke/water → page Manager + Admin) — #111
- [ ] Routing rule: incident Critical → Critical channel (push + email + SMS), bypass quiet hours — #109
- [ ] Seed 5 KB articles — #112
- [ ] Coverage ≥ 80% — #112

### Sprint 7 (10/8–23/8/2026)
**Goal:** Reports + Gateway hardening + Observability + Tier 3 sensor finalize.
**Tasks:**
- [ ] **Migration** `ExtendSensorReadingTierThree`: thêm `BmsErrorCode` vào `sensor_readings` (nullable, 64 chars) — #113
- [ ] Update `SensorReadingItem` + validation (`BmsErrorCode` ≤ 64 chars) — #113
- [ ] Reports endpoints (Ticket: 8 endpoints, **Battery: 7 endpoints** — 5 cũ + Environmental Incident report + Ambient temperature trend) — #114
- [ ] CSV/XLSX export — #114
- [ ] ApiGateway: JWT validate + claim forwarding + rate limiting + aggregated swagger — #115
- [ ] OpenTelemetry tracing setup → Tempo (include WeatherSync + EnvironmentalIncident flow) — #116
- [ ] Grafana dashboards: SLA Ops, **Battery Health (gồm SOH/DCIR/Imbalance)**, **Environmental Monitoring (ambient + incidents)**, System Health — #117
- [ ] AlertManager rules — bao gồm rule cho environmental incident detection latency — #118
- [ ] Full seed data script (`tools/seed.sh`) — bao gồm ambient readings + 1 incident historical example — #119
- [ ] End-to-end test scenarios (golden path + SLA breach + reopen + smoke incident lifecycle) — #119
- [ ] **[Optional P1]** Deploy staging K8s với Helm umbrella chart + smoke test all services — #126 _(nếu bỏ qua sprint này thì fallback docker compose cho demo, không ảnh hưởng điểm chức năng)_

### Sprint 8 (24/8–13/9/2026)
**Goal:** Demo prep + polish.
**Tasks:**
- [ ] Performance testing + tuning per §13.4 SLAs — #120
- [ ] Security audit (OWASP checklist §14.7) — #121
- [ ] Documentation: API contracts final, README per service, postman collection — #122
- [ ] Final seed data với scenarios realistic — #123
- [ ] Demo script: walkthrough end-to-end flow trên Mobile + Web — #123
- [ ] Bug bash + bug fix — #124
- [ ] Final coverage push — #125

---

## 18. Definition of Done

### 18.1. Per ticket (theo `workflow.md`)
- [ ] `/kltn-task KAN-XX` đã viết `logs/KAN-XX/plan.md`
- [ ] User approve plan
- [ ] Code implement
- [ ] `/kltn-reviewcode` → PASS, log `logs/KAN-XX/review.md`
- [ ] `/kltn-test` → PASS với coverage report, log `logs/KAN-XX/test.md`
- [ ] `/kltn-ship KAN-XX` — push branch + commit logs folder + tạo PR
- [ ] Reviewer chạy `/kltn-reviewpr KAN-XX` → APPROVE
- [ ] Author chạy `/kltn-complete` → merge

### 18.2. Per service (production-ready demo)
- [ ] All CQRS handlers có unit test
- [ ] All endpoints có integration test
- [ ] Coverage ≥ 80% line
- [ ] Migration tested rollback
- [ ] Outbox relay running
- [ ] Health endpoints work (`/health/live`, `/health/ready`)
- [ ] Swagger documented
- [ ] Docker container build < 200MB
- [ ] Startup < 10s in container
- [ ] README per service với run local + run test instructions

### 18.3. Per system (end-to-end demo)
1. `docker compose --env-file .env.Docker up -d --build` chạy tất cả service xanh trong < 60s.
2. `tools/seed.sh` populate đầy đủ data.
3. End-to-end scenario chạy được:
   - Customer login Mobile → xem battery realtime → nhận push critical alert
   - System auto-create ticket → Manager assign Staff trên Web
   - SLA timer chạy → Staff resolve trên Web → Manager approve
   - Customer rate trên Mobile → ticket CLOSED
4. SLA breach scenario demo được (chỉnh sensor data hoặc time mock):
   - Ticket P1 SLA tới 80% → push warning
   - Ticket P1 SLA breach → auto ESCALATED → notify Admin
5. Reports endpoint trả số liệu khớp với data thực tế.
6. Grafana dashboards realtime updating.
7. Swagger UI ApiGateway có đủ schema mọi service.
8. Coverage report ≥ 80% per service tại CI.

---

# Phần VI — Phụ lục

## 20. Permission matrix đầy đủ

### Convention
Permission code: `{service}.{resource}.{action}`. Đã có `PermissionCodes` trong AuthService. Thêm mới:

```csharp
public static class PermissionCodes {
    // Battery
    public const string BatteryAssetView = "battery.asset.view";
    public const string BatteryAssetViewOwn = "battery.asset.view-own";
    public const string BatteryAssetManage = "battery.asset.manage";
    public const string BatteryAssetTransfer = "battery.asset.transfer";
    public const string BatteryTypeManage = "battery.type.manage";
    public const string BatteryThresholdManage = "battery.threshold.manage";
    public const string BatterySensorIngest = "battery.sensor.ingest";
    public const string BatterySensorView = "battery.sensor.view";
    public const string BatterySensorViewOwn = "battery.sensor.view-own";
    public const string AlertView = "battery.alert.view";
    public const string AlertViewOwn = "battery.alert.view-own";
    public const string AlertAcknowledge = "battery.alert.acknowledge";
    public const string AlertResolve = "battery.alert.resolve";
    public const string BatteryDashboardView = "battery.dashboard.view";

    // Ticket
    public const string TicketCreate = "ticket.create";
    public const string TicketViewOwn = "ticket.view-own";
    public const string TicketViewAll = "ticket.view-all";
    public const string TicketAssign = "ticket.assign";
    public const string TicketStart = "ticket.start";
    public const string TicketHold = "ticket.hold";
    public const string TicketResolve = "ticket.resolve";
    public const string TicketApprove = "ticket.approve";
    public const string TicketEscalate = "ticket.escalate";
    public const string TicketIncidentDeclare = "ticket.incident.declare";
    public const string TicketRate = "ticket.rate";
    public const string TicketReopen = "ticket.reopen";
    public const string TicketCommentAdd = "ticket.comment.add";
    public const string TicketCommentInternalView = "ticket.comment.internal.view";
    public const string MaintenanceLogManage = "maintenance-log.manage";
    public const string KbView = "kb.view";
    public const string KbManage = "kb.manage";
    public const string TicketReportsView = "ticket.reports.view";

    // Notification
    public const string NotificationViewOwn = "notification.view-own";
    public const string DeviceTokenManage = "notification.device.manage";
    public const string PreferenceManage = "notification.preference.manage";
}
```

### Default role → permission mapping (seed)

| Permission | Admin | Manager | Staff | Customer |
|-----------|:-----:|:-------:|:-----:|:--------:|
| BatteryAssetView | ✅ | ✅ | ✅ | — |
| BatteryAssetViewOwn | — | — | — | ✅ |
| BatteryAssetManage | ✅ | — | — | — |
| BatteryAssetTransfer | ✅ | — | — | — |
| BatteryTypeManage | ✅ | — | — | — |
| BatteryThresholdManage | ✅ | — | — | — |
| BatterySensorIngest | ✅ | — | — | — (use ApiKey) |
| BatterySensorView | ✅ | ✅ | ✅ | — |
| BatterySensorViewOwn | — | — | — | ✅ |
| AlertView | ✅ | ✅ | ✅ | — |
| AlertViewOwn | — | — | — | ✅ |
| AlertAcknowledge | ✅ | ✅ | ✅ | ✅ |
| AlertResolve | ✅ | ✅ | ✅ | — |
| BatteryDashboardView | ✅ | ✅ | — | — |
| TicketCreate | ✅ | ✅ | ✅ | ✅ |
| TicketViewOwn | — | — | ✅ (assigned) | ✅ (owned) |
| TicketViewAll | ✅ | ✅ | — | — |
| TicketAssign | — | ✅ | — | — |
| TicketStart | — | — | ✅ | — |
| TicketHold | — | — | ✅ | — |
| TicketResolve | — | — | ✅ | — |
| TicketApprove | — | ✅ | — | — |
| TicketEscalate | ✅ | ✅ | ✅ (request) | — |
| TicketIncidentDeclare | ✅ | ✅ | — | — |
| TicketRate | — | — | — | ✅ |
| TicketReopen | — | — | — | ✅ |
| TicketCommentAdd | ✅ | ✅ | ✅ | ✅ |
| TicketCommentInternalView | ✅ | ✅ | ✅ | — |
| MaintenanceLogManage | — | — | ✅ | — |
| KbView | ✅ | ✅ | ✅ | — |
| KbManage | ✅ | ✅ | — | — |
| TicketReportsView | ✅ | ✅ | — | — |
| NotificationViewOwn | ✅ | ✅ | ✅ | ✅ |
| DeviceTokenManage | ✅ | ✅ | ✅ | ✅ |
| PreferenceManage | ✅ | ✅ | ✅ | ✅ |

### Ownership check (cross-cutting)
- `ViewOwn` permission → handler bắt buộc check `entity.CustomerId == currentUserId`.
- `Staff` xem ticket: bắt buộc check `ticket.AssignedStaffId == currentUserId` (trừ khi Admin/Manager).

---

## 21. Error code catalog

Chuẩn hóa cho FE handle dễ hơn. Trả về trong `CommonResponse.Message` hoặc field code riêng nếu cần.

### Format
`{SERVICE}_{CATEGORY}_{N}` — ví dụ `TICKET_STATE_001`.

| Code | Meaning | HTTP | Note |
|------|---------|------|------|
| `AUTH_LOGIN_001` | Sai email/password | 200 (isSuccess=false) | — |
| `AUTH_LOGIN_002` | Account bị khóa do nhiều lần sai | 200 | — |
| `AUTH_TOKEN_001` | Token expired | 401 | — |
| `AUTH_TOKEN_002` | Refresh token revoked | 401 | — |
| `AUTH_PERM_001` | Forbidden — thiếu permission | 403 | — |
| `BATTERY_ASSET_001` | Serial number trùng | 200 | — |
| `BATTERY_ASSET_002` | Customer not found | 200 | — |
| `BATTERY_ASSET_003` | BatteryType not found | 200 | — |
| `BATTERY_SENSOR_001` | Asset không tồn tại | 200 | — |
| `BATTERY_ALERT_001` | Alert đã được resolved | 200 | — |
| `TICKET_VAL_001` | BatteryAssetId required | 200 | — |
| `TICKET_VAL_002` | Customer không sở hữu asset | 200 | — |
| `TICKET_STATE_001` | Invalid transition | 200 | "Cannot transition from {From} to {To} by {Actor}" |
| `TICKET_STATE_002` | Ticket đã closed | 200 | — |
| `TICKET_ASSIGN_001` | Staff inactive | 200 | — |
| `TICKET_ASSIGN_002` | Staff vượt quá MaxConcurrentTickets | 200 | — |
| `TICKET_REOPEN_001` | Quá 7 ngày kể từ resolved | 200 | BR-06 |
| `TICKET_REOPEN_002` | Reopen lần thứ 2 → auto escalate | 200 (warning) | BR-07 |
| `TICKET_SLA_001` | SLA timer not running, không thể pause | 200 | — |
| `TICKET_RATE_001` | Đã rate rồi | 200 | — |
| `NOTIF_DEVICE_001` | Token Expo không hợp lệ | 200 | — |
| `FILE_UPLOAD_001` | File quá lớn (>10MB) | 400 | — |
| `FILE_UPLOAD_002` | Content-type không hỗ trợ | 400 | — |
| `GEN_RATE_001` | Rate limit exceeded | 429 | — |
| `GEN_VAL_001` | Validation error (generic) | 200 | `listErrors` populated |
| `GEN_NOTFOUND_001` | Resource not found | 200 (isSuccess=false) | — |

---

## 22. JWT claim structure

```json
{
  "sub": "{accountId}",
  "nameid": "{accountId}",
  "UserId": "{accountId}",
  "FullName": "Nguyễn Văn A",
  "Email": "a@example.com",
  "Role": "3",                                    // 1=Admin, 2=Manager, 3=Staff, 4=Customer
  "Permissions": ["ticket.view-own", "ticket.start", "ticket.resolve", ...],
  "session_id": "{sessionId}",
  "iat": 1715500000,
  "exp": 1715503600,                              // 1 hour
  "iss": "GSU26SE55-AuthService",
  "aud": "GSU26SE55-Clients"
}
```

- AccessToken: 1h
- RefreshToken: 7d (Redis key `RT_{userId}`)
- Permissions cache 10min — nếu role/permission đổi → AuthService publish event `PermissionsChangedEvent` → các service invalidate cache.

---

## 23. Risk register

| # | Risk | Likelihood | Impact | Mitigation | Owner |
|---|------|-----------|--------|------------|-------|
| R-01 | State machine TicketService bug | High | High | Test matrix 30+ transitions, code review focus | BE Lead |
| R-02 | SLA pause/resume tính sai → KPI bị skew | Med | High | `SlaCalculator` unit test 8 case, audit trail SlaPauseEvent | Thắng |
| R-03 | Alert dedup window không đúng → spam ticket | Med | Med | Configurable window, default 30min, test với scenario burst | Thái |
| R-04 | TimescaleDB migration phá DB hiện tại | High | High | Test trên branch riêng, rollback migration verified | Thái |
| R-05 | Outbox lag → event không publish kịp demo | Med | Med | Monitor unprocessed count, 5s tick frequency, retry với backoff | Duy |
| R-06 | Reopen infinite loop | Low | Med | BR-06 enforce 7d, BR-07 escalate sau 2 lần | Duy |
| R-07 | Test coverage không đạt 80% | High | Med | Scaffold-unit-tests luôn chạy cùng scaffold-crud, weekly coverage report | Leader |
| R-08 | Docker compose chậm/fail trên demo machine | Med | High | Health check thorough, restart policy, image pre-pull | Leader |
| R-09 | Expo push token rate limit / sandbox quirks | Med | Low | Polly retry, fallback in-app, document Expo setup | Thắng |
| R-10 | OWASP vulnerability lúc demo | Low | High | Trivy scan đã có, manual review §14 | Leader |
| R-11 | Performance: realtime endpoint < 100ms khó | Med | Med | Caching strategy §13, index `(asset, time DESC)`, benchmark | Thái |
| R-12 | Microservice event chain race condition | Med | High | Outbox + Inbox idempotency, integration test với TestHarness | Duy |
| R-13 | Demo gặp bug khi live | High | High | Final sprint dành cho bug bash + rehearsal | Cả team |

---

## 24. Checklist theo 6 phase business flow

### Phase 1 — Setup & Configuration (ADMIN)
- [x] User CRUD — AuthService DONE
- [x] Account profile expansion (avatar, phone, skill) — §7
- [ ] BatteryType CRUD — BatteryService §1
- [ ] ThresholdConfig CRUD — §1
- [ ] BatteryAsset CRUD + TransferOwner — §1
- [x] SLA rules hardcoded P1/P2/P3 = 4/24/72h — không cần CRUD
- [x] Audit log endpoint — AuthService DONE

### Phase 2 — Monitoring & Detection (CUSTOMER + SYSTEM)
- [ ] SensorReading batch ingest — §1.8
- [ ] Realtime query — §1.8
- [ ] History query với granularity — §1.8
- [ ] ThresholdCheckBackgroundService — §1.6
- [ ] AlertCreate + dedup BR-03 — §1.6
- [ ] Push notify Customer khi critical — §3.4

### Phase 3 — Ticket Creation (CUSTOMER / SYSTEM)
- [ ] TicketCreateCommand (Customer mobile) BR-01 mandatory asset — §2.5
- [ ] BatteryAnomalyDetectedConsumer auto-create BR-02 — §2.7
- [ ] Activity Created BR-08 — §2.3.4

### Phase 4 — Triage & Assignment (MANAGER)
- [ ] Manager queue query — §2.5
- [ ] StaffWorkloadQuery + skill match — §2.5
- [ ] TicketAssignCommand (priority cố định) — §2.5
- [ ] Start SlaTimer on ASSIGNED — §2.4
- [ ] Notify Staff via NotificationService — §3.4

### Phase 5 — Resolution (STAFF)
- [ ] TicketStartCommand → IN_PROGRESS — §2.5
- [ ] TicketHoldCommand → WAITING_* BR-04 — §2.5
- [ ] TicketResumeCommand — §2.5
- [ ] CommentAddCommand — §2.5
- [ ] MaintenanceLogAddCommand — §2.5
- [ ] TicketResolveCommand — §2.5
- [ ] TicketEscalateRequestCommand — §2.5
- [ ] KB suggest endpoint — §4
- [ ] SlaTimerBackgroundService warning 80% — §2.6

### Phase 6 — Verification & Closure (MANAGER + CUSTOMER)
- [ ] TicketApproveCommand BR-05 — §2.5
- [ ] TicketRejectCommand → IN_PROGRESS — §2.5
- [ ] TicketRateCommand (Customer) — §2.5
- [ ] TicketReopenCommand 7d BR-06 — §2.5
- [ ] Escalate on reopen ≥ 2 BR-07 — §2.5
- [ ] AutoCloseBackgroundService 7d — §2.6
- [ ] CSAT report — §5.2

### Cross-cutting
- [x] FileStorageService `UploadedFile` metadata + `fileId` reference — §6bis
- [x] Docker Compose per-service logical database setup (`auth_db`, `file_storage_db`)
- [ ] Outbox cho BatteryService + TicketService — §8.1
- [ ] Inbox idempotency consumer — §8.2
- [ ] OpenTelemetry tracing — §8.4
- [ ] Gateway JWT validate + claim forward — §10.1
- [ ] OpenAPI aggregate at gateway — §10.4
- [ ] Grafana business dashboards — §9.2
- [ ] Coverage ≥ 80% per service — §11
- [ ] Seed data script — §12.1

---

## 25. Câu hỏi cần thống nhất trước khi bắt đầu

| # | Câu hỏi | Đề xuất |
|---|---------|---------|
| Q-01 | Đổi postgres image sang `timescaledb` ngay hay tách DB riêng cho BatteryService? | **Đổi image** — đơn giản, postgres 16 vẫn full feature |
| Q-02 | Outbox cho BatteryService/TicketService áp dụng từ đầu hay sau? | **Từ đầu** — AuthService đã có template |
| Q-03 | Expo Push thật hay mock cho demo? | **Thật** — capstone có Mobile demo |
| Q-04 | KnowledgeBase module hay service riêng? | **Module trong TicketService** — scope hợp lý |
| Q-05 | Account profile/staff fields: nhét vào `Account`, tách bảng extension, hay tách UserService? | **Tách bảng extension trong AuthService** — giữ `Account` sạch, chưa cần UserService riêng |
| Q-06 | API versioning `/api/v1/` từ đầu hay sau? | **Từ đầu** |
| Q-07 | Gateway JWT validate khi nào? | **Sau khi 2 service đầu (Battery, Ticket) có endpoint chạy** |
| Q-08 | TestContainers hay shared dev Postgres? | **TestContainers** |
| Q-09 | Có cần WebSocket cho realtime dashboard? | **Tạm dùng polling 30s** (TanStack Query refetchInterval), WebSocket Sprint 8+ nếu kịp |
| Q-10 | IoT data source thật hay simulator? | **Simulator script** cho capstone (real IoT out of scope) |
| Q-11 | Notification có cần "do not disturb" (quiet hours)? | **Có** — nằm trong NotificationPreference §3.3 |
| Q-12 | Customer có thể cancel ticket không? | **KHÔNG** — chỉ rate hoặc reopen, vì cần audit trail |
| Q-13 | Manager có thể đổi priority sau khi gán không? | **KHÔNG** — theo design.md priority policy |
| Q-14 | Có cần SMS OTP cho login Customer Mobile? | **Có** (đã có SmsService) — optional flag |
| Q-15 | File attachment limit size? | **10MB/file, 5 files/ticket** |
| Q-16 | Cache strategy: Redis hay InMemory? | **Redis** (đã có sẵn) |
| Q-17 | Có pre-staging environment? | **Không** — chỉ local + final demo |
| Q-18 | Các service lưu file bằng `objectKey` hay `fileId`? | **Lưu `fileId`** — FileStorageService phải có `UploadedFile` metadata table, `objectKey` chỉ là internal detail |

---

## 26. Glossary & references

### Glossary
| Term | Định nghĩa |
|------|-----------|
| **Ticket** | Yêu cầu hỗ trợ từ Customer hoặc tự động sinh từ alert critical |
| **Asset** | Một bộ pin cụ thể (BatteryAsset entity) gắn với Customer |
| **Alert** | Cảnh báo sinh ra khi sensor reading vượt ngưỡng |
| **Anomaly** | Bất thường được phát hiện (overheat, overvoltage, ...) |
| **SLA** | Service Level Agreement — deadline xử lý ticket theo priority |
| **Priority** | Mức độ ưu tiên ticket (P1/P2/P3), Manager gán 1 lần |
| **Escalation** | Đẩy ticket lên level cao hơn khi không xử lý được |
| **Incident** | Critical event ảnh hưởng nhiều ticket/asset hoặc rủi ro an toàn |
| **Activity** | Log mỗi hành động trên ticket (BR-08) |
| **Reopen** | Customer mở lại ticket trong 7 ngày sau khi resolved (BR-06) |
| **Maintenance log** | Ghi nhận công việc Staff đã làm khi xử lý |
| **CSAT** | Customer Satisfaction (rating 1-5) |
| **Outbox** | Pattern lưu event vào DB trước khi publish, đảm bảo atomic |
| **Inbox** | Pattern dedup message ở consumer để idempotent |

### References
- ITIL 4 Incident Management — basis của ticket lifecycle
- ITIL 4 Problem Management — basis của Incident flag
- OWASP Top 10 2021 — security checklist §14.7
- Clean Architecture — Robert C. Martin, layered structure
- Microsoft Microservices Patterns — Outbox, Saga
- MassTransit docs — consumer + retry/circuit breaker
- TimescaleDB docs — hypertable, continuous aggregate
- Expo Push docs — https://docs.expo.dev/push-notifications/sending-notifications/

---

## 27. Troubleshooting playbook

### 27.1. "Migration báo lỗi 'relation does not exist'"
- Check DbContext có `DbSet<T>` chưa.
- Check entity Configuration có `ToTable("...")` chưa.
- Run `dotnet ef migrations remove` rồi add lại.

### 27.2. "Consumer không nhận event"
- Check RabbitMQ Management UI: exchange + queue binding đúng?
- Check `appsettings.json`: `RabbitMq:Host` đúng?
- Check log MassTransit: có error consume không?
- Check DI: consumer đã register chưa (`AddMessageBus(... typeof(MyConsumer).Assembly)`)?

### 27.3. "Test integration timeout chờ DB"
- TestContainers cần Docker chạy.
- TimescaleDB image lớn — pre-pull: `docker pull timescale/timescaledb:latest-pg16`.

### 27.4. "JWT 401 ngay sau login"
- Check `JwtSettings:SecretKey` đồng nhất giữa AuthService và gateway.
- Check clock skew giữa containers (NTP).

### 27.5. "Outbox messages không được publish"
- Check `OutboxRelayBackgroundService` đã `AddHostedService` chưa.
- Check log: có exception khi serialize event không.
- Check RabbitMQ queue depth có tăng không.

### 27.6. "SLA timer không trigger warning"
- Check `WarningSentAt` đã null chưa (chỉ gửi 1 lần).
- Check background service đang chạy (`/health/ready`).
- Check `Status = Running` chưa (có thể đang Paused).

### 27.7. "Customer không nhận push"
- Check `NotificationPreference.PushEnabled = true`.
- Check `DeviceToken` còn `LastSeenAt` gần đây.
- Check quiet hours.
- Check Expo response: nếu `DeviceNotRegistered` → invalidate token.

### 27.8. "Performance chậm GET ticket list"
- Check index `(CustomerId, Status, IsDeleted)` tồn tại.
- Check N+1 query trong handler: dùng `.Include()` đầy đủ.
- Check pagination có applied (`Skip/Take`).

---

## 28. Tóm tắt files/paths cần tạo

### Service skeleton (cho 3 service mới)
```
services/BatteryService/
├── BatteryService.slnx
├── src/
│   ├── BatteryService.Api/                     (~10 files: Program + Controllers + appsettings + Dockerfile)
│   ├── BatteryService.Application/             (~50 files: CQRS + DTOs + Consumers + Services)
│   ├── BatteryService.Domain/                  (~14 files: Entities + Enums)
│   └── BatteryService.Infrastructure/          (~20 files: Persistence + Migrations + Background jobs + DI)
└── tests/
    ├── BatteryService.UnitTests/               (~25 test files)
    └── BatteryService.IntegrationTests/        (~10 test files)

services/TicketService/                         (Tương tự, ~140 files total)
services/NotificationService/                   (Tương tự, ~80 files total)
```

### FileStorageService updates (Sprint 1)
```
services/FileStorageService/src/
├── FileStorageService.Domain/                  ← nếu chưa có
│   ├── FileStorageService.Domain.csproj
│   ├── Entities/
│   │   └── UploadedFile.cs
│   └── Enums/
│       ├── FilePurposeEnum.cs
│       └── FileStatusEnum.cs
├── FileStorageService.Application/
│   ├── DTOs/
│   │   ├── FileMetadataDto.cs
│   │   └── FileUploadResponse.cs              ← thêm FileId/Purpose/Status/SizeBytes
│   ├── CQRS/
│   │   ├── Query/GetFileMetadataQuery.cs
│   │   ├── Query/GetPresignedUrlByFileIdQuery.cs
│   │   └── Command/DeleteFileByIdCommand.cs
│   └── Interfaces/Repositories/
│       └── IFileStorageUnitOfWork.cs
└── FileStorageService.Infrastructure/
    ├── Persistence/
    │   ├── ApplicationDbContext.cs
    │   ├── Configurations/UploadedFileConfiguration.cs
    │   └── Migrations/*AddUploadedFileMetadata*
    └── Persistence/Repositories/FileStorageUnitOfWork.cs
```

### Shared updates
```
shared/src/SharedContracts/Events/
├── Battery/
│   ├── BatteryAssetCreatedEvent.cs
│   ├── BatteryAnomalyDetectedEvent.cs
│   └── BatteryAssetTransferredEvent.cs
├── Ticket/
│   ├── TicketCreatedEvent.cs
│   ├── TicketAssignedEvent.cs
│   ├── TicketStatusChangedEvent.cs
│   ├── TicketResolvedEvent.cs
│   ├── TicketApprovedEvent.cs
│   ├── TicketRejectedEvent.cs
│   ├── TicketReopenedEvent.cs
│   ├── TicketClosedEvent.cs
│   ├── TicketEscalatedEvent.cs
│   ├── IncidentDeclaredEvent.cs
│   ├── SlaWarningEvent.cs
│   └── SlaBreachedEvent.cs
├── Account/
│   ├── AccountProfileUpdatedEvent.cs          (update: AvatarFileId, ExternalAvatarUrl, AvatarSource)
│   ├── StaffProfileUpdatedEvent.cs            (new)
│   └── StaffSkillsUpdatedEvent.cs             (new)
└── Notification/
    └── PermissionsChangedEvent.cs             (new — invalidate cache cross-service)
```

### Infra/config updates
```
docker-compose.yml                              ← postgres image, thêm tempo container
.env / .env.Docker                              ← Battery/Ticket/Notification DB conn, Expo token
.env.example                                    ← cập nhật
ci/                                             ← (giữ nguyên)
deploy/                                         ← helm chart cho 3 service mới
.github/workflows/ci.yml                        ← thêm matrix cho 3 service mới
monitoring/grafana/dashboards/                  ← thêm 3 dashboard JSON
monitoring/prometheus/prometheus.yml            ← thêm scrape config cho 3 service
monitoring/alertmanager/alertmanager.yml        ← thêm 3 alert rules
monitoring/tempo.yaml                           ← config Tempo
```

### Gateway updates
```
services/ApiGateway/src/                        ← route config + JWT validate middleware + rate limit + swagger aggregate
```

### Scripts
```
tools/
├── seed.sh                                     ← seed accounts + battery + ticket + KB
├── generate-sensor-data.py                     ← Python simulator IoT data
└── load-test.k6.js                             ← k6 perf test (optional)
```

### Docs (project-level)
```
docs/
├── core-business-flow.html                     ← Đã có (source of truth)
├── api/
│   ├── auth.swagger.json                       ← export per service
│   ├── battery.swagger.json
│   ├── ticket.swagger.json
│   └── notification.swagger.json
├── architecture/
│   ├── microservices-overview.md
│   ├── event-flow.md                           ← biểu đồ event giữa services
│   └── state-machine-ticket.md                 ← chi tiết visual state machine
└── onboarding/
    └── be-newcomer.md                          ← onboarding doc BE dev mới
```

---

## 29. Tóm tắt nhanh — "tôi sẽ làm gì tuần này?"

Cập nhật 2026-05-13:

1. **Đã xong Sprint 1 foundation:**
   - [x] Đổi postgres image sang `timescale/timescaledb:latest-pg16`.
   - [x] Docker Compose tách logical database theo service (`auth_db`, `file_storage_db`) và có `postgres-init` idempotent.
   - [x] Bổ sung `UploadedFile` metadata cho FileStorageService và chuẩn hóa tham chiếu bằng `fileId`.
   - [x] Tạo migration `AddAccountProfileExtensionTables` cho AuthService (`AccountProfile`, `StaffProfile`, `StaffSkill`).
   - [x] Chuẩn hóa avatar flow: uploaded avatar dùng `AvatarFileId`, Google avatar dùng `ExternalAvatarUrl`, FE dùng `displayAvatarUrl`.
2. **Còn lại trước khi chuyển hẳn sang Sprint 2:**
   - [ ] Migration rollback test cho AuthService/FileStorageService.
   - [ ] Viết API contract doc draft riêng cho FE team start Sprint 2.
   - [ ] Update CLAUDE.md memory nếu workflow team yêu cầu.
3. **Tuần sau:** Bắt đầu Sprint 2 — BatteryService MVP:
   - Tạo solution skeleton.
   - Chạy `/scaffold-crud BatteryService BatteryType` đầu tiên (theo §16.1).
4. **Hằng ngày:** Cập nhật memory bằng `/kltn-task KAN-XX` cho mỗi ticket Jira nhận được.

---

# Phần VII — Bổ sung sau review (Gap Analysis)

> Phần này bổ sung sau khi review lần 2 phát hiện gap. Mỗi section đánh dấu **P0/P1/P2** và link tới section gốc trong Phần II–VI để biết cần update ở đâu.

---

## 30. AI Module integration — P0

> **Đây là gap lớn nhất.** Capstone có 3 trụ cột (Mobile/Web/AI) — overall ban đầu gần như bỏ qua AI integration. Hội đồng sẽ hỏi đầu tiên.

### 30.1. Bối cảnh
- AI Module = FastAPI + PyTorch (rules/tech/ai.md), output:
  - **SOH prediction** (LSTM/CNN-LSTM): regression % SOH với MAE < 2%
  - **Anomaly classification** (Isolation Forest): Normal / Degrading / Failed
- Backend (BatteryService) phải gọi AI để:
  1. Predict SOH định kỳ → lưu trend.
  2. Classify anomaly sau khi threshold detector kích hoạt (hybrid pipeline).
  3. Cung cấp SOH/classification cho FE/Mobile dashboard.
  4. Gửi feedback từ Staff về AI để retrain.

### 30.2. Architecture pattern — Hybrid threshold + AI

```
SensorReading ingest
    │
    ▼
ThresholdAnomalyDetector (fast, rule-based)
    │
    ├──[Normal]──→ skip
    │
    └──[Threshold breached]──→
            │
            ▼
    AiInferenceClient.ClassifyAnomaly(last 30 readings)
            │
            ├── Normal     → log false-positive candidate (Staff review)
            ├── Degrading  → Alert severity = Warning
            └── Failed     → Alert severity = Critical → publish event
            │
            └──→ AiInferenceClient.PredictSoh(window)
                     │
                     └──→ enrich Alert with SOH%, attach to event
```

### 30.3. New entities (BatteryService)

#### `SohPrediction`
| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | PK |
| `BatteryAssetId` | Guid (FK) | indexed |
| `PredictedSohPercent` | decimal(5,2) | 0–100 |
| `Confidence` | decimal(4,3) | 0–1 |
| `ModelVersion` | string(20) | "1.0", "1.1" |
| `InputWindowStartUtc` | DateTime | — |
| `InputWindowEndUtc` | DateTime | — |
| `PredictedAt` | DateTime | indexed DESC |
| `LatencyMs` | int | Cho monitoring |
| `RawResponse` | jsonb? | Debug |

#### `AnomalyClassification`
| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | PK |
| `AlertId` | Guid? (FK) | Link tới Alert nếu classify cho alert |
| `BatteryAssetId` | Guid | — |
| `Classification` | enum (Normal=1, Degrading=2, Failed=3) | — |
| `AnomalyScore` | decimal(8,6) | Isolation Forest score |
| `Confidence` | decimal(4,3) | — |
| `ModelVersion` | string(20) | — |
| `ClassifiedAt` | DateTime | — |
| `LatencyMs` | int | — |
| `StaffFeedback` | enum? (Correct=1, FalsePositive=2, FalseNegative=3) | Staff confirm sau khi resolve |
| `StaffFeedbackByUserId` | Guid? | — |
| `StaffFeedbackAt` | DateTime? | — |

### 30.4. AI Bridge service (BatteryService.Application)

```csharp
public interface IAiInferenceClient {
    Task<SohPredictionResult> PredictSohAsync(Guid assetId, IReadOnlyList<SensorReading> window, CancellationToken ct);
    Task<AnomalyClassificationResult> ClassifyAnomalyAsync(Guid assetId, IReadOnlyList<SensorReading> window, CancellationToken ct);
    Task<HealthCheckResult> HealthAsync(CancellationToken ct);
}

// HTTP impl
public class AiInferenceClient : IAiInferenceClient {
    private readonly HttpClient _http;  // base URL: http://ai-module:8000

    public async Task<SohPredictionResult> PredictSohAsync(Guid assetId, ...) {
        var payload = new {
            asset_id = assetId,
            readings = window.Select(r => new { time = r.Time, v = r.Voltage, i = r.Current, t = r.Temperature, soc = r.SocPercent })
        };
        // Polly retry 2 lần, timeout 200ms (vì SLA P1 < 100ms)
        var resp = await _http.PostAsJsonAsync("/predict/soh", payload, ct);
        var result = await resp.Content.ReadFromJsonAsync<SohResponse>(cancellationToken: ct);
        return new SohPredictionResult {
            SohPercent = result.soh_percent,
            Confidence = result.confidence,
            ModelVersion = result.model_version
        };
    }
}
```

**Polly config:**
- Timeout: 200ms (degrade gracefully — không block ingest pipeline)
- Retry: 2 lần exponential backoff
- Circuit breaker: 50% fail rate trong 30s → mở 60s

### 30.5. Background services AI

#### `SohPredictionBackgroundService`
- Frequency: **hourly per asset** (configurable).
- Cho mỗi asset Active → lấy 30 sensor readings gần nhất → call `PredictSohAsync` → lưu `SohPrediction`.
- Sau khi predict → so sánh với `previous.SohPercent`:
  - Giảm > 5% trong 24h → publish `SohRapidDegradationEvent`
  - Giảm xuống dưới 80% → publish `SohWarningEvent` (auto-tạo ticket Warning)
  - Giảm xuống dưới 60% → publish `SohCriticalEvent` (auto-tạo ticket Critical)

#### `AnomalyClassificationOnAlertConsumer`
- Internal consumer (in-process) khi `ThresholdAnomalyDetector` trigger.
- Call `ClassifyAnomalyAsync` → enrich Alert + publish `BatteryAnomalyDetectedEvent` với classification.

### 30.6. Updated `BatteryAnomalyDetectedEvent`
Thêm fields:
```csharp
public record BatteryAnomalyDetectedEvent : IntegrationEvent {
    // ... fields cũ ...
    public AnomalyClassificationEnum Classification { get; init; }   // Normal/Degrading/Failed
    public decimal AnomalyScore { get; init; }
    public decimal? CurrentSohPercent { get; init; }
    public string AiModelVersion { get; init; } = string.Empty;
}
```

### 30.7. New endpoints

```
GET    /api/battery-assets/{id}/soh-prediction              (Customer own / Staff / Manager)
GET    /api/battery-assets/{id}/soh-history?from=&to=       (— same —)
GET    /api/battery-assets/{id}/anomaly-classifications     (— same —)
POST   /api/v1/anomaly-classifications/{id}/feedback           (Staff — confirm correct / false positive)
GET    /api/v1/ai/model-info                                   (Admin — current model version + last retrain)
GET    /api/v1/ai/inference-latency-stats                      (Admin — P50/P95/P99 latency)
GET    /api/v1/ai/health                                       (Internal proxy to AI /health)
```

### 30.8. Caching strategy AI

| Data | TTL | Lý do |
|------|-----|-------|
| SohPrediction latest per asset | 5 phút | Đỡ load AI |
| AnomalyClassification per alert | 1 giờ | Stable sau khi classify |
| Model info | 10 phút | Đổi không thường xuyên |

### 30.9. AI service docker compose
```yaml
ai-module:
  build:
    context: ./ai-module
    dockerfile: Dockerfile
  container_name: solar-ai
  environment:
    MODEL_VERSION: "1.0"
    SCALER_PATH: /app/models/weights/scaler.pkl
    LSTM_PATH: /app/models/weights/soh_lstm_v1.0.pth
    ISO_FOREST_PATH: /app/models/weights/isolation_forest_v1.0.pkl
  ports: ["8000:8000"]
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 10s
    retries: 5
  networks: [solar-net]
```

### 30.10. Performance monitoring
Prometheus metrics:
- `ai_inference_latency_milliseconds` histogram (label: endpoint=soh|classify)
- `ai_inference_total` counter (label: endpoint, status=success|timeout|error)
- `ai_model_version_info` gauge (label: version)

**Alert:** `ai_inference_latency_p95 > 100ms` for 5min → notify team.

### 30.11. Fallback khi AI down
- BatteryService phải vận hành được khi AI Module down:
  - Threshold detector vẫn chạy bình thường (rule-based).
  - Alert vẫn được tạo nhưng `Classification = Unknown`, không có SOH%.
  - Banner UI "AI service unavailable — basic detection only".
  - Circuit breaker mở → ngừng gọi AI 60s.

### 30.12. AI feedback loop (cho retraining)
- Staff resolve ticket → UI hỏi "Phân loại Failed của AI có đúng không?"
- POST `/api/v1/anomaly-classifications/{id}/feedback` lưu `StaffFeedback`.
- Background export hàng tháng → CSV → AI team retrain.
- Endpoint Admin xem accuracy: `GET /api/v1/ai/feedback-stats` (true positive rate, false positive rate).

### 30.13. Tests bắt buộc
- `AiInferenceClientTests`: timeout/retry/circuit-breaker behavior
- `SohPredictionBackgroundServiceTests`: trigger events khi SOH giảm
- `AnomalyClassificationOnAlertConsumerTests`: enrich alert correctly
- Integration test với mocked AI server (WireMock.Net)
- Performance test: 100 concurrent classify call P95 < 100ms

---

## 31. Site entities — P0

> Solar farm thực tế gom asset theo site. Mô hình hiện tại `Customer → Asset` trực tiếp sai về business reality. Topology: `Customer (1) → (*) Site → (*) BatteryAsset`. Sửa từ đầu rẻ hơn refactor sau.

### 31.1. New entities

#### `Site` (BatteryService)
| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | PK |
| `Name` | string(200) | "Solar Farm An Giang #1" |
| `CustomerId` | Guid (FK) | Owner |
| `Address` | string(500)? | — |
| `Latitude`, `Longitude` | decimal? | GPS center |
| `CapacityKw` | decimal? | Tổng công suất site |
| `InstallDate` | DateTime | — |
| `Status` | enum (Active=1, UnderMaintenance=2, Decommissioned=3) | — |
| `ContactPersonName` | string? | Người liên hệ tại site |
| `ContactPersonPhone` | string? | — |

### 31.2. Update existing entity
- `BatteryAsset.SiteId` nullable (backward compatible).
- Migration: `AddSite` — tạo bảng + thêm column nullable.

### 31.3. New endpoints
```
POST   /api/v1/sites                                      (Admin)
GET    /api/v1/sites?customerId=&status=                  (Admin/Manager — Customer own)
GET    /api/v1/sites/{id}                                 (— same —)
GET    /api/v1/sites/{id}/assets                          (list asset trong site)
GET    /api/v1/sites/{id}/dashboard                       (aggregated health của site)
GET    /api/v1/sites/{id}/alerts                          (all alerts của site)
PUT    /api/v1/sites/{id}
DELETE /api/v1/sites/{id}                                 (block nếu còn asset)

GET    /api/v1/customers/me/sites                         (Customer — list sites mình sở hữu)
```

### 31.4. Site-aggregated alert (giảm noise)
Khi nhiều asset cùng site cùng anomaly trong 5 phút → tạo 1 `SiteAlert` thay vì N `Alert`:
- Entity `SiteAlert` (parentSiteId, anomalyType, affectedAssetIds[], severity, detectedAt).
- Push notification 1 lần với title "5 pin tại Solar Farm An Giang #1 overheat" thay vì spam 5 push.
- Customer/Staff drill down xem assets cụ thể.

### 31.5. Site dashboard endpoint
```json
GET /api/v1/sites/{id}/dashboard
{
  "siteId": "...",
  "name": "Solar Farm An Giang #1",
  "totalAssets": 50,
  "activeAssets": 48,
  "assetsWithActiveAlerts": 3,
  "averageSohPercent": 92.5,
  "totalCapacityKw": 500,
  "ticketsOpen": 2,
  "ticketsResolved30d": 12,
  "lastAlertAt": "...",
  "healthScore": 87           // computed: weighted avg SOH + alert penalty
}
```

### 31.6. Migration impact
- `BatteryAsset` migration `AddSiteAndGroup` (Sprint 2 hoặc 3).
- Seed: tạo Site mặc định "Default Site" cho Customer chưa có site, gán assets cũ vào đó.

---

## 32. Ticket relationships — parent-child, merge, watch — P0

### 32.1. New entity `TicketRelation`
| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | PK |
| `SourceTicketId` | Guid (FK) | — |
| `TargetTicketId` | Guid (FK) | — |
| `RelationType` | enum | 1=DuplicateOf, 2=RelatedTo, 3=CausedBy, 4=Blocks, 5=ChildOf, 6=ParentOf |
| `CreatedByUserId` | Guid | — |
| `CreatedAt` | DateTime | — |
| `Reason` | string? | — |

**Constraint:** unique `(SourceTicketId, TargetTicketId, RelationType)`.

### 32.2. New entity `TicketSubscription` (watch/follow)
| Field | Type | Note |
|-------|------|------|
| `TicketId` | Guid (FK, PK part) | — |
| `UserId` | Guid (PK part) | — |
| `SubscribedAt` | DateTime | — |
| `NotificationFrequency` | enum (Immediate=1, Daily=2) | — |

### 32.3. Auto-subscription rules
- Customer owner → auto subscribe.
- Assigned Staff → auto subscribe.
- Manager (assigned) → auto subscribe khi assign.
- Người comment → auto subscribe (giống GitHub).
- @mention → auto subscribe.

### 32.4. Merge & duplicate flow

#### Endpoint
```
POST   /api/v1/tickets/{id}/merge-into/{targetId}      (Manager)
```

#### Logic
```csharp
// Mark source ticket as DuplicateOf target, close source
// Move all comments + attachments + activity → target
// Notify subscribers cả 2 ticket
// Activity log "Merged into TKT-..."
```

### 32.5. Parent-child (Incident → child tickets)
- Khi Manager `DeclareIncident` cho ticket → ticket đó có thể có nhiều child.
- Endpoint `POST /api/v1/tickets/{parentId}/children` (Manager link child tickets).
- Khi parent closed → option auto-close all unclosed children.
- Báo cáo: "Incident X caused N tickets, total resolution time".

### 32.6. Endpoints
```
POST   /api/v1/tickets/{id}/relations                  (link tới ticket khác)
DELETE /api/v1/tickets/{id}/relations/{relationId}
GET    /api/v1/tickets/{id}/relations                  (list relations)

POST   /api/v1/tickets/{id}/subscribe                  (current user follow)
DELETE /api/v1/tickets/{id}/subscribe                  (unfollow)
GET    /api/v1/tickets/{id}/subscribers                (Manager view)
GET    /api/v1/me/subscriptions                        (my followed tickets)
```

### 32.7. UI impact (FE note)
- Ticket detail panel "Related tickets" sidebar.
- Activity feed mention "🔗 Merged with TKT-..."
- "Watch" toggle button.

### 32.8. Tests
- `TicketMergeCommandHandlerTests`: merge xong source closed + comments moved
- `TicketRelationCommandHandlerTests`: prevent circular relation (A duplicateOf B + B duplicateOf A)
- Auto-subscribe trigger khi comment

---

## 33. SLA pause limits & advanced — P0

### 33.1. Loophole hiện tại
BR-04 cho phép pause SLA không giới hạn → Staff gaming SLA bằng cách pause hoài.

### 33.2. New rules

#### BR-04-Extended: Pause limits per priority

| Priority | MaxTotalPauseMinutes | MaxPauseEpisodes | Auto-resume after |
|----------|---------------------|------------------|-------------------|
| P1 Critical | 60 (1h) | 2 | 30 phút chờ Customer |
| P2 High | 480 (8h) | 5 | 24h chờ Customer |
| P3 Normal | 1440 (24h) | 10 | 72h chờ Customer |

- Vượt `MaxTotalPauseMinutes` → SLA timer **auto-resume** + notify Manager + ghi activity.
- Mỗi pause cần `Reason` rõ ràng (đã có).
- Pause lần thứ N+1 (vượt MaxPauseEpisodes) → cần Manager approve (chuyển sang trạng thái `PausePendingApproval`).

#### BR-04-Extended: Customer auto-reply timeout
- `WAITING_CUSTOMER` pause SLA, nhưng nếu Customer không reply trong `AutoResumeAfter` time:
  - Auto-resume SLA.
  - Send reminder push cho Customer.
  - Sau 3 reminder không reply → auto-close ticket as "Resolved (no customer feedback)".

### 33.3. Update `SlaTimer` entity
Thêm fields:
- `MaxTotalPauseMinutes` (snapshot lúc start, theo priority)
- `MaxPauseEpisodes` (snapshot)
- `PauseEpisodesCount` (counter)
- `LastAutoResumeAt` (DateTime?)
- `ApprovalRequired` (bool) — nếu pause lần thứ N+1

### 33.4. Update `SlaPauseEvent` entity
Thêm:
- `IsApprovedByManager` (bool? — nullable cho lần 1)
- `ApprovedByManagerId` (Guid?)
- `AutoResumeReason` (enum? — TimeLimitExceeded / CustomerTimeout / ManagerForce)

### 33.5. Background service mới
`SlaPauseEnforcementBackgroundService` (every 5 phút):
- Scan active pause events.
- Nếu total pause vượt max → auto-resume.
- Nếu pause type `WaitingCustomer` vượt `AutoResumeAfter` → auto-resume + reminder.

### 33.6. Update `TicketHoldCommand`
Validation thêm:
- Reject nếu `PauseEpisodesCount >= MaxPauseEpisodes` AND không có Manager approval payload.

### 33.7. New endpoint
```
PUT    /api/v1/tickets/{id}/approve-pause              (Manager — approve pause lần N+1)
PUT    /api/v1/tickets/{id}/force-resume               (Manager — force resume khi Staff không resume)
```

### 33.8. Reporting impact
Thêm metric:
- `tickets_with_pause_limit_exceeded_total{priority}` counter
- Report "Top staff pause SLA nhiều nhất" — phát hiện gaming SLA.

---

## 34. Real-time updates (SSE / push channel) — P0

### 34.1. Lý do
- P1 Critical alert: 30s polling delay không chấp nhận được.
- Manager queue: live update tickets mới xuất hiện không cần F5.
- SLA countdown realtime cho Staff.

### 34.2. Quyết định technical
**Server-Sent Events (SSE)** — không phải full WebSocket, vì:
- One-way (server → client) đủ dùng.
- Built-in browser/RN support, không cần lib.
- Auto-reconnect.
- Tương thích HTTP/2 multiplexing.
- Đơn giản hơn WebSocket.

### 34.3. Architecture
```
Service publish event → MassTransit
       │
       ▼
NotificationService nhận event
       │
       ├──→ Push (Expo) — đã có
       ├──→ Email — đã có
       ├──→ SMS — đã có
       └──→ SSE Hub (new)
                │
                ├──→ Mobile subscribers
                └──→ Web subscribers
```

### 34.4. New SSE Hub service
Có thể là 1 module trong NotificationService HOẶC service riêng `RealtimeHub`. **Đề xuất module trong NotificationService**.

```
GET /api/v1/realtime/stream?topics=tickets,alerts,sla     (Server-Sent Events)
Headers: Authorization: Bearer {token}, Accept: text/event-stream
```

Server response:
```
event: ticket.assigned
data: {"ticketId":"...", "code":"TKT-2605-0001", "slaDueAt":"..."}

event: alert.critical
data: {"alertId":"...", "assetId":"...", "anomalyType":"Overheat"}

event: sla.warning
data: {"ticketId":"...", "remainingMinutes":45}

event: ping
data: {}
```

### 34.5. Subscriber → topic mapping
| Role | Auto-subscribe topics |
|------|----------------------|
| Customer | `alerts.own`, `tickets.own` |
| Staff | `tickets.assigned`, `sla.assigned`, `mentions` |
| Manager | `tickets.team`, `sla.team`, `escalations`, `incidents` |
| Admin | `system.health`, `incidents`, `audit.critical` |

### 34.6. Implementation
- ASP.NET Core SSE endpoint với `IAsyncEnumerable<SseEvent>`.
- Redis pub/sub backend (vì cần distribute giữa N instance NotificationService).
- Heartbeat 30s (event `ping`) để giữ connection alive.
- Reconnect: server gửi `Last-Event-ID` để client resume.

### 34.7. Endpoints
```
GET    /api/v1/realtime/stream?topics=...               (SSE — long-lived)
GET    /api/v1/realtime/topics                          (list available topics)
```

### 34.8. Fallback
- Mobile: nếu SSE fail → fallback Push (vẫn realtime qua Expo).
- Web: nếu SSE fail → fallback polling 30s.

### 34.9. Tests
- SSE end-to-end test: connect → publish event → assert received within 1s
- Reconnect test với Last-Event-ID
- Auth test: Customer A không nhận event của Customer B

---

## 35. Bulk operations + QR onboarding — P1

### 35.1. Bulk import endpoints

#### Bulk import battery assets (Admin)
```
POST   /api/battery-assets/bulk-import
Content-Type: multipart/form-data
  file: assets.csv
  fileFormat: csv | xlsx
```

CSV columns: `serial_number, battery_type_name, customer_email, install_date, site_name, warranty_end_date, location, notes`

Response:
```json
{
  "totalRows": 100,
  "successCount": 95,
  "failureCount": 5,
  "createdAssetIds": [...],
  "errors": [
    {"row": 23, "field": "customer_email", "value": "...", "error": "Customer not found"},
    {"row": 47, "field": "serial_number", "error": "Duplicate"}
  ]
}
```

#### Bulk invite users
```
POST   /api/v1/auth/users/bulk-invite
  file: users.csv  → email, role, full_name, department
```
- Mỗi row → tạo Account + send invite email (event `SendAdminInviteEvent`).
- Skip nếu email đã tồn tại.

#### Bulk reassign tickets
```
PUT    /api/v1/tickets/bulk-reassign
{
  "ticketIds": ["...", "..."],
  "newStaffId": "...",
  "reason": "Staff X nghỉ phép"
}
```
- Validate mỗi ticket có thể reassign.
- Atomic: hoặc all-or-nothing, hoặc per-ticket success/fail report.

### 35.2. QR code onboarding flow

#### Admin generate QR
1. Admin tạo BatteryAsset → system gen `ClaimCode` (JWT-like, signed, 1-time-use, 90d expiry).
2. Admin print QR sticker chứa URL: `https://app.gsu26se55.com/claim?code={claimCode}` hoặc deeplink `gsu26se55://claim?code=...`.

#### Customer claim
```
POST   /api/battery-assets/claim
{
  "claimCode": "eyJhbGc..."
}
```
- Validate signature + expiry + not-used.
- Link `BatteryAsset.CustomerId = currentUserId`.
- Mark code used.
- Activity log.

#### Entity update
- `BatteryAsset.ClaimCode` (string?, indexed)
- `BatteryAsset.ClaimedAt` (DateTime?)
- `BatteryAsset.ClaimCodeExpiresAt` (DateTime?)

### 35.3. Endpoints summary
```
POST   /api/battery-assets/bulk-import                (Admin)
POST   /api/v1/auth/users/bulk-invite                    (Admin)
PUT    /api/v1/tickets/bulk-reassign                     (Manager)
PUT    /api/v1/tickets/bulk-priority                     (Manager — chỉ cho ticket Open chưa assigned)
POST   /api/battery-assets/{id}/generate-claim-code   (Admin — re-gen QR)
GET    /api/battery-assets/{id}/claim-code-qr.png     (Admin — render QR PNG)
POST   /api/battery-assets/claim                      (Customer)
```

### 35.4. Tests
- Import 100 rows, 5 invalid → 95 created, 5 reported with row/field.
- QR claim flow end-to-end: gen → claim → assert ownership.
- Replay attack: claim code dùng 2 lần → second fail.

---

## 36. Comment / MaintenanceLog advanced — P1

### 36.1. Edit & delete comments

#### Endpoint
```
PUT    /api/v1/comments/{id}                            (author only, within 15min OR Admin always)
DELETE /api/v1/comments/{id}                            (author or Admin — soft delete)
GET    /api/v1/comments/{id}/history                    (edit history view)
```

#### Schema update
- `TicketComment.EditedAt` (DateTime?)
- `TicketComment.EditCount` (int default 0)
- `TicketComment.IsDeleted` (bool — soft delete, show as "deleted by user")

#### History
Lưu `TicketCommentHistory`:
- `Id, CommentId, OldBody, EditedAt, EditedByUserId`

### 36.2. @Mention parsing

#### Logic
- Body chứa `@username` hoặc `@{userId}` → parse khi save.
- Lookup user → tạo `Mention` record.
- Trigger notification → mention user.
- Auto-subscribe mentioned user.

#### Entity `CommentMention`
- `Id, CommentId, MentionedUserId, MentionedByUserId, CreatedAt`

#### Endpoint
```
GET    /api/v1/me/mentions                              (my mentions feed)
```

### 36.3. Reaction (emoji)
- Entity `CommentReaction` (CommentId, UserId, Emoji, ReactedAt).
- 6 emoji standard: 👍 👎 ❤️ 🎉 😕 🚀
- Endpoint `POST /api/v1/comments/{id}/reactions`, body `{"emoji": "👍"}`.

### 36.4. Pinned comments
- Manager pin important comment để hiện trên top.
- `TicketComment.IsPinned` bool, `PinnedAt`, `PinnedByUserId`.
- Max 3 pinned per ticket.

### 36.5. Comment templates (Staff reusable snippets)
Entity `CommentTemplate`:
- `Id, OwnerUserId (nullable for shared), Title, Body, Category, UsageCount`
- Shared templates (Manager tạo) vs personal (Staff tạo).
- Endpoint:
```
GET    /api/v1/comment-templates?scope=mine|shared
POST   /api/v1/comment-templates
PUT    /api/v1/comment-templates/{id}
DELETE /api/v1/comment-templates/{id}
```

### 36.6. MaintenanceLog advanced
Tương tự:
- Edit within 30 phút sau post (vì có thể nhớ ra sót chi tiết).
- `MaintenanceLogTemplate` cho Staff reuse.
- GPS check-in (xem §44).

### 36.7. Tests
- Edit window enforcement: thử edit sau 16 phút → reject (non-Admin).
- Mention parsing với 5 cases: valid user, invalid user, multiple mentions, escaped @, plain text.
- Reaction toggle: react 2 lần cùng emoji → remove.

---

## 37. Alert silence / snooze / ack escalation — P1

### 37.1. Silence (Manager mark known issue)
- Manager đánh dấu 1 anomaly type cho 1 asset/site là "known issue, không alert nữa trong N giờ/ngày".
- Entity `AlertSilenceRule`:
  - `Id, ScopeType (Asset=1|Site=2|BatteryType=3), ScopeId, AnomalyType, SilencedUntil, Reason, CreatedByUserId`
- ThresholdDetector check rule trước khi tạo alert.

### 37.2. Snooze (Customer "tôi biết, đừng push trong 1h")
- Customer mở alert detail → click "Snooze 1h".
- `Alert.SnoozeUntil` (DateTime?).
- Push channel skip alert nếu still snoozed.

### 37.3. Acknowledge escalation
- Critical alert tạo ra → push Customer.
- Nếu Customer không acknowledge trong 15 phút → push lần 2 (escalated to Staff).
- Nếu 30 phút vẫn không ack → auto-create ticket P1 + push Manager.

#### New entity `AlertAckTimeline`
- `Id, AlertId, EscalationLevel (1=Customer, 2=Staff, 3=Manager), EscalatedAt, ResolvedByAck (bool)`

#### Background service
`AlertAckEscalationBackgroundService` (every 5 phút):
- Scan critical alerts không có ack.
- Trigger next level escalation theo timing rule.

### 37.4. Endpoints
```
POST   /api/alerts/{id}/snooze                       (Customer — own)
{
  "durationMinutes": 60,
  "reason": "Đang sửa"
}

POST   /api/v1/alert-silence-rules                      (Manager)
GET    /api/v1/alert-silence-rules?scopeType=&scopeId=
DELETE /api/v1/alert-silence-rules/{id}
```

### 37.5. Group alerts dashboard
- Mobile/Web hiển thị "5 cảnh báo overheat tại Site An Giang" thay vì 5 row riêng.
- Backend: `GET /api/alerts/grouped?groupBy=site,anomaly` returns grouped response.

---

## 38. Edge case business rules matrix — P0

> Bảng này phải vào SRS và CLAUDE.md để mọi BE dev tham chiếu.

### 38.1. Matrix

| # | Edge case | Rule giải quyết | Implementation |
|---|-----------|----------------|----------------|
| EC-01 | Customer xóa account khi có ticket OPEN | Block delete, yêu cầu close hết ticket trước. Hoặc soft-delete + anonymize, tickets giữ nguyên với `CustomerName = "[Deleted]"`. | AuthService `AccountDeleteCommand` check TicketService API; nếu có open → return error |
| EC-02 | Staff nghỉ việc (Account.Status=Inactive) khi có ticket ASSIGNED/IN_PROGRESS | Auto-reassign tới Manager queue (status=Open, AssignedStaffId=null). Notify Manager. | `AccountStatusChangedConsumer` trong TicketService — scan ticket assigned tới staff đó |
| EC-03 | BatteryType bị xóa khi có Asset gắn | Block delete. Force Admin transfer assets sang type khác trước. | `BatteryTypeDeleteCommandHandler` check `Assets.AnyAsync(a => a.TypeId == id && !a.IsDeleted)` |
| EC-04 | ThresholdConfig đổi khi có Alert OPEN | Alert cũ giữ nguyên ngưỡng cũ (audit). Alert mới dùng ngưỡng mới. | Snapshot threshold values trong Alert entity (đã có `ThresholdValue` field) |
| EC-05 | Customer transfer asset khi có Alert OPEN | Alerts vẫn gắn với asset (không transfer). Notify cả old/new customer. | `BatteryAssetTransferOwnerCommandHandler` — không touch alerts |
| EC-06 | Customer transfer asset khi có Ticket OPEN | Block transfer. Yêu cầu close ticket trước. | Validation trong handler |
| EC-07 | Manager nghỉ phép khi có ticket cần approve | Approval timeout 24h → auto-escalate tới Admin hoặc Manager khác. | `TicketApprovalTimeoutBackgroundService` mỗi giờ |
| EC-08 | 2 Manager approve cùng 1 ticket (race condition) | Optimistic concurrency via `RowVersion`. First-write-wins, second gets 409 Conflict. | EF `[Timestamp] byte[] RowVersion` trên Ticket |
| EC-09 | Customer reopen đúng lúc Staff đang resolve song song | Optimistic concurrency. Resolve fail → Staff thấy "Ticket đã reopened, refresh". | Same as EC-08 |
| EC-10 | Alert auto-resolve trong khi Staff đang viết maintenance log | Alert vẫn auto-resolve. Staff tiếp tục log (ticket vẫn còn). Activity ghi "Alert auto-resolved during work". | Soft constraint, không block |
| EC-11 | Asset decommissioned khi có ticket history | Asset không xóa, set `Status=Decommissioned`. Tickets vẫn truy cập được nhưng không tạo mới được. | Validation `TicketCreateCommand` reject nếu asset status != Active |
| EC-12 | Customer hết warranty nhưng ticket vẫn open | Ticket xử lý bình thường (warranty là vấn đề billing, không phải support). Hiển thị warning trên UI. | No backend block |
| EC-13 | Sensor stop sending data 24h | Tạo Alert `DeviceOffline` auto. Notify Customer. | `DeviceOfflineDetectionBackgroundService` daily |
| EC-14 | Bulk import có row duplicate serial | Skip + report. Không atomic fail toàn batch. | Per-row try/catch |
| EC-15 | Customer claim mã QR đã hết hạn | Reject với code `BATTERY_CLAIM_001 — Code expired`. | Validation |
| EC-16 | Customer claim mã của Customer khác đã claim | Reject với `BATTERY_CLAIM_002 — Already claimed`. | Validation |
| EC-17 | Email gửi qua EmailService fail 3 lần | DLQ. Admin có endpoint reprocess. | `OutboxRelayBackgroundService` mark failed sau retry |
| EC-18 | TicketAssignCommand với Staff đang vượt MaxConcurrentTickets | Reject với `TICKET_ASSIGN_002`. Manager phải chọn Staff khác. | Validation trong handler |
| EC-19 | Customer rate ticket nhưng rating = 0 hoặc > 5 | Validation reject, range 1-5. | `IValidatable` |
| EC-20 | SLA timer drift do server restart | On startup, recalc DueAt từ StartedAt + SLA hours - PausedMinutes. | Startup migration check |

### 38.2. Implementation note
- Tất cả rules trên phải có **unit test** trong service tương ứng.
- Document trong `docs/architecture/edge-cases.md` để hội đồng có thể tra cứu.

---

## 39. GDPR & compliance — P1

### 39.1. Data export (right to data portability)
```
POST   /api/v1/auth/me/export-data                      (Customer/Staff/Manager)
```
- Async job: gọi tới Battery/Ticket/Notification để aggregate.
- Response: tạo `DataExportRequest` record, gửi email kèm signed URL download (24h expiry).
- Format: JSON gồm:
  - Profile
  - List battery assets + sensor data 90d
  - List tickets + comments + maintenance logs
  - List notifications
  - List audit logs

### 39.2. Right to be forgotten
```
DELETE /api/v1/auth/me                                  (Customer)
{
  "password": "...",
  "reason": "..."
}
```
- Confirm password.
- Trigger `AccountDeleteCommand` → 2-step process:
  1. Mark `Account.IsScheduledForDeletion=true`, set `DeleteScheduledAt=now+30d` (cooling-off).
  2. Background service after 30 ngày → anonymize:
     - `Account.Email = "deleted_{userId}@anonymized.local"`
     - `Account.FullName = "[Deleted User]"`
     - `Account.PhoneNumber = null`
     - `Account.Address = null`
     - Keep `Id` cho audit trail.
  3. Tickets/Comments giữ nguyên nhưng `CustomerName` show "[Deleted User]".

### 39.3. Data retention policy

| Data type | Retention | After expire | Justify |
|-----------|-----------|--------------|---------|
| SensorReading raw | 90 ngày | Drop (TimescaleDB retention policy) | Volume lớn, có hourly aggregate |
| SensorReading hourly | 1 năm | Aggregate to daily | Trend analysis |
| SensorReading daily | 5 năm | Drop | Long-term trend |
| AuditLog (auth) | 2 năm | Archive to cold storage | Compliance |
| TicketActivity | Forever | — | Audit |
| Ticket + Comment | Forever (anonymized if user deleted) | — | Audit |
| Notification | 1 năm | Drop | UX cleanup |
| LoginAttempt | 6 tháng | Drop | Security baseline |
| OutboxMessage processed | 30 ngày | Drop | Cleanup |
| RefreshToken revoked | 30 ngày | Drop | — |

### 39.4. PII redaction trong logs
- Serilog enricher tự động mask:
  - Email → `a***@example.com`
  - Phone → `09**12345`
  - Password → `[REDACTED]`
- Audit log không mask (cần đầy đủ cho compliance).

### 39.5. Cookie consent (FE concern but BE provides)
- `GET /api/v1/legal/privacy-policy` returns markdown.
- `POST /api/v1/auth/me/consent` lưu consent record.

### 39.6. Endpoints summary
```
POST   /api/v1/auth/me/export-data                      (Customer/Staff/Manager — async)
GET    /api/v1/auth/me/export-data/{requestId}/status   (poll status)
GET    /api/v1/auth/me/export-data/{requestId}/download (signed URL)
DELETE /api/v1/auth/me                                  (right to be forgotten)
PUT    /api/v1/auth/me/cancel-deletion                  (within 30d cooling-off)
GET    /api/v1/legal/privacy-policy
GET    /api/v1/legal/terms-of-service
POST   /api/v1/auth/me/consent
```

### 39.7. Background services
- `DataExportBackgroundService`: process pending export requests.
- `AccountAnonymizationBackgroundService`: daily, scan accounts scheduled-for-deletion past cooling-off.
- `DataRetentionCleanupBackgroundService`: daily, drop expired records.

### 39.8. Tests
- Export data: assert all categories included.
- Cancel deletion in cooling-off → restore.
- After cooling-off → anonymized successfully, audit references intact.

---

## 40. Operational documents (ADR + DR + Runbook) — P1

> Capstone đánh giá cao "operational maturity". Đây là phần documentation đi kèm code.

### 40.1. Architecture Decision Records (ADR)
Folder `docs/adrs/`:

| ADR ID | Title |
|--------|-------|
| ADR-001 | Use Clean Architecture 4-layer per service |
| ADR-002 | CQRS + MediatR over service+repository pattern |
| ADR-003 | Custom `IValidatable<T>` over FluentValidation |
| ADR-004 | Outbox pattern for event publishing |
| ADR-005 | Redis-based Inbox for consumer idempotency |
| ADR-006 | TimescaleDB hypertable for sensor data (vs separate DB) |
| ADR-007 | Centralized NotificationService over per-service notification |
| ADR-008 | SSE over WebSocket for realtime |
| ADR-009 | Microservices per business capability (Auth/Battery/Ticket/Notification) |
| ADR-010 | API Gateway responsible for JWT validation + claim forwarding |
| ADR-011 | KnowledgeBase as module within TicketService, not separate service |
| ADR-012 | Polly for HTTP resilience (retry + circuit breaker + timeout) |
| ADR-013 | Hybrid threshold + AI anomaly detection |
| ADR-014 | Account profile extension tables in AuthService (vs stuffing `Account` / separate UserService) |
| ADR-015 | TestContainers over shared dev Postgres for integration tests |

**ADR template:**
```markdown
# ADR-{ID}: {Title}

## Status
Accepted | Superseded by ADR-XXX | Deprecated

## Context
What is the problem we're solving?

## Decision
What did we decide?

## Consequences
- Positive: ...
- Negative: ...
- Neutral: ...

## Alternatives Considered
- Option B: rejected because ...

## Date
2026-05-XX
```

### 40.2. Disaster Recovery (DR) plan
`docs/operations/dr-plan.md`:

#### Backup strategy
- Postgres: `pg_dump` daily → MinIO bucket `backups/postgres/{date}.sql.gz`.
- Retention: 7 daily + 4 weekly + 12 monthly.
- Verify restore: weekly automated `pg_restore` to temp DB.

#### RTO/RPO targets
| Scenario | RTO (Recovery Time) | RPO (Data Loss) |
|----------|---------------------|-----------------|
| DB corrupt | 1 giờ | 24h (last backup) |
| Single service crash | 5 phút (k8s restart) | 0 (stateless) |
| RabbitMQ down | 30 phút | 0 (Outbox persistent) |
| Redis down | 15 phút | Acceptable (cache only) |
| Total cluster down | 4 giờ | 24h |

#### Restore procedure
1. Provision new infra (terraform / docker-compose).
2. Restore Postgres backup: `gunzip < backup.sql.gz | psql`.
3. Verify migrations match: `dotnet ef database update --no-build`.
4. Restart services with feature flag `MAINTENANCE_MODE=true` (read-only).
5. Smoke test: health endpoints + sample query.
6. Disable maintenance mode.

### 40.3. Runbook per scenario
`docs/operations/runbook/`:
- `01-postgres-down.md`
- `02-rabbitmq-queue-backed-up.md`
- `03-outbox-lag-high.md`
- `04-sla-breach-rate-high.md`
- `05-ai-module-down.md`
- `06-disk-space-low.md`
- `07-secret-rotation.md`

Sample structure:
```markdown
# Runbook: RabbitMQ queue backed up

## Symptoms
- AlertManager fires `RabbitMqQueueDepthHigh`
- Notification delays
- Outbox lag tăng

## Diagnose
1. Check Management UI: http://localhost:15673
2. Identify slow consumer: ...
3. Check log: ...

## Mitigation
1. Scale consumer service: `docker-compose up -d --scale notification=3`
2. If poison message: move to DLQ via management UI
3. If schema mismatch: ...

## Postmortem template
...
```

### 40.4. On-call & incident response
`docs/operations/incident-response.md`:
- Severity levels (SEV1/SEV2/SEV3).
- Communication channel (Slack #incidents).
- Escalation path: Staff → Manager → Admin → Tech Lead.
- Postmortem within 48h.

### 40.5. SLOs (Service Level Objectives)
| Service | Availability | Latency P95 | Error rate |
|---------|--------------|-------------|------------|
| AuthService login | 99.9% | < 200ms | < 0.1% |
| BatteryService realtime | 99.5% | < 150ms | < 1% |
| TicketService write | 99.9% | < 300ms | < 0.5% |
| NotificationService send | 99% | < 500ms | < 2% |
| AI Inference | 99% | < 100ms | < 5% |

### 40.6. Onboarding doc
`docs/onboarding/`:
- `be-newcomer.md` — 1 ngày đầu setup, run local, chạy test.
- `fe-newcomer.md`
- `ai-newcomer.md`
- `glossary.md` — domain terms.

---

## 41. Preventive maintenance schedule — P2

### 41.1. Entity `MaintenanceSchedule`
| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | — |
| `BatteryAssetId` | Guid (FK) | — |
| `MaintenanceType` | enum (Cleaning=1, Inspection=2, SohCheck=3, Calibration=4, FullService=5) | — |
| `IntervalDays` | int | Mỗi N ngày |
| `LastPerformedAt` | DateTime? | — |
| `NextDueAt` | DateTime | computed |
| `IsActive` | bool | — |
| `CreatedByUserId` | Guid | Manager set |

### 41.2. Background service
`PreventiveMaintenanceBackgroundService` (daily):
- Scan schedule with `NextDueAt < now + 7d`.
- Tạo Ticket origin `PreventiveMaintenance` (new origin enum value) tự động.
- Title: "Preventive: {MaintenanceType} - {AssetSerial}".
- Manager auto-assign theo schedule.

### 41.3. Endpoints
```
POST   /api/battery-assets/{id}/maintenance-schedules     (Manager)
GET    /api/battery-assets/{id}/maintenance-schedules
GET    /api/v1/maintenance-schedules/upcoming?within=30d     (Manager)
PUT    /api/v1/maintenance-schedules/{id}/complete           (Staff — mark done, updates LastPerformedAt)
DELETE /api/v1/maintenance-schedules/{id}
```

### 41.4. Reports
- "Assets quá hạn maintenance > 30 ngày"
- "Maintenance compliance rate per Staff"

---

## 42. Parts inventory — P2

### 42.1. Entity `Part`
| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | — |
| `Sku` | string(50) UNIQUE | — |
| `Name` | string(200) | "BMS Module 12V" |
| `Description` | string? | — |
| `Manufacturer` | string? | — |
| `UnitCost` | decimal? | — |
| `StockCount` | int | — |
| `MinStockThreshold` | int | Alert khi xuống |
| `Status` | enum (Active=1, Discontinued=2) | — |

### 42.2. Entity `PartTransaction` (audit)
| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | — |
| `PartId` | Guid (FK) | — |
| `TransactionType` | enum (StockIn=1, Used=2, Adjusted=3, Disposed=4) | — |
| `Quantity` | int | + or - |
| `RelatedTicketId` | Guid? | Nếu dùng cho ticket |
| `PerformedByUserId` | Guid | — |
| `PerformedAt` | DateTime | — |
| `Note` | string? | — |

### 42.3. Integration với MaintenanceLog
- Khi Staff add MaintenanceLog với `PartsUsed` → tự động tạo `PartTransaction` type=Used, deduct stock.
- Stock < MinStockThreshold → notify Manager "Cần nhập linh kiện X".

### 42.4. Endpoints
```
POST   /api/v1/parts                                    (Admin)
GET    /api/v1/parts?lowStock=true                      (Manager/Admin)
PUT    /api/v1/parts/{id}/stock-in                      (Manager — nhập kho)
GET    /api/v1/parts/{id}/transactions
GET    /api/v1/reports/parts-usage?from=&to=
```

> Out of scope chính của capstone nhưng nếu kịp thời gian thì làm — academic bonus.

---

## 43. Public Knowledge Base + Customer self-help — P2

### 43.1. Update `KnowledgeBaseArticle`
Thêm fields:
- `IsPublic` (bool) — visible cho Customer + public
- `PublicTitle` (string?) — version Customer-friendly
- `PublicBody` (string?) — version Customer-friendly (đơn giản hơn Staff version)

### 43.2. Public endpoint (no auth)
```
GET    /api/v1/public/knowledge-base?q=&category=
GET    /api/v1/public/knowledge-base/{slug}
POST   /api/v1/public/knowledge-base/{id}/helpful       (anonymous count — rate limit per IP)
```

### 43.3. Self-help suggest khi Customer tạo ticket
- Form tạo ticket → khi Customer chọn Category → suggest 3 KB articles.
- Nếu Customer click "Đã giải quyết bằng article này" → ticket không được tạo, increment `HelpfulCount`.
- Báo cáo "Articles giảm ticket bao nhiêu".

### 43.4. Endpoint hỗ trợ flow
```
POST   /api/v1/tickets/suggest-articles
{
  "category": "Charging",
  "description": "Pin sạc rất chậm"
}
→ Response: [{articleId, title, snippet}, ...]
```

---

## 44. Mobile deep linking + Staff field features — P1

### 44.1. Deep link URL scheme
| Resource | URL pattern |
|----------|-------------|
| Ticket detail | `gsu26se55://tickets/{id}` |
| Alert detail | `gsu26se55://alerts/{id}` |
| Asset detail | `gsu26se55://assets/{id}` |
| Claim QR | `gsu26se55://claim?code={code}` |
| Notification | `gsu26se55://notifications/{id}` |

### 44.2. Universal Links (iOS) / App Links (Android)
- Web URL `https://app.gsu26se55.com/tickets/{id}` → mở app nếu installed, fallback web.
- Apple file: `/.well-known/apple-app-site-association`
- Android file: `/.well-known/assetlinks.json`
- BatteryService/TicketService endpoint expose 2 file static.

### 44.3. Push payload có deep link
```json
{
  "to": "ExponentPushToken[...]",
  "title": "🔴 Cảnh báo nghiêm trọng",
  "body": "Pin BAT-001 overheat",
  "data": {
    "url": "gsu26se55://alerts/abc-123",
    "type": "alert.critical",
    "alertId": "abc-123"
  }
}
```

### 44.4. Staff field features (Mobile cho Staff đi field)

Mặc dù scope mobile chính là Customer, Staff đi on-site cần:

#### GPS check-in
- `MaintenanceLog.CheckInLatitude/Longitude/At`
- Endpoint `POST /api/v1/maintenance-logs/check-in`
- Verify check-in trong bán kính 100m từ site đăng ký.

#### Offline mode (sync queue)
- Staff không có mạng tại site → log work offline.
- Mobile lưu queue local, sync khi có mạng.
- Backend hỗ trợ `Idempotency-Key` (đã có) cho retry.

#### Photo upload tối ưu
- Resize ảnh client-side trước upload (max 1920px).
- Compress JPEG quality 80.
- Endpoint `POST /api/v1/files/upload` (FileStorageService).

#### Quick actions
- "Mark as Resolved + photo" (1 step thay vì 3).
- Voice-to-text cho maintenance summary.

### 44.5. Endpoints bổ sung
```
POST   /api/v1/maintenance-logs/check-in
GET    /.well-known/apple-app-site-association          (static)
GET    /.well-known/assetlinks.json                     (static)
```

---

## 45. Webhook outbound + public API — P2

### 45.1. Webhook outbound

#### Entity `WebhookSubscription`
| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | — |
| `CreatedByUserId` | Guid | Admin only |
| `Url` | string(500) | HTTPS only |
| `Secret` | string(64) | HMAC sign payload |
| `EventTypes` | string[] | Array of event names |
| `IsActive` | bool | — |
| `FailureCount` | int | Disable sau N fail liên tiếp |

#### Logic
- Admin register webhook + chọn events to subscribe.
- Internal consumer `WebhookDispatcherConsumer` subscribe tất cả events.
- Khi event xảy ra → tìm subscriptions match → POST payload + HMAC header `X-Signature`.
- Retry 3 lần exponential, fail → log + increment failure count.
- 10 consecutive failures → auto-disable + notify Admin.

#### Endpoints
```
POST   /api/v1/admin/webhooks                           (Admin)
GET    /api/v1/admin/webhooks
PUT    /api/v1/admin/webhooks/{id}
DELETE /api/v1/admin/webhooks/{id}
POST   /api/v1/admin/webhooks/{id}/test                 (send test payload)
GET    /api/v1/admin/webhooks/{id}/deliveries           (last 100 attempts)
```

### 45.2. Public API (cho partner integration)

#### API Key management (Admin)
```
POST   /api/v1/admin/api-keys                           (Admin tạo key)
{
  "name": "IoT Gateway #1",
  "scopes": ["sensor.ingest", "asset.read"]
}
→ Response: { "apiKey": "sb_live_..." }  (chỉ show 1 lần)

GET    /api/v1/admin/api-keys
DELETE /api/v1/admin/api-keys/{id}                      (revoke)
PUT    /api/v1/admin/api-keys/{id}/rotate               (gen new secret, old works 24h)
```

#### Auth via API Key
- Header `X-Api-Key: sb_live_...`
- Middleware validate + load scopes vào HttpContext.
- Limit per key: rate limit + scope check per endpoint.

#### Public endpoints (scope-gated)
```
POST   /api/v1/public/sensor-readings/batch             (scope: sensor.ingest)
GET    /api/v1/public/assets/{id}                       (scope: asset.read)
```

### 45.3. Tests
- Webhook signature verification.
- Auto-disable sau 10 fail.
- API key rotation grace period (old + new đều work 24h).

---

## 46. Advanced testing & chaos engineering — P2

### 46.1. Contract testing (Pact)

#### Setup
- Producer (BatteryService) viết contract: "Khi publish BatteryAnomalyDetectedEvent → schema phải có fields ABC".
- Consumer (TicketService) verify contract khi build.
- Lưu contracts ở `tests/contracts/`.

#### Tools
- `PactNet` cho .NET.
- CI step: `dotnet test --filter Category=Contract`.

### 46.2. Load testing (k6 detailed)

`tools/load-test/`:
- `sensor-ingest.k6.js`: 1000 readings/s for 5 phút.
- `customer-realtime.k6.js`: 100 concurrent users polling 30s.
- `manager-queue.k6.js`: 50 Manager đồng thời xem queue.
- `ticket-create.k6.js`: 100 Customer tạo ticket / phút.

Acceptance criteria (per §13.4):
```javascript
export const options = {
  scenarios: { /* ... */ },
  thresholds: {
    http_req_duration: ['p(95)<300', 'p(99)<500'],
    http_req_failed: ['rate<0.01'],
  },
};
```

### 46.3. Chaos engineering

#### Scenarios
| Scenario | Tool/Method | Expected behavior |
|----------|-------------|-------------------|
| Kill RabbitMQ 30s | `docker stop solar-rabbitmq && sleep 30 && docker start` | Outbox accumulates, replay khi up |
| Kill Redis | similar | Cache miss fallback DB |
| Kill 1 BatteryService instance (3-replica) | k8s pod delete | LB redirect, no error to client |
| Network partition AI Module | `tc qdisc add` | Circuit breaker open, fallback threshold-only |
| Disk fill 95% | `dd` fill | AlertManager fires, services degrade gracefully |
| Postgres slow query (sleep 30s) | `pg_sleep` | Timeout, Polly retry, response 503 sau retry exhaust |

#### Automation
- `tools/chaos/`:
  - `kill-service.sh <name> <duration>`
  - `network-partition.sh <service> <duration>`
  - Run trong staging env (không phải local dev).

### 46.4. Mutation testing (Stryker.NET)

```bash
cd services/TicketService
dotnet tool install -g dotnet-stryker
dotnet stryker --project TicketService.Application.csproj
```
- Target: kill rate ≥ 60% cho state machine class.
- CI optional (run weekly nightly).

### 46.5. Visual regression (FE concern, BE provides stable data)
- Seed data deterministic (fixed UUIDs + dates).
- Endpoint `GET /api/v1/test/fixtures/snapshot-data` (only in non-prod).

---

## 47. Security hardening additional — P1

### 47.1. Password policy
- Minimum length 12 chars (đã có 8 — nâng cấp).
- Password history: không reuse 5 password gần nhất.
- Password expiry: 180 ngày (Admin/Manager), không bắt Customer.
- Force change on first login.

#### Entity update `Account`
- `PasswordChangedAt` (DateTime)
- `MustChangePassword` (bool)

#### Entity `PasswordHistory`
- `Id, AccountId, PasswordHash, CreatedAt`
- Keep last 5 per account.

### 47.2. Concurrent session limit
- Account max 3 active session (3 device).
- Login lần thứ 4 → revoke session cũ nhất.
- Customer mobile + Web simultaneously = 2 session OK.

#### Update `Session` entity (đã có RefreshToken)
- Logic trong `LoginCommandHandler`: count active sessions, if >= 3 → revoke oldest.

### 47.3. IP whitelist cho Admin endpoint
- Config `AdminIpWhitelist` (env var, comma-separated CIDR).
- Middleware `AdminIpRestrictionMiddleware` apply cho `/api/v1/admin/*`.
- Fail returns 403.

### 47.4. CSRF protection
- Cookie-based auth (Web) → need CSRF token.
- JWT Bearer (Mobile) → not needed.
- Implementation: ASP.NET Core built-in `AddAntiforgery`.

### 47.5. Brute force lockout policy refined
- Current LoginAttempt entity tracks attempts.
- Policy:
  - 5 failed in 10 min → lock 15 min.
  - 10 failed in 1 hour → lock 1 hour.
  - 20 failed in 24h → lock 24h, notify Admin.
- Per IP + per account separately.

### 47.6. Audit sensitive actions
Force re-auth (password re-confirm) for:
- Delete account
- Change email
- Change password
- Revoke all sessions
- Admin: delete user, transfer asset

### 47.7. CSP headers (đã có `SecurityHeadersMiddleware`)
Tighten:
```
Content-Security-Policy: default-src 'self'; img-src 'self' data: https:; script-src 'self'; style-src 'self' 'unsafe-inline'
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Strict-Transport-Security: max-age=31536000; includeSubDomains
Referrer-Policy: strict-origin-when-cross-origin
```

### 47.8. Secret rotation
- JWT signing key: rotate every 90d, support 2 keys simultaneously (old + new) for grace period.
- Database password: rotate quarterly (out of scope manual).
- API keys: Admin trigger via §45.2 endpoint.

### 47.9. Dependency scanning (đã có Trivy)
Bổ sung:
- `dotnet list package --vulnerable` weekly trong CI.
- Dependabot rules priority HIGH cho security updates (đã có ví dụ RestSharp PR #45).

---

## 48. AI feedback loop & analytics — P1

### 48.1. Staff feedback on AI predictions
- Khi Staff resolve ticket auto-created từ alert → UI ask:
  - "AI classified này là Failed. Có đúng không?" [Đúng] [Sai - false positive] [Sai - false negative]
  - "SOH AI predict 65%. Thực tế bạn đo được bao nhiêu?" (optional input)

#### Endpoint
```
POST   /api/v1/anomaly-classifications/{id}/feedback
{
  "isCorrect": true,
  "actualClassification": "Failed",
  "actualSohPercent": 62.5,
  "note": "Đúng, BMS module failed"
}
```

### 48.2. AI accuracy reporting
```
GET    /api/v1/ai/feedback-stats?from=&to=
→ Response:
{
  "totalPredictions": 1250,
  "totalFeedback": 320,
  "feedbackRate": 0.256,
  "truePositiveRate": 0.85,
  "falsePositiveRate": 0.10,
  "falseNegativeRate": 0.05,
  "sohMaePercent": 1.8,           // Mean Absolute Error
  "modelVersion": "1.0"
}
```

### 48.3. Export training data
Monthly background job exports labeled data → MinIO bucket `ai-training-data/{year-month}.parquet`:
- Features: sensor readings 30 timestep
- Labels: Staff-confirmed classification + actual SOH
- AI team download để retrain.

### 48.4. A/B testing AI model
- Feature flag `AI_MODEL_VERSION` (1.0 vs 1.1).
- Route X% traffic mới to v1.1, compare accuracy.
- Out of scope chính nhưng nice if time.

### 48.5. Drift detection
- Compare prediction distribution week-over-week.
- Nếu shift > 20% → notify AI team (model có thể drift).
- Background job weekly.

---

## 49. Notification advanced (digest + batching) — P1

### 49.1. Digest email (daily/weekly)

#### Entity update `NotificationPreference`
Thêm:
- `DigestEnabled` (bool default true cho Manager/Admin)
- `DigestFrequency` (enum: Daily=1, Weekly=2, None=3)
- `DigestSendHour` (int, 0-23, default 8 — 8AM local time)

#### Background service
`NotificationDigestBackgroundService` (every hour):
- Tìm user có digest due (theo timezone + send hour).
- Aggregate notification 24h/7d gần nhất.
- Render template `digest-daily.hbs` / `digest-weekly.hbs`.
- Publish `SendEmailRequestedEvent`.

### 49.2. Notification batching
- Khi nhiều alert cùng asset trong 5 phút → gộp 1 push.
- Logic trong `NotificationDispatcher`:
  ```
  Before send push:
  - Check Redis key `notif_batch:{userId}:{assetId}` trong 5 phút gần nhất.
  - Nếu tồn tại → append to batch, không send mới.
  - Nếu không → tạo batch + schedule "flush" sau 30s.
  - Sau 30s → send 1 push "Pin X có {count} cảnh báo mới".
  ```

### 49.3. Snooze notification per user
- User trên Mobile click "Don't notify me for 1h about this asset".
- Backend `POST /api/v1/notification-snooze`:
  ```json
  {
    "scopeType": "asset",
    "scopeId": "...",
    "durationMinutes": 60
  }
  ```
- NotificationDispatcher check snooze trước khi send.

### 49.4. In-app notification grouping
- Mobile/Web list notification → group by type + entity.
- Backend endpoint `GET /api/v1/notifications/grouped`:
  ```json
  {
    "groups": [
      { "key": "ticket-TKT-2605-0001", "title": "Ticket TKT-2605-0001", "count": 5, "latestAt": "...", "items": [...] },
      ...
    ]
  }
  ```

### 49.5. Webhook outbound từ NotificationService
Tách `WebhookDispatcher` thành 1 channel mới (xem §45.1).

---

## 50. Updated sprint backlog impact

> Các section §30–49 thêm khá nhiều việc. Đây là phân bổ lại sprint backlog có cập nhật.

### Sprint impact summary

| Sprint | Original scope | Bổ sung | Tổng effort |
|--------|---------------|---------|-------------|
| Sprint 1 | Stabilize foundations | + ADR setup, Edge case doc | 1.1× |
| Sprint 2 | BatteryService MVP | + **Site entities**, + **AI Bridge client skeleton** | 1.4× — cần thêm 1 dev hoặc kéo dài 3 ngày |
| Sprint 3 | BatteryService anomaly engine | + **AI Hybrid pipeline**, + **AlertSilence + Snooze**, + **Bulk import**, + **QR claim** | 1.6× — cân nhắc tách thành Sprint 3a + 3b |
| Sprint 4 | TicketService foundation only | + **TicketRelation**, + **TicketSubscription**, + **Comment edit/mention** giữ trong backlog, không đưa vào sprint này | 1.0× |
| Sprint 5 | TicketService SLA + workflow integration | + **SLA pause limits**, + auto-create từ Battery anomaly, + MaintenanceLog/comment/attachment | 1.3× |
| Sprint 5B | BatteryService advanced monitoring riêng | + Ambient monitoring, EnvironmentalIncident, Tier 2 sensor health | 1.0× sprint riêng |
| Sprint 6 | NotificationService + KB | + **Notification digest/batching**, + **SSE realtime**, + **Public KB** | 1.5× |
| Sprint 7 | Reports + Gateway + Observability | + **GDPR endpoints**, + **Webhook outbound**, + **API key management** | 1.3× |
| Sprint 8 | Demo prep + polish | + **ADR/DR/Runbook finalize**, + **Chaos test**, + **AI feedback report** | giữ nguyên |

### Re-prioritization recommendation

**Phải có cho capstone demo (MUST):**
1. AI Module integration (§30) — Sprint 2-3
2. Site entity (§31) — Sprint 2
3. Edge case rules (§38) — Sprint 4-5 (lúc implement state machine)
4. SLA pause limits (§33) — Sprint 5
5. BatteryService advanced monitoring (§1 ambient/environmental/tier-2) — Sprint 5B
6. SSE realtime (§34) — Sprint 6
7. ADR + Runbook (§40) — Sprint 7-8

**Nên có nếu kịp (SHOULD):**
1. Ticket relations (§32) — Backlog sau Sprint 5, không đưa vào Sprint 4 foundation
2. QR onboarding (§35) — Sprint 3
3. Comment edit/mention (§36) — Backlog sau Sprint 5, chỉ làm comment cơ bản ở #143
4. Alert silence/snooze (§37) — Sprint 3
5. GDPR endpoints (§39) — Sprint 7
6. AI feedback loop (§48) — Sprint 8

**Có thì tốt, không có thì giữ trong backlog (COULD):**
1. Preventive maintenance (§41)
2. Parts inventory (§42)
3. Public KB (§43)
4. Webhook outbound (§45)
5. Chaos testing (§46.3)
6. Mutation testing (§46.4)

### Updated Definition of Done (DOD)
Thêm vào §18:
- [ ] **ADR cập nhật** cho mọi quyết định kiến trúc lớn.
- [ ] **Edge case rule** từ §38 có test cover.
- [ ] **AI integration** smoke test (BatteryService gọi AI predict thành công).
- [ ] **Realtime SSE** demo được trong scope test.
- [ ] **GDPR export** trả về data đầy đủ cho 1 sample user.
- [ ] **Runbook** cho ít nhất 5 scenario thường gặp.

---

## 51. Tóm tắt cập nhật quan trọng nhất

### So với phiên bản đầu, đây là những thay đổi RIPPLE EFFECT:

1. **Entity count: 17 → 30+**
   - Mới: SohPrediction, AnomalyClassification, Site, AlertSilenceRule, TicketRelation, TicketSubscription, CommentMention, CommentReaction, CommentTemplate, MaintenanceSchedule, Part, PartTransaction, WebhookSubscription, PasswordHistory, AlertAckTimeline, DataExportRequest

2. **Endpoints: 100+ → 150+**

3. **Integration events: 17 → 25+**
   - Mới: `SohRapidDegradationEvent`, `SohWarningEvent`, `SohCriticalEvent`, `SiteAlertAggregatedEvent`, `WebhookEventPublishedEvent`

4. **Background services per service tăng**
   - BatteryService: 4 → 7 (thêm SohPrediction, DeviceOfflineDetection, AlertAckEscalation)
   - TicketService: 4 → 6 (thêm SlaPauseEnforcement, ApprovalTimeout, PreventiveMaintenance)

5. **Migration impact**
   - BatteryService cần migration mới: `AddSiteAndGroup`, `AddSohPredictionTables`, `AddAlertSilenceRule`, `AddClaimCode`
   - TicketService cần: `AddTicketRelations`, `AddTicketSubscriptions`, `AddCommentAdvanced`, `AddSlaPauseLimits`, `AddMaintenanceSchedule`
   - AuthService cần: `AddGdprFields`, `AddPasswordHistory`, `AddSessionLimit`

6. **Docker compose updates**
   - Add `ai-module` service
   - Add `tempo` for tracing

7. **Documentation deliverables tăng**
   - `docs/adrs/` — 15 ADR files
   - `docs/operations/` — DR plan, runbooks, incident response, SLOs
   - `docs/architecture/edge-cases.md`
   - `docs/onboarding/`

8. **Team capacity check**
   - Original effort: 8 sprint với 3 BE dev — realistic
   - With additions P0: 8 sprint với 3 BE dev — tight nhưng doable nếu drop COULD items
   - Recommendation: **MUST items + SHOULD items 50%**, COULD items vào backlog sau capstone

---

---

# Phần VIII — Bổ sung lần 2 (Final completeness)

> Phần này bổ sung sau khi review lần 3 phát hiện 5 nhóm critical còn thiếu: **IoT Gateway, Solar Energy metrics, K8s deployment, App management, Demo prep** — và các gap intra-section.

---

## 52. IoT Gateway & Device Management — P0

> Solar battery context: backend phải **giao tiếp với IoT gateway thực tế** (Raspberry Pi / ESP32 / industrial gateway). Section trước chỉ có 1 endpoint batch ingest — không đủ cho production.

### 52.1. Architecture overview

```
Battery (sensor)
    │
    │ Modbus/CAN bus
    ▼
IoT Gateway (RPi/ESP32)
    │
    │ HTTPS REST (đã chọn — xem ADR-016)
    ▼
BatteryService API
    │
    ├──→ Validate device cert + ApiKey
    ├──→ Validate timestamp (within 5min skew)
    ├──→ Dedup via Idempotency-Key
    ├──→ Insert sensor_readings (TimescaleDB)
    ├──→ Update device.last_seen_at
    └──→ Trigger threshold check
```

### 52.2. New entities

#### `IotDevice`
| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | PK |
| `DeviceCode` | string(64) UNIQUE | "GW-001234" |
| `DeviceType` | enum (Gateway=1, StandaloneSensor=2) | — |
| `Model` | string(100) | "RaspberryPi-4B" / "ESP32-WROOM" |
| `FirmwareVersion` | string(20) | "1.2.3" |
| `MacAddress` | string(17)? | — |
| `SiteId` | Guid? (FK) | Site mà gateway đặt tại |
| `Status` | enum (Provisioning=1, Active=2, Offline=3, Decommissioned=4) | — |
| `ApiKeyId` | Guid (FK) | Link tới API key |
| `LastSeenAt` | DateTime? | Update mỗi heartbeat |
| `LastFirmwareUpdateAt` | DateTime? | — |
| `BatteryAssetIds` | jsonb | Array — devices có thể quản lý nhiều battery |
| `ConfigJson` | jsonb? | Per-device config (polling interval, ngưỡng cảnh báo client-side) |

#### `IotDeviceHeartbeat` (time-series, append-only)
| Field | Type |
|-------|------|
| `Time` | DateTime (hypertable column) |
| `DeviceId` | Guid |
| `Cpu` | decimal(5,2)? |
| `MemoryUsageMb` | int? |
| `DiskFreeMb` | int? |
| `Temperature` | decimal? (gateway chassis temp) |
| `ConnectedSensorCount` | int |
| `LocalQueueDepth` | int (số reading chưa upload) |
| `IpAddress` | string(45)? |
| `SignalStrengthDbm` | int? |

**Retention:** 30 ngày.

#### `IotDeviceCalibration`
| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | — |
| `DeviceId` | Guid | — |
| `SensorMetric` | enum (Voltage=1, Current=2, Temperature=3) | — |
| `OffsetValue` | decimal(8,4) | hiệu chuẩn |
| `ScaleFactor` | decimal(6,4) | default 1.0 |
| `CalibratedAt` | DateTime | — |
| `CalibratedByUserId` | Guid | Staff/Admin |
| `CalibrationStandard` | string? | "Fluke 87V multimeter" |
| `Notes` | string? | — |
| `ValidUntil` | DateTime | Calibration expiry (1 năm default) |

#### `IotFirmwareRelease`
| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | — |
| `Version` | string(20) UNIQUE | "1.3.0" |
| `DeviceModel` | string(100) | Compatible model |
| `Channel` | enum (Stable=1, Beta=2) | — |
| `FileId` | Guid (FK) | FileStorageService — .bin/.img |
| `Sha256` | string(64) | Integrity check |
| `ReleaseNotes` | string? | — |
| `IsRequired` | bool | Force update nếu true |
| `MinimumPreviousVersion` | string? | — |
| `ReleasedAt` | DateTime | — |

#### `IotFirmwareUpdateLog`
| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | — |
| `DeviceId` | Guid | — |
| `FromVersion` | string | — |
| `ToVersion` | string | — |
| `Status` | enum (Pending=1, Downloading=2, Installing=3, Success=4, Failed=5, RolledBack=6) | — |
| `InitiatedAt` | DateTime | — |
| `CompletedAt` | DateTime? | — |
| `ErrorMessage` | string? | — |

### 52.3. Device provisioning flow

```
Step 1: Admin tạo IotDevice + APIKey (scope: sensor.ingest, device.heartbeat)
   POST /api/v1/admin/iot-devices
   → Response: { deviceCode, apiKey, provisioningQrCode }

Step 2: Technician chạy script provision trên gateway hardware
   $ curl -X POST https://api/api/v1/iot-devices/provision \
       -H "X-Api-Key: $KEY" \
       -d '{"deviceCode":"GW-001234","macAddress":"...","model":"RPi-4B","firmwareVersion":"1.0.0"}'

Step 3: Backend validate + activate device, return device-specific config
   → { configJson, ntpServer, syncIntervalSec, supportedSensors, ... }

Step 4: Gateway start sending heartbeat + readings
```

### 52.4. Heartbeat endpoint

```http
POST /api/v1/iot-devices/heartbeat
X-Api-Key: ...
X-Device-Code: GW-001234
{
  "timestamp": "2026-05-12T10:15:30Z",
  "cpu": 35.5,
  "memoryUsageMb": 512,
  "diskFreeMb": 14000,
  "connectedSensorCount": 4,
  "localQueueDepth": 0,
  "signalStrengthDbm": -65
}
```
- Backend: insert IotDeviceHeartbeat + update `IotDevice.LastSeenAt`.
- Frequency: every 60s.

### 52.5. Sensor ingest endpoint (updated)

```http
POST /api/sensor-readings/batch
X-Api-Key: ...
X-Device-Code: GW-001234
Idempotency-Key: <uuid>           # tránh duplicate khi gateway retry
Content-Type: application/json
{
  "deviceTimestamp": "2026-05-12T10:15:30Z",     # NTP-synced gateway time
  "readings": [
    {
      "batteryAssetSerial": "BAT-2026-001",
      "time": "2026-05-12T10:15:30Z",
      "voltage": 12.6, "current": -5.2, "temperature": 35.4, "socPercent": 78.5
    },
    ...
  ]
}
```

**Validation:**
- Reject nếu `deviceTimestamp` skew > 5 phút so với server (gateway clock issue → log + alert).
- Reject nếu reading values vô lý: voltage > 1000V, temperature < -50°C hoặc > 150°C (sensor lỗi).
- Apply calibration offset/scale per device + metric.
- Insert into TimescaleDB batch (single SQL `COPY` cho performance).

### 52.6. Device offline detection

`IotDeviceOfflineDetectionBackgroundService` (every 2 phút):
- Scan devices `Status=Active AND LastSeenAt < now - 5min` → mark `Status=Offline`.
- Publish `IotDeviceWentOfflineEvent` → NotificationService notify Customer + Staff.
- Tạo Alert `DeviceOffline` cho mọi battery gắn với device đó (severity Warning).

### 52.7. OTA firmware update flow

#### Admin upload firmware
```
POST /api/v1/admin/iot-firmware-releases
multipart/form-data:
  version: "1.3.0"
  deviceModel: "RPi-4B"
  channel: stable
  file: firmware.bin
  releaseNotes: "..."
  isRequired: true
```

#### Gateway pull
```
GET /api/v1/iot-devices/firmware-check
X-Device-Code: GW-001234
→ {
    "hasUpdate": true,
    "version": "1.3.0",
    "downloadUrl": "<signed URL>",
    "sha256": "...",
    "isRequired": true,
    "releaseNotes": "..."
  }
```

#### Gateway report progress
```
PUT /api/v1/iot-devices/firmware-update-log/{id}
{ "status": "Installing" }    # → "Success" / "Failed"
```

#### Rollback
- Nếu update fail → gateway revert to previous firmware (stored locally).
- Report `Status=RolledBack`.
- Admin alert.

### 52.8. Calibration management

```
POST   /api/v1/iot-devices/{id}/calibrations              (Staff/Admin)
GET    /api/v1/iot-devices/{id}/calibrations
GET    /api/v1/iot-devices/calibrations-expiring?within=30d   (Manager)
```
- Background service alert Manager khi calibration sắp hết hạn.

### 52.9. Multi-sensor per battery support
Cập nhật `SensorReading` entity:
- Thêm `SensorSourceCode` (string(20)?) — "primary", "redundant", "external-temp".
- 1 battery có thể có 3 readings cùng timestamp (3 sensor riêng).
- Query realtime: chọn "primary" làm display value, redundant để verify.

### 52.10. Protocol decision (ADR-016 mới)
**Decision:** HTTPS REST batch ingest cho v1.
**Lý do:**
- Đơn giản, no special infra.
- Idempotency-Key đã có.
- Polly retry đã có.
- TLS đơn giản hơn MQTT-over-TLS setup.

**Trade-off:**
- Latency cao hơn MQTT (1-2s vs <100ms).
- OK cho monitoring (không phải control-plane).

**Future:** MQTT broker (HiveMQ/EMQX) khi cần latency < 100ms hoặc bidirectional command.

### 52.11. Endpoints summary

```
# Admin
POST   /api/v1/admin/iot-devices                         (provision)
GET    /api/v1/admin/iot-devices?status=&siteId=
GET    /api/v1/admin/iot-devices/{id}
PUT    /api/v1/admin/iot-devices/{id}/config             (push config update)
DELETE /api/v1/admin/iot-devices/{id}                    (decommission)
POST   /api/v1/admin/iot-firmware-releases
GET    /api/v1/admin/iot-firmware-releases

# Device-side (X-Api-Key + X-Device-Code)
POST   /api/v1/iot-devices/provision                     (one-time)
POST   /api/v1/iot-devices/heartbeat
GET    /api/v1/iot-devices/firmware-check
PUT    /api/v1/iot-devices/firmware-update-log/{id}
POST   /api/sensor-readings/batch

# Calibration
POST   /api/v1/iot-devices/{id}/calibrations             (Staff/Admin)
GET    /api/v1/iot-devices/{id}/calibrations
GET    /api/v1/iot-devices/calibrations-expiring         (Manager)

# Monitoring
GET    /api/v1/iot-devices/{id}/heartbeat-history?from=&to=
GET    /api/v1/iot-devices/{id}/uptime-stats
```

### 52.12. Metrics

```
iot_device_heartbeats_total{device_id, status}
iot_devices_online_count gauge
iot_devices_offline_total counter
iot_sensor_readings_ingested_total{device_id}
iot_sensor_readings_rejected_total{reason=clock_drift|sensor_outlier|...}
iot_firmware_updates_total{from_version, to_version, status}
```

### 52.13. Tests bắt buộc
- Provisioning flow end-to-end (gen QR → curl provision → device active)
- Heartbeat → LastSeenAt updated
- Offline detection: stop heartbeat 6 phút → status auto Offline + alert created
- Clock skew rejection
- Sensor outlier rejection
- Calibration offset applied correctly
- Firmware OTA flow with rollback simulation

---

## 53. Solar Energy Business Metrics — P0

> Đây là **giá trị kinh doanh** của solar battery monitoring system mà overall ban đầu thiếu hoàn toàn. Customer/Manager cần thấy "tiết kiệm bao nhiêu kWh, bao nhiêu tiền, bao nhiêu CO2".

### 53.1. Concept

```
Solar panel → Battery (sạc) → Battery (xả) → Tải

Energy tracked:
- Energy charged (kWh) = ∫ V × I dt (when current > 0)
- Energy discharged (kWh) = ∫ V × |I| dt (when current < 0)
- Net energy throughput = charged + discharged
- Round-trip efficiency = discharged / charged × 100%
- Cycle count = floor(cumulative_discharged / nominal_capacity_kwh)
- DOD per cycle = (max_soc - min_soc) per cycle
- Cost saved = discharged_kwh × electricity_rate
- CO2 saved = discharged_kwh × emission_factor_vn (0.6429 kg/kWh — VN grid avg)
```

### 53.2. New entities

#### `EnergySession` (charge/discharge segment)
| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | — |
| `BatteryAssetId` | Guid (FK) | — |
| `SessionType` | enum (Charging=1, Discharging=2, Idle=3) | — |
| `StartedAt` | DateTime | — |
| `EndedAt` | DateTime? | — |
| `StartSocPercent` | decimal(5,2) | — |
| `EndSocPercent` | decimal(5,2)? | — |
| `EnergyKwh` | decimal(10,4) | Integral V×I dt |
| `AvgVoltage` | decimal(6,2) | — |
| `AvgCurrent` | decimal(8,2) | — |
| `PeakPowerKw` | decimal(8,3) | — |
| `DurationMinutes` | int | — |

#### `BatteryCycleLog`
| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | — |
| `BatteryAssetId` | Guid | — |
| `CycleNumber` | int | Lifecycle counter |
| `StartedAt` | DateTime | — |
| `EndedAt` | DateTime | — |
| `EnergyChargedKwh` | decimal | — |
| `EnergyDischargedKwh` | decimal | — |
| `MaxSocPercent` | decimal | — |
| `MinSocPercent` | decimal | — |
| `DepthOfDischarge` | decimal | max - min |
| `RoundTripEfficiency` | decimal | discharged/charged |
| `MaxTemperature` | decimal | — |
| `StressScore` | decimal | Composite — input cho AI predict SOH |

#### `EnergyDailySummary` (aggregate, refresh hourly)
| Field | Type |
|-------|------|
| `Id` | Guid |
| `BatteryAssetId` | Guid |
| `Date` | DateOnly |
| `EnergyChargedKwh` | decimal |
| `EnergyDischargedKwh` | decimal |
| `CycleCountDelta` | int |
| `PeakChargePowerKw` | decimal |
| `PeakDischargePowerKw` | decimal |
| `CostSavedVnd` | decimal | Calculated |
| `Co2SavedKg` | decimal | Calculated |
| `AverageEfficiency` | decimal | — |

#### `SiteEnergySummary` (aggregate per site daily)
Cấu trúc tương tự nhưng aggregate theo site.

### 53.3. Configuration entities

#### `ElectricityRate` (per region/customer)
| Field | Type |
|-------|------|
| `Id` | Guid |
| `Region` | string | "VN-South", "VN-North" |
| `TimeOfUseType` | enum (Peak=1, Normal=2, OffPeak=3) |
| `RateVndPerKwh` | decimal |
| `EffectiveFrom` | DateTime |
| `EffectiveTo` | DateTime? |
| `HourStart`, `HourEnd` | int (0-23) | Peak hour range |

#### `CarbonEmissionFactor`
| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | — |
| `Region` | string | "VN" |
| `KgCo2PerKwh` | decimal | VN grid: 0.6429 (EVN data 2024) |
| `Year` | int | Update annually |

### 53.4. Background services

#### `EnergyCalculationBackgroundService` (every 5 phút)
- Scan sensor_readings new since last run.
- Detect session boundaries (current sign change, hysteresis).
- Insert/update EnergySession.
- Detect cycle completion (DOD threshold) → insert BatteryCycleLog.

#### `EnergyDailyAggregateBackgroundService` (every hour, aggregate previous hours)
- Aggregate EnergySession → EnergyDailySummary.
- Calculate cost saved, CO2 saved.

#### `EnergyCostUpdateBackgroundService` (daily, when rate changes)
- Re-compute saved cost cho summary trong 7 ngày gần (nếu rate đổi).

### 53.5. Endpoints

```
# Customer dashboard
GET    /api/battery-assets/{id}/energy/today
GET    /api/battery-assets/{id}/energy/this-month
GET    /api/battery-assets/{id}/energy/daily?from=&to=
GET    /api/battery-assets/{id}/cycles                # cycle history
GET    /api/battery-assets/{id}/savings               # cost + CO2 cumulative

# Site dashboard (Customer/Manager)
GET    /api/v1/sites/{id}/energy/today
GET    /api/v1/sites/{id}/savings

# Admin config
POST   /api/v1/admin/electricity-rates
GET    /api/v1/admin/electricity-rates
POST   /api/v1/admin/carbon-emission-factors
GET    /api/v1/admin/carbon-emission-factors

# Reports (Manager/Admin)
GET    /api/v1/reports/energy-throughput?from=&to=
GET    /api/v1/reports/cost-savings-summary
GET    /api/v1/reports/carbon-savings-summary
GET    /api/v1/reports/top-assets-by-energy
```

### 53.6. Sample response

`GET /api/battery-assets/{id}/savings`
```json
{
  "isSuccess": true,
  "data": {
    "assetId": "...",
    "since": "2026-01-15T00:00:00Z",
    "lifetimeCycleCount": 245,
    "lifetimeEnergyChargedKwh": 18540.5,
    "lifetimeEnergyDischargedKwh": 17320.2,
    "lifetimeRoundTripEfficiency": 0.934,
    "lifetimeCostSavedVnd": 51_960_600,
    "lifetimeCo2SavedKg": 11_135.2,
    "comparison": {
      "vsAverageAssetSameType": "+12% efficiency",
      "vsLastMonth": "+5% energy"
    },
    "thisMonth": {
      "energyDischargedKwh": 320.5,
      "costSavedVnd": 961_500,
      "co2SavedKg": 206.1
    }
  }
}
```

### 53.7. SOH integration với cycle
- `BatteryCycleLog.StressScore` input cho AI:
  - High DOD (> 80%) → stress cao
  - High temperature trong cycle → stress cao
  - High C-rate (current/capacity) → stress cao
- AI SoH prediction dùng cycle log thay vì raw sensor → more accurate.

### 53.8. Charts cho UI
- **Energy daily** bar chart (charged vs discharged)
- **SOC trend** line chart 30 ngày
- **Cycle count** progression
- **Savings cumulative** area chart
- **Efficiency trend** — early warning khi giảm

### 53.9. Time-of-use recommendation (optional advanced)
- Background service phân tích pattern → gợi ý cho Customer:
  - "Nên sạc trong giờ thấp điểm (22h-4h) — tiết kiệm thêm 15%"
  - "Pin của bạn xả nhiều trong giờ cao điểm — đang tối ưu rồi"
- Endpoint `GET /api/battery-assets/{id}/recommendations`.

### 53.10. Tests
- EnergyCalculation: simulate 1h sensor data → assert kWh đúng (within 1%)
- Cycle detection: simulate full charge-discharge → 1 cycle counted
- Cost calculation: với TOU rate → match expected
- Carbon factor change → re-aggregate triggers

---

## 54. Production Deployment (K8s + Helm) — P1

> Docker compose đủ dev. Production demo nên có K8s nếu muốn show "production-ready".

### 54.1. Decision
- **Local dev:** docker compose (giữ nguyên).
- **Demo / staging:** Kubernetes (k3s / minikube / managed).
- **Helm charts:** một chart umbrella chứa tất cả services.

> **⚠️ Sprint risk warning:** K8s/Helm được đề xuất cho demo "production-ready" nhưng **không xuất hiện trong Sprint 7 hay Sprint 8 backlog**. Nếu Helm charts chưa được test từ Sprint 7, đưa vào Sprint 8 rất rủi ro vì Sprint 8 đã là demo prep. **Khuyến nghị:** thêm task `Deploy staging K8s + smoke test` vào Sprint 7 ngay sau Gateway hardening. Nếu không kịp, **fallback là docker compose** — vẫn đủ cho demo capstone và không ảnh hưởng điểm chức năng.

### 54.2. Cấu trúc deploy folder

```
deploy/
├── helm/
│   ├── umbrella/                        # Parent chart deploy all services
│   │   ├── Chart.yaml
│   │   ├── values.yaml                  # default
│   │   ├── values.dev.yaml
│   │   ├── values.staging.yaml
│   │   ├── values.prod.yaml
│   │   └── templates/
│   │       ├── namespace.yaml
│   │       └── _helpers.tpl
│   ├── auth-service/
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   └── templates/
│   │       ├── deployment.yaml
│   │       ├── service.yaml
│   │       ├── configmap.yaml
│   │       ├── secret.yaml
│   │       ├── hpa.yaml                 # Horizontal Pod Autoscaler
│   │       ├── pdb.yaml                 # Pod Disruption Budget
│   │       ├── networkpolicy.yaml
│   │       ├── serviceaccount.yaml
│   │       ├── servicemonitor.yaml      # Prometheus operator
│   │       └── _helpers.tpl
│   ├── battery-service/
│   ├── ticket-service/
│   ├── notification-service/
│   ├── file-storage-service/
│   ├── api-gateway/
│   │   └── templates/
│   │       ├── ingress.yaml             # gateway-only ingress
│   │       └── (same as above)
│   └── ai-module/
├── k8s-raw/                             # Non-helm manifests (optional)
│   ├── postgres-statefulset.yaml
│   ├── redis-statefulset.yaml
│   ├── rabbitmq-cluster.yaml
│   └── minio-deployment.yaml
├── argocd/                              # GitOps (optional)
│   └── application.yaml
└── scripts/
    ├── deploy-staging.sh
    ├── deploy-prod.sh
    └── rollback.sh
```

### 54.3. Deployment manifest template (sample auth-service)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "auth-service.fullname" . }}
  labels:
    {{- include "auth-service.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicaCount }}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0       # Zero downtime
  selector:
    matchLabels:
      {{- include "auth-service.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "auth-service.selectorLabels" . | nindent 8 }}
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"
    spec:
      serviceAccountName: {{ include "auth-service.serviceAccountName" . }}
      initContainers:
        - name: wait-for-postgres
          image: busybox:1.36
          command: ['sh', '-c', 'until nc -z postgres 5432; do sleep 1; done']
        - name: migrate
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          command: ["dotnet", "AuthService.Api.dll", "migrate"]
          envFrom:
            - secretRef:
                name: {{ include "auth-service.fullname" . }}-secrets
            - configMapRef:
                name: {{ include "auth-service.fullname" . }}-config
      containers:
        - name: app
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          ports:
            - name: http
              containerPort: 8080
              protocol: TCP
            - name: metrics
              containerPort: 8080
          envFrom:
            - secretRef:
                name: {{ include "auth-service.fullname" . }}-secrets
            - configMapRef:
                name: {{ include "auth-service.fullname" . }}-config
          startupProbe:
            httpGet: { path: /health/startup, port: http }
            failureThreshold: 30
            periodSeconds: 5
          livenessProbe:
            httpGet: { path: /health/live, port: http }
            initialDelaySeconds: 30
            periodSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet: { path: /health/ready, port: http }
            initialDelaySeconds: 10
            periodSeconds: 5
            failureThreshold: 3
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 500m
              memory: 512Mi
          securityContext:
            runAsNonRoot: true
            runAsUser: 1000
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
```

### 54.4. Resource sizing per service

| Service | Replicas | CPU req | CPU limit | Memory req | Memory limit |
|---------|----------|---------|-----------|------------|--------------|
| AuthService | 2 | 100m | 500m | 256Mi | 512Mi |
| BatteryService | 2 | 200m | 1000m | 512Mi | 1Gi |
| TicketService | 2 | 200m | 800m | 512Mi | 1Gi |
| NotificationService | 2 | 100m | 500m | 256Mi | 512Mi |
| FileStorageService | 1 | 100m | 500m | 256Mi | 512Mi |
| ApiGateway | 2 | 100m | 500m | 256Mi | 512Mi |
| AI Module | 1 (CPU) / 1 (GPU) | 500m | 2000m | 1Gi | 2Gi |
| Postgres (TimescaleDB) | 1 (PVC) | 500m | 2000m | 1Gi | 4Gi |
| Redis | 1 | 100m | 500m | 256Mi | 512Mi |
| RabbitMQ | 1 (or 3 cluster) | 200m | 1000m | 512Mi | 1Gi |

### 54.5. HPA rules

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: battery-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: battery-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target: { type: Utilization, averageUtilization: 70 }
    - type: Resource
      resource:
        name: memory
        target: { type: Utilization, averageUtilization: 80 }
    - type: Pods
      pods:
        metric: { name: rabbitmq_queue_depth }
        target: { type: AverageValue, averageValue: "500" }
```

### 54.6. PDB (Pod Disruption Budget)

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: { name: battery-service-pdb }
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: battery-service
```

### 54.7. Ingress (gateway only)

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-gateway-ingress
  annotations:
    nginx.ingress.kubernetes.io/rate-limit-rpm: "300"
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: nginx
  tls:
    - hosts: ["api.gsu26se55.com"]
      secretName: api-tls
  rules:
    - host: api.gsu26se55.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api-gateway
                port:
                  number: 80
```

### 54.8. Secrets management

**Local dev:** Đọc `.env` (đã có `EnvFileLoader`).
**K8s staging:** Kubernetes Secrets (sealed-secrets cho commit-safe).
**K8s prod:** External Secrets Operator → AWS Secrets Manager / Azure Key Vault.

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata: { name: auth-service-secrets }
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: auth-service-secrets
  dataFrom:
    - extract:
        key: prod/gsu26se55/auth-service
```

### 54.9. Zero-downtime migration (Expand → Migrate data → Contract)

Pattern khi đổi schema không downtime:

**Phase 1 — Expand (deploy version N+1):**
- Migration add column nullable.
- Code N writes both old + new column.
- Code N+1 reads new column with fallback.
- Deploy N+1.

**Phase 2 — Backfill:**
- Background script populate new column for existing rows.

**Phase 3 — Contract (deploy version N+2):**
- Code N+2 reads + writes new column only.
- Migration drop old column.
- Deploy N+2.

→ Document trong runbook khi cần migration phức tạp.

### 54.10. Deployment scripts

```bash
# deploy/scripts/deploy-staging.sh
#!/bin/bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-staging}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"

helm upgrade --install gsu26se55 ./deploy/helm/umbrella \
    --namespace $NAMESPACE \
    --create-namespace \
    --values ./deploy/helm/umbrella/values.staging.yaml \
    --set global.image.tag=$IMAGE_TAG \
    --atomic \
    --timeout 10m

# Smoke test sau deploy
kubectl rollout status deployment/auth-service -n $NAMESPACE
curl -fsSL https://staging-api.gsu26se55.com/health/ready
```

### 54.11. CI/CD pipeline updates

GitHub Actions step thêm:
```yaml
- name: Build & push Docker images
  run: |
    docker buildx build --platform linux/amd64,linux/arm64 \
      -t ${REGISTRY}/auth-service:${{ github.sha }} \
      --push services/AuthService/src/AuthService.Api

- name: Deploy to staging
  if: github.ref == 'refs/heads/main'
  run: ./deploy/scripts/deploy-staging.sh
  env:
    IMAGE_TAG: ${{ github.sha }}
```

### 54.12. Monitoring stack on K8s
- Prometheus Operator + ServiceMonitor CRD per service.
- Grafana via Helm chart.
- Loki via Helm chart.
- Tempo via Helm chart.
- AlertManager → PagerDuty/Slack webhook.

---

## 55. Mobile/Web App Management — P1

### 55.1. App version compatibility

#### Entity `AppVersion`
| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | — |
| `Platform` | enum (iOS=1, Android=2, Web=3) | — |
| `Version` | string(20) | "1.2.3" |
| `BuildNumber` | int | — |
| `MinSupportedVersion` | string | Server reject nếu app < này |
| `LatestVersion` | string | UI suggest update nếu < này |
| `ForceUpdate` | bool | If true → app blocks usage |
| `ReleaseNotes` | string? | Multi-language JSON |
| `StoreUrl` | string | App Store / Play Store URL |
| `ReleasedAt` | DateTime | — |

#### Endpoint
```
GET /api/v1/app-config?platform=ios&version=1.2.3
→ {
    "compatible": true,
    "shouldUpdate": false,
    "forceUpdate": false,
    "latestVersion": "1.2.5",
    "minSupportedVersion": "1.0.0",
    "releaseNotes": "...",
    "storeUrl": "https://apps.apple.com/..."
  }
```

Mobile call this **on every app launch**. Backend response in < 50ms (cached 5 phút).

### 55.2. Feature flags

#### Entity `FeatureFlag`
| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | — |
| `Key` | string UNIQUE | "ai-prediction-enabled", "new-ticket-flow" |
| `Description` | string? | — |
| `IsEnabled` | bool | Global toggle |
| `EnabledForRoles` | string[] | Specific roles |
| `EnabledForUserIds` | Guid[] | Specific users (beta testing) |
| `EnabledForAppVersionMin` | string? | Only versions >= |
| `RolloutPercent` | int (0-100) | Gradual rollout |

#### Evaluation logic
```csharp
public bool IsEnabled(string flagKey, ICurrentUser user) {
    var flag = await _cache.Get($"flag:{flagKey}");
    if (!flag.IsEnabled) return false;
    if (flag.EnabledForUserIds.Contains(user.Id)) return true;
    if (flag.EnabledForRoles.Any(r => user.Role == r)) {
        if (flag.RolloutPercent < 100) {
            var hash = Hash($"{user.Id}:{flagKey}") % 100;
            return hash < flag.RolloutPercent;
        }
        return true;
    }
    return false;
}
```

#### Endpoints
```
GET    /api/v1/feature-flags                            (Admin all)
PUT    /api/v1/feature-flags/{key}                      (Admin)
GET    /api/v1/feature-flags/my                         (any user — only flags applicable to them)
```

### 55.3. Maintenance broadcast

#### Entity `MaintenanceAnnouncement`
| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | — |
| `Title` | string | "Bảo trì hệ thống 2-4h sáng 15/5" |
| `Body` | string | Markdown |
| `Severity` | enum (Info=1, Warning=2, Critical=3) | — |
| `StartAt` | DateTime | Show banner from |
| `EndAt` | DateTime | Hide banner |
| `MaintenanceWindowStart` | DateTime? | Actual downtime |
| `MaintenanceWindowEnd` | DateTime? | — |
| `AffectedServices` | string[] | "All", "Battery only" |
| `ShowToRoles` | string[] | All roles by default |
| `IsActive` | bool | Admin toggle |

#### Endpoints
```
POST   /api/v1/admin/maintenance-announcements          (Admin)
GET    /api/v1/admin/maintenance-announcements
PUT    /api/v1/admin/maintenance-announcements/{id}
DELETE /api/v1/admin/maintenance-announcements/{id}

GET    /api/v1/maintenance-announcements/active         (any role — get current banner)
```

App display banner on top of screen during active period.

### 55.4. In-app announcement (release notes / promotion)

#### Entity `InAppAnnouncement`
| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | — |
| `Title` | string | — |
| `Body` | string | — |
| `ImageFileId` | Guid? | — |
| `TargetRoles` | string[] | — |
| `StartAt`, `EndAt` | DateTime | Active period |
| `PinAtTop` | bool | — |
| `ActionUrl` | string? | Deep link nếu user click |

#### Endpoints
```
POST   /api/v1/admin/announcements                      (Admin)
GET    /api/v1/announcements/active                     (user — list current)
PUT    /api/v1/announcements/{id}/dismiss               (user — hide from feed)
```

### 55.5. Crash reporting integration

Option A: Sentry SaaS — Mobile/Web tự gửi tới Sentry. BE chỉ cần endpoint xem stats.

Option B: Self-host crash collector:
```
POST   /api/v1/crashes
{
  "platform": "ios",
  "version": "1.2.3",
  "errorType": "TypeError",
  "message": "Cannot read property 'x' of undefined",
  "stackTrace": "...",
  "deviceInfo": { "model": "iPhone15,3", "osVersion": "17.4" },
  "userId": "...",
  "occurredAt": "..."
}

GET    /api/v1/admin/crashes?platform=&version=&errorType=
GET    /api/v1/admin/crashes/stats                      # group by errorType
```

> **Đề xuất:** Option A (Sentry free tier) cho scope capstone.

### 55.6. Analytics events tracking

Mobile/Web gửi user action events:
```
POST   /api/v1/analytics/events
{
  "events": [
    { "name": "view_battery_realtime", "properties": {"assetId":"..."}, "timestamp": "..." },
    { "name": "create_ticket", "properties": {"category":"Charging"}, "timestamp": "..." }
  ]
}
```

Lưu in `AnalyticsEvent` table:
| Field | Type |
|-------|------|
| Time | DateTime (hypertable) |
| UserId | Guid? |
| SessionId | string |
| EventName | string |
| Properties | jsonb |
| Platform | enum |
| AppVersion | string |

Analytics endpoints:
```
GET /api/v1/admin/analytics/event-counts?from=&to=&groupBy=name
GET /api/v1/admin/analytics/funnel?steps=login,view_battery,create_ticket
GET /api/v1/admin/analytics/active-users-daily
```

### 55.7. Push tokens cleanup

Background service `PushTokenCleanupBackgroundService` (weekly):
- Mark token expired if `LastSeenAt < now - 90d`.
- Remove permanently after 180d.

### 55.8. App rating prompt logic (backend coordination)

```
GET /api/v1/users/me/should-prompt-rating
→ { "shouldPrompt": true, "reason": "completed_5_tickets_no_issues" }
```

Backend logic:
- Customer rate ticket ≥ 4 sao 3 lần liên tiếp → eligible.
- Đã prompt < 90d trước → skip.

### 55.9. Mobile-optimized endpoints

Một số endpoint trả về payload nhẹ hơn cho mobile:
```
GET    /api/battery-assets/{id}/realtime-lite        (chỉ V, I, T, SOC — bỏ metadata)
GET    /api/v1/tickets/me/lite                          (preview list, không includes)
```

---

## 56. Demo & Presentation Deliverables — P0

> Capstone không chỉ là code — hội đồng đánh giá cả presentation. Phần này là **deliverable chuẩn bị cho demo day**.

### 56.1. Demo script (`docs/demo/demo-script.md`)

Cấu trúc đề xuất (90 phút demo):

```markdown
# Demo Script — GSU26SE55 Solar Battery Monitor

## Pre-demo setup (5 phút)
- Reset demo data: `./tools/reset-demo.sh`
- Verify: docker compose ps shows all green
- Open browser tabs: Web Admin, Web Manager, Web Staff
- Open phones: Customer A app, Customer B app
- Login mỗi account, tab Grafana ready

## Scene 1 — Admin onboarding (10 phút)
1. Admin login Web
2. Show Audit log (đã có activity từ trước)
3. Create new BatteryType "LiFePO4 24V 200Ah" with threshold config
4. Create Site "Solar Farm Long An"
5. Bulk import 10 batteries from CSV → show import result
6. Generate QR code for asset BAT-DEMO-001
7. **Switch to Customer A phone:** scan QR → asset claimed

## Scene 2 — Realtime monitoring (10 phút)
1. Customer A app: view dashboard, see 1 active battery
2. Switch to chart: voltage/current/temp/SOC realtime
3. Show energy savings: "Đã tiết kiệm 12.5 kWh, 3,750 VND, 2.5kg CO2 tháng này"
4. Run sensor simulator script that emits normal data
5. View Grafana battery health dashboard

## Scene 3 — Critical alert + auto ticket (15 phút)
1. Run `./tools/inject-anomaly.sh BAT-DEMO-001 overheat 75`
2. Within 30s: Customer A phone push notification 🔴
3. AI classifies as "Failed" with 92% confidence
4. Auto-ticket created (P1 Critical)
5. Manager web: queue refreshes (SSE live update)
6. Manager assigns Staff Long with priority P1
7. SLA timer starts (4h countdown banner)
8. Staff Long mobile: push notification "Bạn được giao ticket TKT-2605-0042"

## Scene 4 — Staff workflow (15 phút)
1. Staff opens ticket detail
2. KB suggest: "Overheat troubleshooting article"
3. Staff comments asking Customer for photo
4. Hold ticket: WaitingCustomer → SLA pause
5. Customer A: reply with photo (file upload)
6. SLA resumes
7. Staff resolves with maintenance summary
8. Switch back to Manager: approves ticket

## Scene 5 — Customer rate + reopen (5 phút)
1. Customer rates 5 stars + comment
2. Show ticket CLOSED in activity timeline

## Scene 6 — SLA breach scenario (10 phút) — pre-recorded simulation
1. Show pre-prepared P1 ticket near SLA breach (90% mark)
2. Push warning sent to Staff + Manager
3. Time travel to breach → ESCALATED state, Admin notified
4. Manager reassigns to senior staff

## Scene 7 — Reports & analytics (10 phút)
1. Manager opens reports dashboard
2. SLA compliance per priority
3. CSAT trend
4. Top reopen issues
5. Battery health by type
6. Export PDF report

## Scene 8 — AI feedback loop (5 phút)
1. After Scene 4 resolve → Staff confirms AI prediction was correct
2. Admin opens AI dashboard: 85% accuracy, last retrain 30 days ago
3. Trigger export training data for retrain

## Scene 9 — Operational visibility (5 phút)
1. Open Grafana: business + system dashboards
2. Show traces in Tempo for ticket flow
3. Show maintenance announcement publish flow

## Q&A buffer (15 phút)
```

### 56.2. Demo data reset script

`tools/reset-demo.sh`:
```bash
#!/bin/bash
set -euo pipefail

# Stop services
docker compose --env-file .env.Docker down

# Drop & recreate databases
docker compose --env-file .env.Docker up -d postgres
sleep 5
for db in auth_db file_storage_db battery_db ticket_db notification_db; do
    docker exec solar-postgres psql -U postgres -c "DROP DATABASE IF EXISTS $db; CREATE DATABASE $db;"
done

# Bring up all services
docker compose --env-file .env.Docker up -d

# Wait for migrations
sleep 30

# Run seed script
./tools/seed.sh

# Inject demo scenarios (pre-prepared tickets in various states)
./tools/seed-demo-scenarios.sh

echo "Demo environment ready ✅"
```

### 56.3. Demo scenarios pre-prepared

`tools/seed-demo-scenarios.sh` creates:
- 3 tickets in different states (OPEN, IN_PROGRESS, RESOLVED awaiting approval)
- 1 ticket near SLA breach (90% mark) for breach demo
- 1 ticket already breached + escalated (for showing audit)
- 1 ticket reopened (showing BR-06/BR-07 flow)
- 7 days of sensor history with 2 pre-injected anomalies
- 50 audit log entries
- 5 sample KB articles published
- 10 sample notifications across roles

### 56.4. Demo helper scripts

```bash
# tools/inject-anomaly.sh — push abnormal sensor reading
./tools/inject-anomaly.sh <asset-serial> <anomaly-type> <value>

# tools/fast-forward-sla.sh — simulate time skip for SLA breach demo
./tools/fast-forward-sla.sh <ticket-id> <minutes>

# tools/trigger-incident.sh — declare incident across multiple tickets
./tools/trigger-incident.sh
```

### 56.5. Sample data realistic

Seed dùng tên thật Việt Nam:
- Customer: Nguyễn Văn An, Trần Thị Bình, Lê Minh Châu, ...
- Staff: Phạm Hữu Long, Hoàng Thị Mai, ...
- Manager: Đỗ Quốc Tuấn
- Asset locations: "Solar Farm Long An", "Trang trại Bình Thuận"
- Realistic timestamps spread over 3 tháng

### 56.6. Architecture poster

`docs/demo/architecture-poster.pdf` (A1 print):
- System overview diagram (4 microservices + AI module + clients)
- Tech stack icons
- Key metrics: 30+ entities, 150+ endpoints, 25+ events, 80% coverage
- Sponsor logos / team photo

Source file: `docs/demo/architecture-poster.drawio` (commit + export PDF on each major update).

### 56.7. Demo video (5-10 phút intro)

`docs/demo/intro-video.md` — script:
- 30s: problem statement (solar battery monitoring nightmare)
- 60s: solution overview
- 3 phút: feature highlights with screen recording
- 60s: technical architecture
- 30s: team intro + GitHub link

Use **OBS Studio** for recording, host on YouTube unlisted.

### 56.8. Postman collection

`docs/api/postman-collection.json`:
- All 150+ endpoints grouped by service
- Environment file with `{{baseUrl}}, {{authToken}}, {{customerId}}, ...`
- Pre-request script auto-refresh token
- Example responses saved

```bash
# Generate from OpenAPI
openapi2postmanv2 -s docs/api/openapi.json -o docs/api/postman-collection.json
```

### 56.9. API documentation hosting

- Swagger UI aggregated at gateway: `https://api.gsu26se55.com/swagger`
- Redoc alternative: `https://api.gsu26se55.com/redoc`
- Or host on GitHub Pages: `https://gsu26se55.github.io/api-docs/`

### 56.10. Q&A preparation document

`docs/demo/qa-preparation.md`:
30+ câu hỏi hội đồng thường hỏi + câu trả lời chuẩn bị, ví dụ:

```markdown
## Q1: Tại sao chọn microservices thay vì monolith?
A: ...

## Q2: SLA pause loophole — Staff có thể gaming không?
A: Đã có guard BR-04-Extended (xem §33). Max pause minutes per priority, ...

## Q3: AI fail thì sao?
A: Hybrid pipeline (xem §30.2) — threshold detector vẫn chạy độc lập, ...

## Q4: Bảo mật đường truyền IoT gateway → backend?
A: TLS 1.3, API key per device, rotation, ...

## Q5: Scale 10,000 batteries thì sao?
A: HPA (§54.5), TimescaleDB hypertable partition by time, ...

## Q6: Tại sao TimescaleDB thay vì InfluxDB?
A: ADR-006 — ...

## Q7: Tại sao Outbox?
A: ADR-004 — ...

(continue 30+ questions)
```

### 56.11. Test demo dry-run

- 1 tuần trước demo: full dry-run với mock hội đồng (mentor).
- Time all scenes.
- Identify weak transitions.
- Backup recording if live demo fails.

### 56.12. Tech setup checklist demo day

- [ ] Laptop có power + adapter
- [ ] HDMI/USB-C dongle
- [ ] Spare laptop pre-loaded same env
- [ ] Internet backup: 4G hotspot
- [ ] Local-first mode (docker compose, không cần internet)
- [ ] Backup video recorded
- [ ] Mobile phones charged 100%
- [ ] Test projector resolution
- [ ] Browser bookmarks pre-set
- [ ] Demo data seeded
- [ ] Reset script tested

### 56.13. Slide deck (PowerPoint/Google Slides)

Max 20 slides:
1. Title + team
2. Problem
3. Stakeholders (4 role personas)
4. Solution overview
5. Architecture diagram
6. Tech stack
7. Key features 1: AI integration
8. Key features 2: ITIL ticket lifecycle
9. Key features 3: Real-time alert + SLA
10. Demo flow overview
11. (Live demo placeholder)
12. Technical highlights: state machine
13. Technical highlights: TimescaleDB + AI
14. Technical highlights: Observability
15. Test coverage + quality gates
16. Sprint timeline
17. Challenges + how solved
18. Future work
19. Team contributions
20. Q&A

---

## 57. AI advanced — deployment, retrain, batching — P1

### 57.1. Model deployment CI/CD

`ai-module/.github/workflows/deploy-model.yml`:
- Trigger: manual / on push to `models/v*` tag
- Step 1: Run validation tests (MAE < 2%, F1 > 0.80).
- Step 2: Build container with new weights.
- Step 3: Deploy to staging.
- Step 4: Canary test (5% traffic) for 24h.
- Step 5: Promote to prod.
- Rollback: keep previous 2 versions, manual rollback.

### 57.2. Retraining trigger criteria

Auto-trigger retrain job when:
- Drift detected: prediction distribution shift > 20% (KL divergence) week-over-week.
- Accuracy degradation: feedback rate true_positive < 75% over 100 samples.
- Schedule: every 3 months minimum.

Endpoint: `POST /api/v1/admin/ai/retrain-trigger` (Admin manual).

### 57.3. Inference batching

```python
# FastAPI batch endpoint
@router.post("/predict/soh/batch")
async def predict_batch(req: BatchPredictRequest):
    """
    Input: list of {asset_id, readings: [...]}
    Output: list of {asset_id, soh_percent, confidence}
    Batch up to 32 items → single GPU forward pass
    """
```

Backend BatteryService modify `SohPredictionBackgroundService`:
- Collect up to 32 pending predictions trong 100ms window → single batch call.
- Latency tăng nhẹ but throughput 32× higher.

### 57.4. Model versioning storage

```
ai-module/models/
├── weights/
│   ├── current → symlink to v1.2/
│   ├── v1.0/
│   │   ├── scaler.pkl
│   │   ├── soh_lstm.pth
│   │   └── isolation_forest.pkl
│   ├── v1.1/
│   └── v1.2/
└── metadata/
    └── versions.json   # registry with metrics, training data, hash
```

### 57.5. Multi-replica AI scaling

K8s HPA cho AI module:
- Scale based on `ai_inference_queue_depth` metric.
- Scale 1 → 5 replicas dynamically.
- Shared model loaded in memory per replica (read-only).

### 57.6. Drift detection background job

`AiDriftDetectionBackgroundService` weekly:
- Compare predicted distribution last 7 days vs previous 7 days.
- KL divergence calc.
- If > 0.2 → publish `AiModelDriftDetectedEvent` → notify AI team.

### 57.7. A/B test framework

Feature flag `AI_MODEL_VERSION_VARIANT`:
- 90% traffic → v1.1 (control)
- 10% traffic → v1.2 (variant)
- Compare metrics 2 weeks.
- Promote winner.

### 57.8. Endpoints
```
GET    /api/v1/admin/ai/models                          (list versions + metrics)
PUT    /api/v1/admin/ai/models/{version}/promote        (Admin)
POST   /api/v1/admin/ai/models/{version}/rollback
POST   /api/v1/admin/ai/retrain-trigger
GET    /api/v1/admin/ai/drift-status
GET    /api/v1/admin/ai/inference-stats?from=&to=
```

---

## 58. Edge cases extension (EC-21..EC-30) — P0

Bổ sung 10 edge cases vào §38 matrix:

| # | Edge case | Rule giải quyết | Implementation |
|---|-----------|----------------|----------------|
| EC-21 | Concurrent IoT data ingest từ cùng device (request gửi 2 lần do retry) | Idempotency-Key dedup | `IdempotencyKeyMiddleware` đã có |
| EC-22 | Customer dưới 18 (children data protection) | Block registration; require legal guardian | Validation `RegisterCommand`: nếu `birthDate < 18 years ago` → reject |
| EC-23 | Cross-timezone Customer (Mỹ) vs Staff (VN) | Tất cả timestamp lưu UTC, FE convert theo `AccountProfile.TimeZone` | Đã có TimeZone in NotificationPreference, đồng bộ thêm vào AccountProfile |
| EC-24 | Device clock drift > 5 phút | Reject reading + tăng `IotDevice.ClockDriftIncidentCount` | Validation trong sensor batch ingest |
| EC-25 | Sensor reading vô lý (V=1200V) | Reject + log `SensorOutlier` event + auto-disable device sau N outlier | Validation + threshold per metric |
| EC-26 | Customer sở hữu 1000+ asset (enterprise) | Pagination mandatory + cache aggressively | Query handler always paginate, max 100 |
| EC-27 | Ticket spam (1 customer tạo 50 ticket/ngày) | Rate limit per user 10 ticket/day, alert Manager | RateLimiter middleware |
| EC-28 | Attachment có malware | Virus scan (ClamAV integration) trước khi store | FileStorageService middleware |
| EC-29 | Customer thay đổi email khi có active sessions | Revoke all sessions sau email change + require re-login | `ChangeEmailCommandHandler` revoke RT_* keys |
| EC-30 | Daylight Saving Time transition (mặc dù VN không DST) | UTC mọi nơi, FE convert | Convention enforced |

---

## 59. GDPR + security additional — P1

### 59.1. Children's data protection
- Đăng ký yêu cầu `birthDate`.
- < 18 tuổi → require email parent → parent consent qua link.
- `Account.IsMinor` (bool) → giới hạn data collected, no marketing email.

### 59.2. Cookie consent banner (BE provides config)
```
GET /api/v1/legal/cookie-consent-config
→ {
    "categories": [
      {"key":"essential","name":"Thiết yếu","required":true},
      {"key":"analytics","name":"Phân tích","required":false},
      {"key":"marketing","name":"Marketing","required":false}
    ],
    "privacyPolicyUrl": "...",
    "lastUpdated": "..."
  }

POST /api/v1/auth/me/cookie-consent
{ "essential": true, "analytics": true, "marketing": false }
```

### 59.3. Privacy Impact Assessment (PIA)
`docs/legal/privacy-impact-assessment.md`:
- Data types collected per role
- Legal basis (consent, contract, legitimate interest)
- Data flow diagram
- Risks identified + mitigations
- Reviewed annually

### 59.4. Data Processing Agreement (DPA)
`docs/legal/data-processing-agreements/`:
- Expo (push notification) — sub-processor
- SendGrid / Mailgun (email) — sub-processor
- AWS / Azure (hosting) — sub-processor
- Each has signed DPA template.

### 59.5. Cross-border data transfer
- Vietnam: data subject to local regulations.
- If hosting outside VN → SCC (Standard Contractual Clauses) or equivalent.
- Document in PIA.

### 59.6. WAF rules
Application-level WAF (since Cloudflare costs):
```csharp
// Middleware WafMiddleware:
- Block requests với SQL injection pattern: regex `(?i)(union\s+select|drop\s+table|--\s|;\s*--)`
- Block XSS pattern: regex `<script|onerror=|javascript:`
- Block path traversal: `\.\./`
- Block null byte: `%00`
- Log + return 400 Bad Request
```

### 59.7. DDoS protection minimal
- ApiGateway rate limit per IP (đã có §10.2).
- IP block list cho IPs hit rate limit > 5 times in 1h.
- Cloudflare Free tier for prod (HTTPS proxy → DDoS mitigation).

### 59.8. Security incident response playbook
`docs/security/incident-response.md`:
1. **Detect** — alert from monitoring.
2. **Contain** — isolate affected service, revoke compromised credentials.
3. **Eradicate** — patch vulnerability.
4. **Recover** — restore from backup, validate.
5. **Lessons learned** — postmortem within 7 days.
6. **Notify** — affected users within 72h (GDPR), regulator if required.

### 59.9. Bug bounty / responsible disclosure
`SECURITY.md` in repo root:
- Email security@gsu26se55.com for vulnerability reports.
- 90-day disclosure timeline.
- Hall of fame for valid reports.
- No legal action for good-faith research.

### 59.10. Penetration test schedule
- Sprint 8: internal pen test (team member from different role).
- Post-launch (if production): hire external pen test firm annually.

---

## 60. Internal admin tools — P2

### 60.1. User impersonation (debug only)

#### Flow
- Admin opens user detail in admin panel.
- Click "Impersonate" → generates short-lived (15 min) JWT with `impersonatedBy` claim.
- Admin uses this token to debug user issue.
- All actions logged with both original Admin + impersonated user.

#### Endpoint
```
POST   /api/v1/admin/users/{id}/impersonate            (Admin only)
→ { "token": "...", "expiresAt": "...", "warning": "All actions audited" }

GET    /api/v1/admin/impersonation-sessions             (list active)
POST   /api/v1/admin/impersonation-sessions/{id}/end
```

#### Audit
- Entity `ImpersonationSession`: `Id, AdminUserId, ImpersonatedUserId, StartedAt, EndedAt, Reason, ActionsCount`
- Every action while impersonating → audit log with `Impersonator: <adminId>`.

### 60.2. Feature flag management UI endpoints
Đã có §55.2. Admin UI:
- List all flags + status.
- Toggle on/off.
- Set rollout percent slider.
- Add/remove user from allowlist.

### 60.3. Database read-only console (very limited)

```
POST   /api/v1/admin/db-query                           (Admin — heavily restricted)
{ "service": "battery", "query": "SELECT COUNT(*) FROM battery_assets WHERE..." }
```
**Safeguards:**
- Whitelist tables (no `users.password_hash`).
- Block keywords: UPDATE/DELETE/INSERT/DROP/ALTER.
- Read-only DB user.
- Audit every query.
- Timeout 10s.
- Result max 1000 rows.

> Cẩn thận! Rủi ro cao — chỉ implement nếu có time + good test.

### 60.4. Background job monitor

Endpoint trả status các background services:
```
GET /api/v1/admin/background-jobs
→ [
    {
      "name": "OutboxRelayBackgroundService",
      "service": "BatteryService",
      "lastRunAt": "...",
      "lastRunDurationMs": 234,
      "status": "Running",
      "queueDepth": 12,
      "successCount24h": 1245,
      "failureCount24h": 3
    },
    ...
  ]
```

### 60.5. Cache management

```
GET    /api/v1/admin/cache/stats                        (hit rate, key count)
DELETE /api/v1/admin/cache/keys?pattern=user:*          (Admin invalidate)
```

### 60.6. Session viewer

```
GET    /api/v1/admin/sessions?userId=&active=true
POST   /api/v1/admin/sessions/{id}/revoke
POST   /api/v1/admin/users/{id}/revoke-all-sessions     (force logout)
```

### 60.7. System config UI (dynamic config)

```
GET    /api/v1/admin/system-config
PUT    /api/v1/admin/system-config/{key}
```

Editable runtime config:
- `sla_warning_threshold_percent` (default 80)
- `alert_dedup_window_minutes` (default 30)
- `sensor_reading_retention_days` (default 90)
- `max_concurrent_sessions_per_user` (default 3)

Stored in Redis + DB, hot-reload across services.

---

## 61. Search functionality — P1

### 61.1. Strategy
- **Phase 1 (capstone scope):** Postgres `tsvector` full-text search.
- **Phase 2 (future):** Elasticsearch if scale demands.

### 61.2. Searchable entities

#### Tickets
```sql
ALTER TABLE tickets ADD COLUMN search_vector tsvector;
CREATE INDEX idx_tickets_search ON tickets USING GIN(search_vector);

-- Trigger to update
CREATE FUNCTION tickets_search_trigger() RETURNS trigger AS $$
BEGIN
  NEW.search_vector :=
    setweight(to_tsvector('simple', coalesce(NEW.code, '')), 'A') ||
    setweight(to_tsvector('simple', coalesce(NEW.title, '')), 'B') ||
    setweight(to_tsvector('simple', coalesce(NEW.description, '')), 'C');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

#### KB Articles, Battery Assets (serial), Comments — similar pattern.

### 61.3. Search endpoints

```
GET /api/v1/search?q=overheat&types=tickets,kb&from=&to=
→ {
    "results": [
      { "type": "ticket", "id": "...", "code": "TKT-2605-0042", "title": "Overheat alert", "highlight": "...<b>overheat</b>...", "score": 0.85 },
      { "type": "kb", "id": "...", "title": "Overheat troubleshooting", ... }
    ],
    "facets": {
      "byType": { "tickets": 15, "kb": 3 },
      "byPriority": { "P1": 5, "P2": 7, "P3": 3 }
    },
    "took": 45
  }
```

### 61.4. Search-as-you-type (typeahead)
```
GET /api/v1/search/suggest?q=over
→ ["overheat", "overvoltage", "over capacity"]
```

### 61.5. Saved searches
Entity `SavedSearch`:
- `Id, UserId, Name, Query, Filters (jsonb), CreatedAt, LastUsedAt`

```
POST   /api/v1/saved-searches
GET    /api/v1/saved-searches/me
DELETE /api/v1/saved-searches/{id}
```

### 61.6. Search analytics

Log search queries (anonymized):
- Track common queries → identify content gap (lots of "battery swap" search but no article → write one).
- Track zero-result queries → improve KB.

```
GET /api/v1/admin/search-analytics/top-queries?from=&to=
GET /api/v1/admin/search-analytics/zero-result-queries
```

---

## 62. Media pipeline + accessibility — P2

### 62.0. File metadata foundation

FileStorageService không nên chỉ trả raw `objectKey`. Các service nghiệp vụ phải tham chiếu file bằng `fileId` ổn định.

#### Entity `UploadedFile`
| Field | Type | Note |
|-------|------|------|
| `Id` | Guid | `fileId` trả về cho Auth/Ticket/MaintenanceLog |
| `BucketName` | string(100) | MinIO/S3 bucket |
| `ObjectKey` | string(500) | đường dẫn object storage, internal detail |
| `OriginalFileName` | string(255) | tên file client upload |
| `ContentType` | string(100) | whitelist theo purpose |
| `SizeBytes` | long | validate max size |
| `Purpose` | enum/string | `Avatar`, `TicketAttachment`, `MaintenancePhoto`, `KbImage`, `Firmware` |
| `UploadedByUserId` | Guid? | null nếu system/internal |
| `Status` | enum | Uploaded=1, Processing=2, Ready=3, Quarantined=4, Deleted=5 |
| `ChecksumSha256` | string(64)? | integrity/dedup sau này |
| `CreatedAt`, `DeletedAt` | DateTime? | audit + soft delete |

Upload response chuẩn:
```json
{
  "isSuccess": true,
  "statusCode": 201,
  "message": "Upload file thành công.",
  "data": {
    "fileId": "6c9f6e5d-bf26-49e0-a2f4-7e1d2e3a5c90",
    "objectKey": "avatars/6c9f6e5dbf2649e0a2f47e1d2e3a5c90.png",
    "fileName": "avatar.png",
    "contentType": "image/png",
    "sizeBytes": 123456,
    "purpose": "Avatar",
    "status": "Ready",
    "publicUrl": null
  },
  "listErrors": []
}
```

`objectKey` vẫn có thể trả cho debug/backward compatibility, nhưng Auth/Ticket/Battery không được lưu `objectKey` làm foreign reference. Các service chỉ lưu `fileId`.

### 62.1. Image upload pipeline

Khi user upload ảnh attachment:
```
Client upload → FileStorageService
              │
              ▼
         Original stored (private) + UploadedFile metadata created
              │
              ▼
    Background job ImageProcessingJob:
              │
              ├─→ Strip EXIF (privacy — remove GPS, device info)
              ├─→ Resize:
              │     • Thumbnail 200×200
              │     • Medium 800×800
              │     • Large 1920×max
              ├─→ Optimize (jpeg quality 80, webp alternative)
              └─→ Virus scan (ClamAV)
                    │
                    └─→ If clean → mark Status=Ready
                        If infected → quarantine + notify Admin + delete original
```

### 62.2. Endpoints
```
POST   /api/v1/files/upload                             (multipart, max 10MB)
→ { "fileId": "...", "objectKey": "...", "status": "Processing|Ready" }

GET    /api/v1/files/{id}?variant=thumbnail|medium|large|original
GET    /api/v1/files/{id}/metadata
GET    /api/v1/files/{id}/presigned-url?variant=original
```

### 62.3. Content moderation (optional)
- ML-based image moderation (offensive content detection).
- Out of scope cho capstone, note for future.

### 62.4. Accessibility (a11y) backend support

#### Alt text for images
- `TicketAttachment.AltText` field (Customer/Staff cung cấp khi upload).
- API response includes alt text.

#### Color blind friendly
- Status enum response includes both `code` (Critical/Warning/Info) and `colorHint` (`red`, `orange`, `blue`) — FE chọn cách hiển thị.

#### Screen reader metadata
- API responses cho list view có `ariaLabel` field for important rows.

---

## 63. Customer success metrics — P2

### 63.1. NPS survey

Trigger:
- 30 ngày sau registration đầu tiên.
- Sau 5 ticket close với rating ≥ 4.

```
GET /api/v1/users/me/nps-eligibility
POST /api/v1/users/me/nps-response
{
  "score": 9,                  // 0-10
  "comment": "Rất tốt..."
}
```

NPS score = % Promoters (9-10) − % Detractors (0-6).

### 63.2. Customer health score

Computed daily per Customer:
- Asset count active
- Last login recency
- Ticket reopen rate
- Average rating
- Notification engagement
- = Score 0-100

```
GET /api/v1/admin/customers/{id}/health-score
GET /api/v1/admin/customers/health-scores?segment=at-risk
```

### 63.3. Churn prediction (advanced)
- Customer health < 30 for 30 days → "at risk".
- Trigger outreach campaign.

### 63.4. Feature adoption tracking
- Track per feature: % active users have used in last 30d.
- Endpoint `GET /api/v1/admin/analytics/feature-adoption`.

### 63.5. User journey funnel

```
Registration → Activate Account → Claim First Asset → View Dashboard → Create First Ticket
   100%       →     80%          →       65%          →     60%        →       30%
```

Identify drop-off → optimize onboarding.

---

## 64. Status page + maintenance broadcast — P1

### 64.1. Public status page

`status.gsu26se55.com` — accessible without login.

Show:
- Overall status (Operational / Degraded / Down)
- Per-service status:
  - AuthService ✅
  - BatteryService ✅
  - TicketService ⚠️ Degraded (high latency)
  - NotificationService ✅
  - AI Module ❌ Outage
- Active incidents (with timeline)
- Past incidents (last 30 days)
- Uptime % (last 90 days)
- Scheduled maintenance announcements

### 64.2. Implementation
- Static site (Hugo / Next.js export) hosted on GitHub Pages / Vercel.
- Backend endpoint `GET /api/v1/public/status` returns JSON, status page polls every 1 phút.
- Or use **Statuspage.io** free tier (recommended).

### 64.3. Incident lifecycle on status page
- Admin manually creates incident on status page (linked from internal IncidentDeclared event).
- Updates posted as incident progresses.
- Resolution + postmortem link.

### 64.4. Subscribers
- Customer/Staff subscribe email/SMS for status updates.
- `POST /api/v1/public/status/subscribe { email }`.

---

## 65. Documentation auto-generation — P2

### 65.1. API docs from OpenAPI
- Each service exports `swagger.json` on build.
- ApiGateway aggregates.
- Redoc UI hosted public.

### 65.2. ERD from EF Core migrations
```bash
dotnet tool install -g dotnet-erd
dotnet erd --project services/BatteryService/src/BatteryService.Infrastructure --output docs/architecture/battery-erd.svg
```

Run in CI on each migration change, commit SVG.

### 65.3. Architecture diagrams as code (Mermaid/PlantUML)
`docs/architecture/`:
- `microservices.mmd` (Mermaid)
- `event-flow.mmd`
- `state-machine-ticket.mmd`
- `sequence-ticket-create.mmd`

Auto-render to SVG via GitHub Actions on push.

### 65.4. Code coverage report hosted
- CI publishes coverage report to GitHub Pages.
- Per-service breakdown.
- Trend chart over time.

### 65.5. Changelog auto-gen

`tools/release-notes.sh`:
- Parse commits since last tag.
- Group by type: feat/fix/refactor/docs/test.
- Output `CHANGELOG.md`.

---

## 66. Final completeness checklist

> Tổng hợp tất cả các thứ phải xong cho **production-ready demo capstone**.

### 66.1. Code completeness
- [x] AuthService (DONE)
- [x] AuthService profile/staff extension + uploaded/Google avatar source flow
- [ ] BatteryService — entity + CQRS + background jobs + AI bridge + sites + IoT
- [ ] TicketService — entity + state machine + SLA + relationships + escalation
- [ ] NotificationService — consumers + Expo + email + SMS + SSE + digest
- [ ] KnowledgeBase module + public articles
- [ ] AI Module integration (BatteryService → AI HTTP client)
- [x] FileStorageService metadata foundation (`UploadedFile`, `fileId` APIs)
- [ ] FileStorageService — media pipeline (resize, EXIF strip, virus scan)
- [ ] Reports endpoints (Ticket + Battery)
- [ ] Search functionality
- [ ] Energy metrics calculation + dashboard
- [ ] App config + feature flags + maintenance announcements
- [ ] Status page integration
- [ ] Admin tools (impersonation, feature flag, system config)

### 66.2. Database
- [x] AuthService migration `AddAccountProfileExtensionTables` created
- [x] FileStorageService migration `AddUploadedFileMetadata` created
- [x] Docker Compose logical DB split documented/configured (`auth_db`, `file_storage_db`)
- [ ] All migrations tested rollback
- [ ] Seed data realistic + 3-month history
- [ ] TimescaleDB hypertable + retention + continuous aggregate
- [ ] Indexes verified per query plan
- [ ] Zero-downtime migration pattern documented

### 66.3. Infrastructure
- [x] Docker Compose config validated with `--env-file .env.Docker`
- [x] `postgres-init` idempotent service database creation added
- [ ] Docker compose all green start < 60s
- [ ] K8s Helm charts per service
- [ ] CI/CD: build + test + lint + scan + deploy
- [ ] Secrets management
- [ ] Monitoring (Prometheus + Grafana + Loki + Tempo)
- [ ] AlertManager rules
- [ ] AI Module deployed + health check

### 66.4. Quality
- [ ] Test coverage ≥ 80% all services
- [ ] State machine matrix tested
- [ ] Contract tests producer/consumer
- [ ] Load test results documented
- [ ] Smoke test suite < 2 phút
- [ ] Pen test internal done

### 66.5. Documentation
- [ ] OpenAPI / Swagger aggregated at gateway
- [ ] Postman collection
- [ ] README per service
- [ ] CLAUDE.md updated
- [ ] 15 ADRs documented
- [ ] DR plan + 7 runbooks
- [ ] PIA + DPA + cookie config
- [ ] SECURITY.md
- [ ] CHANGELOG.md auto-generated
- [ ] ERD diagrams committed
- [ ] Edge cases matrix (30+)

### 66.6. Demo deliverables
- [ ] Demo script (9 scenes, 90 phút)
- [ ] Reset + inject anomaly + fast-forward scripts
- [ ] Pre-prepared demo scenarios (5+)
- [ ] Architecture poster A1 print
- [ ] Intro video 5-10 phút
- [ ] Slide deck 20 slides
- [ ] Q&A prep doc 30+ questions
- [ ] Backup recording
- [ ] Dry-run with mentor done
- [ ] Tech setup checklist verified

### 66.7. Business value showcase
- [ ] Customer dashboard with energy + cost + CO2 savings
- [ ] AI prediction visible + explainable (confidence + classification)
- [ ] SLA compliance reports
- [ ] CSAT score
- [ ] Top assets / top issues / top staff reports

### 66.8. "Bonus points" academic
- [ ] AI feedback loop demonstrable
- [ ] Drift detection working
- [ ] Real IoT device sending data (even if RPi mock)
- [ ] Carbon savings number visible
- [ ] GDPR export demo
- [ ] Postmortem template ready (if incident happens during demo, recover gracefully)

---

## 67. Tóm tắt final — file đầy đủ chưa?

### Đánh giá lần 3 (sau §52-66)

| Khía cạnh | Coverage trước | Coverage giờ |
|-----------|---------------|--------------|
| Business flow & domain | 9.5/10 | **10/10** |
| Microservices architecture | 9.5/10 | **10/10** |
| AI integration | 9/10 | **10/10** (deployment + retrain) |
| Cross-cutting | 9/10 | **10/10** |
| Security & Compliance | 8/10 | **9.5/10** |
| Testing strategy | 8.5/10 | **9.5/10** |
| IoT/Device management | 4/10 | **10/10** ✅ |
| Solar-specific metrics | 2/10 | **10/10** ✅ |
| Production deployment | 5/10 | **9/10** ✅ |
| Mobile/Web app mgmt | 5/10 | **9/10** ✅ |
| Demo/Presentation | 3/10 | **10/10** ✅ |

### Stats final

| Metric | Value |
|--------|-------|
| Total sections | **66** |
| Total entities defined | **50+** |
| Total commands | **90+** |
| Total queries | **60+** |
| Total integration events | **30+** |
| Total endpoints | **220+** |
| Total background services | **25+** |
| ADRs documented | **16** (+ ADR-016 IoT protocol) |
| Runbooks | **10+** |
| Edge case rules | **30** |
| Demo scenes scripted | **9** |
| Performance SLAs | per endpoint |
| Sprint backlog | **8 sprint detailed** |

---

**End of OVERALL.md (Final Complete Edition)**

**Document lifecycle:**
- v1 (2026-05-12 morning): §0-29 initial roadmap
- v2 (2026-05-12 afternoon): §30-51 gap analysis addendum
- v3 (2026-05-12 evening): §52-67 final completeness — IoT, solar metrics, K8s, app mgmt, demo prep, intra-section additions

**Maintained by:** Leader. Cập nhật mỗi cuối sprint khi `/kltn-sprint` chạy.
**Last major update:** 2026-05-12 — Final completeness edition (§52-67).

**Recommended reading order for newcomer:**
1. §0-0bis (context — 10 phút)
2. §1, §2, §3 (3 main services — 30 phút)
3. §30, §52, §53 (AI, IoT, energy — 20 phút)
4. §38 + §58 (edge cases matrix — 10 phút)
5. §17 (sprint backlog — 10 phút)
6. §56 (demo prep — when nearing deadline)

**Total reading time end-to-end:** ~3-4 hours for complete understanding.
