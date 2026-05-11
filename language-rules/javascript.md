# JavaScript — Vibe Coding Rules (2026)

> Apply these rules whenever asking any AI to generate, review, or modify JavaScript code.
>
> **See also:** [../docs/universal-principles.md](../docs/universal-principles.md) (the 9 pillars), [../docs/workflow-guide.md](../docs/workflow-guide.md) (the loop), [../AGENTS.md](../AGENTS.md) (the protocols).

---

## 🟡 JavaScript Version & Standard

**Target: ESNext (ES2024+), Node.js 22 LTS**

---

## ✅ Mandatory Rules

### 1. Modern ES Module Syntax (No CommonJS)
```javascript
// ❌ REJECT
const express = require('express');
module.exports = { handler };

// ✅ REQUIRE
import express from 'express';
export { handler };
```

### 2. `const` by Default
```javascript
// ❌ REJECT var entirely. Limit let to reassignment cases.
var userName = 'Alice';

// ✅ REQUIRE const unless reassignment is necessary
const userName = 'Alice';
```

### 3. Never Use `innerHTML` for User Data (XSS Prevention)
```javascript
// ❌ REJECT — XSS vulnerability
element.innerHTML = userInput;

// ✅ REQUIRE — Use textContent or DOMPurify
element.textContent = userInput;
// Or sanitize: element.innerHTML = DOMPurify.sanitize(userInput);
```

### 4. Always Await Promises (No Floating Promises)
```javascript
// ❌ REJECT — unhandled promise
fetchData().then(process);

// ✅ REQUIRE — always await in async context
const data = await fetchData();
await process(data);
```

### 5. Use Optional Chaining and Nullish Coalescing
```javascript
// ❌ REJECT verbose null checks
const name = user && user.profile && user.profile.name ? user.profile.name : 'Anonymous';

// ✅ REQUIRE modern operators
const name = user?.profile?.name ?? 'Anonymous';
```

### 6. Environment Variables Only (No Hardcoded Values)
```javascript
// ❌ REJECT
const API_KEY = 'sk-abc123xyz';

// ✅ REQUIRE
const API_KEY = process.env.API_KEY;
if (!API_KEY) throw new Error('API_KEY environment variable is required');
```

### 7. Use `structuredClone` for Deep Copies
```javascript
// ❌ REJECT
const copy = JSON.parse(JSON.stringify(obj));

// ✅ REQUIRE
const copy = structuredClone(obj);
```

---

## 🚫 AI Pitfalls to Watch for in JavaScript

| Pitfall | What to Look For | How to Fix |
|---------|-----------------|------------|
| XSS via innerHTML | `element.innerHTML = data` | Use `textContent` or sanitize |
| `var` declarations | Any `var` keyword | Replace with `const`/`let` |
| CommonJS syntax | `require()` / `module.exports` | Use ES module `import`/`export` |
| Floating promises | `.then()` without `await` | Add `await` |
| `eval()` usage | Any `eval(...)` | Remove — never use `eval` |
| Prototype pollution | Object spread with user input | Validate and whitelist properties |

---

## 📋 Prompt Template for JavaScript

```
You are a senior JavaScript engineer. Write ESNext code for Node.js 22 LTS:
- Use ES Modules (import/export) — no CommonJS
- const by default, let only when reassignment is needed, never var
- All async I/O must use async/await
- Never use innerHTML with user data — use textContent or DOMPurify
- Never hardcode secrets — use process.env with validation
- Use optional chaining (?.) and nullish coalescing (??) throughout
- No eval(), no with statements

TASK: [Your task here]
```
