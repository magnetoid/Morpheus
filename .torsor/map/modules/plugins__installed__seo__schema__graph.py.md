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

# plugins/installed/seo/schema/graph.py

Symbols in `plugins/installed/seo/schema/graph.py`.

- L49 `build_graph(page: SeoPage, *, request=None, url: str='')` (function) — Assemble `{'@context': …, '@graph': [...]}` for a resolved page.
- L95 `graph_for_object(obj)` (function) — The graph for a single object, outside a request.
- L120 `_organization()` (function)
- L126 `_website()` (function)
- L137 `_webpage(page: SeoPage, url: str, website: dict | None, org: dict | None)` (function)
- L162 `_webpage_type(page: SeoPage)` (function)
- L174 `_breadcrumb(page: SeoPage, url: str, request=None)` (function)
- L193 `_kind_nodes(page: SeoPage, url: str, base: str)` (function)
- L205 `_person_node(page: SeoPage, url: str)` (function) — An author landing describes a Person, not just a list of their books.
- L219 `_product_nodes(page: SeoPage, url: str)` (function)
- L293 `_list_nodes(page: SeoPage, url: str)` (function) — CollectionPage's ItemList — merged INTO the WebPage node's mainEntity.
- L325 `_article_nodes(page: SeoPage, url: str)` (function)
- L361 `_fire_filter(graph: dict, page: SeoPage, request)` (function)
- L374 `_safe(func, *args, **kwargs)` (function)
- L382 `_strip_context(node)` (function) — Drop the per-node `@context` — the graph carries one for all of them.
- L389 `_first_items(context: dict)` (function)
- L397 `_normalise_items(items: list)` (function)
- L427 `_product_name(page: SeoPage)` (function)
- L434 `_base_url()` (function)
- L440 `_absolute(request, path: str)` (function)
- L447 `_language()` (function)
