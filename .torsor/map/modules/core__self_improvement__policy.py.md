---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# core/self_improvement/policy.py

Symbols in `core/self_improvement/policy.py`.

- L21 `ClassPolicy` (class)
- L151 `policy_for(class_name: str)` (function) — Return the effective policy for a class. Settings overrides defaults.
- L177 `all_policies()` (function) — Return policies for every known class, in display order.
- L182 `decide_action(*, class_name: str, confidence: float, is_customization_safe: bool=True)` (function) — Return one of `auto_apply`, `propose`, `advise`, `suppress`.
- L202 `export_for_dashboard()` (function) — Serialise every policy for the Settings tab table render.
