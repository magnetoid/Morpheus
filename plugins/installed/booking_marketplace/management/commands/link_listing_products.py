"""Link every booking listing to its catalog Product (docs/plans/booking-extends-product-2026-10.md).

Writes a JSON backup of the listings and of every product that could be reused before
anything changes, and changes nothing when the backup cannot be written. Listings
already linked are skipped, so a second run does nothing.

    python manage.py link_listing_products --backup /tmp/listings-before-link.json
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.products import ensure_product
from plugins.installed.catalog.models import Product


class Command(BaseCommand):
    help = 'Link every booking listing to its catalog Product, after a JSON backup.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--backup', required=True, help='JSON file written before anything changes.'
        )

    def handle(self, *args, backup: str, **options):
        listings = list(BookableService.objects.filter(product__isnull=True).order_by('slug'))
        # A listing reuses a same-named product on its slug or `<slug>-experience…`.
        reusable = Q(pk__in=[])
        for service in listings:
            reusable |= Q(slug__startswith=service.slug)
        data = {
            'listings': json.loads(serializers.serialize('json', BookableService.objects.all())),
            'products': json.loads(serializers.serialize('json', Product.objects.filter(reusable))),
        }
        try:
            Path(backup).write_text(json.dumps(data, indent=1))
        except OSError as e:
            raise CommandError(f'Backup not written ({e}); nothing changed.') from e
        self.stdout.write(
            f'backup: {backup} ({len(data["listings"])} listings, {len(data["products"])} products)'
        )

        before = Product.objects.count()
        linked, failed = 0, []
        for service in listings:
            try:
                ensure_product(service)
                linked += 1
            except Exception as e:  # noqa: BLE001 — one bad listing never stops the rest
                failed.append(service.slug)
                self.stderr.write(f'{service.slug}: {e}')
        created = Product.objects.count() - before
        summary = f'linked={linked} reused={linked - created} created={created}'
        if failed:
            summary += f' failed={len(failed)}: {", ".join(failed)}'
        self.stdout.write(summary)
