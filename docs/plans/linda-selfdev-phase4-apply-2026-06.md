# Linda self-dev Phase 4 — apply step (the write+gate half) — 2026-06

> Policy: **ADR 0014** (signed off 2026-06-08). Build the apply machinery,
> shipped **dormant** behind `MORPHEUS_SELF_UPDATE_ENABLED` (default OFF).
> Scope of THIS phase = turn an owner-approved `CodeProposal` into code **on a
> git branch** (never `main`), behind every gate. Staging deploy + auto-promote
> to prod is **Phase 7** (separate).

## The flow
`draft → consensus → OWNER approves → apply (write to branch) → [Phase 7: staging → promote]`

1. **Draft** (shipped): `code.draft_tool` scans + saves `CodeProposal(status=draft)`.
2. **Consensus** (shipped): `code.evaluate_proposal` records advisory verdict.
3. **Owner approval** (NEW): `selfdev_approve` mgmt command — `CodeProposal.approve(user)`
   raises unless `user.is_superuser`; sets `status=approved`, records approver +
   timestamp. Owner-only is enforced HERE (the binding human step per ADR 0014),
   so the apply step never needs to extract identity from the tool-approval flow.
4. **Apply** (NEW): `core/assistant/apply.apply_proposal(proposal)` — gated engine.

## Where applied code lands (the core/ conflict)
`core/safety.py:PROTECTED_PATHS` blocks `core/`, so the legacy draft target
`core/assistant/tools/generated/<slug>.py` is **un-appliable** under the policy.
Per ADR 0014 (blast radius = under `plugins/installed/`, never core) + ADR 0013
(disable a plugin → its surfaces vanish), applied tools land in a NEW plugin:

- **`plugins/installed/linda_generated/`** — human-authored host (scaffolded this
  phase). `ready()` auto-imports `tools/*.py`, so a tool file dropped there
  registers its `@tool` on next boot. Empty initially (harmless). Registered in
  `MORPHEUS_DEFAULT_APPS`. Disable it → all of Linda's generated tools vanish.
- `code.draft_tool` target_path changes → `plugins/installed/linda_generated/tools/<slug>.py`.

## `core/assistant/apply.py` (the engine — gated, dormant)
- `apply_enabled() -> bool` — truthy `MORPHEUS_SELF_UPDATE_ENABLED`. Default OFF.
- `MAX_APPLIES_PER_DAY = 5` — circuit breaker (count `status=applied` in last 24h).
- `preflight(proposal) -> list[str]` — ALL must be clear (empty list) or no write:
  1. `apply_enabled()` else `'self-update disabled'`.
  2. `proposal.status == 'approved'` else `'not owner-approved'`.
  3. `proposal.passed` (re-run `scan_source`/`passed` on current source) else `'scan failed'`.
  4. consensus decision is `approve`/`sufficient` (advisory but required ≥ quorum;
     `insufficient` defers) else `'consensus not satisfied'`.
  5. target under `plugins/installed/` AND NOT `is_path_protected()` AND `.py`
     else `'protected/invalid path'`.
  6. `find_violations(source, [target])` empty (forbidden patterns / magnitude) else its reasons.
  7. circuit breaker not tripped else `'rate limit'`.
- `apply_proposal(proposal) -> dict` — runs `preflight`; if clear:
  create branch `selfdev/<slug>-<short-id>` off HEAD (NEVER main), write file
  (mkdir -p), `git add` + commit (fixed-arg `subprocess`, no shell — mirror
  `core/updates.py:_git`), set `status=applied` + `applied_branch` + `applied_at`,
  `core.audit.record(event_type='selfdev.apply', ...)`. On any failure: audit +
  return `{'applied': False, 'reason': ...}`, leave status unchanged. Never raises
  to the caller.

## Model (CodeProposal) — migration 0008
Add: `approver` (CharField, blank — username/email of approving superuser),
`approved_at` (nullable DateTime), `applied_branch` (CharField, blank),
`applied_at` (nullable DateTime). Methods: `approve(user)` (superuser-only),
`mark_applied(branch)`.

## Tool — `code.apply_proposal`
`scopes=['system.write','selfdev']`, `requires_approval=True` (hard-gate — a second
human confirm on top of the owner-approval already recorded). Thin wrapper over
`apply_proposal`. Returns the structured result; dormant → returns blocked note.

## Owner-approval surface
`core/assistant/management/commands/selfdev_approve.py` — `--id <uuid> --user
<username>`; looks up the user, calls `proposal.approve(user)` (fails if not
superuser), prints result. Shell access = operator = owner. (A dashboard button
is a later nicety; the command is the minimal real surface.)

## Success criteria (verifiable)
- Flag OFF (default): `apply_proposal` returns blocked, writes nothing, no branch. ✓ test
- Path under `core/` or other protected: preflight rejects. ✓ test
- `status != approved`: preflight rejects. ✓ test
- `approve(non_superuser)` raises; `approve(superuser)` sets approved. ✓ test
- Flag ON + approved + clean source + tmp git repo: writes file to a NEW
  `selfdev/*` branch, commits, never touches `main`, status→applied, audit row. ✓ test
- 6th apply in 24h: circuit breaker rejects. ✓ test

## Out of scope (Phase 7 / later)
Runtime registration of the applied tool (staging deploy loads it), staging clone +
auto-promote to prod, dashboard approve/review UI, merge-to-main. Flipping
`MORPHEUS_SELF_UPDATE_ENABLED` ON is a separate deliberate owner action.
