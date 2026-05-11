# PHP — Vibe Coding Rules (2026)

> Apply these rules whenever asking any AI to generate, review, or modify PHP code.
>
> **See also:** [../docs/universal-principles.md](../docs/universal-principles.md) (the 9 pillars), [../docs/workflow-guide.md](../docs/workflow-guide.md) (the loop), [../AGENTS.md](../AGENTS.md) (the protocols).

---

## 🐘 PHP Version & Standard

**Target: PHP 8.3+ with strict_types=1**

---

## ✅ Mandatory Rules

### 1. Always Declare Strict Types
```php
<?php
// ✅ REQUIRED at the top of EVERY PHP file
declare(strict_types=1);
```

### 2. Use PDO with Parameterized Queries (No mysqli string concat)
```php
// ❌ REJECT — SQL injection vulnerability
$result = mysqli_query($conn, "SELECT * FROM users WHERE email = '$email'");

// ✅ REQUIRE — PDO with named parameters
$stmt = $pdo->prepare("SELECT id, name, email FROM users WHERE email = :email");
$stmt->execute(['email' => $email]);
$user = $stmt->fetch(PDO::FETCH_ASSOC);
```

### 3. Escape All Output (XSS Prevention)
```php
// ❌ REJECT — raw user data in output
echo $_GET['name'];
echo "<p>" . $user['bio'] . "</p>";

// ✅ REQUIRE — escape all output
echo htmlspecialchars($_GET['name'], ENT_QUOTES, 'UTF-8');
echo "<p>" . htmlspecialchars($user['bio'], ENT_QUOTES, 'UTF-8') . "</p>";
```

### 4. Use Modern PHP 8.x Features
```php
// ✅ Named arguments (PHP 8.0+)
$user = new User(name: 'Alice', email: 'alice@example.com');

// ✅ Enums (PHP 8.1+)
enum Status: string {
    case Active = 'active';
    case Inactive = 'inactive';
    case Suspended = 'suspended';
}

// ✅ Readonly properties (PHP 8.1+)
class User {
    public function __construct(
        public readonly string $id,
        public readonly string $email,
    ) {}
}

// ✅ Match expression (PHP 8.0+)
$message = match($status) {
    Status::Active => 'Welcome back!',
    Status::Inactive => 'Account inactive.',
    Status::Suspended => 'Account suspended.',
};
```

### 5. Type Declarations on All Functions
```php
// ❌ REJECT untyped functions
function getUser($id) {
    return $this->repo->find($id);
}

// ✅ REQUIRE full type declarations
function getUser(string $id): ?User {
    return $this->repository->findById($id);
}
```

### 6. Never Use `eval()` or Dynamic Variable Variables
```php
// ❌ REJECT — remote code execution risk
eval($userInput);
$$dynamicVarName = $value;

// ✅ REQUIRE explicit, whitelist-based approaches
```

### 7. Session Security
```php
// ✅ Secure session configuration
session_start([
    'cookie_httponly' => true,
    'cookie_secure' => true,
    'cookie_samesite' => 'Strict',
    'use_strict_mode' => true,
]);

// ✅ Regenerate session ID after login
session_regenerate_id(true);
```

---

## 🚫 AI Pitfalls to Watch for in PHP

| Pitfall | What to Look For | How to Fix |
|---------|-----------------|------------|
| SQL injection | `"WHERE id = '$id'"` string concat | Use PDO with `:param` |
| XSS | `echo $_GET['x']` without escaping | `htmlspecialchars()` all output |
| `eval()` usage | Any `eval(...)` call | Remove entirely |
| No `strict_types` | Missing declare at top | Add `declare(strict_types=1)` |
| Deprecated functions | `mysql_*` functions | Use PDO or MySQLi |
| Unsanitized file paths | `include($_GET['page'])` | Whitelist allowed values only |

---

## 📋 Prompt Template for PHP

```
You are a senior PHP 8.3 engineer. Write modern PHP following these rules:
- ALWAYS start with declare(strict_types=1)
- ALL database queries MUST use PDO with parameterized statements (never string concatenation)
- ALWAYS escape output with htmlspecialchars() — never echo raw user data
- Use modern PHP 8.x features: enums, readonly properties, named args, match expressions
- Full type declarations on all function parameters and return types
- Never use eval(), ereg_*, or mysql_* functions
- Secure session configuration (httponly, secure, samesite cookies)

TASK: [Your task here]
```
