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

Places and experiences get a free photo from Wikimedia Commons (`photo` in the data),
downloaded here, with its author and licence stored beside it for the page to show. It
replaces only an empty cover or one of the bundled stand-in covers, never a photo someone
uploaded; a download that fails leaves the stand-in, and the next run tries again. The
downloads go out 2 s apart and wait out a 429: Commons refuses a burst at once, and the
whole catalogue takes about ten minutes. A replaced cover's file is deleted only once its
part has committed, so a part that fails keeps every page's photo.

    python manage.py seed_croatia [--only places|experiences|hotels|events]

It refuses to run unless the active theme's country is Croatia: on any other store it
would publish Croatian destinations.
"""

from __future__ import annotations

import hashlib
import logging
import time
from functools import cache
from pathlib import Path

from django.core.files import File
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify
from djmoney.money import Money

SEED_DIR = Path(__file__).resolve().parents[2] / 'seed_assets'

HOST_NAME = 'Croatia Experience'
CATEGORIES = ('Adventure', 'Water Sports', 'Culture', 'Dining', 'Wine', 'Wellness')

# Stand-in covers, chosen by type, for a row whose Commons photo could not be fetched.
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

PHOTO_HOST = 'https://upload.wikimedia.org/'
PHOTO_MAX_BYTES = 8 * 1024 * 1024
# Wikimedia refuses requests that do not say who is asking.
PHOTO_USER_AGENT = 'Morpheus seed_croatia/1.0 (store catalogue photos from Wikimedia Commons)'
# A public-domain photo has no licence page, so `licence_url` may be absent.
CREDIT_KEYS = ('author', 'licence', 'licence_url', 'source_url')
# Commons answered a burst from the store's server with 429 at once (2026-11-09); 2 s
# apart, waiting 20, 40 and 80 s after a refusal, fetched all 229 photos.
PHOTO_GAP_S = 2.0
PHOTO_RETRY_WAITS = (20, 40, 80)
PHOTO_MAX_WAIT_S = 120
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_last_request = {'at': 0.0}  # monotonic time of the last download

logger = logging.getLogger('morpheus.booking_marketplace')


def _attach(field, name: str, filename: str) -> None:
    src = SEED_DIR / filename
    if src.exists():
        with src.open('rb') as fh:
            field.save(name, File(fh), save=True)


@cache
def _stand_ins() -> frozenset[str]:
    """Digests of the bundled covers, which a real photo may replace."""
    return frozenset(hashlib.sha256(f.read_bytes()).hexdigest() for f in SEED_DIR.glob('*.jpg'))


def _is_stand_in(fieldfile) -> bool:
    """Empty, or one of the bundled covers: never a photo someone uploaded."""
    if not fieldfile:
        return True
    try:
        with fieldfile.storage.open(fieldfile.name, 'rb') as fh:
            return hashlib.sha256(fh.read()).hexdigest() in _stand_ins()
    except OSError:  # a file missing from storage is somebody's to fix, not ours
        return False


def _pace() -> None:
    """Keep downloads PHOTO_GAP_S apart."""
    wait = _last_request['at'] + PHOTO_GAP_S - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_request['at'] = time.monotonic()


def _retry_wait(response, wait: int) -> float:
    """The longer of our own wait and the server's Retry-After (in seconds), capped."""
    try:
        asked = float(response.headers.get('Retry-After', 0))
    except (TypeError, ValueError):  # an HTTP date: our own wait is long enough
        asked = 0
    return min(max(asked, wait), PHOTO_MAX_WAIT_S)


def _download(url: str) -> bytes | None:
    from core.net import outbound_request
    from core.utils.site import site_base_url

    if not url.startswith(PHOTO_HOST):
        return None
    # Wikimedia asks a client to say who it is and how to reach them.
    headers = {'User-Agent': f'{PHOTO_USER_AGENT} {site_base_url()}'}
    for wait in (*PHOTO_RETRY_WAITS, None):
        _pace()
        try:
            response = outbound_request('get', url, timeout=30, headers=headers)
        except Exception:  # noqa: BLE001 — the stand-in stays and the next run tries again
            logger.warning('seed_croatia: could not download %s', url, exc_info=True)
            return None
        if response.status_code not in _RETRY_STATUSES or wait is None:
            break
        time.sleep(_retry_wait(response, wait))
    kind = response.headers.get('Content-Type', '')
    if response.status_code != 200 or not kind.startswith('image/'):
        logger.warning('seed_croatia: %s answered %s %s', url, response.status_code, kind)
        return None
    if len(response.content) > PHOTO_MAX_BYTES:
        return None
    return response.content


def _delete_after_commit(fieldfile) -> None:
    """Delete the file once the part commits. Deleted at once, a part that then failed
    rolled back to rows naming files that were gone (13 Istria places, live 2026-11-09),
    and a rerun skipped them, since a missing file is not a stand-in."""
    storage, name = fieldfile.storage, fieldfile.name
    transaction.on_commit(lambda: storage.delete(name))


def _set_photo(obj, photo: dict | None, stand_in: str) -> bool:
    """Give the row its Commons photo and credit; True when the photo changed."""
    if not _is_stand_in(obj.image):
        return False
    content = _download(photo['src']) if photo else None
    if content is None:
        if not obj.image:
            _attach(obj.image, f'{obj.slug}.jpg', stand_in)
        return False
    if obj.image:
        _delete_after_commit(obj.image)
    # Named after its bytes: a file name is an address that browsers, the CDN and seo's
    # /img/ copies remember, so the photo must never take the stand-in's old name.
    digest = hashlib.sha256(content).hexdigest()[:10]
    obj.image.save(f'{obj.slug}-{digest}.jpg', ContentFile(content), save=False)
    credit = {key: photo.get(key, '') for key in CREDIT_KEYS}
    obj.image_credit = credit | {'for': obj.image.name}
    obj.save(update_fields=['image', 'image_credit'])
    return True


def _refresh_product_photo(service) -> None:
    """Swap the product's copy of a stand-in cover for the listing's new photo."""
    from django.db.models import FileField

    from plugins.installed.booking_marketplace.products import _copy_images

    product = service.product
    stale = [img for img in product.images.all() if _is_stand_in(img.image)]
    for img in stale:
        # A ProductImage deletes its files with its row: hand them to the commit instead.
        for field in img._meta.concrete_fields:
            fieldfile = getattr(img, field.attname) if isinstance(field, FileField) else None
            if fieldfile:
                _delete_after_commit(fieldfile)
                fieldfile.name = ''
        img.delete()
    if stale:
        _copy_images(service, product)


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
            _set_photo(place, p.get('photo'), PLACE_COVER[p['place_type']])
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
            stand_in = row.get('image') or EXPERIENCE_COVER[row['category']]
            if _set_photo(service, row.get('photo'), stand_in) and service.product_id:
                _refresh_product_photo(service)
            # Every listing extends a catalog Product (v0.109): the dashboard, Linda's
            # product tools and search see it there, with its own copy of the photo.
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
