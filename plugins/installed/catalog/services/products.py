"""Product-level write operations.

``publish_digital_product`` is the canonical "external agent uploads a
PDF book" entry point — validates HTTPS URLs, downloads PDF + cover
under hard size/timeout caps, then materialises Product + ProductImage
in a single transaction.

``create_product`` / ``update_product`` are the generic CRUD surface
used by the MCP tool layer and GraphQL mutations.
``archive_product`` / ``restore_product`` / ``delete_product`` are the
corresponding lifecycle hooks. ``update_digital_pdf`` swaps the
digital_file on an existing digital product.
"""
from __future__ import annotations

import mimetypes
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.text import slugify

from ._helpers import (
    _ALLOWED_IMAGE_TYPES,
    _MAX_IMAGE_BYTES,
    _MAX_PDF_BYTES,
    _PRODUCT_SCALAR_FIELDS,
    _VALID_PRODUCT_TYPES,
    _VALID_STATUSES,
    PublishError,
    _coerce_price,
    _download,
    _serialize_product,
    _unique_slug,
    _unique_sku,
    _validate_https_url,
    logger,
)


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
        # Some CDNs return application/octet-stream — be forgiving — but
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

    # Append author to description if not already mentioned —
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


@transaction.atomic
def update_product(*, slug: str, **fields) -> dict[str, str]:
    """Update an existing product by slug. Only fields present in `fields`
    are touched. Unknown fields raise PublishError to catch typos early.

    Recognised field names:
      • Scalar text/bool/numeric: see ``_PRODUCT_SCALAR_FIELDS``.
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


@transaction.atomic
def update_digital_pdf(*, slug: str, pdf_url: str) -> dict[str, str]:
    """Replace the digital_file on an existing product by downloading
    a new PDF from `pdf_url`. Use this when an agent has a fresh
    revision of a book and wants to swap the customer download.

    The old file is removed by ProductImage-style file-strip semantics
    on the underlying FileField.
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
