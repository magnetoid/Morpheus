---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/assistant/tools/memory.py

Symbols in `core/assistant/tools/memory.py`.

- L45 `memory_remember_tool(*, key: str, value: str, scope: str='merchant', source: str='user-told')` (function)
- L88 `memory_recall_tool(*, query: str='', scope: str='', limit: int=50)` (function)
- L126 `memory_forget_tool(*, key: str, scope: str='merchant')` (function)
- L135 `get_recent_memories(limit: int=50)` (function) — Top-of-turn injection helper — returns ``[{scope, key, value}, ...]``
