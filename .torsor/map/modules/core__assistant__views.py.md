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

# core/assistant/views.py

Symbols in `core/assistant/views.py`.

- L30 `_conversation_key(request)` (function)
- L42 `assistant_page(request)` (function) — Standalone Linda page — full-screen chat.
- L96 `assistant_stream(request)` (function) — POST {message: str} → text/event-stream of run events.
- L202 `assistant_history(request)` (function) — JSON history of a conversation: one of your chats (``?conversation=``)
- L222 `_conversation_cost_summary(key: str)` (function) — Tokens + estimated USD for the conversation. Empty when DB-less.
- L236 `assistant_page_help(request)` (function) — POST page context → JSON {ok, summary, numbers, actions, message}.
