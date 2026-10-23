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

# core/agents/pricing.py

Symbols in `core/agents/pricing.py`.

- L55 `_norm(name: str)` (function) — One spelling for a model name: no vendor prefix ('anthropic/…'), dots as
- L64 `_match(model: str)` (function)
- L78 `estimate_cost(model: str, prompt_tokens: int, completion_tokens: int)` (function) — USD estimate for a (model, token-counts) pair. 0.0 for unknown models.
- L89 `is_priced(model: str)` (function) — Whether we have a price for this model (vs. estimating 0).
