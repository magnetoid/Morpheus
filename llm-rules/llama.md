# Llama (Meta) — Vibe Coding Rules & Strategies

> **Role:** The Local, Air-Gapped, Cost-Free Workhorse
> **Best Models (2026):** Llama 4 70B, Llama 4 8B (fast local), Code Llama 4
>
> **See also:** [../docs/universal-principles.md](../docs/universal-principles.md), [../docs/workflow-guide.md](../docs/workflow-guide.md), [../AGENTS.md](../AGENTS.md).

---

## Model Personality Profile

Llama is the gold standard for **local, private, cost-free AI coding**. Running via Ollama, LM Studio, or vLLM, Llama gives you frontier-adjacent coding assistance with zero API costs and zero data leaving your machine. In 2026, Llama 4 70B delivers near-frontier performance for most coding tasks on capable hardware (64GB+ unified memory or a 24GB GPU).

**Strengths:**

- Zero cost, fully private, offline-capable
- No rate limits — ideal for automated batch pipelines
- Predictable latency (no cloud variance)
- Permissive license for commercial use
- Strong fine-tuning ecosystem

**Weaknesses:**

- Requires local hardware (16–80GB RAM depending on size)
- Knowledge cutoff is older than cloud frontier models
- Needs careful prompting to maintain frontier-level quality
- Output style drifts more than Claude/GPT without strong system prompt

---

## ✅ Core Rules for Llama (Local)

### Rule 1: Always Set a Strong System Prompt

Without a system prompt, Llama is overly casual or verbose. Configure it in Ollama's `Modelfile` or your application's system prompt:

```text
You are a senior software engineer. Write production-quality, secure, and
maintainable code. Never truncate code or use placeholders. If you are unsure
about a library API, say so explicitly rather than guessing. Follow best
practices for the specified language version. Output code first, prose second.
```

### Rule 2: Choose the Right Model Size for Your Hardware

| Hardware | Recommended Model | Speed |
| --- | --- | --- |
| 16GB RAM (M-series Mac) | Llama 4 8B Q8 | Fast |
| 32GB RAM | Llama 4 14B Q4 | Moderate |
| 64GB RAM | Llama 4 70B Q4 | Good |
| GPU (24GB VRAM) | Llama 4 70B Q8 | Fast |
| GPU (48GB+ VRAM) | Llama 4 70B FP16 | Frontier-adjacent |

### Rule 3: Use for Automated Batch Processing

Llama's no-rate-limit advantage makes it ideal for automated pipelines:

- Bulk docstring generation across an entire codebase
- Automated code formatting and style fixes
- Mass unit test generation for legacy functions
- Automated lint-style code review scripts

```bash
# Example: Generate docstrings for every Python file in a project
for file in src/**/*.py; do
  ollama run llama4 "Add NumPy-style docstrings to undocumented functions
  in this file. Return only the updated file:\n$(cat "$file")" > "$file.new"
done
```

### Rule 4: Specify Library Versions Explicitly

Llama has a knowledge cutoff and may not know the latest APIs:

```text
I am using React 19.1, Next.js 15 App Router, TypeScript 5.7.
Do NOT use deprecated React patterns (no class components, no legacy context).
Use the modern React 19 `use()` hook for data fetching where appropriate.
```

### Rule 5: Use Structured Prompting for Consistency

Llama benefits from clear structure (less critical than Claude, but valuable):

```text
TASK: Generate a REST API endpoint
LANGUAGE: TypeScript (strict mode)
FRAMEWORK: Express 5.x
REQUIREMENT: POST /api/users — creates a new user with name and email
VALIDATION: Zod schema validation on request body
ERROR HANDLING: Typed JSON error responses with appropriate HTTP status codes
OUTPUT: Complete, runnable TypeScript file only. No prose.
```

### Rule 6: Implement a Local Quality Gate

Since Llama is less reliable per-token than cloud frontier models, automate verification:

- **TypeScript:** Run `tsc --noEmit` immediately after generation.
- **Python:** Run `ruff check` + `mypy` immediately after generation.
- **Any language:** Run the existing test suite against generated code.

The verification table from [../docs/workflow-guide.md](../docs/workflow-guide.md) phase 4 is mandatory for Llama output — more so than for Claude.

### Rule 7: Pair with Frontier Models for Hard Reasoning

Use Llama as the *generator* in a pipeline where the *planner* is a stronger cloud model:

1. **Claude / Gemini** (cloud, planning only) — produce a step-by-step plan.
2. **Llama 4 70B** (local, generation only) — implement each step from the plan.

This way nothing proprietary leaves the local machine *during generation*, but you still benefit from frontier reasoning at the planning stage (where the input can be a sanitized spec, not the actual code).

---

## 🧪 Llama-Specific Workflow: The "Bulk Backfill" Pattern

Ideal for adding test coverage, docstrings, or types to a legacy codebase:

1. **Inventory:** List all files lacking tests / docstrings / types.
2. **Loop:** For each file, run a focused Llama prompt with a strict system prompt.
3. **Auto-verify:** Run `tsc` / `mypy` / test suite on each generated file.
4. **Reject and retry:** Files that fail verification go to a retry queue with an enhanced prompt.
5. **Human review:** Spot-check 10% of generated files manually before merging.

This pattern uses Llama's zero-cost, no-rate-limit advantage at full leverage.

---

## 🚫 Anti-Patterns for Llama

| Anti-pattern | Why it fails | Do this instead |
| --- | --- | --- |
| No system prompt | Output drifts to casual / verbose | Set strict system prompt in Modelfile |
| Llama 8B for complex multi-file refactor | 8B is for completions, not architecture | Use 70B for complex tasks |
| Skipping the local quality gate | Hallucinated APIs slip into commits | Auto-run type checker after every generation |
| Assuming current framework knowledge | Knowledge cutoff is older than cloud models | Specify exact versions in every prompt |
| Using Llama for real-time ecosystem questions | Llama is offline | Use Grok for current ecosystem info |

---

## 🚫 Common Mistakes to Avoid

| Mistake | Instead |
| --- | --- |
| No system prompt | Always configure a strict system prompt in Modelfile |
| Using Llama 8B for complex multi-file refactoring | Use 70B for complex tasks; 8B for simple completions |
| Not verifying generated code with type checkers | Auto-run `tsc` or `mypy` after every generation |
| Assuming it knows the latest library syntax | Always specify exact versions and any recent changes |
| Using it for tasks requiring real-time knowledge | Llama is offline; use Grok for current ecosystem info |
