"""Linda's tools for marketplace listings (experiences and local goods).

The dashboard's Listings page and editor ship with these (Janus is the brain: a
merchant action ships with its agent tool). An update needs the merchant's yes.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from core.agents import ToolError, ToolResult, tool


def _row(s) -> dict:
    return {
        'slug': s.slug,
        'name': s.name,
        'kind': s.listing_kind,
        'host': s.vendor.name if s.vendor_id else '',
        'location': s.location,
        'price': str(s.price),
        'active': s.is_active,
        'top_pick': s.is_bestseller,
        'url': f'/bookings/{s.slug}/',
        'edit_url': f'/dashboard/listings/{s.pk}/edit/',
    }


@tool(
    name='listings.search',
    description=(
        'Find marketplace listings (bookable experiences and local goods sold by hosts): '
        'by text in the name, place or host, by kind ("experience" or "product") and by '
        'whether they are active.'
    ),
    scopes=['catalog.read'],
    schema={
        'type': 'object',
        'properties': {
            'q': {'type': 'string'},
            'kind': {'type': 'string', 'enum': ['experience', 'product']},
            'active': {'type': 'boolean'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 25},
        },
    },
)
def listings_search_tool(
    *, q: str = '', kind: str = '', active=None, limit: int = 25
) -> ToolResult:
    from django.db.models import Q

    from plugins.installed.booking_marketplace.models import BookableService

    qs = BookableService.objects.select_related('vendor')
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(location__icontains=q) | Q(vendor__name__icontains=q)
        )
    if kind in ('experience', 'product'):
        qs = qs.filter(listing_kind=kind)
    if active is not None:
        qs = qs.filter(is_active=bool(active))
    rows = [_row(s) for s in qs.order_by('name')[: max(1, min(int(limit or 25), 100))]]
    return ToolResult(output={'count': len(rows), 'listings': rows})


def _set_pairs(svc, fields) -> list[str]:
    """The itinerary and guest questions a call passed, checked as the import checks them."""
    from plugins.installed.booking_marketplace.content import PAIR_FIELDS, valid_pairs

    changed = []
    for name, (first, second) in PAIR_FIELDS.items():
        rows = fields.get(name)
        if rows is None:
            continue
        if not valid_pairs(rows, first, second, both=name == 'faqs'):
            raise ToolError(f'{name} must be a list of {first}/{second} rows, none empty')
        setattr(svc, name, rows)
        changed.append(name)
    return changed


@tool(
    name='listings.update',
    description=(
        'Change a marketplace listing: name, short description, description, price, '
        'was-price (strikethrough), location, duration label, active, top pick, the itinerary '
        'and the guest questions (each list replaces the old one). Only the '
        "fields you pass change. Needs the merchant's yes."
    ),
    scopes=['catalog.write'],
    requires_approval=True,
    schema={
        'type': 'object',
        'properties': {
            'slug': {'type': 'string'},
            'name': {'type': 'string'},
            'short_description': {'type': 'string'},
            'description': {'type': 'string'},
            'price': {
                'type': 'string',
                'description': 'Amount in the listing currency, e.g. "19.50".',
            },
            'original_price': {'type': 'string', 'description': 'Was-price; "" removes it.'},
            'location': {'type': 'string'},
            'duration_label': {'type': 'string'},
            'is_active': {'type': 'boolean'},
            'is_bestseller': {'type': 'boolean'},
            'itinerary': {
                'type': 'array',
                'description': 'The steps in order, each {"title", "detail"}.',
                'items': {
                    'type': 'object',
                    'properties': {'title': {'type': 'string'}, 'detail': {'type': 'string'}},
                    'required': ['title'],
                },
            },
            'faqs': {
                'type': 'array',
                'description': 'Guest questions shown on the page, each {"q", "a"}.',
                'items': {
                    'type': 'object',
                    'properties': {'q': {'type': 'string'}, 'a': {'type': 'string'}},
                    'required': ['q', 'a'],
                },
            },
        },
        'required': ['slug'],
    },
)
def listings_update_tool(*, slug: str, **fields) -> ToolResult:
    from djmoney.money import Money

    from plugins.installed.booking_marketplace.models import BookableService

    svc = BookableService.objects.filter(slug=slug).first()
    if svc is None:
        raise ToolError(f'no listing with slug {slug!r}')
    changed = []
    for name in ('name', 'short_description', 'description', 'location', 'duration_label'):
        if name in fields and fields[name] is not None:
            setattr(svc, name, str(fields[name]).strip())
            changed.append(name)
    for name in ('is_active', 'is_bestseller'):
        if name in fields and fields[name] is not None:
            setattr(svc, name, bool(fields[name]))
            changed.append(name)
    changed += _set_pairs(svc, fields)
    currency = svc.price.currency if svc.price else 'EUR'
    for name in ('price', 'original_price'):
        if name not in fields or fields[name] is None:
            continue
        raw = str(fields[name]).strip()
        if name == 'original_price' and raw == '':
            svc.original_price = None
        else:
            try:
                amount = Decimal(raw)
            except InvalidOperation as e:
                raise ToolError(f'{name} must be a number, got {raw!r}') from e
            if amount < 0:
                raise ToolError(f'{name} cannot be negative')
            setattr(svc, name, Money(amount, currency))
        changed.append(name)
    if not changed:
        raise ToolError('nothing to change: pass at least one field')
    svc.save()
    from plugins.installed.booking_marketplace.products import save_listing

    save_listing(svc)  # the listing's catalog Product changes with it
    return ToolResult(output={'updated': changed, 'listing': _row(svc)})
