"""Catalog services — shared write helpers used by the MCP tool layer
and the GraphQL mutations.

`publish_digital_product` is the canonical "external agent uploads a
PDF book" entry point. It accepts URLs (HTTPS only), downloads the
assets server-side with hard size + timeout caps, attaches them to a
new Product (product_type='digital'), and returns identifiers for the
caller.

Never trusts the caller's URL: enforces HTTPS, response size, MIME
type. Never overwrites an existing slug — appends a numeric suffix on
collision.
"""
from __future__ import annotations

import io
import logging
import mimetypes
import re
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

import requests
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.text import slugify

logger = logging.getLogger('morpheus.catalog.services')


_MAX_PDF_BYTES = 50 * 1024 * 1024     # 50 MB hard cap for PDF
_MAX_IMAGE_BYTES = 8 * 1024 * 1024    # 8 MB hard cap for cover image
_DOWNLOAD_TIMEOUT = 30                # seconds
_ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}


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
            # Filename fallback derived from URL path.
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


@transaction.atomic
def publish_digital_product(
    *,
    title: str,
    pdf_url: str,
    price_amount: Any,
    price_currency: str = 'USD',
    description: str = '',
    short_description: str = '',
    author: str = '',
    cover_image_url: str = '',
    category_slug: str = '',
    sku: str = '',
    slug: str = '',
    status: str = 'active',
) -> dict[str, str]:
    """Create a digital-product Product from external URLs.

    Returns ``{'id', 'slug', 'name', 'url', 'sku'}``. Raises
    ``PublishError`` for any caller-fixable problem.
    """
    from djmoney.money import Money
    from plugins.installed.catalog.models import Category, Product, ProductImage

    title = (title or '').strip()
    if not title:
        raise PublishError('title is required')
    if status not in {'draft', 'active', 'archived'}:
        raise PublishError('status must be draft|active|archived')

    _validate_https_url(pdf_url, field='pdf_url')
    if cover_image_url:
        _validate_https_url(cover_image_url, field='cover_image_url')

    price = Money(_coerce_price(price_amount), (price_currency or 'USD').upper())

    # Fetch assets BEFORE creating the product so a failed download
    # doesn't leave a half-built row in the DB.
    pdf_bytes, pdf_ct, pdf_name = _download(pdf_url, max_bytes=_MAX_PDF_BYTES, field='pdf_url')
    if pdf_ct and 'pdf' not in pdf_ct:
        # Be forgiving — some CDNs return application/octet-stream — but
        # block obvious HTML / image fallbacks.
        if pdf_ct.startswith(('text/', 'image/')):
            raise PublishError(f'pdf_url returned {pdf_ct!r}, not a PDF')
    if not pdf_name.lower().endswith('.pdf'):
        pdf_name = f'{slugify(title) or "book"}.pdf'

    cover_blob: tuple[bytes, str, str] | None = None
    if cover_image_url:
        body, ct, fname = _download(
            cover_image_url, max_bytes=_MAX_IMAGE_BYTES, field='cover_image_url',
        )
        if ct and ct not in _ALLOWED_IMAGE_TYPES:
            raise PublishError(
                f'cover_image_url returned {ct!r}; allowed: {sorted(_ALLOWED_IMAGE_TYPES)}'
            )
        if '.' not in fname:
            ext = (mimetypes.guess_extension(ct) or '.jpg').lstrip('.')
            fname = f'{slugify(title) or "cover"}.{ext}'
        cover_blob = (body, ct, fname)

    category = None
    if category_slug:
        category = Category.objects.filter(slug=category_slug).first()
        if category is None:
            raise PublishError(f'category_slug {category_slug!r} not found')

    chosen_slug = _unique_slug(slug or title)
    chosen_sku = _unique_sku(sku, fallback_base=chosen_slug)

    # Append author + format hint to description if not already mentioned —
    # keeps the metadata visible to customers without a metafields model.
    body_text = (description or '').strip()
    if author and author.lower() not in body_text.lower():
        body_text = (f'By {author.strip()}\n\n' + body_text).strip()

    product = Product(
        name=title,
        slug=chosen_slug,
        sku=chosen_sku,
        product_type='digital',
        status=status,
        price=price,
        description=body_text,
        short_description=(short_description or '').strip(),
        category=category,
        track_inventory=False,
    )
    product.digital_file.save(pdf_name, ContentFile(pdf_bytes), save=False)
    product.save()

    if cover_blob is not None:
        body, _ct, fname = cover_blob
        img = ProductImage(
            product=product,
            alt_text=f'{title} — book cover',
            is_primary=True,
            sort_order=0,
        )
        img.image.save(fname, ContentFile(body), save=True)

    logger.info(
        'catalog.publish_digital_product slug=%s sku=%s pdf=%dKB cover=%s',
        product.slug, product.sku, len(pdf_bytes) // 1024,
        bool(cover_blob),
    )
    return {
        'id': str(product.id),
        'slug': product.slug,
        'sku': product.sku,
        'name': product.name,
        'url': f'/products/{product.slug}/',
    }
