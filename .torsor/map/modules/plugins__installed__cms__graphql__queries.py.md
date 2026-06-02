---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/cms/graphql/queries.py

Symbols in `plugins/installed/cms/graphql/queries.py`.

- L28 `CmsPageType` (class)
- L39 `_page_type(p)` (function)
- L53 `CmsQueryExtension` (class)
- L55 `cms_pages(self, info: strawberry.Info, state: Optional[str]=None)` (method)
- L65 `cms_page(self, info: strawberry.Info, slug: str)` (method)
- L74 `CmsPageInput` (class)
- L84 `CmsMutationExtension` (class)
- L86 `create_page(self, info: strawberry.Info, input: CmsPageInput)` (method)
- L109 `update_page(self, info: strawberry.Info, slug: str, input: CmsPageInput)` (method)
- L136 `delete_page(self, info: strawberry.Info, slug: str)` (method)
- L144 `duplicate_page(self, info: strawberry.Info, slug: str)` (method)
- L167 `upsert_block(self, info: strawberry.Info, key: str, label: str, body: str='', kind: str='html')` (method)
