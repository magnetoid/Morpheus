---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/agentic_checkout/tests/test_acp.py

Symbols in `plugins/installed/agentic_checkout/tests/test_acp.py`.

- L29 `_enable_plugin_and_tokens()` (function)
- L53 `AcpCheckoutTests` (class)
- L54 `setUp(self)` (method)
- L80 `_post(self, path, body=None, token=_TOKEN)` (method)
- L89 `_get(self, path, token=_TOKEN)` (method)
- L93 `_create_session(self, quantity=2)` (method)
- L115 `_assert_conformant(self, session: dict)` (method)
- L157 `test_create_session_returns_conformant_shape(self)` (method)
- L177 `test_create_without_buyer_is_not_ready(self)` (method)
- L187 `test_get_session(self)` (method)
- L195 `test_get_unknown_session_404(self)` (method)
- L201 `test_update_replaces_line_items(self)` (method)
- L216 `test_cancel_session(self)` (method)
- L229 `test_complete_returns_unsupported_message_error(self)` (method)
- L247 `test_no_bearer_rejected(self)` (method)
- L251 `test_invalid_bearer_rejected(self)` (method)
- L255 `test_valid_token_missing_scope_forbidden(self)` (method)
- L259 `test_valid_token_with_scope_allowed(self)` (method)
- L269 `test_out_of_stock_surfaces_message(self)` (method)
- L282 `test_plain_storefront_cart_not_accessible(self)` (method) — A Cart without the acp_session marker is invisible (404), so an
- L300 `test_acp_created_cart_is_retrievable(self)` (method)
- L306 `test_expired_session_not_found(self)` (method)
- L319 `test_non_numeric_quantity_yields_message_not_500(self)` (method)
- L329 `test_unknown_currency_yields_message_not_charge(self)` (method)
- L342 `test_update_with_bad_quantity_does_not_empty_cart(self)` (method)
- L357 `AcpManifestTests` (class)
- L358 `setUp(self)` (method)
- L362 `test_acp_manifest_renders(self)` (method)
- L373 `AcpFeedTests` (class)
- L374 `setUp(self)` (method)
- L378 `_get(self, path, token=_TOKEN)` (method)
- L382 `test_feed_renders(self)` (method)
- L390 `test_feed_empty_when_google_shopping_unavailable(self)` (method) — If google_shopping's mapping import fails, the feed serves a valid,
