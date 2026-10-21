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
import logging
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from django.core.management import call_command
from django.http import HttpResponse

from core import deploys
from core.management.commands.morph_backup import Command as BackupCommand

#: Seconds without a heartbeat after which a restore counts as dead.
STALE_AFTER = 90
HEARTBEAT = 5
#: Backups of the data a restore replaced, kept in ``pre-restore/``.
PRE_RESTORE_KEEP = 3
#: The folders the restore screen lists, under MORPHEUS_BACKUP_DIR.
KINDS = {'nightly': '', 'pre-deploy': 'pre-deploy', 'pre-restore': 'pre-restore'}

logger = logging.getLogger('morpheus.restore')


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
        'pg_restore',
        '--clean',
        '--if-exists',
        '--no-owner',
        '--no-acl',
        '--single-transaction',
        '--exit-on-error',
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


def losses(since: datetime) -> list[dict]:
    """What restoring a backup made at ``since`` replaces, as each app counts it
    (RESTORE_LOSSES): ``[{'label': 'orders placed', 'count': 4}, …]``, without
    zero counts. A failing app is skipped by the bus, and the others still count."""
    from core.hooks import MorpheusEvents, hook_registry

    rows = hook_registry.filter(MorpheusEvents.RESTORE_LOSSES, [], since=since) or []
    return [row for row in rows if isinstance(row, dict) and row.get('count')]


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
        sys.executable,
        str(Path(settings.BASE_DIR) / 'manage.py'),
        'morph_restore',
        str(archive),
        '--confirm',
        confirm,
        '--by',
        by,
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
