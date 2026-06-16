---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/environments/services.py

Symbols in `plugins/installed/environments/services.py`.

- L14 `take_snapshot(environment, *, label: str='', actor=None)` (function) — Capture an environment's overrides into a fresh snapshot.
- L32 `diff_snapshots(snapshot_a_payload: dict[str, Any], snapshot_b_payload: dict[str, Any])` (function)
- L51 `promote(*, snapshot, target, actor=None, note: str='', confirm: bool=False, dry_run: bool=False)` (function) — Apply a snapshot to a target environment, creating a Deployment record.
- L97 `rollback(deployment)` (function) — Rollback a deployment by re-applying its `pre` diff to the target.
