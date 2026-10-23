---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/booking_marketplace/search_page.py

Symbols in `plugins/installed/booking_marketplace/search_page.py`.

- L29 `SearchParams` (class) — A search, validated: anything unknown or unusable is dropped, never echoed.
- L40 `read_params(request)` (function) — The search in `request.GET`.
- L60 `_day(raw)` (function)
- L73 `_category(raw)` (function) — An active category named by its slug or its exact name, in any case.
- L87 `date_locale()` (function) — (Babel, browser) locale for dates in the visitor's language.
- L92 `date_label(day)` (function) — 'Sun 18 Oct' or 'ned 18. okt'; '' without a date.
- L104 `values(params: SearchParams)` (function) — What the search bar shows of a search.
- L119 `heading(params: SearchParams)` (function) — The results page's h1: the query, else the category, else the plain title; then the date.
- L127 `_title(params: SearchParams)` (function)
- L143 `chips(request, params: SearchParams)` (function) — One removable chip per filter in force; its link is this page without it.
- L157 `_without(request, param: str)` (function)
- L168 `empty_message(params: SearchParams, *, kind: str='experience')` (function) — What the page says when nothing matches every word, or nothing at all.
- L184 `page_context(request, params: SearchParams, *, close=False, kind='experience')` (function) — The `search` a results page renders (list.html) and its search bar reads.
- L197 `suggestions(request, q: str)` (function) — Up to 5 experiences, 3 places and 3 categories matching every word of `q`.
- L215 `_suggested_experiences(request, index, terms)` (function)
- L246 `_suggested_places(request, index, terms)` (function)
- L261 `_suggested_categories(request, terms)` (function)
- L283 `bar_context(request, variant: str, search: dict | None=None)` (function) — Everything booking_marketplace/_search.html shows.
