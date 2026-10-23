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

# plugins/installed/seo/app.py

Symbols in `plugins/installed/seo/app.py`.

- L13 `SeoPlugin` (class)
- L45 `ready(self)` (method)
- L124 `_form_card_handler(self, kind: str)` (method)
- L136 `_form_saved_handler(self, kind: str)` (method)
- L147 `on_product_list_columns(self, value, products=None, request=None, **kwargs)` (method)
- L162 `on_storefront_head(self, value, request=None, context=None, **kwargs)` (method)
- L167 `on_structured_data_for_object(self, value, obj=None, **kwargs)` (method)
- L174 `on_brain_signals(self, value, **kwargs)` (method) — Merge the SEO slice into the Brain snapshot: content-audit scores,
- L219 `_wire_cms_page_signal(self)` (method)
- L233 `_on_cms_page_saved(self, sender, instance, created, **kwargs)` (method)
- L241 `on_product_created(self, product, **kwargs)` (method)
- L255 `on_product_updated(self, product, **kwargs)` (method) — Refresh the SEO score when a product changes.
- L265 `on_category_updated(self, category, **kwargs)` (method)
- L268 `on_collection_updated(self, collection, **kwargs)` (method)
- L271 `_indexnow_push(self, *, url: str | None=None, model_label: str | None=None, slug: str | None=None)` (method) — Notify Bing/Yandex/Naver/Seznam/Yep about a URL.
- L310 `contribute_storefront_blocks(self)` (method) — PDP "key facts / AI answer" block.
- L338 `contribute_agent_tools(self)` (method)
- L367 `contribute_skills(self)` (method) — The SEO skill — Linda's Worker opts in via skills=['seo'] when
- L417 `contribute_dashboard_pages(self)` (method)
- L528 `get_config_schema(self)` (method) — Site-wide SEO toggles stored on PluginConfig['seo'].
- L731 `contribute_settings_panel(self)` (method)
