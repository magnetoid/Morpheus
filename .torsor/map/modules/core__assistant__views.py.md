---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:51'
updated: '2026-06-02T18:07:51'
---

# core/assistant/views.py

Symbols in `core/assistant/views.py`.

- L23 `_conversation_key(request)` (function)
- L35 `assistant_page(request)` (function) — Standalone Linda page — full-screen chat.
- L86 `assistant_invoke(request)` (function) — POST {message: str} → JSON RunResult. Always responds — never 500s.
- L139 `assistant_stream(request)` (function) — POST {message: str} → text/event-stream of run events.
- L209 `assistant_history(request)` (function) — JSON history of the current conversation — used by the floating widget.
