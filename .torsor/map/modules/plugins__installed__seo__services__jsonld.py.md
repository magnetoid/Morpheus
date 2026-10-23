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

# plugins/installed/seo/services/jsonld.py

Symbols in `plugins/installed/seo/services/jsonld.py`.

- L29 `organization_jsonld()` (function)
- L97 `website_jsonld()` (function)
- L118 `breadcrumb_jsonld(items: list[dict])` (function) — `items` = [{'name': str, 'url': str}, …] in order.
- L130 `_availability(rendered, orm)` (function) — The schema.org availability URL for a product.
- L152 `_safe_field(source, name)` (function) — Read a field without letting a DEFERRED one take the page down.
- L175 `_compare_at(rendered, orm)` (function) — The pre-sale price, from what was rendered first and the row second.
- L187 `_variant_axis(variants)` (function) — What actually differs between these variants.
- L204 `_money(value)` (function)
- L209 `_strikethrough(price, compare_at, currency: str)` (function) — The "was" price, when there genuinely is one.
- L233 `_variant_availability(variant)` (function) — Per-variant stock, from the app that holds it.
- L255 `_apply_variants(out: dict, orm, *, slug: str, currency: str)` (function) — Turn a multi-variant product into a ProductGroup with real offers.
- L310 `product_jsonld(product, *, base_url: str='', extra: dict | None=None, model=None)` (function) — Rich Product structured data.
- L748 `speakable_jsonld(selectors: list[str] | None=None)` (function) — SpeakableSpecification — tells voice assistants which CSS selectors
- L768 `collection_page_jsonld(*, name: str, url: str, description: str, items: list[dict], kind: str='CollectionPage', total: int | None=None, offers: dict | None=None)` (function) — CollectionPage + ItemList for PLP/category pages.
- L820 `aggregate_offer(prices: list, currency: str, *, count: int | None=None)` (function) — Build a schema.org AggregateOffer from a list of numeric prices.
- L845 `qa_page_jsonld(*, name: str, url: str, qa: list[dict])` (function) — QAPage schema — ChatGPT cites QAPage ~58% more than FAQPage
- L870 `article_jsonld(*, headline: str, body: str, url: str, kind: str='Article', description: str='', author: str='', author_url: str='', published_at=None, updated_at=None, image: str='', image_url: str='', word_count: int | None=None, citations: list[str] | None=None, author_same_as: list[str] | None=None)` (function) — Article schema for journal posts.
- L956 `faq_jsonld(qa: list[dict])` (function)
- L997 `_book_platforms(raw)` (function) — Parse the merchant's platform config → schema.org EntryPoint platforms.
- L1009 `_to_isbn13(isbn13, isbn10)` (function) — Google requires ISBN-13 on the edition; convert ISBN-10 when needed.
- L1027 `book_jsonld(data: dict, *, base_url: str='')` (function) — Google Book (Work → Edition → ReadAction) JSON-LD.
- L1118 `video_jsonld(videos: list[dict])` (function) — VideoObject blocks for product videos (Google Video rich result).
