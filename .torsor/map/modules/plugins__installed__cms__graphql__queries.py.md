---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
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
- L114 `journal_entry(self, info: strawberry.Info, slug: str)` (method)
- L123 `CmsPageInput` (class)
- L134 `_parsed_publish_at(raw_value: Optional[str])` (function)
- L149 `CmsMutationExtension` (class)
- L151 `create_page(self, info: strawberry.Info, input: CmsPageInput)` (method)
- L176 `update_page(self, info: strawberry.Info, slug: str, input: CmsPageInput)` (method)
- L207 `delete_page(self, info: strawberry.Info, slug: str)` (method)
- L215 `duplicate_page(self, info: strawberry.Info, slug: str)` (method)
- L238 `upsert_block(self, info: strawberry.Info, key: str, label: str, body: str='', kind: str='html')` (method)
