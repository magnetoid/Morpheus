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

# plugins/installed/booking_marketplace/tests/test_events.py

Symbols in `plugins/installed/booking_marketplace/tests/test_events.py`.

- L29 `_event(**kw)` (function)
- L41 `EventPageTests` (class)
- L42 `test_index_renders_and_lists_an_active_event(self)` (method)
- L47 `test_index_hides_inactive_events(self)` (method)
- L52 `test_detail_renders(self)` (method)
- L58 `test_inactive_event_detail_404s(self)` (method)
- L62 `test_category_filter_narrows_the_list(self)` (method)
- L70 `MonthGroupingTests` (class)
- L71 `test_undated_events_group_last_not_first(self)` (method) — month=0 means "not announced yet" — it must never sort ahead of January.
- L79 `test_months_are_in_calendar_order(self)` (method)
- L86 `EventJsonLdTests` (class) — The honest-dates guard. See the module docstring.
- L89 `_graph(self, slug)` (method) — The page's ONE JSON-LD graph — the head document's, entity nodes included.
- L98 `test_event_node_emitted_when_a_real_date_exists(self)` (method)
- L110 `test_no_event_node_when_the_date_is_unknown(self)` (method) — A month is not a date — never synthesise `startDate` from it.
- L120 `test_faq_node_emitted_from_faqs(self)` (method)
- L125 `EventSitemapTests` (class)
- L126 `test_active_event_and_index_contributed(self)` (method)
- L132 `test_inactive_event_not_contributed(self)` (method)
- L138 `PlaceEventsTests` (class)
- L139 `test_place_page_lists_its_events(self)` (method)
- L146 `SeedEventsCommandTests` (class)
- L147 `test_seed_is_idempotent(self)` (method)
