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

# core/assistant/models.py

Symbols in `core/assistant/models.py`.

- L16 `AssistantConversation` (class)
- L38 `is_automation(self)` (method) — A scheduled automation's chat, written by its runs; nobody types in it.
- L44 `cost_summary(self)` (method) — Tokens + estimated USD cost for this conversation (dashboard display,
- L69 `AssistantMessage` (class)
- L98 `LindaMemory` (class) — Cross-session memory for Linda. One row per remembered fact.
- L140 `__str__(self)` (method)
- L143 `relevance_score(self, *, half_life_days: float=60.0)` (method) — Exponential temporal decay weighted by source confidence.
- L171 `AssistantBriefing` (class) — Linda's daily morning briefing — one row per day.
- L202 `__str__(self)` (method)
- L206 `JanusLearning` (class) — One file of what Janus, Linda's engine, has learned.
- L243 `__str__(self)` (method)
- L247 `CodeProposal` (class) — A technical report Janus wrote about a defect in Morpheus's own code.
- L290 `__str__(self)` (method)
- L294 `OpsProposal` (class) — A staged *business-level* change (price edit, SEO meta fill, …) awaiting
- L363 `__str__(self)` (method)
- L366 `approve(self, user)` (method) — Staff approval — fail-closed (staff
- L390 `apply(self, user=None)` (method) — Apply each staged change, fail-soft per change. Never raises.
