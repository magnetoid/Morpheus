---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/seo/templatetags/seo.py

Symbols in `plugins/installed/seo/templatetags/seo.py`.

- L34 `_canonical_from_request(request)` (function) — Build the canonical URL from a request, stripping query params.
- L119 `seo_title(title: str, *, category: str='', site_name: str='')` (function) — Render the ``<title>`` text using SiteSeoSettings.title_template.
- L200 `seo_meta(context, object=None, fallback_title: str='', fallback_description: str='', fallback_image: str='', canonical_url: str='', og_type: str='website', robots: str='')` (function)
- L284 `seo_preconnect()` (function) — Emit <link rel="preconnect"> for the configured CDN host.
- L321 `seo_organization_jsonld()` (function) — Emit <script type="application/ld+json"> for the Organization.
- L332 `seo_website_jsonld()` (function) — Emit <script type="application/ld+json"> for the WebSite (sitelinks search).
- L343 `seo_product_jsonld(product)` (function) — Emit Product JSON-LD with offer / availability / aggregateRating.
- L360 `seo_product_md_link(slug)` (function) — <link rel="alternate" type="text/markdown" …> pointing at the
- L373 `seo_product_og(product)` (function) — Open Graph product extensions + Twitter label/data pairs.
- L436 `seo_ai_answer_block(context, product)` (function) — Data for the PDP "Key facts" / AI-answer storefront block.
- L495 `seo_speakable_jsonld(selectors=None)` (function) — Speakable schema — declares which CSS selectors hold spoken
- L505 `seo_faq_jsonld(items)` (function) — FAQ schema — items is a list of {q, a}. Although Google retired
- L519 `seo_collection_jsonld(context, items, name='', description='')` (function) — Emit CollectionPage + ItemList JSON-LD for a PLP/category.
- L555 `seo_qa_jsonld(context, qa, name='')` (function) — QAPage schema — qa is a list of {q, a}.
- L571 `seo_responsive_image(src, alt='', sizes='', widths='400,800,1200', priority=False, css_class='', style='', view_transition_name='', img_id='')` (function) — Emit a <picture> element with AVIF + WebP sources + a JPEG/PNG
- L703 `seo_article_jsonld(context, *, headline, body, author='', published=None, modified=None, image='')` (function) — Article schema for journal posts. AI engines weigh this heavily
- L732 `seo_breadcrumb_jsonld(items)` (function) — Emit BreadcrumbList JSON-LD. `items` is a list of {name, url}.
- L744 `seo_verification_metas()` (function) — Emit any configured Google / Bing / Pinterest / FB verification metas.
- L763 `seo_pagination_links(context, page_obj=None)` (function) — Emit <link rel="prev"> + <link rel="next"> for a Django Paginator
- L798 `seo_search_results_jsonld(context, items, query='')` (function) — Emit SearchResultsPage + ItemList for a /search/ page.
- L835 `seo_person_jsonld(context, name, slug='', sameas=None)` (function) — Person JSON-LD for author landing pages. `sameas` is an
- L861 `seo_aboutpage_jsonld(context, name='', description='')` (function) — AboutPage JSON-LD with mainEntity → Organization. Used on /about/.
- L886 `seo_contactpage_jsonld(context, name='', description='')` (function) — ContactPage JSON-LD with mainEntity → Organization + ContactPoint.
- L921 `seo_llms_link()` (function) — Emit a <link rel="alternate"> hint to /llms.txt for LLM crawlers.
- L934 `seo_hreflang(context)` (function) — Emit ``<link rel="alternate" hreflang=…>`` for every active market.
