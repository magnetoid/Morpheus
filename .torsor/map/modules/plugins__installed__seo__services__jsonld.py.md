---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/seo/services/jsonld.py

Symbols in `plugins/installed/seo/services/jsonld.py`.

- L29 `organization_jsonld()` (function)
- L71 `website_jsonld()` (function)
- L92 `breadcrumb_jsonld(items: list[dict])` (function) — `items` = [{'name': str, 'url': str}, …] in order.
- L104 `product_jsonld(product, *, base_url: str='')` (function) — Rich Product structured data.
- L534 `speakable_jsonld(selectors: list[str] | None=None)` (function) — SpeakableSpecification — tells voice assistants which CSS selectors
- L552 `collection_page_jsonld(*, name: str, url: str, description: str, items: list[dict], kind: str='CollectionPage', total: int | None=None)` (function) — CollectionPage + ItemList for PLP/category pages.
- L598 `qa_page_jsonld(*, name: str, url: str, qa: list[dict])` (function) — QAPage schema — ChatGPT cites QAPage ~58% more than FAQPage
- L623 `article_jsonld(*, headline: str, body: str, url: str, author: str='', published_at=None, updated_at=None, image: str='', image_url: str='', citations: list[str] | None=None, author_same_as: list[str] | None=None)` (function) — Article schema for journal posts.
- L692 `faq_jsonld(qa: list[dict])` (function)
