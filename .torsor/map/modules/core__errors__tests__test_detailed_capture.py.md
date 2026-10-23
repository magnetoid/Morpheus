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

# core/errors/tests/test_detailed_capture.py

Symbols in `core/errors/tests/test_detailed_capture.py`.

- L28 `_Clean` (class)
- L29 `setUp(self)` (method)
- L35 `_staff_client(self)` (method)
- L45 `SwitchTests` (class)
- L46 `test_off_until_turned_on_and_off_again(self)` (method)
- L54 `test_it_switches_itself_off_at_the_end_time(self)` (method)
- L59 `test_a_window_is_capped(self)` (method)
- L63 `test_turning_it_on_is_audited(self)` (method)
- L70 `LogBridgeTests` (class)
- L71 `_emit(self, level: int, msg: str, name: str='morpheus.catalog')` (method)
- L77 `test_a_warning_is_kept_only_while_detailed_capture_is_on(self)` (method)
- L86 `test_an_error_is_always_kept(self)` (method)
- L90 `test_request_warnings_are_left_to_the_middleware(self)` (method)
- L96 `RequestCaptureTests` (class)
- L97 `test_nothing_extra_is_recorded_while_off(self)` (method)
- L103 `test_a_rejected_request_is_recorded_with_its_view(self)` (method)
- L112 `test_a_broken_internal_link_is_recorded_once(self)` (method)
- L122 `test_a_404_from_elsewhere_is_not_a_broken_link(self)` (method)
- L128 `test_a_slow_response_is_recorded(self)` (method)
- L137 `test_secret_query_values_are_not_kept(self)` (method)
- L145 `BrowserCaptureTests` (class)
- L146 `_ingest(self, **payload)` (method)
- L153 `test_detailed_browser_reports_are_dropped_while_off(self)` (method)
- L157 `test_detailed_browser_reports_are_kept_while_on(self)` (method)
- L164 `test_the_capture_script_learns_the_mode_from_its_tag(self)` (method)
- L173 `_crash(message: str='boom')` (function)
- L180 `ReportTests` (class)
- L181 `test_the_report_carries_what_a_fixer_needs(self)` (method)
- L194 `test_errors_come_before_warnings(self)` (method)
- L203 `test_a_resolved_group_leaves_the_report_until_it_fires_again(self)` (method)
- L217 `test_the_command_prints_the_report_and_resolves(self)` (method)
- L229 `PageTests` (class)
- L230 `test_the_switch_needs_staff_and_a_post(self)` (method)
- L247 `test_the_report_downloads_as_markdown_and_json(self)` (method)
- L257 `test_resolving_from_the_detail_page(self)` (method)
- L269 `AgentToolTests` (class)
- L270 `test_the_report_is_an_agent_tool_behind_diagnostics_read(self)` (method)
- L285 `FingerprintTests` (class)
- L286 `test_volatile_ids_do_not_split_one_problem_into_many_groups(self)` (method)
- L304 `test_an_id_partly_scrubbed_as_a_phone_number_is_still_the_same_problem(self)` (method)
- L315 `test_different_status_codes_stay_different_problems(self)` (method)
