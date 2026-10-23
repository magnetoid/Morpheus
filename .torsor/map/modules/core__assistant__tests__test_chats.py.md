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

# core/assistant/tests/test_chats.py

Symbols in `core/assistant/tests/test_chats.py`.

- L21 `_FakeAssistant` (class) — Stands in for the engine: records the key it was given, answers once.
- L27 `stream(self, *, message, conversation_key, context)` (method)
- L33 `_events(response)` (function)
- L38 `ChatsTests` (class)
- L39 `setUp(self)` (method)
- L53 `_say(self, message, conversation=None)` (method)
- L61 `_chat(self, user, title='Old chat')` (method)
- L69 `test_the_first_message_starts_a_chat_owned_by_you_and_titled_by_it(self)` (method)
- L77 `test_a_chat_continues_in_its_own_conversation(self)` (method)
- L83 `test_someone_elses_chat_cannot_be_continued(self)` (method)
- L88 `test_the_widget_keeps_its_one_running_thread(self)` (method)
- L94 `test_opening_a_chat_shows_its_messages(self)` (method)
- L101 `test_someone_elses_chat_cannot_be_opened(self)` (method)
- L107 `test_the_chats_tab_lists_only_your_chats(self)` (method)
- L115 `test_a_chat_can_be_renamed_and_archived_by_its_owner_only(self)` (method)
- L131 `test_chats_is_a_tab_of_lindas_section(self)` (method)
- L137 `_automation_chat(self)` (method)
- L149 `test_an_automations_chat_opens_as_its_report_without_a_composer(self)` (method)
- L156 `test_an_automations_chat_takes_no_messages(self)` (method)
- L163 `test_the_chats_tab_marks_automation_chats(self)` (method)
- L171 `ModelPickerTests` (class) — A model can be picked for the next message (owner's ask, 2026-10-10).
- L179 `setUp(self)` (method)
- L193 `test_the_composer_offers_the_models_with_a_key(self)` (method)
- L198 `test_the_pick_rides_on_the_message(self)` (method)
- L206 `test_one_model_needs_no_picker(self)` (method)
