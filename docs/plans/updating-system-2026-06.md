# Plugin / theme / core updating system (epic)

Created 2026-06-03. Standing goal: *a reliable, AI-first, eventually-open-core
platform with a plugin + theme + core updating system.* This is the design +
phased plan. Follows `CLAUDE.md` (foundational → core; modular features →
plugins; spec before non-trivial work).

## Where it lives
- **Inventory + apply/rollback orchestration = core** (`core/versioning.py`,
  later `core/updates/`). A version inventory that must include core itself,
  and the machinery that swaps code, cannot be a disableable plugin — same
  reasoning as observability + the self-improvement loop.
- **Update *sources* + per-component metadata = the component.** Each plugin/
  theme declares its `version` (already does) and, later, an update channel
  (git ref / package index / marketplace URL). Core orchestrates; components
  describe themselves.
- **Dashboard surface = a contribution** (a core "System / Updates" page, or a
  small `platform_updates` plugin for the UI only — UI can be a plugin; the
  apply engine cannot).

## Phases (each shippable + verifiable)
1. **Inventory (DONE 2026-06-03).** `core/versioning.py:component_versions()`
   → core + plugins (enabled) + themes (active) with versions. CLI:
   `manage.py morph_versions [--json]`. Read-only, fail-soft. Foundation for
   everything below.
2. **Dashboard "Updates" page (read-only).** Surface the inventory in the
   dashboard (System group): version table + "all up to date" until phase 3.
   Verify: page lists core/plugins/themes with versions.
3. **Remote update-check.** A pluggable `UpdateSource` per component (git tag,
   PyPI/registry, or a Morpheus marketplace manifest). `check_updates()`
   compares installed vs latest → `{component: {current, latest, available}}`.
   Cache + a beat task. Verify: a component with a newer remote version shows
   "update available"; offline → degrades to "unknown", never errors.
4. **Apply + rollback (core, high-stakes — gated).** Download/verify
   (checksum/signature) → stage → migrate → swap → healthcheck → auto-rollback
   on failure. Plugins/themes first (lower blast radius); **core last**, behind
   maintenance mode + a backup (`morph_backup` already exists) + explicit
   confirm. Route every apply through `core/safety.py`. Verify: apply a plugin
   update in staging; forced-failure auto-rolls-back.
5. **AI-assisted updates (the "AI-first" bit).** The Worker can *propose* +
   stage updates and read changelogs, but apply stays human-confirmed + behind
   the safety boundary (no unattended core swaps). Ties into the
   self-improvement loop's upstream-drift tracking.

## Open-core alignment
Versioning + update channels are exactly what an open-core distribution needs:
OSS core + plugins update from public channels; commercial plugins from a
licensed channel. Keep `UpdateSource` an interface so channels are pluggable.

## Landmines / rules
- Core self-update must never leave the platform unbootable: backup + staged
  swap + healthcheck + auto-rollback, maintenance mode during apply.
- Everything that mutates installed code goes through `core/safety.py`.
- Don't add a togglable "updates" plugin that owns the apply engine (disabling
  it would orphan the updater) — apply is core; only the UI may be a plugin.
- `manage.py morph_versions --json` is the stable contract other tools read.

## Status log
- 2026-06-03: Phase 1 (inventory) shipped — `core/versioning.py` +
  `morph_versions` command + 4 tests.
- 2026-06-03: Phase 2 (read-only Updates page) shipped — `/dashboard/updates/`
  in the Settings sidebar; surfaces core/plugin/theme versions.
- 2026-06-03: **Channel decided = git refs/tags.** Phase 3 (remote
  update-check) shipped — `core/updates.py:platform_update_status(fetch=)`
  compares the deployed checkout vs its upstream; `manage.py
  morph_check_updates`; "Check for updates" button + platform status on the
  Updates page. Read-only + fail-soft (prod container has no `.git` →
  "unavailable", which is correct: this Coolify deploy updates via `git push`;
  the in-app updater serves self-hosted git installs).
- 2026-06-03: **Phase 4 (apply + rollback) shipped — conservatively.**
  `core/updates.py:apply_platform_update(confirm=, run_migrations=)` +
  `manage.py morph_apply_update` (dry-run by default). Safety posture:
  **dry-run unless `--confirm`**; **opt-in** (`MORPHEUS_SELF_UPDATE_ENABLED`,
  default off); **fast-forward only** (aborts on divergence); **backup first**
  (`morph_backup`) → `migrate` → `check`, with **code rollback** (`git reset
  --hard` to the prior sha) on any failure; **CLI-only** (no web trigger);
  **inert without `.git`**. DB migrations are NOT auto-reversed — the
  pre-update backup is the documented restore point. Guard tests (dry-run /
  disabled / noop / unavailable) never run a real apply.
- **Remaining hardening (future):** per-plugin/theme update channels (vs the
  monorepo whole-checkout apply), DB-snapshot restore on migrate failure,
  maintenance-mode middleware during apply, signature verification of refs,
  and an AI-assisted "review changelog + stage" step (phase 5).
