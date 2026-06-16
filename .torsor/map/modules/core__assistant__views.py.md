---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/assistant/views.py

Symbols in `core/assistant/views.py`.

- L24 `_conversation_key(request)` (function)
- L36 `assistant_page(request)` (function) — Standalone Linda page — full-screen chat.
- L92 `assistant_invoke(request)` (function) — POST {message: str} → JSON RunResult. Always responds — never 500s.
- L157 `assistant_stream(request)` (function) — POST {message: str} → text/event-stream of run events.
- L232 `assistant_history(request)` (function) — JSON history of the current conversation — used by the floating widget.
