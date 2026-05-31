# Morpheus — house rules for AI-assisted work

> Companion rulesets: [`vendor/vibe-skills/llm-rules/claude.md`](vendor/vibe-skills/llm-rules/claude.md) (Claude-specific) and [`vendor/vibe-skills/AGENTS.md`](vendor/vibe-skills/AGENTS.md) (cross-IDE). See [`AGENTS.md`](AGENTS.md) for the full map.

This file is **only for things you can't discover from `grep`, `find`, or
`manage.py`.** Stack, file layout, lint config — read the code. Things
written below are the rules, the landmines, and the conventions that
aren't visible from the tree.

Target length: under 200 lines. Edit it when an assumption ships wrong.

---

## Architectural compass

**Build a powerful core e-commerce platform — but ship features in modular
plugins, not core.** Anything that isn't *required* for catalog → cart →
checkout → fulfillment lives in `plugins/installed/<name>/` with its own
`apps.py`, `plugin.py` manifest, `models.py`, `migrations/`, and
templates. Reach for `core/` only when the feature is genuinely
foundational: auth, hooks, i18n kernel, request_id, observability,
**the self-improvement loop** (autonomic engine + code-quality scanner +
upstream-drift tracking — the immune system of a vibecoded platform; cannot
be a togglable plugin), and **the safety boundary** (`core/safety.py` —
single source of truth for what AI can touch; read by self-improvement,
agent_mcp, CI hooks, pre-commit).

When in doubt: it's a plugin.

Examples (this is what's already shipped — mirror the pattern):

- Reviews, loyalty, markets, notifications, workflows, metafields, media,
  CMS — all plugins.
- The agent layer, hooks bus, settings, request lifecycle, self-improvement
  engine, safety boundary — core.

**Plugin contract:**

- Single AppConfig in `apps.py` (plus `ready()` for signal/hook wiring).
- Plugin manifest in `plugin.py` (name/label/version/requires/blocks/tools).
- Register in `morph/settings.py:MORPHEUS_DEFAULT_PLUGINS`.
- Add a migration before merge — system check fails on every prod boot
  if you ship a model without one.
- Storefront integration through `StorefrontBlock(slot=...)` contributions,
  not direct template edits in `themes/`.
- Cross-plugin coupling through the `core.hooks` event bus — never import
  one plugin from another's models.

---

## How to research

**Batched, not stepwise.** Combine `grep`, `find`, `wc`, `head` into one
script and run it once. Spawn a subagent for open-ended exploration so
the noisy output doesn't burn the main context. Reach for the direct tool
only when the target is known.

Bad: 10 sequential greps probing related files.
Good: one script that pulls the 10 results into one paste.

---

## How to execute coding tasks

When the user asks for code, **don't stop until it's fully done.** That
means:

1. Make the change.
2. Compile / syntax check (`python -m py_compile <files>` for Python,
   tag balance for Django templates).
3. Deploy + smoke (rsync → `docker build` on tetra → `docker compose up
   -d --no-build --force-recreate web` → `migrate` → curl the public URL).
4. Honest report: what shipped, what didn't, what's left.

A passing type/lint/syntax check is *necessary*, not *sufficient*.
Smoke against the live URL.

---

## Think before coding

- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop, name what's confusing, ask.

---

## Simplicity first

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or configurability that wasn't requested.
- No error handling for impossible scenarios.
- No backwards-compat shims for code you can just change.
- 200 lines that could be 50 → rewrite.

Test: would a senior engineer say this is overcomplicated? If yes, simplify.

---

## Surgical changes

Touch only what you must. Clean up only your own mess.

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style even if you'd do it differently.
- Notice unrelated dead code? Mention it. Don't delete it.
- Linter / autoreplace drift in unrelated files: revert it before
  staging your own changes.

When your changes create orphans:

- Remove imports / variables / functions that **your** changes made unused.
- Don't remove pre-existing dead code unless asked.

Test: every changed line traces directly to the user's request.

---

## Goal-driven execution

Define success criteria up front. Loop until verified.

- "Add validation" → "Tests for invalid inputs pass."
- "Fix the bug" → "Reproducer test passes."
- "Refactor X" → "All tests still pass."

For multi-step work, state a brief plan with verifiable checkpoints:

1. \[Step] → verify: \[check]
2. \[Step] → verify: \[check]

Strong success criteria let you loop independently. Weak criteria ("make
it work") force the user to check your work for them.

---

## Subagents and context hygiene

- Use subagents for noisy operations (test runs, log greps, full-repo
  searches, web research). Pass back a summary; keep the main window clean.
- Compact at ~70% context, not at the forced 83%.
- Plans don't survive `/clear` or `/compact`. If a plan is load-bearing
  across turns, write it to `docs/plans/<feature>.md` and reference it.
- Long sessions degrade through repeated compaction. End-and-restart
  beats pushing a 90%-full window through another phase.

---

## Verifying AI-generated code

LLM-generated code ships measurably more security and correctness bugs
than human-written code (~1.7× more major issues; 29-45% has known
vulnerability classes; ~20% of suggested third-party packages are
hallucinated). Treat AI output as untrusted-third-party-code:

- **Verified-Output rule.** Before adding a dependency: confirm the
  package exists on PyPI / npm registry, and that we already use it
  elsewhere in the repo, OR explicitly justify the new dep in the
  commit message.
- **Contract-test against real APIs.** Mocks pass while phantom methods
  fail in prod. Hit the actual interface in tests.
- **Feed errors back verbatim.** Don't paraphrase a stack trace into the
  agent — paste it. After a fix, ask whether the rule that would have
  prevented it belongs in this file.

Rules in `CLAUDE.md` are *advisory* — the runtime can ignore them.
**Hooks are the enforcement layer** (PostToolUse hooks for ruff, mypy,
forbidden-import grep). When you find an advisory rule being ignored
repeatedly, promote it to a hook.

---

## Living document

Every time AI-assisted work ships a wrong assumption, the fix-up commit
should also patch this file. If a rule is here twice, consolidate. If a
rule has stopped being violated for 6 months, consider deleting it.
