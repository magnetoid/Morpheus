---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:48'
updated: '2026-06-10T20:08:48'
---

# core/assistant/tools/memory.py

Symbols in `core/assistant/tools/memory.py`.

- L45 `memory_remember_tool(*, key: str, value: str, scope: str='merchant', source: str='user-told')` (function)
- L80 `memory_recall_tool(*, query: str='', scope: str='', limit: int=50)` (function)
- L112 `memory_forget_tool(*, key: str, scope: str='merchant')` (function)
- L120 `get_recent_memories(limit: int=50)` (function) — Top-of-turn injection helper — returns ``[{scope, key, value}, ...]``
