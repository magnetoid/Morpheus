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

# plugins/installed/webstories/tests/test_story_signals.py

Symbols in `plugins/installed/webstories/tests/test_story_signals.py`.

- L25 `_product(status='active', has_images=True)` (function)
- L33 `BookDetailsGateTests` (class)
- L34 `test_the_book_app_is_not_read_while_it_is_off(self)` (method)
- L50 `test_the_book_app_is_read_while_it_is_on(self)` (method)
- L61 `StoryBuildSavepointTests` (class) — Catching the exception is not enough on Postgres; only a savepoint keeps
- L65 `_depth_inside_build(self, receiver, **kwargs)` (method)
- L74 `test_a_product_save_builds_the_story_in_its_own_savepoint(self)` (method)
- L82 `test_an_image_save_builds_the_story_in_its_own_savepoint(self)` (method)
- L91 `test_an_image_delete_builds_the_story_in_its_own_savepoint(self)` (method)
- L107 `test_an_image_deleted_from_a_product_not_on_sale_builds_nothing(self)` (method)
- L117 `test_a_failed_story_never_fails_the_save(self)` (method)
- L136 `ProductDeleteTests` (class) — Deleting a product deletes its images first. The image-delete receiver
- L143 `setUp(self)` (method)
- L154 `_product_with_image(self, status)` (method)
- L173 `test_a_product_with_images_can_be_deleted(self)` (method)
- L187 `test_deleting_one_image_of_a_live_product_rebuilds_its_story(self)` (method)
