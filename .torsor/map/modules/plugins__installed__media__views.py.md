---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/media/views.py

Symbols in `plugins/installed/media/views.py`.

- L30 `_UnifiedAsset` (class) — Adapter that exposes a uniform shape across MediaAsset,
- L61 `__init__(self, *, id, kind, url, filename='', mime_type='', alt_text='', title='', description='', tags=None, width=None, height=None, size_bytes=0, created_at=None, edit_url='', save_url='', source='media', source_label='')` (method)
- L101 `is_image(self)` (method)
- L105 `editable(self)` (method) — How much meta the inline modal can edit: 'full' (MediaAsset →
- L116 `human_size(self)` (method)
- L125 `from_media_asset(cls, a)` (method)
- L147 `from_product_image(cls, pi)` (method)
- L170 `from_digital_file(cls, prod)` (method)
- L215 `from_variant_file(cls, variant)` (method) — Per-variant digital file (ProductVariant.digital_file) — e.g. a book
- L251 `_federated_assets(view: str, search: str='', tag: str='')` (function) — Read-time union of MediaAsset, ProductImage, and Product.digital_file.
- L355 `_doc_view_matches(filename: str, mime: str, view: str)` (function) — Whether a document-ish asset (by filename + mime) belongs in a doc
- L371 `_filter_for_view(qs, view: str)` (function) — Narrow ``qs`` to a single tab. Returns the same queryset when view='all'.
- L396 `_build_tabs(view: str)` (function) — Pre-counted tab list rendered into the template.
- L504 `library(request: HttpRequest)` (function) — Browse the asset library — single page with tabs across every type.
- L550 `upload(request: HttpRequest)` (function) — Multipart upload — single or multi-file.
- L574 `api_upload(request: HttpRequest)` (function) — JSON-returning upload endpoint — used by the picker modal so the
- L605 `delete(request: HttpRequest, asset_id)` (function)
- L615 `edit_meta(request: HttpRequest, asset_id)` (function) — Edit title / alt text / description / tags. The file itself is
- L660 `picker_modal(request: HttpRequest)` (function) — Embeddable picker — used in iframes / dialogs in other forms.
