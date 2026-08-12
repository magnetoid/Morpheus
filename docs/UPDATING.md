# Updating Morpheus

> Status of this document: **verified against the running deployment on
> 2026-08-11 (v0.42.0)**, updated 2026-08-12 for v0.43.2. Claims here were checked, not assumed. Where a
> capability exists but does not currently function, this says so plainly.

Morpheus updates three kinds of thing, and they do **not** share a mechanism:

| Component | Versioned by | Updated by |
|---|---|---|
| **Core** (`core/`, `morph/`, `plugins/`, `themes/`) | `MORPHEUS_VERSION` in `morph/settings.py` | the platform updater below, or a redeploy |
| **Apps** (`plugins/installed/<name>/app.py`) | each manifest's `version` | shipped with core today — no independent channel |
| **Themes** (`themes/library/<name>/`) | each theme's manifest | shipped with core today — no independent channel |

`manage.py morph_versions --json` is the **stable contract** other tools read
for this inventory. Don't parse the dashboard HTML.

---

## What is built today

Phases 1, 2 and 4 of [`docs/plans/updating-system-2026-06.md`](plans/updating-system-2026-06.md)
shipped. Concretely:

**Inventory** — `core/versioning.py:component_versions()` returns core + enabled
apps + active themes with their versions. Read-only, fail-soft.
CLI: `manage.py morph_versions [--json]`.

**Status check** — `core/updates.py:platform_update_status(fetch=False)` compares
the deployed git checkout against its upstream branch and returns
`{source, available, current, sha, branch, upstream, behind, ahead, latest}`,
where `available ∈ {yes, no, unknown, unavailable}`. Cached for 36h under
`morpheus:update_status` so a missed daily run doesn't blank the page.
CLI: `manage.py morph_check_updates`.

**Apply + rollback** — `core/updates.py:apply_platform_update()`. This is the
high-stakes path and it is deliberately conservative:

- **Dry-run by default.** Without `confirm=True` it returns a plan and mutates nothing.
- **Opt-in.** Even with `confirm`, it refuses unless `MORPHEUS_SELF_UPDATE_ENABLED` is on (it is **off** by default).
- **Fast-forward only.** Aborts if the local checkout has diverged. Never force-updates.
- **Dependency guard.** Refuses with `deps_changed` if upstream touched a dependency manifest, because an in-place apply cannot `pip install` — see the native-dep landmine in [`CLAUDE.md`](../CLAUDE.md). Rebuild the image instead, or pass `allow_dependency_changes` once you've installed them.
- **Ordered safety:** backup (`morph_backup`) → `git merge --ff-only` → **boot probe** (`manage.py check` in a *fresh interpreter*, so the new code is genuinely re-imported) → `migrate` → in-process `check`. Any failure rolls the **code** back to the prior commit.
- The boot probe runs **before** `migrate` on purpose, so a non-bootable update reverts with the database untouched.

CLI: `manage.py morph_apply_update [--confirm]`. Dashboard: **Version & updates**.

**Known limit, stated in the code:** DB migrations are *not* auto-reversed on
rollback. The pre-update backup is the restore point, and the result reports
this loudly. Treat any update that migrates as backup-first.

---

## Update checks without git (v0.43.2)

`core/update_sources.py` adds a pluggable `UpdateSource`, with a
`GitHubReleaseSource` implementation. When a deployment has no `.git`,
`platform_update_status()` now falls back to the configured source instead of
giving up, so a container install can finally *ask* whether an update exists:

```bash
MORPHEUS_UPDATE_REPO=magnetoid/morpheus   # owner/repo
MORPHEUS_UPDATE_TOKEN=…                   # only while the repo is private
```

This is **check only** — applying is still git-based and still gated by
`MORPHEUS_SELF_UPDATE_ENABLED`.

Two behaviours worth knowing:

- **A private repository answers 404 to an anonymous client**, which is
  indistinguishable from "no releases yet". That is reported as `unknown` with a
  reason, never as "up to date". Telling a merchant they are current when we
  cannot see the releases is the worst failure mode an updater has.
- **TLS is verified against certifi's bundle** when available. `urllib` uses the
  interpreter's default trust store, which is empty on a python.org macOS build
  unless `Install Certificates.command` was run — every request then dies with
  `CERTIFICATE_VERIFY_FAILED` and the source merely looks "unreachable". This
  was caught by contract-testing against the live API; every mocked test passed.
  Verification is never disabled: an unverified update channel is worse than
  none.

Still missing before this is a real channel: **signatures** (nothing verifies
the artifact), and **per-app/theme sources** (the only unit of update is still
the whole platform).

---

## What does not work, and why

### The updater is inert on this production deployment

`platform_update_status()` and `apply_platform_update()` both begin by checking
for `.git` in the deployment root, and return `unavailable` without it:

> *"No git metadata in this deployment (built image / non-git install)."*

**Verified 2026-08-11 on dotbooks.store:** `/app/.git` does not exist in the
running web container. So the Version & updates page reports `unavailable`, and
`morph_apply_update` refuses, by design. Everything above is correct code that
this deployment cannot reach.

This is not a bug in the updater — it is the deployment model. Coolify builds an
image from a source copy without git metadata, and updates happen by
**rebuild + redeploy** (a push to `main`), not by the in-place updater. That is
a legitimate and arguably safer model. It just means: **do not rely on the
in-app updater on a container deployment. Redeploy.**

Since v0.43.2 the *check* half no longer depends on git — set
`MORPHEUS_UPDATE_REPO` and the section above takes over, so the dashboard can at
least tell you a newer version exists. **Applying** still requires git and is
still the wrong tool here; the answer on a container remains "redeploy".

### The channel model does not fit open-core distribution

The current source is **git fast-forward from the deployment's own upstream
branch**. That works for an operator who deployed by cloning the repository. It
does not work for anyone else, and "anyone else" is the whole point of an
open-core product:

- An operator who runs a **published image** has no upstream branch to fast-forward.
- An operator who installed from a **tarball or package index** has no git at all.
- Nobody gets **integrity guarantees** — a fast-forward trusts whatever the remote says. There is no signature, no checksum, no provenance.
- Apps and themes have **no independent channel**. A merchant cannot update one app; the only unit of update is the whole platform.

Phase 3 of the plan ("a pluggable `UpdateSource` per component") was designed
for exactly this and is **not built**. The status log records the interim
decision — *"Channel decided = git refs/tags"* — which is the decision this
section supersedes for distributed installs.

---

## Design: a release channel on `morpheus.direct`

This is the shape the open-core product needs. It is **not implemented**; it is
recorded here so the next person builds the right thing rather than extending
the git path further.

### 1. A signed release manifest

Served from the project root domain, e.g.
`https://morpheus.direct/updates/stable.json`:

```json
{
  "channel": "stable",
  "generated_at": "2026-08-11T18:00:00Z",
  "core": {
    "version": "v0.42.0",
    "min_upgrade_from": "v0.38.0",
    "artifact": "https://morpheus.direct/dist/morpheus-0.42.0.tar.gz",
    "sha256": "…",
    "signature": "…",
    "notes": "https://morpheus.direct/releases/v0.42.0",
    "breaking": true,
    "requires_rebuild": true
  },
  "apps": {
    "loyalty_points": { "version": "1.4.0", "artifact": "…", "sha256": "…", "signature": "…" }
  }
}
```

Load-bearing fields, each earned from a real incident in this repo:

- **`signature`** — Ed25519 over the manifest, verified against a public key compiled into core. The same key infrastructure the commercial edition needs for licensing; build it once. **Never** apply an unsigned or unverified artifact.
- **`min_upgrade_from`** — refuse to jump a gap the migration path doesn't support, instead of discovering it mid-`migrate`.
- **`requires_rebuild`** — set when a release changes dependencies. The in-place path cannot `pip install`; a release that needs native wheels must tell the operator to rebuild rather than half-apply. (This has 503'd this store before.)
- **`breaking`** — surfaced in the UI *before* apply, linked to the migration note.

### 2. `UpdateSource` as an interface

Keep the source pluggable, per the plan's open-core alignment: the OSS core and
community apps resolve against the public channel; commercial apps resolve
against a licensed channel that authenticates with the customer's key. Same
apply engine, different source. `GitUpdateSource` becomes one implementation
rather than the only one.

### 3. Per-component apply, core last

Apply order is lowest blast radius first: themes → apps → core. Core apply keeps
the existing guarantees (backup, boot probe in a fresh interpreter, rollback)
and additionally runs behind **maintenance mode** — which is real since v0.41.0
(`storefront.middleware_maintenance`), so the storefront returns a 503 with the
merchant's message while code swaps, and staff keep access.

### 4. Container installs update by tag, not by patch

For image-based deployments the honest update path is "pull the new tag and
recreate", not an in-place file swap. The manifest should carry the image
reference so the dashboard can *tell the operator what to pull* and verify the
running version afterwards, rather than pretending it can self-patch.

---

## Rules (do not regress these)

- **The apply engine is core, permanently.** A togglable app that owns the updater could be disabled, orphaning the updater. Only the *UI* may live in an app.
- **Everything that mutates installed code goes through `core/safety.py`.**
- **Never auto-apply a core update unattended.** The Worker may propose and stage updates and read changelogs; a human confirms the apply. This is the AI-first bit done safely — see phase 5, not built.
- **Never leave the platform unbootable.** Backup → staged swap → healthcheck → auto-rollback. The boot probe must run in a *fresh interpreter*; an in-process `check` cannot detect that new code fails to import.
- **`manage.py morph_versions --json` is a stable contract.** Other tools read it.
- A deployment without git metadata must degrade to `unavailable` and say why — never error, never silently claim "up to date".

---

## Operator quick reference

```bash
# What is installed?
python manage.py morph_versions --json

# Is there an update? (network; safe, read-only)
python manage.py morph_check_updates

# Plan an update without touching anything
python manage.py morph_apply_update

# Actually apply (requires MORPHEUS_SELF_UPDATE_ENABLED=1)
python manage.py morph_apply_update --confirm
```

On a **container deployment** (the dotbooks.store model), ignore the above and
redeploy: push to `main`, let the image rebuild, then confirm `/readyz` reports
the expected `MORPHEUS_VERSION`. Recovery for a stuck build queue is in
[`docs/OPERATIONS_RUNBOOK.md`](OPERATIONS_RUNBOOK.md).
