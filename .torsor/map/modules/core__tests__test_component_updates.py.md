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

# core/tests/test_component_updates.py

Symbols in `core/tests/test_component_updates.py`.

- L46 `_Resp` (class) — A urlopen() response: bytes + context-manager protocol.
- L49 `__enter__(self)` (method)
- L52 `__exit__(self, *exc)` (method)
- L57 `_tar_bytes(members: dict[str, bytes | None], *, links: dict[str, str] | None=None)` (function) — Build a .tar.gz in memory. `None` content = directory. `links` adds
- L80 `_sha(data: bytes)` (function)
- L84 `_write_tar(tmp: Path, data: bytes, name: str='a.tar.gz')` (function)
- L104 `_FakeSource` (class)
- L107 `__init__(self, releases)` (method)
- L110 `latest(self)` (method)
- L113 `components(self)` (method)
- L120 `ManifestComponentsTests` (class)
- L121 `setUp(self)` (method)
- L140 `_source(self, doc=None)` (method)
- L148 `test_verified_manifest_yields_app_and_theme_entries(self)` (method)
- L158 `test_tampered_manifest_yields_nothing_at_all(self)` (method) — Editing one entry after signing must invalidate the whole channel —
- L168 `test_one_fetch_serves_latest_and_components(self)` (method)
- L176 `test_github_source_publishes_no_components(self)` (method) — Transport-authenticated only — it may not vouch for arbitrary code.
- L181 `ComponentUpdatesTests` (class)
- L195 `test_lists_only_installed_and_newer(self)` (method)
- L202 `test_core_ok_reflects_min_core(self)` (method)
- L208 `test_no_source_is_empty(self)` (method)
- L212 `test_check_for_update_carries_components(self)` (method)
- L244 `FetchArtifactTests` (class)
- L245 `setUp(self)` (method)
- L249 `_urlopen(self, data=None)` (method)
- L255 `_leftovers(self)` (method)
- L258 `test_matching_checksum_lands_the_bytes(self)` (method)
- L263 `test_mismatched_checksum_is_refused_and_leaves_nothing(self)` (method)
- L268 `test_missing_checksum_is_refused_before_any_network(self)` (method)
- L273 `test_plain_http_is_refused_before_any_network(self)` (method)
- L278 `test_oversize_is_refused_and_leaves_nothing(self)` (method)
- L283 `test_network_failure_is_an_artifact_error_not_a_crash(self)` (method)
- L297 `ArchiveSafetyTests` (class)
- L298 `setUp(self)` (method)
- L301 `_refused(self, members, links=None, msg='')` (method)
- L306 `test_good_archive_reports_its_single_top_dir(self)` (method)
- L310 `test_parent_traversal_refused(self)` (method)
- L313 `test_absolute_path_refused(self)` (method)
- L316 `test_symlink_refused(self)` (method)
- L319 `test_two_top_level_entries_refused(self)` (method)
- L322 `test_loose_root_file_refused(self)` (method)
- L325 `test_not_a_tarball_refused(self)` (method)
- L332 `ExtractComponentTests` (class)
- L333 `setUp(self)` (method)
- L337 `_extract(self, members, kind, name)` (method)
- L341 `test_app_tree_is_normalised_to_its_name(self)` (method)
- L348 `test_theme_tree_extracts(self)` (method)
- L352 `test_app_without_manifest_refused(self)` (method)
- L356 `test_theme_without_theme_py_refused(self)` (method)
- L360 `test_app_with_invisible_migrations_package_refused(self)` (method) — A migrations/ dir without __init__.py is the landmine that left five
- L376 `ShipsWithCoreTests` (class)
- L377 `test_a_default_app_is_refused(self)` (method)
- L385 `test_a_git_tracked_theme_is_refused_when_git_is_present(self)` (method)
- L395 `test_an_out_of_tree_component_is_allowed(self)` (method)
- L400 `test_protected_paths_are_refused(self)` (method)
- L411 `ApplyComponentUpdateTests` (class) — End to end on a temp theme dir: real fetch (mocked socket), real
- L416 `setUp(self)` (method)
- L445 `_probe(self, ok=True)` (method)
- L450 `_siblings(self)` (method)
- L453 `test_dry_run_changes_nothing(self)` (method)
- L460 `test_confirm_without_opt_in_is_disabled(self)` (method)
- L466 `test_needs_newer_core_is_blocked(self)` (method)
- L476 `test_missing_checksum_is_verify_failed_before_download(self)` (method)
- L486 `test_happy_path_swaps_the_tree_and_cleans_up(self)` (method)
- L498 `test_boot_probe_failure_restores_the_previous_tree(self)` (method)
- L507 `test_checksum_mismatch_never_touches_the_tree(self)` (method)
- L520 `test_not_installed_here_is_unavailable(self)` (method)
- L525 `test_unknown_kind_is_unavailable(self)` (method)
- L532 `SignManifestComponentsTests` (class)
- L533 `setUp(self)` (method)
- L537 `_run(self, components: dict)` (method)
- L552 `test_components_are_signed_into_the_manifest(self)` (method)
- L584 `test_entry_without_checksum_is_rejected_at_publish_time(self)` (method)
- L588 `test_plain_http_artifact_is_rejected_at_publish_time(self)` (method)
- L598 `test_bad_component_name_is_rejected(self)` (method)
