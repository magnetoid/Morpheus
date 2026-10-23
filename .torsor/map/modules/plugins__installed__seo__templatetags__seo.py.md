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

# plugins/installed/seo/templatetags/seo.py

Symbols in `plugins/installed/seo/templatetags/seo.py`.

- L32 `_attr(obj, name, default=None)` (function) — Dict-or-model accessor — journal entries arrive as dicts, catalog
- L43 `_canonical_from_request(request)` (function) — Build the canonical URL from a request, stripping query params.
- L133 `seo_title(title: str, *, category: str='', site_name: str='')` (function) — Render the ``<title>`` text using SiteSeoSettings.title_template.
- L214 `seo_meta(context, object=None, fallback_title: str='', fallback_description: str='', fallback_image: str='', canonical_url: str='', og_type: str='website', robots: str='')` (function)
- L298 `seo_preconnect()` (function) — Emit <link rel="preconnect"> for the configured CDN host.
- L335 `seo_organization_jsonld()` (function) — Emit <script type="application/ld+json"> for the Organization.
- L346 `seo_website_jsonld()` (function) — Emit <script type="application/ld+json"> for the WebSite (sitelinks search).
- L357 `seo_product_jsonld(product, extra=None)` (function) — Emit Product JSON-LD with offer / availability / aggregateRating.
- L375 `seo_video_jsonld(videos)` (function) — Emit a VideoObject block per product video (Google Video rich result).
- L395 `seo_book_jsonld(book_data)` (function) — Emit Google Book structured data (Work → Edition → ReadAction).
- L414 `seo_product_md_link(slug)` (function) — <link rel="alternate" type="text/markdown" …> pointing at the
- L427 `seo_product_og(product)` (function) — Open Graph product extensions + Twitter label/data pairs.
- L490 `seo_article_og(entry)` (function) — Open Graph ``article:*`` tags for journal/blog posts.
- L529 `seo_ai_answer_block(context, product)` (function) — Data for the PDP "Key facts" / AI-answer storefront block.
- L588 `seo_speakable_jsonld(selectors=None)` (function) — Speakable schema — declares which CSS selectors hold spoken
- L598 `seo_faq_jsonld(items)` (function) — FAQ schema — items is a list of {q, a}. Although Google retired
- L612 `seo_meta_panel(context, obj)` (function) — Render the reusable per-object SEO settings panel for ``obj``.
- L626 `seo_collection_jsonld(context, items, name='', description='')` (function) — Emit CollectionPage + ItemList JSON-LD for a PLP/category.
- L680 `seo_qa_jsonld(context, qa, name='')` (function) — QAPage schema — qa is a list of {q, a}.
- L696 `seo_responsive_image(src, alt='', sizes='', widths='400,800,1200', priority=False, css_class='', style='', view_transition_name='', img_id='')` (function) — Emit a <picture> element with AVIF + WebP sources + a JPEG/PNG
- L828 `seo_article_jsonld(context, *, headline, body, kind='BlogPosting', description='', author='', author_url='', published=None, modified=None, image='', word_count=None, author_same_as=None, citations=None)` (function) — BlogPosting/Article schema for journal posts. AI engines weigh this
- L878 `seo_breadcrumb_jsonld(items)` (function) — Emit BreadcrumbList JSON-LD. `items` is a list of {name, url}.
- L890 `seo_verification_metas()` (function) — Emit any configured Google / Bing / Pinterest / FB verification metas.
- L909 `seo_pagination_links(context, page_obj=None)` (function) — Emit <link rel="prev"> + <link rel="next"> for a Django Paginator
- L944 `seo_search_results_jsonld(context, items, query='')` (function) — Emit SearchResultsPage + ItemList for a /search/ page.
- L981 `seo_person_jsonld(context, name, slug='', sameas=None)` (function) — Person JSON-LD for author landing pages. `sameas` is an
- L1007 `seo_aboutpage_jsonld(context, name='', description='')` (function) — AboutPage JSON-LD with mainEntity → Organization. Used on /about/.
- L1032 `seo_contactpage_jsonld(context, name='', description='')` (function) — ContactPage JSON-LD with mainEntity → Organization + ContactPoint.
- L1067 `seo_llms_link()` (function) — Emit a <link rel="alternate"> hint to /llms.txt for LLM crawlers.
- L1080 `seo_hreflang(context)` (function) — Emit ``<link rel="alternate" hreflang=…>`` for every active market.
- L1187 `_head_already_rendered(context)` (function)
- L1192 `_register_legacy_head_shim(name: str, wants_context: bool)` (function)
