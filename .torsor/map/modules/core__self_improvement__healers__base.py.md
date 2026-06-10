---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# core/self_improvement/healers/base.py

Symbols in `core/self_improvement/healers/base.py`.

- L31 `HealResult` (class)
- L37 `Healer` (class) — Subclass per issue class. Set ``class_name``.
- L43 `propose(self, recommendation)` (method) — Return {kind, files, patch, ...} for the dashboard preview.
- L47 `safe_to_apply(self, recommendation)` (method) — (ok, reason). Final guard.
- L51 `apply(self, recommendation)` (method) — Make the change. Must be idempotent or guarded.
- L54 `verify(self, recommendation)` (method) — Default: assume apply() returned True == verified.
- L58 `rollback(self, recommendation)` (method) — Best-effort revert. Default is no-op.
- L70 `register_healer(class_name: str)` (function) — Decorator. Use as ``@register_healer('seo_gap')`` on the
- L84 `get_healer(class_name: str)` (function)
- L89 `known_classes()` (function)
