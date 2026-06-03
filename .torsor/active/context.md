---
type: active-context
status: active
tags:
- active
links: []
created: '2026-06-04T01:01:46'
updated: '2026-06-04T01:01:46'
---

# Active Context

## Current focus
Storefront + settings polish session complete. Shipped (all committed to main, NOT pushed — holding per batch-before-push): (1) shipping carrier SettingsPanel folded into the unified page (788a872); (2) Caching unification — image-opt + Cloudflare cache controls now both on /dashboard/settings/caching/, ADR 0005 supersedes ADR 0002 (386d3e9 fix + a6f5920 + 263c28c); (3) checkout one-page money-dict render bug fixed (9fa4063); (4) Genres mega menu from the live Category tree + header declutter (df6a11a). All tested on sqlite.

## Open questions
Remaining de-dup backlog: PAYMENTS (payments + advanced_payments two panels under category 'payments' — unify). KNOWN SEPARATE BUG: 4 pre-existing failures in cloudflare/tests/test_purge.py (test_zone_last_purge_at_updates_on_success etc.) fail on baseline HEAD — purge logic / test-fake mismatch, worth a look. Also: ecommerce.py:655 has the same cfg.config_data dead-read bug as shipping had. Docs TODO: ARCHITECTURE.md note that Caching is the single home for edge/image-perf settings. Nothing pushed this session — user says "ship" to deploy.
