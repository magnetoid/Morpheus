---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/cms/graphql/queries.py

Symbols in `plugins/installed/cms/graphql/queries.py`.

- L31 `CmsPageType` (class)
- L45 `CmsJournalEntryType` (class)
- L56 `_page_type(p)` (function)
- L71 `_journal_entry_type(entry: dict)` (function)
- L87 `CmsQueryExtension` (class)
- L89 `cms_pages(self, info: strawberry.Info, state: Optional[str]=None)` (method)
- L99 `cms_page(self, info: strawberry.Info, slug: str)` (method)
- L107 `journal_entries(self, info: strawberry.Info, limit: int=50)` (method)
- L115 `journal_entry(self, info: strawberry.Info, slug: str)` (method)
- L124 `CmsPageInput` (class)
- L135 `_parsed_publish_at(raw_value: Optional[str])` (function)
- L150 `CmsMutationExtension` (class)
- L152 `create_page(self, info: strawberry.Info, input: CmsPageInput)` (method)
- L177 `update_page(self, info: strawberry.Info, slug: str, input: CmsPageInput)` (method)
- L208 `delete_page(self, info: strawberry.Info, slug: str)` (method)
- L216 `duplicate_page(self, info: strawberry.Info, slug: str)` (method)
- L239 `upsert_block(self, info: strawberry.Info, key: str, label: str, body: str='', kind: str='html')` (method)
