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

# core/assistant/tests/test_janus_activity.py

Symbols in `core/assistant/tests/test_janus_activity.py`.

- L25 `_payload(event, tool, args=None, **extra)` (function)
- L36 `HookScriptTests` (class)
- L37 `setUp(self)` (method)
- L42 `_run(self, payload)` (method)
- L46 `_lines(self)` (method)
- L51 `test_one_line_per_step_start_and_end(self)` (method)
- L71 `test_the_plan_keeps_its_full_result(self)` (method)
- L76 `test_long_arguments_are_clipped(self)` (method)
- L83 `test_it_never_answers_so_it_can_never_block_a_call(self)` (method)
- L89 `test_garbage_and_other_events_are_ignored_quietly(self)` (method)
- L94 `test_a_missing_path_argument_is_harmless(self)` (method)
- L97 `test_it_imports_nothing_but_the_standard_library(self)` (method)
- L108 `HooksConfigTests` (class)
- L109 `test_both_tool_hooks_run_the_script_on_this_turns_file(self)` (method)
- L123 `ReaderTests` (class)
- L124 `setUp(self)` (method)
- L131 `_write(self, *records, partial='')` (method)
- L137 `test_reset_empties_the_file_from_the_last_turn(self)` (method)
- L143 `test_steps_start_then_finish(self)` (method)
- L154 `test_a_failed_step_says_so(self)` (method)
- L162 `test_a_half_written_line_waits_for_its_end(self)` (method)
- L169 `test_nothing_is_replayed(self)` (method)
- L174 `test_a_missing_file_reads_as_no_news(self)` (method)
- L178 `test_the_plan_is_the_todo_tools_full_list(self)` (method)
- L205 `test_store_tools_name_the_area_and_whether_they_change_it(self)` (method)
- L236 `test_unknown_tools_still_show_up(self)` (method)
- L247 `test_end_without_an_id_closes_the_oldest_open_step_of_that_tool(self)` (method)
