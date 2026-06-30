"""Apply a platform update (git fast-forward) — phase 4. Dry-run by default.

    manage.py morph_apply_update             # dry-run: print the plan, no changes
    manage.py morph_apply_update --confirm   # apply (needs MORPHEUS_SELF_UPDATE_ENABLED=1)
    manage.py morph_apply_update --confirm --no-migrate

Backs up first, fast-forwards only, runs migrations + healthcheck, and rolls
the code back on failure. See docs/plans/updating-system-2026-06.md.
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from core.updates import apply_platform_update


class Command(BaseCommand):
    help = 'Apply a platform update via git fast-forward (dry-run unless --confirm).'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--confirm', action='store_true', help='Actually apply (mutates the checkout).'
        )
        parser.add_argument('--no-migrate', action='store_true', help='Skip running migrations.')
        parser.add_argument(
            '--allow-dep-changes',
            action='store_true',
            help='Apply even if dependency manifests changed (you must pip-install them).',
        )
        parser.add_argument('--json', action='store_true', help='Emit JSON.')

    def handle(self, *args, **opts) -> None:
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
        if not result.get('ok'):
            raise CommandError(result.get('reason') or f'update {result.get("status")}')
