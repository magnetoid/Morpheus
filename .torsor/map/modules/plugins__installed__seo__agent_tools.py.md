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

# plugins/installed/seo/agent_tools.py

Symbols in `plugins/installed/seo/agent_tools.py`.

- L18 `get_meta_tool(*, slug: str)` (function)
- L61 `set_meta_tool(*, slug: str, title: str='', description: str='', keywords: str='')` (function)
- L114 `audit_product_tool(*, slug: str)` (function)
- L139 `audit_all_tool(*, limit: int=200)` (function)
- L157 `list_404s_tool(*, limit: int=25)` (function)
- L200 `create_redirect_tool(*, from_path: str, to_path: str, note: str='')` (function)
- L243 `bulk_set_meta_tool(*, updates: list[dict])` (function)
- L293 `set_site_settings_tool(**kwargs)` (function)
- L334 `apply_internal_links_tool(*, slugs: list[str] | None=None, force: bool=False)` (function)
- L396 `apply_external_links_tool(*, slugs: list[str] | None=None, verify_web: bool=True, force: bool=False, limit: int=0)` (function)
- L440 `seo_regenerate_sitemap_tool()` (function)
