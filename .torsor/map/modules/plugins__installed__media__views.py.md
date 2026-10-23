---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/media/views.py

Symbols in `plugins/installed/media/views.py`.

- L31 `_UnifiedAsset` (class) — Adapter that exposes a uniform shape across MediaAsset,
- L62 `__init__(self, *, id, kind, url, filename='', mime_type='', alt_text='', title='', description='', tags=None, width=None, height=None, size_bytes=0, created_at=None, edit_url='', save_url='', source='media', source_label='')` (method)
- L102 `is_image(self)` (method)
- L106 `editable(self)` (method) — How much meta the inline modal can edit: 'full' (MediaAsset →
- L117 `human_size(self)` (method)
- L126 `from_media_asset(cls, a)` (method)
- L148 `from_product_image(cls, pi)` (method)
- L171 `from_digital_file(cls, prod)` (method)
- L216 `from_variant_file(cls, variant)` (method) — Per-variant digital file (ProductVariant.digital_file) — e.g. a book
- L252 `_federated_assets(view: str, search: str='', tag: str='')` (function) — Read-time union of MediaAsset, ProductImage, and Product.digital_file.
- L356 `_doc_view_matches(filename: str, mime: str, view: str)` (function) — Whether a document-ish asset (by filename + mime) belongs in a doc
- L372 `_filter_for_view(qs, view: str)` (function) — Narrow ``qs`` to a single tab. Returns the same queryset when view='all'.
- L397 `_build_tabs(view: str)` (function) — Pre-counted tab list rendered into the template.
- L506 `library(request: HttpRequest)` (function) — Browse the asset library — single page with tabs across every type.
- L553 `upload(request: HttpRequest)` (function) — Multipart upload — single or multi-file.
- L578 `api_upload(request: HttpRequest)` (function) — JSON-returning upload endpoint — used by the picker modal so the
- L610 `delete(request: HttpRequest, asset_id)` (function)
- L621 `edit_meta(request: HttpRequest, asset_id)` (function) — Edit title / alt text / description / tags. The file itself is
- L667 `picker_modal(request: HttpRequest)` (function) — Embeddable picker — used in iframes / dialogs in other forms.
