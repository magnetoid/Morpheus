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

# core/self_improvement/recommend.py

Symbols in `core/self_improvement/recommend.py`.

- L40 `Cluster` (class)
- L50 `run_analyzer(window_hours: int=24)` (function) — Pull signals from the last `window_hours`, cluster, rank, plan,
- L89 `_cluster(qs)` (function) — Deterministic clustering — one cluster per (class, fingerprint).
- L114 `_score(c: Cluster)` (function) — impact_score = severity × reach × evidence × age_decay.
- L130 `_process_cluster(cluster: Cluster)` (function) — Plan → Verify → Gate → Write one SiRecommendation. Returns the
- L224 `_plan(cluster: Cluster, pol)` (function) — Call the analyzer LLM with the recommend prompt. Returns the
- L272 `_heuristic_plan(cluster: Cluster)` (function) — Fallback when no LLM is available — surface the cluster as a
- L309 `_class_for_source(source: str)` (function)
- L313 `_module_for(class_name: str)` (function)
- L321 `_default_title(cluster: Cluster)` (function)
- L325 `_summarise(cluster: Cluster)` (function)
- L335 `_parse_json(text: str)` (function)
