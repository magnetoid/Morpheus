# Linda (assistant) power-up + central updating system

> Goal (2026-06): make Linda — the core staff AI assistant — able to manipulate
> and control the whole shop, and add a central updating system.

## Analysis (current state)
**Linda** = the hard-coded core assistant (`core/assistant/`, `class Assistant`,
label "Linda AI Assistant"; persona in `core/assistant/prompts.py:LINDA_BASE_PROMPT`).
NOT the `lumina` plugin. Surfaced at `/dashboard/assistant/` + a floating widget.
Runs an LLM (ai_assistant provider config) with a tool-calling loop; cross-session
`LindaMemory`. Delegates to the single generic **Worker** (`core/agents/builtin/
worker.py`) — specialization is **scopes + Skills**, never new agent classes
([[feedback_generic_agents]]).

**Tools today (~27)**, `core/assistant/tools/`: reads (orders/products/customers/
analytics/cms/media/settings/metafields/db), writes (order status/cancel/note,
product status/price, cms publish, metafields set/delete — two-step `confirmed`,
hard-gate for deletes), memory, and Worker delegation. Tool pattern: `@tool(name,
description, scopes, schema, requires_approval)` returning `ToolResult`; registered
in `tools/__init__.py:get_default_tools()` or a plugin's `contribute_agent_tools()`.

**Gaps toward "control the whole shop":** no inventory stock writes, no plugin
config writes, no plugin enable/disable, no theme switch, no workflow trigger, no
update control.

**Updating system** (`core/versioning.py`, `core/updates.py`, `morph_*` commands,
`docs/plans/updating-system-2026-06.md`): phases 1-4 done — version inventory,
read-only `/dashboard/updates/` page, git update-check, CLI guarded apply+rollback
(opt-in `MORPHEUS_SELF_UPDATE_ENABLED`, dry-run default, ff-only, backup, rollback).
**Gaps:** no UI trigger (page is read-only), no per-plugin/theme channels, no
AI-assisted proposal (phase 5), no maintenance mode.

## Plan (phased, each shippable + verifiable)

### A. Central updating system — make it actionable from the dashboard
- A1. `/dashboard/updates/` gains **"Check for updates"** (POST → `platform_update_status(fetch=True)`, shows behind/ahead/latest) and, when `MORPHEUS_SELF_UPDATE_ENABLED`, an **"Apply update"** action (POST → `apply_platform_update(confirm=True)`), staff-only, with a dry-run preview first. Surfaces the existing core/updates.py via the UI = the "central updating system". Fail-soft (no .git → "unavailable").
- A2. Component table already lists core/plugins/themes versions; add per-row status (up-to-date / behind) once remote check ran.

### B. Linda controls more of the shop — new tools (scoped + gated)
- B1. `inventory.set_stock` (write, `inventory.write`, confirmed) — set on-hand for a product/variant via the inventory service.
- B2. `settings.set` (write, `system.write`, confirmed) — write a PluginConfig key (the config that powers shop behaviour).
- B3. `updates.status` (read, `system.read`) + `updates.apply` (write, `system.write`, **hard-gated** + `MORPHEUS_SELF_UPDATE_ENABLED`) — Linda can report + drive the central updater. Ties A+B (phase-5 AI-assisted updates, human-confirmed).
- B4. `plugins.toggle` (write, hard-gated, respects PROTECTED_PLUGINS so disabling admin_dashboard etc. is refused — [[plugin_toggle_softbrick]]).
- B5. Persona tune: teach Linda about the new powers + the confirm/hard-gate discipline.

### C. (later) per-plugin/theme update channels + maintenance mode + AI-assisted staging.

## Landmines / rules
- ONE Worker; add tools, never agent classes ([[feedback_generic_agents]]).
- Every write tool is two-step (`confirmed`); destructive/irreversible ones hard-gate.
- All shop-mutating + self-update paths route through `core/safety.py` posture; self-update stays opt-in + CLI-parity (no silent core swaps).
- Plugin toggle must refuse PROTECTED_PLUGINS ([[plugin_toggle_softbrick]]).
- Dashboard `data-ajax`/POST update actions return JSON on success AND failure.

## Status log
- 2026-06: analysis done (research map); plan written.
- 2026-06: **A1 shipped** (e988efa) — `/dashboard/updates/` Apply action wraps the
  guarded `apply_platform_update` (opt-in, ff-only, backup, rollback); 4 tests.
  The central updating system is now dashboard-driven (check + apply), CLI-parity.
- 2026-06: **B shipped** (e3d6e5a) — Linda +4 platform-ops tools (updates.status,
  updates.apply [hard-gated], settings.set, plugins.toggle [refuses protected]) →
  42 tools; persona updated; 9 tests. Inventory/SEO/CRM stay Worker-delegated.
- **Delivered:** central updating system (UI) + Linda can now self-update, write
  store config, and toggle plugins (+ delegate the rest). Core of both asks done.
- **Remaining (breadth — future increments):** more direct shop-control tools
  (theme switch, workflow trigger, refunds, webhooks); updating-system Phase 5
  (per-plugin/theme channels, AI-assisted staging, maintenance-mode middleware,
  DB-snapshot restore). Best continued in a fresh session (context hygiene).
