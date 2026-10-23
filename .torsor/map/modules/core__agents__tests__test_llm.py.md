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

# core/agents/tests/test_llm.py

Symbols in `core/agents/tests/test_llm.py`.

- L24 `ToolSchemaTests` (class)
- L25 `setUp(self)` (method)
- L33 `test_openai_schema(self)` (method)
- L41 `test_anthropic_schema(self)` (method)
- L46 `test_api_name_matches_provider_pattern_for_all_registered_tools(self)` (method)
- L56 `MockProviderTests` (class)
- L57 `test_pops_scripted_responses_in_order(self)` (method)
- L62 `test_echoes_user_when_exhausted(self)` (method)
- L67 `test_records_calls(self)` (method)
- L73 `OpenAIArgParsingTests` (class) — Malformed tool-call JSON falls back to {} AND records a parse_error so the
- L82 `_provider_with_args(self, raw_arguments: str)` (method)
- L97 `test_valid_json_parsed(self)` (method)
- L104 `test_malformed_json_falls_back_to_empty_and_records_error(self)` (method)
- L111 `ProviderResolutionTests` (class)
- L112 `test_unknown_provider_resolves_to_graceful_mock(self)` (method)
- L119 `test_apikey_fun_is_a_registered_provider(self)` (method)
- L142 `test_deepseek_is_a_registered_provider(self)` (method)
- L161 `test_moonshot_is_a_registered_provider(self)` (method)
- L184 `QwenProviderTests` (class) — Qwen Cloud (Alibaba Model Studio; owner's ask, 2026-10-19), wired in every
- L188 `_cfg(self, **fields)` (method)
- L199 `test_qwen_is_a_registered_provider(self)` (method)
- L210 `test_qwen_defaults_are_the_international_endpoint_and_its_key(self)` (method)
- L220 `test_qwen_answers_without_hidden_thinking(self)` (method)
- L240 `test_qwen_models_are_priced(self)` (method)
- L247 `DegradedSentinelTests` (class)
- L248 `test_is_degraded_response_truth_table(self)` (method)
- L259 `FallbackRouterTests` (class)
- L260 `_provider(self, name, *, raises=None, text='ok')` (method)
- L274 `test_failover_to_working_secondary(self)` (method)
- L284 `test_sentinel_reports_primary_error_not_last_secondary(self)` (method)
- L303 `test_unconfigured_fallbacks_are_not_added_as_secondaries(self)` (method)
- L328 `test_configured_fallback_is_added(self)` (method)
- L351 `ReasoningRetryTests` (class) — A reasoning model that spends its whole budget thinking returns HTTP 200
- L358 `_completion(self, content, finish_reason='stop', reasoning_tokens=0, tool_calls=None)` (method)
- L374 `_provider(self, completions)` (method)
- L389 `test_empty_reasoning_completion_is_retried_with_headroom(self)` (method)
- L403 `test_a_tool_call_with_empty_text_is_not_a_reasoning_burn(self)` (method)
- L410 `test_a_healthy_answer_is_not_retried(self)` (method)
- L415 `test_two_empty_answers_do_not_loop(self)` (method)
