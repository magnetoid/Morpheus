---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-07T18:09:00'
updated: '2026-06-07T18:09:00'
rules:
- rule_id: core-no-plugin-imports
  kind: forbid_import
  target: plugins.installed
  scope: core/**/*.py
  exclude: '**/tests/**'
  severity: error
  message: core/ imports nothing from plugins.installed; invert it through a hook (ADR 0013, scripts/check_core_boundary.py).
- rule_id: core-no-app-model-by-name
  kind: forbid_pattern
  severity: warning
  scope: core/**/*.py
  exclude: '**/tests/**'
  target: get_model\(\s*[\'"](catalog|seo|cms|orders|customers|inventory|marketing|promotions|book_product|reviews|loyalty_points|gift_cards|marketplace|booking_marketplace|ai_assistant)[\'"]
  message: Core names an app by string; ask the owning app through a hook instead (ADR 0013).
guidance:
- id: core-no-plugin-specifics
  pattern: core/.*(installed\.|SECTION_ALIAS|marketplace|loyalty|gift_card|reviews)
  message: 'Core must not name or place specific plugins. A plugin''s surfaces + nav section/placement
    are owned by the plugin and contributed; core only offers the mechanism + plugin-agnostic fallback.
    (See ADR: app modularity.)'
  status: enforced by the machine rules core-no-plugin-imports and core-no-app-model-by-name, and scripts/check_core_boundary.py
- id: no-hardcoded-foreign-surface
  pattern: templates/(admin_dashboard|storefront)/.*\.html
  message: A plugin's storefront/dashboard surface must be CONTRIBUTED (StorefrontBlock / DashboardPage
    / account_nav / settings panel) + guarded so it vanishes when the plugin is disabled. Hardcoding it
    here fails the disable test (orphan routes/links/groups).
  status: current; duplicate of ADR 0012 no-hardcoded-foreign-surfaces
- id: section-owned-by-plugin
  pattern: _SECTION_ORDER|_SECTION_LABELS|_SECTION_ICONS|SECTION_REGISTRY
  message: Nav section key/label/icon/placement belongs to the contributing plugin, not a central dict/registry
    in core or context_processors. Centralising it breaks the disable test (the group survives the plugin).
  status: superseded by the v0.81.0 dashboard hubs
---

# ADR 0013: App modularity: disabling a plugin removes ALL its features from storefront and dashboard

## Context
Morpheus is a modular plugin platform: every non-core feature is an app the merchant can toggle off. The goal is full composability. A recent attempt (core/nav.py section registry, d1bfcf1) put dashboard nav-section taxonomy AND plugin-specific aliases (e.g. marketplace→marketing) in core — which both made wrong merges (vendors are their own domain, not marketing) and coupled core to specific plugins, so a plugin's nav placement would NOT disappear when the plugin was disabled. It was reverted (23f5bf8). This ADR makes the modularity contract explicit and names the layer rule that prevents the mistake. Sharpens ADR 0012 and the CLAUDE.md disable test; relates to ADR 0010 (tiny core).

## Decision
Every plugin OWNS and CONTRIBUTES all of its surfaces: storefront blocks/pages, account-nav tiles, dashboard pages, its OWN nav section/group definition (key + label + icon + order), settings panels, agent @tools, URLs, and hooks. None of these may be hardcoded into core/, the admin_dashboard shell, the storefront plugin, or the active theme. Disabling — or removing — a plugin MUST remove EVERY surface it added, from BOTH the storefront and the dashboard, with no orphan left behind: no dead route, no 404 nav link, no stray nav group/header, no storefront block, no account tile, no settings entry. Core provides ONLY the contribution mechanism plus plugin-agnostic safety (e.g. an unknown/blank dashboard section degrades to the 'Apps' catch-all; a disabled plugin's contributions are simply not collected). Curation of the ~9-group nav is therefore opt-in CONVENTION — plugins choose shared standard section keys — never a core-owned merge/alias map. The disable test is the acceptance check: toggle any plugin off and assert zero residual surfaces.

## Consequences
True composability — the platform is whatever set of apps is enabled. Foreign-surface debt found in the 2026-06 audit (reviews list, gift-card checkout, wishlist/downloads/credits account tiles, hardcoded admin nav links for reviews/media/tracking/draft_orders/notifications) must be repaid: each moves into its owning plugin as a contribution. An automated disable test should boot with each plugin off and assert no orphans. Nav coherence comes from plugins opting into a shared section vocabulary, not from core overriding placement.
