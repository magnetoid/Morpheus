"""Storefront home page."""

from __future__ import annotations

from api.client import internal_graphql
from morpheus.app.views import render
from morpheus.core import MorpheusEvents, hook_registry
from plugins.registry import app_registry


def _serialize_product(p) -> dict:
    """ORM Product → the GraphQL-shaped dict the home template renders.

    Used when a merchandising takeover (STOREFRONT_PRODUCTS) returns ORM
    instances for the hero/featured surfaces, which are otherwise fed by
    GraphQL dicts.
    """
    # Same PRODUCT_CALCULATE_PRICE seam the PDP and cart use — the home
    # merchandising cards would otherwise quote the raw list price while the
    # PDP quoted the rule-adjusted one.
    from core.pricing import apply_price_filter

    price = apply_price_filter(getattr(p, 'price', None), product=p)
    compare = getattr(p, 'compare_at_price', None)
    on_sale = bool(
        price and compare and getattr(compare, 'amount', None) and compare.amount > price.amount
    )
    discount = int(round((1 - price.amount / compare.amount) * 100)) if on_sale else 0
    img = p.images.first() if hasattr(p, 'images') else None
    category = getattr(p, 'category', None)
    return {
        'id': str(p.pk),
        'name': p.name,
        'slug': p.slug,
        'productType': getattr(p, 'product_type', ''),
        'shortDescription': getattr(p, 'short_description', '') or '',
        'category': {'name': category.name, 'slug': category.slug} if category else None,
        'price': {
            'amount': float(price.amount) if price else 0.0,
            'currency': price.currency.code if price else 'USD',
        },
        'priceStartsFrom': False,
        'primaryImage': (
            {'url': img.image.url, 'altText': getattr(img, 'alt_text', '') or p.name}
            if img and getattr(img, 'image', None)
            else None
        ),
        'isOnSale': on_sale,
        'discountPercentage': discount,
    }


def _has_real_cover(product) -> bool:
    """True when the book's cover is artwork, not a drawn stand-in.

    `backfill_book_covers` gave all 752 cover-less classics a Pillow-rendered
    "classic imprint" cover — title and author set on a cloth colour — saved as
    ``cover-<slug>.jpg``. They rescue a product card, but blown up to the full
    height of the homepage window they read as a missing cover, which is exactly
    what the shop's front page must not lead with.

    The filename IS the marker (that command names every file it writes). Its
    rarer branch fetches a real cover from gutenberg.org under the same name, so
    a handful of genuine covers are skipped here too — immaterial against 125
    books with artwork, and the alternative is opening every candidate image to
    measure it on a page render.
    """
    img = (product or {}).get('primaryImage') or {}
    url = img.get('url') or ''
    return bool(url) and '/cover-' not in url


def _hero_with_covers(picks: list, pool: list, limit: int = 4) -> list:
    """Hero picks that have real artwork, topped up from the featured pool.

    Never returns empty: a shop whose featured books all carry drawn covers
    still gets its window, because a hero with nothing in it is worse than one
    with a stand-in.
    """
    kept = [p for p in picks if _has_real_cover(p)]
    if len(kept) < limit:
        seen = {p.get('id') for p in kept}
        for candidate in pool:
            if len(kept) >= limit:
                break
            if candidate.get('id') in seen or not _has_real_cover(candidate):
                continue
            kept.append(candidate)
            seen.add(candidate.get('id'))
    return kept or picks


def _surface_products(request, surface: str, *, value=None, limit: int = 8):
    """Fire the merchandising-takeover hook for one placeholder (fail-soft)."""
    try:
        from morpheus.core import MorpheusEvents, hook_registry  # noqa: PLC0415

        return hook_registry.filter(
            MorpheusEvents.STOREFRONT_PRODUCTS,
            value=value,
            surface=surface,
            request=request,
            limit=limit,
        )
    except Exception:  # noqa: BLE001 — merchandising must never break home
        return value


def home(request):
    data = (
        internal_graphql(
            """
        query Home {
          featuredProducts: products(first: 8, featured: true) {
            id name slug productType shortDescription
            category { name slug }
            price { amount currency } priceStartsFrom
            primaryImage { url altText }
            isOnSale discountPercentage
          }
          collections(featured: true, first: 6) {
            id name slug image { url }
          }
          categories(topLevel: true, first: 8) {
            id name slug image { url }
          }
        }
    """,
            request=request,
        )
        or {}
    )
    # Templates use snake_case; GraphQL returns camelCase. Normalise.
    data.setdefault('featured_products', data.get('featuredProducts', []) or [])

    # Merchandising takeover: a dynamics surface block bound to
    # 'home_featured' fully controls the grid (free pick). Otherwise the
    # featured selection stands and personalisation reorders it per-visitor.
    taken = _surface_products(request, 'home_featured', value=None, limit=8)
    if taken:
        data['featured_products'] = [_serialize_product(p) for p in taken]
    else:
        # Per-visitor reorder of the featured grid via PRODUCT_LIST_REORDER —
        # personalisation subscribes; disabled/absent, the order passes through.
        data['featured_products'] = hook_registry.filter(
            MorpheusEvents.PRODUCT_LIST_REORDER,
            value=data['featured_products'],
            request=request,
            surface='home_featured',
        )

    # Hero: its own takeover surface (free pick); default = top 4 of featured.
    hero_taken = _surface_products(request, 'home_hero', value=None, limit=4)
    if hero_taken:
        data['hero_products'] = [_serialize_product(p) for p in hero_taken]
    else:
        data['hero_products'] = list(data['featured_products'][:4])
    # The window shows books with real covers — applied after BOTH paths, so a
    # merchandising takeover and personalisation's reorder are filtered too.
    data['hero_products'] = _hero_with_covers(
        data['hero_products'], data.get('featured_products') or []
    )
    data.setdefault('seasonal_products', data.get('featured_products', []))

    # Staff picks rail — same fallback chain as the dedicated /staff-picks/ page.
    try:
        from plugins.installed.catalog.models import Collection, Product

        sp_collection = (
            Collection.objects.filter(slug='staff-picks', is_active=True).first()
            or Collection.objects.filter(slug='editors-pick-april', is_active=True).first()
        )
        sp_products = (
            list(
                Product.objects.filter(status='active', collections=sp_collection).order_by(
                    '-is_featured', '-created_at'
                )[:8]
            )
            if sp_collection
            else []
        )
    except Exception:  # noqa: BLE001
        sp_collection, sp_products = None, []
    # Reorder-only takeover: dynamics may re-rank the curated picks.
    sp_products = _surface_products(request, 'home_staff_picks', value=sp_products, limit=8) or []
    data['staff_picks_collection'] = sp_collection
    data['staff_picks'] = sp_products

    # Journal teaser — real entries instead of copy hardcoded in the template.
    # Same source as /journal/: published CMS journal pages, and nothing else
    # (fail-soft, mirrors content.journal_index); themes hide an empty section.
    entries = []
    try:
        if app_registry.is_active('cms'):
            from plugins.installed.cms.services import list_journal_entries  # noqa: PLC0415

            entries = list_journal_entries(limit=3)
    except Exception:  # noqa: BLE001 — journal must never break home
        entries = []
    data['journal_teasers'] = entries

    return render(request, 'storefront/home.html', data)
