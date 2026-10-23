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

# core/update_sources.py

Symbols in `core/update_sources.py`.

- L36 `_ssl_context()` (function) — Verify TLS against certifi's bundle when available.
- L58 `ReleaseInfo` (class) — One published version, as a source reports it.
- L74 `ComponentRelease` (class) — One published version of an *app* or *theme* — the per-component channel.
- L93 `parse_version(value: str)` (function) — `'v1.2.3'` → `(1, 2, 3)`. Unparseable → `()`, which sorts lowest.
- L107 `is_newer(candidate: str, current: str)` (function) — True if `candidate` is a strictly higher version than `current`.
- L121 `UpdateSource` (class) — Interface. Implementations must be read-only and must not raise.
- L126 `latest(self)` (method)
- L129 `components(self)` (method) — Per-app / per-theme releases this source publishes. Default: none.
- L140 `GitHubReleaseSource` (class) — Resolve the latest release from the GitHub Releases API.
- L153 `__init__(self, repo: str, token: str='')` (method)
- L157 `_get(self, path: str)` (method)
- L172 `latest(self)` (method)
- L212 `SignedManifestSource` (class) — Resolve the latest release from a signed manifest at a fixed URL.
- L227 `__init__(self, url: str, public_key_b64: str)` (method)
- L233 `_verified_document(self)` (method) — Fetch the manifest once and return it only if its signature verifies.
- L278 `latest(self)` (method)
- L295 `components(self)` (method) — Every app/theme entry of a *verified* manifest — nothing otherwise.
- L330 `configured_source()` (function) — Build the source this deployment is configured to use, or None.
- L360 `installed_components()` (function) — `{(kind, name): version}` for every registered app and discovered theme.
- L372 `component_updates(source: UpdateSource | None=None, installed: dict[tuple[str, str], str] | None=None, core_version: str | None=None)` (function) — Apps/themes the source publishes a newer version of than what's installed.
- L416 `check_for_update(current_version: str)` (function) — Ask the configured source whether something newer exists.
