---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/seo/services/jsonld.py

Symbols in `plugins/installed/seo/services/jsonld.py`.

- L29 `organization_jsonld()` (function)
- L71 `website_jsonld()` (function)
- L92 `breadcrumb_jsonld(items: list[dict])` (function) — `items` = [{'name': str, 'url': str}, …] in order.
- L104 `product_jsonld(product, *, base_url: str='')` (function) — Rich Product structured data.
- L541 `speakable_jsonld(selectors: list[str] | None=None)` (function) — SpeakableSpecification — tells voice assistants which CSS selectors
- L559 `collection_page_jsonld(*, name: str, url: str, description: str, items: list[dict], kind: str='CollectionPage', total: int | None=None)` (function) — CollectionPage + ItemList for PLP/category pages.
- L605 `qa_page_jsonld(*, name: str, url: str, qa: list[dict])` (function) — QAPage schema — ChatGPT cites QAPage ~58% more than FAQPage
- L630 `article_jsonld(*, headline: str, body: str, url: str, author: str='', published_at=None, updated_at=None, image: str='', image_url: str='', citations: list[str] | None=None, author_same_as: list[str] | None=None)` (function) — Article schema for journal posts.
- L699 `faq_jsonld(qa: list[dict])` (function)
