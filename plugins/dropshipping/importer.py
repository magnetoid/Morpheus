"""Bring a supplier's product into the catalogue as a draft, priced from its cost.

Every supplier app that can browse a supplier's catalogue (cjdropshipping,
aliexpress) imports a product the same way:

* a **draft** product — never live until the merchant has looked at it;
* one variant per supplier SKU (a single-SKU product stays a simple product);
* the supplier's photos downloaded into media (failures skipped, not fatal);
* a sale price from the cost by the app's markup, optionally ending in .99;
* the supplier's description reduced to the catalogue's rich-text allowlist —
  supplier HTML carries scripts, styles and hot-linked images.

It goes through the catalog app's own services (``create_product``,
``create_variant``, ``add_product_image``): their validation, unique slugs and
SKUs, and SSRF-guarded download are the catalogue's, never a second copy. The
caller stores its own link rows from the returned map.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

logger = logging.getLogger('morpheus.dropshipping')

MAX_IMAGES = 8
_BLOCKS = re.compile(
    r'<(script|style|noscript|iframe)\b[^>]*>.*?</\1\s*>', re.IGNORECASE | re.DOTALL
)
_SKU_UNSAFE = re.compile(r'[^A-Za-z0-9._-]')


@dataclass
class SupplierVariant:
    supplier_variant_id: str
    name: str
    sku: str
    cost: Decimal
    image_url: str = ''
    stock: int | None = None


@dataclass
class SupplierProduct:
    supplier: str  # short prefix for SKUs: 'CJ', 'AE'
    supplier_product_id: str
    title: str
    description_html: str = ''
    image_urls: list[str] = field(default_factory=list)
    variants: list[SupplierVariant] = field(default_factory=list)
    source_url: str = ''


@dataclass
class ImportResult:
    product: object
    #: supplier_variant_id → ProductVariant, or None for a simple product
    variants: dict[str, object]
    image_errors: list[str]


def sale_price(cost: Decimal, markup: Decimal, *, charm: bool = True) -> Decimal:
    """``cost × markup`` to the cent; with ``charm``, up to the next ``x.99``."""
    price = (Decimal(cost) * Decimal(markup)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if charm and price >= 2:
        price = Decimal(math.ceil(price)) - Decimal('0.01')
    return price


def clean_description(html_text: str) -> str:
    """Supplier HTML on the catalogue's allowlist: no scripts, styles or images."""
    from core.utils.html import sanitize_richtext  # noqa: PLC0415

    text = _BLOCKS.sub('', html_text or '')
    return (sanitize_richtext(text) or '').strip()


def store_currency() -> str:
    """The currency the store sells in: what its active products are priced in.

    Read from the currency column itself: ``.only('price')`` defers
    ``price_currency``, and djmoney then raises ``KeyError`` on ``.price``.
    An empty store falls back to ``settings.STORE_CURRENCY``.
    """
    from collections import Counter  # noqa: PLC0415

    from django.conf import settings  # noqa: PLC0415

    from plugins.installed.catalog.models import Product  # noqa: PLC0415

    seen = Counter(
        Product.objects.filter(status='active').values_list('price_currency', flat=True)[:200]
    )
    if seen:
        return str(seen.most_common(1)[0][0])
    return str(getattr(settings, 'STORE_CURRENCY', '') or 'USD').upper()


def _sku(prefix: str, raw: str, fallback: str) -> str:
    base = _SKU_UNSAFE.sub('', (raw or '').strip()) or _SKU_UNSAFE.sub('', fallback)
    return f'{prefix}-{base}'.upper()[:90]


def _unique_variant_sku(sku: str) -> str:
    from plugins.installed.catalog.models import ProductVariant  # noqa: PLC0415

    candidate, n = sku, 2
    while ProductVariant.objects.filter(sku=candidate).exists():
        candidate = f'{sku}-{n}'
        n += 1
    return candidate


def import_product(
    spec: SupplierProduct,
    *,
    markup: Decimal,
    currency: str,
    charm: bool = True,
) -> ImportResult:
    """Create the draft product, its variants and photos; return the variant map."""
    from django.db import transaction  # noqa: PLC0415

    from plugins.installed.catalog.models import Product, ProductVariant  # noqa: PLC0415
    from plugins.installed.catalog.services.images import add_product_image  # noqa: PLC0415
    from plugins.installed.catalog.services.products import create_product  # noqa: PLC0415
    from plugins.installed.catalog.services.variants import create_variant  # noqa: PLC0415

    if not spec.variants:
        raise ValueError('The supplier product has no purchasable variant.')
    prices = [sale_price(v.cost, markup, charm=charm) for v in spec.variants]
    variable = len(spec.variants) > 1
    with transaction.atomic():
        created = create_product(
            name=spec.title[:300],
            price_amount=min(prices),
            price_currency=currency,
            product_type='variable' if variable else 'simple',
            status='draft',
            sku=_sku(spec.supplier, spec.supplier_product_id, spec.title),
            description=clean_description(spec.description_html),
        )
        product = Product.objects.get(pk=created['id'])
        variant_map: dict[str, object] = {}
        if variable:
            for variant, price in zip(spec.variants, prices, strict=True):
                sku = _unique_variant_sku(
                    _sku(spec.supplier, variant.sku, variant.supplier_variant_id)
                )
                made = create_variant(
                    product_slug=product.slug,
                    name=(variant.name or variant.sku)[:200],
                    sku=sku,
                    price_amount=price,
                    price_currency=currency,
                    requires_shipping=True,
                )
                variant_map[variant.supplier_variant_id] = ProductVariant.objects.get(pk=made['id'])
        else:
            variant_map[spec.variants[0].supplier_variant_id] = None

    image_errors: list[str] = []
    urls = list(dict.fromkeys(u for u in spec.image_urls if u))[:MAX_IMAGES]
    for index, url in enumerate(urls):
        try:
            add_product_image(
                slug=product.slug,
                image_url=url,
                alt_text=spec.title[:255],
                is_primary=index == 0,
                sort_order=index,
            )
        except Exception as e:  # noqa: BLE001 — a missing photo never undoes the import
            image_errors.append(f'{url}: {e}')
            logger.info('dropshipping: image %s skipped for %s: %s', url, product.slug, e)
    return ImportResult(product=product, variants=variant_map, image_errors=image_errors)
