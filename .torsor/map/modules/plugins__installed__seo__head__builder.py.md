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

# plugins/installed/seo/head/builder.py

Symbols in `plugins/installed/seo/head/builder.py`.

- L47 `on_storefront_head(value, request=None, context=None, **kwargs)` (function) — `STOREFRONT_HEAD` subscriber. Returns the document, always.
- L56 `build_document(doc, *, request=None, context=None)` (function)
- L91 `_section(func, *args)` (function)
- L99 `_safe_meta(page: SeoPage)` (function) — Resolution must not be able to blank the head.
- L115 `_resolve_meta(page: SeoPage)` (function) — Merchant overrides → native model fields → the page's own defaults.
- L135 `_apply_title_and_description(doc, page: SeoPage, meta)` (function)
- L155 `_apply_canonical_and_robots(doc, page: SeoPage, meta, request)` (function)
- L194 `_apply_error_head(doc, page: SeoPage)` (function) — Robots for a page that does not exist — the only other thing it says.
- L200 `_is_self(canonical: str, request)` (function) — Does `canonical` name exactly the URL being rendered (same path, same query)?
- L214 `_apply_thin_content_rule(page: SeoPage, meta)` (function) — Hold back a product page whose description is too short to rank.
- L240 `_snippet_directives(meta)` (function) — How much of the page engines — and AI Overviews — may reproduce.
- L268 `_apply_social(doc, page: SeoPage, meta)` (function)
- L299 `_apply_product_og(doc, page: SeoPage)` (function)
- L332 `_apply_site_links(doc, request)` (function) — Verification metas, CDN preconnect and the LLM discovery hint.
- L378 `_apply_alternates(doc, page: SeoPage, request)` (function) — hreflang for languages and markets.
- L407 `_same_path(url: str, request)` (function)
- L416 `_without_market(url: str)` (function)
- L422 `_x_default_href(languages: list[tuple[str, str]], canonical: str)` (function) — `x-default` names ONE url for the whole cluster: the default language.
- L444 `_apply_pagination(doc, page: SeoPage, request)` (function)
- L449 `_apply_graph(doc, page: SeoPage, request)` (function)
- L460 `_og_locale()` (function)
- L466 `_brand()` (function)
- L472 `_store_description()` (function) — The merchant's site-wide meta description (Settings → General).
- L485 `_language_alternates(canonical: str)` (function) — One alternate per configured language, using the i18n URL prefix.
- L513 `_market_alternates(canonical: str)` (function) — `?market=<code>` alternates, one per (locale, country) a market covers.
- L556 `_market_is_indexable(query: str, code: str)` (function)
- L564 `_product_price(product)` (function) — (amount, currency) from a model or the PDP's GraphQL dict.
- L592 `_product_availability(product)` (function)
