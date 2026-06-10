---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/metafields/models.py

Symbols in `plugins/installed/metafields/models.py`.

- L13 `MetafieldManager` (class) — Manager API used by templates and plugin code.
- L27 `for_obj(self, instance, *, ns: str | None=None)` (method) — Return a flat ``{"namespace.key": typed_value}`` dict.
- L39 `set(self, instance, *, namespace: str='', key: str, value: Any, value_type: str='')` (method) — Idempotent upsert. `value` is JSON-serialised on the way in.
- L55 `delete_for(self, instance, *, namespace: str='', key: str)` (method)
- L64 `_infer_value_type(value: Any)` (method)
- L76 `_encode(value: Any, value_type: str)` (method)
- L86 `Metafield` (class) — A single `(content_type, object_id, namespace, key) → value` triple.
- L139 `__str__(self)` (method)
- L144 `full_key(self)` (method)
- L148 `typed_value(self)` (method) — Decode the stored string into the value_type's native form.
