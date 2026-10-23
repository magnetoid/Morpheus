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

# plugins/installed/agent_core/tests/test_janus_activity_log.py

Symbols in `plugins/installed/agent_core/tests/test_janus_activity_log.py`.

- L20 `_staff()` (function)
- L26 `JanusActivityLogTests` (class)
- L27 `setUp(self)` (method)
- L31 `_journal(self, day='2026-09-20', body='')` (method)
- L41 `test_empty_state_renders(self)` (method) — No learning yet must not break the page.
- L48 `test_journal_entries_appear_newest_first(self)` (method)
- L67 `test_memory_line_is_parsed_into_clock_and_kind(self)` (method)
- L73 `test_line_without_the_expected_shape_is_skipped(self)` (method) — A heading or stray text must not be shown as an event.
- L86 `test_audit_events_are_merged_in(self)` (method)
- L100 `test_forgotten_learning_is_described(self)` (method)
- L112 `test_helpers_never_raise_without_tables(self)` (method) — The view helpers swallow a broken read rather than 500 the page.
- L121 `test_tool_calls_are_shown_and_summarised(self)` (method) — agents.decision rows are the engine's live tool-call trail.
- L144 `test_failed_tool_call_is_flagged_and_counted(self)` (method)
- L165 `test_mcp_string_error_output_is_flagged_too(self)` (method) — Rows written before v0.87.2 by the MCP edge (Linda's calls) carry
