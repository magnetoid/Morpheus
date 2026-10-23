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

# plugins/installed/agent_core/tests/test_invoke_audience.py

Symbols in `plugins/installed/agent_core/tests/test_invoke_audience.py`.

- L31 `_exfiltrating_provider()` (function) — A model that does what the attacker's message asks: dump customers.
- L45 `PublicAgentEdgeTests` (class)
- L46 `setUp(self)` (method)
- L56 `_customer_search_ran(self)` (method)
- L59 `_invoke(self)` (method)
- L67 `test_anonymous_cannot_invoke_the_worker(self)` (method)
- L72 `test_logged_in_shopper_cannot_invoke_the_worker(self)` (method)
- L78 `test_anonymous_cannot_stream_the_worker(self)` (method)
- L91 `test_anonymous_cannot_invoke_the_worker_over_graphql(self)` (method)
- L109 `test_staff_can_still_invoke_the_worker(self)` (method)
- L115 `_invoke_with_token(self, graphql_scopes)` (method)
- L142 `test_narrow_bearer_token_cannot_escalate_through_the_worker(self)` (method)
- L149 `test_wildcard_bearer_token_can_invoke_the_worker(self)` (method)
