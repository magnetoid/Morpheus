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
