"""Seed the full researched Montenegro experience catalog (idempotent).

~100 real, web-researched experiences on top of the launch set, plus
name/copy renames of the launch experiences (slug-keyed). Safe to re-run.

    python manage.py seed_experiences_full
"""

from __future__ import annotations

from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from djmoney.money import Money

from plugins.installed.booking_marketplace.management.commands._experiences_data import (
    NEW_EXPERIENCES,
    RENAMES,
)

SEED_DIR = Path(__file__).resolve().parents[2] / 'seed_assets'


class Command(BaseCommand):
    help = 'Seed ~100 researched experiences + apply launch-set renames (idempotent).'

    def handle(self, *args, **opts):
        from plugins.installed.booking_marketplace.models import BookableService
        from plugins.installed.catalog.models import Category, Vendor

        created = renamed = 0
        for slug, fields in RENAMES.items():
            renamed += BookableService.objects.filter(slug=slug).update(**fields)
        for row in NEW_EXPERIENCES:
            if BookableService.objects.filter(slug=row['slug']).exists():
                continue
            vendor, _ = Vendor.objects.get_or_create(
                slug=slugify(row['host']), defaults={'name': row['host'], 'is_active': True}
            )
            category, _ = Category.objects.get_or_create(
                slug=slugify(row['category']),
                defaults={'name': row['category'], 'is_active': True},
            )
            svc = BookableService(
                slug=row['slug'],
                name=row['name'],
                vendor=vendor,
                category=category,
                region=row['region'],
                location=row['location'],
                short_description=row['short_description'],
                description=row['description'],
                duration_minutes=row['duration_minutes'],
                duration_label=row['duration_label'],
                price=Money(row['price'], 'EUR'),
                original_price=(
                    Money(row['original_price'], 'EUR') if row.get('original_price') else None
                ),
                rating=row.get('rating', 0),
                review_count=0,
                is_bestseller=row.get('is_bestseller', False),
                highlights=row.get('highlights', []),
                included=row.get('included', []),
                not_included=row.get('not_included', []),
                itinerary=row.get('itinerary', []),
                faqs=row.get('faqs', []),
                meeting_point=row.get('meeting_point', ''),
                latitude=row.get('latitude'),
                longitude=row.get('longitude'),
                languages=row.get('languages', ['English']),
                what_to_bring=row.get('what_to_bring', []),
                daily_capacity=row.get('daily_capacity', 10),
                max_guests_per_booking=row.get('max_guests_per_booking', 8),
                listing_kind='experience',
                is_active=True,
            )
            img = SEED_DIR / row['image']
            if img.exists():
                with img.open('rb') as fh:
                    svc.image.save(f'{row["slug"]}.jpg', File(fh), save=False)
            svc.save()
            created += 1
        self.stdout.write(self.style.SUCCESS(f'Experiences: {created} created, {renamed} renamed.'))
