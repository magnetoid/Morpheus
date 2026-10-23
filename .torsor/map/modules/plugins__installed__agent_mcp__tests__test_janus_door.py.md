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

# plugins/installed/agent_mcp/tests/test_janus_door.py

Symbols in `plugins/installed/agent_mcp/tests/test_janus_door.py`.

- L31 `_entry(**over)` (function)
- L44 `_store_tokens(*entries)` (function)
- L52 `_rpc(method, params=None)` (function)
- L56 `_FakeTool` (class)
- L57 `__init__(self, name, *, scopes=(), requires_approval=False)` (method)
- L66 `invoke(self, args, agent=None, context=None)` (method)
- L71 `ExternalGateTests` (class) — core/assistant/gates.py — the one gate chain, for an external conversation.
- L74 `setUp(self)` (method)
- L80 `_reason(self, tool, *, approved=frozenset(), scopes=('catalog.write',))` (method)
- L94 `test_the_keys_name_their_token(self)` (method)
- L101 `test_a_yes_in_the_conversation_is_never_consent(self)` (method)
- L111 `test_a_protected_tool_the_merchant_approved_for_the_token_runs(self)` (method)
- L114 `test_a_write_inside_the_tokens_scopes_runs(self)` (method)
- L117 `test_the_scope_check_still_comes_first(self)` (method)
- L122 `test_an_external_key_without_a_grant_set_is_refused(self)` (method)
- L126 `TurnPrincipalTests` (class)
- L127 `test_a_turn_token_carries_its_principal(self)` (method)
- L146 `test_the_runtime_mints_the_principal_it_is_given(self)` (method)
- L157 `ExternalEdgeTests` (class) — The MCP edge holds an external turn to its token, looked up on every call.
- L160 `setUp(self)` (method)
- L185 `_token(self, *, principal=TOKEN_ID, key=None)` (method)
- L194 `_post(self, method, params=None, token=None)` (method)
- L202 `_call(self, name)` (method)
- L206 `test_the_catalogue_is_the_tokens_scopes(self)` (method)
- L210 `test_a_write_inside_the_scopes_runs(self)` (method)
- L214 `test_a_protected_write_needs_the_tokens_approval_not_a_yes(self)` (method)
- L223 `test_a_revoked_token_stops_the_turn(self)` (method)
- L228 `test_a_principal_that_does_not_own_the_conversation_is_refused(self)` (method)
- L233 `test_a_dashboard_conversation_cannot_carry_a_principal(self)` (method)
- L238 `_fake_outcome(**over)` (function)
- L245 `JanusDoorMcpTests` (class)
- L246 `setUp(self)` (method)
- L255 `_post(self, method, params=None, token=TOKEN)` (method)
- L263 `_ask(self, args, token=TOKEN)` (method)
- L267 `test_tools_list_offers_the_door(self)` (method)
- L271 `test_janus_answers_a_question(self)` (method)
- L286 `test_a_conversation_continues_under_its_own_key(self)` (method)
- L292 `test_a_token_without_the_grant_is_refused(self)` (method)
- L298 `test_a_legacy_token_without_scopes_is_refused(self)` (method)
- L304 `test_janus_cannot_call_itself(self)` (method)
- L312 `JanusDoorServiceTests` (class) — The door's own rules, called directly (the queue is stubbed to stay pending).
- L315 `setUp(self)` (method)
- L326 `test_a_running_turn_is_fetched_later(self)` (method)
- L336 `test_another_token_cannot_read_a_turn(self)` (method)
- L344 `test_two_running_questions_is_the_limit(self)` (method)
- L351 `test_too_many_questions_a_minute_are_refused(self)` (method)
- L361 `test_a_turn_whose_worker_died_is_reported_lost(self)` (method)
- L369 `test_a_token_revoked_before_the_turn_runs_is_not_run(self)` (method)
- L379 `JanusDoorGraphqlTests` (class)
- L380 `setUp(self)` (method)
- L389 `_gql(self, query, variables=None, token=TOKEN)` (method)
- L401 `test_ask_janus_answers(self)` (method)
- L406 `test_the_graphql_door_needs_its_own_grant(self)` (method)
- L412 `test_janus_turn_reads_an_answer(self)` (method)
