"""Seed the Privacy / Terms / Imprint CMS pages (idempotent).

Usage:
    python manage.py seed_legal_pages
    python manage.py seed_legal_pages --force   # overwrite existing bodies
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from plugins.installed.gdpr.services import seed_legal_pages


class Command(BaseCommand):
    help = 'Seed the Privacy / Terms / Imprint legal pages as CMS Pages.'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--force',
            action='store_true',
            help='Overwrite existing page bodies (otherwise existing slugs are left alone).',
        )

    def handle(self, *args, **opts) -> None:
        tally = seed_legal_pages(force=bool(opts.get('force')))
        self.stdout.write(
            self.style.SUCCESS(
                'done — created={created} updated={updated} skipped={skipped}'.format(**tally)
            )
        )
