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

# plugins/installed/agent_core/tests/test_automation_tools.py

Symbols in `plugins/installed/agent_core/tests/test_automation_tools.py`.

- L30 `_tool(name)` (function)
- L36 `AutomationToolsTests` (class)
- L37 `setUp(self)` (method)
- L43 `_ctx(self, key=None, **extra)` (method)
- L51 `_run(self, tool_name, /, key=None, **args)` (method)
- L54 `_job(self, **fields)` (method)
- L65 `test_reading_is_free_and_every_change_needs_approval(self)` (method)
- L78 `test_linda_can_reach_all_six(self)` (method)
- L95 `test_create_schedules_a_linda_automation_owned_by_the_merchant(self)` (method)
- L117 `test_create_every_n_minutes(self)` (method)
- L123 `test_create_says_when_scheduled_runs_are_off(self)` (method)
- L131 `test_create_refuses_a_bad_or_missing_schedule(self)` (method)
- L146 `test_list_shows_each_automation_with_its_schedule_and_last_answer(self)` (method)
- L160 `test_pause_resume_and_delete(self)` (method)
- L176 `test_run_now_queues_a_linda_run(self)` (method)
- L184 `test_run_now_leaves_worker_automations_to_the_page(self)` (method)
- L190 `test_an_unknown_id_is_a_clear_error(self)` (method)
- L197 `test_an_automation_cannot_change_automations_but_may_list_them(self)` (method)
- L206 `test_an_external_agent_cannot_see_or_change_automations(self)` (method)
- L217 `test_outside_a_linda_chat_the_tools_refuse(self)` (method)
- L223 `test_a_role_that_may_not_open_the_automations_page_is_refused(self)` (method)
- L243 `AutomationToolsAtTheEdgeTests` (class) — The real tool, called the way Janus calls it: over MCP with a turn token.
- L246 `setUp(self)` (method)
- L253 `_say(self, key, text)` (method)
- L260 `_call(self, key, name, args)` (method)
- L282 `test_creating_one_waits_for_the_merchants_yes(self)` (method)
- L296 `test_an_automation_run_cannot_create_one(self)` (method)
