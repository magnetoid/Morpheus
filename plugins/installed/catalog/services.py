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


# ─── create / update / archive / restore / delete ────────────────────────────


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


@transaction.atomic
def create_product(
    *,
    name: str,
    price_amount: Any,
    price_currency: str = 'USD',
    product_type: str = 'simple',
    status: str = 'draft',
    sku: str = '',
    slug: str = '',
    short_description: str = '',
    description: str = '',
    category_slug: str = '',
    cover_image_url: str = '',
    # Optional scalar fields — passed straight through.
    **extra,
) -> dict[str, str]:
    """Create a new product. Generic create — for digital/PDF-specific
    publishing use :func:`publish_digital_product` instead (handles PDF
    download + digital_file attachment).

    Required: ``name``, ``price_amount``. Everything else has a sensible
    default; ``status`` defaults to 'draft' so a half-built product
    isn't accidentally live.

    Returns the same shape as :func:`update_product`:
    ``{id, slug, sku, name, status, product_type, price_amount,
    price_currency, url}``.
    """
    from djmoney.money import Money
    from plugins.installed.catalog.models import Category, Product, ProductImage

    name = (name or '').strip()
    if not name:
        raise PublishError('name is required')
    if product_type not in _VALID_PRODUCT_TYPES:
        raise PublishError(f'product_type must be one of {sorted(_VALID_PRODUCT_TYPES)}')
    if status not in _VALID_STATUSES:
        raise PublishError(f'status must be one of {sorted(_VALID_STATUSES)}')

    if cover_image_url:
        _validate_https_url(cover_image_url, field='cover_image_url')

    price = Money(_coerce_price(price_amount), (price_currency or 'USD').upper())

    # Reject unknown extra fields up front so typos surface immediately.
    unknown = set(extra.keys()) - _PRODUCT_SCALAR_FIELDS
    if unknown:
        raise PublishError(f'unknown field(s): {sorted(unknown)}')

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
            fname = f'{slugify(name) or "cover"}.{ext}'
        cover_blob = (body, ct, fname)

    category = None
    if category_slug:
        category = Category.objects.filter(slug=category_slug).first()
        if category is None:
            raise PublishError(f'category_slug {category_slug!r} not found')

    chosen_slug = _unique_slug(slug or name)
    chosen_sku = _unique_sku(sku, fallback_base=chosen_slug)

    product = Product(
        name=name,
        slug=chosen_slug,
        sku=chosen_sku,
        product_type=product_type,
        status=status,
        price=price,
        description=(description or '').strip(),
        short_description=(short_description or '').strip(),
        category=category,
    )
    # Apply optional scalars from `extra` (weight, flags, SEO, etc.).
    for k, v in extra.items():
        if k == 'weight':
            if v in (None, '', 'null'):
                v = None
            else:
                try:
                    v = Decimal(str(v))
                except (InvalidOperation, TypeError, ValueError):
                    raise PublishError('weight must be a number') from None
        elif k in {
            'is_featured', 'is_taxable', 'track_inventory',
            'requires_shipping', 'noindex', 'nofollow',
        }:
            v = bool(v) if isinstance(v, bool) else str(v).lower() in {'1', 'true', 'yes', 'on'}
        else:
            v = '' if v is None else str(v)
        setattr(product, k, v)
    product.save()

    if cover_blob is not None:
        body, _ct, fname = cover_blob
        img = ProductImage(
            product=product,
            alt_text=name,
            is_primary=True,
            sort_order=0,
        )
        img.image.save(fname, ContentFile(body), save=True)

    logger.info(
        'catalog.create_product slug=%s sku=%s type=%s status=%s cover=%s',
        product.slug, product.sku, product.product_type, product.status,
        bool(cover_blob),
    )
    return _serialize_product(product)


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


@transaction.atomic
def update_product(*, slug: str, **fields) -> dict[str, str]:
    """Update an existing product by slug. Only fields present in `fields`
    are touched. Unknown fields raise PublishError to catch typos early.

    Recognised field names:
      • Scalar text/bool/numeric:
        name, sku, short_description, description, meta_title,
        meta_description, focus_keyword, canonical_url,
        og_title, og_description, twitter_title, twitter_description,
        twitter_card, weight, weight_unit, is_featured, is_taxable,
        track_inventory, requires_shipping, noindex, nofollow.
      • Status: status ('draft'|'active'|'archived'), product_type
        ('simple'|'variable'|'digital'|'bundle').
      • Pricing: price_amount + optional price_currency,
        compare_at_amount (None to clear), cost_amount (None to clear).
      • Category: category_slug ('' or null clears).
      • SEO JSON: structured_data (dict).

    Returns the serialised product. Raises PublishError on any caller-
    fixable problem (unknown slug, invalid status, malformed price).
    """
    from djmoney.money import Money
    from plugins.installed.catalog.models import Category, Product

    product = Product.objects.filter(slug=slug).first()
    if product is None:
        raise PublishError(f'product slug {slug!r} not found')

    unknown = set(fields.keys()) - _PRODUCT_SCALAR_FIELDS - {
        'status', 'product_type', 'price_amount', 'price_currency',
        'compare_at_amount', 'cost_amount', 'category_slug',
        'structured_data',
    }
    if unknown:
        raise PublishError(f'unknown field(s): {sorted(unknown)}')

    if 'status' in fields:
        status = fields['status']
        if status not in {'draft', 'active', 'archived'}:
            raise PublishError("status must be 'draft'|'active'|'archived'")
        product.status = status

    if 'product_type' in fields:
        pt = fields['product_type']
        if pt not in {'simple', 'variable', 'digital', 'bundle'}:
            raise PublishError("product_type must be 'simple'|'variable'|'digital'|'bundle'")
        product.product_type = pt

    if 'price_amount' in fields:
        amt = _coerce_price(fields['price_amount'])
        currency = (fields.get('price_currency') or str(getattr(product.price, 'currency', 'USD'))).upper()
        product.price = Money(amt, currency)

    if 'compare_at_amount' in fields:
        v = fields['compare_at_amount']
        if v in (None, '', 'null'):
            product.compare_at_price = None
        else:
            product.compare_at_price = Money(
                _coerce_price(v),
                (fields.get('price_currency') or str(getattr(product.price, 'currency', 'USD'))).upper(),
            )

    if 'cost_amount' in fields:
        v = fields['cost_amount']
        if v in (None, '', 'null'):
            product.cost_price = None
        else:
            product.cost_price = Money(
                _coerce_price(v),
                (fields.get('price_currency') or str(getattr(product.price, 'currency', 'USD'))).upper(),
            )

    if 'category_slug' in fields:
        cs = (fields['category_slug'] or '').strip()
        if not cs:
            product.category = None
        else:
            cat = Category.objects.filter(slug=cs).first()
            if cat is None:
                raise PublishError(f'category_slug {cs!r} not found')
            product.category = cat

    if 'structured_data' in fields:
        sd = fields['structured_data']
        if sd is None:
            product.structured_data = {}
        elif isinstance(sd, dict):
            product.structured_data = sd
        else:
            raise PublishError('structured_data must be a JSON object')

    # Scalar copy-over. Booleans coerce to bool; weight to Decimal.
    for k in _PRODUCT_SCALAR_FIELDS:
        if k not in fields:
            continue
        v = fields[k]
        if k == 'weight':
            if v in (None, '', 'null'):
                v = None
            else:
                try:
                    v = Decimal(str(v))
                except (InvalidOperation, TypeError, ValueError):
                    raise PublishError('weight must be a number') from None
        elif k in {
            'is_featured', 'is_taxable', 'track_inventory',
            'requires_shipping', 'noindex', 'nofollow',
        }:
            v = bool(v) if isinstance(v, bool) else str(v).lower() in {'1', 'true', 'yes', 'on'}
        else:
            v = '' if v is None else str(v)
        setattr(product, k, v)

    product.save()
    logger.info('catalog.update_product slug=%s fields=%s', product.slug, sorted(fields.keys()))
    return _serialize_product(product)


@transaction.atomic
def archive_product(*, slug: str) -> dict[str, str]:
    from plugins.installed.catalog.models import Product
    product = Product.objects.filter(slug=slug).first()
    if product is None:
        raise PublishError(f'product slug {slug!r} not found')
    product.status = 'archived'
    product.save(update_fields=['status', 'updated_at'])
    return _serialize_product(product)


@transaction.atomic
def restore_product(*, slug: str, status: str = 'active') -> dict[str, str]:
    if status not in {'draft', 'active'}:
        raise PublishError("status must be 'draft' or 'active'")
    from plugins.installed.catalog.models import Product
    product = Product.objects.filter(slug=slug).first()
    if product is None:
        raise PublishError(f'product slug {slug!r} not found')
    product.status = status
    product.save(update_fields=['status', 'updated_at'])
    return _serialize_product(product)


@transaction.atomic
def delete_product(*, slug: str) -> dict[str, str]:
    """Hard-delete a product. Use archive_product unless you really need
    the row gone — analytics + audit lose history on delete."""
    from plugins.installed.catalog.models import Product
    product = Product.objects.filter(slug=slug).first()
    if product is None:
        raise PublishError(f'product slug {slug!r} not found')
    out = _serialize_product(product)
    product.delete()
    return out


# ─── categories ───────────────────────────────────────────────────────────────


def _serialize_category(c) -> dict:
    return {
        'id': str(c.id),
        'slug': c.slug,
        'name': c.name,
        'parent_slug': c.parent.slug if c.parent_id else '',
    }


@transaction.atomic
def create_category(
    *, name: str, slug: str = '', parent_slug: str = '', description: str = '',
) -> dict[str, str]:
    from plugins.installed.catalog.models import Category

    name = (name or '').strip()
    if not name:
        raise PublishError('name is required')

    parent = None
    if parent_slug:
        parent = Category.objects.filter(slug=parent_slug).first()
        if parent is None:
            raise PublishError(f'parent_slug {parent_slug!r} not found')

    chosen = (slug or '').strip() or slugify(name)
    if Category.objects.filter(slug=chosen).exists():
        raise PublishError(f'slug {chosen!r} already taken')

    cat = Category.objects.create(
        name=name, slug=chosen, parent=parent,
        description=(description or '').strip(),
    )
    logger.info('catalog.create_category slug=%s', cat.slug)
    return _serialize_category(cat)


@transaction.atomic
def update_category(
    *, slug: str, name: str = '', new_slug: str = '',
    parent_slug: str | None = None, description: str | None = None,
) -> dict[str, str]:
    from plugins.installed.catalog.models import Category

    cat = Category.objects.filter(slug=slug).first()
    if cat is None:
        raise PublishError(f'category slug {slug!r} not found')

    if name:
        cat.name = name.strip()
    if new_slug:
        new_slug = new_slug.strip()
        if new_slug != cat.slug and Category.objects.filter(slug=new_slug).exists():
            raise PublishError(f'new_slug {new_slug!r} already taken')
        cat.slug = new_slug
    if parent_slug is not None:
        if not parent_slug:
            cat.parent = None
        else:
            parent = Category.objects.filter(slug=parent_slug).first()
            if parent is None:
                raise PublishError(f'parent_slug {parent_slug!r} not found')
            if parent.pk == cat.pk:
                raise PublishError('a category cannot be its own parent')
            cat.parent = parent
    if description is not None:
        cat.description = description.strip()

    cat.save()
    return _serialize_category(cat)


# ─── Digital file replacement ────────────────────────────────────────────────


@transaction.atomic
def update_digital_pdf(*, slug: str, pdf_url: str) -> dict[str, str]:
    """Replace the digital_file on an existing product by downloading
    a new PDF from `pdf_url`. Use this when an agent has a fresh
    revision of a book and wants to swap the customer download.

    Old file is left on disk for now — orphan cleanup is a separate
    concern (PR N1 in the security review).
    """
    from plugins.installed.catalog.models import Product

    product = Product.objects.filter(slug=slug).first()
    if product is None:
        raise PublishError(f'product slug {slug!r} not found')
    _validate_https_url(pdf_url, field='pdf_url')

    pdf_bytes, pdf_ct, pdf_name = _download(pdf_url, max_bytes=_MAX_PDF_BYTES, field='pdf_url')
    if pdf_ct and 'pdf' not in pdf_ct and pdf_ct.startswith(('text/', 'image/')):
        raise PublishError(f'pdf_url returned {pdf_ct!r}, not a PDF')
    if not pdf_name.lower().endswith('.pdf'):
        pdf_name = f'{slugify(product.name) or "book"}.pdf'

    product.digital_file.save(pdf_name, ContentFile(pdf_bytes), save=True)
    logger.info(
        'catalog.update_digital_pdf slug=%s pdf=%dKB',
        product.slug, len(pdf_bytes) // 1024,
    )
    return {**_serialize_product(product), 'digital_file': product.digital_file.url or ''}


# ─── Product image management ────────────────────────────────────────────────


def _serialize_image(img) -> dict:
    return {
        'id': str(img.id),
        'product_slug': img.product.slug,
        'url': img.image.url if img.image else '',
        'alt_text': img.alt_text or '',
        'is_primary': bool(img.is_primary),
        'sort_order': int(img.sort_order or 0),
    }


@transaction.atomic
def add_product_image(
    *,
    slug: str,
    image_url: str,
    alt_text: str = '',
    is_primary: bool = False,
    sort_order: int = 0,
) -> dict[str, str]:
    """Download an image from `image_url` and attach it to the product.
    If `is_primary` is True, demotes the existing primary image first
    so there's only ever one."""
    from plugins.installed.catalog.models import Product, ProductImage

    product = Product.objects.filter(slug=slug).first()
    if product is None:
        raise PublishError(f'product slug {slug!r} not found')
    _validate_https_url(image_url, field='image_url')

    body, ct, fname = _download(
        image_url, max_bytes=_MAX_IMAGE_BYTES, field='image_url',
    )
    if ct and ct not in _ALLOWED_IMAGE_TYPES:
        raise PublishError(
            f'image_url returned {ct!r}; allowed: {sorted(_ALLOWED_IMAGE_TYPES)}'
        )
    if '.' not in fname:
        ext = (mimetypes.guess_extension(ct) or '.jpg').lstrip('.')
        fname = f'{slugify(product.name) or "image"}.{ext}'

    if is_primary:
        ProductImage.objects.filter(product=product, is_primary=True).update(is_primary=False)

    img = ProductImage(
        product=product,
        alt_text=(alt_text or '').strip() or product.name,
        is_primary=bool(is_primary),
        sort_order=int(sort_order or 0),
    )
    img.image.save(fname, ContentFile(body), save=True)
    logger.info(
        'catalog.add_product_image slug=%s img=%s primary=%s',
        product.slug, img.id, is_primary,
    )
    return _serialize_image(img)


@transaction.atomic
def remove_product_image(*, image_id: str) -> dict[str, str]:
    from plugins.installed.catalog.models import ProductImage

    img = ProductImage.objects.filter(pk=image_id).first()
    if img is None:
        raise PublishError(f'image_id {image_id!r} not found')
    out = _serialize_image(img)
    img.delete()
    return out


@transaction.atomic
def set_primary_image(*, image_id: str) -> dict[str, str]:
    """Promote one image to primary; demote any other primary on the
    same product."""
    from plugins.installed.catalog.models import ProductImage

    img = ProductImage.objects.filter(pk=image_id).first()
    if img is None:
        raise PublishError(f'image_id {image_id!r} not found')
    ProductImage.objects.filter(
        product=img.product, is_primary=True,
    ).exclude(pk=img.pk).update(is_primary=False)
    img.is_primary = True
    img.save(update_fields=['is_primary'])
    return _serialize_image(img)


# ─── Variants (Shopify-parity surface) ────────────────────────────────────────


_VALID_VARIANT_TYPES = {'physical', 'digital', 'virtual'}
_VALID_INVENTORY_POLICIES = {'deny', 'continue'}


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


@transaction.atomic
def create_variant(*, product_slug: str, **fields) -> dict:
    """Create a new ProductVariant on the given product. Required:
    `name` + `sku`. Every other field is optional and follows the
    same semantics as `update_variant`."""
    from plugins.installed.catalog.models import Product, ProductVariant

    product = Product.objects.filter(slug=product_slug).first()
    if product is None:
        raise PublishError(f'product slug {product_slug!r} not found')

    variant = ProductVariant(product=product)
    if 'name' not in fields:
        raise PublishError('name is required')
    if 'sku' not in fields:
        raise PublishError('sku is required')
    _apply_variant_fields(variant, fields)
    variant.save()
    logger.info('catalog.create_variant slug=%s sku=%s type=%s',
                product.slug, variant.sku, variant.variant_type)
    return _serialize_variant(variant)


@transaction.atomic
def update_variant(*, sku: str, **fields) -> dict:
    """Update an existing variant identified by SKU. Pass any subset
    of fields; only the ones present are touched."""
    from plugins.installed.catalog.models import ProductVariant

    variant = ProductVariant.objects.filter(sku=sku).select_related('product').first()
    if variant is None:
        raise PublishError(f'variant sku {sku!r} not found')
    _apply_variant_fields(variant, fields)
    variant.save()
    return _serialize_variant(variant)


@transaction.atomic
def archive_category(*, slug: str) -> dict[str, str]:
    """Soft-delete: detach products + remove the category row.
    Category model has no `status` field so we treat archive as delete."""
    from plugins.installed.catalog.models import Category

    cat = Category.objects.filter(slug=slug).first()
    if cat is None:
        raise PublishError(f'category slug {slug!r} not found')
    out = _serialize_category(cat)
    # Detach products so they don't get cascade-killed (Category has
    # SET_NULL on Product.category already; this is defensive).
    cat.products.update(category=None)
    cat.delete()
    return out
