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

# plugins/installed/catalog/tests/test_graphql_mutation_auth.py

Symbols in `plugins/installed/catalog/tests/test_graphql_mutation_auth.py`.

- L26 `_Info` (class)
- L27 `__init__(self, request)` (method)
- L31 `_request(*, user=None, token_scopes=None, agent_scopes=None)` (function)
- L41 `CheckScopeTests` (class)
- L42 `_user(self, *, staff)` (method)
- L47 `test_anonymous_is_refused(self)` (method)
- L50 `test_signed_in_customer_is_refused(self)` (method)
- L53 `test_dashboard_staff_session_is_allowed(self)` (method)
- L58 `test_mcp_token_is_confined_to_its_scopes(self)` (method)
- L69 `test_api_key_with_the_scope_is_allowed_despite_the_empty_token_stash(self)` (method)
- L73 `test_api_key_is_confined_to_its_scopes(self)` (method)
- L79 `test_api_key_admin_scope_covers_catalog(self)` (method)
- L85 `AgentEndpointTests` (class) — The same rules through the real middleware and GraphQL view.
- L88 `_key(self, scopes)` (method)
- L94 `_post(self, key, query)` (method)
- L104 `test_key_without_catalog_write_cannot_create_a_category(self)` (method)
- L114 `test_catalog_write_key_cannot_archive_a_category(self)` (method)
