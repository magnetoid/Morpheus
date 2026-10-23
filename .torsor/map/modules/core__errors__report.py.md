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

# core/errors/report.py

Symbols in `core/errors/report.py`.

- L21 `_states(fingerprints: list[str])` (function)
- L27 `status_of(group_state, last_seen)` (function) — open | resolved | regressed, from the decision and the latest event.
- L34 `_event(e)` (function)
- L51 `build_report(*, days: int=7, include_resolved: bool=False, limit: int=50, fingerprint: str='')` (function) — The open groups of the last ``days`` days, or one group (``fingerprint``, any age).
- L151 `_title(event)` (function)
- L159 `_context_line(ctx: dict)` (function)
- L182 `render_markdown(report: dict)` (function) — The report as Markdown, written to be pasted into Claude Code.
- L223 `_render_group(n: int, g: dict)` (function) — One group of the Markdown report.
- L270 `resolve(fingerprint: str, *, user=None, note: str='')` (function) — Mark a group resolved. False when no event has that fingerprint.
- L296 `resolve_stale(days: int=STALE_DAYS)` (function) — Resolve every unresolved group whose newest event is older than ``days``.
- L322 `reopen(fingerprint: str)` (function)
