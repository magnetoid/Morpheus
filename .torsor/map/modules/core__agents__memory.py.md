---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:48'
updated: '2026-06-10T20:08:48'
---

# core/agents/memory.py

Symbols in `core/agents/memory.py`.

- L23 `MemoryItem` (class)
- L30 `WorkingMemory` (class) — Per-run scratchpad.
- L33 `__init__(self)` (method)
- L36 `set(self, key: str, value: Any)` (method)
- L39 `get(self, key: str, default: Any=None)` (method)
- L42 `all(self)` (method)
- L46 `_NamespacedStore` (class) — In-memory keyed store; subclassed for episodic + semantic.
- L49 `__init__(self)` (method)
- L53 `write(self, namespace: str, item: MemoryItem)` (method)
- L62 `read(self, namespace: str, *, min_confidence: float=0.0)` (method)
- L66 `forget(self, namespace: str, key: str | None=None)` (method)
