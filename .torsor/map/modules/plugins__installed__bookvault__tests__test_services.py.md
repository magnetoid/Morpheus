---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/bookvault/tests/test_services.py

Symbols in `plugins/installed/bookvault/tests/test_services.py`.

- L23 `_seed_config(**overrides)` (function) — Helper: write a fake PluginConfig so the API client behaves as configured.
- L42 `IsbnLineExtractionTests` (class) — Only 13-digit SKUs are sent to BV — that's the WP plugin's contract.
- L45 `test_skips_non_13_char_sku(self)` (method)
- L57 `test_keeps_13_char_sku(self)` (method)
- L73 `ShippingRatesTests` (class) — get_shipping_rates: empty input → empty output (no API hit);
- L77 `test_empty_lines_returns_empty(self)` (method)
- L86 `test_normalised_output_shape(self)` (method)
- L108 `AuthenticateTests` (class) — authenticate() persists Token/StoreID/Authenticated into PluginConfig.
- L111 `test_happy_path_writes_config(self)` (method)
- L127 `test_request_failure_returns_error(self)` (method)
- L136 `SendOrderTests` (class) — send_order: writes a BookvaultOrderLink row + captures BVRef.
- L139 `setUp(self)` (method)
- L154 `test_writes_bv_ref_to_link_row(self)` (method)
- L165 `test_skips_when_disabled(self)` (method)
- L172 `test_no_config_returns_error(self)` (method)
- L180 `UninstallTests` (class) — send_uninstall_notification: POSTs the site URL to BV's uninstall
- L184 `setUp(self)` (method)
- L187 `test_disconnect_wipes_local_credentials_on_success(self)` (method)
- L201 `test_disconnect_wipes_even_when_webhook_fails(self)` (method)
- L213 `AuthorizeUrlTests` (class) — authorize_url builds register/login OAuth-style URLs for the
- L217 `test_register_url_includes_action_param(self)` (method)
- L224 `test_login_url_has_no_action_param(self)` (method)
- L231 `ProductLinkStatusTests` (class) — product_link_status: Linked / Partial / Unlinked aggregate.
- L234 `setUp(self)` (method)
- L242 `test_no_links_yet_returns_unlinked(self)` (method)
- L245 `test_linked_returns_linked(self)` (method)
- L252 `test_locations_stored_as_int_list(self)` (method) — The product_form template renders fulfilment-location pills
- L266 `test_bulk_helper_one_query_per_page(self)` (method) — bulk_link_status_for must NOT fan out N+1 — it should hit
