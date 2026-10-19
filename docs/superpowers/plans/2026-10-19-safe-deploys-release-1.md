# Safe deploys, release 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every deploy that changes the database backs it up first and stops before migrating if the backup fails. Each deploy is recorded. Settings → Version & updates and Linda say what the store runs and stop offering update buttons that cannot work on a built image.

**Architecture:** The web container's entrypoint runs one new command, `manage.py safe_migrate`, where it ran `migrate`. That command:

1. Asks Django's migration executor what is pending.
2. When something is pending, runs `morph_backup --no-media --keep 5` into `<MORPHEUS_BACKUP_DIR>/pre-deploy/`. The file is named after the version and commit being deployed. A failed backup raises `CommandError` before anything is migrated.
3. Calls `migrate`.
4. Writes a `DeployEvent` row.

A marker file in the container's `/tmp` marks the backup step as done, so a crash loop never backs up a half-migrated database. A new `core/deploys.py` holds the helpers and the page's data. A shared template partial gives both update pages one honest updater card.

**Deviation from the spec, on purpose:** the spec names two commands around `migrate`: `predeploy` before it, and a record step after. Measured on Supernatural's web container (2026-10-19), every `manage.py` start costs about 2.8 s, and the store answers 503 while the web container boots. Two extra commands would add about 5.5 s to the 503 of every deploy. One command does the same three steps in one process, so a deploy with nothing to migrate boots as fast as today. The behaviour the spec asks for is unchanged.

**Tech Stack:** Python 3.12, Django 6.1, PostgreSQL 16 (`pg_dump -Fc`), Django templates with the dashboard's Tailwind classes, POSIX `sh` entrypoint, Coolify Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-19-safe-deploys-design.md`. This plan is release 1 of its "Order of delivery": parts 1 and 5. Part 5 also mentions showing "any rollback"; that comes with release 4, which is the release that detects rollbacks. Releases 2–4 (the CI migration check, restore, automatic rollback) get their own plans.

## Global Constraints

- The pre-deploy backup is the database only: `morph_backup --no-media --dest <backup dir>/pre-deploy --keep 5`, labelled with the version being deployed, in its own folder, so deploys never rotate out the nightly copies.
- With nothing to migrate there is no backup, so most deploys stay as fast as today.
- A failed backup exits non-zero, and nothing is migrated.
- `DeployEvent` holds the version, the commit when known (`SOURCE_COMMIT`, which Coolify sets at runtime), the time, the pre-deploy backup's file, and the migrations applied.
- The page shows the running version, its commit and deploy time, and the latest pre-deploy backup. Without `.git`, the "Update now" and per-app buttons give way to one line: `This store updates when a new version is released.`
- Linda's `updates.status` says the same thing. `updates.apply` answers that it can't run here instead of failing.
- The backup folder is the `MORPHEUS_BACKUP_DIR` env var (default `/app/backups`), never the backups app's setting. Staff and Linda can write settings, and a backup in a folder the web server serves is public.
- Copy staff read is in plain words: say "update", never "migration". The assistant is called Linda. Help guides never use the words in `plugins/app_help.py:JARGON`.
- `core/` imports nothing from `plugins.installed.*` (`scripts/check_core_boundary.py`, baseline 0).
- The release is `v0.118.0` (MINOR), made with `manage.py release`, never by hand.
- Python 3.12 and Django 6.1. Use ruff 0.15.8 (`.venv/bin/ruff`) with line length 100 and single quotes.
- Tests run with `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test <labels>`. The full suite also needs `MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress'`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Work on branch `feat/safe-deploys-1` in `/Users/magnetoid/coding/morph`. Owner rule: one working folder, so no worktree. Pushing `main` deploys all four stores: push once, in Task 6.

## Review Focus

1. **A crash loop with migrations still pending.** If `migrate` fails after the first boot's backup, the container restarts and must not back up again. A second backup would copy a half-migrated database and push the real copy out of the five. Pinned by Task 1, `test_a_restart_after_a_failed_migrate_does_not_back_up_again`.
2. **A backup that dies half way (a full disk).** It must leave no file that looks like a good backup, and nothing may be migrated. Pinned by Task 1, `test_a_backup_that_fails_while_writing_leaves_no_archive` and `test_a_failed_backup_stops_before_migrating_and_leaves_nothing`.
3. **A brand-new database.** A self-hoster's first boot has nothing to protect and maybe no backup folder; it must not need a backup to boot. Pinned by Task 1, `test_a_new_database_has_nothing_to_back_up`.
4. **A plain restart of the same deploy.** It must not add a `DeployEvent` or move the page's "Installed" time. A failure to record must never keep the store down. Pinned by Task 2, `test_a_restart_of_the_same_deploy_adds_nothing` and `test_a_failed_record_does_not_stop_the_store`.
5. **A store with no deploy record and no backup folder yet.** This includes a folder holding files that are not backups. The page and Linda must still work. Pinned by Task 3, `test_none_when_the_folder_does_not_exist`, `test_files_that_are_not_backups_are_ignored` and `test_before_any_record_the_install_time_is_blank`.

---

### Task 1: Back up the database before migrating

**Files:**
- Modify: `core/management/commands/morph_backup.py`. Add a `--label` option and an `archive_path` attribute, and delete a half-written archive.
- Create: `core/deploys.py`. It holds the paths, the commit, the label, the migration plan and the marker file.
- Create: `core/management/commands/safe_migrate.py`
- Modify: `scripts/docker-entrypoint.sh`. Change the header comment and `run_migrations` (lines 3–9 and 38–41).
- Modify: `docker-compose.yml`, in the web service's `volumes` (line 125).
- Test: `core/tests/test_safe_migrate.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces (later tasks rely on these exact names):
  - `core.deploys.BACKUP_KEEP: int` (5)
  - `core.deploys.HANDOFF: pathlib.Path`
  - `core.deploys.backup_root() -> Path` and `core.deploys.predeploy_dir() -> Path`
  - `core.deploys.current_commit() -> str`: a lowercase 7–40 hex sha, or `''`
  - `core.deploys.deploy_label() -> str`, such as `v0.118.0-fe80f3f`
  - `core.deploys.migration_plan() -> tuple[list[str], bool]`: the pending `"app.name"` list, and whether no migration was ever applied
  - `core.deploys.read_handoff() -> dict | None`, `write_handoff(data: dict) -> None` and `clear_handoff() -> None`. The marker's shape is `{'backup': str, 'migrations': list[str]}`.
  - `morph_backup --label TEXT`. Its `Command.archive_path: Path` attribute is set by `handle`.
  - `core.management.commands.safe_migrate.Command`, with methods `_back_up_first()`, `_migrate()` and `_record()`.
  - Test helpers `core.tests.test_safe_migrate._DeployEnvMixin` and `_fake_dump`, which Task 2 imports.

- [ ] **Step 1: Branch**

```bash
cd /Users/magnetoid/coding/morph && git checkout -b feat/safe-deploys-1
```

- [ ] **Step 2: Write the failing tests**

Create `core/tests/test_safe_migrate.py`:

```python
"""manage.py safe_migrate: a database backup before any migration (safe deploys, part 1).

The web container's entrypoint runs it in place of `migrate` on every boot
(scripts/docker-entrypoint.sh). Spec:
docs/superpowers/specs/2026-10-19-safe-deploys-design.md.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.test import SimpleTestCase, TestCase

from core import deploys
from core.management.commands.morph_backup import Command as BackupCommand
from core.management.commands.safe_migrate import Command as SafeMigrate

_REPO = Path(settings.BASE_DIR)


def _fake_dump(self, workdir):
    # The test database is in-memory SQLite, which morph_backup cannot copy. The
    # rest of the backup (archive, name, label, pruning) runs for real.
    (Path(workdir) / 'db.dump').write_bytes(b'dump')


def _broken_dump(self, workdir):
    raise subprocess.CalledProcessError(1, ['pg_dump'])


class _DeployEnvMixin:
    """A temporary backup folder and marker file, and a known commit."""

    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        env = {'MORPHEUS_BACKUP_DIR': str(self.root / 'backups'), 'SOURCE_COMMIT': 'a' * 40}
        for patcher in (
            patch.dict(os.environ, env),
            patch('core.deploys.HANDOFF', self.root / 'predeploy.json'),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def pend(self) -> str:
        """Mark core's newest migration unapplied, so `migrate` would run it.
        The test's transaction puts the row back."""
        leaf = next(
            name for app, name in MigrationLoader(connection).graph.leaf_nodes() if app == 'core'
        )
        MigrationRecorder(connection).record_unapplied('core', leaf)
        return f'core.{leaf}'

    def archives(self) -> list[str]:
        return sorted(p.name for p in (self.root / 'backups' / 'pre-deploy').glob('*.tar.gz'))


class MigrationPlanTests(_DeployEnvMixin, TestCase):
    def test_a_migrated_database_has_nothing_pending(self):
        self.assertEqual(deploys.migration_plan(), ([], False))

    def test_an_unapplied_migration_is_pending(self):
        name = self.pend()
        self.assertEqual(deploys.migration_plan(), ([name], False))


class SafeMigrateTests(_DeployEnvMixin, TestCase):
    def run_command(self, dump=_fake_dump, migrate=None):
        out = io.StringIO()
        with (
            patch.object(BackupCommand, '_dump_database', dump),
            patch.object(SafeMigrate, '_migrate', side_effect=migrate) as migrated,
        ):
            call_command('safe_migrate', stdout=out)
        return out.getvalue(), migrated

    def test_nothing_to_migrate_takes_no_backup(self):
        out, migrated = self.run_command()
        self.assertIn('No migrations to run', out)
        migrated.assert_called_once_with()
        self.assertEqual(self.archives(), [])

    def test_the_database_is_backed_up_before_migrating(self):
        self.pend()
        order = []

        def dump(command, workdir):
            order.append('backup')
            _fake_dump(command, workdir)

        self.run_command(dump=dump, migrate=lambda: order.append('migrate'))
        self.assertEqual(order, ['backup', 'migrate'])
        [archive] = self.archives()
        version = re.escape(settings.MORPHEUS_VERSION)
        self.assertRegex(archive, rf'^morpheus-backup-\d{{8}}T\d{{6}}Z-{version}-aaaaaaa\.tar\.gz$')
        with tarfile.open(self.root / 'backups' / 'pre-deploy' / archive) as tar:
            self.assertEqual(tar.getnames(), ['db.dump'])  # the database only, no media

    def test_the_last_five_are_kept_and_the_nightly_ones_untouched(self):
        folder = self.root / 'backups' / 'pre-deploy'
        folder.mkdir(parents=True)
        for day in range(1, 7):
            (folder / f'morpheus-backup-2020010{day}T000000Z-v0.1.{day}.tar.gz').write_bytes(b'o')
        nightly = self.root / 'backups' / 'morpheus-backup-20200101T000000Z.tar.gz'
        nightly.write_bytes(b'n')
        self.pend()
        self.run_command()
        names = self.archives()
        self.assertEqual(len(names), 5)
        self.assertNotIn('morpheus-backup-20200101T000000Z-v0.1.1.tar.gz', names)
        self.assertNotIn('morpheus-backup-20200102T000000Z-v0.1.2.tar.gz', names)
        self.assertTrue(nightly.exists())

    def test_a_failed_backup_stops_before_migrating_and_leaves_nothing(self):
        self.pend()
        with (
            patch.object(BackupCommand, '_dump_database', _broken_dump),
            patch.object(SafeMigrate, '_migrate') as migrated,
            self.assertRaises(CommandError) as raised,
        ):
            call_command('safe_migrate', stdout=io.StringIO())
        migrated.assert_not_called()
        self.assertIn('nothing was migrated', str(raised.exception))
        self.assertEqual(self.archives(), [])
        self.assertIsNone(deploys.read_handoff())

    def test_a_restart_after_a_failed_migrate_does_not_back_up_again(self):
        # A crash loop: the first boot backed up, then migrate failed, and the
        # container restarted with migrations still pending.
        self.pend()

        def boom():
            raise RuntimeError('migrate failed')

        with self.assertRaises(RuntimeError):
            self.run_command(migrate=boom)
        first = deploys.read_handoff()
        self.assertTrue(first['backup'])
        out, migrated = self.run_command()
        self.assertIn('not repeated', out)
        migrated.assert_called_once_with()
        self.assertEqual(len(self.archives()), 1)

    def test_a_new_database_has_nothing_to_back_up(self):
        MigrationRecorder(connection).migration_qs.all().delete()
        with patch('core.deploys.clear_handoff'):  # keep the marker to read it
            out, _ = self.run_command()
        self.assertIn('New database', out)
        self.assertEqual(self.archives(), [])
        marker = deploys.read_handoff()
        self.assertEqual(marker['backup'], '')
        self.assertIn('core.0001_initial', marker['migrations'])

    def test_a_successful_run_clears_the_marker(self):
        self.pend()
        self.run_command()
        self.assertIsNone(deploys.read_handoff())

    def test_migrate_runs_its_system_checks_without_prompts(self):
        # `manage.py migrate` ran the system checks at every boot, and they are what
        # stops a boot on a broken model relation; call_command skips them by default.
        with patch('core.management.commands.safe_migrate.call_command') as called:
            SafeMigrate()._migrate()
        called.assert_called_once_with('migrate', interactive=False, skip_checks=False)


class BackupArchiveTests(_DeployEnvMixin, TestCase):
    def backup(self, **options):
        dest = self.root / 'b'
        with patch.object(BackupCommand, '_dump_database', _fake_dump):
            call_command('morph_backup', dest=str(dest), no_media=True, stdout=io.StringIO(), **options)
        return dest

    def test_a_backup_that_fails_while_writing_leaves_no_archive(self):
        # A full disk half way through: the partial file would look like a good
        # backup to whoever restores from it.
        full = OSError(28, 'No space left on device')
        with patch('tarfile.TarFile.add', side_effect=full), self.assertRaises(OSError):
            self.backup()
        self.assertEqual(list((self.root / 'b').glob('*')), [])

    def test_a_label_is_made_safe_for_a_file_name(self):
        [archive] = self.backup(label='v0.118.0 beta/2').glob('*.tar.gz')
        self.assertRegex(archive.name, r'^morpheus-backup-\d{8}T\d{6}Z-v0\.118\.0-beta-2\.tar\.gz$')

    def test_no_label_keeps_the_nightly_name(self):
        [archive] = self.backup().glob('*.tar.gz')
        self.assertRegex(archive.name, r'^morpheus-backup-\d{8}T\d{6}Z\.tar\.gz$')


class DeployWiringTests(SimpleTestCase):
    def test_the_web_container_keeps_its_backups_on_the_backup_volume(self):
        # PyYAML is not in the requirements: read the web service's block as text.
        text = (_REPO / 'docker-compose.yml').read_text()
        web = text[text.index('\n  web:\n') : text.index('\n  worker:\n')]
        self.assertIn('- backup_data:/app/backups', web)

    def boot(self, exit_code):
        """The entrypoint's web mode, with stand-in `python` and `gunicorn`."""
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        log = tmp / 'calls.log'
        for name, code in (('python', exit_code), ('gunicorn', 0)):
            fake = tmp / name
            fake.write_text(f'#!/bin/sh\necho "{name} $*" >> "{log}"\nexit {code}\n')
            fake.chmod(0o755)
        proc = subprocess.run(
            ['sh', str(_REPO / 'scripts' / 'docker-entrypoint.sh'), 'web'],
            env={'PATH': f'{tmp}{os.pathsep}{os.environ["PATH"]}'},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return proc.returncode, log.read_text().splitlines()

    def test_migrations_go_through_safe_migrate_before_gunicorn(self):
        code, calls = self.boot(exit_code=0)
        self.assertEqual(code, 0)
        self.assertEqual(calls[0], 'python manage.py safe_migrate')
        self.assertTrue(calls[1].startswith('gunicorn '), calls)

    def test_a_failed_backup_stops_the_boot(self):
        code, calls = self.boot(exit_code=1)
        self.assertNotEqual(code, 0)
        self.assertEqual(calls, ['python manage.py safe_migrate'])
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_safe_migrate -v 2 2>&1 | tail -15`

Expected: the module fails to import. You see `ImportError: Failed to import test module: core.tests.test_safe_migrate` and `ModuleNotFoundError: No module named 'core.deploys'`.

- [ ] **Step 4: Give `morph_backup` a label, its archive path, and no partial archives**

In `core/management/commands/morph_backup.py`, add `import re` to the imports (between `import os` and `import shutil`). Add this option in `add_arguments`, after `--no-media`:

```python
        parser.add_argument(
            '--label', default='', help='Added to the file name, e.g. the version being deployed.'
        )
```

Then replace the start of `handle`, from `ts = datetime.utcnow()…` through the `tar.add` loop, with:

```python
        ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        # The label goes after the timestamp, so names still sort by time for _prune.
        label = re.sub(r'[^A-Za-z0-9._-]+', '-', options['label']).strip('.-')[:60]
        suffix = f'-{label}' if label else ''
        archive_path = dest / f'morpheus-backup-{ts}{suffix}.tar.gz'
        self.archive_path = archive_path
        self.stdout.write(self.style.NOTICE(f'Backing up to {archive_path}'))

        with tempfile.TemporaryDirectory(prefix='morph-bk-') as workdir:
            workdir = Path(workdir)  # noqa: PLW2901
            self._dump_database(workdir)
            if not options['no_media']:
                self._snapshot_media(workdir)
            try:
                with tarfile.open(archive_path, 'w:gz') as tar:
                    for child in workdir.iterdir():
                        tar.add(child, arcname=child.name)
            except BaseException:
                # A half-written archive (a full disk) would look like a good
                # backup to whoever restores from it later.
                archive_path.unlink(missing_ok=True)
                raise
```

The lines after it (`size_mb = …`, the success message, `self._prune(…)`) stay as they are.

- [ ] **Step 5: Create `core/deploys.py`**

```python
"""Safe deploys: a database backup before migrating, and a record of each deploy.

On every boot the web container's entrypoint (scripts/docker-entrypoint.sh) runs
``manage.py safe_migrate`` in place of ``migrate``:

1. When ``migrate`` has anything to apply, it backs the database up first into
   ``<MORPHEUS_BACKUP_DIR>/pre-deploy/``, keeping the last five, named after the
   version and commit being deployed. If the backup fails, it exits non-zero
   before migrating, so the store stays on a schema the previous version knows.
2. It migrates.

A file in the container's /tmp (``HANDOFF``) marks the backup step as done for
this container and carries what it found to the end of the command. A crash
loop restarts the same container with migrations still pending, and a second
backup then would copy a half-migrated database and push the real copy out of
the five.

The backup folder comes from the MORPHEUS_BACKUP_DIR environment variable only,
never from the backups app's setting: staff and Linda can change settings, and
a backup in a folder the web server serves is public.

Spec: docs/superpowers/specs/2026-10-19-safe-deploys-design.md.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

#: Pre-deploy backups kept. The nightly ones rotate separately, in the folder above.
BACKUP_KEEP = 5
HANDOFF = Path(tempfile.gettempdir()) / 'morpheus-predeploy.json'
_COMMIT = re.compile(r'^[0-9a-f]{7,40}$')


def backup_root() -> Path:
    return Path(os.environ.get('MORPHEUS_BACKUP_DIR') or '/app/backups')


def predeploy_dir() -> Path:
    return backup_root() / 'pre-deploy'


def current_commit() -> str:
    """The commit this image was built from, when the platform says (Coolify sets
    SOURCE_COMMIT); '' otherwise."""
    value = os.environ.get('SOURCE_COMMIT', '').strip().lower()
    return value if _COMMIT.match(value) else ''


def deploy_label() -> str:
    """The version being deployed, with its short commit when known: the backup's name."""
    from django.conf import settings

    commit = current_commit()
    return str(settings.MORPHEUS_VERSION) + (f'-{commit[:7]}' if commit else '')


def migration_plan() -> tuple[list[str], bool]:
    """The migrations ``migrate`` would apply now, and whether no migration was ever
    applied (a new database)."""
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    pending = [f'{m.app_label}.{m.name}' for m, backwards in plan if not backwards]
    return pending, not executor.loader.applied_migrations


def read_handoff() -> dict | None:
    try:
        return json.loads(HANDOFF.read_text())
    except (OSError, ValueError):
        return None


def write_handoff(data: dict) -> None:
    HANDOFF.write_text(json.dumps(data))


def clear_handoff() -> None:
    HANDOFF.unlink(missing_ok=True)
```

- [ ] **Step 6: Create `core/management/commands/safe_migrate.py`**

```python
"""`python manage.py safe_migrate`: migrate, backing the database up first.

The web container's entrypoint runs this in place of `migrate` on every boot
(scripts/docker-entrypoint.sh). With nothing to migrate it only runs `migrate`.
With migrations pending it first backs the database up into the pre-deploy
folder, and a failed backup exits non-zero before anything is migrated. The
steps share one process on purpose: each `manage.py` start costs about three
seconds, and the store answers 503 while the web container boots.
See core/deploys.py.
"""

from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from core import deploys
from core.management.commands.morph_backup import Command as BackupCommand


class Command(BaseCommand):
    help = 'Migrate, backing the database up first when there is anything to migrate.'
    requires_system_checks = []  # migrate runs them

    def handle(self, *args, **options):
        self._back_up_first()
        self._migrate()
        self._record()

    def _back_up_first(self) -> None:
        if deploys.read_handoff() is not None:
            # This container ran this step, then restarted (a crash loop). A second
            # backup now could copy a half-migrated database.
            self.stdout.write(
                '[safe_migrate] Backup step already done in this container; not repeated.'
            )
            return
        pending, fresh = deploys.migration_plan()
        backup = ''
        if not pending:
            self.stdout.write('[safe_migrate] No migrations to run, so no backup is needed.')
        elif fresh:
            self.stdout.write(
                f'[safe_migrate] New database: {len(pending)} migrations and nothing to back up.'
            )
        else:
            self.stdout.write(
                f'[safe_migrate] {len(pending)} migrations to run; backing up the database first.'
            )
            command = BackupCommand(stdout=self.stdout, stderr=self.stderr)
            try:
                call_command(
                    command,
                    dest=str(deploys.predeploy_dir()),
                    keep=deploys.BACKUP_KEEP,
                    no_media=True,
                    label=deploys.deploy_label(),
                )
            except Exception as exc:
                raise CommandError(
                    f'[safe_migrate] The backup failed, so nothing was migrated: {exc}'
                ) from exc
            backup = str(command.archive_path)
        deploys.write_handoff({'backup': backup, 'migrations': pending})

    def _migrate(self) -> None:
        # skip_checks=False: `manage.py migrate` ran the system checks on every boot.
        call_command('migrate', interactive=False, skip_checks=False)

    def _record(self) -> None:
        deploys.clear_handoff()
```

- [ ] **Step 7: Wire the entrypoint and the volume**

In `scripts/docker-entrypoint.sh`, change the header lines for `web` and `migrate`:

```sh
#   web     — wait for DB, migrate (safe_migrate: backs up first), collectstatic, run gunicorn
```

```sh
#   migrate — run migrations once (safe_migrate) and exit (useful as a Coolify pre-deploy job)
```

Then replace `run_migrations`:

```sh
run_migrations() {
  echo "[entrypoint] Running migrations…"
  # safe_migrate backs the database up first when anything is pending, and exits
  # non-zero before migrating if that backup fails; `set -e` then stops the boot
  # (core/deploys.py).
  python manage.py safe_migrate
}
```

In `docker-compose.yml`, the web service's `volumes` becomes:

```yaml
    volumes:
      - media_data:/app/media
      # The backup safe_migrate takes before migrating lands here, on the volume
      # the worker's nightly backups use, so it survives the next deploy.
      - backup_data:/app/backups
```

Keep the existing `/app/staticfiles` comment under it unchanged. Coolify reads `/docker-compose.yml` from the repo on every deploy. All four stores carry the 2026-09-19 compose change, so the web container gets `<uuid>_backup-data`, the volume its worker already writes as `morpheus`.

- [ ] **Step 8: Run the tests to verify they pass**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_safe_migrate core.tests.test_update_apply_safety -v 2 2>&1 | tail -25`

Expected: `Ran 20 tests` … `OK`. That is 16 in `test_safe_migrate` and the 4 existing updater safety tests, which also go through `morph_backup`.

- [ ] **Step 9: Lint and commit**

```bash
.venv/bin/ruff check core/deploys.py core/management/commands/safe_migrate.py core/management/commands/morph_backup.py core/tests/test_safe_migrate.py \
 && .venv/bin/ruff format core/deploys.py core/management/commands/safe_migrate.py core/management/commands/morph_backup.py core/tests/test_safe_migrate.py \
 && git add core/deploys.py core/management/commands/safe_migrate.py core/management/commands/morph_backup.py core/tests/test_safe_migrate.py scripts/docker-entrypoint.sh docker-compose.yml \
 && git commit -m "feat(deploys): back the database up before migrating, and stop if the backup fails

The web container now runs manage.py safe_migrate in place of migrate. When
anything is pending it runs morph_backup --no-media --keep 5 into
\$MORPHEUS_BACKUP_DIR/pre-deploy first, named after the version and commit, and
exits non-zero without migrating if that fails. A marker in /tmp keeps a crash
loop from backing up a half-migrated database. The web service mounts the
backup volume, which only the worker had: a backup written from web was lost
at the next deploy.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Record each deploy (`DeployEvent`)

**Files:**
- Modify: `core/models.py`. Add the `timezone` import at the top, and add `DeployEvent` after `ExchangeRate`, before the `core.agents.models` import block (around line 316).
- Create: `core/migrations/0024_deployevent.py`, generated by `makemigrations`.
- Modify: `core/deploys.py`. Extend the docstring and add `record_deploy()`.
- Modify: `core/management/commands/safe_migrate.py`. Replace `_record()`.
- Modify: `scripts/docker-entrypoint.sh`. Change the `run_migrations` comment.
- Test: `core/tests/test_deploy_record.py`

**Interfaces:**
- Consumes (from Task 1): `deploys.read_handoff()`, `write_handoff()`, `clear_handoff()`, `current_commit()`, `SafeMigrate._record()`, and the test helpers `_DeployEnvMixin` and `_fake_dump`.
- Produces:
  - `core.models.DeployEvent` with these fields:
    - `version: CharField(40)`
    - `commit: CharField(40, blank)`
    - `deployed_at: DateTimeField(default=timezone.now)`
    - `backup: CharField(255, blank)`
    - `migrations: JSONField(default=list)`
  - Its `Meta.ordering = ['-deployed_at', '-pk']`, so `.first()` is the newest.
  - `core.deploys.record_deploy() -> tuple[DeployEvent, bool]`, where the bool is "created".

- [ ] **Step 1: Write the failing tests**

Create `core/tests/test_deploy_record.py`:

```python
"""Each deploy is recorded as a DeployEvent (safe deploys, part 1).

safe_migrate writes it after migrating. The Version & updates page and Linda's
updates.status read it, and so will the rollback notice in release 4.
"""

from __future__ import annotations

import io
import os
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.db import DatabaseError
from django.test import TestCase

from core import deploys
from core.management.commands.morph_backup import Command as BackupCommand
from core.management.commands.safe_migrate import Command as SafeMigrate
from core.models import DeployEvent
from core.tests.test_safe_migrate import _DeployEnvMixin, _fake_dump


class RecordDeployTests(_DeployEnvMixin, TestCase):
    def test_a_deploy_is_recorded_with_its_backup_and_migrations(self):
        deploys.write_handoff(
            {'backup': '/app/backups/pre-deploy/b.tar.gz', 'migrations': ['core.0024_deployevent']}
        )
        event, created = deploys.record_deploy()
        self.assertTrue(created)
        self.assertEqual(
            (event.version, event.commit, event.backup, event.migrations),
            (
                settings.MORPHEUS_VERSION,
                'a' * 40,
                '/app/backups/pre-deploy/b.tar.gz',
                ['core.0024_deployevent'],
            ),
        )
        self.assertIsNone(deploys.read_handoff())

    def test_a_restart_of_the_same_deploy_adds_nothing(self):
        first, _ = deploys.record_deploy()
        deploys.write_handoff({'backup': '', 'migrations': []})
        event, created = deploys.record_deploy()
        self.assertFalse(created)
        self.assertEqual(event, first)
        self.assertEqual(DeployEvent.objects.count(), 1)

    def test_a_new_commit_is_a_new_deploy(self):
        deploys.record_deploy()
        with patch.dict(os.environ, {'SOURCE_COMMIT': 'c' * 40}):
            deploys.record_deploy()
        self.assertEqual([e.commit for e in DeployEvent.objects.all()], ['c' * 40, 'a' * 40])

    def test_migrating_again_on_the_same_commit_is_a_new_deploy(self):
        # The same commit deployed again after its database was restored to an
        # older copy: it migrates again, and that deserves its own row.
        deploys.record_deploy()
        deploys.write_handoff({'backup': '/b.tar.gz', 'migrations': ['core.0024_deployevent']})
        deploys.record_deploy()
        self.assertEqual(DeployEvent.objects.count(), 2)

    def test_an_unknown_commit_is_left_blank(self):
        with patch.dict(os.environ, {'SOURCE_COMMIT': 'not-a-sha'}):
            event, _ = deploys.record_deploy()
        self.assertEqual(event.commit, '')


class SafeMigrateRecordsTests(_DeployEnvMixin, TestCase):
    def test_a_deploy_that_migrates_is_recorded_with_its_backup(self):
        name = self.pend()
        out = io.StringIO()
        with (
            patch.object(BackupCommand, '_dump_database', _fake_dump),
            patch.object(SafeMigrate, '_migrate'),
        ):
            call_command('safe_migrate', stdout=out)
        event = DeployEvent.objects.get()
        [archive] = self.archives()
        self.assertEqual(event.backup, str(self.root / 'backups' / 'pre-deploy' / archive))
        self.assertEqual(event.migrations, [name])
        self.assertIn(f'Recorded {settings.MORPHEUS_VERSION} (aaaaaaa), 1 migrations', out.getvalue())

    def test_a_failed_record_does_not_stop_the_store(self):
        err = io.StringIO()
        with (
            patch.object(SafeMigrate, '_migrate'),
            patch('core.deploys.record_deploy', side_effect=DatabaseError('down')),
            self.assertLogs('morpheus.deploys', 'ERROR'),
        ):
            call_command('safe_migrate', stdout=io.StringIO(), stderr=err)
        self.assertIn('Could not record this deploy', err.getvalue())
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_deploy_record -v 2 2>&1 | tail -10`

Expected: `ImportError: cannot import name 'DeployEvent' from 'core.models'`.

- [ ] **Step 3: Add the model**

In `core/models.py`, add `from django.utils import timezone` under `from django.db import models`. Then add this class after `ExchangeRate`, before the `# Agent run-state models …` comment:

```python
class DeployEvent(models.Model):
    """One deploy of this store, written after migrating by ``manage.py
    safe_migrate`` (core/deploys.py). A restart of the same deploy adds no row."""

    version = models.CharField(max_length=40)
    commit = models.CharField(max_length=40, blank=True)
    deployed_at = models.DateTimeField(default=timezone.now)
    # The pre-deploy backup's path; blank when nothing was migrated.
    backup = models.CharField(max_length=255, blank=True)
    # The migrations this deploy applied, as "app_label.name".
    migrations = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['-deployed_at', '-pk']

    def __str__(self) -> str:
        return f'{self.version} at {self.deployed_at:%Y-%m-%d %H:%M}'
```

- [ ] **Step 4: Generate the migration**

Run: `DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py makemigrations core -n deployevent`

Expected: `core/migrations/0024_deployevent.py`, with `- Create model DeployEvent`. Open it and check that it depends on `('core', '0023_modelusageday')`. Its one `CreateModel` should have the fields above, with `id` as a `BigAutoField`, and `options={'ordering': ['-deployed_at', '-pk']}`. Nothing else may be in it. If `makemigrations` writes changes for other apps, stop: that is drift on `main` and not this task's business.

- [ ] **Step 5: Record the deploy in `core/deploys.py`**

Change the docstring's numbered list to end with:

```
2. It migrates.
3. It records the deploy as a ``DeployEvent`` (version, commit, the backup's
   path, the migrations applied). A restart of the same deploy adds nothing.
```

Append to the module:

```python
def record_deploy():
    """Write this boot's DeployEvent from the marker, then remove the marker.

    A boot that migrated nothing, on the version and commit of the newest record,
    is a restart of that deploy and writes nothing. Returns ``(event, created)``.
    """
    from django.conf import settings

    from core.models import DeployEvent

    marker = read_handoff() or {}
    version, commit = str(settings.MORPHEUS_VERSION), current_commit()
    migrations = [str(name) for name in marker.get('migrations') or []]
    newest = DeployEvent.objects.first()
    if newest and (newest.version, newest.commit) == (version, commit) and not migrations:
        clear_handoff()
        return newest, False
    event = DeployEvent.objects.create(
        version=version,
        commit=commit,
        backup=str(marker.get('backup') or ''),
        migrations=migrations,
    )
    clear_handoff()
    return event, True
```

- [ ] **Step 6: Call it from `safe_migrate`**

In `core/management/commands/safe_migrate.py`, add `import logging` above the Django imports. Add `logger = logging.getLogger('morpheus.deploys')` after the imports. Then replace `_record`:

```python
    def _record(self) -> None:
        # The record feeds the Version & updates page; it never keeps the store down.
        try:
            event, created = deploys.record_deploy()
        except Exception:
            logger.exception('safe_migrate: could not record this deploy')
            self.stderr.write('[safe_migrate] Could not record this deploy; carrying on.')
            return
        if not created:
            self.stdout.write(f'[safe_migrate] {event.version} restarted; already recorded.')
            return
        commit = f' ({event.commit[:7]})' if event.commit else ''
        count = f', {len(event.migrations)} migrations applied' if event.migrations else ''
        self.stdout.write(f'[safe_migrate] Recorded {event.version}{commit}{count}.')
```

Replace the command's module docstring with:

```python
"""`python manage.py safe_migrate`: migrate, backing the database up first.

The web container's entrypoint runs this in place of `migrate` on every boot
(scripts/docker-entrypoint.sh). With migrations pending it first backs the
database up into the pre-deploy folder, and a failed backup exits non-zero
before anything is migrated. After migrating it records the deploy as a
DeployEvent. The steps share one process on purpose: each `manage.py` start
costs about three seconds, and the store answers 503 while the web container
boots. See core/deploys.py.
"""
```

In `scripts/docker-entrypoint.sh`, change the `run_migrations` comment's last line to `# (core/deploys.py). It then records the deploy.`

Task 1's `test_a_new_database_has_nothing_to_back_up` patches `core.deploys.clear_handoff`, which `record_deploy` now calls. It still passes, because its `DeployEvent` row is rolled back with the test.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_deploy_record core.tests.test_safe_migrate -v 2 2>&1 | tail -12`

Expected: `Ran 23 tests` … `OK`.

Then run: `DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py makemigrations --check --dry-run`

Expected: `No changes detected`.

- [ ] **Step 8: Lint and commit**

```bash
.venv/bin/ruff check core/models.py core/deploys.py core/management/commands/safe_migrate.py core/tests/test_deploy_record.py \
 && .venv/bin/ruff format core/models.py core/deploys.py core/management/commands/safe_migrate.py core/tests/test_deploy_record.py \
 && git add core/models.py core/migrations/0024_deployevent.py core/deploys.py core/management/commands/safe_migrate.py core/tests/test_deploy_record.py scripts/docker-entrypoint.sh \
 && git commit -m "feat(deploys): record each deploy as a DeployEvent

safe_migrate writes the version, commit (SOURCE_COMMIT), time, the pre-deploy
backup and the migrations applied once it has migrated. A restart of the same
deploy adds nothing, and a failure to record never keeps the store down.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: An honest Version & updates page

**Files:**
- Modify: `core/updates.py`. Add `can_self_update()` after `_repo_root()` (line 65).
- Modify: `core/deploys.py`. Add `latest_predeploy_backup()` and `running_release()`.
- Create: `plugins/installed/admin_dashboard/templates/admin_dashboard/_updater_card.html`
- Modify: `plugins/installed/release_notes/views.py`, in `version_updates`, lines 134–157.
- Modify: `plugins/installed/release_notes/templates/release_notes/index.html`, lines 17–96.
- Modify: `plugins/installed/admin_dashboard/views_split/system.py`, in `updates_page`, lines 38–70.
- Modify: `plugins/installed/admin_dashboard/templates/admin_dashboard/updates.html`, lines 12–91.
- Modify: `plugins/installed/release_notes/help.md`
- Test: create `core/tests/test_running_release.py`. Modify `plugins/installed/release_notes/tests/test_release_notes.py` and `plugins/installed/admin_dashboard/tests/test_updates_apply.py`.

**Interfaces:**
- Consumes: `core.models.DeployEvent` (Task 2), and `deploys.predeploy_dir()` and `current_commit()` (Task 1).
- Produces:
  - `core.updates.can_self_update() -> bool`
  - `core.deploys.latest_predeploy_backup() -> dict | None`, with keys `name: str`, `size: int` (bytes), `taken_at: datetime` (aware, UTC) and `label: str`
  - `core.deploys.running_release() -> dict`, with keys `version`, `commit`, `commit_short`, `deployed_at` (datetime or None), `backup` (the dict above or None) and `self_update` (bool)
  - The template partial `admin_dashboard/_updater_card.html`, which reads the context keys `running`, `platform` and `self_update_enabled`

- [ ] **Step 1: Write the failing tests**

Create `core/tests/test_running_release.py`:

```python
"""What the store runs, for Settings → Version & updates and Linda (safe deploys, part 5)."""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from core.deploys import latest_predeploy_backup, running_release
from core.models import DeployEvent
from core.updates import can_self_update


class _BackupFolderMixin:
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.folder = self.root / 'pre-deploy'
        env = patch.dict(os.environ, {'MORPHEUS_BACKUP_DIR': tmp.name, 'SOURCE_COMMIT': 'e' * 40})
        env.start()
        self.addCleanup(env.stop)


class CanSelfUpdateTests(SimpleTestCase):
    def test_only_a_git_checkout_can_update_itself(self):
        with tempfile.TemporaryDirectory() as tmp, patch('core.updates._repo_root', return_value=Path(tmp)):
            self.assertFalse(can_self_update())
            (Path(tmp) / '.git').mkdir()
            self.assertTrue(can_self_update())


class LatestBackupTests(_BackupFolderMixin, SimpleTestCase):
    def test_none_when_the_folder_does_not_exist(self):
        self.assertIsNone(latest_predeploy_backup())

    def test_the_newest_backup_with_its_size_time_and_label(self):
        self.folder.mkdir()
        (self.folder / 'morpheus-backup-20261018T090000Z-v0.117.0-aaaaaaa.tar.gz').write_bytes(b'1')
        (self.folder / 'morpheus-backup-20261019T140200Z-v0.118.0-bbbbbbb.tar.gz').write_bytes(b'123')
        self.assertEqual(
            latest_predeploy_backup(),
            {
                'name': 'morpheus-backup-20261019T140200Z-v0.118.0-bbbbbbb.tar.gz',
                'size': 3,
                'taken_at': datetime(2026, 10, 19, 14, 2, tzinfo=UTC),
                'label': 'v0.118.0-bbbbbbb',
            },
        )

    def test_files_that_are_not_backups_are_ignored(self):
        self.folder.mkdir()
        (self.folder / 'morpheus-backup-junk.tar.gz').write_bytes(b'x')
        (self.folder / 'notes.txt').write_text('x')
        self.assertIsNone(latest_predeploy_backup())


class RunningReleaseTests(_BackupFolderMixin, TestCase):
    def test_what_runs_and_when_it_was_installed(self):
        when = datetime(2026, 10, 19, 14, 2, tzinfo=UTC)
        DeployEvent.objects.create(version=settings.MORPHEUS_VERSION, commit='e' * 40, deployed_at=when)
        DeployEvent.objects.create(version='v0.0.1', commit='e' * 40)  # not what runs now
        with patch('core.updates.can_self_update', return_value=False):
            release = running_release()
        self.assertEqual(
            release,
            {
                'version': settings.MORPHEUS_VERSION,
                'commit': 'e' * 40,
                'commit_short': 'eeeeeee',
                'deployed_at': when,
                'backup': None,
                'self_update': False,
            },
        )

    def test_before_any_record_the_install_time_is_blank(self):
        self.assertIsNone(running_release()['deployed_at'])
```

In `plugins/installed/release_notes/tests/test_release_notes.py`, add these imports at the top:

```python
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.template.defaultfilters import filesizeformat

from core.models import DeployEvent
```

In `VersionPageTests.test_page_is_the_unified_updater_plus_changelog`, wrap the GET so the test keeps describing a git install wherever it runs:

```python
        with patch('core.updates.can_self_update', return_value=True):
            html = self.client.get('/dashboard/apps/release_notes/version/').content.decode()
```

Append this class:

```python
_NO_GIT = {
    'source': 'git',
    'available': 'unavailable',
    'reason': 'No git metadata in this deployment (built image / non-git install).',
}


class HonestUpdaterTests(TestCase):
    """Safe deploys, part 5: the page says what runs, and offers nothing that cannot work."""

    URL = '/dashboard/apps/release_notes/version/'

    def setUp(self):
        staff = get_user_model().objects.create_user(
            username='ops', email='o@x.io', password='pw', is_staff=True
        )
        self.client.force_login(staff)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.backups = Path(tmp.name)
        env = patch.dict(os.environ, {'MORPHEUS_BACKUP_DIR': tmp.name, 'SOURCE_COMMIT': 'd' * 40})
        env.start()
        self.addCleanup(env.stop)

    def page(self, *, self_update, platform=None):
        # The changelog quotes button names ("Update now", RELEASE_NOTES.md), so
        # read the page without it.
        no_notes = self.backups / 'none.md'
        with (
            patch('core.updates.can_self_update', return_value=self_update),
            patch('core.updates.platform_update_status', return_value=platform or _NO_GIT),
            patch(
                'plugins.installed.release_notes.views._release_notes_path', return_value=no_notes
            ),
        ):
            return self.client.get(self.URL).content.decode()

    def test_a_built_image_gets_one_line_instead_of_buttons(self):
        html = self.page(self_update=False)
        self.assertIn('This store updates when a new version is released.', html)
        for gone in ('Check for updates', 'Update now', 'data-testid="component-updates"', 'No git metadata'):
            self.assertNotIn(gone, html)

    def test_it_shows_the_commit_the_install_time_and_the_backup(self):
        DeployEvent.objects.create(
            version=settings.MORPHEUS_VERSION,
            commit='d' * 40,
            deployed_at=datetime(2026, 10, 19, 12, 0, tzinfo=UTC),
        )
        folder = self.backups / 'pre-deploy'
        folder.mkdir()
        name = f'morpheus-backup-20261019T115900Z-{settings.MORPHEUS_VERSION}-ddddddd.tar.gz'
        (folder / name).write_bytes(b'x' * 2048)
        html = self.page(self_update=False)
        self.assertIn('Commit <code>ddddddd</code>', html)
        self.assertIn('Installed 19 Oct 2026', html)
        self.assertIn('Database backup from before the last update', html)
        self.assertIn(filesizeformat(2048), html)

    def test_without_a_backup_it_says_when_one_is_made(self):
        html = self.page(self_update=False)
        self.assertIn(
            'The store makes one automatically before any update that changes the database.', html
        )

    def test_a_git_install_keeps_its_buttons(self):
        status = {'source': 'git', 'available': 'yes', 'behind': 2, 'upstream': 'origin/main', 'current': 'v1', 'latest': 'v2'}
        html = self.page(self_update=True, platform=status)
        self.assertIn('Update now', html)
        self.assertIn('Check for updates', html)
        self.assertNotIn('This store updates when a new version is released.', html)
```

In `plugins/installed/admin_dashboard/tests/test_updates_apply.py`, add three lines at the end of `ComponentUpdatesSurfaceTests.setUp`, because those tests describe the channel on a git install:

```python
        p = patch('core.updates.can_self_update', return_value=True)
        p.start()
        self.addCleanup(p.stop)
```

Append this class:

```python
class StandaloneUpdaterBuiltImageTests(TestCase):
    """The standalone /dashboard/updates/ page tells the same truth (safe deploys, part 5)."""

    def setUp(self):
        u = get_user_model().objects.create_user(
            username='img', email='i@example.test', password='pw', is_staff=True
        )
        self.client.force_login(u)
        _pin_standalone_updater(self)

    def test_a_built_image_gets_one_line_instead_of_buttons(self):
        status = {'source': 'git', 'available': 'unavailable', 'reason': 'No git metadata.'}
        with (
            patch('core.updates.can_self_update', return_value=False),
            patch('core.updates.platform_update_status', return_value=status),
        ):
            html = self.client.get(reverse('admin_dashboard:updates')).content.decode()
        self.assertIn('This store updates when a new version is released.', html)
        for gone in ('Check for updates', 'Update now', 'data-testid="component-updates"'):
            self.assertNotIn(gone, html)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_running_release plugins.installed.release_notes.tests.test_release_notes plugins.installed.admin_dashboard.tests.test_updates_apply -v 2 2>&1 | tail -20`

Expected: `test_running_release` fails to import with `ImportError: cannot import name 'latest_predeploy_backup' from 'core.deploys'`. The new page tests fail with `AssertionError: 'This store updates when a new version is released.' not found`.

- [ ] **Step 3: `can_self_update()` in `core/updates.py`**

Add it after `_repo_root()`:

```python
def can_self_update() -> bool:
    """True when this install runs from a git checkout, so it can update its own code.

    A built image (every Docker install, our stores included) has no ``.git``. It
    updates when a new version is released and deployed, so the dashboard and
    Linda offer no "Update now" there.
    """
    return (_repo_root() / '.git').exists()
```

- [ ] **Step 4: `latest_predeploy_backup()` and `running_release()` in `core/deploys.py`**

Add `from datetime import UTC, datetime` to the imports (after `import tempfile`). Add `_ARCHIVE` under `_COMMIT`:

```python
_ARCHIVE = re.compile(r'^morpheus-backup-(\d{8}T\d{6}Z)(?:-(.+))?\.tar\.gz$')
```

Append to the module:

```python
def latest_predeploy_backup() -> dict | None:
    """The newest backup in the pre-deploy folder, as ``{name, size, taken_at,
    label}``; None when there is none."""
    for path in sorted(predeploy_dir().glob('morpheus-backup-*.tar.gz'), reverse=True):
        match = _ARCHIVE.match(path.name)
        if not match:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        taken_at = datetime.strptime(match.group(1), '%Y%m%dT%H%M%SZ').replace(tzinfo=UTC)
        return {'name': path.name, 'size': size, 'taken_at': taken_at, 'label': match.group(2) or ''}
    return None


def running_release() -> dict:
    """What this store runs, for Settings → Version & updates and Linda's
    ``updates.status``: version, commit, when it was installed, the newest
    pre-deploy backup, and whether it can update itself."""
    from django.conf import settings

    from core.models import DeployEvent
    from core.updates import can_self_update

    version, commit = str(settings.MORPHEUS_VERSION), current_commit()
    event = DeployEvent.objects.filter(version=version, commit=commit).first()
    return {
        'version': version,
        'commit': commit,
        'commit_short': commit[:7],
        'deployed_at': event.deployed_at if event else None,
        'backup': latest_predeploy_backup(),
        'self_update': can_self_update(),
    }
```

- [ ] **Step 5: The shared updater card**

Create `plugins/installed/admin_dashboard/templates/admin_dashboard/_updater_card.html`:

```django
{% comment %}
The core updater card, shared by Version & updates (release_notes) and the
standalone /dashboard/updates/ page. `running` is core.deploys.running_release():
the version, commit, install time and newest pre-deploy backup. A store that
cannot update itself (no git checkout: every Docker install, ours included) gets
one line where the check and apply buttons would be, since neither can work
there (safe-deploys spec, part 5).
{% endcomment %}
<div class="card card-padded" data-testid="running-release">
  <div class="flex items-center justify-between gap-3 flex-wrap">
    <div>
      <p class="text-xs uppercase tracking-wide text-[color:var(--text-muted)]">Morpheus core</p>
      <p class="text-lg font-semibold">{{ running.version }}</p>
      {% if running.commit or running.deployed_at %}
      <p class="text-sm text-[color:var(--text-muted)]">{% if running.commit %}Commit <code>{{ running.commit_short }}</code>{% endif %}{% if running.commit and running.deployed_at %} · {% endif %}{% if running.deployed_at %}Installed {{ running.deployed_at|date:"j M Y, H:i" }}{% endif %}</p>
      {% endif %}
    </div>
    {% if running.self_update %}
    <form method="post" action="{% url 'admin_dashboard:updates_check' %}">
      {% csrf_token %}
      <button type="submit" class="btn btn-ghost text-sm"><i data-lucide="refresh-cw" class="h-4 w-4"></i> Check for updates</button>
    </form>
    {% endif %}
  </div>
  <div class="mt-3 pt-3 border-t border-[color:var(--border)] text-sm" data-testid="predeploy-backup">
    {% if running.backup %}
      Database backup from before the last update that changed the database: {{ running.backup.taken_at|date:"j M Y, H:i" }} ({{ running.backup.size|filesizeformat }}).
    {% else %}
      <span class="text-[color:var(--text-muted)]">No backup from before an update yet. The store makes one automatically before any update that changes the database.</span>
    {% endif %}
  </div>
  <div class="mt-3 pt-3 border-t border-[color:var(--border)] text-sm">
    {% if not running.self_update %}
      This store updates when a new version is released.{% if platform.available == 'yes' and platform.latest %} {{ platform.latest }} is out.{% endif %}
    {% elif platform.available == 'yes' %}
      <span class="pill pill-warn">Update available</span>
      <span class="text-[color:var(--text-muted)]">{{ platform.behind }} commit(s) behind <code>{{ platform.upstream }}</code> · deployed <code>{{ platform.current }}</code></span>
      <div class="mt-2 flex items-center gap-2 flex-wrap">
        <form method="post" action="{% url 'admin_dashboard:updates_apply' %}" class="inline">
          {% csrf_token %}
          <button type="submit" class="btn btn-primary text-sm"
                  data-confirm="Apply update? This backs up first, fast-forwards the deployment from {{ platform.current }} to {{ platform.latest }}, boot-probes the new code, runs migrations, and auto-rolls-back on any failure.">
            <i data-lucide="download" class="h-4 w-4"></i> Update now
          </button>
        </form>
        {% if not self_update_enabled %}<span class="text-xs text-[color:var(--text-muted)]">Self-update is off — set <code>MORPHEUS_SELF_UPDATE_ENABLED=1</code> to allow one-click apply.</span>{% endif %}
      </div>
    {% elif platform.available == 'no' %}
      <span class="pill pill-success">Up to date</span>
      <span class="text-[color:var(--text-muted)]">on <code>{{ platform.branch }}</code> at <code>{{ platform.current }}</code></span>
    {% else %}
      <span class="pill">Version check {{ platform.available }}</span>
      <span class="text-[color:var(--text-muted)]">{{ platform.reason }}{% if platform.current and platform.current != 'unknown' %} · deployed <code>{{ platform.current }}</code>{% endif %}</span>
    {% endif %}
  </div>
</div>
```

- [ ] **Step 6: Use it on both pages**

In `plugins/installed/release_notes/templates/release_notes/index.html`, replace lines 17–56 with one line: the `{% comment %} Updater…{% endcomment %}` block and the `<div class="card card-padded">` core card down to its closing `</div>`. The line is:

```django
  {% include "admin_dashboard/_updater_card.html" %}
```

Then put `{% if running.self_update %}` on the line before `{# Per-app / per-theme signed release channel … #}`. Put `{% endif %}` after that card's closing `</div>`, which is old line 96, just before `{% if themes %}`.

In `plugins/installed/admin_dashboard/templates/admin_dashboard/updates.html`, replace old lines 12–48 with the same `{% include %}` line. That span runs from the `<div class="card card-padded">` holding "Morpheus core" through the `</div>` that closes it after the platform status block. Then wrap the "App &amp; theme updates" card (old lines 50–91, from `{# Per-app / per-theme channel … #}` through its closing `</div>`) in `{% if running.self_update %}` … `{% endif %}`.

In `plugins/installed/release_notes/views.py`, inside `version_updates`, change the updater block and the context:

```python
    # Updater status — core-owned, no network call on load (last check / daily beat).
    from core.deploys import running_release
    from core.updates import cached_update_status, platform_update_status
    from core.versioning import component_versions

    components_data = component_versions()
    platform = platform_update_status(fetch=False)
    component_updates = platform.get('components')
    if component_updates is None:
        component_updates = (cached_update_status() or {}).get('components') or []

    return render(
        request,
        'release_notes/index.html',
        {
            'version': version,
            'releases': releases,
            'latest': releases[0] if releases else None,
            'running': running_release(),
            'themes': components_data.get('themes') or [],
            'platform': platform,
            'component_updates': component_updates,
            'self_update_enabled': bool(getattr(settings, 'MORPHEUS_SELF_UPDATE_ENABLED', False)),
        },
    )
```

`core_version` is gone from the context, because only the old card read it.

In `plugins/installed/admin_dashboard/views_split/system.py`, inside `updates_page`, add `from core.deploys import running_release` next to the other lazy `core` imports. Replace `'core_version': data.get('core', 'unknown'),` with `'running': running_release(),`. The rest of that context stays.

- [ ] **Step 7: The guide**

In `plugins/installed/release_notes/help.md`, replace the second paragraph of "What it's for" with:

```markdown
It also holds [About Morpheus OS](page:about), the project's page about the platform and its licence, and [Version & updates](page:version), which shows the version this store runs and when it was installed, the backup of the database made before the last update that changed it, and the notes for every release.
```

Add this paragraph at the end of "Good to know":

```markdown
Before an update that changes the database, the store backs the database up first and keeps the last five of these backups; if the backup fails, the update stops before changing anything. A store that runs from a built image, as most do, updates when a new version is released, so its Version & updates page has no update button.
```

- [ ] **Step 8: Compile the templates and run the tests**

Run:

```bash
DATABASE_URL='sqlite:///:memory:' .venv/bin/python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'morph.settings'); django.setup(); from django.template.loader import get_template; [get_template(t) for t in ('admin_dashboard/_updater_card.html', 'release_notes/index.html', 'admin_dashboard/updates.html')]; print('templates compile')"
```

Expected: `templates compile`.

Then run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.tests.test_running_release plugins.installed.release_notes plugins.installed.admin_dashboard.tests.test_updates_apply core.tests.test_update_check -v 2 2>&1 | tail -15`

Expected: `OK`. The release_notes app's help tests (`test_help_*`) are in this run, and they check the new guide text: word count, markers and jargon.

- [ ] **Step 9: Lint and commit**

```bash
.venv/bin/ruff check core plugins/installed/release_notes plugins/installed/admin_dashboard/views_split/system.py plugins/installed/admin_dashboard/tests/test_updates_apply.py \
 && .venv/bin/ruff format core/updates.py core/deploys.py core/tests/test_running_release.py plugins/installed/release_notes/views.py plugins/installed/release_notes/tests/test_release_notes.py plugins/installed/admin_dashboard/views_split/system.py plugins/installed/admin_dashboard/tests/test_updates_apply.py \
 && git add core/updates.py core/deploys.py core/tests/test_running_release.py plugins/installed/admin_dashboard/templates/admin_dashboard/_updater_card.html plugins/installed/admin_dashboard/templates/admin_dashboard/updates.html plugins/installed/admin_dashboard/views_split/system.py plugins/installed/admin_dashboard/tests/test_updates_apply.py plugins/installed/release_notes/views.py plugins/installed/release_notes/templates/release_notes/index.html plugins/installed/release_notes/help.md plugins/installed/release_notes/tests/test_release_notes.py \
 && git commit -m "feat(updates): Version & updates says what runs and offers no button that cannot work

The page shows the running version, its commit, when it was installed and the
newest pre-deploy backup. On a built image (no .git: every Docker install, our
stores included) the check, Update now and per-app buttons give way to one
line: this store updates when a new version is released. The standalone
/dashboard/updates/ page shares the same card.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Linda says the same

**Files:**
- Modify: `core/assistant/tools/admin_ops.py`, lines 16–67 (`updates.status` and `updates.apply`)
- Test: `core/assistant/tests/test_admin_ops.py`, the `UpdatesToolsTests` class (lines 81–115)

**Interfaces:**
- Consumes: `core.deploys.running_release()` and `core.updates.can_self_update()` (Task 3).
- Produces: `updates.status` output keys `running`, `platform` and `core`. `updates.apply` on a built image returns `{'ok': False, 'status': 'unavailable', 'reason': 'no git checkout'}`.

- [ ] **Step 1: Write the failing tests**

In `core/assistant/tests/test_admin_ops.py`, add `from django.conf import settings` to the imports. Wrap the bodies of `test_apply_requires_hard_gate` and `test_apply_calls_guarded_updater` in `with patch('core.updates.can_self_update', return_value=True):`, because they describe a git install. Append these tests to `UpdatesToolsTests`:

```python
    def test_status_on_a_built_image_says_it_updates_on_release(self):
        from core.assistant.tools.admin_ops import updates_status_tool

        status = {'source': 'git', 'available': 'unavailable', 'reason': 'No git metadata.'}
        with (
            patch('core.updates.can_self_update', return_value=False),
            patch('core.updates.platform_update_status', return_value=status),
        ):
            r = updates_status_tool.invoke({})
        self.assertIn('This store updates when a new version is released', r.display)
        self.assertNotIn('Update unavailable', r.display)
        self.assertEqual(r.output['running']['version'], settings.MORPHEUS_VERSION)
        self.assertFalse(r.output['running']['self_update'])

    def test_apply_on_a_built_image_says_it_cannot_run_here(self):
        from core.assistant.tools.admin_ops import updates_apply_tool

        with (
            patch('core.updates.can_self_update', return_value=False),
            patch('core.updates.apply_platform_update') as ap,
        ):
            r = updates_apply_tool.invoke({})
        ap.assert_not_called()
        self.assertEqual(r.output['status'], 'unavailable')
        self.assertIn("can't update itself", r.display)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.assistant.tests.test_admin_ops -v 2 2>&1 | tail -15`

Expected: `test_status_on_a_built_image_says_it_updates_on_release` fails on `r.output['running']` with `KeyError: 'running'`. `test_apply_on_a_built_image_says_it_cannot_run_here` raises `ToolError`, because it hits the confirmation gate first.

- [ ] **Step 3: Implement**

In `core/assistant/tools/admin_ops.py`, replace the `updates.status` and `updates.apply` tools (lines 16–67) with:

```python
@tool(
    name='updates.status',
    description=(
        'Report what this store runs: version, commit, when it was installed, the backup of '
        'the database made before the last update that changed it, and whether the store '
        'can update itself. Where it can (a git checkout), also whether an update is '
        'available and how many commits behind upstream. Read-only.'
    ),
    scopes=['system.read'],
    schema={'type': 'object', 'properties': {}},
)
def updates_status_tool() -> ToolResult:
    from core.deploys import running_release  # noqa: PLC0415
    from core.updates import platform_update_status  # noqa: PLC0415
    from core.versioning import component_versions  # noqa: PLC0415

    running = running_release()
    status = platform_update_status(fetch=True)
    versions = component_versions()
    output = {'running': running, 'platform': status, 'core': versions.get('core')}
    if not running['self_update']:
        return ToolResult(output=output, display=_built_image_summary(running, status))
    return ToolResult(
        output=output,
        display=(
            f'Update {status.get("available")} — deployed {status.get("current")}'
            f'{", " + str(status.get("behind")) + " behind" if status.get("behind") else ""}.'
        ),
    )


def _built_image_summary(running: dict, status: dict) -> str:
    """What updates.status says on a store that cannot update itself."""
    parts = [f'Running {running["version"]}']
    if running['commit']:
        parts.append(f' (commit {running["commit_short"]})')
    if running['deployed_at']:
        parts.append(f', installed {running["deployed_at"]:%Y-%m-%d %H:%M} UTC')
    parts.append('. This store updates when a new version is released; it cannot update itself.')
    if status.get('available') == 'yes' and status.get('latest'):
        parts.append(f' {status["latest"]} is out.')
    if running['backup']:
        taken = running['backup']['taken_at']
        parts.append(
            f' Database backup from before the last update that changed it: {taken:%Y-%m-%d %H:%M} UTC.'
        )
    return ''.join(parts)


@tool(
    name='updates.apply',
    description=(
        'Apply the pending platform update (git fast-forward + backup + migrate '
        '+ healthcheck + auto-rollback). Only a store that runs from a git checkout can: '
        'check updates.status first. Anywhere else (a built image, like most stores) this '
        'answers that the store updates when a new version is released. '
        'DEPLOYMENT-MUTATING: after the user approves, pass confirmed=True, '
        'hard_gate_ack="YES", and echo="platform update". Requires '
        'MORPHEUS_SELF_UPDATE_ENABLED on the server.'
    ),
    scopes=['system.write'],
    schema={
        'type': 'object',
        'properties': {
            'confirmed': {'type': 'boolean', 'default': False},
            'hard_gate_ack': {'type': 'string', 'default': ''},
            'echo': {'type': 'string', 'default': ''},
        },
    },
    requires_approval=True,
)
def updates_apply_tool(
    *, confirmed: bool = False, hard_gate_ack: str = '', echo: str = ''
) -> ToolResult:
    from core.updates import apply_platform_update, can_self_update  # noqa: PLC0415

    if not can_self_update():
        return ToolResult(
            output={'ok': False, 'status': 'unavailable', 'reason': 'no git checkout'},
            display=(
                "This store can't update itself: it runs from a built image and updates "
                'when a new version is released. There is nothing to apply here.'
            ),
        )
    _require_confirmed(confirmed)
    _require_hard_gate(hard_gate_ack=hard_gate_ack, target_name='platform update', echo=echo)
    result = apply_platform_update(confirm=True)
    return ToolResult(output=result, display=f'Update {result.get("status")}.')
```

Tool output is serialized with `json.dumps(…, default=str)` (`core/agents/runtime.py:73` and `agent_mcp`), so the datetimes in `running` reach Linda as text.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' .venv/bin/python manage.py test core.assistant.tests.test_admin_ops core.assistant.tests.test_role_tiers core.assistant.tests.test_enforcement plugins.installed.agent_mcp.tests.test_linda_turn -v 2 2>&1 | tail -12`

Expected: `OK`. `test_linda_turn` still checks that the catalogue resolves (`LindaCatalogueTests`), and the tools' signatures are unchanged.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check core/assistant/tools/admin_ops.py core/assistant/tests/test_admin_ops.py \
 && .venv/bin/ruff format core/assistant/tools/admin_ops.py core/assistant/tests/test_admin_ops.py \
 && git add core/assistant/tools/admin_ops.py core/assistant/tests/test_admin_ops.py \
 && git commit -m "feat(linda): updates.status says what runs; updates.apply says it can't run on a built image

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Docs, checks and the release commit

**Files:**
- Modify: `docs/UPDATING.md` (status header; a new section before `## What does not work, and why`; the "inert" subsection; Rules; quick reference)
- Modify: `docs/OPERATIONS_RUNBOOK.md` (`## Rollback`, `## Backups`)
- Modify: `docs/ARCHITECTURE.md` (the `core/` tree)
- Modify: `CLAUDE.md` (the named-volume landmine, and a new convention after the "merging to `main` deploys" landmine)
- Modify (by `manage.py release`): `morph/settings.py` (`MORPHEUS_VERSION`), `docs/RELEASE_NOTES.md`

**Interfaces:** consumes everything above and produces nothing new.

- [ ] **Step 1: `docs/UPDATING.md`**

Change the status quote's first sentence to:

```markdown
> Status of this document: **verified against the running deployment on
> 2026-08-11 (v0.42.0)**, updated 2026-08-13 for v0.44.0 and 2026-10-19 for v0.118.0 (safe deploys).
```

The rest of the quote is unchanged. Insert this section before `## What does not work, and why`, after the `---` that ends the Janus section:

````markdown
## Safe deploys (v0.118.0)

Our stores, and any Docker install, update by deploying a new image: a push to
`main` builds it, and the platform replaces the containers. On every boot the web
container's entrypoint (`scripts/docker-entrypoint.sh`, `run_migrations`) runs
`manage.py safe_migrate` in place of `migrate`:

1. **Backup first.** When `migrate` has anything to apply, it backs the database
   up (`morph_backup --no-media --keep 5`) into
   `$MORPHEUS_BACKUP_DIR/pre-deploy/`. The default is `/app/backups/pre-deploy/`,
   on the `backup_data` volume the web and worker containers share. The file is
   named after the version and commit being deployed:
   `morpheus-backup-<UTC time>-<version>-<commit>.tar.gz`.
   - If the backup fails, the command exits non-zero and nothing is migrated.
   - With nothing to migrate, or on a new, empty database, there is no backup.
   - A restart of the same container (a crash loop) does not back up again. A
     marker in `/tmp` says the step was done, and a second copy could be of a
     half-migrated database.
2. **`migrate`**, as before.
3. **A record.** `DeployEvent` holds the version, the commit (`SOURCE_COMMIT`,
   which Coolify sets), the time, the backup's path and the migrations applied.
   A restart of the same deploy adds nothing. A failure to record never stops
   the store.

The three steps run in one process because each `manage.py` start costs about 3 s
of the 503 every deploy shows. A deploy with nothing to migrate boots as fast as
before.

Settings → Version & updates shows the running version, its commit, when it was
installed and the newest pre-deploy backup. Without `.git`
(`core.updates.can_self_update()`), it shows "This store updates when a new
version is released." where the check and apply buttons were. Linda's
`updates.status` says the same, and `updates.apply` answers that it cannot run
there.

The nightly backups (03:30 UTC, from the backups app) stay in the folder above,
seven kept, and deploys never rotate them. The backup folder is the
`MORPHEUS_BACKUP_DIR` env var only, never a setting: staff and Linda can write
settings, and a dump in a served folder is public.

Restoring is by hand for now ([`OPERATIONS_RUNBOOK.md`](OPERATIONS_RUNBOOK.md),
Backups). Still to come, per
[`superpowers/specs/2026-10-19-safe-deploys-design.md`](superpowers/specs/2026-10-19-safe-deploys-design.md):

- a CI check that a release's migrations are safe for the previous version;
- a restore command and page;
- an automatic code rollback when a store does not come up.

---
````

In `### The updater is inert on this production deployment`, replace the sentence "So the Version & updates page reports `unavailable`, and `morph_apply_update` refuses, by design." with:

```markdown
So `morph_apply_update` refuses, by design. Since v0.118.0 the Version & updates page and Linda say so plainly, instead of offering check and apply buttons that cannot work there.
```

Add this bullet to `## Rules (do not regress these)`:

```markdown
- **A deploy that migrates is backed up first.** The entrypoint's `run_migrations` calls `safe_migrate`, never bare `migrate`; a failed backup must stop the boot before anything is migrated.
```

Append this to the end of the operator quick reference, after the "On a **container deployment**" paragraph:

````markdown
```bash
# Backups taken before migrating (database only, five kept)
ls -l /app/backups/pre-deploy/

# What was deployed, when, with which backup
python manage.py shell -c "from core.models import DeployEvent; print(*DeployEvent.objects.values_list('deployed_at', 'version', 'commit', 'backup')[:10], sep='\n')"
```
````

- [ ] **Step 2: `docs/OPERATIONS_RUNBOOK.md`**

In `## Rollback`, replace the `Schema:` bullet with:

```markdown
- Schema: migrations are not auto-reversed. Since v0.118.0, every deploy that
  migrates first backs the database up to `/app/backups/pre-deploy/`, named
  after the version it was taken before, and stops before migrating if that
  backup fails. If a migration crashed mid-apply, restore that backup (see
  Backups), then redeploy the last good commit.
```

Replace the `## Backups` bullets with:

````markdown
- **Nightly** (the backups app, 03:30 UTC): database and media to
  `/app/backups/morpheus-backup-<UTC>.tar.gz`, seven kept.
- **Before each deploy that migrates** (`manage.py safe_migrate`, v0.118.0): the
  database alone to `/app/backups/pre-deploy/morpheus-backup-<UTC>-<version>-<commit>.tar.gz`,
  five kept. `DeployEvent` rows say which deploy took which.
- Both live on the store's `backup_data` volume, which the web and worker
  containers mount, **on the same host as the store**. They are not off-site.
- **Rehearse a restore** into a scratch database; it never touches the store's
  data. A backup that has never been restored is a guess, not a plan. In the
  store's web container, run
  `docker exec -i <web> python manage.py shell < this snippet`:

  ```python
  import os, subprocess, tarfile, tempfile
  from django.conf import settings
  from django.db import connection
  from core.models import DeployEvent

  db = settings.DATABASES['default']
  env = dict(os.environ, PGPASSWORD=db['PASSWORD'])
  conn = ['-h', db['HOST'], '-p', str(db['PORT'] or 5432), '-U', db['USER']]
  backup = DeployEvent.objects.exclude(backup='').first().backup
  with tempfile.TemporaryDirectory() as tmp:
      with tarfile.open(backup) as tar:
          tar.extract('db.dump', tmp, filter='data')
      subprocess.run(['createdb', *conn, 'restore_check'], env=env, check=True)
      try:
          restored = subprocess.run(['pg_restore', *conn, '-d', 'restore_check', '--no-owner', f'{tmp}/db.dump'], env=env, capture_output=True, text=True)
          print('RESTORE pg_restore exit', restored.returncode, restored.stderr[-400:])
          copy = subprocess.run(['psql', *conn, '-d', 'restore_check', '-tAc', 'select count(*) from catalog_product'], env=env, check=True, capture_output=True, text=True).stdout.strip()
          with connection.cursor() as cur:
              cur.execute('select count(*) from catalog_product')
              print('RESTORE products in the copy', copy, '| live', cur.fetchone()[0])
      finally:
          subprocess.run(['dropdb', *conn, 'restore_check'], env=env, check=True)
          print('RESTORE scratch database dropped')
  ```
- **The real restore** is by hand until `morph_restore` ships (safe deploys,
  release 3), and it has not been rehearsed on a live store yet:
  1. Stop web, worker and beat.
  2. Run `pg_restore --clean --if-exists --no-owner` with the dump into `morpheus`.
  3. Start them again and check `/readyz`.
````

- [ ] **Step 3: `docs/ARCHITECTURE.md` and `CLAUDE.md`**

In `docs/ARCHITECTURE.md`'s tree, add this line after the `errors/` lines (`│   │                              #   report for Claude Code, health checks.`):

```
│   ├── deploys.py                 # Safe deploys: backup before migrating, DeployEvent.
```

In `CLAUDE.md`, at the end of the paragraph that begins "**Landmine — a named volume takes the ownership of the image directory…**", append:

```markdown
Until v0.118.0 only the worker mounted `/app/backups`, so a file written there from the web container (a `docker exec web …` backup too) left with the container at the next deploy; the web container mounts it now, for the backup `safe_migrate` takes.
```

Insert a new paragraph between the "**Landmine — merging to `main` deploys to production.**" paragraph and the "**Landmine — a native dep that loads at settings-import is deploy-critical.**" one:

```markdown
**Convention — a deploy that migrates is backed up first (v0.118.0).** The web
container's `run_migrations` runs `manage.py safe_migrate`, not `migrate`:
- When anything is pending, it first backs the database up into
  `/app/backups/pre-deploy` (`morph_backup --no-media`, five kept, named after
  the version and commit). If that backup fails, it exits non-zero without
  migrating.
- It then migrates and writes a `DeployEvent`.

It is one process on purpose: each `manage.py` start costs about 3 s of every
deploy's 503. A restart of the same container skips the backup (a marker in
`/tmp`), because a second copy could be of a half-migrated database. Settings →
Version & updates reads both, and on a store without `.git` it shows one line
where the update buttons were (`core.updates.can_self_update`). Guarded by
`core/tests/test_safe_migrate.py`, `test_deploy_record.py` and
`test_running_release.py`.
```

- [ ] **Step 4: The full suite and the CI gates**

Run the full suite, with output to a file:

```bash
DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress' .venv/bin/python manage.py test > /private/tmp/claude-502/-Users-magnetoid-coding-morph/ea077053-0f76-43ff-a44e-08fa22583365/scratchpad/suite.log 2>&1; tail -5 /private/tmp/claude-502/-Users-magnetoid-coding-morph/ea077053-0f76-43ff-a44e-08fa22583365/scratchpad/suite.log
```

Expected: `OK` (with skips). One known order-dependent flake exists: `test_more_filters_cost_no_more_queries` (68 vs 67 queries). If it is the only failure, run it alone; it must pass there. Any other failure stops the task.

Then run the CI gates:

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check . \
 && .venv/bin/python scripts/check_core_boundary.py && .venv/bin/python scripts/check_plugin_boundary.py && .venv/bin/python scripts/check_plugin_standard.py \
 && DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py check \
 && DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py makemigrations --check --dry-run
```

Expected: every step passes, with `No changes detected` last. If `check_plugin_standard.py` reports a baseline entry that no longer reproduces, run it with `--save` and add `scripts/plugin_standard_baseline.json` to the commit below.

- [ ] **Step 5: Commit the docs, then cut the release**

```bash
git add docs/UPDATING.md docs/OPERATIONS_RUNBOOK.md docs/ARCHITECTURE.md CLAUDE.md \
 && git commit -m "docs: safe deploys (backup before migrating, DeployEvent, the honest updates page)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py release --minor "Safe deploys: the database is backed up before any update that changes it" \
  -m "Before an update that changes the database, the store now backs the database up first and keeps the last five of these backups. If the backup fails, the update stops before changing anything." \
  -m "Settings → Version & updates shows the version the store runs, its commit, when it was installed, and the newest of those backups." \
  -m "On stores that update when a new version is released (all of ours), that page no longer offers Check for updates and Update now buttons that could not work there; it says so in one line, and Linda says the same." \
  -m "Fixed: the web container had no permanent backup folder, so a backup made from it was lost at the next deploy." \
  --commit
DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py release --check
```

Expected: `release` reports `v0.117.0 → v0.118.0` and commits `morph/settings.py` and `docs/RELEASE_NOTES.md`. `release --check` passes. Amend the release commit's message so it ends with the `Co-Authored-By` line if `release --commit` did not add it. Check with `git log -1 --format=%B`.

---

### Task 6: Ship and verify on the four stores

This is the finish step. Run it only after the final whole-branch review is clean and its fixes are committed. The push deploys all four stores.

**Files:** none changed.

Store web-container uuids:

| Store | uuid |
|---|---|
| dotbooks | `ghtnqf6lw2bg5229lv1sf4h9` |
| Supernatural | `z10xg4j7yq8x1htipw12a368` |
| Montenegro | `fo8rvcg94bmcyi43e8iq9tvm` |
| Irving | `j7xoogxjqgyakdsjw37eneuh` |

Always pin the uuid: `grep -m1 web-` can match another store.

- [ ] **Step 1: The backup volume is writable for the app user on every store**

```bash
for app in ghtnqf6lw2bg5229lv1sf4h9 z10xg4j7yq8x1htipw12a368 fo8rvcg94bmcyi43e8iq9tvm j7xoogxjqgyakdsjw37eneuh; do ~/.ssh/tetra-ssh.sh "w=\$(docker ps --format '{{.Names}}' | grep '^worker-$app' | head -1); docker exec \$w sh -c 'ls -ld /app/backups; mkdir -p /app/backups/pre-deploy && touch /app/backups/pre-deploy/.w && rm /app/backups/pre-deploy/.w && echo writable $app'"; done; ~/.ssh/tetra-ssh.sh "df -h / | tail -1"
```

Expected: `drwxr-xr-x … morpheus morpheus … /app/backups` and `writable <uuid>` for all four. The disk should show at least 20 GB free; it was at 91% with 39 GB free on 2026-10-19. If any store fails, stop: its first boot would crash-loop on the backup.

- [ ] **Step 2: Merge and push**

```bash
git checkout main && git merge --ff-only feat/safe-deploys-1 && git push origin main && git branch -d feat/safe-deploys-1
```

- [ ] **Step 3: Wait for all four stores**

Run: `SMOKE_DEADLINE_SECS=2400 scripts/deploy_smoke.sh v0.118.0`

Expected: every store reports `v0.118.0` on `/readyz`. If one does not converge, use the stuck-queue recovery in `docs/OPERATIONS_RUNBOOK.md`.

- [ ] **Step 4: Mount, backup file and record on every store**

```bash
for app in ghtnqf6lw2bg5229lv1sf4h9 z10xg4j7yq8x1htipw12a368 fo8rvcg94bmcyi43e8iq9tvm j7xoogxjqgyakdsjw37eneuh; do ~/.ssh/tetra-ssh.sh "c=\$(docker ps --format '{{.Names}}' | grep '^web-$app' | head -1); echo \"== $app \$c\"; docker inspect \$c --format '{{range .Mounts}}{{.Name}} {{.Destination}}{{println}}{{end}}' | grep backups; docker exec \$c ls -l /app/backups/pre-deploy/; docker logs \$c 2>&1 | grep safe_migrate | tail -3; docker exec \$c python manage.py shell -c \"from core.models import DeployEvent; e = DeployEvent.objects.first(); print('EVENT', e.version, e.commit[:7], e.backup, e.migrations)\""; done
```

Expected for each store:
- the mount line `<uuid>_backup-data /app/backups`;
- one file `morpheus-backup-<UTC>-v0.118.0-<sha7>.tar.gz` (dotbooks about 55 MB);
- the log lines `[safe_migrate] 1 migrations to run; backing up the database first.` and `[safe_migrate] Recorded v0.118.0 (<sha7>), 1 migrations applied.`;
- `EVENT v0.118.0 <sha7> /app/backups/pre-deploy/morpheus-backup-…tar.gz ['core.0024_deployevent']`.

- [ ] **Step 5: Restart Irving's web container (a plain restart of the same deploy)**

```bash
~/.ssh/tetra-ssh.sh "c=\$(docker ps --format '{{.Names}}' | grep '^web-j7xoogxjqgyakdsjw37eneuh' | head -1); docker restart \$c"
```

Irving is the beta store, hidden until launch. Check it in Step 8, after the other steps have given it time to boot.

- [ ] **Step 6: The page on dotbooks, through a session built in the container**

Never use `force_login` on a live store. Build a session for a superuser and delete it after:

```bash
~/.ssh/tetra-ssh.sh "c=\$(docker ps --format '{{.Names}}' | grep '^web-ghtnqf6lw2bg5229lv1sf4h9' | head -1); docker exec -i \$c python manage.py shell" <<'PY'
from importlib import import_module

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY, get_user_model
from django.test import Client

user = get_user_model().objects.filter(is_superuser=True, is_active=True).first()
session = import_module(settings.SESSION_ENGINE).SessionStore()
session[SESSION_KEY] = str(user.pk)
session[BACKEND_SESSION_KEY] = settings.AUTHENTICATION_BACKENDS[0]
session[HASH_SESSION_KEY] = user.get_session_auth_hash()
session.create()
try:
    client = Client(HTTP_HOST='dotbooks.store', HTTP_X_FORWARDED_PROTO='https')
    client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key
    resp = client.get('/dashboard/apps/release_notes/version/')
    html = resp.content.decode()
    print('PAGE', resp.status_code,
          '| one line', 'This store updates when a new version is released.' in html,
          '| backup', 'Database backup from before the last update' in html,
          '| commit', 'Commit <code>' in html,
          '| Update now', 'Update now' in html, '| Check', 'Check for updates' in html)
finally:
    session.delete()
PY
```

Expected: `PAGE 200 | one line True | backup True | commit True | Update now False | Check False`. A 302 means a second-factor check wants more in the session: report it rather than work around it.

- [ ] **Step 7: Rehearse a restore on Supernatural, into a scratch database**

Run the snippet from `docs/OPERATIONS_RUNBOOK.md` (Backups, "Rehearse a restore") in Supernatural's web container:

```bash
~/.ssh/tetra-ssh.sh "c=\$(docker ps --format '{{.Names}}' | grep '^web-z10xg4j7yq8x1htipw12a368' | head -1); docker exec -i \$c python manage.py shell" < /private/tmp/claude-502/-Users-magnetoid-coding-morph/ea077053-0f76-43ff-a44e-08fa22583365/scratchpad/restore_rehearsal.py
```

First write the runbook snippet, byte for byte, to that scratchpad file.

Expected:
- `RESTORE pg_restore exit 0`. A non-zero exit lists its errors; read them. A harmless notice, such as about the `public` schema, is not a failure if the counts still match.
- `RESTORE products in the copy N | live N`. The two counts are equal, or differ only by products created since the backup.
- `RESTORE scratch database dropped`. If `restore_check` is left behind by an error, drop it before anything else: `dropdb -h postgres -U morpheus restore_check` from the same container, with `PGPASSWORD` set.

- [ ] **Step 8: Irving after its restart, and the error log everywhere**

```bash
~/.ssh/tetra-ssh.sh "c=\$(docker ps --format '{{.Names}}' | grep '^web-j7xoogxjqgyakdsjw37eneuh' | head -1); docker logs --since 10m \$c 2>&1 | grep safe_migrate; docker exec \$c ls /app/backups/pre-deploy/ | wc -l; docker exec \$c python manage.py shell -c \"from core.models import DeployEvent; print('EVENTS', DeployEvent.objects.count())\""
for app in ghtnqf6lw2bg5229lv1sf4h9 z10xg4j7yq8x1htipw12a368 fo8rvcg94bmcyi43e8iq9tvm j7xoogxjqgyakdsjw37eneuh; do ~/.ssh/tetra-ssh.sh "c=\$(docker ps --format '{{.Names}}' | grep '^web-$app' | head -1); docker exec \$c python manage.py shell -c \"from datetime import timedelta; from django.utils import timezone; from core.errors.models import ErrorEvent; print('ERRORS $app', ErrorEvent.objects.filter(created_at__gte=timezone.now() - timedelta(hours=1)).count())\""; done
```

Expected for Irving:
- the log line `[safe_migrate] No migrations to run, so no backup is needed.`;
- the log line `[safe_migrate] v0.118.0 restarted; already recorded.`;
- `1` file and `EVENTS 1`.

Expected for the error log: `ERRORS <uuid> 0` for every store. If a count is not 0, read the events before reporting.

- [ ] **Step 9: Record the outcome in memory**

Update `releases-2026-10-19.md` in `/Users/magnetoid/.claude/projects/-Users-magnetoid-coding-morph/memory/`: v0.118.0 shipped, and what each check above showed. Releases 2–4 of the spec remain.
