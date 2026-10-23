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

# plugins/installed/customers/models.py

Symbols in `plugins/installed/customers/models.py`.

- L13 `Customer` (class) — Custom user model — replaces Django's default User.
- L89 `__str__(self)` (method)
- L93 `full_name(self)` (method)
- L97 `default_address(self)` (method)
- L101 `Address` (class)
- L127 `__str__(self)` (method)
- L130 `save(self, *args, **kwargs)` (method)
- L154 `CustomerSegment` (class) — RFM scorecard + segment for one customer, recomputed nightly.
- L182 `__str__(self)` (method)
- L186 `SegmentMigration` (class) — Append-only log of segment transitions — powers the migration summary
- L202 `__str__(self)` (method)
