# GitHub Copilot — Vibe Coding Rules & Strategies

> **Role:** The IDE-Native Team Collaborator
> **Interfaces (2026):** VS Code, JetBrains, Neovim, GitHub.com, Copilot Workspace
>
> **See also:** [../docs/universal-principles.md](../docs/universal-principles.md), [../docs/workflow-guide.md](../docs/workflow-guide.md), [../AGENTS.md](../AGENTS.md).

---

## Model Personality Profile

GitHub Copilot in 2026 is more than autocomplete — it's a full agentic tool embedded in your existing IDE, with Copilot Workspace for multi-file edits and Copilot Code Review for PR-time analysis. Its strength is **low-friction, in-editor assistance** that respects your existing project conventions without requiring context switching.

**Strengths:**

- Deepest IDE integration of any agent (VS Code, JetBrains, Neovim native)
- Repo-aware context via `#file:`, `#sym:`, and `@workspace` references
- Enterprise governance (content exclusions, audit logs, private model routing)
- Copilot Workspace for multi-file feature work
- Strong fit for team workflows (PR review, issue-to-code)

**Weaknesses:**

- Reasoning depth is below standalone Claude or o-series models
- Quality depends heavily on the instruction file (`copilot-instructions.md`)
- Free-form chat mode is less polished than Claude or GPT
- Can over-rely on the most-recently-edited file as context

---

## ✅ Core Rules for GitHub Copilot

### Rule 1: Create a `copilot-instructions.md` File

Place this in `.github/copilot-instructions.md` or the project root. Copilot reads it automatically:

```markdown
# Copilot Instructions

## Tech Stack
- Framework: Next.js 15 App Router
- Language: TypeScript (strict mode, no `any`)
- Styling: Tailwind CSS v4
- Database: PostgreSQL with Prisma ORM

## Coding Standards
- Use `const` over `let` unless reassignment is required.
- All async functions must have explicit error handling with try/catch.
- Validate all API inputs using Zod schemas.
- Never hardcode secrets — use environment variables from `.env`.

## Architectural Patterns
- API routes: Next.js route handlers in `app/api/`.
- Repository pattern for all database access.
- React Server Components by default; client components only when necessary.
```

If your project uses [`AGENTS.md`](../AGENTS.md), have `copilot-instructions.md` simply reference it: `Read AGENTS.md and follow all protocols.` Don't fork the rules.

### Rule 2: Use `/clear` Between Unrelated Tasks

Copilot accumulates context from your conversation. Pillar 9.A (Context Bleed) is a real risk. Clear it between unrelated tasks:

```text
/clear
```

### Rule 3: Reference Existing Files for Pattern Consistency

Before generating new code, anchor it to an existing pattern in the repo:

```text
#file:src/api/users.ts
Generate a new route handler for `products` following the same exact pattern
as the `users` route above. Use the same error handling and response format.
```

### Rule 4: Use Copilot Workspace for Multi-File Features

For features touching multiple files, use Copilot Workspace:

- Describe the feature in natural language.
- **Review the generated plan** before accepting any edits.
- Edit the plan if it proposes changes to files you don't want modified.
- Never accept the entire workspace edit blindly — review file by file.

### Rule 5: Use `/explain` and `/doc` for Legacy Code

```text
/explain
Why does this authentication middleware use a double-checked locking pattern?
Is this still necessary in Node.js 22?
```

```text
/doc
Generate comprehensive JSDoc comments for this entire service class.
Include parameter types, return values, and thrown exceptions.
```

### Rule 6: Use Copilot Code Review on PRs

Enable **Copilot code review** at the repo level. It runs automatically on PRs and catches a different class of issues than human review (consistency, missing null checks, obvious bugs). Treat its findings as a first-pass triage, not a substitute for human review of security-sensitive paths.

### Rule 7: Enterprise & Privacy Rules

- **Never paste proprietary business logic** into public AI sessions.
- Use **Copilot Business** or **Enterprise** for private model routing.
- Enable **content exclusions** in settings for files containing secrets.
- For regulated industries, audit Copilot's data-handling agreements before adoption.

---

## 🧪 Copilot-Specific Workflow: The "Issue-to-PR" Pattern

Copilot's tightest integration with the GitHub flow:

1. **Issue:** Open a GitHub issue describing the bug or feature with acceptance criteria.
2. **Assign to Copilot:** Use Copilot Workspace's "implement this issue" action.
3. **Plan review:** Read Copilot's proposed plan; edit to match your spec.
4. **Generate:** Let Copilot produce the change set.
5. **Human verify:** Run the verification table (workflow-guide.md phase 4).
6. **PR:** Copilot opens the PR; you fill in the security-sensitive notes section.
7. **Merge:** Standard branch protections apply.

---

## 🚫 Anti-Patterns for Copilot

| Anti-pattern | Why it fails | Do this instead |
| --- | --- | --- |
| No `copilot-instructions.md` | Copilot defaults to its built-in style, not yours | Always create the instructions file |
| Mixing unrelated tasks in one chat | Pillar 9.A (Context Bleed) | Use `/clear` between features |
| Accepting Workspace edits without per-file review | High-blast-radius commits with no diff review | Review file by file; reject scoped-creep edits |
| Treating Copilot Review as sufficient | It catches consistency, not security or design | Always layer human review on top |
| Free-form chat for hard reasoning | Not its strength | Switch to Claude / o-series for hard reasoning |

---

## 🚫 Common Mistakes to Avoid

| Mistake | Instead |
| --- | --- |
| No instruction file | Create `.github/copilot-instructions.md` (or reference `AGENTS.md`) |
| Mixing unrelated tasks in one session | Use `/clear` between different features |
| Not referencing existing patterns | Use `#file:` to anchor new code to existing examples |
| Merging code without review | Always diff and review before accepting suggestions |
| Pasting proprietary code into public Copilot | Use Copilot Business / Enterprise for private routing |
