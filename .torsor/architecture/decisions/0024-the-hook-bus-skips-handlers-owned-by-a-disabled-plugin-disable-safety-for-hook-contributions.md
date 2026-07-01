---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-01T03:40:12'
updated: '2026-07-01T03:40:12'
rules:
- id: hook-bus-gates-on-owner-active-state
  pattern: def fire|def filter|_owner_inactive|set_active_check
  message: "core/hooks.py fire()/filter() must skip handlers owned by an inactive\
    \ plugin (owner tagged via register_hook plugin=..., predicate via set_active_check).\
    \ Do NOT remove this gating \u2014 it's what makes hook-contributed surfaces vanish\
    \ on disable (ADR 0023). Covered by core/tests/test_hook_disable_gating.py."
- id: optional-plugin-surface-via-hook-not-hard-import
  pattern: plugins/installed/(admin_dashboard|storefront)/.*(views|dashboard).*\.py
  message: "Rendering an OPTIONAL plugin's surface (card/column/panel) from a shared\
    \ shell? Contribute it via the plugin's hook (PRODUCT_FORM_CARDS etc.) so the\
    \ bus auto-hides it on disable \u2014 never a hard `from plugins.installed.<X>\
    \ import` (a try/except guards absence, not disable). Foundational plugins (catalog/orders/customers)\
    \ are exempt \u2014 they're never disabled."
---

# ADR 0024: The hook bus skips handlers owned by a disabled plugin (disable-safety for hook contributions)

## Context
A merchant disabled book_product but its 'Book details' card kept rendering on the product editor. Two causes combined: (1) plugins.registry.deactivate() drops a plugin's contributions (StorefrontBlock/DashboardPage/SettingsPanel) but INTENTIONALLY does not unwind the hooks it wired in ready() — so a re-enable doesn't double-register them; (2) core/hooks.py fire()/filter() invoked every registered handler regardless of whether the owning plugin was still active. So a runtime-disabled plugin's register_hook handlers kept firing, and any surface contributed through a hook (PRODUCT_FORM_CARDS, DASHBOARD_KPIS, ACTIVITY_FEED, ACCOUNT_SUMMARY_FIELDS, …) survived the disable. book_product additionally hard-wired its card into admin_dashboard (template block + try/except view import), which bypassed the bus entirely. This is the ADR 0023 disable-test failing in the view/hook layer, invisible to test_disable_guards.py (which only scans base.html).

## Decision
The hook bus is the disable-safety net for hook-based contributions: core/hooks.py fire() and filter() MUST skip any handler whose owning plugin is inactive. Ownership is tagged at subscription time — Plugin.register_hook passes plugin=self.name to hook_registry.register, which stores (priority, handler, mode, plugin). The registry wires its is_active predicate into the bus via hook_registry.set_active_check(self.is_active) at construction, so core/hooks never imports plugins.* (the core boundary stays clean); core-owned handlers register with plugin=None and are never gated. Consequence: every register_hook/contribute_* surface is disable-safe for free. Corollary (ADR 0006/0023): a shared shell (admin_dashboard, storefront, a theme) must render an OPTIONAL plugin's surface via that plugin's hook/contribution — never a hard import (a try/except ImportError guards absence, not disable; a disabled plugin is still importable). book_product's product-form card moved to PRODUCT_FORM_CARDS/PRODUCT_FORM_SAVED accordingly.

## Consequences
Disabling a plugin now removes its contributed cards/KPIs/feed/account tiles immediately, at runtime, no restart. Guarded by core/tests/test_hook_disable_gating.py. Remaining known leak (still bypasses the bus via hard import): bookvault's product-list column + fulfilment card in admin_dashboard/views_split/products.py — self-hides on is_authenticated() but leaks if disabled-while-configured; migrate to PRODUCT_FORM_CARDS + a new PRODUCT_LIST_COLUMNS hook. The orders imports in storefront/views/account.py are foundational (orders is never disabled), so they don't bite the disable test.
