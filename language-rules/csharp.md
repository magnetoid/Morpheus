# C# — Vibe Coding Rules (2026)

> Apply these rules whenever asking any AI to generate, review, or modify C# code.
>
> **See also:** [../docs/universal-principles.md](../docs/universal-principles.md) (the 9 pillars), [../docs/workflow-guide.md](../docs/workflow-guide.md) (the loop), [../AGENTS.md](../AGENTS.md) (the protocols).

---

## 🔷 C# Version & Standard

**Target: C# 13 / .NET 9**

---

## ✅ Mandatory Rules

### 1. Enable Nullable Reference Types
```xml
<!-- In .csproj — mandatory -->
<Nullable>enable</Nullable>
<ImplicitUsings>enable</ImplicitUsings>
<TreatWarningsAsErrors>true</TreatWarningsAsErrors>
```
Add to every prompt: *"Nullable reference types are enabled. Handle all nullable cases explicitly with `?` annotations."*

### 2. Use Records for Immutable Data
```csharp
// ❌ REJECT verbose class with properties
public class CreateUserRequest {
    public string Name { get; set; }
    public string Email { get; set; }
}

// ✅ REQUIRE records for DTOs and value objects
public record CreateUserRequest(string Name, string Email);

// ✅ With validation (using FluentValidation)
public sealed record CreateUserRequest(string Name, string Email);
```

### 3. Use `ILogger<T>` for All Logging
```csharp
// ❌ REJECT
Console.WriteLine($"User created: {userId}");

// ✅ REQUIRE
private readonly ILogger<UserService> _logger;

_logger.LogInformation("User created. UserId: {UserId}", userId);
```

### 4. Async/Await Everywhere for I/O
```csharp
// ❌ REJECT .Result or .Wait() (causes deadlocks)
var user = GetUserAsync(id).Result;

// ✅ REQUIRE proper async
public async Task<User?> GetUserAsync(string id, CancellationToken ct = default)
{
    return await _repository.FindByIdAsync(id, ct);
}
```

### 5. Use `CancellationToken` in All Async Methods
```csharp
// ✅ Always thread CancellationToken through the call chain
public async Task<User?> GetUserAsync(
    string id,
    CancellationToken cancellationToken = default)
{
    return await _dbContext.Users
        .FirstOrDefaultAsync(u => u.Id == id, cancellationToken);
}
```

### 6. Dependency Injection via Constructor
```csharp
// ✅ Constructor injection — testable and explicit
public class UserService
{
    private readonly IUserRepository _repository;
    private readonly ILogger<UserService> _logger;

    public UserService(IUserRepository repository, ILogger<UserService> logger)
    {
        _repository = repository;
        _logger = logger;
    }
}
```

### 7. Use `Result<T>` Pattern (e.g., with OneOf or ErrorOr)
```csharp
// ✅ Functional error handling
using ErrorOr;

public async Task<ErrorOr<User>> CreateUserAsync(CreateUserRequest request)
{
    if (await _repository.EmailExistsAsync(request.Email))
        return Error.Conflict("User.EmailExists", "Email already registered.");

    var user = new User(request.Name, request.Email);
    await _repository.AddAsync(user);
    return user;
}
```

---

## 🚫 AI Pitfalls to Watch for in C#

| Pitfall | What to Look For | How to Fix |
|---------|-----------------|------------|
| `.Result` or `.Wait()` | Deadlock-prone blocking calls | Use `await` properly |
| Missing CancellationToken | Async methods without CT param | Add `CancellationToken ct = default` |
| No nullable annotations | `string` instead of `string?` | Enable nullable and annotate |
| `Console.WriteLine` in production | Any console output | Use `ILogger<T>` |
| Field injection | Service Locator pattern | Use constructor injection |
| Missing `IAsyncDisposable` | DB contexts not disposed | Use `using` or DI lifetime management |

---

## 📋 Prompt Template for C#

```
You are a senior C# / .NET 9 engineer. Write C# 13 code following these rules:
- Nullable reference types ENABLED — annotate all nullable types with ?
- Records for all DTOs, commands, and value objects
- ILogger<T> for all logging — no Console.WriteLine
- async/await throughout — never use .Result or .Wait()
- CancellationToken as last parameter in all async methods
- Constructor injection only — no service locator pattern
- ErrorOr<T> or similar Result type for business logic error handling
- TreatWarningsAsErrors is active — generate zero-warning code

TASK: [Your task here]
```
