---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/tests/test_registry_url_ordering.py

Symbols in `core/tests/test_registry_url_ordering.py`.

- L19 `UrlMountOrderingTests` (class)
- L20 `test_plugin_route_beats_the_discovery_router(self)` (method) — bookvault's connect/ is its own view again, not a discovery 404.
- L26 `test_discovery_still_routes_dashboard_page_slugs(self)` (method) — A slug a plugin did NOT mount itself still falls through to the
- L32 `test_shell_pages_unaffected(self)` (method)
- L39 `test_equal_prefixes_keep_registration_order(self)` (method) — The sort is stable: same-depth prefixes keep first-registrant-wins
