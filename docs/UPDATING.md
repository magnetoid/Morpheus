# Updating Morpheus

> Status of this document: **verified against the running deployment on
> 2026-08-11 (v0.42.0)**, updated 2026-08-13 for v0.44.0. Claims here were checked, not assumed. Where a
> capability exists but does not currently function, this says so plainly.

Morpheus updates three kinds of thing, and they do **not** share a mechanism:

| Component | Versioned by | Updated by |
|---|---|---|
| **Core** (`core/`, `morph/`, `plugins/`, `themes/`) | `MORPHEUS_VERSION` in `morph/settings.py` | the platform updater below, or a redeploy |
| **Apps that ship with core** (`MORPHEUS_DEFAULT_APPS`) | each manifest's `version` | with core — they are part of the platform tree |
| **Apps installed on their own** (`MORPHEUS_EXTRA_APPS`) | each manifest's `version` | the **per-app channel** (v0.44.0) — one at a time, from the signed manifest |
| **Themes** (`themes/library/<name>/`) | each theme's manifest | with core if git-tracked; otherwise the **per-theme channel** (v0.44.0) |

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
MORPHEUS_UPDATE_TOKEN=…                   # optional now the repo is public (raises the GitHub API rate limit)
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

Signing landed in v0.43.3 and the per-app / per-theme channel in v0.44.0 (both
below). Still missing: **artifact verification for the *core* apply** — the
core path is git fast-forward and carries no artifact to verify; a
container deployment redeploys instead.

---

## Updating one app or theme (v0.44.0)

An app or theme installed **on its own** — a commercial app wired in through
`MORPHEUS_EXTRA_APPS`, a theme dropped into `themes/library/` — has its own
entry in the signed manifest and can be updated without touching the platform:

```bash
python manage.py morph_check_updates            # lists app/theme updates under the platform line
python manage.py morph_apply_update --app  my_app          # dry run: the plan
python manage.py morph_apply_update --app  my_app --confirm
python manage.py morph_apply_update --theme my_theme --confirm
```

Dashboard: **Updates → App & theme updates** — one row per component with a
newer signed version, one **Update** button each (gated on the `system.write`
capability). The list is populated by the daily check and by **Check for
updates**; the page itself never makes a network call.

The engine is `core/component_updates.py:apply_component_update`, and it is as
conservative as the platform path, in this order:

1. **Refuses what ships with core.** An app in `MORPHEUS_DEFAULT_APPS`, or any
   directory tracked by the deployment's git checkout, is versioned with
   `MORPHEUS_VERSION`; overwriting it would fork the tree from the platform
   channel, so it returns `blocked` with "update core instead". Paths under
   `core/safety.py`'s protected set are refused the same way.
2. **Refuses a release that needs a newer core** (`min_core`) — shown in the
   UI as "needs core vX first", not hidden, so the merchant learns what the
   blocker is.
3. **Requires a checksum.** The manifest signature covers each entry's
   `sha256`; the artifact is streamed over HTTPS with a size cap and hashed as
   it lands, and a mismatch deletes the file and returns `verify_failed`. An
   entry without a checksum is refused before any download.
4. **Inspects the archive before extracting.** Absolute paths, `..`, symlinks
   and hardlinks, device nodes, more than one top-level directory, or a
   decompressed size past the ceiling all refuse the archive untouched.
   Extraction then also uses `tarfile`'s `data` filter. The result must look
   like what it claims to be — `app.py` / `theme.py` at its root — and an app
   with a `migrations/` directory must ship `migrations/__init__.py` (the
   invisible-migrations landmine).
5. **Swaps by rename, probes, rolls back.** The current tree is moved aside,
   the new one moved in, `manage.py check` runs in a *fresh interpreter*
   (so the new code is genuinely imported), then `migrate` (apps) and
   `check`; any failure renames the previous tree back. Nothing is ever
   half-swapped, and no staging directory is left behind either way.
6. **Dry-run by default, opt-in to apply** — the same `MORPHEUS_SELF_UPDATE_ENABLED`
   gate as the platform path, and `morph_backup` first.

**Restart afterwards.** The running processes still hold the old modules;
the result says `restart_required` and the dashboard message tells the
merchant. On a container deployment the same caveat as core applies: files
written into the container are gone on the next redeploy unless the apps or
themes directory is a persistent volume — put out-of-tree components on one.

### Publishing an app or theme release

On the release machine (where the private key lives), describe the components
in a JSON file and sign them into the manifest with the platform release:

```json
{
  "apps":   {"my_app":   {"version": "1.4.0", "artifact": "https://morpheus.direct/dist/my_app-1.4.0.tar.gz",
                          "sha256": "…", "min_core": "v0.44.0", "notes": "https://…"}},
  "themes": {"my_theme": {"version": "2.0.0", "artifact": "https://…", "sha256": "…"}}
}
```

```bash
MORPHEUS_SIGNING_KEY=… python manage.py morph_sign_manifest \
    --artifact … --sha256 … --components components.json --out stable.json
```

The command refuses an entry without a `version`, an `https://` `artifact`,
or a 64-hex `sha256` — a manifest with a malformed entry is worse than none,
because clients would refuse it later with a less useful message. The
artifact is a `.tar.gz` with **one** top-level directory (`my_app/` or
`my_app-1.4.0/`, as `git archive` produces) containing the component tree.

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
- Nobody gets **integrity guarantees on the git path** — a fast-forward trusts whatever the remote says. (The signed-manifest source added in v0.43.3 does verify; the git path does not and cannot.)
- Apps and themes that ship with core have no channel of their own — they are the platform. Apps and themes installed **on their own** do (v0.44.0, above).

Phase 3 of the plan ("a pluggable `UpdateSource` per component") was designed
for exactly this. The interface exists (v0.43.2) with two implementations, and
since v0.44.0 the signed-manifest source resolves individual apps and themes
too (`UpdateSource.components()`); the GitHub source deliberately does not —
it authenticates the transport, not the publisher, and an app update is
arbitrary code imported at boot. The status log records the interim decision —
*"Channel decided = git refs/tags"* — which this section supersedes for
distributed installs.

---

## Design: a release channel on `morpheus.direct`

This is the shape the open-core product needs. **Mostly implemented as of
v0.44.0** — signing, verification, per-component check and per-component apply
exist; **hosting** does not (nothing is published at `morpheus.direct` yet —
though the repository is public since 2026-08-21, so anonymous clients can
reach the GitHub releases). What is built and what is not is marked inline
below.

**Built:** `core/signing.py` (Ed25519 sign/verify with a canonical JSON form),
`SignedManifestSource` in `core/update_sources.py` (core + `apps` + `themes`),
`core/component_updates.py` (verified fetch, inspected extract, guarded apply),
and `manage.py morph_sign_manifest --components` for the publisher side.

```bash
# once, on the release machine — the private key never leaves it
python manage.py morph_sign_manifest --generate-key

# each release
MORPHEUS_SIGNING_KEY=… python manage.py morph_sign_manifest \
    --artifact https://morpheus.direct/dist/morpheus-0.43.3.tar.gz \
    --sha256 … --out stable.json
```

Deployments then set `MORPHEUS_UPDATE_MANIFEST_URL` and
`MORPHEUS_UPDATE_PUBLIC_KEY`. A signed manifest takes precedence over the
GitHub source, because it proves the *publisher* produced the bytes; HTTPS only
proves you reached a server.

**Verification fails closed** — the deliberate opposite of `core/authz.py`. An
unsigned manifest, a bad signature, a wrong key, a missing public key, or a
non-HTTPS URL all cause the source to be ignored entirely. Running unverified
code is worse than not updating. (Authorization fails *open* because locking a
merchant out of their own dashboard is worse than a missed permission check —
the two postures are opposite on purpose.)

**Not built:** hosting the manifest anywhere, and downloading/verifying a
*core* artifact — the core apply is still git fast-forward, and a container
install redeploys. Per-app / per-theme entries are read and applied (v0.44.0).

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

Apply order is lowest blast radius first: themes → apps → core. Per-component
apply is built (v0.44.0, above): one component at a time, verified, probed,
rolled back on failure. Core apply keeps the existing guarantees (backup, boot
probe in a fresh interpreter, rollback). Not yet: running the core swap behind
**maintenance mode** — which is real since v0.41.0
(`storefront.middleware_maintenance`) — so the storefront returns a 503 with
the merchant's message while code swaps, and staff keep access.

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

# One app or theme installed on its own (same gate; dry-run without --confirm)
python manage.py morph_apply_update --app my_app --confirm
python manage.py morph_apply_update --theme my_theme --confirm
```

On a **container deployment** (the dotbooks.store model), ignore the above and
redeploy: push to `main`, let the image rebuild, then confirm `/readyz` reports
the expected `MORPHEUS_VERSION`. Recovery for a stuck build queue is in
[`docs/OPERATIONS_RUNBOOK.md`](OPERATIONS_RUNBOOK.md).
