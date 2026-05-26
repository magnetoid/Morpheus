"""Product image management — attach, remove, set primary."""
from __future__ import annotations

import mimetypes

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.text import slugify

from ._helpers import (
    _ALLOWED_IMAGE_TYPES,
    _MAX_IMAGE_BYTES,
    PublishError,
    _download,
    _serialize_image,
    _validate_https_url,
    logger,
)


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
