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

**A plugin owns all of its own code.** Every file a feature needs — views,
URLs, templates, dashboard pages, settings panels, GraphQL, beat tasks —
lives under `plugins/installed/<name>/`. It appears *elsewhere* by
**contributing**, never by editing another layer's files:

- Storefront surface → a `StorefrontBlock(slot=...)` (or the plugin's own
  URL + template), **not** an edit to `plugins/installed/storefront/` or
  `themes/`.
- Dashboard page / nav entry / settings form → the plugin's dashboard-page,
  nav, or `contribute_settings_panel` contribution, **not** an edit to
  `plugins/installed/admin_dashboard/`.
- Behaviour inside another plugin's flow (cart total, order lifecycle) → a
  `core.hooks` subscriber, **not** an import of its models or an edit to
  its views.

**Two litmus tests:**

1. **Delete** `plugins/installed/<name>/` → the feature is gone with no
   dangling view, URL, template, or import in core, the theme, or a
   sibling plugin.
2. **Disable** the plugin (toggle it off) → *every* surface it added —
   sidebar nav entries, settings pages, storefront blocks, account tiles —
   **disappears from Morpheus OS.** A surface that survives a disable was
   hard-coded in the wrong layer. Contributed surfaces are rendered only
   while the plugin is enabled; hard-coded ones are not, which is the bug.

If adding feature X made you edit a file outside `plugins/installed/X/`,
that edit belongs back inside X as a contribution.

**Disable-test enforcement:** hardcoded plugin nav links in the dashboard
shell must sit behind `{% plugin_enabled "<plugin>" %}` so they vanish on
disable; `admin_dashboard/tests/test_disable_guards.py` fails the build if a
plugin link is added unguarded. (loyalty's `/account/points/` and the
payments settings panel — the old known debt — are now properly contributed.)

**Known debt to repay (still fails the disable test):**
`storefront/views/account.py` still hardcodes orders/returns/store-credit
fields (loyalty, gift_cards and digital_products already migrated to
`ACCOUNT_SUMMARY_FIELDS`). The dashboard home *activity feed* is fixed —
assembled via the `ACTIVITY_FEED` filter with orders / agent_core /
reviews / loyalty_points / crm subscribing (guarded by
`admin_dashboard/tests/test_activity_feed_modular.py`) — but the KPI /
setup / pulse tiles in `admin_dashboard/views_split/home.py` still import
orders / catalog / ai_assistant / agent_core / inventory models directly.

**Core → plugin imports (wrong direction; core should never import
`plugins.installed.*`):** `core/emails` is fixed (cms's EmailTemplate now
arrives via the `EMAIL_TEMPLATE_OVERRIDE` filter; the site base URL moved
to `core/utils/site.py` and seo delegates to it). Still leaking:
`core/agents/llm.py` + `core/assistant/consensus.py` reach into
ai_assistant's provider config (~10 sites); `core/assistant/tools/*`
queries catalog/orders/cms/metafields/… models directly — the right fix
is migrating those tools to each plugin's `contribute_agent_tools()`;
and `core/context_processors.cart_context` imports orders.Cart
(`Plugin.register_context_processor` exists but nothing consumes the
registry's list yet, so it can't move until that API is wired up).

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

**Landmine — running tests locally.** Bare `python manage.py test` reads
`DATABASE_URL` from `.env` and tries to reach the Docker `db` host, so it
hangs/dies outside the container. Always pin an in-memory DB:

```bash
DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.<name>
```

CI gates a change with `ruff check .`, `ruff format --check .`, and
`python manage.py makemigrations --check --dry-run` (the migration check is
the one that fails every prod boot if you ship a model without one).

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

**Code and docs ship together.** Any change that alters architecture, a
convention, a public contract, a count, or a landmine must update the
relevant Markdown *in the same commit* — not "later." Which doc:

| You changed… | Update… |
|---|---|
| `core/` structure, a subsystem's job, the request lifecycle | `docs/ARCHITECTURE.md` |
| a plugin's purpose / deps / the plugin contract | `docs/PLUGIN_DEVELOPMENT.md` (+ that plugin's `plugin.py`) |
| a house rule, landmine, or convention | this file (`CLAUDE.md`) |
| the public API / MCP / GraphQL surface | `docs/MORPHEUS_API.md`, `docs/MCP_SERVER.md` |
| a skill's behaviour | `docs/SKILLS.md` + the skill's `SKILL.md` |

Prefer pointing at the source of truth over hard-coding volatile facts:
a plugin *count* in prose rots (it drifted to 47/49/54 across three docs
while the real number was 61) — write "see `MORPHEUS_DEFAULT_PLUGINS`."

Every time AI-assisted work ships a wrong assumption, the fix-up commit
should also patch this file. If a rule is here twice, consolidate. If a
rule has stopped being violated for 6 months, consider deleting it.
