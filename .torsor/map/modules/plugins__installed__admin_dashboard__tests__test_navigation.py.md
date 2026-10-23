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

# plugins/installed/admin_dashboard/tests/test_navigation.py

Symbols in `plugins/installed/admin_dashboard/tests/test_navigation.py`.

- L38 `disabled(name: str)` (function) — Runtime-disable an app exactly the way the Apps toggle does.
- L50 `_Staff` (class)
- L51 `setUp(self)` (method)
- L61 `html(self, url: str)` (method)
- L66 `_nav(self, path)` (method)
- L74 `SidebarTests` (class)
- L75 `test_the_sidebar_is_the_sections_in_order(self)` (method)
- L87 `test_a_sections_pages_are_its_sidebar_group(self)` (method)
- L111 `test_a_group_reads_as_a_heading_over_its_pages(self)` (method)
- L119 `test_a_page_after_a_group_is_set_apart(self)` (method)
- L135 `test_the_section_you_are_in_renders_open(self)` (method)
- L141 `test_crm_is_its_own_section_after_customers(self)` (method)
- L155 `test_a_disabled_crm_takes_its_section_with_it(self)` (method)
- L161 `test_a_section_with_nothing_in_it_is_not_listed(self)` (method)
- L167 `test_the_settings_sidebar_is_the_categories(self)` (method)
- L181 `EveryEntryAnswersTests` (class)
- L182 `test_every_tab_and_tool_answers(self)` (method)
- L192 `WhereAmITests` (class)
- L193 `test_a_tab_page_marks_its_section_and_tab(self)` (method)
- L200 `test_a_group_is_one_tab_with_sub_tabs(self)` (method)
- L209 `test_affiliates_is_its_own_section_with_its_pages_as_tabs(self)` (method)
- L221 `test_a_record_below_a_tab_belongs_to_it(self)` (method)
- L227 `test_an_app_mount_deeper_than_a_tab_wins(self)` (method)
- L234 `test_a_settings_page_switches_to_settings_mode(self)` (method)
- L239 `test_the_catalogue_and_an_app_settings_form_are_settings(self)` (method)
- L243 `test_home_is_home(self)` (method)
- L248 `test_the_page_carries_its_place_for_htmx_swaps(self)` (method)
- L255 `test_an_app_page_is_found_at_its_router_path_too(self)` (method)
- L262 `TabStripTests` (class)
- L263 `test_tabs_render_and_the_breadcrumb_waits_below_them(self)` (method)
- L271 `test_a_detail_page_keeps_its_breadcrumb(self)` (method)
- L280 `test_hidden_pages_have_no_tab_but_a_home(self)` (method)
- L286 `test_a_disabled_apps_tab_leaves(self)` (method)
- L291 `test_linda_tabs_sit_inside_the_chat_layout(self)` (method)
- L297 `StorefrontPaysNothingTests` (class)
- L298 `test_no_dashboard_navigation_on_a_shop_page(self)` (method)
- L305 `test_the_plugin_context_no_longer_counts_badges(self)` (method)
- L315 `IconMapTests` (class) — The dashboard draws lucide names through a Remix Icon map in base.html;
- L320 `test_every_navigation_icon_has_a_glyph(self)` (method)
