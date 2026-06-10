---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/media/models.py

Symbols in `plugins/installed/media/models.py`.

- L14 `_upload_path(instance, filename: str)` (function) — Sharded upload path — keeps any single directory under ~10k files.
- L20 `MediaAsset` (class) — A reusable file in the media library.
- L87 `__str__(self)` (method)
- L91 `url(self)` (method)
- L98 `is_image(self)` (method)
- L102 `human_size(self)` (method) — Bytes → KB / MB / GB string for display.
- L112 `from_upload(cls, *, uploaded_file, uploaded_by=None, alt_text: str='', tags: list | None=None)` (method) — Create a MediaAsset from a Django UploadedFile.
- L160 `_warm_variants(asset, widths=(400, 800))` (method) — Best-effort: pre-generate WebP variants for a freshly uploaded
