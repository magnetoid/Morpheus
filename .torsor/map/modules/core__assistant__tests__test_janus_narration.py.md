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

# core/assistant/tests/test_janus_narration.py

Symbols in `core/assistant/tests/test_janus_narration.py`.

- L24 `_api_call(content, tool_calls=1, total=1200, **usage)` (function)
- L41 `_api_error(status=503, retry=1, retryable=True)` (function)
- L56 `_HookCase` (class)
- L57 `setUp(self)` (method)
- L62 `_run(self, payload)` (method)
- L65 `_lines(self)` (method)
- L71 `HookNarrationTests` (class)
- L72 `test_the_words_before_a_tool_call_are_kept_with_the_token_use(self)` (method)
- L81 `test_the_final_answer_is_not_narration(self)` (method)
- L88 `test_thinking_tags_are_not_shown_as_words(self)` (method)
- L92 `test_a_long_narration_is_clipped(self)` (method)
- L96 `test_a_provider_error_records_the_status_never_its_text(self)` (method)
- L103 `ReaderNarrationTests` (class)
- L104 `setUp(self)` (method)
- L111 `_write(self, *records)` (method)
- L116 `test_words_become_a_say_event_and_tokens_add_up(self)` (method)
- L127 `test_a_retry_says_whether_another_try_follows(self)` (method)
- L133 `HookWiringTests` (class)
- L134 `test_the_config_subscribes_every_event_the_chat_reads(self)` (method)
- L141 `test_the_contract_checks_the_same_events(self)` (method)
- L146 `QuestionStepLabelTests` (class)
- L147 `test_the_question_step_says_she_is_asking(self)` (method)
