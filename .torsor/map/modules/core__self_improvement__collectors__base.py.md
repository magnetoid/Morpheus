---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# core/self_improvement/collectors/base.py

Symbols in `core/self_improvement/collectors/base.py`.

- L25 `Signal` (class) — One raw observation, pre-persistence.
- L40 `Collector` (class) — Subclass-and-implement contract.
- L51 `__init_subclass__(cls, **kwargs: Any)` (method)
- L58 `run(self)` (method) — Yield signals. Subclasses must implement.
- L62 `execute(self)` (method) — Run + persist, wrapped in an SiIngestJob.
