---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-13T01:07:07'
updated: '2026-06-13T01:07:07'
rules:
- id: plugin-owns-dashboard-nav-placement
  applies_to: plugins/installed/admin_dashboard/templates
  forbids: hardcoded plugin-specific dashboard nav links or menu ordering; plugin
    menu placement must come from each plugin's DashboardPage(section, order) contribution
  severity: high
---

# ADR 0016: Plugin-owned dashboard menu placement (WordPress-plugin model)

## Context
User rule (2026-06-13): every arrangement of where a specific menu/nav entry lands in the dashboard for an app's pages must be coded inside that app — like WordPress plugins registering their own admin menu — never hardcoded in admin_dashboard, the dashboard shell, or another layer. This extends the existing plugin contract (a plugin owns all its code; surfaces appear by contributing) to nav PLACEMENT/ORDERING specifically: the section, order, and position of a plugin's dashboard menu entry are the plugin's responsibility, declared on its own DashboardPage contribution.

## Decision
A plugin declares where its dashboard menu entry appears via its own DashboardPage(section=..., order=..., nav=...) contribution in the plugin's plugin.py — NOT via edits to admin_dashboard nav templates or a central nav list. To place an entry relative to another (e.g. "Book taxonomies just below Collections"), set the DashboardPage.order so it sorts into the right position within its section. admin_dashboard must not hardcode plugin-specific nav links (already guarded by admin_dashboard/tests/test_disable_guards.py for the disable-test; placement/order is the same principle). Reference: book_product contributes its 'Book taxonomies' page with section='catalog' + nav='main' + a canonical url; this is the pattern to mirror.

## Consequences
Disabling a plugin removes its menu entry automatically (disable-test clean). Reordering a plugin's nav position is a one-line order= change in that plugin, reviewable in isolation. No central nav file to edit or merge-conflict on. Cost: cross-plugin ordering is implicit via the shared section + order keyspace, so two plugins wanting adjacent slots must coordinate order values.
