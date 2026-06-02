---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:51'
updated: '2026-06-02T18:07:51'
---

# core/self_improvement/prompts.py

Symbols in `core/self_improvement/prompts.py`.

- L23 `recommend_v1(*, module: str, recommendation_class: str, customization_summary: str, signal_summary: str, file_excerpts: str, prior_fixes_summary: str, reversibility: bool, auto_threshold: float, protected_paths: list[str])` (function) — The canonical recommend prompt. Returns a string ready to send.
- L88 `verify_v1(*, recommendation: dict[str, Any])` (function) — Adversarial verifier prompt. Different framing from recommend_v1
- L123 `weekly_digest_v1(*, accepted: int, rejected: int, rollback_rate: float, top_classes: list[dict])` (function) — Tiny prompt for the weekly digest email body. The LLM has just
- L148 `_count(blob: str)` (function) — How many signal rows are summarised in the blob (heuristic — counts
