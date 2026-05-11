# AI Agent Master Instructions (AGENTS.md)

> The universal source of truth for any CLI- or IDE-based AI coding agent
> (Claude Code, Codex CLI, Cursor, Windsurf, Trae, Cline, RooCode, Continue,
> standard Copilot) interacting with this repository.
>
> `AGENTS.md` is the open standard adopted by OpenAI, Cursor, and others. Keep
> this file canonical; if you maintain `.cursorrules`, `.windsurfrules`, or
> `.traerules`, derive them from this file (don't fork the rules).

---

## Read Me First

When this file is loaded, do these three things in order, **before any code action:**

1. Read [docs/universal-principles.md](docs/universal-principles.md). The 9 pillars are non-negotiable.
2. Read [docs/workflow-guide.md](docs/workflow-guide.md) and adopt the six-phase loop (Plan → Load → Generate → Verify → Save → Handoff).
3. Read the language-rules file for the language we're working in (`language-rules/<lang>.md`).

If the project has not yet filled out [docs/spec-template.md](docs/spec-template.md), ask the user to populate it before generating non-trivial code.

---

## Global Tech Stack Constraints

*(User: fill these out for your project. The agent must treat any deviation as a red flag and surface it before proceeding.)*

- **Frontend Framework:** [e.g., Next.js 15, React 19]
- **Styling:** [e.g., Tailwind CSS v4, Vanilla CSS Modules]
- **Backend / API:** [e.g., Node.js 22, Python FastAPI]
- **Database:** [e.g., PostgreSQL 17 with Prisma]
- **Language(s):** [e.g., Strict TypeScript 5.7+, Python 3.12+]
- **Test runner:** [e.g., Vitest, Pytest]
- **Package manager:** [e.g., pnpm, uv]

---

## Vibe Coding Protocols

### 1. Plan-First

Before any `write_to_file` or large multi-file refactor, output a 3-bullet plan and list the files you intend to touch. Wait for user confirmation, **unless** the prompt explicitly says `auto-run`, `just do it`, or you are in a documented auto-mode session.

### 2. Context-Preservation

Do not invent new patterns. Search the existing codebase (grep, ripgrep, or your IDE's symbol search) for similar components, API routes, or test files **before** creating a new one. Mirror the existing pattern.

### 3. Anti-Laziness

You are forbidden from writing `// ... rest of code`, `# rest of implementation`, `<unchanged>`, or any equivalent placeholder. Output the entire functional block or file unless the user specifically asks for a diff or partial fragment.

### 4. Zero-Trust Defaults

Treat every user input as malicious. Treat every external API response as malformed. Default to: parameterized queries, escaped output, validated input, secrets via environment, error logs without secret data.

### 5. Multi-Agent Workflows

If you are operating as one role inside a specialized pipeline:

- **Planner:** Edit only `docs/spec-template.md`. Do not write code.
- **Generator:** Fulfill the spec strictly. Do not edit the spec.
- **Reviewer:** Find bugs, security flaws, and performance issues. Do not write the fix unless explicitly asked.

### 6. Checkpoint Protocol *(2026 addition)*

After every atomic chunk (one feature, one fix, one refactor), **stop and verify** before starting the next chunk. Verification = type-check + lint + tests + spec match (see [docs/workflow-guide.md](docs/workflow-guide.md) phase 4). Never build chunk N on top of an unverified chunk N-1. If you cannot verify (e.g., no test runner), say so explicitly and ask the user how to proceed.

### 7. Tool-Use & MCP Hygiene *(2026 addition)*

- Prefer the dedicated tool over shelling out: `Read` over `cat`, `Edit` over `sed`, the IDE's symbol search over ad-hoc grep where available.
- Never ask for tool permissions you don't need. Read-only investigation should not require write or network permissions.
- If an MCP server is available for a task (database query, API call, file system on a remote host), prefer it over generating shell commands the user must approve.
- For irreversible actions (`rm -rf`, force push, schema migrations, package uninstall, branch delete), ask before acting — even in auto mode.

### 8. Spec-to-PR Protocol *(2026 addition)*

When the work crosses from "one chunk" to "a feature":

1. The PR description **is** the spec section delivered. Paste the relevant section from `docs/spec-template.md`.
2. Include the verification table from [docs/workflow-guide.md](docs/workflow-guide.md) phase 4 with checkboxes ticked.
3. Call out the security-sensitive paths explicitly so reviewers focus there.
4. Never push to `main`/`master` directly. Branch + PR even for solo projects — the diff review against `main` is the safety net.

---

## What "Done" Means

A chunk is done when **all** of these are true:

- It compiles / type-checks cleanly.
- The linter is clean.
- New tests exist for new behavior; the full suite passes.
- It matches the spec section it was meant to deliver.
- It follows the existing repo pattern (a reference file was used in phase 2).
- No new dependencies were silently added.
- No secrets, API keys, or PII appear in the diff.
- Commit is atomic, with a message that explains *why*.

If any of these is false, the chunk is not done. Loop back to phase 3 of the workflow guide.
