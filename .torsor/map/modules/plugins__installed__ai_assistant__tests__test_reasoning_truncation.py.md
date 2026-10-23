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

# plugins/installed/ai_assistant/tests/test_reasoning_truncation.py

Symbols in `plugins/installed/ai_assistant/tests/test_reasoning_truncation.py`.

- L29 `_response(content, finish_reason='stop', reasoning_tokens=0)` (function) — Mimic an OpenAI-compatible ChatCompletion.
- L46 `TruncationDetectionTests` (class)
- L47 `test_detects_empty_content_burned_on_reasoning(self)` (method)
- L50 `test_plain_length_truncation_is_not_a_reasoning_burn(self)` (method) — A non-reasoning model that ran out of room mid-sentence still
- L55 `test_normal_completion_is_not_truncation(self)` (method)
- L58 `test_malformed_response_does_not_raise(self)` (method)
- L63 `ReasoningRetryTests` (class)
- L64 `_gateway(self)` (method)
- L77 `test_retries_with_headroom_and_returns_the_answer(self)` (method)
- L100 `test_retries_at_most_once(self)` (method) — Two empty answers means something else is wrong — don't loop, and
- L113 `test_healthy_completion_is_not_retried(self)` (method)
