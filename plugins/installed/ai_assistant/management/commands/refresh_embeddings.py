"""Backfill ProductEmbedding rows synchronously.

The Celery hook (ai_assistant.plugin.on_product_created/updated) keeps
embeddings fresh on writes, but products created before the hook was
wired (or while the worker wasn't draining) leave the table empty —
which silently degrades similar_to to its category-shuffle fallback.

Run once after deploy to backfill, or after a `populate_descriptions`
run to refresh stale text-hashes. Idempotent: skips rows whose stored
source_text_hash already matches the recomputed digest.

Usage:
    python manage.py refresh_embeddings
    python manage.py refresh_embeddings --slugs pinocchio,moby-dick
    python manage.py refresh_embeddings --force      # ignore hash, rebuild all
"""
from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger('morpheus.ai.embeddings')


class Command(BaseCommand):
    help = 'Backfill / refresh ProductEmbedding rows for active products.'

    def add_arguments(self, parser):
        parser.add_argument('--slugs', default='',
                            help='Comma-separated slugs (default: all active).')
        parser.add_argument('--force', action='store_true',
                            help='Rebuild even when source_text_hash matches.')

    def handle(self, *args, **opts):
        from plugins.installed.ai_assistant.models import ProductEmbedding
        from plugins.installed.ai_assistant.services.search import upsert_product_embedding
        from plugins.installed.catalog.models import Product

        slugs = [s.strip() for s in (opts.get('slugs') or '').split(',') if s.strip()]
        force = bool(opts['force'])

        qs = Product.objects.filter(status='active').select_related('category')
        if slugs:
            qs = qs.filter(slug__in=slugs)

        written = skipped = errored = 0
        for product in qs:
            if force:
                ProductEmbedding.objects.filter(product=product).delete()
            try:
                before = ProductEmbedding.objects.filter(product=product).first()
                upsert_product_embedding(product)
                after = ProductEmbedding.objects.filter(product=product).first()
                if before and after and before.source_text_hash == after.source_text_hash:
                    skipped += 1
                else:
                    written += 1
                    self.stdout.write(f'  embedded {product.slug}')
            except Exception as exc:  # noqa: BLE001
                logger.warning('refresh_embeddings: %s failed: %s', product.slug, exc)
                errored += 1

        self.stdout.write(self.style.SUCCESS(
            f'done — written={written} skipped={skipped} errored={errored}'
        ))
