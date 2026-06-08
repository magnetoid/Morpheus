---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-07T15:28:23'
updated: '2026-06-07T15:28:23'
rules:
- id: extend-dont-invent-sections
  pattern: section\s*=
  message: Register into an EXISTING dashboard section from the known set; don't invent
    a new top-level section. New concept? Contribute into the closest existing section.
- id: no-hardcoded-foreign-surfaces
  pattern: templates/(admin_dashboard|storefront)/.*\.html
  message: A plugin's surface must be CONTRIBUTED (DashboardPage/StorefrontBlock/account_nav/settings
    panel), not hardcoded into admin_dashboard/storefront/theme. Hardcoded foreign
    surfaces fail the disable test (orphan 404s).
- id: settings-extend-category
  pattern: contribute_settings_panel|settings_categor
  message: Settings must extend a shared settings CATEGORY (one coherent hub), not
    a bespoke standalone settings page that duplicates an existing one.
---

# ADR 0012: Plugins extend named shared surfaces, not bolt on new ones

## Context
A platform of many plugins only feels seamless (Shopify-like) if apps EXTEND shared surfaces rather than each adding their own. The 2026-06 dashboard audit found the symptoms of slippage: ~21 top-level nav sections, duplicated settings (AI flags, caching/SW, GA4), and hardcoded plugin surfaces in the storefront/theme. These happen when a plugin ADDS a surface instead of extending an existing one.

## Decision
Every plugin surfaces itself ONLY by contributing into a core-owned, named extension point: settings → a fixed set of CATEGORIES; dashboard → a fixed set of SECTIONS (~9, Shopify-style: Home, Orders, Products, Customers, Marketing, Discounts, Content, Analytics, Settings); storefront → slots (StorefrontBlock, account_nav); agent → the @tool registry; cross-plugin behaviour → core.hooks. Rule of thumb: EXTEND the existing surface when the concept already exists (a tax plugin extends the Taxes settings category — it never creates a new top-level "MyTax" section); create a NEW surface only for a genuinely new concept, and even then contribute it into a known section, never hardcode it into admin_dashboard, the storefront, or the theme. The core must hold a single source of truth for the allowed sections/categories so plugins can only register into a known group. Validated by the disable test: toggling a plugin off removes every surface it added.

## Consequences
N plugins feel like one product; no duplicated/slightly-different settings; no orphan 404s when a plugin is disabled. The highest-leverage work is hardening the extension-point registries (e.g. a real SECTION_ORDER / settings-category registry), not adding features. Supersedes ad-hoc section lists.
