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

# core/brain/analyst.py

Symbols in `core/brain/analyst.py`.

- L42 `_summarize_signals(signals: dict)` (function) — A compact, token-cheap text digest of the signals for the prompt.
- L100 `_parse_json(text: str)` (function) — Lenient JSON extraction from an LLM reply (strips code fences / prose).
- L117 `analyze(signals: dict | None=None)` (function) — Run the LLM over the signals → structured recommendations (uncached).
- L167 `get_analysis(*, force: bool=False)` (function) — Cached analysis for the dashboard. `force` re-runs the LLM.
- L189 `cached_analysis()` (function) — Whatever's cached, without triggering an LLM call (for page GET).
