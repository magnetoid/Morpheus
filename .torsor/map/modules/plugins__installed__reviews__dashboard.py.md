---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/reviews/dashboard.py

Symbols in `plugins/installed/reviews/dashboard.py`.

- L28 `reviews_list(request)` (function) — List + filter reviews. Default to 'all' so newcomers see everything.
- L65 `review_action(request, review_id)` (function) — Approve / hide / unhide a single review. POST-only.
- L88 `review_respond(request, review_id)` (function) — Add a public merchant reply. Stored as a metafield on the Review
