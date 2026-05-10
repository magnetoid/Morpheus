"""Idempotent loader for the demo bookstore dataset."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from djmoney.money import Money

from plugins.installed.demo_data import seeds

logger = logging.getLogger('morpheus.demo_data')


@dataclass
class SeedSummary:
    counts: dict[str, int] = field(default_factory=dict)

    def inc(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n


def seed_all(*, currency: str = 'USD', wipe: bool = False) -> SeedSummary:
    """Seed the demo dataset. Re-runnable; will not duplicate rows.

    Args:
        currency: ISO currency code for prices.
        wipe: if True, deletes existing demo rows first (DESTRUCTIVE).
    """
    summary = SeedSummary()

    if wipe:
        _wipe_demo(summary)

    with transaction.atomic():
        cat_by_slug = _seed_categories(summary)
        col_by_slug = _seed_collections(summary)
        ven_by_slug = _seed_vendors(summary)
        _seed_books(summary, cat_by_slug, ven_by_slug, col_by_slug, currency)
        _seed_customers(summary)
        _seed_orders(summary, currency)

    return summary


def _seed_categories(summary: SeedSummary) -> dict[str, Any]:
    from plugins.installed.catalog.models import Category

    by_slug: dict[str, Any] = {}
    for entry in seeds.CATEGORIES:
        cat, created = Category.objects.update_or_create(
            slug=entry['slug'],
            defaults={'name': entry['name'], 'is_active': True},
        )
        by_slug[entry['slug']] = cat
        if created:
            summary.inc('categories')
    return by_slug


def _seed_collections(summary: SeedSummary) -> dict[str, Any]:
    from plugins.installed.catalog.models import Collection

    by_slug: dict[str, Any] = {}
    for entry in seeds.COLLECTIONS:
        col, created = Collection.objects.update_or_create(
            slug=entry['slug'],
            defaults={
                'name': entry['name'],
                'description': entry['description'],
                'is_active': True,
                'is_featured': entry.get('is_featured', False),
            },
        )
        by_slug[entry['slug']] = col
        if created:
            summary.inc('collections')
    return by_slug


def _seed_vendors(summary: SeedSummary) -> dict[str, Any]:
    from plugins.installed.catalog.models import Vendor

    by_slug: dict[str, Any] = {}
    for entry in seeds.VENDORS:
        v, created = Vendor.objects.update_or_create(
            slug=entry['slug'],
            defaults={
                'name': entry['name'],
                'commission_rate': Decimal(entry['commission_rate']),
                'is_active': True,
            },
        )
        by_slug[entry['slug']] = v
        if created:
            summary.inc('vendors')
    return by_slug


def _seed_books(
    summary: SeedSummary,
    cat_by_slug: dict[str, Any],
    ven_by_slug: dict[str, Any],
    col_by_slug: dict[str, Any],
    currency: str,
) -> None:
    from plugins.installed.catalog.models import Product

    featured_collection = col_by_slug.get('reading-the-spring')
    pick_collection = col_by_slug.get('editors-pick-april')

    for row in seeds.BOOKS:
        (name, slug, sku, cat_slug, ven_slug, price, short_desc, desc, featured) = row
        defaults = {
            'name': name,
            'sku': sku,
            'short_description': short_desc,
            'description': desc,
            'price': Money(Decimal(price), currency),
            'status': 'active',
            'is_featured': featured,
            'category': cat_by_slug.get(cat_slug),
            'vendor': ven_by_slug.get(ven_slug),
        }
        product, created = Product.objects.update_or_create(slug=slug, defaults=defaults)
        if created:
            summary.inc('books')
        # Attach to a collection or two
        if featured and pick_collection is not None:
            product.collections.add(pick_collection)
        if featured_collection is not None:
            product.collections.add(featured_collection)
        _seed_book_metafields(product, slug)
        _seed_book_cover(product, slug)


def _seed_book_metafields(product, slug: str) -> None:
    """Write book.* metafields for the seeded book — fails closed so the
    metafields plugin being absent never breaks the catalog seed."""
    meta = seeds.BOOK_METADATA.get(slug)
    if not meta:
        return
    try:
        from plugins.installed.metafields.models import Metafield
    except Exception:  # noqa: BLE001
        return
    for key, value in meta.items():
        Metafield.objects.set(product, namespace='book', key=key, value=value)


def _seed_book_cover(product, slug: str) -> None:
    """Download the Project Gutenberg cover and attach as a ProductImage.

    Idempotent: skips download when the product already has any image.
    Fails closed — a network blip can't break catalog seeding.
    """
    if product.images.exists():
        return
    meta = seeds.BOOK_METADATA.get(slug) or {}
    gid = meta.get('gutenberg_id')
    if not gid:
        return
    url = f'https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.cover.medium.jpg'
    try:
        import urllib.request
        from django.core.files.base import ContentFile
        from plugins.installed.catalog.models import ProductImage
        req = urllib.request.Request(url, headers={'User-Agent': 'Morpheus-DemoSeed/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        if not data or len(data) < 1024:  # small/empty = Gutenberg returned a miss
            return
        img = ProductImage(product=product, alt_text=product.name, is_primary=True, sort_order=0)
        img.image.save(f'gutenberg-{gid}.jpg', ContentFile(data), save=True)
    except Exception as e:  # noqa: BLE001 — never block seed on a failed cover
        logger.debug('demo_data: cover fetch failed for %s (gid=%s): %s', slug, gid, e)


def _seed_customers(summary: SeedSummary) -> None:
    User = get_user_model()
    demo_customers = [
        {'email': 'reader.one@example.com',  'first_name': 'Mara',  'last_name': 'Holst'},
        {'email': 'reader.two@example.com',  'first_name': 'Idris', 'last_name': 'Khan'},
        {'email': 'reader.three@example.com', 'first_name': 'Lucia', 'last_name': 'Berg'},
    ]
    for c in demo_customers:
        user, created = User.objects.get_or_create(
            email=c['email'],
            defaults={'first_name': c['first_name'], 'last_name': c['last_name']},
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=['password'])
            summary.inc('customers')


def _seed_orders(summary: SeedSummary, currency: str) -> None:
    """Create a couple of completed orders for nicer dashboard numbers."""
    from django.contrib.auth import get_user_model
    from plugins.installed.catalog.models import Product
    from plugins.installed.orders.models import Order, OrderItem

    User = get_user_model()
    customer = User.objects.filter(email='reader.one@example.com').first()
    if customer is None:
        return
    book_a = Product.objects.filter(slug='on-quiet-hours').first()
    book_b = Product.objects.filter(slug='unfinished-light').first()
    if not book_a or not book_b:
        return

    if Order.objects.filter(email=customer.email).exists():
        return  # already seeded

    subtotal = Money(Decimal('32.00'), currency)
    order = Order.objects.create(
        customer=customer,
        email=customer.email,
        subtotal=subtotal,
        total=subtotal,
        payment_status='paid',
        source='demo',
    )
    OrderItem.objects.create(
        order=order, product=book_a, product_name=book_a.name,
        quantity=1, unit_price=book_a.price, total_price=book_a.price,
    )
    OrderItem.objects.create(
        order=order, product=book_b, product_name=book_b.name,
        quantity=1, unit_price=book_b.price, total_price=book_b.price,
    )
    summary.inc('orders')


# ── Wipe (DESTRUCTIVE — hidden behind --fresh) ─────────────────────────────────


def _wipe_demo(summary: SeedSummary) -> None:
    """Remove rows seeded by this loader. Identifies them by slug/email."""
    from plugins.installed.catalog.models import Category, Collection, Product, Vendor
    from plugins.installed.orders.models import Order

    book_slugs = [b[1] for b in seeds.BOOKS]
    legacy_slugs = list(getattr(seeds, 'LEGACY_BOOK_SLUGS', []) or [])
    Product.objects.filter(slug__in=book_slugs + legacy_slugs).delete()
    Collection.objects.filter(slug__in=[c['slug'] for c in seeds.COLLECTIONS]).delete()
    Category.objects.filter(slug__in=[c['slug'] for c in seeds.CATEGORIES]).delete()
    Vendor.objects.filter(slug__in=[v['slug'] for v in seeds.VENDORS]).delete()
    Order.objects.filter(source='demo').delete()
    summary.inc('wiped', 1)


# ─────────────────────────────────────────────────────────────────────────────
# Random-product generator (theme-aware)
# ─────────────────────────────────────────────────────────────────────────────

import random
import secrets


_TOPIC_PRODUCTS = {
    'bookstore': {
        'category': 'Random reads',
        'price_range': (Decimal('12'), Decimal('38')),
        'titles': [
            'The Quiet Hour', 'Letters from a Distant Garden', 'Anatomy of Patience',
            'On Solitude and Other Habits', 'The Architecture of Memory',
            'Small Animals at Dawn', 'A Catalogue of Lost Names', 'Four Seasons in Lisbon',
            'How to Read a Window', 'The Long Sentence', 'Notebook of Salt',
            'Rooms in the Margin', 'A Theory of Walking', 'Almost Nothing Happens',
            'Field Guide to the Familiar', 'The Translator\'s Confession',
            'Late Apricots', 'Inventory of Departures', 'A Brief History of Hesitation',
            'The Last Bookshop in Town', 'Coastal Disturbances', 'Houses That Outlive Us',
            'On the Use of Quiet', 'The Slowest Marathon', 'A Year of Empty Mornings',
            'Letters Never Sent', 'Notes from the Greenhouse', 'The Cartographer\'s Daughter',
            'Wintering in Prose', 'A Practical Guide to Stillness',
        ],
    },
    'apparel': {
        'category': 'Capsule pieces',
        'price_range': (Decimal('45'), Decimal('220')),
        'titles': [
            'Heritage Linen Shirt', 'Field Trouser', 'Boxy Cardigan',
            'Slate Wool Blazer', 'Selvedge Denim', 'Sailcloth Tote',
            'Workwear Coat', 'Collarless Shirt', 'Drawcord Trouser',
            'Heavyweight Tee', 'Felted Cap', 'Dyed Cotton Scarf',
            'Slow Knit Pullover', 'Yarn-dyed Twill Pant', 'Reverse Sweat',
            'Crewneck in Charcoal', 'Pleated Wide Trouser', 'Half-zip Pullover',
            'Engineer Cap', 'Box Pocket Shirt', 'Three-button Knit',
            'French-seam Tee', 'Lightweight Coat', 'Oversized Knit',
            'Hopsack Trouser', 'Garment-dyed Hoodie', 'Cropped Anorak',
            'Selvedge Shorts', 'Field Vest', 'Boxy Overshirt',
        ],
    },
    'general': {
        'category': 'Sample products',
        'price_range': (Decimal('15'), Decimal('120')),
        'titles': [f'Sample product #{i:02d}' for i in range(1, 41)],
    },
}


def _detect_topic() -> str:
    """Best-effort: read the active theme's `demo_topic` attribute.
    Falls back to 'bookstore' for dot_books, else 'general'."""
    try:
        from django.conf import settings as dj_settings
        from themes.registry import theme_registry

        active_name = getattr(dj_settings, 'MORPHEUS_ACTIVE_THEME', '')
        theme = theme_registry.get(active_name) if active_name else None
        if theme is not None:
            topic = getattr(theme, 'demo_topic', None)
            if topic:
                return topic
            if 'book' in (active_name or '').lower():
                return 'bookstore'
    except Exception:  # noqa: BLE001
        pass
    return 'general'


def seed_random_products(*, count: int = 30, topic: str = '',
                         currency: str = 'USD',
                         wipe_random: bool = False) -> SeedSummary:
    """Generate N random products themed for the active storefront.

    Idempotent across runs at the title level — adding more re-runs only
    adds *new* titles. Set `wipe_random=True` to remove products with the
    `is_random_demo=True` metadata flag first.

    Args:
        count: how many products to ensure.
        topic: 'bookstore' | 'apparel' | 'general'. Auto-detected if empty.
        currency: ISO currency.
        wipe_random: if True, delete previously-generated random demo first.
    """
    from django.utils.text import slugify
    from plugins.installed.catalog.models import Category, Product

    summary = SeedSummary()
    chosen_topic = topic or _detect_topic()
    spec = _TOPIC_PRODUCTS.get(chosen_topic, _TOPIC_PRODUCTS['general'])
    titles = list(spec['titles'])
    random.shuffle(titles)
    count = max(1, min(int(count or 30), len(titles)))

    if wipe_random:
        deleted, _ = Product.objects.filter(metadata__is_random_demo=True).delete()
        summary.inc('random_demo_wiped', deleted)

    cat, _ = Category.objects.get_or_create(
        slug=slugify(spec['category']),
        defaults={'name': spec['category'], 'is_active': True},
    )
    summary.inc('categories', 1 if _ else 0)

    low, high = spec['price_range']
    for title in titles[:count]:
        slug = slugify(title) + '-' + secrets.token_hex(2)
        # make pricing predictable but varied
        price = (low + (high - low) * Decimal(random.random())).quantize(Decimal('0.01'))
        product, created = Product.objects.get_or_create(
            slug=slug,
            defaults={
                'name': title,
                'sku': f'RD-{secrets.token_hex(4).upper()}',
                'category': cat,
                'short_description': f'Generated demo product · {chosen_topic}',
                'price': Money(price, currency),
                'status': 'active',
                'metadata': {'is_random_demo': True, 'topic': chosen_topic},
            },
        )
        if created:
            summary.inc('products', 1)
    summary.counts.setdefault('topic', chosen_topic)
    summary.counts.setdefault('count_requested', count)
    return summary
