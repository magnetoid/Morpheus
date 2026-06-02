---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:51'
updated: '2026-06-02T18:07:51'
---

# core/assistant/models.py

Symbols in `core/assistant/models.py`.

- L9 `AssistantConversation` (class)
- L20 `AssistantMessage` (class)
- L43 `LindaMemory` (class) — Cross-session memory for Linda. One row per remembered fact.
- L75 `__str__(self)` (method)
- L78 `relevance_score(self, *, half_life_days: float=60.0)` (method) — Exponential temporal decay weighted by source confidence.
