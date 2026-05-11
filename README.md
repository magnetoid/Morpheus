# Vibe Agent Framework — Master Index
> **The Ultimate Vibe Coding Ruleset for 2026**
> Drop this entire folder into the root of any project to instantly configure any AI coding agent with battle-tested best practices.

---

## Directory Structure

```
vibe-agent-framework/
├── README.md                        ← This file (master index)
├── .cursorrules                     ← Cursor IDE agent config
├── .windsurfrules                   ← Windsurf IDE agent config
├── .traerules                       ← Trae IDE agent config
├── AGENTS.md                        ← Universal agent instructions (Cline, RooCode, etc.)
│
├── docs/
│   ├── spec-template.md             ← Architecture-first planning template
│   ├── context-template.md          ← Session handoff / context preservation
│   ├── universal-principles.md      ← Core vibe coding pillars (all agents)
│   └── workflow-guide.md            ← The ideal vibe coding workflow
│
├── llm-rules/
│   ├── claude.md                    ← Rules & strategies for Claude (Anthropic)
│   ├── gpt.md                       ← Rules & strategies for GPT-4o / o3 (OpenAI)
│   ├── gemini.md                    ← Rules & strategies for Gemini 2.5 Pro (Google)
│   ├── deepseek.md                  ← Rules & strategies for DeepSeek R2
│   ├── grok.md                      ← Rules & strategies for Grok 4 (xAI)
│   ├── copilot.md                   ← Rules & strategies for GitHub Copilot
│   ├── mistral.md                   ← Rules & strategies for Mistral / Codestral
│   └── llama.md                     ← Rules & strategies for Llama 3 (Meta / local)
│
└── language-rules/
    ├── python.md                    ← Python vibe coding rules
    ├── typescript.md                ← TypeScript vibe coding rules
    ├── javascript.md                ← JavaScript vibe coding rules
    ├── rust.md                      ← Rust vibe coding rules
    ├── go.md                        ← Go (Golang) vibe coding rules
    ├── java.md                      ← Java vibe coding rules
    ├── csharp.md                    ← C# vibe coding rules
    ├── sql.md                       ← SQL vibe coding rules
    ├── php.md                       ← PHP vibe coding rules
    └── bash.md                      ← Bash / Shell scripting rules
```

---

## How to Use This Framework

### Bootstrapping a New Project
```bash
# Copy the entire framework into your project root
cp -r /path/to/vibe-agent-framework/* /path/to/your/project/

# Then open your IDE (Cursor/Windsurf/Trae) and say:
# "Read AGENTS.md, docs/spec-template.md, and the relevant language-rules file.
#  Confirm when ready to begin."
```

### Starting a Vibe Coding Session
1. **Fill out `docs/spec-template.md`** with your project's goals and tech stack.
2. **Tell your agent which LLM ruleset to follow** from `llm-rules/`.
3. **Reference the relevant language rules** from `language-rules/`.
4. **Code iteratively** — one atomic chunk at a time.
5. **End sessions** by updating `docs/context-template.md`.

---

## Quick Reference: LLM Strengths

| LLM | Best For | Avoid Using For |
|-----|----------|-----------------|
| **Claude** | Architecture, refactoring, long-form reasoning | Simple one-liners (overkill) |
| **GPT-4o** | Rapid UI prototyping, iteration speed | Complex cross-file refactoring |
| **GPT o3** | Deep algorithmic problems, debugging logic | Quick UI changes (too slow) |
| **Gemini 2.5** | Ingesting massive codebases / docs | Precise syntactical generation |
| **DeepSeek R2** | Algorithmic complexity, edge-case tests | UI/UX aesthetic decisions |
| **Grok 4** | Real-time info, large-context codebase work | Highly structured output formats |
| **Copilot** | IDE-integrated suggestions, team workflows | Standalone complex reasoning |
| **Mistral** | Privacy-sensitive local workloads | Latest framework knowledge |
| **Llama 3** | Air-gapped / local inference, cost-free runs | Frontier reasoning tasks |

---

## Quick Reference: Language Rules Cheatsheet

| Language | Key AI Pitfalls to Watch | Critical Rules |
|----------|--------------------------|----------------|
| **Python** | hallucinated library methods, missing type hints | Use Pydantic, enforce PEP 8, always use `asyncio` |
| **TypeScript** | `any` types, missing null checks | Strict mode ON, Zod validation, no `any` |
| **JavaScript** | async/await bugs, XSS via `innerHTML` | Always use ESLint, prefer `const`, sanitize DOM |
| **Rust** | Lifetime annotations, incorrect `unsafe` blocks | Never use `unwrap()` in prod, clippy enforced |
| **Go** | Unhandled errors, goroutine leaks | Always handle `err`, use `context.Context` |
| **Java** | NPEs, verbose boilerplate, Spring misuse | Records, Optional, modern Java 21+ patterns |
| **C#** | Nullable refs, dependency injection misuse | Nullable annotations on, use `ILogger` |
| **SQL** | SQL injection, N+1 queries | Always parameterize, verify query plans |
| **PHP** | XSS, path traversal, `eval()` usage | Use PDO, escape outputs, modern PHP 8.3+ |
| **Bash** | Unquoted variables, no error handling | `set -euo pipefail`, always quote variables |
