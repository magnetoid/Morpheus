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

# core/assistant/janus_progress_hook.py

Symbols in `core/assistant/janus_progress_hook.py`.

- L33 `_clip(args: dict)` (function)
- L40 `_int(value)` (function)
- L44 `_model_call(extra: dict)` (function) — What a model call said before its tool calls, and the tokens it used.
- L72 `_model_error(extra: dict)` (function) — A failed model call: its HTTP status and whether Janus may try again
- L86 `record(payload: dict)` (function) — The line to write for one hook call, or None when there is nothing to show.
- L120 `main(argv: list[str], stdin)` (function)
