# TypeScript — Vibe Coding Rules (2026)

> Apply these rules whenever asking any AI to generate, review, or modify TypeScript code.
>
> **See also:** [../docs/universal-principles.md](../docs/universal-principles.md) (the 9 pillars), [../docs/workflow-guide.md](../docs/workflow-guide.md) (the loop), [../AGENTS.md](../AGENTS.md) (the protocols).

---

## 🔷 TypeScript Version & Standard

**Target: TypeScript 5.7+ with Strict Mode**
Always specify the framework and TS version. Strict mode is non-negotiable.

```
# Add to every TypeScript prompt:
"Use TypeScript 5.7+ with strict mode enabled. No `any` types."
```

---

## ✅ Mandatory Rules

### 1. Strict Mode is Always On
Your `tsconfig.json` must include — and the AI must respect:
```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "noUncheckedIndexedAccess": true
  }
}
```
Add to every prompt: *"Strict mode is active. Handle all null/undefined cases explicitly."*

### 2. Absolute Ban on `any`
```typescript
// ❌ REJECT immediately
const data: any = await fetch(url);
function processData(input: any) {}

// ✅ REQUIRE proper typing
const data: UserResponse = await fetch(url).then(r => r.json());
function processData(input: ProcessInput): ProcessResult {}

// ✅ If truly unknown, use `unknown` and narrow it
function processUnknown(input: unknown): string {
  if (typeof input === 'string') return input;
  throw new TypeError('Expected string');
}
```

### 3. Zod for Runtime Validation
Type safety at compile time is not enough. Validate API responses and user inputs at runtime:
```typescript
import { z } from 'zod';

const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  name: z.string().min(1).max(100),
  createdAt: z.coerce.date(),
});

type User = z.infer<typeof UserSchema>;

// Validate API response at runtime
const user = UserSchema.parse(await response.json());
```

### 4. Result Types for Error Handling (No Thrown Exceptions in Business Logic)
```typescript
// Define a Result type
type Result<T, E = Error> = 
  | { success: true; data: T }
  | { success: false; error: E };

// ✅ Return Results instead of throwing
async function getUser(id: string): Promise<Result<User>> {
  try {
    const user = await db.user.findUnique({ where: { id } });
    if (!user) return { success: false, error: new Error('User not found') };
    return { success: true, data: user };
  } catch (e) {
    return { success: false, error: e instanceof Error ? e : new Error(String(e)) };
  }
}
```

### 5. Use `const` and Immutable Patterns
```typescript
// ❌ REJECT
let config = { url: '', timeout: 0 };

// ✅ REQUIRE
const config = {
  url: process.env.API_URL ?? '',
  timeout: 5000,
} as const;
```

### 6. Discriminated Unions for State Management
```typescript
// ✅ Model all possible states explicitly
type RequestState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: string };
```

---

## 🚫 AI Pitfalls to Watch for in TypeScript

| Pitfall | What to Look For | How to Fix |
|---------|-----------------|------------|
| `any` types | `any` anywhere in generated code | Replace with proper types or `unknown` |
| Missing null checks | `user.name.length` without null guard | Use optional chaining `user?.name?.length` |
| Non-null assertions | `user!.email` | Explicitly handle the null case |
| `as` type casting | `data as User` | Use Zod `.parse()` for runtime validation |
| Missing `await` | `const user = fetchUser()` | Ensure all Promises are awaited |
| `enum` usage | TypeScript `enum` | Prefer `as const` objects or string unions |

---

## 📋 Prompt Template for TypeScript

```
You are a senior TypeScript engineer. Write TypeScript 5.7+ code following these rules:
- Strict mode enabled (noImplicitAny, strictNullChecks, noUncheckedIndexedAccess)
- Absolutely NO `any` types — use `unknown` with narrowing when type is uncertain
- Runtime validation with Zod for all external data (API responses, user input)
- `const` by default; only `let` when reassignment is needed
- Discriminated unions for all possible state representations
- Result<T,E> pattern for business logic error handling

TASK: [Your task here]
```
