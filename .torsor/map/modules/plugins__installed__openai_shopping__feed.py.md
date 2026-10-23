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

# plugins/installed/openai_shopping/feed.py

Symbols in `plugins/installed/openai_shopping/feed.py`.

- L16 `FeedConfig` (class) — The settings panel's values. The three channel-resolver fields
- L38 `config()` (function) — The panel's values, read fresh (a plugin config cache is per-process).
- L59 `_seller(cfg: FeedConfig, base: str)` (function)
- L78 `_row(item: dict, *, cfg: FeedConfig, seller: dict, group: dict | None=None)` (function) — One feed row from a shared-resolver feed-attr dict.
- L122 `_variant_name(row: dict, base: dict)` (function) — The resolver titles a variant ``<product> — <variant>``; keep the tail.
- L130 `build_rows()` (function) — Every active product the shared resolver accepts, as feed rows.
- L161 `render_jsonl(rows: list[dict[str, Any]])` (function)
- L165 `coverage()` (function) — Counts for the dashboard page and the Channels overview.
