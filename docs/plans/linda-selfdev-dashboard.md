# Linda self-development approval dashboard (Phase 2)

## Context

Linda can draft code for herself (`code.draft_tool` → a `CodeProposal` row),
have it statically scanned (`codegen.scan_source`) and reviewed by a multi-model
consensus panel (`consensus.evaluate`), then — behind every gate — applied to a
`selfdev/*` git branch (never `main`) by `apply.apply_proposal`. **Today the only
way to see or approve a proposal is the CLI** (`manage.py selfdev_approve`). The
owner has no window into what Linda has drafted, why a scan flagged it, what the
consensus panel said, or what's blocking an apply.

This phase adds an **owner dashboard** over that fully-gated, already-tested
machinery: list proposals, inspect source + scan findings + consensus verdicts +
the live preflight block-reasons, and **one-click run-consensus / approve / apply /
revert**. It adds visibility and a button — it widens **no** gate.

## Approach

All new code lives in the **`agent_core`** plugin (already Linda's dashboard
surface at `/dashboard/agents/`). Core gains one small helper (`apply.revert_branch`).
No new models, no migration.

### Core (one addition)
- `core/assistant/apply.py` → `revert_branch(proposal) -> dict`: delete the
  proposal's `selfdev/<name>-<id8>` branch via `git branch -D` (plumbing, never
  touches `main`/HEAD/worktree), audit-log `selfdev.revert`, and reset the row to
  `approved` with `applied_branch`/`applied_at` cleared. Never raises.

### agent_core plugin (the dashboard)
- **Views** (`views.py`, all `@staff_member_required`; the three mutating actions
  additionally require `request.user.is_superuser`):
  - `selfdev_list_view` — `CodeProposal`s grouped by status (draft / approved /
    applied / rejected) + the `apply_enabled()` master-switch banner.
  - `selfdev_detail_view` — source, `findings`, `consensus['verdicts']`, and
    `apply.preflight(proposal)` block-reasons so the owner sees *why* apply is
    blocked before clicking.
  - `selfdev_action_view(proposal_id, action)` — POST dispatch over existing
    gated functions:
    - `consensus` → `consensus.evaluate` → persist to `proposal.consensus`.
    - `approve`  → `CodeProposal.approve(request.user)` (superuser-gated, fail-closed).
    - `apply`    → `apply.apply_proposal` (re-checks every gate; returns reasons if blocked).
    - `reject`   → set status `rejected`.
    - `revert`   → `apply.revert_branch`.
- **URLs** (`urls_dashboard.py`): `selfdev/`, `selfdev/<uuid>/`, `selfdev/<uuid>/<action>/`.
- **DashboardPage** (`contribute_dashboard_pages`): a `nav='main'`, `section='ai'`
  entry "Self-development" → `/dashboard/agents/selfdev/` (auto-surfaced via the
  contributed-nav loop; no edit to `admin_dashboard/base.html`).
- **Templates**: `agent_core/dashboard/selfdev_list.html`, `selfdev_detail.html`
  (extend `admin_dashboard/base.html`, mirror `runs.html`).

### Safety invariants (unchanged — the dashboard widens no gate)
`MORPHEUS_SELF_UPDATE_ENABLED` master switch (default off; the dashboard cannot
flip it); superuser-only approve/apply/revert; consensus ≥2/3 quorum re-checked at
apply; 5 applies/24h; `core/safety.py` re-checked on current source; branch-only
writes; apply target stays `plugins/installed/linda_generated/tools/<slug>.py`.

## Reuse (wire, don't rewrite)
`apply.preflight`, `apply.apply_proposal`, `apply.apply_enabled`,
`consensus.evaluate`, `CodeProposal.approve`/`mark_applied`,
`codegen.scan_source`/`passed`.

## Verification
- Permission-boundary tests on every mutating view: anon → redirect/403;
  authed non-superuser → 403; superuser → allowed.
- `apply` blocked (with a visible reason) when `MORPHEUS_SELF_UPDATE_ENABLED` unset.
- `approve` flips a draft to `approved`; `revert` resets an applied row + (if a repo)
  removes the branch.
- `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.agent_core`
  + `manage.py check`. Smoke `/dashboard/agents/selfdev/` after deploy.
