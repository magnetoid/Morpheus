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

# plugins/installed/seo/tests/test_robots_contributions.py

Symbols in `plugins/installed/seo/tests/test_robots_contributions.py`.

- L21 `RobotsContributionTests` (class)
- L22 `setUp(self)` (method)
- L25 `test_the_storefront_private_paths_are_present(self)` (method) — These come from `storefront.app.on_robots_rules`, not from seo.
- L31 `test_the_chrome_paths_seo_owns_are_present(self)` (method)
- L36 `test_every_group_receives_the_disallows(self)` (method) — A path worth blocking is worth blocking for every crawler. The file
- L48 `test_a_blocked_parameter_reaches_robots_txt(self)` (method)
- L52 `test_other_policies_do_not_reach_robots_txt(self)` (method) — `block` is the only policy that stops a fetch. A no-indexed page has
- L61 `test_search_is_not_disallowed(self)` (method) — Site search is already `noindex, follow` through its page kind. A
- L67 `test_the_sitemap_index_is_advertised(self)` (method)
