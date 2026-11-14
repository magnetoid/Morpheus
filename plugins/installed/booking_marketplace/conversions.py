"""A lead or a booking, announced once after it commits (v0.162.0).

`ENQUIRY_CREATED`, `BOOKING_CREATED` and `BOOKING_CONFIRMED` (core/hooks.py) carry
one shape, built here, so analytics and tracking report a conversion without
reading this app's models. Each fires from `transaction.on_commit`: a booking that
rolls back is never reported, and nothing a subscriber does can undo the booking.
"""

from __future__ import annotations

import contextlib
import logging

from django.db import transaction

logger = logging.getLogger('morpheus.booking_marketplace')


def _stored(obj, field: str):
    """The field as stored: a page may show a translation on the same instance
    (core.i18n keeps the original in `_morph_untranslated`)."""
    if obj is None:
        return ''
    originals = getattr(obj, '__dict__', {}).get('_morph_untranslated') or {}
    return originals[field] if field in originals else (getattr(obj, field, '') or '')


def _default_language_label(value) -> str:
    """A choice label in the store's default language, not the visitor's."""
    from django.utils import translation

    from core.i18n.services import default_language

    with translation.override(default_language()):
        return str(value)


def _experience_item(service, *, price=None, quantity=1) -> dict:
    product = service.product if service.product_id else None
    category = service.category if service.category_id else None
    return {
        'id': _stored(product, 'slug') if product is not None else service.slug,
        'name': _stored(product, 'name') if product is not None else _stored(service, 'name'),
        'category': _stored(category, 'name') if category is not None else '',
        'price': price,
        'quantity': max(1, int(quantity or 1)),
    }


def _stay_item(prop, room_type=None, *, price=None, quantity=1) -> dict:
    name = _stored(prop, 'name')
    item_id = prop.slug
    if room_type is not None:
        name = f'{name} · {room_type.name}'
        item_id = f'{prop.slug}/{room_type.slug}'
    return {
        'id': item_id,
        'name': name,
        'category': _default_language_label(prop.get_property_type_display()),
        'price': price,
        'quantity': max(1, int(quantity or 1)),
    }


def enquiry_shape(enquiry) -> dict:
    """ENQUIRY_CREATED's kwargs for an experience enquiry or a stay enquiry."""
    from plugins.installed.booking_marketplace.models import StayEnquiry

    if isinstance(enquiry, StayEnquiry):
        prop = enquiry.property if enquiry.property_id else None
        room = enquiry.room_type if enquiry.room_type_id else None
        items = [_stay_item(prop, room, quantity=enquiry.rooms)] if prop is not None else []
        return {
            'enquiry': enquiry,
            'kind': 'stay',
            'reference': str(enquiry.pk),
            'value': None,
            'items': items,
            'product': None,
            'customer': enquiry.customer,
            'service_date': enquiry.check_in,
        }
    service = enquiry.service if enquiry.service_id else None
    return {
        'enquiry': enquiry,
        'kind': 'experience',
        'reference': str(enquiry.pk),
        'value': None,
        'items': [_experience_item(service, quantity=enquiry.guests)] if service else [],
        'product': service.product if service is not None and service.product_id else None,
        'customer': enquiry.customer,
        'service_date': enquiry.preferred_date,
    }


def booking_shape(booking) -> dict:
    """BOOKING_CREATED / BOOKING_CONFIRMED's kwargs for an experience or a stay booking.

    A booking is one item at its total, so the items add up to the value.
    """
    from plugins.installed.booking_marketplace.models import StayBooking

    if isinstance(booking, StayBooking):
        return {
            'booking': booking,
            'kind': 'stay',
            'reference': str(booking.pk),
            'value': booking.total,
            'items': [_stay_item(booking.property, booking.room_type, price=booking.total)],
            'product': None,
            'customer': booking.customer,
            'service_date': booking.check_in,
        }
    service = booking.service
    return {
        'booking': booking,
        'kind': 'experience',
        'reference': str(booking.pk),
        'value': booking.total_price,
        'items': [_experience_item(service, price=booking.total_price)],
        'product': service.product if service.product_id else None,
        'customer': booking.customer,
        'service_date': booking.booking_date,
    }


def _fire(event: str, shape: dict, request) -> None:
    from morpheus.core import hook_registry

    with contextlib.suppress(Exception):  # a subscriber never fails a booking
        hook_registry.fire(event, **shape, request=request)


def announce_enquiry(enquiry, *, request=None) -> None:
    """ENQUIRY_CREATED, once the enquiry commits."""
    from morpheus.core import MorpheusEvents

    def _send():
        _fire(MorpheusEvents.ENQUIRY_CREATED, enquiry_shape(enquiry), request)

    transaction.on_commit(_send)


def announce_booking(booking, *, request=None) -> None:
    """BOOKING_CREATED once the booking commits, then BOOKING_CONFIRMED when it
    was created confirmed (a stay always is)."""
    from morpheus.core import MorpheusEvents

    def _send():
        shape = booking_shape(booking)
        _fire(MorpheusEvents.BOOKING_CREATED, shape, request)
        if booking.status == 'confirmed':
            _fire(MorpheusEvents.BOOKING_CONFIRMED, booking_shape(booking), request)

    transaction.on_commit(_send)


def announce_confirmed(booking) -> None:
    """BOOKING_CONFIRMED for a booking a host or staff member confirmed later.

    No request: the shopper is not there, so the visit and the GA ids come from
    what their apps stamped on the booking when it was made.
    """
    from morpheus.core import MorpheusEvents

    transaction.on_commit(
        lambda: _fire(MorpheusEvents.BOOKING_CONFIRMED, booking_shape(booking), None)
    )


def consent_stamp(request):
    """The shopper's consent, kept on the booking for a later confirmation's
    sends (core.consent.allowed reads `metadata['consent']`, as on an order)."""
    if request is None:
        return None
    try:
        from core.consent import stamp

        return {'consent': stamp(request)}
    except Exception as exc:  # noqa: BLE001 — a missing stamp only means a later send asks the store
        logger.warning('booking_marketplace: no consent stamp: %s', exc)
        return None
