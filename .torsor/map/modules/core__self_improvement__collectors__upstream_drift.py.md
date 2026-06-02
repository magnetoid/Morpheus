---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:51'
updated: '2026-06-02T18:07:51'
---

# core/self_improvement/collectors/upstream_drift.py

Symbols in `core/self_improvement/collectors/upstream_drift.py`.

- L46 `UpstreamDriftCollector` (class)
- L49 `__init__(self, repo_root: Path | None=None)` (method)
- L52 `run(self)` (method)
- L86 `_signal_for(self, path: str, added_str: str, removed_str: str, upstream_ref: str)` (method)
- L104 `_classify(self, path: str, added: int, removed: int, upstream_ref: str)` (method)
- L116 `_count_hunks(self, path: str, upstream_ref: str)` (method) — Approximate hunk count via unified-diff `@@` headers. Cheap
- L127 `_severity_for(classification: str)` (method)
- L136 `_resolve_upstream_ref(self)` (method) — Return the git ref representing canonical Morpheus, or '' if
- L151 `_read_customizations_upstream(self)` (method)
- L166 `_auto_detect_upstream_ref(self)` (method) — Find the latest tag matching `morpheus-*`. Returns '' if none
- L181 `_git(self, args: list[str])` (method)
- L196 `_int(s: str)` (method)
