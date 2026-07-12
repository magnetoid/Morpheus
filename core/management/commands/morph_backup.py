"""`python manage.py morph_backup` — dump database + media to local disk.

Configuration via env:
    MORPHEUS_BACKUP_DIR  (default: /tmp/morpheus-backups)
    MORPHEUS_BACKUP_KEEP (default: 7)  — keep N most recent backups

For Postgres uses `pg_dump`; for SQLite copies the file. Media is tarred
from MEDIA_ROOT. Output: a single `.tar.gz` per run timestamped UTC.

Schedule via Celery beat: see plugins/installed/agent_core/plugin.py
for the registration pattern. We don't auto-register here so merchants
opt in by adding the entry — backups are storage-heavy and we don't
want them silently consuming disk on day one.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger('morpheus.backup')


class Command(BaseCommand):
    help = 'Dump database + media to MORPHEUS_BACKUP_DIR (default /app/backups).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dest',
            # Default to a path that is volume-mounted in compose so dumps SURVIVE
            # a redeploy. /tmp lived inside the container and was wiped on every
            # deploy (and every merge to main is a deploy), so a "successful"
            # backup was gone within the day.
            default=os.environ.get('MORPHEUS_BACKUP_DIR', '/app/backups'),
        )
        parser.add_argument(
            '--keep', type=int, default=int(os.environ.get('MORPHEUS_BACKUP_KEEP', '7'))
        )
        parser.add_argument('--no-media', action='store_true', help='Skip media files.')

    def handle(self, *args, **options):
        dest = Path(options['dest']).resolve()
        dest.mkdir(parents=True, exist_ok=True)

        ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        archive_path = dest / f'morpheus-backup-{ts}.tar.gz'
        self.stdout.write(self.style.NOTICE(f'Backing up to {archive_path}'))

        with tempfile.TemporaryDirectory(prefix='morph-bk-') as workdir:
            workdir = Path(workdir)  # noqa: PLW2901
            self._dump_database(workdir)
            if not options['no_media']:
                self._snapshot_media(workdir)
            with tarfile.open(archive_path, 'w:gz') as tar:
                for child in workdir.iterdir():
                    tar.add(child, arcname=child.name)

        size_mb = archive_path.stat().st_size / (1024 * 1024)
        self.stdout.write(self.style.SUCCESS(f'Wrote {archive_path} ({size_mb:.1f} MiB)'))

        self._prune(dest, keep=options['keep'])

    def _dump_database(self, workdir: Path) -> None:
        db = settings.DATABASES.get('default') or {}
        engine = db.get('ENGINE') or ''
        out = workdir / 'db.dump'

        if 'postgres' in engine or 'psycopg' in engine:
            cmd = ['pg_dump', '--no-owner', '--no-acl', '-Fc', '-f', str(out)]
            env = os.environ.copy()
            if db.get('HOST'):
                cmd.extend(['-h', db['HOST']])
            if db.get('PORT'):
                cmd.extend(['-p', str(db['PORT'])])
            if db.get('USER'):
                cmd.extend(['-U', db['USER']])
            if db.get('NAME'):
                cmd.append(db['NAME'])
            if db.get('PASSWORD'):
                env['PGPASSWORD'] = db['PASSWORD']
            self.stdout.write(f'  pg_dump → {out.name}')
            subprocess.run(cmd, check=True, env=env)  # noqa: S603
        elif 'sqlite' in engine:
            shutil.copy2(db['NAME'], out)
            self.stdout.write(f'  copied sqlite db → {out.name}')
        else:
            self.stdout.write(
                self.style.WARNING(f'Unsupported engine: {engine} — skipping db dump')
            )

    def _snapshot_media(self, workdir: Path) -> None:
        media_root = getattr(settings, 'MEDIA_ROOT', None)
        if not media_root or not Path(media_root).exists():
            return
        target = workdir / 'media.tar'
        with tarfile.open(target, 'w') as tar:
            tar.add(media_root, arcname='media')
        self.stdout.write(f'  media → {target.name} ({target.stat().st_size // 1024} KiB)')

    def _prune(self, dest: Path, *, keep: int) -> None:
        archives = sorted(dest.glob('morpheus-backup-*.tar.gz'), reverse=True)
        for old in archives[keep:]:
            try:
                old.unlink()
                self.stdout.write(f'  pruned {old.name}')
            except OSError as e:
                self.stdout.write(self.style.WARNING(f'  prune failed on {old}: {e}'))
