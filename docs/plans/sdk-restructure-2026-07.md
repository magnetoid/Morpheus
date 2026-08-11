# SDK restructure — three SDKs: Theme, Core-app, Plugin (2026-07)

**Torsor ADR 0035** — while developing, keep three project SDKs current: Theme,
Core-app, Plugin. User decision (2026-07-28): shape = `morpheus.{plugin,theme,core}`
subpackages (one installable `morpheus` package, three doors, top-level back-compat);
approach = **big-bang full migration** (carve the SDKs AND rewrite ~60 plugins + themes
onto the new imports).

## Why this is the highest-blast-radius change in the repo

`manage.py check` fails the prod boot on any bad import; ~60 plugins import from
`morpheus`/`core`. So the migration is **strictly ordered** and every step ends at a
green `check` + full suite. Nothing ships half-migrated.

## Real import surface (survey 2026-07-28)

**From `morpheus.*`:** `Plugin` 109, `SettingsPanel` 67, `StorefrontBlock` 56,
`events` 53, `DashboardPage` 52, `models` 45, `morpheus.views` 103 (Django glue:
render/redirect/staff_member_required/Http404/HttpResponse/get_object_or_404/…),
`forms` 6, `EmailTemplateDef` 6, `dashboard_trail` 8, `hooks` 4.

**From `core.*`:** `core.hooks` 92, `core.agents` 81, `core.utils.site` 34,
`core.models` 33, `core.assistant.models` 15, `core.money` 10, `core.emails` 9,
`core.audit.models` 9, `core.audit.services` 8, `core.assistant.tools` 8,
`core.agents.tools` 8, `core.utils.rate_limit` 7, `core.agents.llm` 6,
`core.agents.events` 6, `core.brain` 6, …

## The three SDK surfaces

Existing `morpheus/` modules (`__init__`, `views.py`, `models.py`, `events.py`,
`hooks.py`, `forms.py`) are reorganized under the three subpackages; top-level names
stay as thin re-exports for back-compat during the sweep.

### `morpheus.app` — authoring a plugin
- `Plugin`, `PluginConfigurationError` ← `plugins.base`
- `DashboardPage`, `SettingsPanel`, `StorefrontBlock`, `EmailTemplateDef`, `dashboard_trail`
  ← `plugins.contributions`
- `morpheus.app.views` (the 103× Django glue — moved from `morpheus/views.py`)
- `morpheus.app.models` (ORM + `MoneyField`/`Money` — from `morpheus/models.py`)
- `morpheus.app.forms` (from `morpheus/forms.py`)

### `morpheus.core` — consuming the kernel from a plugin
- `events` (the `MorpheusEvents` constant mirror — from `morpheus/events.py`)
- `hooks` (`hook_registry`, `fire`, `filter_value` — from `morpheus/hooks.py`)
- Agents SDK: `tool`, `ToolResult`, `ToolError`, `agent_registry` ← `core.agents`
- Audit: `record_ai_decision` ← `core.audit.services`
- Money: `Money`, `MoneyField`, `money_str` ← `core.money` / djmoney
- Utils: `site_base_url` ← `core.utils.site`; `rate_limit` ← `core.utils.rate_limit`
- (Deeper kernel surfaces — `core.assistant.tools`, `core.brain`, `core.agents.llm` —
  re-exported as `morpheus.core.assistant` / `.brain` / `.llm` submodules as needed.)

### `morpheus.theme` — authoring a storefront theme
- `StorefrontBlock` (re-export — the slot contribution type)
- Slot registry / slot-name constants + the storefront context contract
- The `{% load morph %}` template-tag library (`core/templatetags/morph.py`) surfaced as
  the theme SDK's tag set (storefront_blocks, plugin_enabled, money, ai_disclosure, …)
- Theme manifest structure + theme discovery/registration (`themes/library/` conventions)

## Back-compat contract (must hold at every step)

`morpheus/__init__.py` keeps re-exporting `Plugin`, `DashboardPage`, `SettingsPanel`,
`StorefrontBlock`, `EmailTemplateDef`, `dashboard_trail` from `morpheus.app`; and the
`morpheus.views` / `morpheus.models` / `morpheus.events` / `morpheus.hooks` / `morpheus.forms`
module paths keep resolving (thin shims re-exporting from the new homes). So **existing
`from morpheus import …` code never breaks** even mid-sweep. Old paths are removed only in
the final step, after every plugin is migrated and green.

## Execution order (each step ends green: `manage.py check` + `DATABASE_URL=sqlite tests`)

1. **Foundation (this deploy, NON-breaking):** create `morpheus/app/`, `morpheus/theme/`,
   `morpheus/core/` facades re-exporting the real implementations; keep every old
   `morpheus.*` path working via shims. Add a per-SDK README + quickstart. Verify `check` +
   a smoke import + a sample plugin still boots. → shippable on its own.
2. **Core-app SDK adoption:** migrate `from core.hooks/agents/audit/money/utils import …`
   across plugins → `from morpheus.core import …`. Batch by plugin; `check` after each batch.
3. **Plugin SDK adoption:** migrate `from morpheus import …` / `from morpheus.views/models/forms
   import …` → `from morpheus.app import …`. Batch by plugin.
4. **Theme SDK adoption:** migrate themes + `StorefrontBlock` producers onto `morpheus.theme`;
   document the slot/tag contract.
5. **Seal:** remove the back-compat shims (or keep as deprecated re-exports), add a boundary
   guard/hook that new plugins import from the SDK subpackages, docs (ARCHITECTURE,
   PLUGIN_DEVELOPMENT, per-SDK README), `manage.py release` (MINOR/MAJOR).

## Execution vehicle

Steps 2–4 are a ~60-plugin mechanical fan-out — ideal for a **multi-agent workflow**
(one agent per plugin: rewrite imports, run `check`, report) or a dedicated fresh session.
NOT to be rushed at the tail of a long session — a missed import is a live prod 503.
The foundation (step 1) is safe to build any time and unblocks incremental adoption per
ADR 0035.
