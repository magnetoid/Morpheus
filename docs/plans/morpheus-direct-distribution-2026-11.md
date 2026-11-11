# Updates from morpheus.direct — design (2026-11)

**Status: approved by the owner 2026-11-11. R1 is live; R2 is this release.**

## What the owner asked, and what they decided

On 2026-11-11, in Serbian, the owner asked for three things: stores getting Morpheus updates from morpheus.direct, an app marketplace there, and licence activation. In the design talk that day they decided:

- **Licences: set aside.** They said licences are activated, not sold, and that the model should be "open core or something similar", then that licences can wait. When they come back, LICENSE has to change: BUSL-1.1 without an Additional Use Grant requires a commercial licence for any production use, which contradicts open core. That is the owner's and a lawyer's call.
- **Apps: set aside.** "Apps aren't important now; we keep them on GitHub, as they are." The marketplace is deferred. The sketch at the end, "Later: the app marketplace", keeps what the design talk settled for when it returns.
- **Linda's `updates.apply` stays as it is.**
- **Removing a marketplace app, when the marketplace comes, only switches it off in its first version.**
- **The daily check:** the owner had no preference, so it stays on by default (my call, below).

So this design covers one thing: **any Morpheus install learns that a release exists, and takes it the right way for how it runs.** Calls the owner did not make are marked **(my call)**.

## Why

Today only the owner's five stores get new versions, because Coolify builds `main` for them. Anyone else who installs Morpheus has no way to hear that a release exists, and no supported way to take it:
- `docs/UPDATING.md` sketches a channel on morpheus.direct, but nothing publishes one;
- a container install reports "unavailable" or "unknown".

## What already exists (do not rebuild)

- **Signing.** `core/signing.py` signs and verifies Ed25519 over canonical JSON (`canonical_bytes`, `sign_manifest`, `verify_manifest`). It has no Django imports.
- **`manage.py morph_sign_manifest`.** It generates a keypair (`--generate-key`) and signs a manifest with a core entry; apps and themes are optional.
- **`core/update_sources.py`.**
  - `SignedManifestSource` fails closed: no key, a bad signature or a non-HTTPS URL means the manifest is ignored.
  - `check_for_update()` speaks the `available ∈ {yes, no, unknown, unavailable}` vocabulary.
- **`core/updates.py`.**
  - `platform_update_status` falls back to the configured source only when there is no `.git` (`core/updates.py:88`).
  - The daily beat caches the result for 36 h.
  - `apply_platform_update` fast-forwards a git checkout and is gated by `MORPHEUS_SELF_UPDATE_ENABLED`, which is off by default.
  - `can_self_update()` means a `.git` and the git tool.
- **Linda.** She has `updates.status` and `updates.apply` (`core/assistant/tools/admin_ops.py:76`: scope `system.write`, hard-gated, git checkouts only).
- **Deploy-time pieces.**
  - `safe_migrate` backs up before migrating.
  - The migration gate keeps the previous release working.
  - `scripts/deploy_guard.py` (`sign`, `deploy_commit`) already sends a store's own Coolify manual webhook a signed push naming one commit.
- **Images and releases.**
  - `.github/workflows/cd.yml` pushes `ghcr.io/magnetoid/morpheus:<sha>` and `:latest` after CI passes on `main`.
  - `release.yml` creates an annotated tag and a GitHub Release (not prerelease) on every version push, before deploy-smoke runs.
  - `docker-compose.yml` runs `${MORPHEUS_IMAGE:-ghcr.io/magnetoid/morpheus:latest}`, with a `build:` fallback.

## Goals

1. **Any install learns that a new release exists.** It shows the notes, a "breaking" flag, and what to do to take it, the right way for a git checkout, Coolify, or docker compose with our image.
2. **An install on Coolify that builds this repository can take a release with one button**, pressed by a superuser.
3. **One signer, one trust root.** What a store is told about releases is signed by the owner's key and verified before it is believed.
4. **A release is offered only after it ran on the owner's stores.** Something that left them down is never offered to anyone.

## Non-goals

- Licences and the licensed channel (set aside by the owner).
- The app marketplace, and installing apps or themes from morpheus.direct (set aside by the owner). Apps keep coming from this repository.
- Changing how the owner's five stores deploy: they keep building `main` on Coolify.
- Moving the store themes out of the public repo.
- A beta channel. There is one channel, `stable`, meaning every release that passed deploy-smoke.
- Applying a core update by itself on a schedule.

## Anti-goals (a failure even if it "works")

- **A store setting that names code to install or a commit to deploy.** Linda can write settings, so such a setting is remote code execution (CLAUDE.md). The manifest URL, the public keys and the deploy hook are env vars or baked defaults, never settings. The store only ever deploys the commit the verified manifest names.
- **A core update applied unattended.** A person presses the button, every time.
- **Saying it works before it does.** The README and the site keep the channel under "not yet" until the release that ships it is live.
- **Telling morpheus.direct which store is asking.** The daily check carries a version, nothing that identifies the store.

## Design

### 1. The channel: morpheus.direct hosts and signs one manifest

**morpheus-web becomes the channel (my call).** The repo `magnetoid/morpheus-web` serves morpheus.direct today. It will also serve `https://morpheus.direct/updates/stable.json`, the one signed manifest.

- **Where the key lives.** The private key goes in one place: the morpheus-web GitHub secret `MORPHEUS_SIGNING_KEY`, with a copy in the owner's Keychain. It never goes in the Morpheus repo, a store, or a deployment.
- **Why not sign in Morpheus.** The alternative was for Morpheus's own workflows to sign after deploy-smoke and publish the file. That works too. But when the marketplace returns, its registry lives on morpheus.direct, and one signer in one place stays true.

**A new workflow in morpheus-web, `channel.yml`,** runs every 3 hours and on manual dispatch (every 3 hours rather than hourly, because the private repo's Actions minutes are limited; my call). Each run:

1. **Finds the newest release.** It reads the newest GitHub Release of `magnetoid/Morpheus` (public, no token) and resolves its tag to the commit. Tags are annotated, so the tag ref names a tag object; dereference it (`refs/tags/vX.Y.Z^{}`).
2. **Waits for deploy-smoke.** It publishes a release only once the `deploy-smoke` workflow run for that commit concluded `success`. A release that left the owner's stores down, and was rolled back, is never offered. The channel keeps naming the previous good one, and the run logs why.
   - deploy-smoke cancels a run in progress when the next push lands, so a release commit's own run can be `cancelled`. Then a later `main` commit with the same `MORPHEUS_VERSION` that passed smoke counts, and **that** commit is the one published: it is what ran on the stores, and on v0.122.0 only it had an image (my call, after review).
3. **Waits for the image.** It checks that `ghcr.io/magnetoid/morpheus:<sha>` exists. A release whose image is not there yet (404) waits for the next run; any other answer turns the run red.
4. **Builds the core entry:**
   - `version` and `commit` (the commit deploy-smoke passed on: the dereferenced tag commit, or the later same-version commit);
   - `image`, pinned to its digest: `ghcr.io/magnetoid/morpheus:<sha>@sha256:<digest>`, so the signature vouches for the bytes, not only a tag (my call, after review);
   - `notes_url` (the GitHub Release);
   - `notes` (the first lines of that release's notes);
   - `breaking`: true when `docs/MIGRATING.md` at that commit has a section for the version.
5. **Signs the whole document.** It does a sparse checkout of `core/signing.py` from that commit and calls `sign_manifest` from a small wrapper, so the signer and every store share one canonical form.
   - The file is pinned by its sha256 in morpheus-web (`channel/signing.sha256`), checked before any of it runs: code merged into Morpheus `main` must never run beside the signing key unreviewed. A change to `core/signing.py` turns the run red until someone reviews it and updates the pin (my call, after review).
   - Signing runs in its own job, which holds the secret and only a read token; a second job, with no secret and no Morpheus code, commits the file.
6. **Publishes only on a change.** It commits `updates/stable.json` only when the content changed. That push deploys morpheus.direct, as any push does today. `generated_at` is not part of the comparison, or every hour would commit.

**Manifest shape.** This extends what `SignedManifestSource` reads today:

```json
{
  "channel": "stable",
  "generated_at": "2026-11-20T10:00:00Z",
  "core": {
    "version": "v0.153.0",
    "commit": "<40-hex>",
    "image": "ghcr.io/magnetoid/morpheus:<40-hex>@sha256:<64-hex>",
    "notes_url": "https://github.com/magnetoid/Morpheus/releases/tag/v0.153.0",
    "notes": "…",
    "breaking": false
  },
  "signature": "<base64>"
}
```

The signature covers everything except `signature`.

**Key handling.**
- The owner generates the keypair once with `manage.py morph_sign_manifest --generate-key`.
- The public key is baked into `morph/settings.py` as the default of `MORPHEUS_UPDATE_PUBLIC_KEY`.
- The setting takes a comma-separated list, so a rotation ships the new key in a release before the signer switches to it **(my call)**.
- `MORPHEUS_UPDATE_MANIFEST_URL` defaults to `https://morpheus.direct/updates/stable.json`.
- Both stay env vars, so a fork can point at its own channel.
- Under `settings._RUNNING_TESTS` both default to empty, so tests never touch the network.
- Setting the URL to `off` turns the check off.

**The daily check is on by default (my call; the owner had no preference).**
- Every install asks morpheus.direct once a day, through the beat task that already runs.
- It sends a `User-Agent` with the Morpheus version (the client already sends `_USER_AGENT`; the version is appended). It sends no store name, domain or id.
- Cloudflare's request counts give the owner a rough count of installs per version.
- The README and `docs/UPDATING.md` say this and how to turn it off.

### 2. Taking a release

**What the status says changes.**
- **When a manifest is configured, status reads it first, whether or not `.git` exists.** Today `platform_update_status` checks `.git` before anything else (`core/updates.py:88`). Two cases then answer "unknown" instead of reading the manifest:
  - an image can carry `/app/.git` without the git tool, because `.dockerignore` does not exclude `.git`;
  - a laptop clone checked out at a tag has no upstream.

  The git comparison stays only where it is needed: the fast-forward path.
- The release entry gains `commit`, `image` and `breaking`; `notes_url` maps onto the existing `url` field.
- Settings → Version & updates (the `release_notes` app) and Linda's `updates.status` show:
  - the new version, its notes and a "breaking" badge, linking `docs/MIGRATING.md`;
  - how this install takes it.

**How an install takes it.** This is detected, never configured in a setting:

| How this install runs | Detected by | What the page offers |
|---|---|---|
| Git checkout with git | `can_self_update()` | The existing "Update now" (fast-forward), changed to fast-forward to the manifest's `commit`. It refuses when that commit is not a descendant of HEAD, and still refuses dependency changes. |
| Coolify building `magnetoid/Morpheus`, deploy hook set | `MORPHEUS_DEPLOY_HOOK_URL` + `MORPHEUS_DEPLOY_HOOK_SECRET` env, plus `MORPHEUS_DEPLOY_HOOK_BRANCH` (default `main`) | "Update now" (§2a) |
| Anything else: compose with our image, other hosts, forks | the fallback | The exact commands to set `MORPHEUS_IMAGE=<image from the manifest>`, then `docker compose pull` and `docker compose up -d`, plus a link to the notes |

**Linda's `updates.apply` stays as it is** (owner, 2026-11-11): git checkouts only, hard-gated, after the merchant's own yes. It now fast-forwards to the manifest's commit, like the button. The Coolify button in §2a is not reachable from it.

**2a. Update now on Coolify.** Coolify's manual GitHub webhook deploys the `after` commit of a push its secret signed. `scripts/deploy_guard.py` already uses this mechanism to put a store back.

1. A superuser presses "Update now", gated by `system.write` plus `is_superuser`, the restore screen's posture **(my call)**.
2. A confirm screen shows:
   - the current and the new version, the notes and the breaking flag;
   - "the database is backed up before it migrates";
   - a link to the restore screen;
   - "if the new version does not come up, put the previous one back in Coolify", with a link to Coolify's rollback.
3. On confirm, the store sends its own hook a signed push naming the manifest's `commit`.
   - It uses the same body and signature as `deploy_guard.deploy_commit`, with repository `magnetoid/Morpheus` and branch `MORPHEUS_DEPLOY_HOOK_BRANCH`.
   - Move `sign` and the body builder into `core/updates.py` and have the script import them, so there is one copy.
   - A fork's Coolify resource would not have the manifest's commit, so a fork gets the instructions row, never the button **(my call)**.
4. It writes an audit row naming the person, the old version and the new one.
5. Coolify builds the commit and swaps the containers. `safe_migrate` backs up and migrates, as on every deploy.

**Constraints on the deploy hook.**
- **Env vars only.** The hook URL, secret and branch are env vars, never settings: a setting that can trigger a deploy would be the RCE hole again.
- **Only the manifest's commit.** The store only ever sends the commit the verified manifest names: no free-form commit, and no older one. Going back stays Coolify's rollback or the restore screen.
- **No automatic rollback for other people's installs.** `deploy_guard.py` watches only the owner's stores, so another install gets no automatic code rollback. The confirm screen says so.

## Release sequence

Each Morpheus release ships through `manage.py release`, with:
- the help guide of each app it touches (`release_notes` for Version & updates);
- tests;
- a merge only on the owner's explicit yes, because a merge deploys all five stores.

The morpheus-web steps are site deploys, with no `MORPHEUS_VERSION`.

| # | Where | What | Live check |
|---|---|---|---|
| R1 | morpheus-web | The keypair (the owner runs `--generate-key`; the private key goes to the GitHub secret and the Keychain), `channel.yml`, the first signed `updates/stable.json` | `morpheus.direct/updates/stable.json` verifies against the public key locally and names the newest release that passed deploy-smoke |
| R2 | Morpheus, minor | Baked URL and public key, the `off` switch, the version in `User-Agent`, status reads the manifest first, `commit`/`image`/`breaking`, the "how to take it" table, `updates.status` fields, fast-forward to the manifest's commit. Docs: UPDATING.md, README (the daily check and how to turn it off), the release_notes guide | The five stores say "up to date"; a laptop clone at the previous tag says the new version is out and offers the fast-forward |
| R3 | Morpheus, minor | §2a "Update now" on Coolify, the signed-push helpers moved into core, the audit row | On a staging Coolify app (never a live store) with the hook set, update from the previous tag to the current one |

R2 needs R1 live, because its baked key must be the real one. R3 needs R2.

## Tests the builder must add

- **Channel settings:**
  - under tests the URL and key are empty;
  - `off` turns the check off;
  - a list of keys accepts either key;
  - a manifest signed by an unknown key is ignored.
- **Status:**
  - with a manifest configured, an image with `.git` but no git reports the manifest's release;
  - so does a clone at a tag without an upstream;
  - a git checkout still offers the fast-forward.
- **Fast-forward:** it moves to the manifest's commit only, and refuses a commit that is not a descendant.
- **Deploy hook:**
  - it sends only the manifest's commit;
  - it is never offered without the URL and the secret, nor on a fork;
  - its signature matches `deploy_guard`'s for the same body (one helper);
  - nothing in a POST can change the commit.
- **Boundaries:** the permission trio on every new view (anonymous, staff without `system.write`, superuser).
- **Linda:** `updates.apply` keeps its gate and scope, and no tool can reach the Coolify path.
- **morpheus-web:** a release whose deploy-smoke run failed, or whose image is missing, is not published.

## Left to the builder

- Module and view file names, template layout, the exact confirm-screen copy (plain words, per the help rules).
- How `channel.yml` checks the GHCR image (the registry API or `docker manifest inspect`) and reads the deploy-smoke run (the Actions API by `head_sha`).
- Caching the manifest fetch inside one request.

## Later: the app marketplace (set aside by the owner, 2026-11-11)

This is not part of the release sequence. It records what the design talk settled, so the work does not start from zero when the owner brings it back.

- **Where it lives.** It is the same channel: a registry in morpheus-web (`apps/registry/<name>.json`, reviewed by pull request), signed into `stable.json` by `channel.yml`. A catalogue page on morpheus.direct is generated from that registry.
- **Who publishes.** Authors submit, and the owner reviews and signs. There are no per-publisher keys at first.
- **Apps first, themes later.** A theme outside the tree needs registry work an app does not:
  - discovery imports `themes.library.<name>.theme` only (`themes/registry.py:44`);
  - template and static paths assume `MORPHEUS_THEMES_DIR` (`themes/base.py:191-200`);
  - a `themes/` folder on `sys.path` collides with the in-tree `themes` package.
- **Installing needs what does not exist today.** `apply_component_update` only replaces an installed component. The marketplace needs:
  - a persistent `MORPHEUS_MARKETPLACE_DIR` volume, created owned by `morpheus` in the Dockerfile;
  - an `installed.json` there that only core's install engine writes and `settings.py` reads, fail-soft and with validated names;
  - apps imported as `morpheus_apps.<name>`;
  - WhiteNoise serving each installed app's `static/`, since static files are collected only at build time;
  - its own env switch, because `MORPHEUS_SELF_UPDATE_ENABLED` is off by default;
  - migrations only at the next boot through `safe_migrate`, with web, worker and beat all restarted.
- **Removing an app (owner, 2026-11-11):** the first version only switches an app off. Code and data stay, because a table no model knows blocks deleting the customer, order or product its rows name.
- **Linda:** she may read the catalogue and recommend, but gets no install, update or removal tool for marketplace code.
- **The first listing** is to be chosen when it returns.
