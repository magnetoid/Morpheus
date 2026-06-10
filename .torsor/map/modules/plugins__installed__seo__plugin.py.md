---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/seo/plugin.py

Symbols in `plugins/installed/seo/plugin.py`.

- L12 `SeoPlugin` (class)
- L39 `ready(self)` (method)
- L57 `_wire_cms_page_signal(self)` (method)
- L71 `_on_cms_page_saved(self, sender, instance, created, **kwargs)` (method)
- L79 `on_product_created(self, product, **kwargs)` (method)
- L93 `on_product_updated(self, product, **kwargs)` (method) — Refresh the SEO score when a product changes.
- L103 `on_category_updated(self, category, **kwargs)` (method)
- L106 `on_collection_updated(self, collection, **kwargs)` (method)
- L109 `_indexnow_push(self, *, url: str | None=None, model_label: str | None=None, slug: str | None=None)` (method) — Notify Bing/Yandex/Naver/Seznam/Yep about a URL.
- L150 `contribute_storefront_blocks(self)` (method) — PDP "key facts / AI answer" block.
- L169 `contribute_agent_tools(self)` (method)
- L194 `contribute_skills(self)` (method) — The SEO skill — Linda's Worker opts in via skills=['seo'] when
- L242 `contribute_dashboard_pages(self)` (method)
- L314 `get_config_schema(self)` (method) — Site-wide SEO toggles stored on PluginConfig['seo'].
- L435 `contribute_settings_panel(self)` (method)
