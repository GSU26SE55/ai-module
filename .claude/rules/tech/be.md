# Backend Rules — ASP.NET Core Microservices

## 1. Clean Architecture (4 layers)

```
ServiceName/
├── ServiceName.Api/            → Controllers, Program.cs
├── ServiceName.Application/    → CQRS, DTOs, Interfaces, Validation
├── ServiceName.Domain/         → Entities, Enums (ZERO dependency)
└── ServiceName.Infrastructure/ → DbContext, Repositories, Consumers, DI, BackgroundJobs
```

Dependency direction: `Api → Application, Infrastructure` | `Application → Domain only` | `Domain → nothing`

Shared libraries:
- `SharedKernel/` — Base entities, interfaces (IGenericRepository, IUnitOfWork)
- `SharedContracts/` — DTOs, Integration events
- `SharedInfrastructure/` — Middleware, Behaviors, GenericRepository, Caching, Bus

---

## 2. Entity & Domain

```csharp
public class Battery : AuditableEntity  // PHẢI extend AuditableEntity
{
    public string Name { get; set; } = string.Empty;
    public BatteryStatusEnum Status { get; set; } = BatteryStatusEnum.Active;
    public Guid? LocationId { get; set; }           // Nullable FK
    public Location? Location { get; set; }          // Navigation
    public ICollection<Ticket> Tickets { get; set; } = new List<Ticket>();
}

public enum BatteryStatusEnum
{
    Active = 1,     // BẮT ĐẦU TỪ 1, KHÔNG phải 0
    Inactive = 2,
    Failed = 3,
}
```

**Rules:**
- ALL entities PHẢI extend `AuditableEntity` (cho Id, CreatedAt, CreatedBy, UpdatedAt, IsDeleted, DeletedAt)
- PK: `Guid Id` — KHÔNG dùng int auto-increment
- Enum values bắt đầu từ `1`
- Domain layer: ZERO dependency

---

## 3. CQRS + MediatR

**Folder structure:**
```
Application/
├── Commands/{Entity}{Action}/{Entity}{Action}Command.cs
│                             {Entity}{Action}CommandHandler.cs
├── Queries/{Entity}Get{Scope}/{Entity}Get{Scope}Query.cs
│                              {Entity}Get{Scope}QueryHandler.cs
└── DTOs/Response/{Entity}Response.cs
```

**Command Handler pattern:**
```csharp
public class BatteryCreateCommandHandler : IRequestHandler<BatteryCreateCommand, CommonResponse<BatteryDTO>>
{
    private readonly IServiceUnitOfWork _unitOfWork;

    public async Task<CommonResponse<BatteryDTO>> Handle(BatteryCreateCommand request, CancellationToken ct)
    {
        var exists = await _unitOfWork.Batteries.AnyAsync(x => x.Name == request.Name && !x.IsDeleted);
        if (exists) return new CommonResponse<BatteryDTO> { IsSuccess = false, Message = "Already exists" };

        var entity = new Battery { Name = request.Name };

        await _unitOfWork.BeginTransactionAsync();
        try
        {
            await _unitOfWork.Batteries.AddAsync(entity);
            await _unitOfWork.CommitTransactionAsync();
        }
        catch (Exception ex)
        {
            await _unitOfWork.RollbackTransactionAsync();
            return new CommonResponse<BatteryDTO> { IsSuccess = false, Message = ex.Message };
        }

        return new CommonResponse<BatteryDTO> { IsSuccess = true, Data = new BatteryDTO { Id = entity.Id.ToString() } };
    }
}
```

**Query Handler pattern:**
```csharp
var query = _unitOfWork.Batteries.GetAllAsync()  // SYNC — returns IQueryable directly
    .Include(x => x.Location)
    .Where(x => !x.IsDeleted);

if (request.Status.HasValue) query = query.Where(x => x.Status == request.Status);

query = request.IsDescending == true
    ? query.OrderByDescending(x => x.CreatedAt)
    : query.OrderBy(x => x.CreatedAt);
```

**Rules:**
- Handler chỉ inject `IUnitOfWork` — KHÔNG inject DbContext trực tiếp
- Controller chỉ gọi `_mediator.Send()` — KHÔNG chứa logic
- Query handlers KHÔNG gọi `SaveChangesAsync`
- 1 Command/Query + 1 Handler per folder

---

## 4. Repository & UnitOfWork ⚠️ CRITICAL

```csharp
public interface IGenericRepository<T>
{
    Task<T?> GetByIdAsync(object id);
    IQueryable<T> GetAllAsync();        // ⚠️ SYNC — trả IQueryable trực tiếp, KHÔNG await
                                        // Tên "Async" là legacy từ SharedKernel — KHÔNG thay đổi
    Task AddAsync(T entity);            // async — CÓ await
    void UpdateAsync(T entity);         // ⚠️ VOID — KHÔNG await (EF tracking tự xử lý)
    void DeleteAsync(T entity);         // ⚠️ VOID — KHÔNG await (interceptor tự chuyển soft delete)
    Task<bool> AnyAsync(Expression<Func<T, bool>> predicate);
}
```

```csharp
// ✅ ĐÚNG
var query = _unitOfWork.Batteries.GetAllAsync().Where(x => !x.IsDeleted);
_unitOfWork.Batteries.UpdateAsync(entity);      // NO await
_unitOfWork.Batteries.DeleteAsync(entity);      // NO await
await _unitOfWork.Batteries.AddAsync(entity);   // HAS await

// ❌ SAI — 3 lỗi phổ biến nhất
var query = await _unitOfWork.Batteries.GetAllAsync();  // WRONG — GetAllAsync là SYNC
await _unitOfWork.Batteries.UpdateAsync(entity);         // WRONG — UpdateAsync là VOID
await _unitOfWork.Batteries.DeleteAsync(entity);         // WRONG — DeleteAsync là VOID
```

> **Dự án GSU26SE55 KHÔNG cấu hình global query filter (`HasQueryFilter`).** Vì vậy LUÔN LUÔN thêm `.Where(x => !x.IsDeleted)` trong mọi query. Không bao giờ bỏ qua filter này.

**Transaction pattern:**
```csharp
await _unitOfWork.BeginTransactionAsync();
try
{
    _unitOfWork.Children.DeleteAsync(child);    // NO await
    _unitOfWork.Batteries.UpdateAsync(battery); // NO await
    await _unitOfWork.CommitTransactionAsync(); // auto-calls SaveChangesAsync
}
catch { await _unitOfWork.RollbackTransactionAsync(); }
```

---

## 5. Response Wrappers & DTO

```csharp
// CommonResponse<T> — wrapper chuẩn
public class CommonResponse<T> : CommonResponseBase
{
    public T? Data { get; set; }
    public List<Errors> ListErrors { get; set; } = new();
}
// IsSuccess defaults TRUE — set FALSE explicitly on error
// ListErrors = List<Errors> (Field + Detail)

// Response types
public class BatteryGetListResponse : CommonResponse<PaginationResponse<object>> { }
public class BatteryGetByIdResponse : CommonResponse<object> { }
public class BatteryCreateResponse : CommonResponse<BatteryDTO> { }

// DTO
public class BatteryDTO
{
    public string Id { get; set; }    // Guid → string (KHÔNG giữ Guid trong main DTO)
    public string? Name { get; set; }
    public BatteryStatusEnum Status { get; set; }
    public DateTime CreatedAt { get; set; }
    public LocationDTO? Location { get; set; }  // nullable = conditional include
}
```

**Rules:**
- Guid → string trong main DTO (`.ToString()`)
- NO AutoMapper — inline mapping trong handler
- `HasXxx = false` mặc định cho GetList, `HasXxx = true` cho GetById

---

## 6. REST API Controller

```csharp
[ApiController]
[Route("api/batteries")]   // lowercase, plural, kebab-case
public class BatteryController : ControllerBase
{
    private readonly IMediator _mediator;
    public BatteryController(IMediator mediator) => _mediator = mediator;

    [HttpGet]
    public async Task<IActionResult> GetAll([FromQuery] BatteryGetListQuery query)
        => Ok(await _mediator.Send(query));

    [HttpGet("{id}")]
    public async Task<IActionResult> GetById(Guid id)
        => Ok(await _mediator.Send(new BatteryGetByIdQuery { Id = id }));

    [HttpPost]
    [Authorize]
    public async Task<IActionResult> Create([FromBody] BatteryCreateCommand cmd)
        => Ok(await _mediator.Send(cmd));

    [HttpPut("{id}")]
    [Authorize]
    public async Task<IActionResult> Update(Guid id, [FromBody] BatteryUpdateCommand cmd)
    { cmd.Id = id; return Ok(await _mediator.Send(cmd)); }

    [HttpDelete("{id}")]
    [Authorize(Policy = "AdminOnly")]
    public async Task<IActionResult> Delete(Guid id)
        => Ok(await _mediator.Send(new BatteryDeleteCommand { Id = id }));

    [HttpPatch("{id}")]
    [Authorize(Policy = "AdminOnly")]
    public async Task<IActionResult> Restore(Guid id)
        => Ok(await _mediator.Send(new BatteryRestoreCommand { Id = id }));
}
```

---

## 7. Soft Delete ⚠️

`AuditableEntityInterceptor` auto-convert `DeleteAsync()` → `IsDeleted=true, DeletedAt=UtcNow`.

```csharp
// Soft delete (interceptor tự xử lý)
_unitOfWork.Batteries.DeleteAsync(battery);  // NO await

// Restore
battery.IsDeleted = false;
battery.DeletedAt = null;
_unitOfWork.Batteries.UpdateAsync(battery);  // NO await

// Query: ALWAYS filter deleted
var query = _unitOfWork.Batteries.GetAllAsync().Where(x => !x.IsDeleted);

// Cascade: xóa children TRƯỚC parent
foreach (var ticket in battery.Tickets)
    _unitOfWork.Tickets.DeleteAsync(ticket); // NO await
_unitOfWork.Batteries.DeleteAsync(battery);  // NO await
await _unitOfWork.CommitTransactionAsync();
```

**Quy tắc bắt buộc:** LUÔN filter `.Where(x => !x.IsDeleted)` trong mọi query (dự án không dùng global query filter).

---

## 8. Validation

```csharp
public class BatteryCreateCommand : IRequest<BatteryCreateResponse>, IValidatable<BatteryCreateResponse>
{
    public string Name { get; set; }

    public Task<BatteryCreateResponse> ValidateAsync()
    {
        var response = new BatteryCreateResponse();

        if (string.IsNullOrEmpty(Name))
            response.ListErrors.Add(new Errors { Field = "Name", Detail = "Required" });
        else if (Name.Length > 100)
            response.ListErrors.Add(new Errors { Field = "Name", Detail = "Max 100 chars" });

        // Thu thập TẤT CẢ errors (không fail sớm)
        if (response.ListErrors.Count > 0) response.IsSuccess = false;
        return Task.FromResult(response);
    }
}
```

**Common regex:**

| Field | Pattern |
|-------|---------|
| Email | `[\w.+-]+@[\w-]+\.[\w]{2,}` |
| Password | `^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[!@#$%^&*]).{8,}$` |
| Phone VN | `^(0[35789])[0-9]{8}$` |

**Pipeline:** `Request → ValidationBehavior → nếu !IsSuccess → return ngay (skip handler)`

---

## 9. Error Handling

| Layer | Xử lý | Response |
|-------|-------|----------|
| Validation pipeline | `ValidateAsync()` | 200 OK, `isSuccess=false, listErrors:[...]` |
| Handler business logic | return IsSuccess=false | 200 OK, `isSuccess=false, message:"..."` |
| Unhandled exception | GlobalExceptionMiddleware | **500** JSON |
| JWT missing/expired | OnChallenge event | **401** JSON |
| JWT forbidden | OnForbidden event | **403** JSON |

**Handler error patterns:**
```csharp
if (entity == null) return new CommonResponse<T> { IsSuccess = false, Message = "Not found" };
if (entity.IsDeleted) return new CommonResponse<T> { IsSuccess = false, Message = "Is deleted" };
```

**Middleware pipeline order:**
```csharp
app.UseSharedInfrastructure(); // GlobalExceptionMiddleware — FIRST
app.UseSwagger(); app.UseSwaggerUI();
app.UseCors("AllowAll");
app.UseAuthentication();
app.UseAuthorization();
app.MapControllers();
```

---

## 10. Dependency Injection

```csharp
// Infrastructure/DependencyInjection/ManageDependencyInjection.cs
services.AddScoped<IUnitOfWork, UnitOfWork>();
services.AddScoped<ICacheService, RedisCacheService>();
services.AddTransient(typeof(IPipelineBehavior<,>), typeof(ValidationBehavior<,>));
services.AddMediatR(cfg => cfg.RegisterServicesFromAssembly(Assembly.Load("Service.Application")));
services.AddMessageBus(configuration, typeof(MyConsumer).Assembly);
services.AddHostedService<MyBackgroundService>();
```

**Anti-patterns:**
- KHÔNG inject Scoped vào Singleton
- KHÔNG `new()` services thủ công
- KHÔNG inject DbContext trong handlers — dùng UnitOfWork

---

## 11. RabbitMQ / MassTransit

```csharp
// Event — dùng record, KHÔNG phải class
public record BatteryAnomalyDetectedEvent : IntegrationEvent
{
    public Guid BatteryId { get; set; }
    public string Severity { get; set; } = string.Empty;
}

// Consumer
public class BatteryAnomalyDetectedConsumer : IConsumer<BatteryAnomalyDetectedEvent>
{
    public async Task Consume(ConsumeContext<BatteryAnomalyDetectedEvent> context)
    {
        var evt = context.Message;
        // ... process event
        // Throw exception → MassTransit auto-retry
    }
}
```

**Convention publish:**
- Service KHÔNG có Outbox: publish **SAU** `CommitTransactionAsync()` (default)
- Service CÓ Outbox (nếu áp dụng): publish **TRƯỚC** `SaveChangesAsync()` (atomic)

---

## 12. JWT Authentication

```
Login → AccessToken (1h) + RefreshToken (7d, Redis key: RT_{userId})
API call → Authorization: Bearer {accessToken}
Token expired → POST /refresh
Logout → delete from Redis
```

**Claims:** `NameIdentifier, UserId, FullName, Email, Role` ("1"=Admin, "2"=Manager, "3"=Staff, "4"=Customer)

**Policies:**
```csharp
options.AddPolicy("AdminOnly", p => p.RequireClaim("Role", "1"));
options.AddPolicy("ManagerOnly", p => p.RequireClaim("Role", "2"));
```

---

## 13. EF Core & Database

```bash
# Run from Api project directory
dotnet ef migrations add AddBattery -p ../ServiceName.Infrastructure -s .
dotnet ef database update -p ../ServiceName.Infrastructure -s .
```

- Database per service (mỗi service có DB riêng)
- PostgreSQL + TimescaleDB cho time-series data
- Auto-migrate on startup (`db.Database.Migrate()`)
- DbContext tên `ApplicationDbContext` (mỗi service)

---

## 14. Migration Checklist ⚠️

Bắt buộc kiểm tra trước khi chạy `/kltn-ship`:

```bash
# Tên migration rõ ràng — mô tả thay đổi
dotnet ef migrations add AddBatteryStatusColumn -p ../ServiceName.Infrastructure -s .

# Áp dụng migration
dotnet ef database update -p ../ServiceName.Infrastructure -s .

# Rollback test — BẮT BUỘC nếu migration thay đổi schema
dotnet ef database update PreviousMigrationName -p ../ServiceName.Infrastructure -s .
dotnet ef database update -p ../ServiceName.Infrastructure -s .   # apply lại → phải thành công
```

**Checklist trước khi commit migration:**
- [ ] Tên migration mô tả rõ thay đổi (e.g., `AddBatteryStatusColumn`, `CreateTicketTable`)
- [ ] Có `Down()` method — rollback phải hoạt động
- [ ] Nếu thêm `NOT NULL` column: có `defaultValue` hoặc đã populate existing rows
- [ ] Nếu rename column: dùng `RenameColumn`, không xóa + tạo lại (tránh mất data)
- [ ] Đã test rollback: `database update [prev]` → `database update` → không lỗi
- [ ] Không có raw SQL nguy hiểm trong `Up()` / `Down()` (e.g., `DROP TABLE`, `TRUNCATE`)

**Seed data khi thêm NOT NULL column vào bảng có data:**
```csharp
// Trong Up() — populate trước khi add constraint
migrationBuilder.Sql("UPDATE batteries SET status = 1 WHERE status IS NULL");
migrationBuilder.AlterColumn<int>("status", "batteries", nullable: false, defaultValue: 1);
```

---

## 15. Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Entity | `{Name}.cs` | `Battery.cs` |
| Enum | `{Name}Enum.cs` | `BatteryStatusEnum.cs` |
| Command | `{Entity}{Action}Command.cs` | `BatteryCreateCommand.cs` |
| Handler | `{Entity}{Action}CommandHandler.cs` | `BatteryCreateCommandHandler.cs` |
| Query | `{Entity}Get{Scope}Query.cs` | `BatteryGetListQuery.cs` |
| DTO | `{Entity}DTO.cs` | `BatteryDTO.cs` |
| Response | `{Entity}{Action}Response.cs` | `BatteryCreateResponse.cs` |
| Consumer | `{EventName}Consumer.cs` | `BatteryAnomalyConsumer.cs` |
| Event | `{Action}Event.cs` | `BatteryAnomalyDetectedEvent.cs` |
| Background | `{Name}BackgroundService.cs` | `SohPredictionBackgroundService.cs` |
| DI File | `ManageDependencyInjection.cs` | (same per service) |

**C# conventions:**
- Classes/Methods: PascalCase
- Async methods: `...Async` suffix
- Private fields: `_camelCase`
- Parameters: camelCase
- Routes: `api/batteries`, `api/battery-readings` (lowercase, plural, kebab-case)
