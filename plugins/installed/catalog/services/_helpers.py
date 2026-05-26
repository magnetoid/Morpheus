"""Private helpers shared by every services/ module.

Constants, the public ``PublishError`` exception, URL + file download
primitives, slug + SKU uniquifiers, the price coercer, the
``_serialize_*`` formatters, and the variant-field applier all live
here so the public-API modules (products, categories, images,
variants) stay slim.

Leading underscore on the filename marks the module as private — the
storefront/views/ split uses the same convention. External callers
import from the package root (``catalog.services``), never from
``catalog.services._helpers``.
"""
from __future__ import annotations

import io
import logging
import re
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

import requests
from django.utils.text import slugify

logger = logging.getLogger('morpheus.catalog.services')


# ── Download / validation limits ──────────────────────────────────────
_MAX_PDF_BYTES = 50 * 1024 * 1024     # 50 MB hard cap for PDF
_MAX_IMAGE_BYTES = 8 * 1024 * 1024    # 8 MB hard cap for cover image
_DOWNLOAD_TIMEOUT = 30                # seconds
_ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}


# ── Field allow-lists ─────────────────────────────────────────────────
_PRODUCT_SCALAR_FIELDS = {
    # str-like
    'name', 'sku', 'short_description', 'description',
    'meta_title', 'meta_description', 'focus_keyword', 'canonical_url',
    'og_title', 'og_description', 'twitter_title', 'twitter_description',
    'twitter_card', 'weight_unit',
    # bool
    'is_featured', 'is_taxable', 'track_inventory', 'requires_shipping',
    'noindex', 'nofollow',
    # numeric (handled in coercion)
    'weight',
}

_VALID_PRODUCT_TYPES = {'simple', 'variable', 'digital', 'bundle'}
_VALID_STATUSES = {'draft', 'active', 'archived'}
_VALID_VARIANT_TYPES = {'physical', 'digital', 'virtual'}
_VALID_INVENTORY_POLICIES = {'deny', 'continue'}


class PublishError(Exception):
    """Raised when a digital-product publish call can't proceed.
    Message is safe to surface to the caller (no internal paths)."""


def _validate_https_url(url: str, *, field: str) -> None:
    parsed = urlparse(url or '')
    if parsed.scheme != 'https':
        raise PublishError(f'{field} must be an https:// URL')
    if not parsed.netloc:
        raise PublishError(f'{field} is not a valid URL')


def _download(url: str, *, max_bytes: int, field: str) -> tuple[bytes, str, str]:
    """Stream `url` → (body, content_type, filename). Hard size + timeout caps."""
    try:
        with requests.get(url, stream=True, timeout=_DOWNLOAD_TIMEOUT) as r:
            r.raise_for_status()
            content_type = (r.headers.get('Content-Type') or '').split(';')[0].strip().lower()
            cl = r.headers.get('Content-Length')
            if cl and int(cl) > max_bytes:
                raise PublishError(f'{field} exceeds {max_bytes // (1024 * 1024)} MB limit')
            buf = io.BytesIO()
            for chunk in r.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                buf.write(chunk)
                if buf.tell() > max_bytes:
                    raise PublishError(f'{field} exceeds {max_bytes // (1024 * 1024)} MB limit')
            url_name = PurePosixPath(urlparse(url).path).name or field
            return buf.getvalue(), content_type, url_name
    except requests.RequestException as e:
        raise PublishError(f'{field} download failed: {e}') from None


def _unique_slug(base: str) -> str:
    """Return a slug that doesn't collide with an existing product."""
    from plugins.installed.catalog.models import Product

    base = slugify(base) or 'book'
    candidate = base
    n = 2
    while Product.objects.filter(slug=candidate).exists():
        candidate = f'{base}-{n}'
        n += 1
        if n > 200:
            raise PublishError('could not allocate a unique slug')
    return candidate


def _unique_sku(suggested: str, *, fallback_base: str) -> str:
    from plugins.installed.catalog.models import Product

    base = re.sub(r'[^A-Za-z0-9._-]', '', (suggested or '')).upper().strip('-_.')
    if not base:
        base = ('BOOK-' + re.sub(r'[^A-Z0-9]', '', slugify(fallback_base).upper()))[:32]
    candidate = base
    n = 2
    while Product.objects.filter(sku=candidate).exists():
        candidate = f'{base}-{n}'
        n += 1
        if n > 200:
            raise PublishError('could not allocate a unique SKU')
    return candidate


def _coerce_price(amount: Any) -> Decimal:
    try:
        d = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError):
        raise PublishError('price_amount is not a valid number') from None
    if d < 0:
        raise PublishError('price_amount must be >= 0')
    return d


# ── Serializers ───────────────────────────────────────────────────────


def _serialize_product(p) -> dict:
    return {
        'id': str(p.id),
        'slug': p.slug,
        'sku': p.sku,
        'name': p.name,
        'status': p.status,
        'product_type': p.product_type,
        'price_amount': str(getattr(p.price, 'amount', '')) if p.price else '',
        'price_currency': str(getattr(p.price, 'currency', '')) if p.price else '',
        'url': f'/products/{p.slug}/',
    }


def _serialize_category(c) -> dict:
    return {
        'id': str(c.id),
        'slug': c.slug,
        'name': c.name,
        'parent_slug': c.parent.slug if c.parent_id else '',
    }


def _serialize_image(img) -> dict:
    return {
        'id': str(img.id),
        'product_slug': img.product.slug,
        'url': img.image.url if img.image else '',
        'alt_text': img.alt_text or '',
        'is_primary': bool(img.is_primary),
        'sort_order': int(img.sort_order or 0),
    }


def _serialize_variant(v) -> dict:
    return {
        'id': str(v.id),
        'product_slug': v.product.slug,
        'name': v.name,
        'sku': v.sku,
        'size': getattr(v, 'size', '') or '',
        'short_description': getattr(v, 'short_description', '') or '',
        'description': getattr(v, 'description', '') or '',
        'price_amount': str(getattr(v.price, 'amount', '')) if v.price else '',
        'price_currency': str(getattr(v.price, 'currency', '')) if v.price else '',
        'variant_type': getattr(v, 'variant_type', 'physical'),
        'requires_shipping': bool(getattr(v, 'requires_shipping', True)),
        'is_taxable': bool(getattr(v, 'is_taxable', True)),
        'inventory_policy': getattr(v, 'inventory_policy', 'deny'),
        'barcode': getattr(v, 'barcode', '') or '',
        'is_active': bool(v.is_active),
        'sort_order': int(v.sort_order or 0),
    }


# ── Variant field applier ─────────────────────────────────────────────


def _apply_variant_fields(variant, fields: dict, *, allow_sku_collision_check: bool = True) -> None:
    """Mutate `variant` in place with whatever fields are present. Skips
    unspecified keys so partial updates work. Raises PublishError on
    invalid input."""
    from djmoney.money import Money
    from plugins.installed.catalog.models import ProductVariant

    if 'name' in fields:
        name = (fields['name'] or '').strip()
        if not name:
            raise PublishError('variant name is required')
        variant.name = name
    if 'sku' in fields:
        sku = (fields['sku'] or '').strip()
        if not sku:
            raise PublishError('variant sku is required')
        if allow_sku_collision_check:
            qs = ProductVariant.objects.filter(sku=sku)
            if variant.pk:
                qs = qs.exclude(pk=variant.pk)
            if qs.exists():
                raise PublishError(f'sku {sku!r} already in use by another variant')
        variant.sku = sku
    if 'price_amount' in fields:
        v = fields['price_amount']
        if v in (None, '', 'null'):
            variant.price = None
        else:
            currency = (fields.get('price_currency')
                        or str(getattr(variant.price, 'currency', None) or 'USD')).upper()
            variant.price = Money(_coerce_price(v), currency)
    if 'compare_at_amount' in fields:
        v = fields['compare_at_amount']
        if v in (None, '', 'null'):
            variant.compare_at_price = None
        else:
            currency = (fields.get('price_currency')
                        or str(getattr(variant.price, 'currency', None) or 'USD')).upper()
            variant.compare_at_price = Money(_coerce_price(v), currency)
    if 'variant_type' in fields:
        vt = fields['variant_type']
        if vt not in _VALID_VARIANT_TYPES:
            raise PublishError(f'variant_type must be one of {sorted(_VALID_VARIANT_TYPES)}')
        variant.variant_type = vt
        # Helpful auto: if requires_shipping wasn't explicitly set,
        # default it from variant_type.
        if 'requires_shipping' not in fields:
            variant.requires_shipping = (vt == 'physical')
    if 'requires_shipping' in fields:
        variant.requires_shipping = bool(fields['requires_shipping'])
    if 'is_taxable' in fields:
        variant.is_taxable = bool(fields['is_taxable'])
    if 'inventory_policy' in fields:
        ip = fields['inventory_policy']
        if ip not in _VALID_INVENTORY_POLICIES:
            raise PublishError(f'inventory_policy must be one of {sorted(_VALID_INVENTORY_POLICIES)}')
        variant.inventory_policy = ip
    if 'barcode' in fields:
        variant.barcode = (fields['barcode'] or '').strip()[:50]
    if 'size' in fields:
        variant.size = (fields['size'] or '').strip()[:50]
    if 'short_description' in fields:
        variant.short_description = (fields['short_description'] or '').strip()
    if 'description' in fields:
        variant.description = (fields['description'] or '').strip()
    if 'is_active' in fields:
        variant.is_active = bool(fields['is_active'])
    if 'sort_order' in fields:
        try:
            variant.sort_order = max(0, int(fields['sort_order']))
        except (TypeError, ValueError):
            raise PublishError('sort_order must be an integer') from None
