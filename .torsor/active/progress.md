---
type: progress
status: active
tags:
- active
links: []
created: '2026-06-04T01:01:46'
updated: '2026-06-04T01:01:46'
---

# Progress

Done + committed (main, unpushed): shipping panel fold (ADR 0003); caching settings unification Phases 0-2 (ADR 0005, supersedes 0002) incl. a live 500 fix on the caching page; checkout |money fix; storefront Genres mega menu + nav_categories context processor. Test runner note: use `DATABASE_URL='sqlite:///:memory:' python manage.py test …` locally (bare manage.py test hits the .env Docker `db` host). Caching plan: docs/plans/caching-settings-unification-2026-06.md.
