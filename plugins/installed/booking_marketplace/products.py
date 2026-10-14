"""A listing's catalog Product: linked or created once, then the source of truth.

Product owns name, slug, descriptions, price, was-price, category, host, photos and
status; the listing keeps the booking data and, for now, copies of the shared fields
that the rest of the app still reads (kept in step by sync_from_product).
"""

from __future__ import annotations

import logging

from django.db import transaction

logger = logging.getLogger('morpheus.booking_marketplace')


def _resolve_slug(service):
    """The Product to reuse, and the slug to use.

    A product on the slug with the same name and no listing of its own is this listing's
    old catalogue copy (Montenegro's 17 archived goods): reuse it. Any other product is
    someone else's and is never overwritten; the listing takes `<slug>-experience`, then
    `<slug>-experience-2`, … until a slug is free.
    """
    from plugins.installed.catalog.models import Product

    candidates = [service.slug, f'{service.slug}-experience']
    candidates += [f'{service.slug}-experience-{n}' for n in range(2, 100)]
    for slug in candidates:
        existing = Product.objects.filter(slug=slug).first()
        if existing is None:
            return None, slug
        same_name = existing.name.strip().lower() == service.name.strip().lower()
        if same_name and getattr(existing, 'booking', None) is None:
            return existing, slug
    raise ValueError(f'No free product slug for listing {service.slug!r}')


def _stored(fieldfile) -> bool:
    try:
        return bool(fieldfile) and fieldfile.storage.exists(fieldfile.name)
    except Exception:  # noqa: BLE001 — an unreachable storage never stops the link
        return False


def _copy_images(service, product) -> None:
    """The listing photo (primary) then its gallery, for a product with no photos yet.

    A reused product keeps the photos it has: copying the listing's on top would show
    the same picture twice under two file names. A file missing from storage is skipped.
    """
    from plugins.installed.catalog.models import ProductImage

    if product.images.exists():
        return
    photos = [(service.image, service.name)] + [
        (img.image, img.alt or service.name) for img in service.images.all()
    ]
    photos = [(f, alt) for f, alt in photos if _stored(f)]
    for i, (fieldfile, alt) in enumerate(photos):
        ProductImage.objects.create(
            product=product,
            image=fieldfile.name,
            is_primary=(i == 0),
            sort_order=i,
            alt_text=alt[:255],
        )


@transaction.atomic
def ensure_product(service):
    """Link the listing to its Product, creating it from the listing if needed."""
    from djmoney.money import Money

    from plugins.installed.catalog.models import Product
    from plugins.installed.seo.models import Redirect

    if service.product_id:
        return service.product
    existing, slug = _resolve_slug(service)
    product = existing or Product(slug=slug, sku=f'BK-{service.pk.hex[:12].upper()}')
    product.name = service.name
    product.short_description = service.short_description
    product.description = service.description
    product.price = Money(service.price.amount, service.price.currency)
    product.compare_at_price = (
        Money(service.original_price.amount, service.original_price.currency)
        if service.original_price
        else None
    )
    product.category_id = service.category_id
    product.vendor_id = service.vendor_id
    product.product_type = 'service'
    product.status = 'active' if service.is_active else 'draft'
    product.requires_shipping = False
    product.track_inventory = False
    product.save()
    _copy_images(service, product)
    service.product = product
    service.save(update_fields=['product'])
    # An experience is a page at /bookings/<slug>/; anyone at its product URL goes there.
    Redirect.objects.get_or_create(
        from_path=f'/products/{product.slug}/',
        defaults={
            'to_path': f'/bookings/{service.slug}/',
            'status_code': 301,
            'source': 'auto_slug',
            'note': 'Booking listing: the page is at /bookings/',
        },
    )
    return product


def sync_from_product(product) -> None:
    """Copy the Product's shared fields onto its listing."""
    service = getattr(product, 'booking', None)
    if service is None:
        return
    service.name = product.name
    service.short_description = product.short_description
    service.description = product.description
    service.price = product.price
    service.original_price = product.compare_at_price
    service.category_id = product.category_id
    service.vendor_id = product.vendor_id
    service.is_active = product.status == 'active'
    service.save(
        update_fields=[
            'name',
            'short_description',
            'description',
            'price',
            'original_price',
            'category',
            'vendor',
            'is_active',
        ]
    )


def sync_to_product(service) -> None:
    """Copy a host's or the listing editor's edits of the shared fields onto the Product."""
    product = service.product
    if product is None:
        return
    product.name = service.name
    product.short_description = service.short_description
    product.description = service.description
    product.price = service.price
    product.compare_at_price = service.original_price
    product.category_id = service.category_id
    product.vendor_id = service.vendor_id
    # An inactive listing hides its product, but a product the merchant archived
    # stays archived rather than coming back as a draft.
    if service.is_active:
        product.status = 'active'
    elif product.status == 'active':
        product.status = 'draft'
    product._booking_sync = True  # on_product_updated: this save came from the listing
    try:
        product.save()
    finally:
        product._booking_sync = False


def save_listing(service) -> None:
    """After a listing is saved by its host or the editor: link its Product, push the edits."""
    ensure_product(service)
    sync_to_product(service)


def on_product_updated(*, product=None, **_) -> None:
    """PRODUCT_UPDATED: the product editor (or Linda) changed a listing's product."""
    if product is None or getattr(product, '_booking_sync', False):
        return
    try:
        # Its own savepoint: a failure here never aborts the caller's transaction.
        with transaction.atomic():
            sync_from_product(product)
    except Exception:  # noqa: BLE001
        logger.warning('booking: sync from product %s failed', product.pk, exc_info=True)
