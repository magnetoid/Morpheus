---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/partner_portal.py

Symbols in `plugins/partner_portal.py`.

- L37 `Period` (class) — The last ``days`` calendar days (today included) and the span before it.
- L46 `dates(self)` (method)
- L50 `label(self)` (method)
- L54 `period_from(request, default: int=DEFAULT_PERIOD)` (function) — The period a portal page reports on, from ``?days=`` (7, 30 or 90).
- L69 `period_links(period: Period)` (function)
- L81 `change(current, previous)` (function) — How ``current`` moved against ``previous``, for a KPI tile.
- L98 `change_points(current: Decimal, previous: Decimal)` (function) — A rate's move in percentage points (a rate's percent change misleads).
- L108 `rate(part, whole)` (function) — ``part / whole`` as a percentage with one decimal; 0 when ``whole`` is 0.
- L115 `daily(rows, period: Period)` (function) — Spread ``{date: value}`` over every day of ``period`` (missing days are 0).
- L121 `sparkline(values, *, width: int=100, height: int=32)` (function) — SVG geometry for a KPI tile's trend line (``viewBox 0 0 width height``).
- L136 `bar_chart(values, period: Period, *, fmt=str, highlight=None)` (function) — Bars for a daily series: heights as percentage strings, a tip per bar and
- L167 `initials(text: str)` (function)
- L173 `nav_items(items, active: str)` (function) — ``items`` are ``(key, label, url[, badge[, badge_tone]])`` tuples, in tab order.
- L191 `portal_context(*, kind: str, kicker: str, name: str, title: str, sub: str='', status: dict | None=None, nav=(), active: str='', nav_label: str='', actions=(), avatar_url: str='')` (function) — The template context every portal page carries.
