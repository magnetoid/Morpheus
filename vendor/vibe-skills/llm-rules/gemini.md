# Gemini (Google) — Vibe Coding Rules & Strategies

> **Role:** The Deep Context Analyzer & Multimodal Reasoner
> **Best Models (2026):** Gemini 3 Pro, Gemini 3 Flash, Gemini 2.5 Pro (still competitive)
>
> **See also:** [../docs/universal-principles.md](../docs/universal-principles.md), [../docs/workflow-guide.md](../docs/workflow-guide.md), [../AGENTS.md](../AGENTS.md).

---

## Model Personality Profile

Gemini's defining superpower is its **industry-leading context window** (millions of tokens) and its **multimodal capabilities** — it can process code, diagrams, screenshots, PDFs, and log files simultaneously. In 2026, Gemini 2.5 Pro is the go-to model for tasks requiring whole-repository analysis or the ingestion of extensive external documentation.

**Strengths:**
- Ingesting entire codebases, documentation sites, or server log dumps
- Cross-file bug tracing and system-level analysis
- Multimodal reasoning (connecting UI screenshots to underlying code logic)
- Extremely fast processing speed at large context scales
- Spec-driven workflow orchestration

**Weaknesses:**
- Can sometimes be less precise with strict syntactical generation than Claude
- May be verbose or provide excessive explanations when concise code is needed
- Quality can drift if provided with irrelevant context (despite large window)

---

## ✅ Core Rules for Gemini

### Rule 1: Leverage the Context Window Aggressively
Gemini's context window is its primary advantage. Use it for tasks that would overwhelm other models:

```
I am uploading my entire project codebase (attached).
Please do the following:
1. Map the complete data flow from the frontend API call → backend service → database layer.
2. Identify all components that touch the `user` entity.
3. Flag any potential security vulnerabilities in the user data handling path.
```

### Rule 2: Use a Strong System Instruction / Persona
Setting a clear role in the system instruction (or beginning of the prompt) significantly sharpens Gemini's judgment and output style:

```
You are a Senior Software Architect specializing in distributed systems and cloud-native 
applications. You prioritize reliability, maintainability, and observability over clever 
syntax. You follow our project's established modular patterns. 
When uncertain about our project's conventions, ask rather than invent.
```

### Rule 3: The Spec-Driven Workflow (Gemini's Ideal Pattern)
Gemini excels at orchestrating the entire spec-to-code lifecycle:

**Step 1 — Brainstorm:**
```
I want to build [feature description]. Let's brainstorm together.
Ask me questions to help flesh out the full requirements, edge cases, and constraints.
```

**Step 2 — Spec Generation:**
```
Based on our discussion, compile a formal technical specification.
Include: data models, API endpoints, component structure, and error handling strategy.
Output as a structured Markdown document.
```

**Step 3 — Targeted Execution (new sessions):**
```
[Feed the spec into a new session]
Using this spec as the source of truth, implement ONLY the [specific component].
```

### Rule 4: Multimodal Input — Combine Visuals with Code
Gemini's multimodal capabilities are a unique advantage. Upload alongside your prompts:
- **UI Screenshots**: "Fix this layout bug — the screenshot shows the current broken state."
- **Architecture Diagrams**: "Implement the service described in this system architecture diagram."
- **Error Screenshots**: "Debug this — here's a screenshot of the error in the browser console."
- **API Docs PDFs**: "Based on this documentation PDF, write a client wrapper for the Stripe API."

### Rule 5: Cross-File Bug Hunting
Gemini's large context window makes it uniquely powerful for distributed bugs:

```
I'm attaching:
- The full server error logs (last 500 lines)
- The 4 files most likely related to this error: [list files]

The error occurs intermittently when users submit the checkout form.
Trace the root cause through the logs and code. Identify the exact line 
causing the failure and propose a fix.
```

### Rule 6: Repository-Wide Auditing
Use Gemini as a "codebase health scanner":

```
Perform a full audit of the attached codebase. Identify:
1. All instances of hardcoded secrets or credentials
2. All unparameterized SQL queries (SQL injection risks)
3. All components exceeding 400 lines that should be refactored
4. All TODO comments that represent unfinished work

Provide findings as a prioritized list with file names and line numbers.
```

### Rule 7: Use Gemini as the "Brains", Claude/GPT as the "Hands"
This is the Strategic Stack principle:
1. **Use Gemini** to analyze the problem, identify the approach, and generate a plan.
2. **Pass Gemini's analysis** to Claude or GPT to write the precise, final code.

**Example:**
```
[Gemini prompt]
Analyze the performance bottleneck in this service layer. 
Identify the root cause and propose a concrete refactoring strategy.
Do NOT write the code — just provide the analysis and strategy.

[Claude prompt with Gemini's output]
Based on this analysis: [paste Gemini's output]
Implement the proposed refactoring for `UserService.ts`. 
Provide the complete updated file.
```

### Rule 8: Use a `GEMINI.md` File for Persistent Context
Create a `GEMINI.md` (or `docs/context-template.md`) file in your project and reference it at the start of every session:

```
Read GEMINI.md first. It contains our project's architecture, conventions, 
and decisions log. Acknowledge when ready to proceed.
```

---

## 🚫 Common Mistakes to Avoid

| Mistake | Instead |
|---------|---------|
| Dumping entire repo without a focused question | Combine large context with a precise, scoped question |
| Using Gemini only for code generation | Leverage its analysis, planning, and multimodal strengths |
| Ignoring multimodal inputs | Upload diagrams, screenshots, and PDFs alongside code |
| Not using the Spec-Driven workflow | Brainstorm → Spec → Execute (in separate sessions) |
| Starting a session without context | Always reference `context-template.md` at session start |
