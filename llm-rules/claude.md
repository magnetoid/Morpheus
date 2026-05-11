# Claude (Anthropic) — Vibe Coding Rules & Strategies

> **Role:** The Architect & Refactor Master
> **Best Models (2026):** Claude Opus 4.7, Claude Sonnet 4.6, Claude Haiku 4.5
>
> **See also:** [../docs/universal-principles.md](../docs/universal-principles.md), [../docs/workflow-guide.md](../docs/workflow-guide.md), [../AGENTS.md](../AGENTS.md).

---

## Model Personality Profile

Claude is widely recognized as the gold standard for **complex reasoning, system architecture, and production-grade code quality**. It excels at following long, structured instructions with rigorous consistency. In 2026, Anthropic has shifted the paradigm toward "Context Engineering" — structuring inputs precisely to guide Claude's powerful reasoning engine.

**Strengths:**
- Deep, multi-step logical reasoning
- Rigorous adherence to complex constraints and style guides
- Exceptional quality in refactoring and architectural transformations
- Highly resistant to generating obviously insecure patterns

**Weaknesses:**
- Can over-engineer simple solutions (creates unnecessary abstractions)
- Slower on simple/trivial tasks compared to lighter models
- May occasionally be overly cautious or add excessive caveats

---

## ✅ Core Rules for Claude

### Rule 1: Use XML Tags for Structured Prompts
Claude's architecture is trained to parse XML tags for context separation. This is the single highest-leverage prompting technique for Claude.

```xml
<context>
  This is a Next.js 15 application using the App Router, Prisma ORM, and PostgreSQL.
  The coding style uses strict TypeScript with no `any` types.
</context>

<code>
  // Paste existing code here
</code>

<task>
  Refactor the `getUserById` function to use the repository pattern.
  Extract database logic into a `UserRepository` class.
</task>

<constraints>
  - Keep the solution as simple as possible. No unnecessary abstractions.
  - Do not introduce any new dependencies.
  - Maintain full backwards compatibility with the existing function signature.
</constraints>

<output_format>
  Provide: 1) The new UserRepository class, 2) The updated getUserById function.
  Do NOT provide explanatory prose — only the code blocks.
</output_format>
```

### Rule 2: Apply the 4-Block Prompt Pattern
Structure every non-trivial prompt in this order:
1. **Instructions** — What does "done" look like?
2. **Context** — What is the relevant background?
3. **Task** — What specific action should be taken?
4. **Output Format** — Exactly how should the response be structured?

### Rule 3: Delegate Heavy Architecture & Refactoring
Claude is uniquely suited for tasks that require reasoning about the *entire* system, not just a single function. Use Claude when you need to:
- Apply SOLID principles to an existing module
- Extract a service layer from a monolithic component
- Refactor a complex state management solution
- Audit and redesign an authentication flow

**Example Prompt:**
```
<task>
  Analyze this Express.js router file and refactor it to separate:
  1. Route definitions (thin controllers)
  2. Business logic (service layer)
  3. Data access (repository layer)
  Apply the Repository Pattern. Use strict TypeScript throughout.
</task>
```

### Rule 4: Use Socratic Prompting for Unknown Requirements
Instead of making assumptions, ask Claude to surface hidden requirements:

```
Before writing any code, identify the top 5 questions whose answers would 
most significantly change the implementation of this feature. Ask me those 
questions one at a time before proceeding.
```

### Rule 5: Counter Over-Engineering
Claude tends to create multiple layers of abstraction. Prevent this explicitly:

```
Keep the solution as simple as possible without unnecessary abstractions.
Prefer a flat, readable implementation over a "clever" or over-engineered one.
Use inline logic rather than creating new helper functions or classes unless
they are clearly reused in at least 3 places.
```

### Rule 6: Chain-of-Thought for Complex Algorithms
For algorithmic or multi-step logical tasks, explicitly enable step-by-step reasoning:

```
Think through this step by step before writing any code:
1. First, analyze the current data flow.
2. Then, identify the exact bottleneck.
3. Finally, propose a refactored implementation.

Show your reasoning before the code.
```

### Rule 7: Uncertainty Handling
Instruct Claude to admit uncertainty rather than hallucinate:

```
If you are unsure about a specific library API, version, or method signature,
explicitly state "I am not certain about this API — please verify against the docs."
Do NOT guess or hallucinate a plausible-sounding method name.
```

---

## 🧪 Claude-Specific Workflow: The "Deep Refactor" Pattern

This workflow is ideal for inheriting a messy codebase and making it production-ready:

1. **Ingestion:** *"Read all files in `src/services/`. Produce a 1-paragraph summary of what each file does and identify any architectural anti-patterns."*
2. **Planning:** *"Based on your analysis, propose an improved architecture. Do not write any code yet."*
3. **Approval:** Review and approve (or modify) the proposed architecture.
4. **Execution:** *"Now implement the changes to `UserService.ts` as proposed. Provide the complete file."*
5. **Testing:** *"Write the Jest unit tests for the new `UserService.ts`."*

---

## 🚫 Common Mistakes to Avoid with Claude

| Mistake | Instead |
|---------|---------|
| Vague prompt: "Make this better" | Specific: "Improve error handling in `fetchUser()` to catch network errors and return a typed `Result<T, E>`" |
| Asking for everything at once | Break into: schema → service → controller → tests |
| Ignoring over-engineering | Add: "Keep this as simple as possible" to every refactor prompt |
| Not specifying output format | Add: "Provide only the code. No explanatory prose." |
| Long conversation threads | Start fresh sessions with a `context.md` summary |
