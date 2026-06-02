---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-02T21:22:56'
updated: '2026-06-02T21:22:56'
rules:
- id: settings-no-duplication
  rule: No duplicate or near-duplicate settings surfaces in the settings dashboard;
    unify per domain.
  where: settings dashboard
  severity: warn
- id: unify-in-owning-app
  rule: Settings unification/merges are coded in the plugin that owns the setting,
    never patched at the admin_dashboard layer.
  severity: warn
---

# ADR 0003: Settings dashboard: unify, never duplicate — fixes belong in the owning app

## Context
The settings dashboard aggregates surfaces contributed by many plugins (StorefrontBlock / DashboardPage / SettingsPanel). Duplicate or near-duplicate settings + UI elements have crept in — e.g. shipping exposing separate Zones and Rates pages for one domain, or the same toggle/section appearing in more than one place. Duplicates confuse merchants and drift out of sync.

## Decision
There must be NO duplication on the settings dashboard. Duplicate or closely-related settings/elements are UNIFIED into a single surface (one page/section per domain). Crucially, the unification is implemented in the PLUGIN that owns the setting — its own dashboard view + template + contribution — NOT patched or special-cased at the admin_dashboard aggregation layer. The dashboard only renders what plugins contribute; the merge happens at the source. New settings reuse an existing section in their owning plugin instead of adding a parallel one.

## Consequences
When two pages cover one domain (e.g. shipping zones + rates), merge them into a single page within that plugin. Reviewers + coach/check_drift should flag duplicate settings surfaces. First application: shipping → one 'Shipping' page combining zones + rates.
