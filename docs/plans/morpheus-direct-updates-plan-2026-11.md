# Updates from morpheus.direct — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Any Morpheus install learns from one signed manifest on morpheus.direct that a release exists, and takes it the right way for how it runs: a git fast-forward, a one-button Coolify deploy, or shown commands.

**Architecture:** morpheus-web gains a scheduled workflow that publishes `updates/stable.json`, signed with the owner's Ed25519 key, but only for a release that passed deploy-smoke and whose image exists. Morpheus bakes the channel URL and the public key as env defaults, reads the manifest before git, and offers one of three paths. A Coolify install sends its own manual webhook a signed push naming the manifest's commit. That is the mechanism `scripts/deploy_guard.py` already uses, moved into core so there is one copy.

**Tech Stack:**
- Django 6.1 / Python 3.12, stdlib `urllib`;
- `cryptography` 50.0.2 (Ed25519, through `core/signing.py`);
- GitHub Actions, nginx (morpheus-web), Coolify v4 manual GitHub webhook.

**Spec:** `docs/plans/morpheus-direct-distribution-2026-11.md` (approved by the owner 2026-11-11).

## Global Constraints

**Configuration and safety**
- No store setting may name code, a commit, a channel URL, a key or a deploy hook. They are env vars or baked defaults only, because Linda writes settings (anti-goal 1).
- A core update is never applied unattended: a person presses a button every time.
- The daily check sends only `User-Agent: morpheus-updater/<MORPHEUS_VERSION>`, never a store name, domain or id.
- The store only ever deploys or fast-forwards to the commit a verified manifest names, and only one that is newer than `MORPHEUS_VERSION`.

**Tests**
- Tests never touch the network.
- Under `settings._RUNNING_TESTS`, `MORPHEUS_UPDATE_MANIFEST_URL` and `MORPHEUS_UPDATE_PUBLIC_KEY` default to `''`.
- Every test mocks `urllib.request.urlopen` or injects a fetcher.
- Run with `DATABASE_URL='sqlite:///:memory:' python manage.py test <labels>`.

**CI gates (each Morpheus release)**
- `ruff check . && ruff format --check .` with ruff 0.15.8.
- `python manage.py check && python manage.py makemigrations --check --dry-run`.
- `python scripts/check_core_boundary.py && python scripts/check_plugin_boundary.py && python scripts/check_plugin_standard.py`.
- `python manage.py release --check`.

**Dashboard**
- Compile every changed template with `get_template()`.
- Use only Tailwind classes already in `admin_dashboard/static/admin_dashboard/tailwind.css`. Otherwise run `npm ci && npm run build` in `admin_dashboard/frontend` and commit the result (CI `dashboard-css`).

**Help text**
- Plain words; the assistant is called Linda.
- `release_notes/tests/test_help_*.py` must pass: no developer words, no new headings outside the set.

**Scripts**
- `scripts/deploy_guard.py` stays runnable by the system Python with the standard library only, so `core/deploy_hook.py` imports nothing outside the stdlib.

**Shipping**
- Each Morpheus release is its own PR and version: `python manage.py release --minor "…" -m "…"`.
- It is merged only on the owner's explicit yes, asked separately each time; a merge deploys all five stores.
- Croatia is queued by hand through the Coolify API until its Git source is fixed.
- A push to morpheus-web `main` deploys morpheus.direct publicly and needs the owner's explicit yes.

**Copy**
- Say "source-available", never "open source".

## Review Focus

1. **A cancelled smoke run on the release commit.** deploy-smoke uses `cancel-in-progress: true`, so a docs push right after a release cancels the release commit's run. The channel must still publish once a later `main` commit with the same `MORPHEUS_VERSION` passed smoke, or it stalls on every release followed by a quick push. Test in Task 2.
2. **A manifest URL that answers HTML.** Before the file exists, or through nginx's SPA fallback, the URL can answer index.html with 200. The client must report "unknown", never crash or say "up to date", and nginx must answer 404. Tests in Task 1 and Task 5.
3. **A store running a newer version than the channel.** This is every owner store between a merge and the channel catching up. Status must be "up to date", and neither path may offer or send the older commit. Tests in Task 6 and Task 11.
4. **Two presses of Update now.** A double-click, or two superusers at once, must queue one deploy; the second press says it was already sent. Test in Task 11.
5. **A page load right after the upgrade.** The cache still holds a git-style status from before. The page must not show that as the channel's answer, and no page load may fetch the manifest. Test in Task 6.

---

## Part R1 — the channel (morpheus-web; site deploys, no `MORPHEUS_VERSION`)

Work in a clone of `magnetoid/morpheus-web` in the session scratchpad, never beside `morph/`. It is a private repo, so Actions minutes count against the account's free allowance.

### Task 1: Serve `/updates/` as JSON, never the home page

**Files:**
- Modify: `Dockerfile`
- Modify: `default.conf`
- Create: `updates/.gitkeep`

**Interfaces:**
- Produces: `https://morpheus.direct/updates/stable.json` answers the file as `application/json`, or 404 when it is absent.

- [ ] **Step 1: Copy the folder into the image.** Add `COPY updates /usr/share/nginx/html/updates` after the `img` line in `Dockerfile`.
- [ ] **Step 2: Add a location block** to `default.conf`, before `location /`:

```nginx
location /updates/ {
    default_type application/json;
    try_files $uri =404;
    add_header Cache-Control "public, max-age=300" always;
}
```

- [ ] **Step 3: Verify.**
  - Run `docker build -t mw-test . && docker run --rm -d -p 3999:3000 --name mw-test mw-test`.
  - Then `curl -s -o /dev/null -w '%{http_code}\n' localhost:3999/updates/stable.json`. Expected: `404`.
  - Without Docker on the machine, run the same `curl` against the live site after Task 4's push.
  - Then `docker rm -f mw-test`.
- [ ] **Step 4: Commit** (no push yet). Run `git add Dockerfile default.conf updates/.gitkeep`, then `git commit -m "channel: serve /updates/ as JSON, 404 when absent"`.

### Task 2: The manifest builder and its tests

**Files:**
- Create: `channel/build_manifest.py`
- Create: `channel/test_build_manifest.py`

**Interfaces:**
- Consumes: `core/signing.py` from the Morpheus release commit, loaded by path:
  - `sign_manifest(manifest: dict, private_key_b64: str) -> dict`;
  - `verify_manifest(manifest: dict, public_key_b64: str) -> bool`.
- Produces: the CLI used by Task 3.
  - `python channel/build_manifest.py resolve --state channel/.state.json` writes `publish`, `commit`, `version` and `reason` to `$GITHUB_OUTPUT`, and the full core entry to the state file.
  - `python channel/build_manifest.py publish --state channel/.state.json --signing <path to signing.py> --out updates/stable.json` reads `MORPHEUS_SIGNING_KEY` and `MORPHEUS_UPDATE_PUBLIC_KEY` from the env.
  - It writes the file only when the release changed, and prints `changed` or `unchanged`.

All network access goes through injectable `fetch_json(url) -> dict | list`, `fetch_text(url) -> str | None` and `fetch_status(url, headers) -> int`. They are stdlib `urllib`, sending `GITHUB_TOKEN` when set.

Functions in `channel/build_manifest.py`:
- `newest_release(fetch_json) -> dict`. Reads `GET https://api.github.com/repos/magnetoid/Morpheus/releases/latest` and returns `{'version': tag_name, 'notes': body, 'notes_url': html_url}`.
- `tag_commit(version, fetch_json) -> str`. Reads `GET …/git/ref/tags/<version>`. When `object.type == 'tag'`, it follows `GET …/git/tags/<sha>` to `object.sha`.
- `smoke_passed(commit, version, fetch_json, fetch_text) -> tuple[bool, str]`. Returns the verdict and a reason for the log. Algorithm:

```
runs = GET …/actions/workflows/deploy-smoke.yml/runs?branch=main&status=completed&per_page=50  (newest first)
own = [r for r in runs if r.head_sha == commit]
if any(r.conclusion == 'failure' for r in own): return False, 'deploy-smoke failed on the release commit'
if any(r.conclusion == 'success' for r in own): return True, 'deploy-smoke passed on the release commit'
for r in runs where r.conclusion == 'success':
    compare = GET …/compare/<commit>...<r.head_sha>
    if compare.status in ('ahead', 'identical'):
        settings = GET raw.githubusercontent.com/magnetoid/Morpheus/<r.head_sha>/morph/settings.py
        if MORPHEUS_VERSION default in settings == version: return True, f'passed on later commit {sha7} of the same version'
return False, 'no successful deploy-smoke for this release yet'
```

- `image_exists(commit, fetch_json, fetch_status) -> bool`.
  - Get an anonymous token from `https://ghcr.io/token?scope=repository:magnetoid/morpheus:pull`.
  - Send `HEAD https://ghcr.io/v2/magnetoid/morpheus/manifests/<commit>` with the OCI index, OCI manifest and Docker v2 manifest `Accept` types. A 200 means it exists.
- `is_breaking(commit, version, fetch_text) -> bool`. True when `docs/MIGRATING.md` at the commit has a line that equals `## <version>` or starts with `## <version> `.
- `first_lines(notes: str, limit: int = 600) -> str`. Cuts at the last line break before `limit`.
- `core_entry(release: dict, commit: str, breaking: bool) -> dict`. Returns `{version, commit, image: f'ghcr.io/magnetoid/morpheus:{commit}', notes_url, notes: first_lines(...), breaking}`. (Superseded by the R1 fix wave: `commit` is the commit deploy-smoke passed on, and `image` carries `@sha256:<digest>`.)
- `same_release(old: dict | None, new: dict) -> bool`. Compares `channel` and `core` only, so `generated_at` and `signature` never count as a change.
- `publish(...)`:
  - builds `{'channel': 'stable', 'generated_at': <UTC ISO, seconds>, 'core': entry}`;
  - signs it with the loaded module;
  - refuses to write unless `verify_manifest(signed, MORPHEUS_UPDATE_PUBLIC_KEY)` is True;
  - writes it with `json.dumps(…, indent=2, sort_keys=True)` plus a trailing newline.

- [ ] **Step 1: Write the failing tests** in `channel/test_build_manifest.py`, with `unittest` and fake fetchers. Expected values:
  - `test_dereferences_an_annotated_tag`: a ref with `object.type == 'tag'` → `tag_commit` returns the inner `object.sha`.
  - `test_own_successful_smoke_publishes` → `(True, …)`.
  - `test_own_failed_smoke_never_publishes`: the release commit's run failed and a later same-version commit passed → `(False, …)`.
  - `test_cancelled_own_run_publishes_after_later_same_version_success`: own run `cancelled`, later run `success`, compare `ahead`, settings at the later sha say the same version → `(True, …)`.
  - `test_later_success_with_a_different_version_does_not_count` → `(False, …)`.
  - `test_missing_image_waits`: `fetch_status` returns 404 → `image_exists` is False.
  - `test_breaking_when_migrating_has_the_version_section`: text `"## v0.153.0 — x\n"` → True; `"## v0.153.1 — x\n"` → False for `v0.153.0`.
  - `test_generated_at_alone_is_not_a_change` → `same_release` is True.
  - `test_publish_signs_and_verifies`:
    - load `core/signing.py` from `os.environ['MORPHEUS_SIGNING_MODULE']`, and skip the test when it is unset;
    - generate a keypair, publish to a temp file, read it back;
    - `verify_manifest(doc, public)` is True and `doc['core']['image'] == 'ghcr.io/magnetoid/morpheus:' + commit`.
  - `test_publish_refuses_a_key_mismatch`: sign with key A and set `MORPHEUS_UPDATE_PUBLIC_KEY` to key B → it raises `SystemExit` and no file is written.
- [ ] **Step 2: Run them and see them fail.** Run `MORPHEUS_SIGNING_MODULE=<morph checkout>/core/signing.py <morph checkout>/.venv/bin/python -m unittest channel/test_build_manifest.py -v`. Expected: ImportError, or each test FAIL.
- [ ] **Step 3: Implement** the functions above and the `resolve` / `publish` subcommands with `argparse`. `resolve`:
  - writes `publish=false` with the reason when smoke has not passed or the image is missing;
  - exits 0 in every case except an API error, which exits 1 so the run shows red.
- [ ] **Step 4: Run the tests and see them pass.** Same command. Expected: all OK, with `test_publish_*` running, not skipped.
- [ ] **Step 5: Commit.** Run `git add channel/`, then `git commit -m "channel: build and sign updates/stable.json from the newest smoke-passed release"`. Add `channel/.state.json` to `.gitignore` in the same commit.

### Task 3: The scheduled workflow

**Files:**
- Create: `.github/workflows/channel.yml`

**Interfaces:**
- Consumes: Task 2's CLI.
- Consumes the repo secret `MORPHEUS_SIGNING_KEY` and the repo variable `MORPHEUS_UPDATE_PUBLIC_KEY` (both set in Task 4).

The workflow, in order:
- `on`:
  - `schedule: - cron: '17 */3 * * *'`. Every 3 hours rather than the spec's hourly **(my call)**: each run bills a whole minute of the private repo's allowance, and hourly would spend about 720 of the free 2,000 a month.
  - `workflow_dispatch`.
- `permissions: contents: write`.
- `concurrency: {group: channel, cancel-in-progress: false}`.
- Steps:
  1. `actions/checkout@v4`.
  2. `actions/setup-python@v5` with 3.12.
  3. Run `python -m unittest channel/test_build_manifest.py -v`; the signing tests skip here, with no module yet.
  4. `resolve` (id `resolve`, env `GITHUB_TOKEN: ${{ github.token }}`).
  5. When `steps.resolve.outputs.publish == 'true'`:
     - `actions/checkout@v4` with `repository: magnetoid/Morpheus`, `ref: ${{ steps.resolve.outputs.commit }}`, `path: morpheus`, `sparse-checkout: core/signing.py`, `sparse-checkout-cone-mode: false`;
     - `pip install cryptography==50.0.2`;
     - `MORPHEUS_SIGNING_MODULE=morpheus/core/signing.py python -m unittest channel/test_build_manifest.py -v`;
     - `publish` with env `MORPHEUS_SIGNING_KEY: ${{ secrets.MORPHEUS_SIGNING_KEY }}` and `MORPHEUS_UPDATE_PUBLIC_KEY: ${{ vars.MORPHEUS_UPDATE_PUBLIC_KEY }}`.
  6. When publish printed `changed`:
     - set the git user `morpheus-channel` and `noreply@morpheus.direct`;
     - commit `updates/stable.json` with message `channel: stable → <version>`;
     - push.

- [ ] **Step 1: Write the workflow** as above.
- [ ] **Step 2: Verify syntax.** Run `actionlint .github/workflows/channel.yml` when installed, else `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/channel.yml'))"`. Expected: no errors.
- [ ] **Step 3: Commit.** Run `git add .github/workflows/channel.yml`, then `git commit -m "channel: publish stable.json every 3 hours and on demand"`.

### Task 4: Keys, first publish, live check (needs the owner's yes)

**Files:**
- Morpheus: none yet.
- The public key printed here becomes Task 5's baked default.

- [ ] **Step 1: Make the keypair without printing the private key.** The owner runs this, or says yes to Claude running it. It uses the Morpheus venv and needs `gh` logged in:

```bash
cd <morph checkout> && .venv/bin/python - <<'EOF'
import subprocess
from core.signing import generate_keypair
private, public = generate_keypair()
subprocess.run(['gh', 'secret', 'set', 'MORPHEUS_SIGNING_KEY', '-R', 'magnetoid/morpheus-web'], input=private, text=True, check=True)
subprocess.run(['security', '-i'], input=f'add-generic-password -U -a signing -s morpheus.direct-channel -w {private}\n', text=True, check=True)  # stdin, never argv
subprocess.run(['gh', 'variable', 'set', 'MORPHEUS_UPDATE_PUBLIC_KEY', '-R', 'magnetoid/morpheus-web', '--body', public], check=True)
print('public key:', public)
EOF
```

  Expected: `public key: <44 chars>`. Record the public key in `docs/UPDATING.md` in Task 9; it is public.
- [ ] **Step 2: Push** Tasks 1–3 to morpheus-web `main`, only on the owner's explicit yes. Then check the morpheus-web app's Coolify deployments before forcing one.
- [ ] **Step 3: Run the channel.** Run `gh workflow run channel.yml -R magnetoid/morpheus-web`, then `gh run watch -R magnetoid/morpheus-web`. Expected:
  - the run is green;
  - a commit `channel: stable → vX.Y.Z` appears on morpheus-web `main`;
  - its push queues a site deploy.
- [ ] **Step 4: Live check.** Run `curl -s "https://morpheus.direct/updates/stable.json?cb=$RANDOM" -o /tmp/stable.json`, then:

```bash
.venv/bin/python -c "import json; from core.signing import verify_manifest; d=json.load(open('/tmp/stable.json')); print(verify_manifest(d, '<public key>'), d['core']['version'], d['core']['commit'][:7])"
```

  Expected: `True v<newest release that passed deploy-smoke> <the commit deploy-smoke passed on>`, and `core.image` ends in `@sha256:<64 hex>`. `curl -sI` shows `content-type: application/json`.
- [ ] **Step 5: Note it** in memory (`morpheus-direct-distribution.md`): the keypair exists, where the private key lives, and that the channel is live.

---

## Part R2 — Morpheus minor: the client

One branch and one PR (`feat/update-channel`), one `release --minor`. It needs R1 live, because the baked key must be the real one.

### Task 5: Channel settings and the signed source

**Files:**
- Modify: `morph/settings.py:84-89`
- Modify: `core/update_sources.py`
- Create: `core/tests/test_update_channel.py`

**Interfaces:**
- Produces, in `morph/settings.py`:
  - `MORPHEUS_UPDATE_CHANNEL_URL = 'https://morpheus.direct/updates/stable.json'` (a constant, not env);
  - `MORPHEUS_UPDATE_MANIFEST_URL = config('MORPHEUS_UPDATE_MANIFEST_URL', default='' if _RUNNING_TESTS else MORPHEUS_UPDATE_CHANNEL_URL)`;
  - `MORPHEUS_UPDATE_PUBLIC_KEY = config('MORPHEUS_UPDATE_PUBLIC_KEY', default='' if _RUNNING_TESTS else '<Task 4 public key>')`, a comma-separated list of keys.
- Produces, in `core/update_sources.py`:
  - `user_agent() -> str` returns `f'morpheus-updater/{core_version()}'`. It replaces `_USER_AGENT` at both call sites.
  - `checks_off() -> bool` is True when `MORPHEUS_UPDATE_MANIFEST_URL.strip().lower() == 'off'`.
  - `ReleaseInfo` gains `commit: str = ''`, `image: str = ''` and `breaking: bool = False`.
  - `SignedManifestSource(url: str, public_key_b64: str)` keeps its signature. It splits `public_key_b64` on commas into `self.public_keys`, and the document verifies when any key verifies.
  - `SignedManifestSource.latest()` maps `url` from `core.notes_url` (today it wrongly copies `notes`).
  - `commit` is kept only when it matches `^[0-9a-f]{40}$`, else `''`. It can be a later commit than the tag's (the one deploy-smoke passed on); nothing may assume they are equal.
  - `image` is kept only when it matches `^[^\s@]+:[0-9a-f]{40}@sha256:[0-9a-f]{64}$` and is at most 200 characters; when the source URL is `MORPHEUS_UPDATE_CHANNEL_URL` it must also start with `ghcr.io/magnetoid/morpheus:`, so a leaked key cannot point installs at another registry. Otherwise `''`.
  - `configured_source()` returns `None` when `checks_off()`, before looking at `MORPHEUS_UPDATE_REPO`.
  - `check_for_update(current_version) -> dict`:
    - when off: `{'source': 'none', 'available': 'unavailable', 'reason': 'Update checks are switched off (MORPHEUS_UPDATE_MANIFEST_URL=off).', 'current': …, 'components': []}`;
    - otherwise its result gains `commit`, `image`, `breaking`, `notes` and `notes_url` (the last from `release.url`).

- [ ] **Step 1: Write the failing tests** in `core/tests/test_update_channel.py` (`SimpleTestCase`, `override_settings`, `mock.patch('core.update_sources.urllib.request.urlopen')`, keys from `core.signing.generate_keypair()`):
  - `test_tests_run_with_no_channel`: `settings.MORPHEUS_UPDATE_MANIFEST_URL == ''` and `settings.MORPHEUS_UPDATE_PUBLIC_KEY == ''`.
  - `test_off_turns_the_check_off`, with URL `'off'` and `MORPHEUS_UPDATE_REPO='magnetoid/Morpheus'`:
    - `check_for_update('v1.0.0')['available'] == 'unavailable'`;
    - `'off' in` its reason;
    - `urlopen.assert_not_called()`.
  - `test_either_listed_key_verifies`: signed with key B, keys `f'{A},{B}'` → `latest().version == 'v9.0.0'`.
  - `test_an_unknown_key_is_ignored`: signed with C, keys `A,B` → `latest() is None`.
  - `test_user_agent_names_the_version_only`, with `MORPHEUS_VERSION='v9.9.9'`: the request's `User-Agent` header `== 'morpheus-updater/v9.9.9'` and no other header carries a host or store name.
  - `test_reads_commit_image_breaking_and_notes_url`:
    - `release.commit == 'a'*40`;
    - `release.image == 'ghcr.io/magnetoid/morpheus:' + 'a'*40 + '@sha256:' + 'd'*64`;
    - `release.breaking is True`;
    - `release.url == 'https://github.com/magnetoid/Morpheus/releases/tag/v9.0.0'`.
  - `test_a_malformed_commit_is_dropped`: commit `'abc'` → `release.commit == ''`.
  - `test_the_default_channel_refuses_a_foreign_image`: URL = `MORPHEUS_UPDATE_CHANNEL_URL`, image `evil.example/x:` + 'a'*40 + '@sha256:' + 'd'*64 → `release.image == ''`; an image without a digest → `''`.
  - `test_an_html_answer_is_unknown`: `urlopen` returns `b'<!doctype html><html>'` → `check_for_update('v1.0.0')['available'] == 'unknown'`.
- [ ] **Step 2: Run them and see them fail.** Run `DATABASE_URL='sqlite:///:memory:' python manage.py test core.tests.test_update_channel -v 2`. Expected: failures on the new fields, `off` and the key list.
- [ ] **Step 3: Implement** the interfaces above.
- [ ] **Step 4: Run the tests and see them pass.** Run `DATABASE_URL='sqlite:///:memory:' python manage.py test core.tests.test_update_channel core.tests.test_update_sources core.tests.test_component_updates core.tests.test_signing`. Expected: OK.
- [ ] **Step 5: Commit.** Run `git add morph/settings.py core/update_sources.py core/tests/test_update_channel.py`, then `git commit -m "feat(updates): morpheus.direct channel by default, key list, off switch, release commit and image"`.

### Task 6: Status reads the manifest first, page loads stay offline

**Files:**
- Modify: `core/updates.py:80-160`
- Create: `core/tests/test_update_status_channel.py`

**Interfaces:**
- Consumes: Task 5's `configured_source()`, `SignedManifestSource`, `check_for_update()` and `checks_off()`.
- Produces:
  - `update_path() -> str` returns `'git'` when `can_self_update()`, else `'manual'`. Task 11 adds `'coolify'`.
  - `platform_update_status(*, fetch: bool = False) -> dict`:
    - when `configured_source()` is a `SignedManifestSource`:
      - with `fetch=True` it returns `check_for_update(core_version())`;
      - otherwise the cached status when `cached.get('source') == 'manifest'`;
      - otherwise `{'source': 'manifest', 'available': 'unknown', 'reason': 'Not checked yet. The store checks once a day; Check for updates checks now.', 'current': core_version(), 'components': []}`;
    - every return path adds `'path': update_path()`;
    - without a manifest source, today's git and GitHub-repo behaviour is unchanged.

- [ ] **Step 1: Write the failing tests:**
  - `test_image_with_git_dir_but_no_git_reads_the_manifest`:
    - `BASE_DIR` is a temp dir containing `.git/`, and `shutil.which` is patched to return `None`;
    - the manifest says v9.0.0 and `MORPHEUS_VERSION` is v1.0.0;
    - with `fetch=True`: `available == 'yes'`, `latest == 'v9.0.0'`, `path == 'manual'`.
  - `test_clone_at_a_tag_without_upstream_reads_the_manifest`:
    - a real temp repo with one commit tagged `v1.0.0`, no remote;
    - `MORPHEUS_VERSION` is v1.0.0 and the manifest says v9.0.0;
    - with `fetch=True`: `available == 'yes'`, `path == 'git'`.
  - `test_page_load_never_fetches`: with `fetch=False`, `urlopen.assert_not_called()`.
  - `test_a_cached_git_status_is_not_shown_as_the_channel`: the cache holds `{'source': 'git', 'available': 'no'}` → with `fetch=False`, `available == 'unknown'` and `'Not checked yet'` in the reason.
  - `test_store_ahead_of_the_channel_is_up_to_date`: `MORPHEUS_VERSION` v0.160.0, manifest v0.159.0 → `available == 'no'`.
- [ ] **Step 2: Run and see them fail.** Run `DATABASE_URL='sqlite:///:memory:' python manage.py test core.tests.test_update_status_channel`. Expected: FAIL.
- [ ] **Step 3: Implement** `update_path()` and the manifest-first branch. `refresh_update_status()` keeps calling `platform_update_status(fetch=True)` and caching the result.
- [ ] **Step 4: Run the tests and see them pass.** Run `DATABASE_URL='sqlite:///:memory:' python manage.py test core.tests.test_update_status_channel core.tests.test_update_check core.tests.test_update_sources`. Expected: OK.
- [ ] **Step 5: Commit.** Run `git add core/updates.py core/tests/test_update_status_channel.py`, then `git commit -m "feat(updates): status reads the signed channel before git; page loads read the cache"`.

### Task 7: Fast-forward to the manifest's commit

**Files:**
- Modify: `core/updates.py:191-340` (`apply_platform_update`, `_dependency_changes`)
- Modify: `core/tests/test_update_apply_safety.py`

**Interfaces:**
- Consumes: the status from Task 6 (`source`, `commit`, `latest`).
- Produces: `apply_platform_update(*, confirm=False, run_migrations=True, allow_dependency_changes=False) -> dict` keeps its signature and return shape.
  - The target is `status['commit']` when `status['source'] == 'manifest'`; otherwise it is `status['upstream']`, as today.
  - `plan['upstream']` becomes `plan['target']`.
  - Its new refusal is `{'ok': False, 'status': 'no_commit', 'reason': 'The release names no commit to update to.'}`.

How it gets the commit:
1. Run `_git(['fetch', '--quiet', 'origin', commit], root, timeout=60)`.
2. Check it with `_git_ok(['cat-file', '-e', f'{commit}^{{commit}}'], root)`. If that fails, return `apply_failed` with "could not fetch the release's commit".
3. If `merge-base --is-ancestor HEAD <commit>` fails, return `diverged` with "The release's commit is not a later commit than this checkout. Update by hand."
4. `_dependency_changes(root, target)` and `merge --ff-only <target>` both use the target.

- [ ] **Step 1: Write the failing tests.** Use real temp git repos and mirror the setup of the existing tests in `test_update_apply_safety.py`: `MORPHEUS_SELF_UPDATE_ENABLED=True`, `_boot_probe` and `call_command` patched, and a bare "origin" repo on disk.
  - `test_moves_to_the_manifest_commit_only`: origin holds A → B → C, the checkout is at A, the manifest names B → `status == 'applied'` and `HEAD == B`, not C.
  - `test_refuses_a_commit_that_is_not_a_descendant`: the manifest names a commit on a side branch → `status == 'diverged'` and HEAD is unchanged.
  - `test_still_refuses_dependency_changes`: B changes `requirements.txt` → `status == 'deps_changed'` and HEAD is unchanged.
  - `test_a_release_without_a_commit_is_refused`: the manifest has no commit → `status == 'no_commit'`.
  - `test_store_ahead_of_the_channel_is_a_noop`: `MORPHEUS_VERSION` is newer than the manifest's version → `status == 'noop'`, no fetch and HEAD is unchanged.
- [ ] **Step 2: Run and see them fail.** Run `DATABASE_URL='sqlite:///:memory:' python manage.py test core.tests.test_update_apply_safety`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement** the target resolution above.
- [ ] **Step 4: Run the tests and see them pass.** Run the same, plus `core.assistant.tests.test_admin_ops plugins.installed.admin_dashboard.tests.test_updates_apply`. Expected: OK, and Linda's `updates.apply` keeps its gate.
- [ ] **Step 5: Commit.** Run `git add core/updates.py core/tests/test_update_apply_safety.py`, then `git commit -m "feat(updates): fast-forward to the release's commit, never past it"`.

### Task 8: Show it on Version & updates and to Linda

**Files:**
- Modify: `plugins/installed/admin_dashboard/templates/admin_dashboard/_updater_card.html`
- Modify: `core/update_sources.py` (`MIGRATING_URL`)
- Modify: `core/assistant/tools/admin_ops.py:56-73` (`_built_image_summary`)
- Create: `plugins/installed/admin_dashboard/tests/test_updater_card_channel.py`
- Modify: `core/assistant/tests/test_admin_ops.py`

**Interfaces:**
- Consumes: the status keys from Tasks 5–6: `available`, `latest`, `notes`, `notes_url`, `breaking`, `image`, `path` and `source`.
- Produces: `MIGRATING_URL = 'https://github.com/magnetoid/Morpheus/blob/main/docs/MIGRATING.md'` in `core/update_sources.py`. `check_for_update` adds it as `migrating_url` when `breaking`.

The card, when `platform.source == 'manifest'`:
- "Check for updates" shows when `running.self_update or platform.source == 'manifest'`.
- When `available == 'yes'`, it shows:
  - "{{ platform.latest }} is out";
  - the notes (`linebreaksbr`) and a "Release notes" link to `notes_url`;
  - with `breaking`, a `pill pill-warn` "Has upgrade steps" linking `migrating_url`.
- Then, by `path`:
  - `git`: today's Update now form, its confirm text saying it moves to `{{ platform.latest }}`;
  - `manual`: "To update: set `MORPHEUS_IMAGE={{ platform.image }}` in your .env, then run `docker compose pull` and `docker compose up -d --no-build`." When there is no image, only the notes link.
- `no` says "Up to date". `unknown` and `unavailable` show the reason.
- The non-manifest branches stay as they are.

Linda's `_built_image_summary(running, status)`:
- for `path == 'manual'` with an image, it appends: " To take it, set MORPHEUS_IMAGE=<image>, then run docker compose pull and docker compose up -d --no-build.";
- when `breaking`, it appends " It has upgrade steps: <migrating_url>.".

- [ ] **Step 1: Write the failing tests.** For the card, GET `/dashboard/updates/` as a superuser with `core.updates.platform_update_status` patched to return each dict:
  - `test_manual_install_shows_the_image_commands`: the body contains `MORPHEUS_IMAGE=ghcr.io/magnetoid/morpheus:` + the sha, and `docker compose pull`.
  - `test_git_install_offers_update_now`: the body contains `reverse('admin_dashboard:updates_apply')`.
  - `test_breaking_release_links_the_upgrade_steps`: `MIGRATING_URL` is in the body.
  - `test_up_to_date_says_so`: "Up to date".
  - `test_check_button_shows_for_a_manifest_install_without_git`: `reverse('admin_dashboard:updates_check')` is in the body when `can_self_update` returns False.
  - `test_the_card_compiles`: `get_template('admin_dashboard/_updater_card.html')`.
  - In `test_admin_ops.py`, `test_status_says_how_a_built_image_takes_the_release`: the display contains `MORPHEUS_IMAGE=`.
- [ ] **Step 2: Run and see them fail.** Run `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.admin_dashboard.tests.test_updater_card_channel core.assistant.tests.test_admin_ops`. Expected: FAIL.
- [ ] **Step 3: Implement** the card branches and the summary lines.
- [ ] **Step 4: Run the tests and see them pass.** Run the same, plus `plugins.installed.release_notes`. Expected: OK.
- [ ] **Step 5: Commit.** Run `git add plugins/installed/admin_dashboard/templates/admin_dashboard/_updater_card.html core/update_sources.py core/assistant/tools/admin_ops.py plugins/installed/admin_dashboard/tests/test_updater_card_channel.py core/assistant/tests/test_admin_ops.py`, then `git commit -m "feat(updates): Version & updates and Linda say what is out and how to take it"`.

### Task 9: Docs, release and live check for R2

**Files:**
- Modify: `docs/UPDATING.md`
- Modify: `README.md`
- Modify: `plugins/installed/release_notes/help.md`
- Modify: `morph/settings.py` (version)
- Modify: `docs/RELEASE_NOTES.md`

- [ ] **Step 1: `docs/UPDATING.md`.** Add a section "Updates from morpheus.direct" covering:
  - what is checked, once a day, and the exact `User-Agent`;
  - how to turn it off (`MORPHEUS_UPDATE_MANIFEST_URL=off`);
  - how a fork points at its own channel and keys;
  - key rotation (a release adds the new key to the list before the signer switches);
  - the three paths;
  - the public key.

  Correct the "What does not work" lines that this release makes untrue.
- [ ] **Step 2: `README.md`.** Replace the "being designed" bullet with what ships: the daily check, what it sends, and how to switch it off.
- [ ] **Step 3: The Version & updates guide.** In `release_notes/help.md`, say in plain words that once a day the store asks morpheus.direct whether a new version is out, and what each kind of store does to take it. Then run `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.release_notes`. Expected: OK.
- [ ] **Step 4: Run every gate in Global Constraints**, plus `DATABASE_URL='sqlite:///:memory:' python manage.py test core plugins.installed.admin_dashboard plugins.installed.release_notes`. Expected: all green.
- [ ] **Step 5: Release.** Run `python manage.py release --minor "Every Morpheus install hears about new versions from morpheus.direct" -m "…" --commit`. Push the branch and open the PR. Merge only on the owner's explicit "yes" for this PR, then queue Croatia.
- [ ] **Step 6: Live check.**
  - In each store's web container, run `python manage.py shell -c "from core.updates import refresh_update_status as r; s=r(); print(s['source'], s['available'], s.get('latest'))"`. Expected: `manifest no v<this release or the previous one>`.
  - In a laptop clone at the previous tag, run `python manage.py morph_check_updates`. Expected: it names the newest release and the git path.
- [ ] **Step 7: Site.** With the owner's yes, change morpheus.direct's "not yet" item to say that stores hear about new versions, and push morpheus-web.

---

## Part R3 — Morpheus minor: Update now on Coolify

One branch and one PR (`feat/update-coolify`), one `release --minor`, after R2 is live.

### Task 10: One signed-push helper for the store and the guard

**Files:**
- Create: `core/deploy_hook.py`
- Modify: `scripts/deploy_guard.py:186-229` (remove `sign`, `queued` and the body building; import them)
- Create: `core/tests/test_deploy_hook.py`

**Interfaces:**
- Produces, in `core/deploy_hook.py` (stdlib imports only):
  - `REPOSITORY = 'magnetoid/Morpheus'`;
  - `sign(secret: str, body: bytes) -> str` returns `'sha256=' + hmac sha256 hex`;
  - `push_event(commit: str, branch: str, repository: str = REPOSITORY) -> bytes` returns `json.dumps({'ref': f'refs/heads/{branch}', 'after': commit, 'repository': {'full_name': repository}, 'commits': []}).encode()`;
  - `push_headers(secret: str, body: bytes, user_agent: str) -> dict[str, str]` returns `Content-Type`, `X-GitHub-Event: push`, `X-Hub-Signature-256` and `User-Agent`;
  - `queued(text: str) -> bool`, moved unchanged from deploy_guard.
- `deploy_guard.deploy_commit(hook, repository, branch, secret, commit, post=http_post)`:
  - keeps its signature;
  - builds with `push_event` and `push_headers(…, 'morpheus-deploy-guard')`;
  - the script inserts `str(ROOT)` at the front of `sys.path` before `from core.deploy_hook import push_event, push_headers, queued, sign`.

- [ ] **Step 1: Write the failing tests:**
  - `test_guard_and_store_share_one_signer`: load the script the way `test_deploy_guard.py` does → `guard.sign is core.deploy_hook.sign`.
  - `test_push_event_names_the_commit_branch_and_repository`: `json.loads(push_event('a'*40, 'main')) == {'ref': 'refs/heads/main', 'after': 'a'*40, 'repository': {'full_name': 'magnetoid/Morpheus'}, 'commits': []}`.
  - `test_deploy_hook_imports_no_django`: in a subprocess, run `python -I -c "import sys; sys.path.insert(0, '<repo root>'); import core.deploy_hook; print('django' in sys.modules)"` → it prints `False`.
- [ ] **Step 2: Run and see them fail.** Run `DATABASE_URL='sqlite:///:memory:' python manage.py test core.tests.test_deploy_hook`. Expected: ImportError.
- [ ] **Step 3: Implement** the module and the script change.
- [ ] **Step 4: Run the tests and see them pass.** Run `DATABASE_URL='sqlite:///:memory:' python manage.py test core.tests.test_deploy_hook core.tests.test_deploy_guard`, and also `python scripts/deploy_guard.py --help` from the repo root with the system `python3`. Expected: OK, and the help prints.
- [ ] **Step 5: Commit.** Run `git add core/deploy_hook.py scripts/deploy_guard.py core/tests/test_deploy_hook.py`, then `git commit -m "refactor: one signed-push helper for the deploy guard and the store"`.

### Task 11: Update now on Coolify

**Files:**
- Modify: `morph/settings.py` (three env vars)
- Modify: `core/updates.py` (`deploy_hook_ready`, `update_path`, `request_deploy`)
- Modify: `plugins/installed/admin_dashboard/views_split/system.py` (`updates_deploy`)
- Modify: `plugins/installed/admin_dashboard/urls.py:255-261`
- Create: `plugins/installed/admin_dashboard/templates/admin_dashboard/updates_deploy_confirm.html`
- Modify: `_updater_card.html`
- Create: `plugins/installed/admin_dashboard/tests/test_updates_deploy.py`

**Interfaces:**
- Consumes: Task 10's `push_event`, `push_headers` and `queued`; Task 5's `configured_source()`, `user_agent()`, `MORPHEUS_UPDATE_CHANNEL_URL`, plus the existing `is_newer()` and `_ssl_context()` from `core/update_sources.py` and `core_version()` from `core/versioning.py`.
- Produces, in settings (env only):
  - `MORPHEUS_DEPLOY_HOOK_URL = config('MORPHEUS_DEPLOY_HOOK_URL', default='')`;
  - `MORPHEUS_DEPLOY_HOOK_SECRET = config('MORPHEUS_DEPLOY_HOOK_SECRET', default='')`;
  - `MORPHEUS_DEPLOY_HOOK_BRANCH = config('MORPHEUS_DEPLOY_HOOK_BRANCH', default='main')`.
- Produces, in `core/updates.py`:
  - `deploy_hook_ready() -> bool`: the URL starts with `https://` and the secret is set.
  - `update_path() -> str`: `'git'` when `can_self_update()`. Otherwise `'coolify'` when `deploy_hook_ready()` and `MORPHEUS_UPDATE_MANIFEST_URL == MORPHEUS_UPDATE_CHANNEL_URL`; a fork on its own channel never gets the button. Otherwise `'manual'`.
  - `request_deploy(*, user) -> dict`. Returns `{'ok': bool, 'status': str, 'from': str, 'to': str, 'commit': str, 'reason': str}`, where `status` is one of `queued`, `not_queued`, `already_sent`, `no_update`, `no_commit`, `unknown` and `not_configured`. It runs in order:
    1. Not `'coolify'` → `not_configured`.
    2. Read a fresh `configured_source().latest()`, never the cache. `None` → `unknown`.
    3. `not is_newer(release.version, core_version())` → `no_update`.
    4. No `release.commit` → `no_commit`.
    5. `cache.add(f'morpheus:update_deploy:{release.commit}', user.pk, 600)` is False → `already_sent`.
    6. POST `push_event(release.commit, settings.MORPHEUS_DEPLOY_HOOK_BRANCH)` with `push_headers(secret, body, user_agent())` to the hook URL. Use `urllib`, a 30 s timeout and `_ssl_context()`.
    7. `ok = 200 <= code < 300 and queued(text)`. When not ok, delete the cache key so a retry can send.
    8. `core.audit.services.record(event_type='updates.deploy_requested', actor=user, target=release.version, metadata={'from', 'to', 'commit', 'queued': ok, 'http': code})`.
- Produces, in `system.py`, `updates_deploy(request)`:
  - `@staff_member_required` and `@require_capability('system.write')`;
  - `raise Http404` unless `request.user.is_superuser and update_path() == 'coolify'`;
  - GET renders the confirm page with `platform_update_status(fetch=False)` and `running_release()`;
  - POST reads nothing from `request.POST`, calls `request_deploy(user=request.user)`, adds a message per status, and redirects to `admin_dashboard:updates`.
  - The `not_queued` message names the likely cause: "Coolify did not queue a deployment. That happens when its application does not build magnetoid/Morpheus (a fork) or the webhook secret is wrong. Update with the commands on this page instead." A fork with the hook set lands here, because Coolify matches the push to an application by repository name.
- URL: `path('updates/deploy/', views.updates_deploy, name='updates_deploy')`, plus the `views` re-export the other update views use.

The confirm page says, in plain words:
- the current and the new version, the notes and the "Has upgrade steps" flag with its link;
- "The database is backed up before it changes";
- a link to Version & updates → Backups;
- "If the new version does not come up, put the previous one back in Coolify (the application's Deployments → Rollback)";
- "This store has no automatic rollback".

It ends with one POST form ("Update to vX.Y.Z"). The card, when `path == 'coolify'` and `available == 'yes'`:
- for a superuser: a link "Update now" to `admin_dashboard:updates_deploy`;
- for everyone else: "A superuser can update this store."

- [ ] **Step 1: Write the failing tests** in `test_updates_deploy.py`. Use `override_settings` for the hook vars and the channel URL. Patch `core.updates.can_self_update` → False, `configured_source` → a source whose `latest()` returns a release with commit `'b'*40`, and `core.updates.urllib.request.urlopen` to capture requests.
  - **Boundaries:**
    - `test_anonymous_is_sent_to_sign_in`: GET → 302 to the login URL;
    - `test_staff_who_is_not_superuser_gets_404`: GET → 404, POST → 404, `urlopen.assert_not_called()`;
    - `test_superuser_sees_the_confirm_page`: GET → 200 and contains `v9.0.0`.
  - **When the button exists:**
    - `test_not_offered_without_url_or_secret`: GET → 404, and the card has no `updates_deploy` link;
    - `test_not_offered_on_another_channel`: `MORPHEUS_UPDATE_MANIFEST_URL='https://example.com/x.json'` → 404;
    - `test_a_git_checkout_keeps_the_fast_forward`: `can_self_update` → True → 404 here, and `update_path() == 'git'`.
  - **What it sends:**
    - `test_post_sends_only_the_manifest_commit`: POST `{'commit': 'f'*40, 'branch': 'evil'}` → one request whose JSON has `after == 'b'*40` and `ref == 'refs/heads/main'`, and whose `X-Hub-Signature-256 == sign(secret, body)`;
    - `test_refuses_a_release_that_is_not_newer`: `MORPHEUS_VERSION` equals the release → no request, and the message says it is up to date;
    - `test_a_second_press_is_not_sent_twice`: two POSTs → one request, and the second message says it was already sent;
    - `test_an_answer_that_did_not_queue_is_reported_and_can_be_retried`: the hook answers `{"message": "No resources found."}` → `status == 'not_queued'`, the cache key is gone, and a second POST sends again.
  - **Records:**
    - `test_the_audit_row_names_the_person_and_both_versions`: an `AuditEvent` with `event_type == 'updates.deploy_requested'`, the superuser as actor, and `metadata['from'] == 'v1.0.0'` and `metadata['to'] == 'v9.0.0'`;
    - `test_templates_compile`: the confirm page and the card.
- [ ] **Step 2: Run and see them fail.** Run `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.admin_dashboard.tests.test_updates_deploy`. Expected: FAIL (no URL).
- [ ] **Step 3: Implement** the settings, `deploy_hook_ready`, the `update_path` change, `request_deploy`, the view, URL, template and card.
- [ ] **Step 4: Run the tests and see them pass.** Run the same, plus `core.tests.test_update_status_channel plugins.installed.admin_dashboard.tests.test_updater_card_channel plugins.installed.admin_dashboard.tests.test_disable_guards`. Expected: OK.
- [ ] **Step 5: Commit.** Use explicit paths for the files above, then `git commit -m "feat(updates): Update now on Coolify sends the release's commit to the store's own deploy hook"`.

### Task 12: Linda cannot reach it; docs, release and staging check

**Files:**
- Modify: `core/tests/test_deploy_hook.py`
- Modify: `docs/UPDATING.md`, `plugins/installed/release_notes/help.md`, `CLAUDE.md` and `README.md`
- Release files: `morph/settings.py` (version) and `docs/RELEASE_NOTES.md`

- [ ] **Step 1: Write the failing test.** Add `test_no_agent_tool_can_send_a_deploy`. For every tool in `core.agents.registry.agent_registry.platform_tools()`, read `inspect.getsource(inspect.getmodule(tool.handler))` and assert it contains neither `request_deploy` nor `deploy_hook`.

  Also add `test_updates_apply_on_a_coolify_install_sends_nothing`. With the hook configured and `can_self_update` → False, calling the `updates.apply` handler with `confirmed=True, hard_gate_ack='YES', echo='platform update'` returns `status == 'unavailable'` and `urlopen.assert_not_called()`.

  Also add `test_updates_apply_keeps_its_gate`: `get_tool('updates.apply')` has `scopes == ['system.write']` and `requires_approval is True`.

  Run `DATABASE_URL='sqlite:///:memory:' python manage.py test core.tests.test_deploy_hook`. Expected: PASS once Task 11 is in, since nothing reaches it. Treat a failure as a real leak to fix.
- [ ] **Step 2: Docs.**
  - **`docs/UPDATING.md` — "Update now on Coolify":**
    - the three env vars;
    - where Coolify shows the manual GitHub webhook URL and its secret;
    - that the store sends only the channel's commit;
    - that it has no automatic rollback, and how to roll back in Coolify;
    - never Redeploy after a rollback.
  - **The `release_notes/help.md` guide:** the button, who can press it, what happens.
  - **`CLAUDE.md`:** one convention paragraph, "a store takes a release only from the signed channel (vX.Y.0)":
    - URL, keys and hook are env only;
    - status reads the manifest first and page loads read the cache;
    - the hook sends only the manifest's newer commit;
    - Linda has no tool for it, because a deploy is a superuser's press, and the owner kept `updates.apply` as it was;
    - name the guarding tests.
  - **`README.md`:** what a Coolify install gets.
- [ ] **Step 3: Run every gate in Global Constraints**, plus `DATABASE_URL='sqlite:///:memory:' python manage.py test core plugins.installed.admin_dashboard plugins.installed.release_notes`. Expected: all green.
- [ ] **Step 4: Release.** Run `python manage.py release --minor "Update now on Coolify, from the signed channel" -m "…" --commit`, then open the PR. Merge only on the owner's explicit yes, then queue Croatia.
- [ ] **Step 5: Staging check.** This is the owner's decision at this point: it needs a Coolify application that is not a live store.
  1. Build `magnetoid/Morpheus` at the previous release tag.
  2. Set the three hook env vars from that application's manual webhook.
  3. As a superuser, press Update now.
  4. Expected: Coolify queues a deployment of the release commit, and after the swap Version & updates says "Up to date" on the new version.
  5. Delete the staging application afterwards.
- [ ] **Step 6: Site.** With the owner's yes, update morpheus.direct to say a Coolify install updates with one button, and push morpheus-web.
