# SQL — Vibe Coding Rules (2026)

> Apply these rules whenever asking any AI to generate, review, or modify SQL queries.
>
> **See also:** [../docs/universal-principles.md](../docs/universal-principles.md) (the 9 pillars), [../docs/workflow-guide.md](../docs/workflow-guide.md) (the loop), [../AGENTS.md](../AGENTS.md) (the protocols).

---

## 🗄️ SQL Standard

**Target: PostgreSQL 17 (primary), with notes for MySQL 9 / SQLite**

---

## ✅ Mandatory Rules

### 1. ALWAYS Use Parameterized Queries (The #1 Security Rule)
SQL Injection is the most common vulnerability in AI-generated database code.
```sql
-- ❌ REJECT string concatenation (SQL Injection vulnerability)
-- (in any language, this pattern is CRITICAL)
query = "SELECT * FROM users WHERE email = '" + userEmail + "'"

-- ✅ REQUIRE parameterized queries in every ORM/driver
-- Python (asyncpg)
await conn.fetch("SELECT * FROM users WHERE email = $1", user_email)

-- Node.js (pg)
await client.query("SELECT * FROM users WHERE email = $1", [userEmail])

-- Go (sqlx)
db.GetContext(ctx, &user, "SELECT * FROM users WHERE email = $1", email)
```

### 2. Always Specify Column Names (No `SELECT *`)
```sql
-- ❌ REJECT — fragile, over-fetches data
SELECT * FROM users WHERE id = $1;

-- ✅ REQUIRE — explicit columns, documents intent
SELECT id, name, email, created_at
FROM users
WHERE id = $1;
```

### 3. Detect and Fix N+1 Query Problems
AI frequently generates N+1 patterns. Force JOINs:
```sql
-- ❌ REJECT — N+1: one query per user's orders
SELECT * FROM users;
-- Then for each user: SELECT * FROM orders WHERE user_id = $1

-- ✅ REQUIRE — single JOIN query
SELECT 
    u.id,
    u.name,
    u.email,
    COUNT(o.id) AS order_count,
    SUM(o.total) AS lifetime_value
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
GROUP BY u.id, u.name, u.email;
```

### 4. Use Transactions for Multi-Step Operations
```sql
-- ✅ Wrap related mutations in a transaction
BEGIN;
    INSERT INTO orders (user_id, total) VALUES ($1, $2) RETURNING id;
    UPDATE inventory SET stock = stock - $3 WHERE product_id = $4;
    INSERT INTO order_items (order_id, product_id, quantity) VALUES ($5, $4, $3);
COMMIT;
-- ROLLBACK on any failure
```

### 5. Index Strategy — Tell the AI to Generate Indexes
```sql
-- ✅ Always create indexes for FK columns and common WHERE clauses
CREATE INDEX CONCURRENTLY idx_orders_user_id ON orders(user_id);
CREATE INDEX CONCURRENTLY idx_orders_created_at ON orders(created_at DESC);
CREATE INDEX CONCURRENTLY idx_users_email ON users(email); -- for login lookups
```

### 6. Use `EXPLAIN ANALYZE` Prompt Pattern
For performance-critical queries, ask the AI to show the query plan:
```
Write this query and then provide the EXPLAIN ANALYZE output format
with explanations of what to look for (sequential scans vs index scans,
estimated vs actual rows, etc.)
```

### 7. Soft Deletes Pattern
```sql
-- ✅ Never hard-delete production data without explicit confirmation
-- Use soft delete with timestamp
ALTER TABLE users ADD COLUMN deleted_at TIMESTAMPTZ;

-- ✅ Always filter in application queries
SELECT id, name, email 
FROM users 
WHERE deleted_at IS NULL AND id = $1;
```

---

## 🚫 AI Pitfalls to Watch for in SQL

| Pitfall | What to Look For | How to Fix |
|---------|-----------------|------------|
| SQL Injection | String concatenation in queries | Always use $1/$2 parameters |
| `SELECT *` | `SELECT *` in any application query | Specify explicit column list |
| N+1 queries | Loop with DB query inside | Use JOIN or batch fetch |
| Missing indexes | No `CREATE INDEX` alongside `CREATE TABLE` | Add indexes for FK and filter columns |
| No transactions | Multi-step mutations without BEGIN/COMMIT | Wrap in transaction |
| `DELETE` without `WHERE` | `DELETE FROM table` | Always add `WHERE` clause |

---

## 📋 Prompt Template for SQL

```
You are a senior database engineer (PostgreSQL 17).
Write SQL following these rules:
- ALL queries must use parameterized inputs ($1, $2...) — NEVER string concatenation
- NEVER use SELECT * — always specify explicit column names
- Identify and eliminate N+1 patterns — use JOINs and batch operations
- Wrap all multi-step mutations in transactions (BEGIN/COMMIT)
- Include relevant CREATE INDEX statements alongside CREATE TABLE
- Add soft-delete columns (deleted_at TIMESTAMPTZ) and always filter WHERE deleted_at IS NULL

TASK: [Your task here]
```
