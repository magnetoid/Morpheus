---
type: decision
status: accepted
tags:
- adr
links:
- '0003-settings-dashboard-unify-never-duplicate-fixes-belong-in-the-owning-app'
created: '2026-06-03T00:00:00'
updated: '2026-06-03T00:00:00'
rules:
- id: domain-owns-its-settings-page
  rule: A commerce domain with a dedicated settings page (DashboardPage) must NOT also
    contribute its own SettingsPanel in that domain's category. Fold the config into
    the page instead — a self-panel is a duplicate sidebar entry.
  where: plugin manifests + domain dashboard views
  severity: warn
- id: domain-page-absorbs-sibling-panels
  rule: A domain settings page must render sibling-plugin SettingsPanels whose category
    == the domain, so new domain plugins surface ON the page (not as a separate scattered
    settings entry).
  severity: warn
- id: suppress-page-owned-category-nav
  rule: Categories owned by a nav='settings' DashboardPage (section == slug) are suppressed
    from settings_category_nav so the sidebar shows ONE entry per domain (the page).
  where: plugins/context_processors.py
  severity: warn
---

# ADR 0004: The domain page is the single home — it absorbs sibling settings

## Context
ADR 0003 said "unify per domain, fix in the owning plugin." In practice the
settings sidebar still rendered *two* nav systems at once:

1. `settings_category_nav` — Shopify-style `SettingsCategory` links, populated by
   any plugin's `SettingsPanel(category=X)`.
2. `settings_sections` — `DashboardPage`s with `nav='settings'`, grouped by section.

A commerce domain (Tax, Shipping) has a rich `DashboardPage` **and** a same-named
`SettingsCategory`. The domain plugin *also* contributed its own `SettingsPanel`
in that category → pure self-duplication ("2 taxes", "2 shippings"). The tax
panel was even a no-op (wrote plugin-config nothing reads; the service reads the
`TaxConfiguration` model). And sibling plugins legitimately land in a domain
category (e.g. `bookvault` → `category='shipping'`), so removing only the domain
plugin's own panel does **not** collapse the category.

User directive: *"unify all shipping into one page, and all new shipping plugins
should appear on that page too, because it is the page that categorizes shipping
settings. Same for taxes. I don't want scattered options around settings — it is
not logical."*

## Decision
Each commerce domain has **exactly one owning settings page** — the rich
`DashboardPage`. That page is the single home for **all** of the domain's
settings:

- **(a)** the domain's own config, folded into the page natively (no
  self-`SettingsPanel`); and
- **(b)** every **sibling** plugin's `SettingsPanel` whose `category == <domain>`,
  rendered on the page by reading `plugin_registry` (a shared `_panel_card`
  partial; each card POSTs to that plugin's existing
  `/dashboard/settings/<plugin>/` handler).

A new plugin that adds domain settings just contributes
`SettingsPanel(category='<domain>')` and it appears **automatically** on the
domain page — never as a separate scattered entry. The standalone
`SettingsCategory` nav link is **suppressed** for page-owned domains (the page IS
the category landing), so the sidebar shows one entry per domain.

## Consequences
- `context_processors` excludes page-owned categories (those with a
  `nav='settings'` `DashboardPage` whose `section == slug`) from
  `settings_category_nav`.
- Domain plugins drop their own `SettingsPanel` and fold config into the page
  view (`set_config` or a config model).
- Money-path config (shipping carrier credentials) must stay readable by services
  after folding — verify before/after.
- First applications: **tax** (ADR 0003 / commit 90a06c9 removed the dead panel +
  folded `TaxConfiguration`) and **shipping** (fold carrier creds + absorb the
  `bookvault` panel onto the Shipping page). The rule generalizes to any future
  domain hub.
