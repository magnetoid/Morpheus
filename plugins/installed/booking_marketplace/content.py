"""Write content to listings and their Products, with a backup that restores it.

The input maps a listing slug to the fields to write; every field is optional:

    {"<slug>": {
        "name": "…", "short_description": "…", "description": "<p>…</p>",
        "category": "<category slug>",
        "seo_title": "…", "seo_description": "…",
        "highlights": ["…"], "what_to_bring": ["…"],
        "itinerary": [{"title": "…", "detail": "…"}],
        "faqs": [{"q": "…", "a": "…"}],
        "seo_auto_filled": false, "seo_provenance": {"title": "ai"}
    }}

Product owns the name, the texts and the category (PRODUCT_UPDATED copies them onto
the listing); the listing owns its booking lists; the product's SeoMeta row holds the
SEO title and description. `snapshot()` returns the current values of exactly the
fields an input writes, in the same shape, so applying a backup restores it.
"""

from __future__ import annotations

from django.db import transaction

PRODUCT_FIELDS = ('name', 'short_description', 'description')
LIST_FIELDS = ('highlights', 'what_to_bring')
PAIR_FIELDS = {'itinerary': ('title', 'detail'), 'faqs': ('q', 'a')}
SEO_FIELDS = {'seo_title': 'title', 'seo_description': 'description'}
FIELDS = {
    *PRODUCT_FIELDS,
    *LIST_FIELDS,
    *PAIR_FIELDS,
    *SEO_FIELDS,
    'category',
    'seo_auto_filled',
    'seo_provenance',
}
LIMITS = {'name': 200, 'short_description': 300, 'seo_title': 200, 'seo_description': 320}


def _text_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value)


def _pairs(value, first: str, second: str, *, both: bool) -> bool:
    if not isinstance(value, list):
        return False
    for row in value:
        if not (isinstance(row, dict) and set(row) <= {first, second}):
            return False
        one, two = row.get(first), row.get(second, '')
        if not (isinstance(one, str) and one.strip() and isinstance(two, str)):
            return False
        if both and not two.strip():
            return False
    return True


def _text_problems(fields) -> list[str]:
    from plugins.installed.booking_marketplace.products import plain_text

    problems = []
    for key in (*PRODUCT_FIELDS, *SEO_FIELDS):
        if key in fields and not isinstance(fields[key], str):
            problems.append(f'{key} must be text')
    if isinstance(fields.get('name'), str) and not fields['name'].strip():
        problems.append('name is empty')
    for key, limit in LIMITS.items():
        value = fields.get(key)
        if isinstance(value, str):
            size = len(plain_text(value)) if key == 'short_description' else len(value)
            if size > limit:
                problems.append(f'{key} is {size} characters, over {limit}')
    return problems


def _shape_problems(fields, categories) -> list[str]:
    problems = [f'unknown field {key!r}' for key in sorted(set(fields) - FIELDS)]
    for key in LIST_FIELDS:
        if key in fields and not _text_list(fields[key]):
            problems.append(f'{key} must be a list of text')
    for key, (first, second) in PAIR_FIELDS.items():
        if key in fields and not _pairs(fields[key], first, second, both=key == 'faqs'):
            problems.append(f'{key} must be a list of {first}/{second} rows')
    category = fields.get('category')
    if 'category' in fields and category is not None and category not in categories:
        problems.append(f'unknown category {category!r}')
    if 'seo_auto_filled' in fields and not isinstance(fields['seo_auto_filled'], bool):
        problems.append('seo_auto_filled must be true or false')
    if 'seo_provenance' in fields and not isinstance(fields['seo_provenance'], dict):
        problems.append('seo_provenance must be an object')
    return problems


def validate(data) -> list[str]:
    """Every problem with an input, or []: nothing is written while any remain."""
    from plugins.installed.booking_marketplace.models import BookableService
    from plugins.installed.catalog.models import Category

    if not isinstance(data, dict) or not data:
        return ['the file must map listing slugs to their fields']
    linked = set(
        BookableService.objects.filter(slug__in=list(data), product__isnull=False).values_list(
            'slug', flat=True
        )
    )
    categories = set(Category.objects.values_list('slug', flat=True))
    problems = []
    for slug, fields in data.items():
        if slug not in linked:
            problems.append(f'{slug}: no listing with a product')
        elif not isinstance(fields, dict):
            problems.append(f'{slug}: the fields must be an object')
        else:
            found = _shape_problems(fields, categories) + _text_problems(fields)
            problems += [f'{slug}: {problem}' for problem in found]
    return problems


def _seo_row(product, *, create: bool = False):
    from django.contrib.contenttypes.models import ContentType

    from plugins.installed.seo.models import SeoMeta

    lookup = {
        'content_type': ContentType.objects.get_for_model(type(product)),
        'object_id': str(product.pk),
    }
    if create:
        return SeoMeta.objects.get_or_create(**lookup)[0]
    return SeoMeta.objects.filter(**lookup).first()


def snapshot(data) -> dict:
    """The current values of exactly the fields `data` writes, in the input's shape."""
    from plugins.installed.booking_marketplace.models import BookableService

    backup = {}
    for service in BookableService.objects.filter(slug__in=list(data)).select_related(
        'product__category'
    ):
        fields, product, current = data[service.slug], service.product, {}
        for key in PRODUCT_FIELDS:
            if key in fields:
                current[key] = getattr(product, key)
        for key in (*LIST_FIELDS, *PAIR_FIELDS):
            if key in fields:
                current[key] = getattr(service, key)
        if 'category' in fields:
            current['category'] = product.category.slug if product.category_id else None
        if any(key in fields for key in SEO_FIELDS):
            meta = _seo_row(product)
            for key, column in SEO_FIELDS.items():
                current[key] = getattr(meta, column, '') if meta else ''
            current['seo_auto_filled'] = bool(meta.auto_filled) if meta else True
            current['seo_provenance'] = dict(meta.provenance or {}) if meta else {}
        backup[service.slug] = current
    return backup


@transaction.atomic
def apply(data) -> int:
    """Write a validated input; returns the number of listings written."""
    from plugins.installed.booking_marketplace.models import BookableService
    from plugins.installed.catalog.models import Category

    written = 0
    for service in BookableService.objects.filter(slug__in=list(data)).select_related('product'):
        fields, product = data[service.slug], service.product
        for key in PRODUCT_FIELDS:
            if key in fields:
                setattr(product, key, fields[key])
        if 'category' in fields:
            slug = fields['category']
            product.category = Category.objects.get(slug=slug) if slug else None
        product.save()  # PRODUCT_UPDATED copies the name, texts and category onto the listing
        service.refresh_from_db()
        lists = [key for key in (*LIST_FIELDS, *PAIR_FIELDS) if key in fields]
        for key in lists:
            setattr(service, key, fields[key])
        if lists:
            service.save(update_fields=lists)
        if any(key in fields for key in SEO_FIELDS):
            meta = _seo_row(product, create=True)
            origin = dict(meta.provenance or {})
            for key, column in SEO_FIELDS.items():
                if key in fields:
                    setattr(meta, column, fields[key])
                    origin[column] = 'ai'
            meta.auto_filled = fields.get('seo_auto_filled', False)
            meta.provenance = fields.get('seo_provenance', origin)
            meta.save()
        written += 1
    return written
