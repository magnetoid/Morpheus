---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:48'
updated: '2026-06-10T20:08:48'
---

# api/tests.py

Symbols in `api/tests.py`.

- L6 `GraphQLAgentAuthTests` (class)
- L7 `test_graphql_agent_requires_bearer_token(self)` (method)
- L15 `test_graphql_agent_accepts_valid_api_key(self)` (method)
- L33 `WebhookSignatureTests` (class) — The HMAC helper must produce stable, verifiable signatures.
- L36 `test_signature_round_trips(self)` (method)
- L44 `test_signature_rejects_tampered_payload(self)` (method)
- L51 `test_signature_rejects_wrong_secret(self)` (method)
- L58 `GraphQLDepthLimitTests` (class)
- L59 `test_depth_limit_rejects_deeply_nested_query(self)` (method)
- L73 `RestPermissionTests` (class) — REST defaults: products are public, orders require auth.
- L76 `test_products_are_public(self)` (method)
- L80 `test_orders_require_auth(self)` (method)
- L85 `test_legacy_rest_alias_removed(self)` (method)
- L91 `RequestIdMiddlewareTests` (class) — Every response carries an X-Request-ID header (generated or echoed).
- L94 `test_response_carries_generated_request_id(self)` (method)
- L99 `test_response_echoes_inbound_request_id(self)` (method)
- L104 `JsonFormatterTests` (class)
- L105 `test_json_formatter_emits_required_fields(self)` (method)
- L127 `SentryScrubberTests` (class)
- L128 `test_before_send_scrubs_auth_headers_and_password(self)` (method)
- L153 `DRFExceptionHandlerTests` (class)
- L154 `test_unhandled_drf_exception_returns_envelope(self)` (method)
