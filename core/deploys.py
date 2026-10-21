"""Safe deploys: a database backup before migrating, and a record of each deploy.

On every boot the web container's entrypoint (scripts/docker-entrypoint.sh) runs
``manage.py safe_migrate`` in place of ``migrate``:

1. When ``migrate`` has anything to apply, it backs the database up first into
   ``<MORPHEUS_BACKUP_DIR>/pre-deploy/``, keeping the last five, named after the
   version and commit being deployed. If the backup fails, it exits non-zero
   before migrating, so the store stays on a schema the previous version knows.
2. It migrates.
3. It records the deploy as a ``DeployEvent`` (version, commit, the backup's
   path, the migrations applied). A restart of the same deploy adds nothing.

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
from datetime import UTC, datetime
from pathlib import Path

#: Pre-deploy backups kept. The nightly ones rotate separately, in the folder above.
BACKUP_KEEP = 5
HANDOFF = Path(tempfile.gettempdir()) / 'morpheus-predeploy.json'
_COMMIT = re.compile(r'^[0-9a-f]{7,40}$')
_ARCHIVE = re.compile(r'^morpheus-backup-(\d{8}T\d{6}Z)(?:-(.+))?\.tar\.gz$')


def backup_root() -> Path:
    return Path(os.environ.get('MORPHEUS_BACKUP_DIR') or '/app/backups')


def predeploy_dir() -> Path:
    return backup_root() / 'pre-deploy'


def current_commit() -> str:
    """The commit this image was built from, when the platform says (Coolify sets
    SOURCE_COMMIT); '' otherwise."""
    value = os.environ.get('SOURCE_COMMIT', '').strip().lower()
    return value if _COMMIT.match(value) else ''


_VERSION = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)$')


def version_key(text: str) -> tuple[int, int, int] | None:
    """``vX.Y.Z`` as numbers, for comparing releases; None for anything else."""
    match = _VERSION.match(str(text or '').strip())
    return tuple(int(part) for part in match.groups()) if match else None  # type: ignore[return-value]


def is_older(version: str, than: str) -> bool:
    a, b = version_key(version), version_key(than)
    return a is not None and b is not None and a < b


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
    if marker.get('recorded') and (marker.get('version'), marker.get('commit')) == (
        version,
        commit,
    ):
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
    return send_alert(
        f'{name}: {failed} did not come up, so the store is back on {event.version}', body
    )


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


def running_release() -> dict:
    """What this store runs, for Settings → Version & updates and Linda's
    ``updates.status``: version, commit, when it was installed, the newest
    pre-deploy backup, whether it can update itself, and how the last restore ended."""
    from django.conf import settings
    from django.db import DatabaseError, transaction

    from core import restore
    from core.models import DeployEvent
    from core.updates import can_self_update

    version, commit = str(settings.MORPHEUS_VERSION), current_commit()
    try:
        with transaction.atomic():
            event = DeployEvent.objects.filter(version=version, commit=commit).first()
    except DatabaseError:
        # Restored from a backup older than the code: no table until migrate runs,
        # and this page must still show how the restore went.
        event = None
    return {
        'version': version,
        'commit': commit,
        'commit_short': commit[:7],
        'deployed_at': event.deployed_at if event else None,
        'backup': latest_predeploy_backup(),
        'self_update': can_self_update(),
        'last_restore': restore.last(),
        'rolled_back_from': event.rolled_back_from if event else '',
        'failed_backup': failed_backup_name(event.rolled_back_from)
        if event and event.rolled_back_from
        else '',
    }
