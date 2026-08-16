"""Check whether a platform, app or theme update is available.

python manage.py morph_check_updates           # fetch + report
python manage.py morph_check_updates --no-fetch # local refs only
python manage.py morph_check_updates --json

The platform half reads the git upstream when there is one, else the
configured release source (core/update_sources.py). The app/theme half always
reads the release source — those channels never depended on git.
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from core.update_sources import component_updates
from core.updates import platform_update_status


class Command(BaseCommand):
    help = 'Check for platform, app and theme updates.'

    def add_arguments(self, parser) -> None:
        parser.add_argument('--no-fetch', action='store_true', help='Skip git fetch.')
        parser.add_argument('--json', action='store_true', help='Emit JSON.')

    def handle(self, *args, **opts) -> None:
        status = platform_update_status(fetch=not opts.get('no_fetch'))
        # A git deployment's status carries no components; a gitless one
        # already does. Ask once either way — the source memoises the fetch.
        if 'components' not in status:
            status['components'] = component_updates()
        if opts.get('json'):
            self.stdout.write(json.dumps(status, indent=2))
            return
        avail = status.get('available')
        if avail == 'yes':
            behind = status.get('behind')
            detail = (
                f'{behind} commit(s) behind {status.get("upstream")}'
                if behind is not None
                else f'latest {status.get("latest")}'
            )
            self.stdout.write(
                self.style.WARNING(
                    f'Update available: {detail} (deployed {status.get("current")}).'
                )
            )
        elif avail == 'no':
            self.stdout.write(self.style.SUCCESS(f'Up to date ({status.get("current")}).'))
        else:
            self.stdout.write(f'Update status {avail}: {status.get("reason", "")}')

        components = status.get('components') or []
        if not components:
            self.stdout.write('Apps/themes: nothing newer published for what is installed.')
            return
        self.stdout.write(self.style.WARNING(f'{len(components)} app/theme update(s):'))
        for c in components:
            note = '' if c.get('core_ok', True) else f'  (needs core {c.get("min_core")} first)'
            self.stdout.write(
                f'  {c["kind"]:5} {c["name"]:24} {c["current"]} → {c["latest"]}{note}'
            )
