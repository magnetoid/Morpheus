---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/agents/memory.py

Symbols in `core/agents/memory.py`.

- L24 `MemoryItem` (class)
- L31 `WorkingMemory` (class) — Per-run scratchpad.
- L34 `__init__(self)` (method)
- L37 `set(self, key: str, value: Any)` (method)
- L40 `get(self, key: str, default: Any=None)` (method)
- L43 `all(self)` (method)
- L47 `_NamespacedStore` (class) — In-memory keyed store; subclassed for episodic + semantic.
- L50 `__init__(self)` (method)
- L54 `write(self, namespace: str, item: MemoryItem)` (method)
- L63 `read(self, namespace: str, *, min_confidence: float=0.0)` (method)
- L67 `forget(self, namespace: str, key: str | None=None)` (method)
