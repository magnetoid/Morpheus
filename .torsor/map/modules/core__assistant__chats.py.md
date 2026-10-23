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

# core/assistant/chats.py

Symbols in `core/assistant/chats.py`.

- L26 `thread_key(user)` (function) — The widget's running thread — one per staff member.
- L31 `running_thread(user)` (function) — The widget's thread, owned by its user (rows from before chats had no owner).
- L42 `start_chat(user, first_message: str)` (function) — A new chat, titled by its first message.
- L51 `owned_chat(user, chat_id)` (function) — The chat `chat_id` when it is `user`'s; 404 otherwise — never someone else's.
- L63 `chats_for(user, *, archived: bool=False)` (function) — `user`'s chats with at least one message, most recent first.
- L77 `transcript(conv: AssistantConversation, limit: int=100)` (function) — What the chat page shows when a chat is reopened: the words, not the tool rows.
- L84 `chats_page(request)` (function)
- L100 `chat_action(request, chat_id, action: str)` (function)
