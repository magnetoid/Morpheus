---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/admin_dashboard/views_split/_shared.py

Symbols in `plugins/installed/admin_dashboard/views_split/_shared.py`.

- L17 `_is_ajax(request: HttpRequest)` (function) — True when the client opted into the AJAX response branch.
- L28 `ajax_or_redirect(request: HttpRequest, *redirect_args, payload: dict | None=None, **redirect_kwargs)` (function) — If the request is an AJAX submit, return JSON ``{ok: true, ...}``.
- L76 `DateRange` (class) — Resolved date window for a dashboard view.
- L94 `from_str(self)` (method)
- L98 `to_str(self)` (method)
- L102 `_parse_iso_date(value: str)` (function)
- L111 `_resolve_date_range(request: HttpRequest)` (function) — Pull the active date window off the query string.
- L174 `_aware(dt: datetime)` (function)
- L182 `_period(request: HttpRequest)` (function)
- L189 `_since(days: int)` (function)
- L194 `Metric` (class)
- L203 `_sparkline_points(series: list, width: int=120, height: int=28)` (function) — Convert a numeric series into an SVG `<polyline>` `points` string,
- L226 `_trend(now, before)` (function)
- L236 `_pct_delta(now, before)` (function)
- L247 `paginate_and_sort(request: HttpRequest, qs, *, default_sort: str, allowed_sorts: tuple[str, ...]=(), default_per_page: int=25)` (function) — Apply ?sort=&dir=&page=&per_page= to a queryset.
- L312 `_bulk_ids(request: HttpRequest, field: str='ids')` (function) — Extract a sanitised list of UUID-like ids from POST.
- L323 `call_llm(prompt: str, system: str='', max_tokens: int=600)` (function) — Single source of truth for "ask the configured AI provider for some
