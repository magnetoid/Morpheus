---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-01T02:50:37'
updated: '2026-07-01T02:50:37'
rules:
- id: disable-removes-every-plugin-surface
  rule: Every surface a plugin adds (StorefrontBlock, DashboardPage, nav entry, settings
    panel, account tile, KPI, activity item, URL) must render only while the plugin
    is enabled; disabling the plugin must remove ALL of them. A surface that survives
    a disable was hard-coded in the wrong layer.
- id: enable-reveals-surfaces-via-contribution-only
  rule: "A plugin's features appear on host surfaces ONLY through its own contributions\
    \ (StorefrontBlock/DashboardPage/contribute_settings_panel/register_urls/core.hooks\
    \ subscriber) \u2014 never by editing core, the theme, or a sibling plugin. If\
    \ enabling a feature required editing a file outside plugins/installed/<name>/,\
    \ that edit belongs back inside the plugin."
- id: hardcoded-plugin-links-gated-by-plugin-enabled
  pattern: href=|url '|{% url
  message: "Referencing a plugin's route/surface from a shared shell (dashboard nav,\
    \ theme, sibling)? Wrap it in {% plugin_enabled \"<name>\" %} so it disappears\
    \ on disable \u2014 otherwise admin_dashboard/tests/test_disable_guards.py fails\
    \ the build. Prefer a DashboardPage/StorefrontBlock contribution over a hard-coded\
    \ link."
---

# ADR 0023: Plugins behave like WordPress plugins: enable reveals every surface, disable removes every surface

## Context
The merchant's mental model is WordPress: turning an app ON makes its features, sections, and UI elements appear across the storefront and dashboard; turning it OFF makes all of them vanish. Morpheus already encodes this as the "modularity contract" and ADR 0016 (WordPress plugin menu model), but it keeps getting violated by surfaces hard-coded in the wrong layer — a nav link, settings panel, storefront block, or account tile that renders regardless of whether the owning plugin is enabled. Known debt that this caused: loyalty's /account/points/ and the payments settings panel once survived a disable; storefront account sub-pages still query plugin models directly. The invariant must be an explicit, enforceable rule, not just an aspiration.

## Decision
Every feature a plugin adds — storefront sections/blocks, dashboard pages, sidebar/nav entries, settings panels, account tiles, KPIs, activity-feed items, URLs — MUST reach its host surface ONLY by contribution (StorefrontBlock(slot=...), DashboardPage, contribute_settings_panel, register_urls, or a core.hooks/filter subscriber) and MUST be rendered only while the plugin is enabled. Enabling the plugin reveals all of its surfaces with zero edits to core, the theme, or a sibling plugin; disabling it removes ALL of them from Morpheus OS. The two litmus tests are binding: (1) delete plugins/installed/<name>/ and no dangling view/URL/template/import remains anywhere; (2) toggle the plugin off and every surface it contributed disappears. Any plugin surface that must be referenced from a shared shell (e.g. a hard-coded dashboard nav link) MUST be wrapped in {% plugin_enabled "<name>" %} so it vanishes on disable. A surface that survives a disable was hard-coded in the wrong layer and is a bug.

## Consequences
Adding a feature that touches any surface outside plugins/installed/<name>/ is a smell — that edit belongs back inside the plugin as a contribution. The disable-test gate (admin_dashboard/tests/test_disable_guards.py, run as its own CI step) fails the build when a plugin nav link is added to the dashboard shell without a {% plugin_enabled %} guard. Contributed surfaces are rendered by the plugin registry only while the plugin is enabled, so enable/disable parity is automatic for anything routed through contributions. Remaining debt to repay: storefront account sub-pages (orders list, credits, downloads) still query plugin models directly rather than assembling via contributions.
