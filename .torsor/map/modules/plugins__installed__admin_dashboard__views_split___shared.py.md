---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/admin_dashboard/views_split/_shared.py

Symbols in `plugins/installed/admin_dashboard/views_split/_shared.py`.

- L21 `_is_ajax(request: HttpRequest)` (function) — True when the client opted into the AJAX response branch.
- L32 `ajax_or_redirect(request: HttpRequest, *redirect_args, payload: dict | None=None, **redirect_kwargs)` (function) — If the request is an AJAX submit, return JSON ``{ok: true, ...}``.
- L81 `DateRange` (class) — Resolved date window for a dashboard view.
- L100 `from_str(self)` (method)
- L104 `to_str(self)` (method)
- L108 `_parse_iso_date(value: str)` (function)
- L117 `_resolve_date_range(request: HttpRequest)` (function) — Pull the active date window off the query string.
- L180 `_aware(dt: datetime)` (function)
- L188 `_period(request: HttpRequest)` (function)
- L195 `_since(days: int)` (function)
- L200 `Metric` (class)
- L209 `_sparkline_points(series: list, width: int=120, height: int=28)` (function) — Convert a numeric series into an SVG `<polyline>` `points` string,
- L232 `_trend(now, before)` (function)
- L242 `_pct_delta(now, before)` (function)
- L253 `paginate_and_sort(request: HttpRequest, qs, *, default_sort: str, allowed_sorts: tuple[str, ...]=(), default_per_page: int=25)` (function) — Apply ?sort=&dir=&page=&per_page= to a queryset.
- L318 `_bulk_ids(request: HttpRequest, field: str='ids')` (function) — Extract a sanitised list of UUID-like ids from POST.
- L329 `call_llm(prompt: str, system: str='', max_tokens: int=600)` (function) — Single source of truth for "ask the configured AI provider for some
