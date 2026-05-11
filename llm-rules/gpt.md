# GPT (OpenAI) — Vibe Coding Rules & Strategies

> **Role:** The Versatile Prototyper & Creative Engine
> **Best Models (2026):** GPT-5 (versatile generalist), o4-class reasoning models (deep reasoning / debugging), GPT-4o (still competitive for fast UI work)
>
> **See also:** [../docs/universal-principles.md](../docs/universal-principles.md), [../docs/workflow-guide.md](../docs/workflow-guide.md), [../AGENTS.md](../AGENTS.md).

---

## Model Personality Profile

OpenAI's models span a critical spectrum in 2026:
- **GPT-4o**: Fast, versatile, excellent at creative generation and UI work. Great for rapid zero-to-one prototyping.
- **o3 (Reasoning Model)**: Performs internal chain-of-thought. Best for deep algorithmic problems, architectural debates, and systematic debugging. Slower, but dramatically more accurate for complex tasks.

**Knowing which model to use is the most critical GPT skill.**

**GPT-4o Strengths:**
- Rapid prototyping and UI generation
- Broad knowledge across many frameworks
- Excellent at "persona-based" role-playing prompts
- Fast iteration speed

**o3 Strengths:**
- Complex algorithmic reasoning
- Multi-step debugging across files
- Architecture trade-off analysis

**Shared Weaknesses:**
- Tendency to truncate long outputs (placeholders like `// ... rest of code`)
- Can introduce subtle logic bugs in complex multi-file changes
- May confidently hallucinate non-existent library methods

---

## ✅ Core Rules for GPT-4o

### Rule 1: Match Model to Task

| Task | Use |
|------|-----|
| Building a UI component | GPT-4o |
| Rapid prototyping | GPT-4o |
| Generating multiple variations | GPT-4o |
| Writing boilerplate/CRUD | GPT-4o |
| Complex bug debugging | o3 |
| Architectural trade-off analysis | o3 |
| Optimizing a complex algorithm | o3 |
| Security audit | o3 or Claude |

### Rule 2: Use Strong Persona Prompting (GPT-4o)
GPT-4o responds exceptionally well to role-based prompting. Establishing a persona dramatically shapes the quality and style of the output.

**Effective Persona Templates:**
```
Act as a Senior Staff Frontend Engineer at a top-tier tech company.
You build beautiful, performant, accessible web UIs. 
You use React 19, TypeScript strict mode, and Tailwind CSS.
You never compromise on accessibility (WCAG 2.2 AA).
```

```
Act as a Security-First Backend Engineer.
You write defensive code by default — assume all user inputs are malicious.
Use parameterized queries, validate all inputs with Zod, and log all errors.
```

### Rule 3: The Anti-Truncation Protocol (CRITICAL)
GPT-4o's most notorious failure mode is truncating long outputs with placeholders.
**Always append this to prompts involving full file generation:**

```
CRITICAL INSTRUCTION: You MUST provide the COMPLETE, FULLY FUNCTIONAL file.
Do NOT truncate, omit code sections, or use placeholders like:
- "// ... existing code ..."
- "// rest of implementation"
- "// TODO"
If the output is long, continue generating until the ENTIRE file is complete.
```

### Rule 4: Use Positive Framing (Tell It What TO Do)
GPT-4o responds better to affirmative instructions than negative ones.

| ❌ Negative (Weaker) | ✅ Positive (Stronger) |
|---------------------|----------------------|
| "Don't use external libraries" | "Use only the Node.js standard library" |
| "Don't write messy code" | "Write clean, self-documenting code with single-responsibility functions" |
| "Don't use var" | "Use only `const` and `let`" |

### Rule 5: Use Delimiters to Separate Context from Instructions
Place instructions first, then context. Use clear delimiters:

```
### TASK
Refactor the function below to use async/await instead of callbacks.

### CONSTRAINTS
- Do not change the function signature.
- TypeScript strict mode is active.

### CODE TO REFACTOR
"""
function fetchUser(id, callback) { ... }
"""
```

### Rule 6: Leverage Rapid Variation Generation
GPT-4o excels at generating multiple stylistic variations. Use it for UI "vibe exploration":

```
Generate 3 variations of this login card component:
1. Minimalist / clean (think Linear.app)
2. Glassmorphic / dark mode (think Vercel dashboard)
3. Bold / colorful (think Stripe marketing site)

For each variation, provide complete JSX and Tailwind CSS classes.
```

---

## ✅ Core Rules for o3 (Reasoning Model)

### Rule 1: Keep Prompts Simple and Goal-Oriented
o3 performs its own internal chain-of-thought. Adding explicit "think step by step" instructions can actually **degrade** its performance by interrupting its internal reasoning process.

| ❌ For o3 | ✅ For o3 |
|-----------|----------|
| "Think step by step about why this fails" | "Debug why this function returns undefined for null inputs" |
| "Let's go through this one step at a time" | "Find all edge cases in this sorting algorithm" |

### Rule 2: Use o3 for Deep Debugging
Provide the full error trace, the relevant files, and a direct question:

```
The following error occurs when calling `processPayment()`:
[ERROR TRACE]

Relevant files are attached. Identify the root cause and provide the fix.
```

### Rule 3: Architecture Trade-Off Analysis
o3 is excellent at evaluating architectural decisions:

```
I need to choose between:
A) Event-driven microservices with Kafka
B) Monolith with async job queues (BullMQ)

My constraints: 3-person team, <10k daily active users, 18-month MVP timeline.
Analyze the trade-offs and make a concrete recommendation with justification.
```

---

## 🚫 Common Mistakes to Avoid

| Mistake | Instead |
|---------|---------|
| Using o3 for a simple UI component | Use GPT-4o — o3 is overkill |
| Using GPT-4o for deep multi-file debugging | Use o3 — it has better internal reasoning |
| No anti-truncation instruction | Always add the CRITICAL INSTRUCTION block |
| Negative constraints | Reframe as positive instructions |
| One mega-prompt for entire feature | Break into atomic steps with verification loops |
