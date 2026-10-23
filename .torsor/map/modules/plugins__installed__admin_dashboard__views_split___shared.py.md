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

# plugins/installed/admin_dashboard/views_split/_shared.py

Symbols in `plugins/installed/admin_dashboard/views_split/_shared.py`.

- L21 `_is_ajax(request: HttpRequest)` (function) — True when the client opted into the AJAX response branch.
- L32 `ajax_or_redirect(request: HttpRequest, *redirect_args, payload: dict | None=None, follow: bool=False, **redirect_kwargs)` (function) — If the request is an AJAX submit, return JSON ``{ok: true, ...}``.
- L66 `ajax_form_errors(request: HttpRequest, form)` (function) — The error-path twin of :func:`ajax_or_redirect`.
- L108 `DateRange` (class) — Resolved date window for a dashboard view.
- L127 `from_str(self)` (method)
- L131 `to_str(self)` (method)
- L135 `_parse_iso_date(value: str)` (function)
- L144 `_resolve_date_range(request: HttpRequest)` (function) — Pull the active date window off the query string.
- L207 `_aware(dt: datetime)` (function)
- L215 `_period(request: HttpRequest)` (function)
- L222 `_since(days: int)` (function)
- L227 `Metric` (class)
- L236 `_sparkline_points(series: list, width: int=120, height: int=28)` (function) — Convert a numeric series into an SVG `<polyline>` `points` string,
- L259 `_trend(now, before)` (function)
- L269 `_pct_delta(now, before)` (function)
- L280 `paginate_and_sort(request: HttpRequest, qs, *, default_sort: str, allowed_sorts: tuple[str, ...]=(), default_per_page: int=25)` (function) — Apply ?sort=&dir=&page=&per_page= to a queryset.
- L345 `_bulk_ids(request: HttpRequest, field: str='ids')` (function) — Extract a sanitised list of UUID-like ids from POST.
- L356 `call_llm(prompt: str, system: str='', max_tokens: int=600, timeout: float | None=None)` (function) — Single source of truth for "ask the configured AI provider for some
- L423 `entity_form_cards(kind: str, obj, request)` (function) — Rendered cards for one entity form. Fail-soft per card — a broken
- L446 `fire_entity_form_saved(kind: str, obj, request)` (function) — Let contributors persist their own fields after the entity is saved.
