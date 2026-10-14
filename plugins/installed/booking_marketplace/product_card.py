"""The Booking details card on the dashboard product editor (PRODUCT_FORM_CARDS / _SAVED).

A listing's Product is edited in the product editor; this card carries what only a
booking needs. Inputs are named ``booking__<field>``, so a save without the card on
the form (another editor, an API call) changes nothing here.
"""

from __future__ import annotations

PREFIX = 'booking__'
_TEXT = {
    'location': 120,
    'duration_label': 60,
    'meeting_point': None,
    'cancellation_policy': None,
}
_NUMBERS = ('duration_minutes', 'daily_capacity', 'max_guests_per_booking')
_LINES = ('highlights', 'included', 'not_included', 'what_to_bring')


def on_product_form_cards(value, product=None, **kwargs):
    listing = getattr(product, 'booking', None) if getattr(product, 'pk', None) else None
    if listing is None:
        return value
    from plugins.installed.booking_marketplace.models import REGIONS, BookableService

    value.append(
        {
            'template': 'booking_marketplace/_product_form_card.html',
            'context': {
                'listing': listing,
                'listing_kinds': BookableService.LISTING_KINDS,
                'regions': REGIONS,
                'line_fields': [(name, '\n'.join(getattr(listing, name) or [])) for name in _LINES],
            },
            'order': 60,
        }
    )
    return value


def _number(raw: str):
    try:
        number = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return number if number >= 1 else None


def on_product_form_saved(product=None, post=None, **kwargs):
    listing = getattr(product, 'booking', None) if product is not None else None
    if listing is None or post is None or not any(k.startswith(PREFIX) for k in post):
        return
    from plugins.installed.booking_marketplace.models import REGIONS, BookableService

    def has(name):
        return f'{PREFIX}{name}' in post

    def get(name):
        return (post.get(f'{PREFIX}{name}') or '').strip()

    if has('listing_kind') and get('listing_kind') in dict(BookableService.LISTING_KINDS):
        listing.listing_kind = get('listing_kind')
    if has('region') and (get('region') == '' or get('region') in dict(REGIONS)):
        listing.region = get('region')
    for name, limit in _TEXT.items():
        if has(name):
            setattr(listing, name, get(name)[:limit] if limit else get(name))
    for name in _NUMBERS:
        number = _number(get(name)) if has(name) else None
        if number is not None:  # a blank or bad number keeps the stored one
            setattr(listing, name, number)
    if has('languages'):
        listing.languages = [s.strip() for s in get('languages').split(',') if s.strip()]
    for name in _LINES:
        if has(name):
            setattr(
                listing, name, [line.strip() for line in get(name).splitlines() if line.strip()]
            )
    from django.db import transaction

    with transaction.atomic():  # its own savepoint: a failure never aborts the editor's save
        listing.save()
