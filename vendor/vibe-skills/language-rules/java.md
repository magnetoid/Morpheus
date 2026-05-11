# Java — Vibe Coding Rules (2026)

> Apply these rules whenever asking any AI to generate, review, or modify Java code.
>
> **See also:** [../docs/universal-principles.md](../docs/universal-principles.md) (the 9 pillars), [../docs/workflow-guide.md](../docs/workflow-guide.md) (the loop), [../AGENTS.md](../AGENTS.md) (the protocols).

---

## ☕ Java Version & Standard

**Target: Java 21 LTS (Virtual Threads, Records, Sealed Classes)**

---

## ✅ Mandatory Rules

### 1. Use Modern Java 21 Features
```java
// ❌ REJECT old-style Java patterns
public class User {
    private final String name;
    private final String email;
    public User(String name, String email) { this.name = name; this.email = email; }
    public String getName() { return name; }
    public String getEmail() { return email; }
}

// ✅ REQUIRE Java 16+ Records
public record User(String name, String email) {}
```

### 2. Use `Optional` Instead of Returning `null`
```java
// ❌ REJECT null returns
public User getUserById(String id) {
    return userRepository.find(id); // may return null
}

// ✅ REQUIRE Optional
public Optional<User> getUserById(String id) {
    return userRepository.findById(id);
}
```

### 3. Use Virtual Threads for I/O (Java 21)
```java
// ✅ Structured concurrency with virtual threads
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    Future<User> userFuture = executor.submit(() -> fetchUser(id));
    Future<Order[]> ordersFuture = executor.submit(() -> fetchOrders(id));
    
    User user = userFuture.get();
    Order[] orders = ordersFuture.get();
}
```

### 4. Use Pattern Matching (Java 21)
```java
// ❌ REJECT old instanceof casting
if (shape instanceof Circle) {
    Circle c = (Circle) shape;
    return c.radius() * c.radius() * Math.PI;
}

// ✅ REQUIRE pattern matching
return switch (shape) {
    case Circle c -> c.radius() * c.radius() * Math.PI;
    case Rectangle r -> r.width() * r.height();
    default -> throw new IllegalArgumentException("Unknown shape");
};
```

### 5. Dependency Injection via Constructor (Not Field Injection)
```java
// ❌ REJECT field injection
@Service
public class UserService {
    @Autowired
    private UserRepository repository; // field injection
}

// ✅ REQUIRE constructor injection
@Service
public class UserService {
    private final UserRepository repository;
    
    public UserService(UserRepository repository) {
        this.repository = repository;
    }
}
```

### 6. Use `ILogger` (SLF4J) Not `System.out.println`
```java
// ❌ REJECT
System.out.println("User created: " + userId);

// ✅ REQUIRE
private static final Logger log = LoggerFactory.getLogger(UserService.class);
log.info("User created: userId={}, email={}", userId, email);
```

---

## 🚫 AI Pitfalls to Watch for in Java

| Pitfall | What to Look For | How to Fix |
|---------|-----------------|------------|
| Legacy POJO boilerplate | 10+ line getter/setter classes | Use Records |
| Null returns | `return null` in service methods | Return `Optional<T>` |
| `System.out.println` | Any sysout in production code | Use SLF4J `log.info()` |
| Field `@Autowired` | Field-level Spring injection | Use constructor injection |
| Old-style thread management | `new Thread(...)` for I/O | Use virtual threads |
| Raw type usage | `List list` without generics | Always use `List<String>` |

---

## 📋 Prompt Template for Java

```
You are a senior Java 21 engineer. Write modern Java following these rules:
- Use Records for immutable data carriers (not POJOs with getters/setters)
- Return Optional<T> instead of null from repository/service methods
- Use pattern matching and switch expressions (Java 21 syntax)
- Constructor injection only — no @Autowired field injection
- Use SLF4J (LoggerFactory) for all logging — no System.out.println
- Use virtual threads (Executors.newVirtualThreadPerTaskExecutor) for I/O concurrency
- Strong typing — no raw types

TASK: [Your task here]
```
