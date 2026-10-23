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

# plugins/installed/storefront/tests/test_home_hero.py

Symbols in `plugins/installed/storefront/tests/test_home_hero.py`.

- L14 `_hero_product(name: str, slug: str)` (function)
- L33 `_two_pick_home()` (function) — The mocked Home query response the rendered-hero tests share.
- L45 `HomeHeroTests` (class)
- L46 `setUp(self)` (method)
- L51 `test_home_query_requests_slider_copy_fields(self, mocked_graphql, mocked_render)` (method)
- L68 `test_homepage_renders_multi_slide_hero(self, mocked_graphql, _rank_for_visitor)` (method)
- L97 `test_hero_drops_the_marketing_headline_and_decode_gimmick(self, mocked_graphql, _rank_for_visitor)` (method) — The hero is the book, not an effect.
- L121 `test_long_titles_step_down_the_display_scale(self, mocked_graphql, _rank_for_visitor)` (method) — One title must not set the height of the whole hero.
- L156 `test_cover_column_is_a_definite_track(self, mocked_graphql, _rank_for_visitor)` (method) — The book fills the hero top to bottom, flush to the right margin.
- L177 `test_hero_skips_drawn_covers_and_tops_up(self, mocked_graphql, _rank_for_visitor)` (method) — The window leads with artwork, not a stand-in.
- L214 `test_hero_is_never_empty(self, mocked_graphql, _rank_for_visitor)` (method) — Every featured book carrying a drawn cover must still fill the window
