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

# core/assistant/tools/memory.py

Symbols in `core/assistant/tools/memory.py`.

- L57 `memory_remember_tool(*, key: str, value: str, scope: str='merchant', source: str='user-told')` (function)
- L108 `memory_recall_tool(*, query: str='', scope: str='', limit: int=50)` (function)
- L165 `memory_forget_tool(*, key: str, scope: str='merchant')` (function)
- L174 `get_recent_memories(limit: int=50, *, query: str='')` (function) — Top-of-turn injection helper — returns ``[{scope, key, value}, ...]``
