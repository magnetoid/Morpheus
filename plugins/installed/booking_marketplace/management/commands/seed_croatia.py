"""Fill a Croatian store with real places, experiences, hotels and events (idempotent).

croatia-experience.me opened empty. The data is in `seed_data/croatia/`, written to the
owner's rules (docs/plans/croatia-catalogue-2026-11.md):
- every place, hotel and event is real;
- every experience is a real activity at a real place, at a market price, hosted by the
  store itself (the vendor Croatia Experience), because no operator has signed up yet;
- hotels carry no rooms, rates, ratings or amenities, so the guest sends an enquiry;
- nothing gets reviews, a rating, a "was" price or a bestseller flag.

Keyed by slug. A second run creates nothing. A run fills only the fields that are still
empty, so an edit made in the dashboard is never overwritten.

    python manage.py seed_croatia [--only places|experiences|hotels|events]

It refuses to run unless the active theme's country is Croatia: on any other store it
would publish Croatian destinations.
"""

from __future__ import annotations

from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify
from djmoney.money import Money

SEED_DIR = Path(__file__).resolve().parents[2] / 'seed_assets'

HOST_NAME = 'Croatia Experience'
CATEGORIES = ('Adventure', 'Water Sports', 'Culture', 'Dining', 'Wine', 'Wellness')

# Covers until real photos come: the bundled seed images, chosen by type.
PLACE_COVER = {
    'coastal': 'sailing.jpg',
    'mountains': 'hiking.jpg',
    'national_parks': 'hiking.jpg',
    'cultural': 'culture.jpg',
    'cities': 'culture.jpg',
    'lakes': 'kayak.jpg',
}
EXPERIENCE_COVER = {
    'Adventure': 'hiking.jpg',
    'Water Sports': 'kayak.jpg',
    'Culture': 'culture.jpg',
    'Dining': 'dining.jpg',
    'Wine': 'wine.jpg',
    'Wellness': 'spa.jpg',
}

PARTS = ('places', 'experiences', 'hotels', 'events')


def _attach(field, name: str, filename: str) -> None:
    src = SEED_DIR / filename
    if src.exists():
        with src.open('rb') as fh:
            field.save(name, File(fh), save=True)


def _fill(obj, values: dict) -> None:
    """Set each field that is still empty; save only those."""
    dirty = []
    for field, value in values.items():
        current = getattr(obj, field)
        if current in (None, '', [], {}) and value not in (None, '', [], {}):
            setattr(obj, field, value)
            dirty.append(field)
    if dirty:
        obj.save(update_fields=dirty)


class Command(BaseCommand):
    help = 'Fill a Croatian store with real places, experiences, hotels and events (idempotent).'

    def add_arguments(self, parser):
        parser.add_argument('--only', choices=PARTS, help='Seed one part only.')

    def handle(self, *args, only: str | None = None, **opts):
        from plugins.installed.booking_marketplace import country

        code = country.current().code
        if code != 'HR':
            raise CommandError(
                f"seed_croatia fills a Croatian store, and this store's theme names {code}."
            )
        from plugins.installed.booking_marketplace.seed_data import croatia as data

        for part in PARTS:
            if only in (None, part):
                with transaction.atomic():
                    created, total = getattr(self, f'_seed_{part}')(data)
                self.stdout.write(
                    self.style.SUCCESS(f'{part}: {created} created ({total} in the data).')
                )

    # -- parts ---------------------------------------------------------------

    def _host(self):
        from plugins.installed.catalog.models import Vendor

        vendor, _ = Vendor.objects.get_or_create(
            slug=slugify(HOST_NAME), defaults={'name': HOST_NAME, 'is_active': True}
        )
        return vendor

    def _seed_places(self, data) -> tuple[int, int]:
        from plugins.installed.booking_marketplace.models import Place

        created = 0
        for i, p in enumerate(data.PLACES):
            values = {
                'name': p['name'],
                'region': p['region'],
                'place_type': p['place_type'],
                'summary': p['summary'],
                'description': p['description'],
                'highlights': p['highlights'],
                'overview': p['overview'],
                'faqs': p['faqs'],
                'quick_facts': p['quick_facts'],
                'good_for': p['good_for'],
                'sections': p['sections'],
                'external_links': p['external_links'],
                'latitude': p['latitude'],
                'longitude': p['longitude'],
            }
            place, was_created = Place.objects.get_or_create(
                slug=p['slug'],
                defaults={
                    **values,
                    'is_featured': p.get('featured', False),
                    'sort_order': i,
                    'is_active': True,
                },
            )
            if not was_created:
                _fill(place, values)
            if not place.image:
                _attach(place.image, f'{place.slug}.jpg', PLACE_COVER[p['place_type']])
            created += was_created
        return created, len(data.PLACES)

    def _seed_experiences(self, data) -> tuple[int, int]:
        from plugins.installed.booking_marketplace.models import BookableService
        from plugins.installed.booking_marketplace.products import ensure_product
        from plugins.installed.catalog.models import Category

        host = self._host()
        categories = {}
        for name in CATEGORIES:
            categories[name], _ = Category.objects.get_or_create(
                slug=slugify(name), defaults={'name': name, 'is_active': True}
            )
        created = 0
        for row in data.EXPERIENCES:
            service = BookableService.objects.filter(slug=row['slug']).first()
            if service is None:
                service = BookableService.objects.create(
                    slug=row['slug'],
                    name=row['name'],
                    vendor=host,
                    category=categories[row['category']],
                    region=row['region'],
                    location=row['location'],
                    short_description=row['short_description'],
                    description=row['description'],
                    duration_minutes=row['duration_minutes'],
                    duration_label=row['duration_label'],
                    price=Money(row['price'], 'EUR'),
                    highlights=row['highlights'],
                    included=row['included'],
                    not_included=row['not_included'],
                    itinerary=row['itinerary'],
                    faqs=row['faqs'],
                    meeting_point=row['meeting_point'],
                    latitude=row['latitude'],
                    longitude=row['longitude'],
                    languages=row['languages'],
                    what_to_bring=row['what_to_bring'],
                    daily_capacity=row['daily_capacity'],
                    max_guests_per_booking=row['max_guests_per_booking'],
                    listing_kind='experience',
                    is_active=True,
                )
                created += 1
            if not service.image:
                cover = row.get('image') or EXPERIENCE_COVER[row['category']]
                _attach(service.image, f'{service.slug}.jpg', cover)
            # Every listing extends a catalog Product (v0.109): the dashboard, Linda's
            # product tools and search see it there.
            ensure_product(service)
        return created, len(data.EXPERIENCES)

    def _seed_hotels(self, data) -> tuple[int, int]:
        from plugins.installed.booking_marketplace.models import Property

        host = self._host()
        created = 0
        for h in data.HOTELS:
            values = {
                'name': h['name'],
                'property_type': h['property_type'],
                'star_rating': h['star_rating'],
                'region': h['region'],
                'location': h['location'],
                'short_description': h['short_description'],
                'description': h['description'],
            }
            # No rooms, rates, rating or amenities (owner, 2026-11-08): the page asks.
            prop, was_created = Property.objects.get_or_create(
                slug=h['slug'], defaults={**values, 'vendor': host, 'is_active': True}
            )
            if not was_created:
                _fill(prop, values)
            created += was_created
        return created, len(data.HOTELS)

    def _seed_events(self, data) -> tuple[int, int]:
        from plugins.installed.booking_marketplace.models import Event, Place

        places = {p.slug: p for p in Place.objects.all()}
        created = 0
        for i, e in enumerate(data.EVENTS):
            values = {
                'name': e['name'],
                'category': e['category'],
                'region': e['region'],
                'place': places.get(e['place_slug']),
                'venue': e['venue'],
                'when_label': e['when_label'],
                'month': e['month'],
                'summary': e['summary'],
                'description': e['description'],
                'highlights': e['highlights'],
                'faqs': e['faqs'],
                'official_url': e.get('official_url', ''),
            }
            event, was_created = Event.objects.get_or_create(
                slug=e['slug'],
                defaults={
                    **values,
                    'is_featured': e.get('featured', False),
                    'sort_order': i,
                    'is_active': True,
                },
            )
            if not was_created:
                _fill(event, values)
            created += was_created
        return created, len(data.EVENTS)
