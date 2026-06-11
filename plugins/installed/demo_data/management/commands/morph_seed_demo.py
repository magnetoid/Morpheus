"""
manage.py morph_seed_demo [--currency USD] [--fresh]

Idempotent seed of the bookstore demo dataset (~25 books, 6 categories,
3 collections, 3 vendors, a couple of customers + a paid order).
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Seed the demo bookstore dataset (idempotent).'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--currency', default='USD', help='ISO currency code for prices (default: USD).'
        )
        parser.add_argument(
            '--fresh',
            action='store_true',
            help='DESTRUCTIVE: delete existing demo rows before re-seeding.',
        )

    def handle(self, *args, **opts) -> None:
        from plugins.installed.demo_data.services import seed_all

        summary = seed_all(currency=opts['currency'], wipe=opts['fresh'])
        self.stdout.write(self.style.SUCCESS(f'Seeded: {summary.counts}'))
