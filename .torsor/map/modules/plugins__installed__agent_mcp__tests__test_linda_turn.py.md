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

# plugins/installed/agent_mcp/tests/test_linda_turn.py

Symbols in `plugins/installed/agent_mcp/tests/test_linda_turn.py`.

- L28 `_rpc(method, params=None)` (function)
- L32 `_FakeTool` (class)
- L33 `__init__(self, name, *, scopes=(), requires_approval=False)` (method)
- L42 `invoke(self, args, agent=None, context=None)` (method)
- L47 `LindaTurnEdgeTests` (class)
- L48 `setUp(self)` (method)
- L67 `_say(self, text)` (method) — What the chat view does before the engine starts: store the human turn.
- L73 `_token(self, *, mode='general', ttl=85, user=None)` (method)
- L78 `_post(self, method, params=None, token=None)` (method)
- L86 `_call(self, name, args=None, token=None)` (method)
- L90 `_text(resp)` (method)
- L94 `test_turn_token_authenticates_the_admin_endpoint(self)` (method)
- L97 `test_tampered_token_is_rejected(self)` (method)
- L101 `test_expired_token_is_rejected(self)` (method)
- L106 `test_user_demoted_mid_turn_loses_access(self)` (method)
- L112 `test_turn_token_is_not_a_bearer_credential_anywhere_else(self)` (method)
- L124 `test_listing_hides_tools_outside_lindas_scope_profile(self)` (method)
- L129 `test_restricted_mode_narrows_the_catalogue(self)` (method)
- L139 `test_a_shop_fact_is_proposed_not_saved_until_the_merchant_says_yes(self)` (method)
- L150 `test_out_of_profile_tool_is_refused_even_if_called_directly(self)` (method)
- L155 `test_platform_internals_and_shopper_tools_are_not_lindas(self)` (method)
- L168 `test_read_tool_runs_as_the_merchant_and_lands_in_the_conversation(self)` (method)
- L178 `test_approval_tool_is_refused_until_the_merchant_says_yes(self)` (method)
- L190 `test_retry_in_the_same_turn_cannot_approve_itself(self)` (method)
- L202 `test_one_yes_authorises_one_call(self)` (method)
- L211 `test_negation_beats_affirmation(self)` (method)
- L219 `test_consent_is_bound_to_the_exact_arguments(self)` (method)
- L226 `test_standing_token_grant_is_not_consent(self)` (method)
- L234 `test_a_write_without_its_own_approval_flag_still_needs_a_yes(self)` (method)
- L248 `test_spending_and_data_sharing_tools_need_a_yes(self)` (method)
- L256 `test_a_self_reporting_audit_runs_without_asking(self)` (method)
- L262 `test_yes_then_a_retry_with_confirmed_spends_the_consent(self)` (method)
- L271 `test_kill_switch_stops_every_write_linda_could_make(self)` (method)
- L278 `test_an_oversized_result_is_cut_with_a_hint(self)` (method)
- L291 `test_refused_write_is_audited_with_the_human_as_actor(self)` (method)
- L299 `test_executed_write_is_audited_with_the_human_as_actor(self)` (method)
- L308 `LindaCatalogueTests` (class) — The real registry: Linda can reach the store work merchants ask for.
- L311 `_names(self, mode: str, *, superuser: bool=False)` (method)
- L319 `test_general_mode_covers_everyday_store_work(self)` (method)
- L337 `test_every_mode_can_ask_the_merchant_a_question(self)` (method)
- L341 `test_every_mode_has_tools_to_work_with(self)` (method)
- L347 `test_prompt_and_skills_name_only_tools_linda_has(self)` (method)
- L367 `test_every_tool_declares_the_arguments_its_handler_requires(self)` (method)
- L389 `test_settings_list_reads_the_stored_config(self)` (method)
- L401 `LegacyEndpointTests` (class)
- L402 `test_tools_list_survives_a_cache_outage(self)` (method)
- L410 `test_external_clients_are_not_refused_by_csrf(self)` (method)
