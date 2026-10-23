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

# plugins/installed/release_notes/tests/test_release_notes.py

Symbols in `plugins/installed/release_notes/tests/test_release_notes.py`.

- L33 `ParseReleasesTests` (class)
- L34 `test_splits_versions_newest_first(self)` (method)
- L40 `test_empty_doc(self)` (method)
- L44 `VersionPageTests` (class)
- L45 `setUp(self)` (method)
- L51 `test_page_renders_for_staff(self)` (method)
- L58 `test_anon_blocked(self)` (method)
- L62 `test_page_is_the_unified_updater_plus_changelog(self)` (method) — The two update pages are one: the version page now also renders the
- L76 `test_updates_page_redirects_to_the_unified_page(self)` (method) — /dashboard/updates/ folds into the one page while release_notes is on.
- L84 `SitePageTests` (class) — About lives on the project website and opens embedded here.
- L92 `setUp(self)` (method)
- L98 `test_about_embeds_the_website_page(self)` (method)
- L112 `test_the_rest_of_the_dashboard_frames_nothing_external(self)` (method)
- L117 `test_the_account_menu_links_help_and_about(self)` (method)
- L123 `test_anon_blocked(self)` (method)
- L136 `HonestUpdaterTests` (class) — Safe deploys, part 5: the page says what runs, and offers nothing that cannot work.
- L141 `setUp(self)` (method)
- L153 `page(self, *, self_update, platform=None)` (method)
- L166 `test_a_built_image_gets_one_line_instead_of_buttons(self)` (method)
- L177 `test_it_shows_the_commit_the_install_time_and_the_backup(self)` (method)
- L193 `test_without_a_backup_it_says_when_one_is_made(self)` (method)
- L199 `test_a_git_install_keeps_its_buttons(self)` (method)
