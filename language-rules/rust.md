# Rust — Vibe Coding Rules (2026)

> Apply these rules whenever asking any AI to generate, review, or modify Rust code.
>
> **See also:** [../docs/universal-principles.md](../docs/universal-principles.md) (the 9 pillars), [../docs/workflow-guide.md](../docs/workflow-guide.md) (the loop), [../AGENTS.md](../AGENTS.md) (the protocols).

---

## 🦀 Rust Version & Standard

**Target: Rust Stable (2024 Edition), Cargo with Clippy**

---

## ✅ Mandatory Rules

### 1. Never Use `unwrap()` or `expect()` in Production Code
```rust
// ❌ REJECT in production paths
let user = get_user(id).unwrap();
let file = File::open(path).expect("file should exist");

// ✅ REQUIRE proper error propagation
let user = get_user(id)?;
let file = File::open(path).map_err(|e| AppError::Io(e))?;
```

### 2. Use the `?` Operator with Typed Error Enums
```rust
// ✅ Define a typed error enum
#[derive(Debug, thiserror::Error)]
pub enum AppError {
    #[error("Database error: {0}")]
    Database(#[from] sqlx::Error),
    #[error("Not found: {0}")]
    NotFound(String),
    #[error("Unauthorized")]
    Unauthorized,
}

// ✅ Use ? for propagation
pub async fn get_user(id: Uuid) -> Result<User, AppError> {
    let user = sqlx::query_as!(User, "SELECT * FROM users WHERE id = $1", id)
        .fetch_optional(&pool)
        .await?
        .ok_or_else(|| AppError::NotFound(format!("User {id}")))?;
    Ok(user)
}
```

### 3. Enforce Clippy on All Generated Code
The AI must generate Clippy-clean code. Add to every prompt:
```
The code must pass `cargo clippy -- -D warnings` with zero warnings.
```

### 4. Never Use `unsafe` Without Explicit Justification
```rust
// ❌ REJECT unsafe without documented justification
unsafe {
    // some pointer magic
}

// ✅ REQUIRE comment explaining necessity and invariants maintained
// SAFETY: We have exclusive access to this memory region because [reason].
// This is valid because [invariant that makes this sound].
unsafe {
    // some pointer magic
}
```

### 5. Prefer `Arc<Mutex<T>>` and Message Passing Over Raw Pointers
```rust
// ✅ For shared state across async tasks
use std::sync::Arc;
use tokio::sync::Mutex;

let shared_state = Arc::new(Mutex::new(AppState::default()));
```

### 6. Use `tokio` for Async Runtimes
```rust
// ✅ Standard async runtime for 2026
#[tokio::main]
async fn main() -> Result<(), AppError> {
    // ...
}
```

### 7. Clippy Lints to Enforce in Prompts
Add this to your Rust project's `main.rs` or `lib.rs`:
```rust
#![deny(clippy::unwrap_used)]
#![deny(clippy::expect_used)]
#![deny(clippy::panic)]
#![deny(unsafe_code)]
#![warn(clippy::pedantic)]
```
Tell the AI: *"Respect the deny/warn lints defined at the crate root."*

---

## 🚫 AI Pitfalls to Watch for in Rust

| Pitfall | What to Look For | How to Fix |
|---------|-----------------|------------|
| `unwrap()`/`expect()` | Anywhere in non-test code | Use `?` with typed errors |
| Incorrect lifetimes | Complex borrow errors | Ask AI to simplify; avoid over-engineering lifetimes |
| `unsafe` blocks | Any `unsafe` | Demand justification comment or remove |
| `clone()` abuse | Excessive `.clone()` calls | Investigate if ownership can be restructured |
| Blocking in async | `std::thread::sleep` in async | Use `tokio::time::sleep` |
| `String` vs `&str` confusion | Unnecessary owned `String` | Prefer `&str` in function arguments |

---

## 📋 Prompt Template for Rust

```
You are a senior Rust engineer writing production-quality Rust (2024 edition).
Follow these rules:
- Never use unwrap() or expect() in non-test code — use the ? operator
- All errors must be typed using thiserror derive macros
- Use tokio for async runtimes
- No unsafe blocks without a SAFETY comment explaining the invariants
- Code must pass `cargo clippy -- -D warnings`
- Prefer Arc<Mutex<T>> and channels for concurrency over raw pointers
- Use &str in function arguments, owned String only when necessary

TASK: [Your task here]
```
