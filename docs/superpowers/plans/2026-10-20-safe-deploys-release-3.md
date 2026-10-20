# Safe deploys, release 3: restoring a backup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A superuser can put a store's data back as a backup has it, from Settings → Version & updates or with `manage.py morph_restore`, all or nothing, with the store closed while it runs.

**Architecture:** One engine, `core/restore.py`, runs every restore. It backs the current database up into `pre-restore/` and closes the store with a file on the backups volume, which `RestoreGateMiddleware` reads before anything touches the database. Then it ends the other database sessions, runs `pg_restore --single-transaction`, drops the cache's keys, and records the outcome beside the file. The CLI (`morph_restore`) and the page (release_notes, which starts the same command detached) are two doors to it. Each app counts what a restore would lose through a new filter, `RESTORE_LOSSES`.

**Tech Stack:** Django 6.1, PostgreSQL 16 (`pg_restore` 16.15 in the image), django-redis, gunicorn (gthread), unittest via `manage.py test`.

**Spec:** `docs/superpowers/specs/2026-10-19-safe-deploys-design.md`, part 4 ("Restoring data, by hand") and "To verify" items 3 and 4.

## Global Constraints

- From the spec: "`manage.py morph_restore <file> --confirm "<store name>"` restores a backup: maintenance mode on, other database sessions ended, `pg_restore --clean --if-exists --no-owner`, maintenance mode off."
- From the spec: "A superuser-only page on Settings → Version & updates lists the pre-deploy and nightly backups (time, version, size) and runs the same restore in the background. Before it starts, it says what the backup does not contain, from the database itself ("4 orders and 2 new customers since 14:02 will be lost"), and asks for the store's name typed out."
- From the spec: "Parts 1, 2, 4 and 5 live in the app and work the same anywhere."
- From release 1 (`core/deploys.py`): the backup folder comes from `MORPHEUS_BACKUP_DIR` only, never from the backups app's setting, because staff and Linda can change settings.
- `core/` imports nothing from `plugins.installed.*` (core-boundary ratchet at 0). Core asks the apps through the hook bus.
- Janus rule (ADR 0039): a merchant action ships with its agent tool, or the change says why an agent must not have it. Here: no restore tool, and the docs and help say why.
- Every app ships its own help. A change to what staff see updates `plugins/installed/release_notes/help.md` in the same commit: 60–400 body words, headings from `app_help.HEADINGS`, none of `app_help.JARGON` (plugin, hook, celery, queryset, middleware) in the prose.
- A dashboard page never caps its own width (`admin_dashboard/tests/test_page_width.py`). Compile every new template with `get_template()`.
- One release, v0.120.0, cut with `manage.py release --minor` while `MORPHEUS_EXTRA_APPS` is set. A push to `main` deploys all four stores: push once, at the end.
- Tests run as `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test …`. The full suite adds `MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress'`.
- Commits end with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`. Never bypass the pre-commit hook. It refuses raw SQL that drops or truncates a table in any added line, docs included (`core/safety.py` `PRECOMMIT_FORBIDDEN_PATTERNS`).
- Copy is plain words, and the assistant is called Linda.

### Verified before writing this plan (2026-10-20, Supernatural, a scratch database)

- `pg_restore` 16.15 is in the image, the same version as the server. The app's database role is a superuser.
- `pg_restore --clean --if-exists --no-owner --no-acl --single-transaction --exit-on-error` restored the 16 MB pre-deploy backup into a populated database: exit 0 in 29.4 s, and 708 = 708 products.
- The role ended another of its own sessions with `pg_terminate_backend`. The store's database had 37 open sessions.
- The cache and Celery's broker are the same Redis database (`REDIS_URL` for both, no key prefix), so `cache.clear()` would empty the task queue.
- `DATABASES` keep connections for 600 s (`conn_max_age=600`) with no health check.
- The web container runs `exec gunicorn` (no `--preload`, `--max-requests 1000`). Each process keeps app settings in memory (`Plugin._config_cache`).
- Today's maintenance mode is a storefront setting in the database that lets staff through. A restore replaces that database, so it cannot use it.

### Decisions this plan makes where the spec is silent or cannot hold

1. **Everyone, the superuser included, sees "restoring" while it runs.** The spec said "apart from the superuser running it", but the dashboard needs the database that is being replaced and locked. The page reloads itself until the restore is done, then shows how it ended.
2. **The current data is backed up first**, into `pre-restore/` (three kept), so a wrong restore can be undone the same way.
3. **A restore never runs migrations.** Someone who restored to get away from a bad migration would run it again. When the backup is older than the running code, the outcome names the migrations it lacks, and a redeploy applies them.
4. **The closed sign is a file on the backups volume** (`restore/running.json`), never a row or a cache key: the restore replaces the one and clears the other. A heartbeat keeps the file fresh. A restore that dies stops closing the store 90 s later.
5. **The `pg_restore` flags add `--no-acl --single-transaction --exit-on-error`** to the spec's three. The backups are dumped with `--no-acl`, and all or nothing is the point.
6. **Only the cache's own keys are dropped** (`delete_pattern('*')`), never `cache.clear()`.
7. **Every reused database connection is checked first** (`CONN_HEALTH_CHECKS`). Otherwise each connection the restore ended fails one request.
8. **A restore started from the page reloads the web workers** with a SIGHUP to the gunicorn master, so they drop what they held in memory. The worker and beat containers need a restart, and the screen says so.
9. **"What will be lost" counts** orders placed, customers signed up and products added or changed, each through the app that owns them. The screen also says that everything else saved since then is replaced too.
10. **Photos and files are not restored:** the database only, as the spec's command does.
11. **Linda gets no restore tool.** She sees the last restore's outcome in `updates.status`.

## Review Focus

1. **A restore killed half way** (a deploy replaces the container while it runs). The store must reopen on its own within 90 s, the data must be either the backup's or as before, and Version & updates must say the restore did not report back. Pinned by `LockTests.test_a_dead_restore_is_taken_over`, `test_a_restore_that_stopped_beating_no_longer_closes_the_store` (Task 1) and `test_a_restore_that_stopped_is_reported` (Task 4).
2. **Two restores at once** (a double click, two superusers). The second is refused and the first runs. Pinned by `test_a_second_restore_is_refused_while_one_runs` (Task 1) and `test_no_restore_while_another_runs` (Task 2).
3. **A file the list doesn't offer**: a `.part` file, a name under the wrong kind, an unknown kind, or a file in the backups app's own folder setting. Each is answered 404 and nothing runs. Pinned by `test_names_outside_the_list_are_not_found` and `test_only_this_store_s_backup_folder_is_listed` (Task 4).
4. **The store's name typed loosely.** Spaces around it are fine; a different case is refused. Pinned by `test_spaces_around_the_name_are_fine_but_case_counts` (Task 2) and `test_the_wrong_name_starts_nothing` (Task 4).
5. **A backup older than the running code.** The outcome names the migrations it lacks and says to redeploy; nothing migrates behind anyone's back. Pinned by `test_a_backup_older_than_the_code_names_what_it_lacks` (Task 2) and `test_the_page_shows_how_the_last_restore_ended` (Task 4).

---

## File structure

| File | Responsibility |
|---|---|
| `core/restore.py` (new) | The restore engine: its state files, the heartbeat, the gate middleware, extracting and restoring a dump, the listing, the losses, starting a restore in the background |
| `core/management/commands/morph_restore.py` (new) | The command-line door to `core.restore.run` |
| `core/deploys.py` | `describe_backup()` (one parser for backup names; an impossible date is skipped); `running_release()` gains `last_restore` |
| `core/hooks.py` | `MorpheusEvents.RESTORE_LOSSES` |
| `morph/settings.py` | The gate first after `SecurityMiddleware`; `CONN_HEALTH_CHECKS` on every database |
| `plugins/installed/orders/app.py`, `customers/app.py`, `catalog/app.py` | Each counts its own losses |
| `plugins/installed/release_notes/restore_views.py`, `restore_urls.py` (new) | The restore screen at `/dashboard/restore/<kind>/<file>/` |
| `plugins/installed/release_notes/templates/release_notes/_backups_card.html`, `restore_confirm.html` (new) | The Backups card and the restore screen |
| `plugins/installed/release_notes/app.py`, `views.py`, `templates/release_notes/index.html`, `help.md` | Mount the screen, show the card, document it |
| `CLAUDE.md`, `docs/UPDATING.md`, `docs/OPERATIONS_RUNBOOK.md`, `docs/ARCHITECTURE.md` | The convention, the procedures, the request path |

---

### Task 1: The restore gate

**Files:**
- Create: `core/restore.py`
- Modify: `morph/settings.py` (MIDDLEWARE, the `for db_config in DATABASES.values():` loop)
- Test: `core/tests/test_restore_gate.py`

**Interfaces:**
- Consumes: `core.deploys.backup_root() -> Path` (release 1).
- Produces:
  - `core.restore.STALE_AFTER = 90` and `HEARTBEAT = 5`;
  - `RestoreError(Exception)` and `RestoreBusy(RestoreError)`;
  - `state_dir() -> Path` and `running_path() -> Path`;
  - `is_running() -> bool`, `stalled() -> dict | None` and `last() -> dict | None`;
  - `start(info: dict) -> None`, which raises `RestoreBusy`;
  - `finish(outcome: dict) -> None` and `heartbeat(path: Path, every: float = HEARTBEAT)` (a context manager);
  - `RestoreGateMiddleware`.

- [ ] **Step 1: Write the failing tests**

`core/tests/test_restore_gate.py`:

```python
"""While a restore runs, every page says so (safe deploys, part 4)."""

from __future__ import annotations

import json
import os
import tempfile
import time
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from core import restore


class _StateFolder:
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = patch.dict(os.environ, {'MORPHEUS_BACKUP_DIR': tmp.name})
        env.start()
        self.addCleanup(env.stop)

    def _running(self, age=0.0, info=None):
        path = restore.running_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(info or {'file': 'b.tar.gz', 'state': 'running'}))
        stamp = time.time() - age
        os.utime(path, (stamp, stamp))
        return path


class GateTests(_StateFolder, TestCase):
    def test_every_page_says_restoring_while_a_restore_runs(self):
        self._running()
        for path in ('/', '/dashboard/', '/graphql/', '/readyz'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 503, path)
            self.assertContains(response, "Restoring the store", status_code=503)
            self.assertEqual(response['Retry-After'], '30')
            self.assertEqual(response['Cache-Control'], 'no-store')

    def test_the_liveness_probe_stays_open(self):
        # It reads nothing, and a failing one could get the container replaced mid-restore.
        self._running()
        self.assertEqual(self.client.get('/healthz').status_code, 200)

    def test_no_restore_no_gate(self):
        self.assertNotEqual(self.client.get('/dashboard/').status_code, 503)

    def test_a_restore_that_stopped_beating_no_longer_closes_the_store(self):
        self._running(age=restore.STALE_AFTER + 5)
        self.assertNotEqual(self.client.get('/dashboard/').status_code, 503)


class GatePlacementTests(SimpleTestCase):
    def test_the_gate_runs_before_anything_reads_the_database(self):
        stack = settings.MIDDLEWARE
        gate = stack.index('core.restore.RestoreGateMiddleware')
        self.assertLess(gate, stack.index('django.contrib.sessions.middleware.SessionMiddleware'))
        self.assertLess(gate, stack.index('core.storefront_cache.StorefrontCacheMiddleware'))

    def test_reused_connections_are_checked_first(self):
        # A restore ends every other database session; a dead connection must be
        # replaced, not fail the request that picks it up.
        self.assertTrue(settings.DATABASES['default'].get('CONN_HEALTH_CHECKS'))


class LockTests(_StateFolder, SimpleTestCase):
    def test_a_second_restore_is_refused_while_one_runs(self):
        restore.start({'file': 'a'})
        with self.assertRaises(restore.RestoreBusy):
            restore.start({'file': 'b'})
        self.assertEqual(json.loads(restore.running_path().read_text())['file'], 'a')

    def test_a_dead_restore_is_taken_over(self):
        self._running(age=restore.STALE_AFTER + 5, info={'file': 'old'})
        restore.start({'file': 'new'})
        self.assertEqual(json.loads(restore.running_path().read_text())['file'], 'new')
        self.assertTrue(restore.is_running())

    def test_finish_records_the_outcome_and_opens_the_store(self):
        restore.start({'file': 'a'})
        restore.finish({'state': 'done', 'file': 'a'})
        self.assertFalse(restore.is_running())
        self.assertEqual(restore.last(), {'state': 'done', 'file': 'a'})

    def test_stalled_names_the_restore_that_stopped(self):
        self._running(age=restore.STALE_AFTER + 5, info={'file': 'x', 'state': 'running'})
        self.assertEqual(restore.stalled()['file'], 'x')
        self.assertFalse(restore.is_running())

    def test_nothing_stalled_while_a_restore_beats(self):
        self._running()
        self.assertIsNone(restore.stalled())

    def test_nothing_before_the_first_restore(self):
        self.assertIsNone(restore.last())
        self.assertIsNone(restore.stalled())
        self.assertFalse(restore.is_running())

    def test_the_heartbeat_keeps_the_restore_alive(self):
        path = self._running(age=restore.STALE_AFTER - 1)
        with restore.heartbeat(path, every=0.05):
            time.sleep(0.3)
        self.assertLess(time.time() - path.stat().st_mtime, 5)
```

- [ ] **Step 2: Run them to see them fail**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_restore_gate`
Expected: ERROR, `ImportError: cannot import name 'restore' from 'core'`.

- [ ] **Step 3: Write `core/restore.py` (state, heartbeat, gate)**

```python
"""Restoring a backup (safe deploys, part 4). ``manage.py morph_restore`` and
the restore screen on Settings → Version & updates run this one engine.

A restore puts the whole database back as a backup has it, all or nothing:
``pg_restore --single-transaction``, so a failure leaves the database exactly as
it was. Before it starts, it backs the current database up into
``pre-restore/``, so a wrong restore is undone the same way.

While it runs, every page answers "restoring" (``RestoreGateMiddleware``): the
tables are locked and being replaced. That sign is a file on the backups volume,
``restore/running.json``, never a row or a cache key, because the restore
replaces the database and clears the cache. The restore touches the file every
few seconds. One that dies (a deploy replaces its container) stops closing the
store ``STALE_AFTER`` seconds later.

It never runs migrations. Someone who restored to get away from a bad migration
would run it again. A backup older than the running code instead reports the
migrations it lacks, and a redeploy applies them.

Spec: docs/superpowers/specs/2026-10-19-safe-deploys-design.md, part 4.
"""

from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from django.http import HttpResponse

from core import deploys

#: Seconds without a heartbeat after which a restore counts as dead.
STALE_AFTER = 90
HEARTBEAT = 5


class RestoreError(Exception):
    """A restore refused or failed, in words for the person who asked for it."""


class RestoreBusy(RestoreError):
    """Another restore is running."""


def state_dir() -> Path:
    return deploys.backup_root() / 'restore'


def running_path() -> Path:
    return state_dir() / 'running.json'


def _age(path: Path) -> float | None:
    try:
        return time.time() - path.stat().st_mtime
    except OSError:
        return None


def _read(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def is_running() -> bool:
    """A restore is under way: its file exists and was touched lately."""
    age = _age(running_path())
    return age is not None and age <= STALE_AFTER


def stalled() -> dict | None:
    """A restore that stopped without reporting back: its file is there, but
    nothing has touched it for STALE_AFTER seconds."""
    age = _age(running_path())
    if age is None or age <= STALE_AFTER:
        return None
    return _read(running_path()) or {}


def last() -> dict | None:
    """How the latest restore ended, as ``run`` recorded it; None before the first."""
    return _read(state_dir() / 'last.json')


def start(info: dict) -> None:
    """Close the store for a restore, or raise RestoreBusy while another runs.
    A dead restore's file is taken over."""
    path = running_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if stalled() is not None:
        path.unlink(missing_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RestoreBusy('Another restore is running. Wait for it to finish.') from exc
    with os.fdopen(fd, 'w') as fh:
        json.dump(info, fh)


def finish(outcome: dict) -> None:
    """Record how the restore ended, then open the store."""
    target = state_dir() / 'last.json'
    partial = target.with_name('last.json.part')
    partial.write_text(json.dumps(outcome))
    partial.replace(target)
    running_path().unlink(missing_ok=True)


@contextmanager
def heartbeat(path: Path, every: float = HEARTBEAT):
    """Touch ``path`` every ``every`` seconds while the block runs."""
    stop = threading.Event()

    def beat() -> None:
        while not stop.wait(every):
            try:
                os.utime(path)
            except OSError:
                return

    thread = threading.Thread(target=beat, name='restore-heartbeat', daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=every + 1)


_RESTORING_PAGE = (
    '<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="15">'
    '<title>Restoring</title>'
    '<div style="font-family:system-ui;max-width:34rem;margin:14vh auto;'
    'padding:0 1.25rem;text-align:center;line-height:1.6">'
    '<h1 style="font-size:1.5rem;margin:0 0 .75rem">Restoring the store\'s data</h1>'
    '<p style="color:#555;margin:0">This takes a minute or two. '
    'This page reloads itself.</p></div>'
)


class RestoreGateMiddleware:
    """Every page answers 503 "restoring" while a restore runs, before anything
    reads the database. /healthz stays open: it reads nothing, and a failing
    liveness probe could get the container replaced in the middle."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_running() and not request.path.startswith('/healthz'):
            response = HttpResponse(
                _RESTORING_PAGE, status=503, content_type='text/html; charset=utf-8'
            )
            response['Retry-After'] = '30'
            response['Cache-Control'] = 'no-store'
            return response
        return self.get_response(request)
```

- [ ] **Step 4: Wire the gate and the connection checks into `morph/settings.py`**

In `MIDDLEWARE`, directly after `'django.middleware.security.SecurityMiddleware',`:

```python
    # While a backup is being restored, every page answers "restoring" before
    # anything reads the database being replaced (core/restore.py).
    'core.restore.RestoreGateMiddleware',
```

At the top of the body of `for db_config in DATABASES.values():`:

```python
    # A restore (core/restore.py) ends every other session: a reused connection is
    # checked first and replaced, instead of failing the request that picks it up.
    db_config['CONN_HEALTH_CHECKS'] = True
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_restore_gate`
Expected: `Ran 14 tests`, `OK`.

- [ ] **Step 6: Commit**

```bash
git add core/restore.py core/tests/test_restore_gate.py morph/settings.py
git commit -m "feat(restore): close the store while a backup is restored" -m "core/restore.py keeps the restore's state in files on the backups volume, never in the database or the cache it replaces and clears. RestoreGateMiddleware answers 503 'restoring' before anything reads the database; a restore that stops beating stops closing the store after 90 s. CONN_HEALTH_CHECKS replaces the connections a restore ends." -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: The restore engine and `manage.py morph_restore`

**Files:**
- Modify: `core/restore.py` (append the engine)
- Modify: `core/deploys.py` (`describe_backup`, used by `latest_predeploy_backup`)
- Create: `core/management/commands/morph_restore.py`
- Test: `core/tests/test_morph_restore.py`

**Interfaces:**
- Consumes: Task 1's `start`, `finish`, `heartbeat`, `running_path`, `RestoreError`, `RestoreBusy`. Also `core.deploys.backup_root()`, `deploys.migration_plan() -> (list[str], bool)`, `core.utils.site.store_name() -> str`, and the `morph_backup` command (`--dest --keep --no-media --label`, with `archive_path` set on the instance).
- Produces:
  - `core.deploys.describe_backup(path) -> {name, size, taken_at, label} | None`.
  - In `core.restore`:
    - `KINDS = {'nightly': '', 'pre-deploy': 'pre-deploy', 'pre-restore': 'pre-restore'}` and `PRE_RESTORE_KEEP = 3`;
    - `kind_of(path) -> str` and `extract_dump(archive, into) -> Path`;
    - `end_other_sessions() -> int`, `restore_database(dump) -> None`, `clear_cache() -> None` and `back_up_current(stdout=None) -> str` (the file's name);
    - `run(archive, *, confirm, by='', stdout=None) -> dict`. The outcome keys are `state` (done or failed), `file`, `kind`, `taken_at`, `by`, `started_at`, `finished_at`, `pre_restore`, `missing` and `error`.
    - `reload_web(pid: int) -> None`.
  - The command `morph_restore ARCHIVE --confirm NAME [--by WHO] [--reload-web PID]`.

- [ ] **Step 1: Write the failing tests**

`core/tests/test_morph_restore.py`:

```python
"""manage.py morph_restore: all or nothing, the current data saved first (safe deploys, part 4)."""

from __future__ import annotations

import io
import os
import signal
import subprocess
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase

from core import deploys, restore
from core.models import StoreSettings

NAME = 'morpheus-backup-20261020T012146Z-v0.118.0-e1198af.tar.gz'
BEFORE = 'morpheus-backup-20261020T170000Z-before-restore.tar.gz'


def _archive(folder: Path, name: str = NAME, members: dict | None = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    with tarfile.open(path, 'w:gz') as tar:
        for member, data in (members if members is not None else {'db.dump': b'DUMP'}).items():
            info = tarfile.TarInfo(member)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path


class _Folder:
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        env = patch.dict(os.environ, {'MORPHEUS_BACKUP_DIR': tmp.name})
        env.start()
        self.addCleanup(env.stop)


class DescribeBackupTests(_Folder, SimpleTestCase):
    def test_a_backup_is_described_by_its_name_and_size(self):
        path = _archive(self.root)
        info = deploys.describe_backup(path)
        self.assertEqual(info['label'], 'v0.118.0-e1198af')
        self.assertEqual(info['taken_at'].isoformat(), '2026-10-20T01:21:46+00:00')
        self.assertEqual(info['size'], path.stat().st_size)

    def test_a_name_with_an_impossible_date_is_skipped(self):
        path = self.root / 'morpheus-backup-20261399T999999Z.tar.gz'
        path.write_bytes(b'x')
        self.assertIsNone(deploys.describe_backup(path))

    def test_an_unfinished_backup_is_skipped(self):
        path = self.root / f'{NAME}.part'
        path.write_bytes(b'x')
        self.assertIsNone(deploys.describe_backup(path))


class ExtractTests(_Folder, SimpleTestCase):
    def test_the_dump_comes_out_of_the_archive(self):
        into = self.root / 'out'
        into.mkdir()
        dump = restore.extract_dump(_archive(self.root), into)
        self.assertEqual(dump.read_bytes(), b'DUMP')

    def test_an_archive_without_a_database_is_refused(self):
        with self.assertRaisesMessage(restore.RestoreError, 'holds no database'):
            restore.extract_dump(_archive(self.root, members={'media.tar': b'm'}), self.root)

    def test_a_file_that_is_not_an_archive_is_refused(self):
        junk = self.root / NAME
        junk.write_bytes(b'not a tar')
        with self.assertRaisesMessage(restore.RestoreError, 'cannot be read'):
            restore.extract_dump(junk, self.root)

    def test_a_dump_that_is_a_link_is_refused(self):
        path = self.root / NAME
        with tarfile.open(path, 'w:gz') as tar:
            link = tarfile.TarInfo('db.dump')
            link.type = tarfile.SYMTYPE
            link.linkname = '/etc/passwd'
            tar.addfile(link)
        with self.assertRaisesMessage(restore.RestoreError, 'not a backup'):
            restore.extract_dump(path, self.root)


class DatabaseRestoreTests(SimpleTestCase):
    def test_pg_restore_runs_all_or_nothing_with_the_store_s_credentials(self):
        done = subprocess.CompletedProcess([], 0, '', '')
        with patch('core.restore.subprocess.run', return_value=done) as run:
            restore._pg_restore(
                {'NAME': 'shop', 'HOST': 'db', 'PORT': 5432, 'USER': 'u', 'PASSWORD': 'p'},
                Path('/tmp/db.dump'),
            )
        argv = run.call_args.args[0]
        self.assertEqual(
            argv,
            [
                'pg_restore', '--clean', '--if-exists', '--no-owner', '--no-acl',
                '--single-transaction', '--exit-on-error',
                '-h', 'db', '-p', '5432', '-U', 'u', '-d', 'shop', '/tmp/db.dump',
            ],
        )
        self.assertEqual(run.call_args.kwargs['env']['PGPASSWORD'], 'p')

    def test_a_failed_pg_restore_says_nothing_changed(self):
        failed = subprocess.CompletedProcess([], 1, '', 'pg_restore: error: one\npg_restore: two\n')
        with (
            patch('core.restore.subprocess.run', return_value=failed),
            self.assertRaisesMessage(restore.RestoreError, 'nothing changed'),
        ):
            restore._pg_restore({'NAME': 'shop'}, Path('/tmp/db.dump'))

    def test_a_sqlite_database_file_is_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, dump = Path(tmp) / 'db.sqlite3', Path(tmp) / 'db.dump'
            db.write_bytes(b'OLD')
            dump.write_bytes(b'NEW')
            with patch('django.db.connections.close_all'):
                restore._sqlite_restore({'NAME': str(db)}, dump)
            self.assertEqual(db.read_bytes(), b'NEW')
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ['db.dump', 'db.sqlite3'])

    def test_an_in_memory_database_is_refused(self):
        with self.assertRaisesMessage(restore.RestoreError, 'in-memory'):
            restore._sqlite_restore({'NAME': 'file:memorydb_default?mode=memory&cache=shared'}, Path('x'))

    def test_no_sessions_to_end_on_sqlite(self):
        self.assertEqual(restore.end_other_sessions(), 0)


class ClearCacheTests(SimpleTestCase):
    def test_only_the_cache_s_own_keys_go_when_redis_backs_it(self):
        # The cache shares its Redis database with Celery's queue.
        fake = Mock(spec=['delete_pattern', 'clear'])
        with patch('django.core.cache.cache', fake):
            restore.clear_cache()
        fake.delete_pattern.assert_called_once_with('*')
        fake.clear.assert_not_called()

    def test_a_cache_without_patterns_is_cleared(self):
        fake = Mock(spec=['clear'])
        with patch('django.core.cache.cache', fake):
            restore.clear_cache()
        fake.clear.assert_called_once_with()


class BackUpCurrentTests(_Folder, SimpleTestCase):
    def test_the_current_data_goes_to_its_own_folder_three_kept(self):
        def fake(command, **kwargs):
            command.archive_path = Path(kwargs['dest']) / BEFORE

        with patch('core.restore.call_command', side_effect=fake) as call:
            self.assertEqual(restore.back_up_current(), BEFORE)
        kwargs = call.call_args.kwargs
        self.assertEqual(kwargs['dest'], str(self.root / 'pre-restore'))
        self.assertEqual(kwargs['keep'], 3)
        self.assertTrue(kwargs['no_media'])
        self.assertEqual(kwargs['label'], 'before-restore')


class RunTests(_Folder, TestCase):
    def setUp(self):
        super().setUp()
        row = StoreSettings.objects.first() or StoreSettings.objects.create()
        row.store_name = 'Test Shop'
        row.save()
        self.archive = _archive(self.root / 'pre-deploy')
        self.calls = Mock()
        for name, target, kwargs in (
            ('backup', 'core.restore.back_up_current', {'return_value': BEFORE}),
            ('end', 'core.restore.end_other_sessions', {'return_value': 2}),
            ('restore', 'core.restore.restore_database', {}),
            ('plan', 'core.deploys.migration_plan', {'return_value': ([], False)}),
        ):
            patcher = patch(target, **kwargs)
            self.calls.attach_mock(patcher.start(), name)
            self.addCleanup(patcher.stop)

    def _restore(self, *extra, confirm='Test Shop'):
        out = io.StringIO()
        call_command('morph_restore', str(self.archive), '--confirm', confirm, *extra, stdout=out)
        return out.getvalue()

    def test_the_current_data_is_saved_first_then_restored_and_recorded(self):
        output = self._restore('--by', 'boss')
        self.assertEqual([c[0] for c in self.calls.mock_calls], ['backup', 'end', 'restore', 'plan'])
        last = restore.last()
        self.assertEqual(last['state'], 'done')
        self.assertEqual((last['file'], last['kind'], last['by']), (NAME, 'pre-deploy', 'boss'))
        self.assertEqual(last['pre_restore'], BEFORE)
        self.assertEqual(last['taken_at'], '2026-10-20T01:21:46+00:00')
        self.assertFalse(restore.is_running())
        self.assertIn(f'Restored {NAME}', output)

    def test_the_wrong_name_changes_nothing(self):
        with self.assertRaisesMessage(CommandError, 'Test Shop'):
            self._restore(confirm='Other Shop')
        self.assertEqual(self.calls.mock_calls, [])
        self.assertIsNone(restore.last())
        self.assertFalse(restore.running_path().exists())

    def test_spaces_around_the_name_are_fine_but_case_counts(self):
        self._restore(confirm='  Test Shop  ')
        self.assertEqual(restore.last()['state'], 'done')
        with self.assertRaises(CommandError):
            self._restore(confirm='test shop')

    def test_no_restore_while_another_runs(self):
        restore.start({'file': 'other'})
        with self.assertRaisesMessage(CommandError, 'Another restore'):
            self._restore()
        self.assertEqual(self.calls.mock_calls, [])
        self.assertTrue(restore.is_running())

    def test_an_archive_without_a_database_never_closes_the_store(self):
        self.archive = _archive(self.root / 'pre-deploy', members={'media.tar': b'm'})
        with self.assertRaisesMessage(CommandError, 'holds no database'):
            self._restore()
        self.assertFalse(restore.running_path().exists())
        self.assertEqual(self.calls.mock_calls, [])

    def test_a_failed_restore_changes_nothing_and_says_so(self):
        self.calls.restore.side_effect = restore.RestoreError(
            'The database could not be restored, so nothing changed: boom'
        )
        with self.assertRaisesMessage(CommandError, 'boom'):
            self._restore()
        self.assertEqual(restore.last()['state'], 'failed')
        self.assertIn('boom', restore.last()['error'])
        self.assertFalse(restore.is_running())

    def test_a_failed_backup_of_the_current_data_stops_the_restore(self):
        self.calls.backup.side_effect = subprocess.CalledProcessError(1, ['pg_dump'])
        with self.assertRaisesMessage(CommandError, 'could not be backed up first'):
            self._restore()
        self.calls.restore.assert_not_called()
        self.assertEqual(restore.last()['state'], 'failed')

    def test_cached_values_are_dropped_after_a_restore(self):
        cache.set('restore-test-key', 'old')
        self._restore()
        self.assertIsNone(cache.get('restore-test-key'))

    def test_a_backup_older_than_the_code_names_what_it_lacks(self):
        self.calls.plan.return_value = (['shop.0002_extra'], False)
        output = self._restore()
        self.assertEqual(restore.last()['missing'], ['shop.0002_extra'])
        self.assertIn('shop.0002_extra', output)
        self.assertIn('Redeploy', output)

    def test_the_web_workers_reload_after_a_restore_started_from_the_page(self):
        with patch('core.restore.os.kill') as kill:
            self._restore('--reload-web', '4242')
        kill.assert_called_once_with(4242, signal.SIGHUP)

    def test_nothing_reloads_after_a_failed_restore(self):
        self.calls.restore.side_effect = restore.RestoreError('nothing changed: boom')
        with patch('core.restore.os.kill') as kill, self.assertRaises(CommandError):
            self._restore('--reload-web', '4242')
        kill.assert_not_called()

    def test_the_store_is_closed_while_the_data_is_replaced(self):
        seen = []
        self.calls.restore.side_effect = lambda dump: seen.append(restore.is_running())
        self._restore()
        self.assertEqual(seen, [True])
```

- [ ] **Step 2: Run them to see them fail**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_morph_restore`
Expected: ERROR or FAIL. `module 'core.deploys' has no attribute 'describe_backup'`, `module 'core.restore' has no attribute 'extract_dump'`, and `Unknown command: 'morph_restore'`.

- [ ] **Step 3: Add `describe_backup` to `core/deploys.py`**

Replace the body of `latest_predeploy_backup` and add the parser it now uses. An impossible date used to raise `ValueError` out of `strptime`, which made the page 500 (a deferred minor from release 1):

```python
def describe_backup(path: Path) -> dict | None:
    """A backup file as ``{name, size, taken_at, label}``, from its name and size;
    None for anything that is not a finished backup."""
    match = _ARCHIVE.match(path.name)
    if not match:
        return None
    try:
        taken_at = datetime.strptime(match.group(1), '%Y%m%dT%H%M%SZ').replace(tzinfo=UTC)
        size = path.stat().st_size
    except (OSError, ValueError):
        return None
    return {'name': path.name, 'size': size, 'taken_at': taken_at, 'label': match.group(2) or ''}


def latest_predeploy_backup() -> dict | None:
    """The newest backup in the pre-deploy folder, as ``describe_backup`` gives it;
    None when there is none."""
    for path in sorted(predeploy_dir().glob('morpheus-backup-*.tar.gz'), reverse=True):
        info = describe_backup(path)
        if info:
            return info
    return None
```

- [ ] **Step 4: Append the engine to `core/restore.py`**

Add these imports to the module's import block, keeping it sorted:

```python
import logging
import shutil
import signal
import subprocess
import tarfile
import tempfile
from datetime import UTC, datetime

from django.core.management import call_command

from core.management.commands.morph_backup import Command as BackupCommand
```

Add these constants under `HEARTBEAT`, and the logger:

```python
#: Backups of the data a restore replaced, kept in ``pre-restore/``.
PRE_RESTORE_KEEP = 3
#: The folders the restore screen lists, under MORPHEUS_BACKUP_DIR.
KINDS = {'nightly': '', 'pre-deploy': 'pre-deploy', 'pre-restore': 'pre-restore'}

logger = logging.getLogger('morpheus.restore')
```

Then append at the end of the module:

```python
def _now() -> str:
    return datetime.now(UTC).isoformat(timespec='seconds')


def kind_of(archive: Path) -> str:
    """Which list ``archive`` belongs to; '' for a file anywhere else."""
    root = deploys.backup_root().resolve()
    parent = Path(archive).resolve().parent
    for kind, sub in KINDS.items():
        if parent == (root / sub if sub else root):
            return kind
    return ''


def extract_dump(archive: Path, into: Path) -> Path:
    """The backup's database dump, extracted into ``into``."""
    try:
        with tarfile.open(archive) as tar:
            member = tar.getmember('db.dump')
            if not member.isfile():
                raise RestoreError(f'{archive.name} is not a backup this store can restore.')
            tar.extract(member, into, filter='data')
    except KeyError as exc:
        raise RestoreError(f'{archive.name} holds no database.') from exc
    except (OSError, tarfile.TarError) as exc:
        raise RestoreError(f'{archive.name} cannot be read: {exc}') from exc
    return into / 'db.dump'


def end_other_sessions() -> int:
    """End every other session on this database, so the restore gets its locks."""
    from django.db import connection

    if connection.vendor != 'postgresql':
        return 0
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity '
            'WHERE datname = current_database() AND pid <> pg_backend_pid()'
        )
        return cursor.fetchone()[0]


def restore_database(dump: Path) -> None:
    from django.conf import settings

    db = settings.DATABASES['default']
    engine = db.get('ENGINE') or ''
    if 'postgres' in engine or 'psycopg' in engine:
        _pg_restore(db, dump)
    elif 'sqlite' in engine:
        _sqlite_restore(db, dump)
    else:
        raise RestoreError(f'This store cannot restore a {engine} database.')


def _pg_restore(db: dict, dump: Path) -> None:
    cmd = [
        'pg_restore', '--clean', '--if-exists', '--no-owner', '--no-acl',
        '--single-transaction', '--exit-on-error',
    ]
    env = os.environ.copy()
    if db.get('HOST'):
        cmd += ['-h', db['HOST']]
    if db.get('PORT'):
        cmd += ['-p', str(db['PORT'])]
    if db.get('USER'):
        cmd += ['-U', db['USER']]
    if db.get('PASSWORD'):
        env['PGPASSWORD'] = db['PASSWORD']
    cmd += ['-d', db['NAME'], str(dump)]
    done = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)  # noqa: S603
    if done.returncode:
        detail = ' '.join((done.stderr or '').strip().splitlines()[-3:])
        raise RestoreError(f'The database could not be restored, so nothing changed: {detail}')


def _sqlite_restore(db: dict, dump: Path) -> None:
    from django.db import connections

    name = str(db.get('NAME') or '')
    if not name or name == ':memory:' or 'mode=memory' in name:
        raise RestoreError('An in-memory database cannot be restored.')
    target = Path(name)
    connections.close_all()
    partial = target.with_name(f'{target.name}.restoring')
    shutil.copy2(dump, partial)
    partial.replace(target)


def clear_cache() -> None:
    """Drop every cached value: each describes the data the restore replaced. Only
    the cache's own keys: the cache shares its Redis database with Celery's
    queue, which cache.clear() would empty too."""
    from django.core.cache import cache

    if hasattr(cache, 'delete_pattern'):
        cache.delete_pattern('*')
    else:
        cache.clear()  # LocMem (tests, local development) holds nothing else


def back_up_current(stdout=None) -> str:
    """Back the current database up into pre-restore/; the new file's name."""
    command = BackupCommand(stdout=stdout, stderr=stdout)
    call_command(
        command,
        dest=str(deploys.backup_root() / 'pre-restore'),
        keep=PRE_RESTORE_KEEP,
        no_media=True,
        label='before-restore',
    )
    return command.archive_path.name


def run(archive: Path, *, confirm: str, by: str = '', stdout=None) -> dict:
    """Restore ``archive`` over the store's database; the outcome, as last.json
    keeps it. Raises RestoreError, with the store open and untouched, when it
    will not start: the name does not match, the file is no backup, or another
    restore runs. Once it has started, a failure is the outcome's ``error``."""
    from core.utils.site import store_name

    archive = Path(archive)
    name = store_name()
    if not name or (confirm or '').strip() != name:
        raise RestoreError(f"To confirm, type the store's name exactly: {name}")
    if not archive.is_file():
        raise RestoreError(f'There is no backup at {archive}.')
    info = deploys.describe_backup(archive)
    with tempfile.TemporaryDirectory(prefix='morph-restore-') as tmp:
        dump = extract_dump(archive, Path(tmp))
        outcome = {
            'state': 'running',
            'file': archive.name,
            'kind': kind_of(archive),
            'taken_at': info['taken_at'].isoformat() if info else '',
            'by': by,
            'started_at': _now(),
        }
        start(outcome)
        with heartbeat(running_path()):
            outcome.update(_restore(dump, stdout))
        outcome['finished_at'] = _now()
        finish(outcome)
    # Loud on purpose: a restore replaced the store's data.
    logger.warning('restore %s: %s', outcome['state'], outcome)
    return outcome


def _restore(dump: Path, stdout) -> dict:
    try:
        pre_restore = back_up_current(stdout)
    except Exception as exc:  # noqa: BLE001 — reported to the person; nothing changed
        return {
            'state': 'failed',
            'error': f'The current data could not be backed up first, so nothing was restored: {exc}',
        }
    try:
        end_other_sessions()
        restore_database(dump)
    except Exception as exc:  # noqa: BLE001 — all or nothing: nothing changed
        return {'state': 'failed', 'pre_restore': pre_restore, 'error': str(exc)}
    clear_cache()
    try:
        missing = deploys.migration_plan()[0]
    except Exception:  # noqa: BLE001 — the restore itself is done
        logger.exception('restore: could not read the migration plan')
        missing = []
    return {'state': 'done', 'pre_restore': pre_restore, 'missing': missing}


def reload_web(pid: int) -> None:
    """Ask the gunicorn master for fresh workers. Each process keeps app
    settings in memory, and fresh ones read the restored settings."""
    try:
        os.kill(pid, signal.SIGHUP)
    except OSError:
        logger.warning('restore: could not reload the web workers (pid %s)', pid, exc_info=True)
```

- [ ] **Step 5: Write `core/management/commands/morph_restore.py`**

```python
"""`python manage.py morph_restore <backup> --confirm "<store name>"`: put the
database back as a backup made by morph_backup has it, all or nothing. The
current data is backed up into pre-restore/ first, and every page says
"restoring" while it runs. The engine is core/restore.py, which the restore
screen on Settings → Version & updates runs too.
"""

from __future__ import annotations

import getpass
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core import restore


class Command(BaseCommand):
    help = 'Restore the database from a morph_backup archive (all or nothing).'

    def add_arguments(self, parser):
        parser.add_argument('archive', help='A morpheus-backup-*.tar.gz file.')
        parser.add_argument('--confirm', required=True, help="The store's name, typed out.")
        parser.add_argument('--by', default='', help='Who asked for the restore, for the record.')
        parser.add_argument(
            '--reload-web',
            type=int,
            default=0,
            metavar='PID',
            help='The gunicorn master to reload once the restore is done.',
        )

    def handle(self, *args, **options):
        try:
            outcome = restore.run(
                Path(options['archive']),
                confirm=options['confirm'],
                by=options['by'] or _whoami(),
                stdout=self.stdout,
            )
        except restore.RestoreError as exc:
            raise CommandError(str(exc)) from exc
        if outcome['state'] != 'done':
            raise CommandError(outcome.get('error') or 'The restore failed and changed nothing.')
        if options['reload_web']:
            restore.reload_web(options['reload_web'])
        self.stdout.write(
            self.style.SUCCESS(
                f"Restored {outcome['file']}. The data from before it is in "
                f"pre-restore/{outcome['pre_restore']}."
            )
        )
        if outcome.get('missing'):
            self.stdout.write(
                self.style.WARNING(
                    'This backup lacks migrations the running version needs: '
                    f"{', '.join(outcome['missing'])}. Redeploy the store, or run "
                    'manage.py migrate, to apply them.'
                )
            )
        self.stdout.write('Restart the worker and beat, so background jobs read the restored data.')


def _whoami() -> str:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 — a missing login name only blanks the record
        return ''
```

- [ ] **Step 6: Run the tests to see them pass**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_morph_restore core.tests.test_restore_gate core.tests.test_running_release`
Expected: `OK`. `test_running_release` still passes on the refactored `latest_predeploy_backup`.

- [ ] **Step 7: Lint, then commit**

Run: `ruff check core/restore.py core/deploys.py core/management/commands/morph_restore.py core/tests/test_morph_restore.py && ruff format --check core/restore.py core/deploys.py core/management/commands/morph_restore.py core/tests/test_morph_restore.py`
Expected: `All checks passed!`, and every file already formatted. Run `ruff format` on any file it names, then check again.

```bash
git add core/restore.py core/deploys.py core/management/commands/morph_restore.py core/tests/test_morph_restore.py
git commit -m "feat(restore): manage.py morph_restore, all or nothing" -m "Backs the current data up into pre-restore/ (three kept), closes the store, ends the other database sessions, runs pg_restore --clean --if-exists --no-owner --no-acl --single-transaction --exit-on-error, drops the cache's own keys (never cache.clear(): Celery's queue shares the Redis database) and records the outcome. It never migrates: a backup older than the code names the migrations it lacks. deploys.describe_backup is the one parser for backup names, and skips an impossible date." -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: What a restore loses

**Files:**
- Modify: `core/hooks.py` (after `HEALTH_CHECKS` in `MorpheusEvents`)
- Modify: `core/restore.py` (append `losses`)
- Modify: `plugins/installed/orders/app.py`, `plugins/installed/customers/app.py`, `plugins/installed/catalog/app.py`
- Test: `core/tests/test_restore_losses.py`, `plugins/installed/orders/tests/test_restore_losses.py`

**Interfaces:**
- Consumes: `hook_registry.filter(event, value, **kwargs)`, which skips a failing handler and skips inactive apps' handlers.
- Produces: `MorpheusEvents.RESTORE_LOSSES = 'restore.losses'` (a filter: value `list[dict]`, kwargs `since=datetime`); `core.restore.losses(since) -> list[{'label': str, 'count': int}]`, with zero counts left out. The labels are `'orders placed'`, `'customers signed up'` and `'products added or changed'`.

- [ ] **Step 1: Write the failing tests**

`core/tests/test_restore_losses.py`:

```python
"""What restoring a backup loses, as each app counts it (safe deploys, part 4)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from core import restore
from plugins.installed.catalog.models import Product


class RestoreLossesTests(TestCase):
    def test_customers_and_products_since_the_backup_are_counted(self):
        since = timezone.now()
        User = get_user_model()
        early = User.objects.create_user(username='early', email='e@x.io', password='pw')
        User.objects.filter(pk=early.pk).update(date_joined=since - timedelta(hours=1))
        User.objects.create_user(username='late', email='l@x.io', password='pw')
        User.objects.create_user(username='crew', email='c@x.io', password='pw', is_staff=True)
        Product.objects.create(
            name='Radio', slug='radio-r3', sku='R3-1', price=Money(Decimal('29.00'), 'USD'), status='active'
        )
        rows = {row['label']: row['count'] for row in restore.losses(since)}
        self.assertEqual(rows['customers signed up'], 1)
        self.assertEqual(rows['products added or changed'], 1)

    def test_nothing_changed_nothing_listed(self):
        self.assertEqual(restore.losses(timezone.now() + timedelta(days=1)), [])
```

`plugins/installed/orders/tests/test_restore_losses.py`:

```python
"""Orders count the orders a restore would lose (RESTORE_LOSSES)."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from core import restore
from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.inventory.models import StockLevel, Warehouse
from plugins.installed.orders.models import Order
from plugins.installed.orders.services import CartService, OrderService

_ADDR = {
    'first_name': 'A',
    'last_name': 'B',
    'address_line_1': '1 St',
    'city': 'Town',
    'postal_code': '11000',
    'country': 'US',
}


class OrdersLostTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Widget', slug='widget-r3', sku='R3-W', status='active', price=10
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, name='Std', sku='R3-WV', price=Money(Decimal('10.00'), 'USD')
        )
        warehouse = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)
        StockLevel.objects.create(variant=self.variant, warehouse=warehouse, quantity=10, reserved_quantity=0)

    def _place(self, session_key):
        cart = CartService.get_or_create_cart(session_key=session_key)
        CartService.add_item(cart, str(self.product.id), quantity=1, variant_id=str(self.variant.id))
        return OrderService.create_from_cart(cart, 'buyer@example.com', _ADDR, _ADDR)

    def test_orders_placed_since_the_backup_are_counted(self):
        since = timezone.now()
        old = self._place('s-old')
        Order.objects.filter(pk=old.pk).update(placed_at=since - timezone.timedelta(hours=2))
        self._place('s-new')
        rows = {row['label']: row['count'] for row in restore.losses(since)}
        self.assertEqual(rows['orders placed'], 1)
```

- [ ] **Step 2: Run them to see them fail**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_restore_losses plugins.installed.orders.tests.test_restore_losses`
Expected: ERROR, `module 'core.restore' has no attribute 'losses'`.

- [ ] **Step 3: Declare the event in `core/hooks.py`**

After the `HEALTH_CHECKS = 'health.checks'` line in `MorpheusEvents`:

```python
    # RESTORE_LOSSES — filter, value=list[dict], kwargs: since=datetime (when the
    #                  backup was made). The restore screen asks each app what a
    #                  restore would replace; each appends ``{'label': str,
    #                  'count': int}`` for its own records since then (orders:
    #                  orders placed; customers: customers signed up; catalog:
    #                  products added or changed). Read by core.restore.losses.
    RESTORE_LOSSES = 'restore.losses'
```

- [ ] **Step 4: Append `losses` to `core/restore.py`**

```python
def losses(since: datetime) -> list[dict]:
    """What restoring a backup made at ``since`` replaces, as each app counts it
    (RESTORE_LOSSES): ``[{'label': 'orders placed', 'count': 4}, …]``, without
    zero counts. A failing app is skipped by the bus, and the others still count."""
    from core.hooks import MorpheusEvents, hook_registry

    rows = hook_registry.filter(MorpheusEvents.RESTORE_LOSSES, [], since=since) or []
    return [row for row in rows if isinstance(row, dict) and row.get('count')]
```

- [ ] **Step 5: Each app counts its own**

`plugins/installed/orders/app.py`: in `ready()`, next to the `HEALTH_CHECKS` line:

```python
        self.register_hook(events.RESTORE_LOSSES, self.on_restore_losses, priority=10)
```

and a method beside `on_health_checks`:

```python
    def on_restore_losses(self, value, since=None, **kwargs):
        """RESTORE_LOSSES: the orders placed since the backup was made."""
        from plugins.installed.orders.models import Order  # noqa: PLC0415

        value.append(
            {'label': 'orders placed', 'count': Order.objects.filter(placed_at__gt=since).count()}
        )
        return value
```

`plugins/installed/customers/app.py`: in `ready()`:

```python
        self.register_hook(events.RESTORE_LOSSES, self.on_restore_losses, priority=20)
```

and the method:

```python
    def on_restore_losses(self, value, since=None, **kwargs):
        """RESTORE_LOSSES: the customers who signed up since the backup was made."""
        from django.contrib.auth import get_user_model  # noqa: PLC0415

        joined = get_user_model().objects.filter(date_joined__gt=since, is_staff=False)
        value.append({'label': 'customers signed up', 'count': joined.count()})
        return value
```

`plugins/installed/catalog/app.py`: in `ready()`:

```python
        self.register_hook(events.RESTORE_LOSSES, self.on_restore_losses, priority=30)
```

and the method:

```python
    def on_restore_losses(self, value, since=None, **kwargs):
        """RESTORE_LOSSES: the products added or changed since the backup was made."""
        from plugins.installed.catalog.models import Product  # noqa: PLC0415

        changed = Product.objects.filter(updated_at__gt=since)
        value.append({'label': 'products added or changed', 'count': changed.count()})
        return value
```

- [ ] **Step 6: Run the tests to see them pass**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_restore_losses plugins.installed.orders.tests.test_restore_losses core.tests.test_hook_disable_gating`
Expected: `OK`.

- [ ] **Step 7: Lint, check the boundaries, commit**

Run: `ruff check core plugins/installed/orders plugins/installed/customers plugins/installed/catalog && .venv/bin/python scripts/check_core_boundary.py && .venv/bin/python scripts/check_plugin_boundary.py`
Expected: `All checks passed!`, then both guards print `OK … no new ones`.

```bash
git add core/hooks.py core/restore.py plugins/installed/orders/app.py plugins/installed/customers/app.py plugins/installed/catalog/app.py core/tests/test_restore_losses.py plugins/installed/orders/tests/test_restore_losses.py
git commit -m "feat(restore): each app counts what a restore would lose" -m "RESTORE_LOSSES (a filter, kwargs since): orders count the orders placed, customers the customers who signed up, catalog the products added or changed since the backup. core.restore.losses reads it and leaves out zero counts; core imports none of them." -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: The Backups card and the restore screen

**Files:**
- Modify: `core/restore.py` (append `backups`, `find`, `spawn`)
- Modify: `core/deploys.py` (`running_release` gains `last_restore`)
- Create: `plugins/installed/release_notes/restore_views.py`, `plugins/installed/release_notes/restore_urls.py`
- Create: `plugins/installed/release_notes/templates/release_notes/_backups_card.html`, `plugins/installed/release_notes/templates/release_notes/restore_confirm.html`
- Modify: `plugins/installed/release_notes/app.py` (`ready()`), `plugins/installed/release_notes/views.py` (`version_updates`), `plugins/installed/release_notes/templates/release_notes/index.html`
- Test: `plugins/installed/release_notes/tests/test_restore_page.py`, `core/tests/test_running_release.py` (one test added)

**Interfaces:**
- Consumes: Tasks 1–3 (`last`, `stalled`, `KINDS`, `losses`, `RestoreError`, `run` via the command); `deploys.describe_backup`; `core.utils.site.store_name`.
- Produces:
  - `core.restore.backups() -> list[dict]` with the keys `name`, `size`, `taken_at`, `label`, `kind` and `path`, newest first;
  - `find(kind, name) -> dict | None`;
  - `spawn(archive, *, confirm, by, reload_pid=0) -> None`;
  - `running_release()['last_restore']`;
  - the URL name `restore:confirm` (`/dashboard/restore/<kind>/<name>/`).

- [ ] **Step 1: Write the failing tests**

`plugins/installed/release_notes/tests/test_restore_page.py`:

```python
"""Restoring a backup from Settings → Version & updates (safe deploys, part 4)."""

from __future__ import annotations

import io
import json
import os
import tarfile
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.template.loader import get_template
from django.test import TestCase

from core import restore
from core.models import StoreSettings

VERSION_PAGE = '/dashboard/apps/release_notes/version/'
PRE = 'morpheus-backup-20261020T012146Z-v0.118.0-e1198af.tar.gz'
NIGHTLY = 'morpheus-backup-20261020T033000Z.tar.gz'
BEFORE = 'morpheus-backup-20261019T120000Z-before-restore.tar.gz'


def _write_archive(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, 'w:gz') as tar:
        info = tarfile.TarInfo('db.dump')
        info.size = 4
        tar.addfile(info, io.BytesIO(b'DUMP'))


class RestorePageTests(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        env = patch.dict(os.environ, {'MORPHEUS_BACKUP_DIR': tmp.name})
        env.start()
        self.addCleanup(env.stop)
        _write_archive(self.root / 'pre-deploy' / PRE)
        _write_archive(self.root / NIGHTLY)
        _write_archive(self.root / 'pre-restore' / BEFORE)
        (self.root / 'pre-deploy' / f'{PRE}.part').write_bytes(b'x')
        (self.root / 'notes.txt').write_text('x')
        row = StoreSettings.objects.first() or StoreSettings.objects.create()
        row.store_name = 'Test Shop'
        row.save()
        User = get_user_model()
        self.boss = User.objects.create_user(
            username='boss', email='b@x.io', password='pw', is_staff=True, is_superuser=True
        )
        self.crew = User.objects.create_user(username='crew', email='c@x.io', password='pw', is_staff=True)

    def _confirm_url(self, kind='pre-deploy', name=PRE):
        return f'/dashboard/restore/{kind}/{name}/'

    def test_the_templates_compile(self):
        get_template('release_notes/_backups_card.html')
        get_template('release_notes/restore_confirm.html')

    def test_superusers_see_every_backup_newest_first(self):
        self.client.force_login(self.boss)
        html = self.client.get(VERSION_PAGE).content.decode()
        self.assertIn('data-testid="backups"', html)
        self.assertLess(html.index(NIGHTLY), html.index(PRE))
        self.assertLess(html.index(PRE), html.index(BEFORE))
        for label in ('Nightly', 'Before an update', 'Before a restore'):
            self.assertIn(label, html)
        self.assertNotIn(f'{PRE}.part', html)
        self.assertNotIn('notes.txt', html)

    def test_staff_who_are_not_superusers_see_no_backups(self):
        self.client.force_login(self.crew)
        self.assertNotIn('data-testid="backups"', self.client.get(VERSION_PAGE).content.decode())
        self.assertEqual(self.client.get(self._confirm_url()).status_code, 404)

    def test_only_this_store_s_backup_folder_is_listed(self):
        # Staff and Linda can change the backups app's folder setting; a restore
        # trusts its file completely, so only MORPHEUS_BACKUP_DIR is listed.
        from plugins.registry import app_registry

        other = tempfile.TemporaryDirectory()
        self.addCleanup(other.cleanup)
        stray = 'morpheus-backup-20261020T100000Z.tar.gz'
        _write_archive(Path(other.name) / stray)
        app_registry.get('backups').set_config('backup_dir', other.name)
        self.client.force_login(self.boss)
        self.assertNotIn(stray, self.client.get(VERSION_PAGE).content.decode())
        self.assertEqual(self.client.get(self._confirm_url('nightly', stray)).status_code, 404)

    def test_names_outside_the_list_are_not_found(self):
        self.client.force_login(self.boss)
        for kind, name in (
            ('pre-deploy', f'{PRE}.part'),
            ('nightly', PRE),
            ('media', PRE),
            ('pre-deploy', 'morpheus-backup-20200101T000000Z.tar.gz'),
        ):
            self.assertEqual(self.client.get(self._confirm_url(kind, name)).status_code, 404, (kind, name))

    def test_the_screen_names_what_the_restore_loses(self):
        self.client.force_login(self.boss)
        rows = [{'label': 'orders placed', 'count': 4}, {'label': 'customers signed up', 'count': 2}]
        with patch('core.restore.losses', return_value=rows):
            response = self.client.get(self._confirm_url())
        self.assertContains(response, '4 orders placed and 2 customers signed up')
        self.assertContains(response, 'Test Shop')
        self.assertContains(response, 'hx-boost="false"')

    def test_the_screen_says_so_when_nothing_was_counted(self):
        self.client.force_login(self.boss)
        with patch('core.restore.losses', return_value=[]):
            response = self.client.get(self._confirm_url())
        self.assertContains(response, 'No orders, customers or products have changed since then')

    def test_the_wrong_name_starts_nothing(self):
        self.client.force_login(self.boss)
        with patch('core.restore.spawn') as spawn:
            response = self.client.post(self._confirm_url(), {'confirm': 'test shop'})
        self.assertEqual(response.status_code, 400)
        # The message is a variable, so its apostrophes are escaped: match words without one.
        self.assertContains(response, 'Type it exactly as it is shown', status_code=400)
        spawn.assert_not_called()

    def test_the_right_name_starts_the_restore_in_the_background(self):
        self.client.force_login(self.boss)
        with patch('core.restore.spawn') as spawn:
            response = self.client.post(self._confirm_url(), {'confirm': ' Test Shop '})
        self.assertRedirects(response, VERSION_PAGE, fetch_redirect_response=False)
        spawn.assert_called_once_with(
            self.root / 'pre-deploy' / PRE, confirm=' Test Shop ', by='boss', reload_pid=0
        )

    def test_under_gunicorn_the_web_workers_reload_afterwards(self):
        self.client.force_login(self.boss)
        with patch('core.restore.spawn') as spawn:
            self.client.post(self._confirm_url(), {'confirm': 'Test Shop'}, SERVER_SOFTWARE='gunicorn/26.0')
        self.assertEqual(spawn.call_args.kwargs['reload_pid'], os.getppid())

    def test_a_restore_that_cannot_start_says_why(self):
        self.client.force_login(self.boss)
        with patch('core.restore.spawn', side_effect=OSError('no python')):
            response = self.client.post(self._confirm_url(), {'confirm': 'Test Shop'})
        self.assertContains(response, 'could not start', status_code=400)

    def test_the_page_shows_how_the_last_restore_ended(self):
        restore.state_dir().mkdir(parents=True)
        (restore.state_dir() / 'last.json').write_text(
            json.dumps({
                'state': 'done', 'file': PRE, 'kind': 'pre-deploy', 'by': 'boss',
                'finished_at': '2026-10-20T17:05:00+00:00', 'pre_restore': BEFORE,
                'missing': ['shop.0002_extra'],
            })
        )
        self.client.force_login(self.boss)
        html = self.client.get(VERSION_PAGE).content.decode()
        self.assertIn('data-testid="restore-last"', html)
        self.assertIn('shop.0002_extra', html)
        self.assertIn('Redeploy the store', html)
        (restore.state_dir() / 'last.json').write_text(
            json.dumps({'state': 'failed', 'file': PRE, 'error': 'pg_restore said no'})
        )
        html = self.client.get(VERSION_PAGE).content.decode()
        self.assertIn('failed and changed nothing', html)
        self.assertIn('pg_restore said no', html)

    def test_a_restore_that_stopped_is_reported(self):
        path = restore.running_path()
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'state': 'running', 'file': PRE, 'started_at': '2026-10-20T17:00:00+00:00'}))
        stamp = time.time() - restore.STALE_AFTER - 5
        os.utime(path, (stamp, stamp))
        self.client.force_login(self.boss)
        self.assertContains(self.client.get(VERSION_PAGE), 'did not report back')
```

Add to `core/tests/test_running_release.py`, in `RunningReleaseTests(_BackupFolderMixin, TestCase)`:

```python
    def test_the_last_restore_is_part_of_the_release_record(self):
        folder = self.root / 'restore'
        folder.mkdir()
        (folder / 'last.json').write_text('{"state": "done", "file": "x.tar.gz"}')
        self.assertEqual(running_release()['last_restore'], {'state': 'done', 'file': 'x.tar.gz'})
```

- [ ] **Step 2: Run them to see them fail**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test plugins.installed.release_notes.tests.test_restore_page core.tests.test_running_release`
Expected: FAIL or ERROR. `TemplateDoesNotExist: release_notes/_backups_card.html`, 404s for the confirm URLs, and `KeyError: 'last_restore'`.

- [ ] **Step 3: Append the listing and the background start to `core/restore.py`**

Add `import sys` to the imports, then append:

```python
def backups() -> list[dict]:
    """The backups the restore screen offers, newest first: nightly, made before
    an update that changed the database, and made before a restore. Only from
    MORPHEUS_BACKUP_DIR: staff and Linda can change the backups app's folder
    setting, and a restore trusts its file completely."""
    found = []
    root = deploys.backup_root()
    for kind, sub in KINDS.items():
        folder = root / sub if sub else root
        for path in folder.glob('morpheus-backup-*.tar.gz'):
            info = deploys.describe_backup(path)
            if info:
                found.append({**info, 'kind': kind, 'path': path})
    return sorted(found, key=lambda b: b['taken_at'], reverse=True)


def find(kind: str, name: str) -> dict | None:
    """The listed backup a screen names by kind and file name, never by path."""
    for backup in backups():
        if backup['kind'] == kind and backup['name'] == name:
            return backup
    return None


def spawn(archive: Path, *, confirm: str, by: str, reload_pid: int = 0) -> None:
    """Start ``manage.py morph_restore`` detached from the request, so it outlives
    the request and the worker that served it. Its output goes to
    restore/restore.log."""
    from django.conf import settings

    folder = state_dir()
    folder.mkdir(parents=True, exist_ok=True)
    argv = [
        sys.executable, str(Path(settings.BASE_DIR) / 'manage.py'), 'morph_restore',
        str(archive), '--confirm', confirm, '--by', by,
    ]
    if reload_pid:
        argv += ['--reload-web', str(reload_pid)]
    with open(folder / 'restore.log', 'ab') as log:
        subprocess.Popen(  # noqa: S603 — a fixed command, no shell
            argv,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            cwd=settings.BASE_DIR,
            start_new_session=True,
        )
```

Add a test for `spawn` to `core/tests/test_morph_restore.py` (class `SpawnTests(_Folder, SimpleTestCase)`):

```python
class SpawnTests(_Folder, SimpleTestCase):
    def test_the_restore_runs_detached_with_the_page_s_answers(self):
        with patch('core.restore.subprocess.Popen') as popen:
            restore.spawn(self.root / NAME, confirm='Test Shop', by='boss', reload_pid=42)
        argv = popen.call_args.args[0]
        self.assertEqual(
            argv[2:],
            ['morph_restore', str(self.root / NAME), '--confirm', 'Test Shop', '--by', 'boss', '--reload-web', '42'],
        )
        self.assertTrue(popen.call_args.kwargs['start_new_session'])
        self.assertTrue((self.root / 'restore' / 'restore.log').exists())
```

- [ ] **Step 4: `running_release` carries the last restore**

In `core/deploys.py`, `running_release()` imports `from core import restore` inside the function, next to its other imports, and adds one key to the returned dict:

```python
        'last_restore': restore.last(),
```

- [ ] **Step 5: Write the screen**

`plugins/installed/release_notes/restore_urls.py`:

```python
"""The restore screen, mounted at /dashboard/restore/ by ReleaseNotesPlugin.ready()."""

from django.urls import path

from plugins.installed.release_notes import restore_views

app_name = 'restore'

urlpatterns = [
    path('<str:kind>/<str:name>/', restore_views.restore_backup, name='confirm'),
]
```

`plugins/installed/release_notes/restore_views.py`:

```python
"""Restoring a backup from Settings → Version & updates: superusers only.

The screen names the backup, says what restoring it replaces (each app counts
its own records since the backup was made) and what happens, and asks for the
store's name. Then it starts ``manage.py morph_restore`` in the background
(``core.restore.spawn``) and goes back to Version & updates. Linda has no tool
for this: a restore replaces everything saved since the backup.
"""

from __future__ import annotations

import os

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import redirect, render

from core import restore
from core.utils.site import store_name

KIND_LABELS = {
    'nightly': 'Nightly',
    'pre-deploy': 'Before an update',
    'pre-restore': 'Before a restore',
}
VERSION_PAGE = '/dashboard/apps/release_notes/version/'


def _join(parts: list[str]) -> str:
    if len(parts) < 2:
        return ''.join(parts)
    return ', '.join(parts[:-1]) + ' and ' + parts[-1]


@staff_member_required
def restore_backup(request, kind: str, name: str):
    if not request.user.is_superuser:
        raise Http404
    backup = restore.find(kind, name)
    if backup is None:
        raise Http404
    error = ''
    if request.method == 'POST':
        typed = request.POST.get('confirm', '')
        if typed.strip() != store_name():
            error = "That isn't the store's name. Type it exactly as it is shown."
        else:
            # Under gunicorn this worker's parent is the master, which the restore
            # reloads once it is done (each process keeps settings in memory).
            server = request.META.get('SERVER_SOFTWARE', '')
            reload_pid = os.getppid() if server.startswith('gunicorn') else 0
            try:
                restore.spawn(
                    backup['path'], confirm=typed, by=request.user.get_username(), reload_pid=reload_pid
                )
            except OSError as exc:
                error = f'The restore could not start: {exc}'
            else:
                messages.success(
                    request,
                    'The restore has started. Until it finishes, everyone sees a "restoring" page.',
                )
                return redirect(VERSION_PAGE)
    lost = _join([f"{row['count']} {row['label']}" for row in restore.losses(backup['taken_at'])])
    return render(
        request,
        'release_notes/restore_confirm.html',
        {
            'backup': backup,
            'kind_label': KIND_LABELS[backup['kind']],
            'lost': lost,
            'store_name': store_name(),
            'error': error,
            'version_page': VERSION_PAGE,
        },
        status=400 if error else 200,
    )
```

`plugins/installed/release_notes/templates/release_notes/restore_confirm.html`:

```django
{% extends "admin_dashboard/base.html" %}
{% block title %}Restore a backup · Morpheus{% endblock %}

{% block content %}
<div class="mx-auto space-y-6">
  <div>
    <h1 class="text-xl font-semibold tracking-tight">Restore a backup</h1>
    <p class="text-sm text-[color:var(--text-muted)]">{{ kind_label }} backup from {{ backup.taken_at|date:"j M Y, H:i" }}{% if backup.label %} ({{ backup.label }}){% endif %}, {{ backup.size|filesizeformat }}.</p>
  </div>

  <div class="card card-padded text-sm space-y-3" data-testid="restore-losses">
    <p class="font-semibold">Everything saved since {{ backup.taken_at|date:"j M Y, H:i" }} is replaced.{% if lost %} That includes {{ lost }}.{% endif %}</p>
    {% if not lost %}<p class="text-[color:var(--text-muted)]">No orders, customers or products have changed since then. Anything else saved since is replaced too.</p>{% endif %}
    <ul class="list-disc pl-5 space-y-1">
      <li>The store first backs up its data as it is now, so you can undo this from "Before a restore" on Version &amp; updates.</li>
      <li>While it runs, a minute or two, everyone sees a "restoring" page, you included.</li>
      <li>Photos and other files are not touched.</li>
      <li>You may need to sign in again afterwards.</li>
    </ul>
  </div>

  <form method="post" class="card card-padded space-y-3" hx-boost="false">
    {% csrf_token %}
    <label class="block text-sm" for="restore-confirm">To confirm, type the store's name: <strong>{{ store_name }}</strong></label>
    <input id="restore-confirm" name="confirm" type="text" class="input w-full" autocomplete="off" required>
    {% if error %}<p class="text-sm text-[color:var(--danger)]" data-testid="restore-error">{{ error }}</p>{% endif %}
    <div class="flex items-center gap-2">
      <button type="submit" class="btn btn-danger"><i data-lucide="history" class="h-4 w-4"></i> Restore this backup</button>
      <a class="btn btn-ghost" href="{{ version_page }}">Cancel</a>
    </div>
  </form>
</div>
{% endblock %}
```

`plugins/installed/release_notes/templates/release_notes/_backups_card.html`:

```django
{% comment %}
The backups this store can be restored from (safe deploys, part 4), for
superusers only. Each row opens its restore screen, which says what the restore
replaces and asks for the store's name.
{% endcomment %}
<div class="card overflow-hidden" data-testid="backups">
  <div class="card-padded border-b border-[color:var(--border)]">
    <h2 class="font-semibold text-sm">Backups</h2>
    <p class="text-sm text-[color:var(--text-muted)]">Put the store's data back as it was when one of these was made. Photos and other files are not touched.</p>
  </div>
  {% if restore_stalled %}
  <div class="card-padded text-sm border-b border-[color:var(--border)]" data-testid="restore-stalled">
    A restore of {{ restore_stalled.file|default:"a backup" }}{% if restore_stalled.started_at %}, started {{ restore_stalled.started_at|date:"j M Y, H:i" }},{% endif %} did not report back. A restore changes everything or nothing, so the store holds either that backup's data or what it had before. Check, and restore again if you need to.
  </div>
  {% elif restore_last %}
  <div class="card-padded text-sm border-b border-[color:var(--border)]" data-testid="restore-last">
    {% if restore_last.state == 'done' %}
      Last restore: {{ restore_last.file }}{% if restore_last.by %}, by {{ restore_last.by }}{% endif %}{% if restore_last.finished_at %}, finished {{ restore_last.finished_at|date:"j M Y, H:i" }}{% endif %}. The data from before it is listed under "Before a restore".
      {% if restore_last.missing %}<br>The running version needs database changes this backup does not have: {{ restore_last.missing|join:", " }}. Redeploy the store to apply them.{% endif %}
      <br>Restart the store's worker and beat, so background jobs read the restored data.
    {% else %}
      The last restore, {{ restore_last.file }}, failed and changed nothing: {{ restore_last.error }}
    {% endif %}
  </div>
  {% endif %}
  {% if backups %}
  <table class="morph-table morph-table-zebra">
    <thead><tr><th>Made</th><th>Kind</th><th>Version</th><th>Size</th><th></th></tr></thead>
    <tbody>
      {% for b in backups %}
      <tr>
        <td>{{ b.taken_at|date:"j M Y, H:i" }}</td>
        <td>{% if b.kind == 'nightly' %}Nightly{% elif b.kind == 'pre-deploy' %}Before an update{% else %}Before a restore{% endif %}</td>
        <td class="font-mono text-xs">{{ b.label|default:"—" }}</td>
        <td>{{ b.size|filesizeformat }}</td>
        <td class="text-right"><a class="btn btn-ghost text-sm" href="{% url 'restore:confirm' b.kind b.name %}">Restore…</a></td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <div class="card-padded text-sm text-[color:var(--text-muted)]">No backups on this store yet.</div>
  {% endif %}
</div>
```

- [ ] **Step 6: Mount the screen and show the card**

`plugins/installed/release_notes/app.py`, in `ready()`, after the Help `register_urls`:

```python
        self.register_urls(
            'plugins.installed.release_notes.restore_urls',
            prefix='dashboard/restore/',
            namespace='restore',
        )
```

`plugins/installed/release_notes/views.py`, `version_updates`. Add `from datetime import datetime` at the top and `from core import restore` beside the function's other core imports. Add a helper above the view:

```python
def _with_times(record: dict | None) -> dict | None:
    """A restore record with its ISO times as datetimes, for the |date filter."""
    if not record:
        return record
    out = dict(record)
    for key in ('started_at', 'finished_at', 'taken_at'):
        try:
            out[key] = datetime.fromisoformat(out[key]) if out.get(key) else None
        except (TypeError, ValueError):
            out[key] = None
    return out
```

Then extend the context:

```python
            'show_backups': request.user.is_superuser,
            'backups': restore.backups() if request.user.is_superuser else [],
            'restore_last': _with_times(restore.last()) if request.user.is_superuser else None,
            'restore_stalled': _with_times(restore.stalled()) if request.user.is_superuser else None,
```

`plugins/installed/release_notes/templates/release_notes/index.html`, directly after `{% include "admin_dashboard/_updater_card.html" %}`:

```django
  {% if show_backups %}{% include "release_notes/_backups_card.html" %}{% endif %}
```

- [ ] **Step 7: Run the tests to see them pass**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test plugins.installed.release_notes core.tests.test_running_release core.tests.test_morph_restore plugins.installed.admin_dashboard.tests.test_page_width plugins.installed.admin_dashboard.tests.test_navigation`
Expected: `OK`.

- [ ] **Step 8: Lint, then commit**

Run: `ruff check core plugins/installed/release_notes && ruff format --check core plugins/installed/release_notes`
Expected: `All checks passed!`, and everything already formatted. Run `ruff format` on any file it names, then check again.

```bash
git add core/restore.py core/deploys.py core/tests/test_running_release.py core/tests/test_morph_restore.py plugins/installed/release_notes
git commit -m "feat(restore): restore a backup from Settings → Version & updates" -m "Superusers get a Backups card (nightly, before an update, before a restore; only MORPHEUS_BACKUP_DIR) and a restore screen at /dashboard/restore/<kind>/<file>/ that says what the restore replaces, asks for the store's name and starts morph_restore detached; under gunicorn it then reloads the web workers. The card shows how the last restore ended, or that one did not report back. running_release carries the last restore, so Linda's updates.status sees it; Linda has no restore tool." -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Docs, release, deploy and a live rehearsal

**Files:**
- Modify: `plugins/installed/release_notes/help.md`, `CLAUDE.md`, `docs/UPDATING.md`, `docs/OPERATIONS_RUNBOOK.md`, `docs/ARCHITECTURE.md`
- Modify (by `manage.py release`): `morph/settings.py` (`MORPHEUS_VERSION`), `docs/RELEASE_NOTES.md`

**Interfaces:**
- Consumes: everything above.
- Produces: v0.120.0 on all four stores.

- [ ] **Step 1: The app's help**

In `plugins/installed/release_notes/help.md`, add to `## Common tasks`:

```markdown
- Restore a backup: a superuser opens [Version & updates](page:version), picks one under Backups, reads what it will replace, and types the store's name.
```

and append to `## Good to know`:

```markdown

A restore puts all the store's data back as it was when the backup was made, or changes nothing if it fails. The store first backs up its data as it is, so a restore can be undone the same way, and shows everyone a "restoring" page while it runs. Linda cannot restore a backup: it replaces everything saved since.
```

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test plugins.installed.release_notes`
Expected: `OK`. The guide stays inside 60–400 body words with no jargon, and the `page:version` marker resolves.

- [ ] **Step 2: The convention, in `CLAUDE.md`**

After the "a migration leaves the previous release working (v0.119.0)" convention, add:

```markdown
**Convention — a restore is all or nothing, and the store closes while it runs (v0.120.0).**
`manage.py morph_restore <backup> --confirm "<store name>"` and the superuser-only restore screen
(Settings → Version & updates → Backups, `/dashboard/restore/<kind>/<file>/`) run one engine,
`core/restore.py`. In order, it:
- backs the current data up into `pre-restore/` (three kept);
- ends every other database session;
- runs `pg_restore --clean --if-exists --no-owner --no-acl --single-transaction --exit-on-error`;
- drops the cache.

Five traps:
1. The closed sign is a file on the backups volume (`restore/running.json`, read by
   `RestoreGateMiddleware` before any middleware that touches the database), never a row or a
   cache key: the restore replaces the one and clears the other. A heartbeat keeps the file fresh,
   so a restore that dies reopens the store 90 s later.
2. The cache shares its Redis database with Celery's queue (`REDIS_URL` for both, no prefix), so
   never `cache.clear()` outside tests. `delete_pattern('*')` drops only the cache's keys.
3. Ending the sessions kills every reused connection, so `CONN_HEALTH_CHECKS` is on: a dead
   connection is replaced instead of failing a request.
4. Each process keeps app settings in memory. A restore from the screen reloads the web workers
   (SIGHUP to the gunicorn master), and the result asks for a worker and beat restart.
5. A restore never runs migrations: someone who restored to undo a bad migration would run it
   again. A backup older than the code lists what it lacks, and a redeploy applies it.

The screen lists only files under `MORPHEUS_BACKUP_DIR`, never the backups app's folder setting,
which staff and Linda can change. It takes a kind and a file name, never a path. Each app counts
what a restore loses through `RESTORE_LOSSES`. Linda has no restore tool by design, and
`updates.status` shows the last restore. Guarded by `core/tests/test_restore_gate.py`,
`test_morph_restore.py`, `test_restore_losses.py` and
`release_notes/tests/test_restore_page.py`.
```

- [ ] **Step 3: The procedures**

`docs/UPDATING.md`: replace the line `- a restore command and page;` in "Still to come" with:

```markdown
- ~~a restore command and page~~: shipped in v0.120.0. `manage.py morph_restore <backup>
  --confirm "<store name>"` restores a backup all or nothing, after backing the current
  data up; a superuser starts the same restore from Settings → Version & updates
  (`core/restore.py`);
```

`docs/OPERATIONS_RUNBOOK.md`: replace the whole "**The real restore** is by hand until `morph_restore` ships…" bullet, including its three numbered steps, with:

```markdown
- **Restoring** (v0.120.0) puts the whole database back as a backup has it, all or
  nothing, after backing the current data up into `/app/backups/pre-restore/` (three
  kept), so a restore can be undone the same way. A superuser starts it from Settings →
  Version & updates → Backups → Restore…, which says what will be replaced and asks for
  the store's name. From a shell:
  `docker exec -it <web> python manage.py morph_restore /app/backups/pre-deploy/<file> --confirm "<store name>"`.
  - While it runs, every page answers 503 "restoring" (`/healthz` excepted).
  - It never runs migrations. When the backup is older than the running code, the result
    names the migrations it lacks, and a redeploy applies them. If one of them is why you
    restored, put the previous version back first.
  - Afterwards, restart the worker and beat (Coolify → Restart), so background jobs read
    the restored data. A restore started from the screen reloads the web workers itself;
    one started from a shell needs the web restarted too.
  - The outcome is in `/app/backups/restore/last.json`, and the output of a screen-started
    restore is in `restore.log` beside it.
  - A restore that is killed (a deploy replaced the container) stops closing the store 90 s
    later. It changed everything or nothing.
```

`docs/ARCHITECTURE.md`, under "Django middleware stack:" in "Request lifecycle", as the first item:

```text
   - RestoreGateMiddleware (first, before anything reads the database): every
     page answers 503 "restoring" while a backup is being restored (core/restore.py)
```

- [ ] **Step 4: Verify the docs commit is clean, then commit**

Run: `git add plugins/installed/release_notes/help.md CLAUDE.md docs/UPDATING.md docs/OPERATIONS_RUNBOOK.md docs/ARCHITECTURE.md && git commit -m "docs: safe deploys, part 3 (restoring a backup)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"`
Expected: `[pre-commit] all checks passed.`

- [ ] **Step 5: The full suite and CI's gates**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress' .venv/bin/python manage.py test > <workspace>/suite.log 2>&1; grep -E '^Ran |^OK|^FAILED' <workspace>/suite.log`
Expected: `OK (skipped=10)`, with about 5,220 tests.

Run: `ruff check . -q && ruff format --check . | tail -1 && .venv/bin/python manage.py check && .venv/bin/python manage.py makemigrations --check --dry-run && .venv/bin/python scripts/check_core_boundary.py && .venv/bin/python scripts/check_plugin_boundary.py && .venv/bin/python scripts/check_plugin_standard.py`
Expected: every gate is clean. There are no migrations, and both boundary guards print `no new ones`.

- [ ] **Step 6: Cut v0.120.0**

Run with the full-suite environment variables exported:

```bash
.venv/bin/python manage.py release --minor "Restore a backup from the dashboard" \
  -m "A superuser can now put the store's data back as it was when a backup was made. Settings → Version & updates lists the nightly backups, those made before an update and those made before a restore. Before anything happens, it says what will be replaced, such as the orders placed and the customers who signed up since, and asks for the store's name." \
  -m "A restore changes everything or nothing. The store first backs up its data as it is, so a restore can be undone the same way, and shows everyone a \"restoring\" page while it runs." \
  -m "Fixed: when the database restarts, or a restore ends its connections, the next pages no longer fail. Each connection is checked before it is reused." \
  --commit
git commit --amend -q -m "$(git log -1 --format=%B)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
.venv/bin/python manage.py release --check
```

Expected: `v0.119.0 -> v0.120.0`, and `release --check` prints `✓ version v0.120.0 in sync with RELEASE_NOTES`. The release-2 gate finds no new migration.

- [ ] **Step 7: Merge and push (deploys all four stores)**

```bash
git checkout main && git merge --ff-only feat/safe-deploys-3 && git push origin main && git branch -d feat/safe-deploys-3
SMOKE_DEADLINE_SECS=2400 bash scripts/deploy_smoke.sh
gh run list --limit 6 --json workflowName,headSha,status,conclusion
```

Expected: `SMOKE OK — every store serves v0.120.0`, and `ci` and `release` succeed on the pushed commit.

- [ ] **Step 8: Live checks on Supernatural, the store's data untouched**

Write `<scratchpad>/live_restore_check.py` (settings, the card, one restore screen by GET only, and the gate in this one process):

```python
"""v0.120.0 live checks. Never POSTs: no restore runs on the store's own data."""
import os
import tempfile
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY, get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.test import Client

from core import restore

stack = settings.MIDDLEWARE
print('LIVE health checks on:', settings.DATABASES['default'].get('CONN_HEALTH_CHECKS'))
print('LIVE gate right after SecurityMiddleware:',
      stack.index('core.restore.RestoreGateMiddleware') == stack.index('django.middleware.security.SecurityMiddleware') + 1)
hosts = [h.lstrip('.') for h in settings.ALLOWED_HOSTS if '.' in h and '*' not in h and 'localhost' not in h]
host = hosts[0] if hosts else 'localhost'
user = get_user_model().objects.filter(is_superuser=True, is_active=True).first()
session = SessionStore()
session[SESSION_KEY] = str(user.pk)
session[BACKEND_SESSION_KEY] = settings.AUTHENTICATION_BACKENDS[0]
session[HASH_SESSION_KEY] = user.get_session_auth_hash()
session.create()
try:
    client = Client(secure=True, HTTP_HOST=host, HTTP_X_FORWARDED_PROTO='https')
    client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key
    page = client.get('/dashboard/apps/release_notes/version/')
    listed = restore.backups()
    print('LIVE version page', page.status_code, 'card:', b'data-testid="backups"' in page.content,
          'backups:', len(listed), [b['kind'] for b in listed][:8])
    newest = next((b for b in listed if b['kind'] == 'pre-deploy'), None)
    if newest:
        screen = client.get(f"/dashboard/restore/pre-deploy/{newest['name']}/")
        body = screen.content.decode()
        at = body.find('Everything saved since')
        print('LIVE restore screen', screen.status_code, body[at:at + 240].replace('\n', ' '))
finally:
    session.delete()
with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'MORPHEUS_BACKUP_DIR': tmp}):
    client = Client(secure=True, HTTP_HOST=host, HTTP_X_FORWARDED_PROTO='https')
    restore.start({'file': 'live-check', 'state': 'running'})
    closed = client.get('/')
    restore.finish({'state': 'done', 'file': 'live-check'})
    opened = client.get('/')
    print('LIVE gate closed:', closed.status_code, b'Restoring the store' in closed.content, '| open:', opened.status_code)
```

Run it: `~/.ssh/tetra-ssh.sh -- scp -q <scratchpad>/live_restore_check.py root@tetra.imbamarketing.com:/tmp/ && ~/.ssh/tetra-ssh.sh 'c=$(docker ps --format "{{.Names}}" | grep "^web-z10xg4j7yq8x1htipw12a368" | head -1); docker exec -i "$c" python manage.py shell < /tmp/live_restore_check.py 2>&1 | grep LIVE; rm -f /tmp/live_restore_check.py'`
Expected:
- `LIVE health checks on: True`;
- `LIVE gate right after SecurityMiddleware: True`;
- `LIVE version page 200 card: True backups: N`, with N ≥ 1;
- `LIVE restore screen 200 Everything saved since …`;
- `LIVE gate closed: 503 True | open:` followed by anything but 503.

Write `<scratchpad>/r3_scratch.py`, the scratch copy, run in the web container. `REHEARSE=setup|peek|drop`:

```python
"""Safe deploys release 3 rehearsal: a scratch copy of the store, never the store's own database."""
import os
import subprocess
import tarfile
import tempfile

from django.conf import settings

db = settings.DATABASES['default']
env = dict(os.environ, PGPASSWORD=db['PASSWORD'])
conn = ['-h', db['HOST'], '-p', str(db['PORT'] or 5432), '-U', db['USER']]
SCRATCH = 'restore_check_r3'
mode = os.environ['REHEARSE']


def psql(sql):
    done = subprocess.run(['psql', *conn, '-d', SCRATCH, '-tAc', sql], env=env, check=True, capture_output=True, text=True)
    return done.stdout.strip()


if mode == 'setup':
    subprocess.run(['createdb', *conn, SCRATCH], env=env, check=True)
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(os.environ['REHEARSE_BACKUP']) as tar:
            tar.extract('db.dump', tmp, filter='data')
        done = subprocess.run(['pg_restore', *conn, '-d', SCRATCH, '--no-owner', '--no-acl', f'{tmp}/db.dump'], env=env, capture_output=True, text=True)
        print('REHEARSE scratch loaded, exit', done.returncode)
    first = psql('select id from catalog_product order by id limit 1')
    psql(f"update catalog_product set name = 'REHEARSAL CHANGED' where id = '{first}'")
    print('REHEARSE renamed one product; products:', psql('select count(*) from catalog_product'))
elif mode == 'peek':
    print('REHEARSE renamed products:', psql("select count(*) from catalog_product where name = 'REHEARSAL CHANGED'"),
          '| products:', psql('select count(*) from catalog_product'))
elif mode == 'drop':
    subprocess.run(['dropdb', *conn, SCRATCH], env=env, check=True)
    print('REHEARSE scratch database dropped')
```

Write `<scratchpad>/r3_rehearse.sh`, run on tetra as `~/.ssh/tetra-ssh.sh 'bash -s' < <scratchpad>/r3_rehearse.sh` after `scp`-ing `r3_scratch.py` to `/tmp/`:

```bash
set -u
uuid=z10xg4j7yq8x1htipw12a368
web=$(docker ps --format '{{.Names}}' | grep "^web-$uuid" | head -1)
img=$(docker inspect -f '{{.Config.Image}}' "$web")
# The store's own network: on a shared one, a service name can resolve to another store.
net=$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$web" | tr ' ' '\n' | grep "$uuid" | head -1)
work=$(mktemp -d /tmp/r3-XXXXXX); chmod 700 "$work"; mkdir "$work/vol"; chmod 777 "$work/vol"
trap 'docker exec -u 0 "$web" rm -f /tmp/r3_scratch.py; rm -rf "$work"; rm -f /tmp/r3_scratch.py' EXIT
latest=$(docker exec "$web" sh -c 'ls -1 /app/backups/pre-deploy/morpheus-backup-*.tar.gz | tail -1')
file=$(basename "$latest")
docker cp "$web:$latest" "$work/vol/$file"; chmod 644 "$work/vol/$file"
docker exec "$web" env | grep -Ev '^(DATABASE_URL|MORPHEUS_BACKUP_DIR|REDIS_URL|HOSTNAME|HOME|PATH)=' > "$work/env"; chmod 600 "$work/env"
scratch_url=$(docker exec "$web" python -c "import os, urllib.parse as u; p = u.urlsplit(os.environ['DATABASE_URL']); print(u.urlunsplit(p._replace(path='/restore_check_r3')))")
name=$(docker exec "$web" python manage.py shell -c "from core.utils.site import store_name; print(store_name())" 2>/dev/null | tail -1)
echo "REHEARSE network=$net backup=$file store=$name"
docker cp /tmp/r3_scratch.py "$web:/tmp/r3_scratch.py"
scratch() { docker exec -e REHEARSE="$1" -e REHEARSE_BACKUP="$latest" "$web" sh -c 'python manage.py shell < /tmp/r3_scratch.py' 2>&1 | grep REHEARSE; }
oneoff() {
  start=$(date +%s)
  docker run --rm --network "$net" --env-file "$work/env" -e DATABASE_URL="$scratch_url" \
    -e MORPHEUS_BACKUP_DIR=/rehearsal -e REDIS_URL=redis://127.0.0.1:1/0 -v "$work/vol:/rehearsal" \
    "$img" python manage.py morph_restore "/rehearsal/$file" --confirm "$1" > "$work/out.txt" 2>&1
  echo "REHEARSE morph_restore exit $? in $(( $(date +%s) - start ))s"; grep -v '^\[MORPHEUS\]' "$work/out.txt" | tail -4
}
scratch setup
echo 'REHEARSE --- wrong name'; oneoff 'wrong'; scratch peek
echo 'REHEARSE --- right name'; oneoff "$name"; scratch peek
echo "REHEARSE outcome: $(cat "$work/vol/restore/last.json" 2>/dev/null)"
echo "REHEARSE pre-restore: $(ls "$work/vol/pre-restore/" 2>/dev/null)"
scratch drop
```

Expected:
- **Wrong name:** `exit 1` with "type the store's name exactly", then `renamed products: 1`.
- **Right name:** `exit 0`, `Restored <file>`, and a warning that names `core.0024_deployevent`. That backup was made before v0.118.0 migrated, so the missing-migration report is exercised for real.
- **After it:** `renamed products: 0`, the same product count, a `…-before-restore.tar.gz` under `pre-restore/`, and a `last.json` with `"state": "done"`.
- **Clean up:** `scratch database dropped`. The temp folder and its env file are removed when the script exits.

Record the restore's duration in the ledger.

- [ ] **Step 9: Record and close**

- Update memory: `releases-2026-10-19.md` gets "release 3 shipped as v0.120.0", the rehearsal timings and the deferred minors, and the next step is release 4. Update the `MEMORY.md` line too.
- Delete this plan's workspace once the final review is clean.
