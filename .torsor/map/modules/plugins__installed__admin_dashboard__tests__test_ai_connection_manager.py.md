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

# plugins/installed/admin_dashboard/tests/test_ai_connection_manager.py

Symbols in `plugins/installed/admin_dashboard/tests/test_ai_connection_manager.py`.

- L14 `_ai()` (function)
- L18 `ConnectionManagerRenderTests` (class)
- L19 `setUp(self)` (method)
- L29 `test_connected_provider_shows_as_card_unconnected_in_picker(self)` (method)
- L43 `test_no_connected_shows_empty_state(self)` (method)
- L49 `DisconnectTests` (class)
- L50 `setUp(self)` (method)
- L57 `test_disconnect_clears_keys_and_reassigns_active(self)` (method)
- L76 `test_disconnect_unknown_provider_rejected(self)` (method)
- L81 `test_disconnect_requires_post(self)` (method)
- L87 `DisconnectPermissionBoundaryTests` (class) — The three mandatory permission-boundary tests for the disconnect view.
- L90 `setUp(self)` (method)
- L94 `test_anonymous_blocked(self)` (method)
- L98 `test_authed_non_staff_blocked(self)` (method)
- L106 `test_staff_allowed(self)` (method)
- L116 `ProviderCatalogUXTests` (class) — Curated model suggestions + provider blurbs improve the connect flow.
- L119 `setUp(self)` (method)
- L127 `test_model_datalist_and_blurb_render(self)` (method)
- L136 `test_qwen_cloud_is_offered(self)` (method)
- L148 `test_every_provider_has_models(self)` (method)
- L159 `FetchedModelsPersistenceTests` (class) — Fetch persists the provider's model list server-side, so the
- L163 `setUp(self)` (method)
- L171 `test_fetched_models_render_as_permanent_dropdown(self)` (method)
- L186 `test_probe_persists_returned_models_to_config(self)` (method)
