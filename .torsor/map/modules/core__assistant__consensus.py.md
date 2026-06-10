---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:48'
updated: '2026-06-10T20:08:48'
---

# core/assistant/consensus.py

Symbols in `core/assistant/consensus.py`.

- L38 `configured_providers()` (function) — Names of providers that actually have an API key — the consensus panel.
- L54 `_review_prompt(proposal)` (function)
- L63 `_parse_verdict(provider: str, text: str)` (function) — Pull the {approve,score,concerns} JSON out of a model reply. Fail-soft:
- L83 `review_with(provider_name: str, proposal)` (function) — One provider's independent verdict on the proposal. Fail-soft per provider.
- L103 `aggregate(verdicts: list[dict])` (function) — Decide from a list of verdicts. <2 valid → insufficient (defer to human).
- L124 `evaluate(proposal)` (function) — Run the full consensus panel over a proposal (advisory; no side effects on
