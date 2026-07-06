---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-06T11:45:41'
updated: '2026-07-06T11:45:41'
rules:
- id: about-and-version-pages
  statement: Morpheus must maintain a public About page and a dashboard Version page
    that surfaces detailed version data (running core version, per-plugin + theme
    versions with enabled/active state, the docs/RELEASE_NOTES.md changelog, and update
    status).
  applies_to: plugins/installed/storefront (About /about/), plugins/installed/release_notes
    (Settings -> Version & updates), core/versioning.py, docs/RELEASE_NOTES.md
  guard: The storefront must serve /about/. The dashboard must expose Settings ->
    Version & updates (release_notes plugin) rendering docs/RELEASE_NOTES.md + MORPHEUS_VERSION,
    and the version/updates surface must show core.versioning.component_versions()
    (core + per-plugin + theme versions with state). Do not delete these pages or
    strip the detailed version inventory / changelog.
  severity: warning
---

# ADR 0030: Morpheus ships an About page and a detailed Version page

## Context
Users and operators must be able to see what the platform is (About) and exactly what version is running (Version), in detail. Both surfaces already exist; this ADR makes them a standing requirement. About = the public storefront /about/ page (plugins/installed/storefront/urls.py -> storefront.views.about; themes/*/templates/storefront/about.html). Version = the dashboard Settings -> Version & updates page (release_notes plugin: DashboardPage slug='version' -> release_notes.views.version_updates), which renders docs/RELEASE_NOTES.md as release cards next to the running MORPHEUS_VERSION; alongside it the admin_dashboard Updates surface shows the full component version inventory from core/versioning.py (core_version, plugin_versions with enabled state, theme_versions, component_versions) plus platform_update_status. Complements ADR 0019 (versioned release notes) and ADR 0020 (every push to main is a new version).

## Decision
Morpheus must ship and maintain (1) a public About page and (2) a Version page that exposes DETAILED version data: the running core version (MORPHEUS_VERSION), every plugin's version + enabled state, theme versions, the release-notes changelog (docs/RELEASE_NOTES.md), and update/health status. The version inventory (core/versioning.py) is foundational and stays in core — it must include core itself, same reasoning as observability and the self-improvement loop — so it can never be a disableable plugin; the release-notes/Version & updates page is the release_notes plugin; the About page is a storefront page. Every MORPHEUS_VERSION bump adds a dated docs/RELEASE_NOTES.md entry (ADR 0019/0020).

## Consequences
The Version page always reflects core.versioning.component_versions(); every version bump adds a dated docs/RELEASE_NOTES.md entry; removing the About page, or reducing the Version page below the detailed component inventory + changelog, is a drift violation.
