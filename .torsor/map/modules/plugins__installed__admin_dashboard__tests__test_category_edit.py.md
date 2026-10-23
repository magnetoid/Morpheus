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

# plugins/installed/admin_dashboard/tests/test_category_edit.py

Symbols in `plugins/installed/admin_dashboard/tests/test_category_edit.py`.

- L18 `CategoryEditTests` (class)
- L19 `setUp(self)` (method)
- L34 `test_url_reverses(self)` (method)
- L37 `test_anonymous_blocked(self)` (method)
- L45 `test_non_staff_blocked(self)` (method)
- L50 `test_staff_get_renders(self)` (method)
- L59 `test_staff_post_updates_category(self)` (method)
- L80 `test_staff_post_can_reparent(self)` (method)
- L102 `test_duplicate_slug_rejected(self)` (method)
- L122 `test_self_parent_rejected(self)` (method)
- L141 `test_descendant_parent_rejected(self)` (method)
- L162 `CategoryCreateTests` (class) — "New category" is a dashboard page. It once linked to Django's stock
- L167 `setUp(self)` (method)
- L173 `test_url_reverses(self)` (method)
- L176 `test_non_staff_blocked(self)` (method)
- L183 `test_staff_get_renders_an_empty_form(self)` (method)
- L191 `test_staff_post_creates_a_category_with_a_slug_from_its_name(self)` (method)
- L213 `test_a_duplicate_slug_re_renders_the_form(self)` (method)
- L221 `test_the_list_links_to_the_dashboard_page(self)` (method)
- L231 `NoStockAdminLinkTests` (class) — Django's stock admin is mounted only under DEBUG (morph/urls.py), so a
- L235 `test_no_dashboard_template_links_into_the_stock_admin(self)` (method)
