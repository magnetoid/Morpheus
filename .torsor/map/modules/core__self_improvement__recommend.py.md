---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# core/self_improvement/recommend.py

Symbols in `core/self_improvement/recommend.py`.

- L39 `Cluster` (class)
- L49 `run_analyzer(window_hours: int=24)` (function) — Pull signals from the last `window_hours`, cluster, rank, plan,
- L81 `_cluster(qs)` (function) — Deterministic clustering — one cluster per (class, fingerprint).
- L106 `_score(c: Cluster)` (function) — impact_score = severity × reach × evidence × age_decay.
- L113 `_process_cluster(cluster: Cluster)` (function) — Plan → Verify → Gate → Write one SiRecommendation. Returns the
- L176 `_plan(cluster: Cluster, pol)` (function) — Call the analyzer LLM with the recommend prompt. Returns the
- L215 `_heuristic_plan(cluster: Cluster)` (function) — Fallback when no LLM is available — surface the cluster as a
- L252 `_class_for_source(source: str)` (function)
- L256 `_module_for(class_name: str)` (function)
- L264 `_default_title(cluster: Cluster)` (function)
- L268 `_summarise(cluster: Cluster)` (function)
- L278 `_parse_json(text: str)` (function)
