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

# core/self_improvement/collectors/zero_search.py

Symbols in `core/self_improvement/collectors/zero_search.py`.

- L38 `_normalise_query(q: str)` (function)
- L42 `_over_rate_cap()` (function) — True once >_HOURLY_CAP misses have been recorded this hour. Fail-open on
- L54 `on_search_performed(*, query: str='', result_count: int=-1, **_: Any)` (function) — Hook handler. Drops anything that returned at least one result;
