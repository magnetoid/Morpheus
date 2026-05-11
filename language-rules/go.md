# Go (Golang) — Vibe Coding Rules (2026)

> Apply these rules whenever asking any AI to generate, review, or modify Go code.
>
> **See also:** [../docs/universal-principles.md](../docs/universal-principles.md) (the 9 pillars), [../docs/workflow-guide.md](../docs/workflow-guide.md) (the loop), [../AGENTS.md](../AGENTS.md) (the protocols).

---

## 🐹 Go Version & Standard

**Target: Go 1.23+**

---

## ✅ Mandatory Rules

### 1. Always Handle Errors (The Go Way)
The most critical rule in Go. AI often generates code that ignores errors.
```go
// ❌ REJECT — ignoring errors
user, _ := getUser(ctx, id)

// ✅ REQUIRE — explicit error handling
user, err := getUser(ctx, id)
if err != nil {
    return fmt.Errorf("getUser(%s): %w", id, err)
}
```

### 2. Always Pass `context.Context` as the First Parameter
```go
// ❌ REJECT — no context
func getUser(id string) (*User, error) {}

// ✅ REQUIRE — context as first param
func getUser(ctx context.Context, id string) (*User, error) {}
```

### 3. Use `%w` for Error Wrapping
```go
// ❌ REJECT — loses error chain
return fmt.Errorf("failed: %s", err.Error())

// ✅ REQUIRE — preserves chain with %w
return fmt.Errorf("processOrder: %w", err)
```

### 4. Always Close Resources with `defer`
```go
// ✅ Close immediately after checking error
rows, err := db.QueryContext(ctx, query, args...)
if err != nil {
    return nil, fmt.Errorf("query: %w", err)
}
defer rows.Close()
```

### 5. Prevent Goroutine Leaks
```go
// ✅ Use context for cancellation
func runWorker(ctx context.Context, ch <-chan Job) {
    for {
        select {
        case job, ok := <-ch:
            if !ok {
                return // channel closed
            }
            processJob(job)
        case <-ctx.Done():
            return // context cancelled
        }
    }
}
```

### 6. Use Structured Logging (slog — stdlib)
```go
// ❌ REJECT fmt.Println for logging
fmt.Println("User created:", userID)

// ✅ REQUIRE slog (Go 1.21+ standard library)
slog.InfoContext(ctx, "user created", "userID", userID, "email", email)
```

### 7. Table-Driven Tests
```go
// ✅ Standard Go test structure
func TestProcessOrder(t *testing.T) {
    tests := []struct {
        name    string
        input   Order
        want    *Result
        wantErr bool
    }{
        {name: "valid order", input: Order{...}, want: &Result{...}},
        {name: "empty order ID", input: Order{ID: ""}, wantErr: true},
    }
    
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := ProcessOrder(context.Background(), tt.input)
            if (err != nil) != tt.wantErr {
                t.Errorf("ProcessOrder() error = %v, wantErr %v", err, tt.wantErr)
            }
            // ...
        })
    }
}
```

---

## 🚫 AI Pitfalls to Watch for in Go

| Pitfall | What to Look For | How to Fix |
|---------|-----------------|------------|
| Ignored errors | `result, _ := ...` | Always handle the error return |
| Missing context | Functions without `ctx context.Context` | Add context as first parameter |
| Goroutine leaks | Goroutines without exit conditions | Use `ctx.Done()` or channel close |
| `fmt.Println` for logging | `fmt.Println` / `log.Println` | Use `slog.InfoContext` |
| Non-wrapped errors | `fmt.Errorf("error: %s", err)` | Use `%w` for wrapping |
| Mutex without defer | Lock without guaranteed unlock | Always `defer mu.Unlock()` after lock |

---

## 📋 Prompt Template for Go

```
You are a senior Go engineer. Write idiomatic Go 1.23+ following these rules:
- ALWAYS handle all errors explicitly — never use the blank identifier _ for errors
- Pass context.Context as the FIRST parameter to all functions doing I/O
- Use %w in fmt.Errorf for error wrapping (preserves the error chain)
- Always defer Close() / Unlock() immediately after acquiring resources
- Use the standard library slog package for structured logging
- Prevent goroutine leaks by using ctx.Done() or channel close signals
- Write table-driven tests using t.Run()

TASK: [Your task here]
```
