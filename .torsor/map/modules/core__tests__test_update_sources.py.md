---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/tests/test_update_sources.py

Symbols in `core/tests/test_update_sources.py`.

- L25 `VersionComparisonTests` (class)
- L26 `test_parses_the_numeric_core(self)` (method)
- L31 `test_unparseable_is_empty_not_an_error(self)` (method)
- L35 `test_ordering(self)` (method)
- L41 `test_never_offers_an_update_it_cannot_compare(self)` (method) — A dev checkout reporting 'unknown' must not be told to update.
- L47 `GitHubSourceTests` (class)
- L48 `_source(self, token='')` (method)
- L51 `test_accepts_a_full_url_or_a_slug(self)` (method)
- L55 `test_reads_the_tag_and_notes(self)` (method)
- L67 `test_a_404_without_a_token_is_unknown_not_up_to_date(self)` (method) — A private repo 404s anonymously. Reporting that as "no update" would
- L75 `test_network_failure_returns_none_never_raises(self)` (method)
- L80 `CheckForUpdateTests` (class)
- L82 `test_unconfigured_is_unavailable_with_a_reason(self)` (method)
- L89 `test_unreachable_source_is_unknown_not_no(self)` (method)
- L95 `test_reports_yes_and_no_correctly(self)` (method)
- L108 `GitlessDeploymentTests` (class) — The reason this module exists: a container image has no .git.
- L112 `test_status_falls_back_to_the_release_source_without_git(self)` (method)
- L127 `test_without_git_and_without_a_source_it_still_says_why(self)` (method)
- L136 `_NoGitPath` (class) — Stands in for a deployment root whose `.git` does not exist.
- L139 `__truediv__(self, other)` (method)
- L142 `exists(self)` (method)
