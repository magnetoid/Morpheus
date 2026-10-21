# Safe deploys, release 4: a store that does not come up goes back — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a new release leaves a store down, CI puts that store back on the previous release by itself, and the store emails its operators and says so on Settings → Version & updates.

**Architecture:**
- **The guard.** When `deploy-smoke` fails, a stdlib script, `scripts/deploy_guard.py`, checks each store three times. A store that is down every time is sent a signed GitHub push event, through that store's own Coolify manual webhook, naming the previous release tag's commit.
- **The store.** It learns it was rolled back from its own records. `safe_migrate` now records each deploy *before* migrating, and a boot older than the newest record notes `rolled_back_from`, emails the operators once, and shows it on the page.

**Tech Stack:** Python 3.12 stdlib for the guard (GitHub Actions' system Python, no requirements installed); Django 6.1 in the app; GitHub Actions; Coolify 4.4.6.

**Spec:** `docs/superpowers/specs/2026-10-19-safe-deploys-design.md`, part 3 ("The code goes back automatically"), the rollback email, and "To verify" item 1.

## Global Constraints

- **From the spec:** "When `deploy-smoke` finds a store that never reports the new version healthy by its deadline, it runs `scripts/deploy_guard.py rollback <store>`: finds the store's last good commit: the newest release tag older than the failed one; … waits for `/readyz` to report that version."
- **From the spec:** "The email comes from the store itself. On boot the web process compares its version with the highest one in `DeployEvent`; lower means it was rolled back. It records that once, shows it on the Version & updates page, and emails `ERROR_ALERT_EMAILS` (else the superusers, else the store contact): which version failed, which one runs now, and which pre-deploy backup holds the data from just before the failed migration."
- **From the spec:** "Part 3 needs a deploy platform's API; `docs/UPDATING.md` documents the guard script and the contract it expects (deploy a commit, read `/readyz`), with Coolify as the example."
- **Owner's decision (2026-10-21):** roll back through each store's own Coolify deploy webhook (manual GitHub webhook secret), never a Coolify API token. The Coolify team holds 34 applications, clients' included.
- **Owner's decisions (2026-10-19):** our four stores first; roll code back automatically and restore data by hand; guard the current Coolify setup.
- **From release 2:** a migration this release adds must pass `manage.py release`'s gate. A new column gets `db_default`.
- **From the release 1 review:** record the deploy attempt, with its backup, before migrating, or a crashed migration leaves nothing for rollback detection.
- **Process:** one release, v0.121.0, cut with `manage.py release --minor` while `MORPHEUS_EXTRA_APPS` is set. A push to `main` deploys all four stores: push once, at the end, after the whole-branch review.
- **Tests:** `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test …`; the full suite adds `MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress'`.
- **Commits:** each ends with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`. One heredoc per shell call. Never bypass the pre-commit hook.
- **Copy:** plain words; the assistant is called Linda; the app's help guide stays inside 60–400 words with no `app_help.JARGON`.

### Verified before writing this plan (Coolify 4.4.6 source and the live API, 2026-10-21)

- **API deploys follow the pin.** `queue_application_deployment` resolves `$commit ?: ($application->git_commit_sha ?: 'HEAD')`. So an API deploy, or the Redeploy button, builds the app's `git_commit_sha`, which is `HEAD` (main) on all four store apps.
- **Pushes ignore it.** A GitHub push webhook queues `commit: webhookCommitSha($payload, 'after')`. A push deploys its own commit, whatever the pin says. The spec's "To verify" item 1 is therefore half false: a pin does not stop the next push, and Release 4 needs no pin at all.
- **The manual webhook.** `/webhooks/source/github/events/manual` (POST) finds every application on the payload's `repository.full_name` and `ref` branch, whatever its source type. For each one it checks `X-Hub-Signature-256` against that application's own `manual_webhook_secret_github`, then queues `commit: after`. A queued deploy answers `{"status": "success", "message": "Deployment queued.", …}`; a bad signature answers with a failure entry.
- **What CI holds.** One store's secret can deploy commits of this repository to that one store, which is what pushing to main can already do. All four store apps have a manual webhook secret set.
- **The stores are distinct apps.** They are `dockercompose`, `git_repository` `magnetoid/morpheus`, `git_branch` `main`. `montenegro-experience-hub`, another app, carries the same domain as the Montenegro store, so nothing may match stores by domain alone.

### Decisions this plan makes where the spec is silent or cannot hold

1. **No pin and no unpin step.** A push deploys its own commit, so a fix reaches every store with no help. The catch: after a rollback, Redeploy in Coolify would build main, the failed commit, so the email, the card and the runbook say not to do that.
2. **Down, not late.** A store still healthy on an older version is queued or missed its webhook, and it is left alone. One that answers 503 for a few seconds is mid-swap; each store is checked three times, 20 s apart, before it counts as down.
3. **Webhooks first, then one wait.** All the down stores get their webhook first, then the guard waits for all of them together (30 minutes), because Coolify builds them one after another.
4. **The rollback stays red.** The guard exits 1 whenever it rolled a store back, so the run is red and GitHub emails the pusher. That is the only signal when the release rolled back to predates v0.121.0 and cannot email.
5. **Recording before migrating.** It falls back to after migrating when it cannot write yet: a fresh database, or a deploy that migrates `DeployEvent` itself (this release's own). The marker file says which row this container wrote, so a crash-loop restart adds no second row.
6. **The comparison.** It is by version (`vX.Y.Z`) against the newest row, by time. A restored database whose newest row is newer than the running code reads as a rollback too, which, as far as the data goes, it is.
7. **What the guard reads.** Its configuration is one JSON secret, `MORPHEUS_DEPLOY_HOOKS`, so the public repository names no infrastructure. Task 4 builds it from the Coolify API, with the API token used only on this machine, and never prints it.

## Review Focus

1. **A store mid-swap at the deadline** (503 for a few seconds, then up) must not be rolled back. Pinned by `test_a_brief_503_is_not_down` (Task 3).
2. **A store still on the previous version** (its build queued behind the others, or its webhook missed) must not be rolled back. Pinned by `test_a_store_still_on_the_old_version_is_left_alone` (Task 3).
3. **The previous release among odd tags.** It is the newest `vX.Y.Z` tag older than the one being deployed, whatever order git lists them in and whatever other tags exist (`morpheus-known-good`, `v1.0.0-rc1`). Pinned by `test_the_previous_release_ignores_other_tags_and_order` (Task 3).
4. **A restarted rolled-back container** must not email again, and the next normal deploy must not read as a rollback. Pinned by `test_the_operators_hear_once` and `test_a_newer_version_is_not_a_rollback` (Task 2).
5. **An unconfigured guard** must fail loudly, not pass quietly. Pinned by `test_without_its_secret_the_guard_says_rollback_is_off` (Task 3).

---

## File structure

| File | Responsibility |
|---|---|
| `scripts/deploy_guard.py` (new) | Decide which stores are down, and send each its signed push for the previous release |
| `core/deploys.py` | `version_key`, `is_older`, `failed_backup_name`, `notify_rollback`; `record_deploy` records before migrating and notes `rolled_back_from`; `running_release` reports it |
| `core/management/commands/safe_migrate.py` | Back up, record the attempt, migrate, then clear the marker; email once on a rollback |
| `core/models.py` + `core/migrations/0025_deployevent_rolled_back_from.py` (new) | `DeployEvent.rolled_back_from` |
| `plugins/installed/admin_dashboard/templates/admin_dashboard/_updater_card.html` | "Put back" notice on Version & updates |
| `.github/workflows/deploy-smoke.yml` | Checkout with tags; run the guard when the smoke fails |
| `CLAUDE.md`, `docs/UPDATING.md`, `docs/OPERATIONS_RUNBOOK.md`, `plugins/installed/release_notes/help.md` | The convention, the contract, the procedure, the help |

---

### Task 1: Verify a signed push rolls a store back (live, Irving)

This changes no code. It proves the mechanism before anything depends on it, on Irving, the beta store with "hidden until launch" on. That means two builds of roughly 5 minutes each, and a few seconds of 503 at each swap. v0.120.0 and v0.120.1 differ only in Pillow and certifi.

**Files:**
- Create: `<scratchpad>/r4_webhook_check.py` (not in the repo)

**Interfaces:**
- Produces: the confirmed payload shape and response for Task 3: `ref`, `after`, `repository.full_name` = `magnetoid/morpheus`, and the success entry's `status` = `success`. If anything differs, ledger a ruling and carry it into Task 3's constants.

- [ ] **Step 1: Write the check**

```python
"""Safe deploys release 4, Task 1: does a signed manual push deploy a commit to one store?
Reads Irving's webhook secret with the Coolify API token (this machine only); the
webhook call itself uses only that secret, as CI will. Prints no secret."""
import hashlib, hmac, json, subprocess, sys, time, urllib.request

COOLIFY = 'https://coo.imbamarketing.com'
UUID = 'j7xoogxjqgyakdsjw37eneuh'  # Irving Survival
STORE = 'https://beta.irvingsurvival.com'
HOOK = f'{COOLIFY}/webhooks/source/github/events/manual'
token = subprocess.run(['security', 'find-generic-password', '-a', 'api', '-s', 'coo.imbamarketing.com', '-w'],
                       capture_output=True, text=True, check=True).stdout.strip()


def api(path):
    req = urllib.request.Request(COOLIFY + path, headers={'Authorization': f'Bearer {token}'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def push(secret, commit):
    body = json.dumps({'ref': 'refs/heads/main', 'after': commit,
                       'repository': {'full_name': 'magnetoid/morpheus'}, 'commits': []}).encode()
    sig = 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(HOOK, data=body, method='POST', headers={
        'Content-Type': 'application/json', 'X-GitHub-Event': 'push', 'X-Hub-Signature-256': sig,
        'User-Agent': 'morpheus-deploy-guard'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def queued():
    rows = api('/api/v1/deployments')
    rows = rows if isinstance(rows, list) else rows.get('data', [])
    return [(r.get('application_name'), r.get('status'), (r.get('commit') or '')[:8]) for r in rows]


def version():
    try:
        with urllib.request.urlopen(f'{STORE}/readyz?cb={time.time()}', timeout=15) as r:
            return json.load(r).get('version')
    except Exception:
        return None


def wait(target, minutes=25):
    end = time.time() + minutes * 60
    while time.time() < end:
        if version() == target:
            return True
        time.sleep(20)
    return False


secret = api(f'/api/v1/applications/{UUID}')['manual_webhook_secret_github']
old = subprocess.run(['git', 'rev-list', '-n', '1', 'v0.120.0'], capture_output=True, text=True, check=True).stdout.strip()
now = subprocess.run(['git', 'rev-parse', 'origin/main'], capture_output=True, text=True, check=True).stdout.strip()
print('R4 Irving runs', version(), '| old', old[:8], '| main', now[:8])
status, text = push('wrong-secret', old)
print('R4 bad signature:', status, text[:200], '| queue:', queued())
start = time.time()
status, text = push(secret, old)
print('R4 signed push for v0.120.0:', status, text[:300])
print('R4 queue right after:', queued())
print('R4 Irving on v0.120.0:', wait('v0.120.0'), f'after {time.time() - start:.0f}s')
start = time.time()
status, text = push(secret, now)
print('R4 signed push for main:', status, text[:300])
print('R4 Irving back on main:', wait('v0.120.1'), f'after {time.time() - start:.0f}s')
```

- [ ] **Step 2: Run it**

Run: `cd /Users/magnetoid/coding/morph && git fetch -q --tags origin && .venv/bin/python <scratchpad>/r4_webhook_check.py`

Expected:
- **Bad signature:** a failure answer, and no Irving deployment in the queue.
- **Signed push for v0.120.0:** a `success` entry naming Irving only. The queue shows Irving with the old commit and no other store app.
- **Irving on v0.120.0:** True.
- **Signed push for main:** a `success` entry, then Irving back on main (v0.120.1): True.

If the answer shape or the repository name differs (for example, the success entry is nested), ledger a ruling, adjust Task 3's `queued()` and the payload, and continue. If a signed push queues nothing, stop: the design depends on it.

- [ ] **Step 3: Ledger the result**

Append the observed answers, queue lines and timings to the ledger. There is no commit: this task changes nothing in the repository.

---

### Task 2: The store notices it was put back

**Files:**
- Modify: `core/models.py` (`DeployEvent`), create `core/migrations/0025_deployevent_rolled_back_from.py` (via `makemigrations`)
- Modify: `core/deploys.py`, `core/management/commands/safe_migrate.py`
- Modify: `plugins/installed/admin_dashboard/templates/admin_dashboard/_updater_card.html`
- Modify: `core/tests/test_deploy_record.py` (one assertion, see Step 1)
- Test: `core/tests/test_rollback_notice.py` (new)

**Interfaces:**
- Consumes:
  - `core.errors.alerts.send_alert(subject, body) -> bool` (fail-soft);
  - `core.utils.site.store_name()` and `site_base_url()`;
  - `deploys.read_handoff`, `write_handoff` and `clear_handoff`.
- Produces:
  - In `core.deploys`:
    - `version_key(text) -> tuple[int, int, int] | None` and `is_older(version, than) -> bool`;
    - `failed_backup_name(version) -> str` and `notify_rollback(event) -> bool`;
    - `record_deploy()`, which keeps the marker and adds `recorded`, `version` and `commit` to it.
  - `DeployEvent.rolled_back_from`.
  - `running_release()['rolled_back_from']` and `['failed_backup']`.

- [ ] **Step 1: Write the failing tests**

`core/tests/test_rollback_notice.py`:

```python
"""A store put back on an older release says so, once (safe deploys, part 3)."""

from __future__ import annotations

import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase, override_settings

from core import deploys
from core.management.commands.morph_backup import Command as BackupCommand
from core.management.commands.safe_migrate import Command as SafeMigrate
from core.models import DeployEvent
from core.tests.test_safe_migrate import _DeployEnvMixin, _fake_dump

RUNNING = 'v0.121.0'


class VersionTests(SimpleTestCase):
    def test_versions_compare_as_numbers(self):
        self.assertTrue(deploys.is_older('v0.9.9', 'v0.10.0'))
        self.assertTrue(deploys.is_older('v0.120.1', 'v0.121.0'))
        self.assertFalse(deploys.is_older('v0.121.0', 'v0.121.0'))
        self.assertFalse(deploys.is_older('v0.122.0', 'v0.121.0'))

    def test_an_unparsable_version_is_never_older(self):
        self.assertFalse(deploys.is_older('dev', 'v0.121.0'))
        self.assertFalse(deploys.is_older('v0.120.0', 'nightly'))
        self.assertIsNone(deploys.version_key('v1.0.0-rc1'))


@override_settings(MORPHEUS_VERSION=RUNNING)
class RecordTests(_DeployEnvMixin, TestCase):
    def test_an_older_version_after_a_newer_deploy_is_a_rollback(self):
        DeployEvent.objects.create(version='v0.122.0', commit='b' * 40)
        event, created = deploys.record_deploy()
        self.assertTrue(created)
        self.assertEqual(event.rolled_back_from, 'v0.122.0')

    def test_a_newer_version_is_not_a_rollback(self):
        DeployEvent.objects.create(version='v0.120.1', commit='b' * 40)
        event, _ = deploys.record_deploy()
        self.assertEqual(event.rolled_back_from, '')

    def test_the_marker_names_the_row_this_container_wrote(self):
        event, _ = deploys.record_deploy()
        marker = deploys.read_handoff()
        self.assertEqual((marker['recorded'], marker['version']), (event.pk, RUNNING))

    def test_the_failed_release_s_backup_is_found_by_its_version(self):
        DeployEvent.objects.create(version='v0.122.0', commit='b' * 40, backup='/app/backups/pre-deploy/x.tar.gz')
        self.assertEqual(deploys.failed_backup_name('v0.122.0'), 'x.tar.gz')
        self.assertEqual(deploys.failed_backup_name('v0.130.0'), '')


@override_settings(MORPHEUS_VERSION=RUNNING)
class SafeMigrateOrderTests(_DeployEnvMixin, TestCase):
    def _run(self, migrate=None, record=None):
        out = io.StringIO()
        patches = [
            patch.object(BackupCommand, '_dump_database', _fake_dump),
            patch.object(SafeMigrate, '_migrate', side_effect=migrate),
            patch('core.errors.alerts.send_alert', return_value=True),
        ]
        if record is not None:
            patches.append(patch('core.deploys.record_deploy', side_effect=record))
        mocks = [p.start() for p in patches]
        try:
            call_command('safe_migrate', stdout=out)
        finally:
            for p in patches:
                p.stop()
        return out.getvalue(), mocks[2]

    def test_the_attempt_is_recorded_before_migrating(self):
        self.pend()

        def boom():
            raise RuntimeError('migrate failed')

        with self.assertRaises(RuntimeError):
            self._run(migrate=boom)
        event = DeployEvent.objects.get()
        self.assertEqual(event.version, RUNNING)
        self.assertTrue(event.backup)  # the copy from just before it, for the rollback notice

    def test_a_restart_after_a_crashed_migration_adds_no_row(self):
        self.pend()

        def boom():
            raise RuntimeError('migrate failed')

        with self.assertRaises(RuntimeError):
            self._run(migrate=boom)
        self._run()
        self.assertEqual(DeployEvent.objects.count(), 1)

    def test_a_record_that_cannot_be_written_yet_is_written_after_migrating(self):
        calls = []

        def record():
            calls.append('record')
            if len(calls) == 1:
                raise DatabaseError('no such column: rolled_back_from')
            return DeployEvent.objects.create(version=RUNNING, commit='a' * 40), True

        def migrate():
            calls.append('migrate')

        self._run(migrate=migrate, record=record)
        self.assertEqual(calls, ['record', 'migrate', 'record'])

    def test_the_operators_hear_once(self):
        DeployEvent.objects.create(version='v0.122.0', commit='b' * 40, backup='/app/backups/pre-deploy/x.tar.gz')
        out, alert = self._run()
        alert.assert_called_once()
        subject, body = alert.call_args.args
        self.assertIn('v0.122.0', subject)
        self.assertIn(RUNNING, subject)
        self.assertIn('x.tar.gz', body)
        self.assertIn('do not redeploy', body)
        self.assertIn('after v0.122.0', out)
        _, alert_again = self._run()  # a restart of the rolled-back container
        alert_again.assert_not_called()


@override_settings(MORPHEUS_VERSION=RUNNING)
class RunningReleaseTests(_DeployEnvMixin, TestCase):
    def test_the_page_names_the_rollback_and_the_failed_backup(self):
        DeployEvent.objects.create(version='v0.122.0', commit='b' * 40, backup='/app/backups/pre-deploy/x.tar.gz')
        deploys.record_deploy()
        running = deploys.running_release()
        self.assertEqual((running['rolled_back_from'], running['failed_backup']), ('v0.122.0', 'x.tar.gz'))

    def test_the_card_says_the_store_was_put_back(self):
        DeployEvent.objects.create(version='v0.122.0', commit='b' * 40)
        deploys.record_deploy()
        staff = get_user_model().objects.create_user(username='boss', email='b@x.io', password='pw', is_staff=True)
        self.client.force_login(staff)
        html = self.client.get('/dashboard/apps/release_notes/version/').content.decode()
        self.assertIn('data-testid="rolled-back"', html)
        self.assertIn('v0.122.0 did not come up', html)
```

In `core/tests/test_deploy_record.py`, `test_a_deploy_is_recorded_with_its_backup_and_migrations` ends with `self.assertIsNone(deploys.read_handoff())`. Under this task's contract, `record_deploy` keeps the marker and `safe_migrate` clears it after migrating. Change that line to:

```python
        self.assertEqual(deploys.read_handoff()['recorded'], event.pk)
```

- [ ] **Step 2: Run them to see them fail**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_rollback_notice core.tests.test_deploy_record`
Expected: ERROR or FAIL: `module 'core.deploys' has no attribute 'is_older'`, `DeployEvent() got unexpected keyword arguments: 'rolled_back_from'`, and the attempt not recorded when migrate fails.

- [ ] **Step 3: The field and its migration**

In `core/models.py`, `DeployEvent`, replace the class docstring and add the field after `migrations`:

```python
    """One deploy of this store, written by ``manage.py safe_migrate`` before it
    migrates (after, when the table itself is being migrated), so a crashed
    migration still leaves the attempt and its backup (core/deploys.py). A
    restart of the same deploy adds no row."""
```

```python
    # The newer version this boot replaced, when it is a rollback; '' otherwise.
    rolled_back_from = models.CharField(max_length=40, blank=True, default='', db_default='')
```

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py makemigrations core -n deployevent_rolled_back_from`
Expected: `core/migrations/0025_deployevent_rolled_back_from.py`, holding one `AddField` with `db_default=''`, which the release gate accepts.

- [ ] **Step 4: `core/deploys.py`**

Add `from pathlib import Path` is already there; add the helpers after `current_commit()`:

```python
_VERSION = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)$')


def version_key(text: str) -> tuple[int, int, int] | None:
    """``vX.Y.Z`` as numbers, for comparing releases; None for anything else."""
    match = _VERSION.match(str(text or '').strip())
    return tuple(int(part) for part in match.groups()) if match else None  # type: ignore[return-value]


def is_older(version: str, than: str) -> bool:
    a, b = version_key(version), version_key(than)
    return a is not None and b is not None and a < b
```

Replace `record_deploy()` with:

```python
def record_deploy():
    """Write this boot's DeployEvent from the marker. safe_migrate calls it before
    migrating, so a migration that crashes still leaves the attempt and its
    backup; the marker then names the row, and a restart of the same container
    adds nothing. safe_migrate clears the marker once migrating has worked.

    A boot that migrates nothing, on the version and commit of the newest record,
    is a restart of that deploy and writes nothing. A boot older than the newest
    record is a rollback: its row names the version it replaced
    (``rolled_back_from``). Returns ``(event, created)``.
    """
    from django.conf import settings

    from core.models import DeployEvent

    marker = read_handoff() or {}
    version, commit = str(settings.MORPHEUS_VERSION), current_commit()
    if marker.get('recorded') and (marker.get('version'), marker.get('commit')) == (version, commit):
        event = DeployEvent.objects.filter(pk=marker['recorded']).first()
        if event is not None:
            return event, False
    migrations = [str(name) for name in marker.get('migrations') or []]
    newest = DeployEvent.objects.first()
    if newest and (newest.version, newest.commit) == (version, commit) and not migrations:
        return newest, False
    event = DeployEvent.objects.create(
        version=version,
        commit=commit,
        backup=str(marker.get('backup') or ''),
        migrations=migrations,
        rolled_back_from=newest.version if newest and is_older(version, newest.version) else '',
    )
    write_handoff({**marker, 'recorded': event.pk, 'version': version, 'commit': commit})
    return event, True


def failed_backup_name(version: str) -> str:
    """The pre-deploy backup taken before ``version`` migrated; '' when it made
    no database changes."""
    from core.models import DeployEvent

    path = (
        DeployEvent.objects.filter(version=version)
        .exclude(backup='')
        .values_list('backup', flat=True)
        .first()
    )
    return Path(path).name if path else ''


def notify_rollback(event) -> bool:
    """Email the operators that this store went back to an older release. Called
    once, by the boot that recorded the rollback."""
    from core.errors.alerts import send_alert
    from core.utils.site import site_base_url, store_name

    failed, name = event.rolled_back_from, store_name() or 'The store'
    backup = failed_backup_name(failed)
    if backup:
        data = (
            f'If {failed} changed the database before it failed, the copy from just before it is '
            f'{backup}. Restore it from Settings → Version & updates → Backups only if you need '
            'the data as it was.'
        )
    else:
        data = f'{failed} made no database changes, so there is nothing to restore.'
    body = '\n\n'.join(
        [
            f'{failed} did not come up on {name}, so the store was put back on {event.version} at '
            f'{event.deployed_at:%Y-%m-%d %H:%M} UTC. Shoppers see the store as it was before {failed}.',
            f'Nothing was restored: the data is as {failed} left it. {data}',
            'The next release deploys as usual. Until then, do not redeploy the store from '
            f'Coolify: that would deploy {failed} again.',
            f'Version & updates: {site_base_url().rstrip("/")}/dashboard/updates/',
        ]
    )
    return send_alert(f'{name}: {failed} did not come up, so the store is back on {event.version}', body)
```

In `running_release()`, after the `event` lookup, add the two keys to the returned dict:

```python
        'rolled_back_from': event.rolled_back_from if event else '',
        'failed_backup': failed_backup_name(event.rolled_back_from) if event and event.rolled_back_from else '',
```

- [ ] **Step 5: `safe_migrate` records first and clears the marker last**

In `core/management/commands/safe_migrate.py`, add `from django.db import transaction` to the imports and replace `handle` and `_record`:

```python
    def handle(self, *args, **options):
        self._back_up_first()
        # Before migrating, so a migration that crashes still leaves the attempt
        # and its backup on record for the rollback notice.
        recorded = self._record(final=False)
        self._migrate()
        if not recorded:
            self._record(final=True)
        deploys.clear_handoff()

    def _record(self, *, final: bool) -> bool:
        """Record this deploy; False when it cannot be written yet. Before
        migrating, the table or one of its columns can still be missing (a new
        database, or a deploy that migrates DeployEvent itself): then it is
        written after migrating. The record never keeps the store down."""
        try:
            with transaction.atomic():
                event, created = deploys.record_deploy()
        except Exception:
            if not final:
                return False
            logger.exception('safe_migrate: could not record this deploy')
            self.stderr.write('[safe_migrate] Could not record this deploy; carrying on.')
            return True
        if not created:
            self.stdout.write(f'[safe_migrate] {event.version} restarted; already recorded.')
            return True
        commit = f' ({event.commit[:7]})' if event.commit else ''
        count = f', {len(event.migrations)} migrations' if event.migrations else ''
        self.stdout.write(f'[safe_migrate] Recorded {event.version}{commit}{count}.')
        if event.rolled_back_from:
            told = deploys.notify_rollback(event)
            self.stdout.write(
                f'[safe_migrate] Back on {event.version} after {event.rolled_back_from}: '
                + ('told the operators.' if told else 'could not email the operators.')
            )
        return True
```

- [ ] **Step 6: The card**

In `_updater_card.html`, directly after the `data-testid="predeploy-backup"` block's closing `</div>`:

```django
  {% if running.rolled_back_from %}
  <div class="mt-3 pt-3 border-t border-[color:var(--border)] text-sm" data-testid="rolled-back">
    <span class="pill pill-warn">Put back</span>
    {{ running.rolled_back_from }} did not come up, so this store runs {{ running.version }} again{% if running.deployed_at %} since {{ running.deployed_at|date:"j M Y, H:i" }}{% endif %}.
    {% if running.failed_backup %}The data from just before {{ running.rolled_back_from }} changed the database is in {{ running.failed_backup }}.{% endif %}
    Do not redeploy the store from Coolify until a fix is released: that would deploy {{ running.rolled_back_from }} again.
  </div>
  {% endif %}
```

- [ ] **Step 7: Run the tests to see them pass**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_rollback_notice core.tests.test_deploy_record core.tests.test_safe_migrate core.tests.test_running_release plugins.installed.release_notes core.tests.test_migration_gate`
Expected: `OK`.

- [ ] **Step 8: Lint and commit**

Run: `ruff check core plugins/installed/admin_dashboard && ruff format core && .venv/bin/python manage.py makemigrations --check --dry-run`
Expected: `All checks passed!` and `No changes detected`.

```bash
git add core/models.py core/migrations/0025_deployevent_rolled_back_from.py core/deploys.py core/management/commands/safe_migrate.py core/tests/test_rollback_notice.py core/tests/test_deploy_record.py plugins/installed/admin_dashboard/templates/admin_dashboard/_updater_card.html
git commit -m "feat(deploys): a store put back on an older release says so, once" -m "safe_migrate records each deploy before migrating (after, when DeployEvent itself is being migrated), so a crashed migration still leaves the attempt and its backup; the marker names the row, so a crash-loop restart adds none. A boot older than the newest record writes rolled_back_from, emails the operators once (core.errors.alerts.send_alert: which version failed, which runs now, the backup from just before) and Version & updates shows it." -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: The guard

**Files:**
- Create: `scripts/deploy_guard.py`
- Test: `core/tests/test_deploy_guard.py`

**Interfaces:**
- Consumes:
  - Task 1's confirmed payload and answer shape;
  - `morph/settings.py`'s `MORPHEUS_VERSION` line;
  - git release tags `vX.Y.Z`.
- Produces: the command `python3 scripts/deploy_guard.py rollback [--dry-run]`.
  - It exits 0 when every store is up, or late and left alone.
  - It exits 1 when it rolled a store back, or failed to.
  - It exits with a message when unconfigured.
  - It reads the `MORPHEUS_DEPLOY_HOOKS` env JSON, `{"webhook", "repository", "branch", "stores": {base URL: secret}}`.

- [ ] **Step 1: Write the failing tests**

`core/tests/test_deploy_guard.py`:

```python
"""scripts/deploy_guard.py: put back a store that did not come up (safe deploys, part 3)."""

from __future__ import annotations

import hashlib
import hmac
import http.server
import importlib.util
import json
import threading
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

_SPEC = importlib.util.spec_from_file_location(
    'deploy_guard', Path(__file__).resolve().parents[2] / 'scripts' / 'deploy_guard.py'
)
guard = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(guard)

NEW, OLD = 'v0.121.0', 'v0.120.1'
UP_NEW = (200, json.dumps({'status': 'ok', 'version': NEW}))
UP_OLD = (200, json.dumps({'status': 'ok', 'version': OLD}))
DOWN = (503, '')


def _get(responses):
    """A fake GET: each URL answers from its list, one entry per call, the last repeating."""
    calls = {}

    def get(url, timeout=15):
        answers = responses[url]
        index = calls.get(url, 0)
        calls[url] = index + 1
        return answers[min(index, len(answers) - 1)]

    return get


class VersionTests(SimpleTestCase):
    def test_the_previous_release_ignores_other_tags_and_order(self):
        tags = ['v0.119.0', 'morpheus-known-good', 'v0.121.0', 'v1.0.0-rc1', 'v0.120.1', 'v0.9.9', 'v0.120.0']
        self.assertEqual(guard.previous_release(NEW, tags), OLD)
        self.assertEqual(guard.previous_release('v0.9.9', tags), None)

    def test_the_version_being_deployed_is_read_from_settings(self):
        text = "MORPHEUS_VERSION = config('MORPHEUS_VERSION', default='v0.121.0')\n"
        self.assertEqual(guard.expected_version(text), NEW)


class ClassifyTests(SimpleTestCase):
    def _classify(self, readyz, home=(200, '')):
        get = _get({'https://s/readyz': readyz, 'https://s/': [home]})
        sleeps = []
        return guard.classify('https://s', NEW, get=get, sleep=sleeps.append), sleeps

    def test_a_store_on_the_new_version_is_up(self):
        self.assertEqual(self._classify([UP_NEW])[0], 'up')

    def test_a_store_still_on_the_old_version_is_left_alone(self):
        self.assertEqual(self._classify([UP_OLD])[0], 'late')

    def test_a_brief_503_is_not_down(self):
        state, sleeps = self._classify([DOWN, UP_NEW])
        self.assertEqual(state, 'up')
        self.assertEqual(sleeps, [guard.CHECK_GAP])

    def test_down_means_down_at_every_check(self):
        state, sleeps = self._classify([DOWN])
        self.assertEqual(state, 'down')
        self.assertEqual(len(sleeps), guard.CHECKS - 1)

    def test_a_home_page_that_fails_is_not_up(self):
        self.assertEqual(self._classify([UP_NEW], home=(500, ''))[0], 'down')


class _FakeCoolify(http.server.BaseHTTPRequestHandler):
    seen: list = []

    def do_POST(self):  # noqa: N802 — the stdlib's name
        body = self.rfile.read(int(self.headers['Content-Length']))
        # The message object, not a dict: urllib sends 'X-github-event', and HTTP
        # header names are case-insensitive, as the object's lookups are.
        type(self).seen.append((self.path, self.headers, body))
        reply = json.dumps([{'status': 'success', 'message': 'Deployment queued.'}]).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(reply)

    def log_message(self, *args):
        pass


class WebhookTests(SimpleTestCase):
    def test_the_push_is_signed_with_the_store_s_own_secret(self):
        _FakeCoolify.seen = []
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), _FakeCoolify)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        hook = f'http://127.0.0.1:{server.server_port}/webhooks/source/github/events/manual'
        status, text = guard.deploy_commit(hook, 'magnetoid/morpheus', 'main', 's3cret', 'c' * 40)
        self.assertEqual(status, 200)
        self.assertTrue(guard.queued(text))
        path, headers, body = _FakeCoolify.seen[0]
        self.assertEqual(path, '/webhooks/source/github/events/manual')
        self.assertEqual(headers['X-GitHub-Event'], 'push')
        expected = 'sha256=' + hmac.new(b's3cret', body, hashlib.sha256).hexdigest()
        self.assertEqual(headers['X-Hub-Signature-256'], expected)
        payload = json.loads(body)
        self.assertEqual(
            (payload['ref'], payload['after'], payload['repository']['full_name']),
            ('refs/heads/main', 'c' * 40, 'magnetoid/morpheus'),
        )

    def test_an_answer_without_a_queued_deployment_is_not_success(self):
        self.assertFalse(guard.queued(json.dumps([{'status': 'failed', 'message': 'Invalid signature.'}])))
        self.assertFalse(guard.queued('not json'))


class RollbackTests(SimpleTestCase):
    CONFIG = {
        'webhook': 'https://coolify/webhooks/source/github/events/manual',
        'repository': 'magnetoid/morpheus',
        'branch': 'main',
        'stores': {'https://up': 'a', 'https://late': 'b', 'https://down': 'c'},
    }

    def _run(self, down_after=(DOWN,), dry_run=False, post_answer=(200, '[{"status": "success"}]')):
        get = _get(
            {
                'https://up/readyz': [UP_NEW],
                'https://up/': [(200, '')],
                'https://late/readyz': [UP_OLD],
                'https://late/': [(200, '')],
                'https://down/readyz': [DOWN] * guard.CHECKS + list(down_after),
                'https://down/': [(200, '')],
            }
        )
        posts, lines = [], []

        def post(url, body, headers, timeout=30):
            posts.append((url, json.loads(body), headers))
            return post_answer

        code = guard.rollback(
            self.CONFIG, NEW, ['v0.120.0', OLD, NEW], dry_run=dry_run, get=get, post=post,
            sleep=lambda s: None, commit_of=lambda tag: {OLD: 'd' * 40}[tag], log=lines.append,
            clock=iter(range(0, 10_000, 30)).__next__,
        )
        return code, posts, '\n'.join(lines)

    def test_only_the_store_that_is_down_is_put_back_on_the_previous_release(self):
        code, posts, log = self._run(down_after=(DOWN, UP_OLD))
        self.assertEqual(code, 1)  # a rollback is still a failed release
        self.assertEqual(len(posts), 1)
        url, payload, headers = posts[0]
        self.assertEqual(payload['after'], 'd' * 40)
        expected = 'sha256=' + hmac.new(b'c', json.dumps(payload).encode(), hashlib.sha256).hexdigest()
        self.assertEqual(headers['X-Hub-Signature-256'], expected)
        self.assertIn('OK    https://down serves v0.120.1 again', log)
        self.assertIn('LATE  https://late', log)

    def test_a_dry_run_sends_nothing(self):
        code, posts, log = self._run(dry_run=True)
        self.assertEqual(posts, [])
        self.assertIn('would put back v0.120.1', log)

    def test_a_webhook_that_queues_nothing_is_a_failure(self):
        code, posts, log = self._run(post_answer=(200, '[{"status": "failed"}]'))
        self.assertEqual(code, 1)
        self.assertIn('FAIL  https://down', log)

    def test_a_store_that_stays_down_after_the_rollback_is_reported(self):
        code, _, log = self._run(down_after=(DOWN,))
        self.assertEqual(code, 1)
        self.assertIn('did not come up on v0.120.1 either', log)


class ConfigTests(SimpleTestCase):
    def test_without_its_secret_the_guard_says_rollback_is_off(self):
        with patch.dict('os.environ', {}, clear=True), self.assertRaises(SystemExit) as stop:
            guard.load_config()
        self.assertIn('Automatic rollback is off', str(stop.exception))

    def test_a_config_without_stores_is_refused(self):
        env = {'MORPHEUS_DEPLOY_HOOKS': json.dumps({'webhook': 'https://x', 'repository': 'a/b'})}
        with patch.dict('os.environ', env, clear=True), self.assertRaises(SystemExit):
            guard.load_config()
```

- [ ] **Step 2: Run them to see them fail**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_deploy_guard`
Expected: ERROR. `FileNotFoundError`, because `scripts/deploy_guard.py` does not exist yet.

- [ ] **Step 3: Write `scripts/deploy_guard.py`**

```python
#!/usr/bin/env python3
"""Put a store back on the previous release when a new one leaves it down.

Run by .github/workflows/deploy-smoke.yml after scripts/deploy_smoke.sh fails
(safe deploys, part 3). Standard library only: CI runs it with the system
Python.

A store is put back only when it is down, not when it is late. One that still
serves an older version is queued behind the others, or missed its webhook, and
is left alone. One that answers 503 for a few seconds is being swapped, so each
store is checked CHECKS times, CHECK_GAP seconds apart.

It puts a store back by sending that store's Coolify manual GitHub webhook a
signed push event naming the previous release tag's commit: Coolify deploys the
``after`` commit of a push to the application whose own secret signed it. The
guard holds only those per-store secrets, never an API token: one secret can
deploy commits of this repository to one store, which is what pushing to main
can do anyway. A push deploys its own commit whatever an application is pinned
to, so nothing needs unpinning; but Coolify's Redeploy deploys main, the commit
that failed, until a fix is pushed.

Configuration, the MORPHEUS_DEPLOY_HOOKS secret (JSON):
  {"webhook": "https://<coolify>/webhooks/source/github/events/manual",
   "repository": "<owner>/<repo>", "branch": "main",
   "stores": {"https://store.example": "<that application's manual webhook secret>"}}
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = 3  # a store counts as down only when it fails this many checks in a row
CHECK_GAP = 20  # seconds between them
WAIT = 30 * 60  # how long the stores put back get to come up, together
_VERSION = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)$')
_SETTINGS = re.compile(r"MORPHEUS_VERSION = config\('MORPHEUS_VERSION', default='([^']+)'\)")


def version_key(text: str) -> tuple[int, ...] | None:
    match = _VERSION.match(text.strip())
    return tuple(int(part) for part in match.groups()) if match else None


def expected_version(settings_text: str) -> str:
    match = _SETTINGS.search(settings_text)
    return match.group(1) if match else ''


def previous_release(expected: str, tags: list[str]) -> str | None:
    """The newest release tag older than ``expected``."""
    ceiling = version_key(expected)
    if ceiling is None:
        return None
    older = [tag for tag in tags if (key := version_key(tag)) is not None and key < ceiling]
    return max(older, key=version_key) if older else None


def http_get(url: str, timeout: float = 15) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={'User-Agent': 'morpheus-deploy-guard'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 — configured https URLs
            return response.status, response.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode('utf-8', 'replace')
    except (urllib.error.URLError, OSError):
        return 0, ''


def http_post(url: str, body: bytes, headers: dict, timeout: float = 30) -> tuple[int, str]:
    request = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 — the configured webhook
            return response.status, response.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode('utf-8', 'replace')
    except (urllib.error.URLError, OSError) as exc:
        return 0, str(exc)


def store_state(base: str, get=http_get) -> tuple[str, bool]:
    """``(version, healthy)``: what /readyz reports, and whether the store works
    as a shop (/readyz ``ok`` and the home page 200)."""
    status, body = get(f'{base}/readyz')
    try:
        data = json.loads(body) if status == 200 else {}
    except ValueError:
        data = {}
    version = str(data.get('version') or '') if isinstance(data, dict) else ''
    if not isinstance(data, dict) or data.get('status') != 'ok':
        return version, False
    home, _ = get(f'{base}/')
    return version, home == 200


def classify(base: str, expected: str, *, get=http_get, sleep=time.sleep) -> str:
    """'up' (healthy on ``expected``), 'late' (healthy on another version) or
    'down' (not healthy at any of CHECKS checks)."""
    for attempt in range(CHECKS):
        version, healthy = store_state(base, get)
        if healthy:
            return 'up' if version == expected else 'late'
        if attempt + 1 < CHECKS:
            sleep(CHECK_GAP)
    return 'down'


def sign(secret: str, body: bytes) -> str:
    return 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def deploy_commit(hook: str, repository: str, branch: str, secret: str, commit: str, post=http_post):
    """Send the store's webhook a signed push event naming ``commit``."""
    body = json.dumps(
        {'ref': f'refs/heads/{branch}', 'after': commit, 'repository': {'full_name': repository}, 'commits': []}
    ).encode()
    headers = {
        'Content-Type': 'application/json',
        'X-GitHub-Event': 'push',
        'X-Hub-Signature-256': sign(secret, body),
        'User-Agent': 'morpheus-deploy-guard',
    }
    return post(hook, body, headers)


def queued(text: str) -> bool:
    """Whether Coolify's answer says a deployment was queued."""
    try:
        data = json.loads(text)
    except ValueError:
        return False
    stack = [data]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if item.get('status') == 'success':
                return True
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return False


def _git(*args: str) -> str:
    cmd = ['git', *args]
    done = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True)  # noqa: S603
    return done.stdout


def tag_commit(tag: str) -> str:
    return _git('rev-list', '-n', '1', tag).strip()


def release_tags() -> list[str]:
    return _git('tag', '--list', 'v*').split()


def load_config(env=None) -> dict:
    env = os.environ if env is None else env
    raw = (env.get('MORPHEUS_DEPLOY_HOOKS') or '').strip()
    if not raw:
        raise SystemExit('Automatic rollback is off: MORPHEUS_DEPLOY_HOOKS is not set (docs/UPDATING.md).')
    try:
        config = json.loads(raw)
    except ValueError as exc:
        raise SystemExit(f'MORPHEUS_DEPLOY_HOOKS is not JSON: {exc}') from exc
    for key in ('webhook', 'repository', 'stores'):
        if not config.get(key):
            raise SystemExit(f'MORPHEUS_DEPLOY_HOOKS has no "{key}".')
    config.setdefault('branch', 'main')
    return config


def rollback(config, expected, tags, *, dry_run=False, get=http_get, post=http_post,
             sleep=time.sleep, commit_of=tag_commit, log=print, clock=time.monotonic) -> int:
    """Put back every store that is down on the previous release; the exit code."""
    stores = {base.rstrip('/'): secret for base, secret in config['stores'].items()}
    down = []
    for base in stores:
        state = classify(base, expected, get=get, sleep=sleep)
        if state == 'up':
            log(f'UP    {base} serves {expected}')
        elif state == 'late':
            log(f'LATE  {base} still serves an older version: queued, or its webhook was missed; left alone')
        else:
            down.append(base)
    if not down:
        return 0
    previous = previous_release(expected, tags)
    if previous is None:
        for base in down:
            log(f'FAIL  {base} is down, and there is no release older than {expected} to put back')
        return 1
    commit = commit_of(previous)
    failures, waiting = 0, []
    for base in down:
        if dry_run:
            log(f'DOWN  {base}: would put back {previous} ({commit[:7]})')
            continue
        status, text = deploy_commit(config['webhook'], config['repository'], config['branch'], stores[base], commit, post=post)
        if status == 200 and queued(text):
            log(f'BACK  {base}: putting back {previous} ({commit[:7]})')
            waiting.append(base)
        else:
            log(f'FAIL  {base}: the webhook queued nothing ({status}): {text[:200]}')
            failures += 1
    end = clock() + WAIT
    while waiting:
        for base in list(waiting):
            version, healthy = store_state(base, get)
            if healthy and version == previous:
                log(f'OK    {base} serves {previous} again')
                waiting.remove(base)
        if not waiting or clock() >= end:
            break
        sleep(CHECK_GAP)
    for base in waiting:
        log(f'FAIL  {base} did not come up on {previous} either')
        failures += 1
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Put back the stores a new release left down.')
    parser.add_argument('command', choices=['rollback'])
    parser.add_argument('--dry-run', action='store_true', help='Say what would happen; send nothing.')
    args = parser.parse_args(argv)
    config = load_config()
    expected = expected_version((ROOT / 'morph' / 'settings.py').read_text())
    return rollback(config, expected, release_tags(), dry_run=args.dry_run)


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_deploy_guard`
Expected: `OK`.

- [ ] **Step 5: Lint and commit**

Run: `ruff check scripts/deploy_guard.py core/tests/test_deploy_guard.py && ruff format scripts/deploy_guard.py core/tests/test_deploy_guard.py`
Expected: `All checks passed!`.

```bash
git add scripts/deploy_guard.py core/tests/test_deploy_guard.py
git commit -m "feat(deploys): scripts/deploy_guard.py puts back a store a release left down" -m "Down, not late: three checks 20 s apart, and a store still healthy on an older version is left alone. A down store gets a signed push naming the previous release tag's commit through its own Coolify manual webhook (per-store secret, never an API token), then the guard waits for all of them together. A rollback still exits 1, so the run stays red." -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Wire it in, document it, ship it

**Files:**
- Modify: `.github/workflows/deploy-smoke.yml`
- Modify: `CLAUDE.md`, `docs/UPDATING.md`, `docs/OPERATIONS_RUNBOOK.md`, `plugins/installed/release_notes/help.md`
- Modify (by `manage.py release`): `morph/settings.py`, `docs/RELEASE_NOTES.md`

**Interfaces:**
- Consumes: Tasks 2 and 3.
- Produces: v0.121.0 on all four stores, with the `MORPHEUS_DEPLOY_HOOKS` secret set.

- [ ] **Step 1: The workflow**

Replace the `jobs:` block of `.github/workflows/deploy-smoke.yml`:

```yaml
jobs:
  smoke:
    runs-on: ubuntu-latest
    # 25 minutes of smoke, a minute of checks, then up to 30 minutes for the
    # stores put back to come up.
    timeout-minutes: 70
    env:
      MORPHEUS_DEPLOY_HOOKS: ${{ secrets.MORPHEUS_DEPLOY_HOOKS }}
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0 # the guard reads the release tags
      - name: Wait for production to serve this version, then smoke it
        run: bash scripts/deploy_smoke.sh
      - name: Put back the stores this release left down
        if: failure()
        run: python3 scripts/deploy_guard.py rollback
```

Add to `core/tests/test_deploy_guard.py`:

```python
class WorkflowTests(SimpleTestCase):
    def test_deploy_smoke_runs_the_guard_when_the_smoke_fails(self):
        text = (Path(__file__).resolve().parents[2] / '.github' / 'workflows' / 'deploy-smoke.yml').read_text()
        self.assertIn('fetch-depth: 0', text)
        self.assertIn('if: failure()', text)
        self.assertIn('python3 scripts/deploy_guard.py rollback', text)
        self.assertIn('secrets.MORPHEUS_DEPLOY_HOOKS', text)
```

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_deploy_guard.WorkflowTests`
Expected: FAIL before the YAML edit; `OK` after it.

- [ ] **Step 2: The docs and the help**

`CLAUDE.md`, after the "a restore is all or nothing" convention:

```markdown
**Convention — a store a release leaves down goes back to the previous release (v0.121.0).**
When deploy-smoke times out, `scripts/deploy_guard.py rollback` checks each store three times,
20 s apart:
- up on the new version: nothing to do;
- up on an older version: it is queued or missed its webhook, so it is left alone;
- down at every check: it puts the store back on the previous release.

It puts a store back by sending that store's Coolify manual GitHub webhook a signed push naming
the previous release tag's commit, then waits for every store it put back. It never uses an API
token: the Coolify team holds 34 applications, clients' included, and a write token would reach all
of them. One store's webhook secret deploys only this repository's commits to that store (the secret
`MORPHEUS_DEPLOY_HOOKS`, which names no infrastructure in the repository).

What Coolify's source says (v4.4.6):
- A push deploys its `after` commit, whatever the app's `git_commit_sha`.
- Redeploy, or an API deploy, deploys `git_commit_sha` (`HEAD`), which is the failed commit. After
  a rollback, push a fix; never Redeploy.

The store reports it itself. `safe_migrate` records each deploy *before* migrating (after, when
`DeployEvent` itself is being migrated), so a crashed migration still leaves the attempt and its
backup. The marker names the row, so a crash-loop restart adds none. A boot older than the newest
record writes `rolled_back_from`, emails the operators once (`core.errors.alerts.send_alert`), and
Version & updates says so. A rollback exits 1, so the run stays red. That red run is the only signal
when the release put back predates v0.121.0, which cannot email. Guarded by
`core/tests/test_deploy_guard.py` and `test_rollback_notice.py`.
```

`docs/UPDATING.md`: replace `- an automatic code rollback when a store does not come up.` with:

```markdown
- ~~an automatic code rollback when a store does not come up~~: shipped in v0.121.0.

### Automatic rollback

After every push to `main`, deploy-smoke waits for each store to serve the new version. When a
store is down at the deadline (not merely still on the old version), `scripts/deploy_guard.py
rollback` puts it back on the previous release tag. It does this by sending that store's deploy
platform a signed GitHub push event whose `after` is the tag's commit. Configure it with the
`MORPHEUS_DEPLOY_HOOKS` repository secret:

    {"webhook": "https://<coolify>/webhooks/source/github/events/manual",
     "repository": "<owner>/<repo>", "branch": "main",
     "stores": {"https://store.example": "<that application's manual webhook secret>"}}

Any platform works if it deploys the `after` commit of a signed push and serves `/readyz` with the
running version. Coolify's manual GitHub webhook does: it uses each application's own secret, found
under the application's Webhooks settings. The store then emails its operators (`ERROR_ALERT_EMAILS`,
else the superusers) and Settings → Version & updates says it was put back. After a rollback, push a
fix rather than redeploying: a redeploy builds the branch head, which is the release that failed.
```

`docs/OPERATIONS_RUNBOOK.md`, "Rollback": replace the "Code:" bullet with:

```markdown
- Code: automatic since v0.121.0 for a store that a push leaves down. deploy-smoke's
  guard puts it back on the previous release, the run stays red, and the store emails
  the operators. A rollback to a release older than v0.121.0 cannot email; the red run
  is the signal. Do not click Redeploy in Coolify afterwards: it builds `main`, the
  failed commit. Push a fix, or `git revert` the bad commit and push; that push deploys
  every store again. By hand: the same revert-and-push, verified with deploy-smoke.
```

`plugins/installed/release_notes/help.md`, appended to `## Good to know`:

```markdown

If an update does not come up, the store goes back to the version before it by itself, emails you, and Version & updates says which version failed.
```

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test plugins.installed.release_notes`
Expected: `OK`. The guide stays inside 400 body words.

- [ ] **Step 3: Commit the wiring and docs**

```bash
git add .github/workflows/deploy-smoke.yml core/tests/test_deploy_guard.py CLAUDE.md docs/UPDATING.md docs/OPERATIONS_RUNBOOK.md plugins/installed/release_notes/help.md
git commit -m "feat(deploys): deploy-smoke puts back the stores a release leaves down" -m "The smoke job checks out the tags and runs scripts/deploy_guard.py rollback when the smoke fails (70-minute timeout). The convention, the self-hosted contract, the runbook and the help say what it does, and that after a rollback a fix is pushed, never redeployed." -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 4: The full suite and CI's gates**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress' .venv/bin/python manage.py test > <workspace>/suite.log 2>&1; grep -E '^Ran |^OK|^FAILED' <workspace>/suite.log`
Expected: `OK (skipped=10)`.

Run: `ruff check . -q && ruff format --check . | tail -1 && .venv/bin/python manage.py check && .venv/bin/python manage.py makemigrations --check --dry-run && .venv/bin/python scripts/check_core_boundary.py && .venv/bin/python scripts/check_plugin_boundary.py && .venv/bin/python scripts/check_plugin_standard.py && .venv/bin/pip-audit --require-hashes -r requirements.lock.txt`
Expected: every gate clean.

- [ ] **Step 5: Cut v0.121.0**

With the full-suite environment variables exported:

```bash
.venv/bin/python manage.py release --minor "A store an update leaves down goes back to the previous version by itself" \
  -m "If an update leaves a store down, it is put back on the previous version automatically, and its operators get an email: which version failed, which one runs now, and where the data from just before it is." \
  -m "Settings → Version & updates says when a store was put back. Until a fix is released, do not redeploy the store from Coolify: that would deploy the failed version again." \
  --commit
git commit --amend -q -m "$(git log -1 --format=%B)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
.venv/bin/python manage.py release --check
```

Expected: `v0.120.1 -> v0.121.0`. The release-2 gate reviews `core.0025_deployevent_rolled_back_from` and passes it (`db_default`). `release --check` is in sync.

- [ ] **Step 6: The whole-branch review, before anything is pushed**

Run the executing skill's final review: review package, then an Opus reviewer with this plan's Review Focus, then the fix pass. Push only once it is clean.

- [ ] **Step 7: The secret (owner's decision, 2026-10-21)**

Write `<scratchpad>/r4_hooks.py`. It builds the guard's JSON from the Coolify API on this machine (the API token never leaves it) and either pipes it to `gh` (`set`) or runs the guard with it (`dry-run`). It prints no secret:

```python
"""Safe deploys release 4: the guard's configuration, built from the Coolify API on this machine."""
import importlib.util, json, os, subprocess, sys, urllib.request

STORES = {  # Coolify application uuid → the store's base URL
    'ghtnqf6lw2bg5229lv1sf4h9': 'https://dotbooks.store',
    'z10xg4j7yq8x1htipw12a368': 'https://supernatural-shop.com',
    'fo8rvcg94bmcyi43e8iq9tvm': 'https://montenegro-experience.me',
    'j7xoogxjqgyakdsjw37eneuh': 'https://beta.irvingsurvival.com',
}


def build_config() -> dict:
    token = subprocess.run(['security', 'find-generic-password', '-a', 'api', '-s', 'coo.imbamarketing.com', '-w'],
                           capture_output=True, text=True, check=True).stdout.strip()
    stores = {}
    for uuid, base in STORES.items():
        req = urllib.request.Request(f'https://coo.imbamarketing.com/api/v1/applications/{uuid}',
                                     headers={'Authorization': f'Bearer {token}'})
        app = json.load(urllib.request.urlopen(req, timeout=30))
        assert app['git_repository'] == 'magnetoid/morpheus' and app['git_branch'] == 'main', uuid
        assert app.get('manual_webhook_secret_github'), f'{uuid} has no manual webhook secret'
        stores[base] = app['manual_webhook_secret_github']
    return {'webhook': 'https://coo.imbamarketing.com/webhooks/source/github/events/manual',
            'repository': 'magnetoid/morpheus', 'branch': 'main', 'stores': stores}


if __name__ == '__main__':
    config = build_config()
    if sys.argv[1:] == ['set']:
        subprocess.run(['gh', 'secret', 'set', 'MORPHEUS_DEPLOY_HOOKS', '--repo', 'magnetoid/Morpheus'],
                       input=json.dumps(config), text=True, check=True)
        print('secret set for', len(config['stores']), 'stores')
    elif sys.argv[1:] == ['dry-run']:
        os.environ['MORPHEUS_DEPLOY_HOOKS'] = json.dumps(config)
        spec = importlib.util.spec_from_file_location('deploy_guard', 'scripts/deploy_guard.py')
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
        sys.exit(guard.main(['rollback', '--dry-run']))
    else:
        sys.exit('usage: r4_hooks.py set | dry-run')
```

Run: `.venv/bin/python <scratchpad>/r4_hooks.py set && gh secret list --repo magnetoid/Morpheus`
Expected: `secret set for 4 stores`, and the list shows `MORPHEUS_DEPLOY_HOOKS`.

- [ ] **Step 8: Merge and push (deploys all four stores)**

```bash
git checkout main && git merge --ff-only feat/safe-deploys-4 && git push origin main && git branch -d feat/safe-deploys-4
SMOKE_DEADLINE_SECS=2400 bash scripts/deploy_smoke.sh
```

Expected: `SMOKE OK — every store serves v0.121.0`. In the deploy-smoke run on GitHub, the guard step is skipped because the smoke passed. CI is green.

- [ ] **Step 9: Live checks**

1. **The guard, dry run, against the live stores.** Run `cd /Users/magnetoid/coding/morph && .venv/bin/python <scratchpad>/r4_hooks.py dry-run`.
   Expected: four `UP … serves v0.121.0` lines and exit 0.
2. **The store's notice, on a scratch copy of Supernatural.** This runs the runbook's rehearsal pattern in a one-off container on the new image, with its own network.
   - Create `restore_check_r4` from the newest pre-deploy backup and migrate it.
   - Insert a newer row: `INSERT INTO core_deployevent (version, commit, deployed_at, backup, migrations, rolled_back_from) VALUES ('v9.9.9', '', now(), '/app/backups/pre-deploy/x.tar.gz', '[]', '')`.
   - Empty `core_storesettings.smtp_host`, so the mail goes to the console.
   - Run `python manage.py safe_migrate` in the one-off container. It gets `DATABASE_URL` pointing at the scratch copy, `MORPHEUS_BACKUP_DIR=/rehearsal`, `REDIS_URL=redis://127.0.0.1:1/0`, `EMAIL_HOST=` and `ERROR_ALERT_EMAILS=ops@example.invalid`.
   - Expected: `Back on v0.121.0 after v9.9.9: told the operators.`, and the email's text printed in the output, naming `x.tar.gz` and "do not redeploy". `core_deployevent` then has a v0.121.0 row with `rolled_back_from = 'v9.9.9'`. Drop the scratch database.
3. **The rollback mechanism.** Task 1 proved it on Irving.

- [ ] **Step 10: Record and close**

Update memory: `releases-2026-10-19.md` gets "release 4 shipped as v0.121.0", the Coolify facts, the per-store webhook design and the deferred minors; update its line in `MEMORY.md`. Then delete this plan's workspace once the review is clean.
