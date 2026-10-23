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

# core/assistant/tests/test_assistant.py

Symbols in `core/assistant/tests/test_assistant.py`.

- L12 `AssistantBootTests` (class)
- L13 `test_assistant_constructs_without_plugins(self)` (method)
- L16 `test_default_tools_loaded(self)` (method)
- L33 `AssistantTurnTests` (class) — One turn on the Janus engine, with the engine mocked (no model call).
- L36 `_turn(self, payload, key)` (method)
- L49 `test_completed_turn_is_stored(self)` (method)
- L59 `test_engine_error_becomes_a_friendly_failed_turn(self)` (method)
- L64 `test_missing_engine_is_reported_not_raised(self)` (method)
- L73 `AssistantStreamTests` (class) — What the chat receives while a turn runs, and what the reply records.
- L76 `setUp(self)` (method)
- L83 `_stream(self, fake, key='t:stream', **context)` (method)
- L96 `test_tool_calls_reach_the_chat_while_the_turn_runs(self)` (method)
- L122 `test_steps_and_the_plan_reach_the_chat(self)` (method)
- L142 `test_the_prompt_teaches_only_the_janus_tools_the_turn_has(self)` (method)
- L155 `test_the_reply_records_tokens_and_counts_toward_the_spend_cap(self)` (method)
- L176 `test_the_system_prompt_stays_the_same_between_messages(self)` (method)
- L193 `ToolMigrationTests` (class) — D3: orders.search / orders.get moved to the orders plugin but stay in
- L213 `test_read_tools_contributed_by_their_plugins(self)` (method)
- L231 `test_linda_still_exposes_migrated_tools_by_name(self)` (method)
- L236 `test_not_imported_from_core_ecommerce_anymore(self)` (method)
- L252 `test_migrated_orders_search_queries_real_orders(self)` (method)
- L259 `FilesystemToolTests` (class)
- L260 `test_list_dir_returns_entries(self)` (method)
- L267 `test_path_traversal_rejected(self)` (method)
- L274 `FallbackStoreTests` (class)
- L275 `test_file_history_round_trip(self, tmp_path=None)` (method)
