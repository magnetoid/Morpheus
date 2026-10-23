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

# core/assistant/tests/test_chat_layout.py

Symbols in `core/assistant/tests/test_chat_layout.py`.

- L20 `_staff()` (function)
- L30 `LindaChatLayoutTests` (class)
- L31 `setUp(self)` (method)
- L34 `_html(self)` (method)
- L39 `test_the_composer_is_a_sibling_of_the_scroll_container(self)` (method)
- L50 `test_no_suggested_prompts_are_shown(self)` (method)
- L56 `test_the_typing_field_has_a_drop_shadow_but_no_border_or_ring(self)` (method)
- L69 `test_the_floating_launcher_is_not_rendered_on_lindas_own_page(self)` (method)
- L74 `test_the_floating_launcher_is_still_rendered_on_other_admin_pages(self)` (method) — Hiding it must be scoped to Linda's page, not the whole dashboard.
- L80 `test_desktop_sidebar_is_viewport_bounded_not_page_height(self)` (method) — An expanded nav group must not grow the page and push the composer off-screen.
- L96 `test_no_django_comment_leaks_into_the_page(self)` (method) — A multi-line ``{# … #}`` is not a comment and renders as literal text.
