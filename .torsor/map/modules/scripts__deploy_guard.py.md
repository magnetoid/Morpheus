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

# scripts/deploy_guard.py

Symbols in `scripts/deploy_guard.py`.

- L65 `version_key(text: str)` (function)
- L70 `expected_version(settings_text: str)` (function)
- L75 `previous_release(expected: str, tags: list[str])` (function) — The newest release tag older than ``expected``.
- L84 `next_release(release: str, tags: list[str])` (function) — The oldest release tag newer than ``release``.
- L93 `_body(response)` (function)
- L100 `http_get(url: str, timeout: float=15)` (function)
- L112 `http_post(url: str, body: bytes, headers: dict, timeout: float=30)` (function)
- L123 `store_state(base: str, get=http_get)` (function) — ``(version, state)``: the version /readyz reports, and 'ok' (/readyz
- L145 `classify_all(stores, expected, *, get=http_get, sleep=time.sleep, clock=time.monotonic)` (function) — Each store's state: 'up' (healthy on ``expected``), 'late' (healthy on
- L166 `read_before(path: str)` (function) — What each store served when the smoke started: the ``base version`` lines
- L177 `target_release(base: str, expected: str, tags: list[str], before: dict)` (function) — The release ``base`` goes back to: the one it served when the smoke
- L188 `sign(secret: str, body: bytes)` (function)
- L192 `deploy_commit(hook: str, repository: str, branch: str, secret: str, commit: str, post=http_post)` (function) — Send the store's webhook a signed push event naming ``commit``.
- L213 `queued(text: str)` (function) — Whether Coolify's answer says a deployment was queued.
- L231 `_git(*args: str)` (function)
- L237 `tag_commit(tag: str)` (function)
- L241 `release_tags()` (function)
- L245 `load_config(env=None)` (function)
- L263 `contract_migrations(release: str, tags: list[str])` (function) — The migrations added after the release that followed ``release`` that
- L282 `report(states: dict, expected: str, log)` (function)
- L297 `choose_targets(down, expected, tags, before, *, contract_of, log)` (function) — The release each store that is down goes back to; a store it cannot
- L319 `send_back(config, stores, targets, *, commit_of, post, log)` (function) — Send each store the push for its release; the stores queued, with that release.
- L340 `wait_back(waiting, expected, *, get, sleep, log, clock)` (function) — Wait, for all of them together, until each store serves the release it
- L366 `rollback(config, expected, tags, *, dry_run=False, before=None, get=http_get, post=http_post, sleep=time.sleep, clock=time.monotonic, commit_of=tag_commit, contract_of=None, log=print)` (function) — Put back every store that is down; the exit code: 0 when every store is
- L402 `main(argv: list[str] | None=None)` (function)
