---
type: system-patterns
status: active
tags: [architecture]
---

# System Patterns

## Architecture overview
Three layers, two registries (see `docs/ARCHITECTURE.md` for the canonical
detail):

- **Core** (`core/`) — small, almost everything else can be ripped out and the
  engine still boots: hooks bus, models, Celery, settings, request_id, JSON
  logging, i18n kernel, the agent kernel (`core/agents/`), the hard-coded
  Assistant (`core/assistant/`), the audit log, the self-improvement loop, and
  the safety boundary (`core/safety.py`).
- **Plugins** (`plugins/installed/<name>/`) — self-contained Django apps; the
  active set is `MORPHEUS_DEFAULT_PLUGINS` in `morph/settings.py` (source of
  truth — never a hard-coded count). Each has `apps.py`, `plugin.py` manifest,
  `models.py`, `migrations/`, `tests/`.
- **Themes** (`themes/library/<name>/`) — presentation only; declare which
  storefront **slots** exist + own layout/CSS. Active: `dot_books`.

Registries: **PluginRegistry** (discovers, topo-sorts, activates, collects
contributions, isolates crashes) and **AgentRegistry** (every Tool/Agent; Skills
resolve to tool bundles at invocation).

## Conventions
- **When in doubt, it's a plugin.** Core only for genuinely foundational things.
- **Every model ships with its migration in the same change** (prod boot fails a
  system check otherwise).
- **Dashboard `data-ajax` forms must return JSON on success *and* failure**
  (`{ok, errors}`) — an HTML/redirect response makes the JS flash a false
  "Saved" (recorded landmine).
- **Treat AI-generated code as untrusted-third-party code**; the enforcement
  layer is hooks (ruff / mypy / forbidden-import grep / pre-commit), not advisory
  `CLAUDE.md` prose.
- **Code and docs ship together** — architecture/convention/contract/count
  changes update the relevant Markdown in the same commit.
- Errors degrade gracefully: broad `except` around optional-plugin / optional-dep
  paths so one feature never breaks an unrelated render.

## Patterns in use
- **Modularity contract** — theme exposes named slots; plugins fill them via
  `StorefrontBlock(slot=…)` / `DashboardPage` / `contribute_settings_panel`;
  **disabling a plugin removes every surface it added**. No surface is
  hard-coded in core/theme/sibling.
- **No cross-plugin imports** — plugins coordinate only through the `core.hooks`
  event bus (`order.placed`, `product.updated`, `cart.checkout.totals`, …);
  handlers can transform or veto.
- **Event-sourced + transactional outbox** shipped to NATS JetStream; every
  outbound webhook HMAC-SHA256 signed.
- **Agent layer** — `MorpheusAgent` / `Tool` / `Skill` / `AgentRuntime` kernel; a
  hard-coded merchant Assistant in `core/`; an MCP server cluster
  (audience-scoped) + UCP / Trusted-Agent discovery at `/.well-known/`. Machine-
  actionable first, human-pretty second.
- **Schema-less data** via the `metafields` plugin — `(content_type, object_id,
  namespace, key, value)` triples on any model.
- **Central media library** (`media` plugin) federates uploads + product images
  + product/variant digital files into one view; on-the-fly WebP/AVIF variants
  served from `seo` at `/img/<fmt>/<width>/<path>`.
- **Plugin crash isolation** — a broken `ready()` is logged + excluded; siblings
  keep loading.
