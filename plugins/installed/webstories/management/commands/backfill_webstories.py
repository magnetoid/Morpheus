"""Backfill Web Stories for every active product that has at least one image.

Idempotent: re-running just refreshes the panels from current data.
Skips products without images (no story would render anyway).

Usage::

    python manage.py backfill_webstories
    python manage.py backfill_webstories --dry-run
    python manage.py backfill_webstories --limit 50
"""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

from plugins.installed.catalog.models import Product
from plugins.installed.webstories.services import ensure_story

logger = logging.getLogger('morpheus.webstories')


class Command(BaseCommand):
    help = 'Backfill Web Stories for every active product with at least one image.'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Count eligible products without writing.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Cap on number of products to process (0 = no limit).',
        )

    def handle(self, *args, **options) -> None:
        dry_run = options['dry_run']
        limit = options['limit']

        qs = (
            Product.objects.filter(status='active', images__isnull=False)
            .distinct()
            .order_by('-updated_at')
        )
        if limit > 0:
            qs = qs[:limit]

        total = qs.count()
        self.stdout.write(f'Found {total} eligible products{" (dry-run)" if dry_run else ""}')

        if dry_run:
            return

        ok = 0
        failed = 0
        for i, product in enumerate(qs.iterator(chunk_size=100), start=1):
            try:
                ensure_story(product)
                ok += 1
            except Exception as e:  # noqa: BLE001
                failed += 1
                logger.warning('backfill_webstories: %s failed: %s', product.slug, e)
            if i % 100 == 0:
                self.stdout.write(f'  …{i}/{total} processed')

        self.stdout.write(self.style.SUCCESS(f'Backfilled {ok} stories ({failed} failed).'))
