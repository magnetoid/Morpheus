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

# api/tests_csrf_bearer.py

Symbols in `api/tests_csrf_bearer.py`.

- L19 `_Base` (class)
- L20 `setUp(self)` (method)
- L27 `_post(self, path, **extra)` (method)
- L36 `LlmTasksCsrfTests` (class)
- L37 `test_a_session_post_without_the_token_is_refused(self)` (method)
- L42 `test_a_bearer_request_skips_csrf_and_reaches_the_view(self)` (method)
- L54 `test_a_session_get_is_not_affected(self)` (method)
- L59 `AgentInvokeCsrfTests` (class)
- L60 `test_a_session_post_without_the_token_is_refused(self)` (method)
- L65 `test_a_bearer_request_skips_csrf_and_reaches_the_view(self)` (method)
- L70 `test_stream_is_gated_the_same_way(self)` (method)
- L77 `GraphqlBearerCsrfTests` (class) — An external agent POSTs to /graphql/ with a Bearer token and no cookies.
- L85 `setUp(self)` (method)
- L100 `test_a_bearer_query_reaches_graphql_without_a_csrf_token(self)` (method)
- L111 `test_a_session_post_without_the_token_is_still_refused(self)` (method)
