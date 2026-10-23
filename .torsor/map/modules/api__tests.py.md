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

# api/tests.py

Symbols in `api/tests.py`.

- L6 `GraphQLAgentAuthTests` (class)
- L7 `test_graphql_agent_requires_bearer_token(self)` (method)
- L15 `test_graphql_agent_accepts_valid_api_key(self)` (method)
- L35 `test_graphql_agent_catalog_write_key_can_create_category(self)` (method) — Core API keys authenticate as agents, not Django staff users.
- L70 `WebhookSignatureTests` (class) — The HMAC helper must produce stable, verifiable signatures.
- L73 `test_signature_round_trips(self)` (method)
- L81 `test_signature_rejects_tampered_payload(self)` (method)
- L88 `test_signature_rejects_wrong_secret(self)` (method)
- L95 `GraphQLDepthLimitTests` (class)
- L96 `test_depth_limit_rejects_deeply_nested_query(self)` (method)
- L110 `RestPermissionTests` (class) — REST defaults: products are public, orders require auth.
- L113 `test_products_are_public(self)` (method)
- L117 `test_orders_require_auth(self)` (method)
- L122 `test_legacy_rest_alias_removed(self)` (method)
- L128 `RequestIdMiddlewareTests` (class) — Every response carries an X-Request-ID header (generated or echoed).
- L131 `test_response_carries_generated_request_id(self)` (method)
- L136 `test_response_echoes_inbound_request_id(self)` (method)
- L141 `JsonFormatterTests` (class)
- L142 `test_json_formatter_emits_required_fields(self)` (method)
- L171 `SentryScrubberTests` (class)
- L172 `test_before_send_scrubs_auth_headers_and_password(self)` (method)
- L198 `DRFExceptionHandlerTests` (class)
- L199 `test_unhandled_drf_exception_returns_envelope(self)` (method)
- L216 `ReadyzTests` (class)
- L217 `test_readyz_reports_version_for_deploy_smoke(self)` (method)
