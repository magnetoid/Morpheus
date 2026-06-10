---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/reviews/dashboard.py

Symbols in `plugins/installed/reviews/dashboard.py`.

- L25 `reviews_list(request)` (function) — List + filter reviews. Default to 'all' so newcomers see everything.
- L59 `review_action(request, review_id)` (function) — Approve / hide / unhide a single review. POST-only.
- L81 `review_respond(request, review_id)` (function) — Add a public merchant reply. Stored as a metafield on the Review
