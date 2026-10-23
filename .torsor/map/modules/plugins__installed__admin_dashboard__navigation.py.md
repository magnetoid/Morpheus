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

# plugins/installed/admin_dashboard/navigation.py

Symbols in `plugins/installed/admin_dashboard/navigation.py`.

- L39 `NavSection` (class)
- L94 `section(key: str)` (function)
- L98 `main_section_key(raw: str)` (function) — The sidebar section a ``DashboardPage``/``DashboardCard`` section names,
- L105 `card_section_keys()` (function)
- L109 `settings_category_key(raw: str)` (function) — The settings category a panel or ``nav='settings'`` page names.
- L124 `CoreTab` (class) — A dashboard page the shell itself serves, filed like an app's page.
- L188 `CoreTool` (class) — A platform page the shell serves, drawn as a settings tool card.
- L244 `Tab` (class)
- L260 `Tool` (class)
- L272 `Location` (class)
- L281 `page_url(page)` (function)
- L285 `_is_superuser(user)` (function)
- L289 `tabs(user=None)` (function) — Every main-namespace entry: the shell's tabs and every contributed
- L333 `tools()` (function) — Every settings tool card: contributed ``nav='settings'`` pages and the
- L366 `_mounts()` (function)
- L372 `_settings_head(path: str)` (function) — ``x`` of ``/dashboard/settings/x/…`` or of the legacy
- L383 `settings_category_for(head: str)` (function) — The category ``/dashboard/settings/<head>/`` belongs to: the category
- L406 `_settings_location(path: str, all_tools: list[Tool])` (function) — Settings-mode pages that are not tool pages: the hub, a category, a
- L425 `locate(path: str, all_tabs: list[Tab], all_tools: list[Tool])` (function) — The entry ``path`` belongs to: the longest tab or tool URL it starts
- L456 `_entry_location(path: str, url: str, entry)` (function) — Where ``path`` is when it lives at or below ``entry``'s ``url``.
- L466 `_urls_of(entry)` (function) — The URLs an entry answers at: its own, and — for an app page whose
- L477 `_mount_location(path, plugin, prefix, all_tabs, all_tools)` (function) — The page of ``plugin`` a path under its URL mount belongs to: the one
- L500 `_tab_entry(tab: Tab, current: Tab | None, badges: dict)` (function)
- L510 `tab_strip(section_tabs: list[Tab], current: Tab | None, badges: dict)` (function) — (top-level tabs, sub-tabs of the active group). A group with one live
- L544 `sidebar_children(section_tabs: list[Tab], current: Tab | None, badges: dict)` (function) — A section's pages for its sidebar group: the tab strip's pages, a group's
- L569 `_has_cards(section_key: str)` (function)
- L575 `build(request)` (function) — Everything the dashboard shell renders for navigation, once per request.
- L643 `current_app(request)` (function) — The app the current dashboard page belongs to, for its Help link: the
- L659 `settings_categories_nav(loc: Location, all_tools: list[Tool])` (function) — The settings sidebar: every category with something in it (General and
- L688 `section_label(key: str)` (function)
- L693 `page_section_label(page)` (function) — Where a contributed page is filed, in words — for the palette and the
- L737 `_plural(n: int, one: str, many: str)` (function)
- L741 `_contributions(instance)` (function) — What an app adds, asked of the app itself — so an app that is off can
- L762 `_app_area(c: dict)` (function) — The area an app's first surface lands in: a listed page's section, a
- L782 `_app_adds(c: dict)` (function) — Everything an app adds to the dashboard and storefront, in words.
- L812 `describe_app(instance)` (function) — ``{'area', 'area_label', 'adds'}`` for the Apps catalogue: where the app
