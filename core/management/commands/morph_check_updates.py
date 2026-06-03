"""Check whether a platform update is available (git channel, phase 3).

python manage.py morph_check_updates           # fetch + report
python manage.py morph_check_updates --no-fetch # local refs only
python manage.py morph_check_updates --json
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from core.updates import platform_update_status


class Command(BaseCommand):
    help = 'Check for a platform update against the tracked git upstream.'

    def add_arguments(self, parser) -> None:
        parser.add_argument('--no-fetch', action='store_true', help='Skip git fetch.')
        parser.add_argument('--json', action='store_true', help='Emit JSON.')

    def handle(self, *args, **opts) -> None:
        status = platform_update_status(fetch=not opts.get('no_fetch'))
        if opts.get('json'):
            self.stdout.write(json.dumps(status, indent=2))
            return
        avail = status.get('available')
        if avail == 'yes':
            self.stdout.write(
                self.style.WARNING(
                    f'Update available: {status.get("behind")} commit(s) behind '
                    f'{status.get("upstream")} (deployed {status.get("current")}).'
                )
            )
        elif avail == 'no':
            self.stdout.write(self.style.SUCCESS(f'Up to date ({status.get("current")}).'))
        else:
            self.stdout.write(f'Update status {avail}: {status.get("reason", "")}')
