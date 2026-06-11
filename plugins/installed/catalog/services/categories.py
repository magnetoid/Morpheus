"""Category-level write operations."""

from __future__ import annotations

from django.db import transaction
from django.utils.text import slugify

from ._helpers import (
    PublishError,
    _serialize_category,
    logger,
)


@transaction.atomic
def create_category(
    *,
    name: str,
    slug: str = '',
    parent_slug: str = '',
    description: str = '',
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
        name=name,
        slug=chosen,
        parent=parent,
        description=(description or '').strip(),
    )
    logger.info('catalog.create_category slug=%s', cat.slug)
    return _serialize_category(cat)


@transaction.atomic
def update_category(
    *,
    slug: str,
    name: str = '',
    new_slug: str = '',
    parent_slug: str | None = None,
    description: str | None = None,
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
