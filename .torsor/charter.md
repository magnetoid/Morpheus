---
type: charter
status: active
tags: [charter]
---

# Project Charter — Morpheus OS

## What we are building
Morpheus OS is a modular, plugin-native, AI-first e-commerce platform. The core
is small — catalog → cart → checkout → fulfillment plus the foundations
everything depends on (auth, hooks, settings, i18n kernel, request lifecycle,
observability, the self-improvement loop, and the `core/safety.py` boundary).
**Everything else is a plugin** under `plugins/installed/<name>/`. It runs live
at dotbooks.store (the "dot books" bookstore theme).

## Why it exists
To be an enterprise-grade commerce platform that is more advanced toward
AI-first integration than Shopify, Saleor, Medusa, and WooCommerce: agents are a
first-class audience (a hard-coded merchant Assistant in core, a real agent
kernel, an MCP server cluster, UCP + Trusted-Agent discovery), sitting on top of
a complete, modular commerce engine — not bolted on.

## Non-negotiable principles
- **When in doubt, it's a plugin.** Only genuinely foundational things live in
  `core/`. Anything not required for catalog → cart → checkout → fulfillment is a
  plugin with its own `apps.py`, `plugin.py`, `models.py`, `migrations/`.
- **The modularity contract.** A theme exposes named slots → plugins fill them
  via `StorefrontBlock`/`DashboardPage`/settings contributions → **disabling a
  plugin removes every surface it added.** A surface that survives a disable was
  hard-coded in the wrong layer.
- **No cross-plugin imports.** Plugins coordinate only through the `core.hooks`
  event bus — never import one plugin from another's models.
- **A plugin owns all its own code.** It appears elsewhere by *contributing*,
  never by editing core, the theme, or a sibling plugin.
- **Every model ships with a migration** in the same change (prod boot fails
  otherwise).
- **Treat AI-generated code as untrusted-third-party code** — verify against
  real APIs; hooks (ruff/mypy/forbidden-import) are the enforcement layer, not
  advisory `CLAUDE.md` rules.
- **Code and docs ship together** — a change to architecture, a convention, a
  contract, or a count updates the relevant Markdown in the same commit.
- **AI-first surface stays machine-actionable first, human-pretty second** —
  every model, hook, and state transition is designed for agents to act on.

See `CLAUDE.md`, `docs/ARCHITECTURE.md`, and `docs/PLUGIN_DEVELOPMENT.md` for the
authoritative detail; `MORPHEUS_DEFAULT_PLUGINS` in `morph/settings.py` is the
source of truth for the active plugin set.
