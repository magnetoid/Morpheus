# DeepSeek — Vibe Coding Rules & Strategies

> **Role:** The Efficient Reasoner & Algorithm Champion
> **Best Models (2026):** DeepSeek R2, DeepSeek V3.2, DeepSeek Coder V3
>
> **See also:** [../docs/universal-principles.md](../docs/universal-principles.md), [../docs/workflow-guide.md](../docs/workflow-guide.md), [../AGENTS.md](../AGENTS.md).

---

## Model Personality Profile

DeepSeek has established itself in 2026 as a **cost-efficient, high-reasoning powerhouse**. The R2 model features a "reasoning-first" architecture — it thinks and validates before outputting code, making it exceptionally accurate for algorithmic and logic-heavy tasks. It often rivals frontier proprietary models on coding benchmarks at a fraction of the cost, making it ideal for high-volume, automated workflows.

**Strengths:**
- Exceptional algorithmic accuracy and edge-case detection
- Transparent chain-of-thought reasoning traces
- Outstanding performance-to-cost ratio (ideal for API-heavy automation)
- Excellent at generating comprehensive test suites
- Strong in backend/server-side logic and mathematical computation

**Weaknesses:**
- May struggle with modern UI "vibes" (Tailwind aesthetics, animations)
- Less trained on the very latest framework releases vs. GPT-4o
- Can be slower than GPT-4o for simple/trivial tasks

---

## ✅ Core Rules for DeepSeek R2

### Rule 1: Embrace the Reasoning Trace
DeepSeek R2's "think-before-output" is a feature, not a bug. Unlike o3 (where you shouldn't add CoT instructions), for DeepSeek you can explicitly request visible reasoning to validate the approach before accepting the code:

```
Before writing any code, think through the following:
1. What are the edge cases for this function?
2. What data structures would be most efficient?
3. What is the time and space complexity of your proposed approach?

Show your reasoning, then provide the implementation.
```

### Rule 2: Use for Algorithmic & Complex Logic Tasks
DeepSeek is your go-to model when correctness is more important than speed:
- Sorting, searching, graph traversal algorithms
- Data transformation pipelines
- Mathematical computations (statistics, finance, ML preprocessing)
- Parser and compiler logic
- Concurrency and async coordination patterns

**Example Prompt:**
```
Implement a rate limiter using the Token Bucket algorithm in TypeScript.
Requirements:
- Thread-safe (works with async/concurrent requests)
- Configurable: capacity (max tokens), refill rate (tokens/second)
- Returns a Result<boolean, RateLimitError> type
- Include time complexity analysis in a comment

Reason through the approach before coding.
```

### Rule 3: Comprehensive Test Suite Generation
DeepSeek's strength in edge-case detection makes it the best model for generating exhaustive test suites:

```
Write a comprehensive Jest test suite for the `processPayment()` function below.

Cover ALL of the following:
- Happy path (successful payment)
- Network timeout errors
- Invalid card number formats
- Insufficient funds
- Expired card
- Currency format edge cases (0.001, 999999.99, negative values)
- Concurrent duplicate requests
- Null and undefined inputs
- Rate limiting / retry scenarios

Ensure each test has a descriptive name that explains what it is testing.
```

### Rule 4: API-Driven Automation (Cost-Efficient Bulk Tasks)
Because DeepSeek offers frontier-quality reasoning at much lower cost per token, it's ideal for automated, high-volume workflows:
- Bulk docstring generation across a large codebase
- Automated code review passes (lint suggestions)
- Batch unit test generation for legacy functions
- Automated migration script generation

**Pro Tip:** Build a pipeline that sends each function in your codebase to DeepSeek via API and generates docstrings or tests automatically.

### Rule 5: Use for Code Review & Security Auditing
DeepSeek's reasoning trace makes its audit findings more trustworthy:

```
Perform a security audit of this function. 
Reason through each potential vulnerability before listing your findings.

For each vulnerability found, provide:
1. Severity (Critical / High / Medium / Low)
2. Type (OWASP category)
3. The exact vulnerable line
4. A corrected code snippet
```

### Rule 6: Complement with GPT-4o for UI Work
For projects requiring both algorithmic backend logic AND polished UI:
- **DeepSeek R2** → Backend services, data processing, algorithms, tests
- **GPT-4o** → Frontend components, UI animations, user experience

---

## 🚫 Common Mistakes to Avoid

| Mistake | Instead |
|---------|---------|
| Using DeepSeek for Tailwind/CSS-heavy UI | Use GPT-4o for aesthetic UI work |
| Ignoring the reasoning trace | Read the trace — it shows you the model's assumptions |
| Using it for trivial one-liners | Save it for complex logic where accuracy matters |
| Not leveraging API for bulk tasks | Automate repetitive generation at low cost via API |
| Asking for framework-specific UX patterns | Verify output against official framework docs |
