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
                f'Restored {outcome["file"]}. The data from before it is in '
                f'pre-restore/{outcome["pre_restore"]}.'
            )
        )
        if outcome.get('missing'):
            self.stdout.write(
                self.style.WARNING(
                    'This backup lacks migrations the running version needs: '
                    f'{", ".join(outcome["missing"])}. Until they run, parts of the store fail. '
                    'If one of them is why you restored, put the previous version back first. '
                    'Redeploy the store, or run manage.py migrate, to apply them.'
                )
            )
        self.stdout.write('Restart the worker and beat, so background jobs read the restored data.')


def _whoami() -> str:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 — a missing login name only blanks the record
        return ''
