---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# api/tests.py

Symbols in `api/tests.py`.

- L6 `GraphQLAgentAuthTests` (class)
- L7 `test_graphql_agent_requires_bearer_token(self)` (method)
- L15 `test_graphql_agent_accepts_valid_api_key(self)` (method)
- L35 `WebhookSignatureTests` (class) — The HMAC helper must produce stable, verifiable signatures.
- L38 `test_signature_round_trips(self)` (method)
- L46 `test_signature_rejects_tampered_payload(self)` (method)
- L53 `test_signature_rejects_wrong_secret(self)` (method)
- L60 `GraphQLDepthLimitTests` (class)
- L61 `test_depth_limit_rejects_deeply_nested_query(self)` (method)
- L75 `RestPermissionTests` (class) — REST defaults: products are public, orders require auth.
- L78 `test_products_are_public(self)` (method)
- L82 `test_orders_require_auth(self)` (method)
- L87 `test_legacy_rest_alias_removed(self)` (method)
- L93 `RequestIdMiddlewareTests` (class) — Every response carries an X-Request-ID header (generated or echoed).
- L96 `test_response_carries_generated_request_id(self)` (method)
- L101 `test_response_echoes_inbound_request_id(self)` (method)
- L106 `JsonFormatterTests` (class)
- L107 `test_json_formatter_emits_required_fields(self)` (method)
- L136 `SentryScrubberTests` (class)
- L137 `test_before_send_scrubs_auth_headers_and_password(self)` (method)
- L163 `DRFExceptionHandlerTests` (class)
- L164 `test_unhandled_drf_exception_returns_envelope(self)` (method)
