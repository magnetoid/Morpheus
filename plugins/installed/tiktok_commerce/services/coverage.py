"""Catalog feed coverage / eligibility report."""

from __future__ import annotations

from .mapping import map_product
from .settings import tiktok_settings


def coverage_report(*, limit: int | None = None) -> dict:
    from plugins.installed.catalog.models import Product  # noqa: PLC0415

    settings = tiktok_settings()
    qs = Product.objects.filter(status='active').select_related('category').order_by('-created_at')
    if limit:
        qs = qs[:limit]

    total = eligible = 0
    missing = {'image': 0, 'price': 0, 'gtin_or_mpn': 0, 'brand': 0}
    examples: dict[str, list] = {k: [] for k in missing}

    for product in qs.iterator():
        total += 1
        try:
            item = map_product(product, settings)
        except Exception:  # noqa: BLE001
            item = None
        if item is None:
            img = getattr(product, 'primary_image', None)
            reason = 'image' if not (img and getattr(img, 'image', None)) else 'price'
            missing[reason] += 1
            _ex(examples, reason, product)
            continue
        eligible += 1
        if not (item.get('gtin') or item.get('mpn')):
            missing['gtin_or_mpn'] += 1
            _ex(examples, 'gtin_or_mpn', product)
        if not item.get('brand'):
            missing['brand'] += 1
            _ex(examples, 'brand', product)

    pct = round(100 * eligible / total, 1) if total else 0.0
    labels = {
        'image': 'image_link',
        'price': 'price',
        'gtin_or_mpn': 'gtin / mpn',
        'brand': 'brand',
    }
    gaps = [
        {'attribute': labels[k], 'count': missing[k], 'examples': examples[k]}
        for k in missing
        if missing[k]
    ]
    return {'total': total, 'eligible': eligible, 'eligible_pct': pct, 'gaps': gaps}


def _ex(examples: dict, key: str, product) -> None:
    if len(examples[key]) < 5:
        examples[key].append({'slug': getattr(product, 'slug', ''), 'name': product.name})
