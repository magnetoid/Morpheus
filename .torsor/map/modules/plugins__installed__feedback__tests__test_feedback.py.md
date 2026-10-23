---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/feedback/tests/test_feedback.py

Symbols in `plugins/installed/feedback/tests/test_feedback.py`.

- L19 `_staff(email='staff@example.com')` (function)
- L24 `SubmitTests` (class)
- L25 `setUp(self)` (method)
- L28 `_post(self, **payload)` (method)
- L32 `test_anonymous_cannot_submit(self)` (method)
- L40 `test_staff_submits_message_only(self)` (method)
- L53 `test_empty_message_is_rejected(self)` (method)
- L59 `test_screenshot_is_stored(self)` (method)
- L67 `test_garbage_screenshot_does_not_lose_the_ticket(self)` (method) — A broken image must not cost the report — the message is the point.
- L76 `test_client_errors_are_attached(self)` (method)
- L82 `test_console_log_is_attached_and_sanitised(self)` (method)
- L99 `QueueTests` (class)
- L100 `setUp(self)` (method)
- L104 `test_anonymous_cannot_read_the_queue(self)` (method)
- L108 `test_staff_sees_the_queue_and_detail(self)` (method)
- L114 `test_status_can_be_updated(self)` (method)
- L124 `ContributionTests` (class) — The shell must carry the entry and the modal WITHOUT importing this app.
- L127 `setUp(self)` (method)
- L130 `test_dropdown_entry_and_modal_render_in_the_shell(self)` (method)
- L135 `test_surfaces_vanish_when_the_app_is_disabled(self)` (method)
