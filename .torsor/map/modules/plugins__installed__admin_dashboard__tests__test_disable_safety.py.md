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

# plugins/installed/admin_dashboard/tests/test_disable_safety.py

Symbols in `plugins/installed/admin_dashboard/tests/test_disable_safety.py`.

- L65 `disabled(name: str)` (function) — Runtime-disable ``name`` exactly the way the Apps-page toggle does, and
- L78 `_login_staff(client, username: str)` (function)
- L86 `_make_product(slug: str='disable-safety-book')` (function)
- L99 `ShellNeverFiveHundredTests` (class) — With each optional plugin disabled, the shell still renders.
- L102 `setUp(self)` (method)
- L106 `test_shell_pages_render_with_each_optional_app_disabled(self)` (method)
- L115 `test_owned_pages_are_404_not_500_under_any_disable(self)` (method)
- L145 `test_ai_probe_is_json_503_when_ai_assistant_disabled(self)` (method)
- L157 `MarketingSurfaceTests` (class) — (a) The coupon pages are the marketing plugin's surface: 404 when it is
- L163 `setUp(self)` (method)
- L174 `test_coupon_pages_404_when_disabled_200_when_enabled(self)` (method)
- L193 `test_delete_does_not_operate_while_disabled(self)` (method)
- L204 `ProductVideoSurfaceTests` (class) — (b) The product editor's video card + the video CRUD endpoints.
- L207 `setUp(self)` (method)
- L223 `test_video_vanishes_from_product_editor_when_disabled(self)` (method)
- L234 `test_video_crud_is_404_when_disabled_and_operates_when_enabled(self)` (method)
- L259 `CachingCloudflareSurfaceTests` (class) — (c) The Caching settings page: the cloudflare zone rows/controls vanish
- L263 `setUp(self)` (method)
- L275 `_get(self)` (method)
- L280 `test_zone_rows_vanish_when_cloudflare_disabled(self)` (method)
- L292 `test_cf_actions_do_not_operate_when_disabled(self)` (method)
- L302 `CmsSurfaceTests` (class) — (d) Theme builder + email-template edit are cms surfaces (404 when off);
- L306 `setUp(self)` (method)
- L314 `test_theme_builder_404_when_disabled_200_when_enabled(self)` (method)
- L337 `test_email_template_edit_404_when_disabled_list_still_renders(self)` (method)
- L350 `test_palette_stops_offering_cms_pages_when_disabled(self)` (method)
- L364 `DraftOrdersSurfaceTests` (class) — The Orders page loses its Drafts button and /orders/new/ 404s when
- L368 `setUp(self)` (method)
- L371 `test_drafts_button_and_new_order_page(self)` (method)
