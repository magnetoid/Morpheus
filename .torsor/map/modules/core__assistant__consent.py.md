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

# core/assistant/consent.py

Symbols in `core/assistant/consent.py`.

- L75 `_key(conversation_key: str, fingerprint: str)` (function)
- L79 `_fingerprint(tool_name: str, args: dict | None)` (function)
- L85 `is_affirmative(message: str)` (function) — True when a human message reads as an unqualified go-ahead.
- L101 `request(*, conversation_key: str, tool_name: str, args: dict | None)` (function) — Record that Linda proposed this exact call and is awaiting a human yes.
- L112 `consume(*, conversation_key: str, tool_name: str, args: dict | None, human_message: str, human_message_at: float | None=None)` (function) — Spend a pending consent for this exact call, if the human just said yes.
- L143 `clear(*, conversation_key: str, tool_name: str, args: dict | None)` (function) — Drop a pending consent (tests / explicit cancellation).
