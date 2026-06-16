---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/metafields/models.py

Symbols in `plugins/installed/metafields/models.py`.

- L14 `MetafieldManager` (class) — Manager API used by templates and plugin code.
- L28 `for_obj(self, instance, *, ns: str | None=None)` (method) — Return a flat ``{"namespace.key": typed_value}`` dict.
- L40 `set(self, instance, *, namespace: str='', key: str, value: Any, value_type: str='')` (method) — Idempotent upsert. `value` is JSON-serialised on the way in.
- L57 `delete_for(self, instance, *, namespace: str='', key: str)` (method)
- L68 `_infer_value_type(value: Any)` (method)
- L80 `_encode(value: Any, value_type: str)` (method)
- L90 `Metafield` (class) — A single `(content_type, object_id, namespace, key) → value` triple.
- L152 `__str__(self)` (method)
- L157 `full_key(self)` (method)
- L161 `typed_value(self)` (method) — Decode the stored string into the value_type's native form.
