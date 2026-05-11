# CLAUDE.md — Repository Guide for Claude Code

> This file is for Claude Code (and other AI agents) working **inside this repo**.
> If you are looking for the rules to drop into your *own* project, see
> [vibe-agent-framework/AGENTS.md](vibe-agent-framework/AGENTS.md) instead.

## What this repo is

`ultimate-vibe-coding-skills` is a documentation-first toolkit. There is **no
application code** here — the deliverable is the `vibe-agent-framework/` directory,
which is meant to be copied into other projects.

- Root [`README.md`](README.md) — the philosophy & 2026 vibe-coding overview.
- [`vibe-agent-framework/`](vibe-agent-framework/) — the actual drop-in toolkit.

## How to navigate

When asked to add or change a rule, find the right file by category:

| Asked about... | Edit |
| --- | --- |
| The 9 pillars / mindset | [vibe-agent-framework/docs/universal-principles.md](vibe-agent-framework/docs/universal-principles.md) |
| The 6-phase loop / workflow | [vibe-agent-framework/docs/workflow-guide.md](vibe-agent-framework/docs/workflow-guide.md) |
| Universal agent protocols | [vibe-agent-framework/AGENTS.md](vibe-agent-framework/AGENTS.md) |
| A specific LLM (Claude / GPT / Gemini / etc.) | `vibe-agent-framework/llm-rules/<llm>.md` |
| A specific language (Python / TS / Rust / etc.) | `vibe-agent-framework/language-rules/<lang>.md` |
| A specific IDE (Cursor / Windsurf / Trae) | `vibe-agent-framework/.<ide>rules` |
| Spec / context templates | `vibe-agent-framework/docs/{spec,context}-template.md` |

`AGENTS.md` is the canonical source — `.cursorrules`, `.windsurfrules`, and
`.traerules` derive from it. If you change a protocol, change `AGENTS.md` first
and propagate downward.

## Style conventions for new content

When writing or editing rule files, match the existing voice:

- **Markdown only.** No HTML, no emoji except as section markers (the existing files use them).
- **Tables for cheat sheets**, prose for principles, code blocks for prompt templates.
- **Header style** (LLM files): `**Role:**` line + `**Best Models (2026):**` line + `**See also:**` link line.
- **Header style** (language files): a one-line "Apply these rules whenever..." callout + a `**See also:**` link line.
- **Standard sections** for language files: Header → Mandatory Rules → AI Pitfalls Table → Prompt Template → Common Mistakes.
- **Cross-link aggressively.** Every rule file should link back to `docs/universal-principles.md`, `docs/workflow-guide.md`, and `AGENTS.md`.
- **Lead with the rule, then *why*, then *how to apply*.** Every directive should be testable / falsifiable, not vague.

## What NOT to do

- Don't add new top-level rule categories (frameworks/, databases/, skills/) without explicit user direction — the framework deliberately stays scoped.
- Don't fork rules across files. If a rule appears in `AGENTS.md`, IDE files should reference it, not restate it.
- Don't create example apps or sample projects in this repo — the framework *is* the deliverable.
- Don't delete or rename existing files without confirming first; downstream projects may have copied them by name.

## Verification before committing

After any rule change:

1. Every internal markdown link still resolves.
2. Every rule file still has its standard sections.
3. The directory tree in `vibe-agent-framework/README.md` matches the actual filesystem.
4. No file exceeds 400 lines (the framework's own atomic-chunking guidance applies to itself).

## Git conventions

- Commit per logical change (one new rule, one fixed link, one polished file).
- Branch + PR for non-trivial edits, even though this repo is solo.
- Never push directly to `main`.
- Commit messages: imperative summary, blank line, *why* in 2–3 lines.
