---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-04T23:46:10'
updated: '2026-06-04T23:46:10'
rules:
- id: prefer-db-over-hardcode
  pattern: = '[A-Z][a-z].*Store'|DEFAULT_.*=|HARDCODE
  message: Merchant-facing options must be DB-driven (StoreSettings/SiteSeoSettings/PluginConfig/model
    field), editable from the dashboard. Only hardcode true constants; resolve dynamic
    values from the DB with a fallback.
---

# ADR 0009: Morpheus OS is database-driven, not hardcoded — settings live in the DB and are editable

## Context
Morpheus is a configurable commerce OS. Hardcoded constants (brand strings, options, routes, copy) make features uneditable by the merchant and cause drift like the "Morpheus Store" title bug, where an env/settings constant overrode the merchant's DB-stored store name.

## Decision
Almost every option/value must be dynamically connected to the database (StoreSettings, SiteSeoSettings, PluginConfig, model fields) so it is changeable later from the dashboard. Only hardcode when there is no reasonable alternative (true constants, stable framework wiring), and prefer pointing at the DB source of truth over a literal. When reading a brand/option/flag, resolve it from the DB with a sensible fallback chain — never a bare module constant the merchant cannot change.

## Consequences
Features stay merchant-configurable; fewer hardcode-vs-DB divergence bugs. New literals that represent merchant-facing options should instead be DB-backed settings with a dashboard surface.
