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
