"""Apply an update — the platform (git fast-forward) or one app / theme (signed
manifest artifact). Dry-run by default.

    manage.py morph_apply_update                    # platform: print the plan, no changes
    manage.py morph_apply_update --confirm          # platform: apply (needs MORPHEUS_SELF_UPDATE_ENABLED=1)
    manage.py morph_apply_update --confirm --no-migrate
    manage.py morph_apply_update --app  NAME [--confirm]   # one app, from the signed manifest
    manage.py morph_apply_update --theme NAME [--confirm]  # one theme

Both paths back up first, probe the new code in a fresh interpreter, run
migrations + healthcheck, and roll back on failure. See docs/UPDATING.md.
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from core.component_updates import apply_component_update
from core.updates import apply_platform_update


class Command(BaseCommand):
    help = 'Apply a platform, app or theme update (dry-run unless --confirm).'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--confirm', action='store_true', help='Actually apply (mutates the install).'
        )
        parser.add_argument('--no-migrate', action='store_true', help='Skip running migrations.')
        parser.add_argument(
            '--allow-dep-changes',
            action='store_true',
            help='Platform only: apply even if dependency manifests changed (you must pip-install them).',
        )
        target = parser.add_mutually_exclusive_group()
        target.add_argument('--app', default='', help='Update this app from the signed manifest.')
        target.add_argument(
            '--theme', default='', help='Update this theme from the signed manifest.'
        )
        parser.add_argument('--json', action='store_true', help='Emit JSON.')

    def handle(self, *args, **opts) -> None:
        if opts.get('app') or opts.get('theme'):
            kind, name = ('app', opts['app']) if opts.get('app') else ('theme', opts['theme'])
            result = apply_component_update(
                kind,
                name,
                confirm=opts.get('confirm', False),
                run_migrations=not opts.get('no_migrate', False),
            )
        else:
            result = apply_platform_update(
                confirm=opts.get('confirm', False),
                run_migrations=not opts.get('no_migrate', False),
                allow_dependency_changes=opts.get('allow_dep_changes', False),
            )
        if opts.get('json'):
            self.stdout.write(json.dumps(result, indent=2))
        else:
            self.stdout.write(f'status: {result.get("status")}')
            if result.get('plan'):
                self.stdout.write(f'  plan: {result["plan"]}')
            for k in ('message', 'reason', 'from', 'to'):
                if result.get(k):
                    self.stdout.write(f'  {k}: {result[k]}')
            if result.get('restart_required'):
                self.stdout.write(
                    self.style.WARNING('  restart the web/worker processes to load the new code')
                )
        if not result.get('ok'):
            raise CommandError(result.get('reason') or f'update {result.get("status")}')
