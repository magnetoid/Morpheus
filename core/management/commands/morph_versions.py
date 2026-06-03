"""Print the installed-component version inventory (core, plugins, themes).

    python manage.py morph_versions          # human table
    python manage.py morph_versions --json    # machine-readable

The read-only first surface of the updating system — see
docs/plans/updating-system-2026-06.md.
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from core.versioning import component_versions


class Command(BaseCommand):
    help = 'List installed component versions (core, plugins, themes).'

    def add_arguments(self, parser) -> None:
        parser.add_argument('--json', action='store_true', help='Emit JSON.')

    def handle(self, *args, **opts) -> None:
        data = component_versions()
        if opts.get('json'):
            self.stdout.write(json.dumps(data, indent=2))
            return

        self.stdout.write(self.style.MIGRATE_HEADING(f'Morpheus core: {data["core"]}'))

        plugins = data['plugins']
        enabled = sum(1 for p in plugins if p['enabled'])
        self.stdout.write(
            self.style.MIGRATE_HEADING(f'\nPlugins ({enabled}/{len(plugins)} enabled):')
        )
        for p in plugins:
            mark = 'on ' if p['enabled'] else 'off'
            self.stdout.write(f'  [{mark}] {p["name"]:<24} v{p["version"]}')

        themes = data['themes']
        self.stdout.write(self.style.MIGRATE_HEADING(f'\nThemes ({len(themes)}):'))
        for t in themes:
            mark = '* ' if t['active'] else '  '
            self.stdout.write(f'  {mark}{t["name"]:<24} v{t["version"]}')
