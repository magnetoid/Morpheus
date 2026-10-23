---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/booking_marketplace/tests/test_experience_jsonld.py

Symbols in `plugins/installed/booking_marketplace/tests/test_experience_jsonld.py`.

- L25 `_graphs(html)` (function) — Parse every ld+json script body in the page into its @graph list.
- L34 `_find_types(html)` (function)
- L43 `ExperienceJsonLdTests` (class)
- L45 `setUpTestData(cls)` (method)
- L63 `test_product_graph_present_and_parses(self)` (method)
- L70 `_product(self)` (method)
- L78 `test_unverified_ratings_publish_nothing(self)` (method) — The fixture is the live condition: the columns say 4.8 from 3, one
- L86 `test_verified_reviews_publish_rating_and_nodes_from_the_same_set(self)` (method)
- L108 `test_script_tag_not_breakable_by_content(self)` (method)
