"""Accommodation (stays) engine — server-side trusted pricing + availability.

All money and inventory logic lives here, never in views/templates/client:
- `quote_stay` derives room subtotal, the 12% service fee, and the Montenegro
  tourist tax for a date range + occupancy (single source of truth).
- `room_availability` derives free rooms from overlapping bookings (no calendar).
- `create_stay_booking` checks availability under a row lock and persists a
  server-derived snapshot. `submit_stay_enquiry` captures a listing-mode lead.

Mirrors the discipline of services.py (create_booking / price_quote).
"""

from __future__ import annotations

import datetime
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.booking_marketplace.services import (
    ACTIVE_STATUSES,
    SERVICE_FEE_RATE,
    BookingError,
)

STAY_TOURIST_TAX_PER_PERSON_NIGHT = Decimal(str(getattr(settings, 'BOOKING_TOURIST_TAX', '1.00')))
MAX_STAY_NIGHTS = 30


def _as_date(v) -> datetime.date:
    """Coerce a date / datetime / ISO 'YYYY-MM-DD' string to a date."""
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    try:
        return datetime.date.fromisoformat(str(v).strip())
    except (ValueError, AttributeError):
        raise BookingError('Please choose valid dates.') from None


def nights_between(check_in, check_out) -> int:
    ci, co = _as_date(check_in), _as_date(check_out)
    if ci < timezone.localdate():
        raise BookingError('Check-in cannot be in the past.')
    nights = (co - ci).days
    if nights < 1:
        raise BookingError('Check-out must be after check-in.')
    if nights > MAX_STAY_NIGHTS:
        raise BookingError(f'Stays are limited to {MAX_STAY_NIGHTS} nights.')
    return nights


def quote_stay(room_type, *, check_in, check_out, rooms=1, adults=2, children=0) -> dict:
    """Server-derived quote for a stay. Raises BookingError on bad input."""
    ci, co = _as_date(check_in), _as_date(check_out)
    nights = nights_between(ci, co)
    try:
        rooms, adults, children = int(rooms), int(adults), int(children)
    except (TypeError, ValueError):
        raise BookingError('Please enter valid guest and room numbers.') from None
    if rooms < 1:
        raise BookingError('At least one room is required.')
    if adults < 1:
        raise BookingError('At least one adult is required.')
    guests = adults + children
    if guests > room_type.max_occupancy * rooms:
        raise BookingError(f'Up to {room_type.max_occupancy} guest(s) per room.')
    if children > room_type.max_children * rooms:
        raise BookingError('Too many children for this room type.')

    currency = room_type.base_rate.currency
    rate = room_type.base_rate
    nightly = [
        {'date': (ci + datetime.timedelta(days=i)).isoformat(), 'rate': rate} for i in range(nights)
    ]
    room_subtotal = rate * nights * rooms
    fee_amount = (room_subtotal.amount * SERVICE_FEE_RATE).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )
    service_fee = Money(fee_amount, currency)
    tax_amount = (STAY_TOURIST_TAX_PER_PERSON_NIGHT * guests * nights).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )
    tourist_tax = Money(tax_amount, currency)
    return {
        'nights': nights,
        'rooms': rooms,
        'adults': adults,
        'children': children,
        'guests': guests,
        'check_in': ci,
        'check_out': co,
        'nightly': nightly,
        'room_subtotal': room_subtotal,
        'service_fee': service_fee,
        'tourist_tax': tourist_tax,
        'total': room_subtotal + service_fee + tourist_tax,
        'currency': str(currency),
    }


def room_availability(room_type, check_in, check_out) -> int:
    """Rooms of `room_type` free for every night in [check_in, check_out).

    Availability = room_count minus the peak number of rooms occupied on any
    single night in the range by overlapping pending/confirmed StayBookings.
    A booking occupies night N iff booking.check_in <= N < booking.check_out,
    so a check-out day frees the room for a same-day check-in.
    """
    from plugins.installed.booking_marketplace.models import StayBooking

    ci, co = _as_date(check_in), _as_date(check_out)
    overlapping = list(
        StayBooking.objects.filter(
            room_type=room_type,
            status__in=ACTIVE_STATUSES,
            check_in__lt=co,
            check_out__gt=ci,
        ).values('check_in', 'check_out', 'rooms')
    )
    peak = 0
    for i in range((co - ci).days):
        night = ci + datetime.timedelta(days=i)
        used = sum(b['rooms'] for b in overlapping if b['check_in'] <= night < b['check_out'])
        peak = max(peak, used)
    return max(0, (room_type.room_count or 0) - peak)


@transaction.atomic
def create_stay_booking(
    *,
    room_type,
    customer=None,
    customer_name,
    customer_email,
    customer_phone='',
    check_in,
    check_out,
    rooms=1,
    adults=2,
    children=0,
    notes='',
):
    """Create a confirmed stay booking with server-derived totals.

    Locks the room-type row so concurrent bookings can't oversell: the
    availability check + insert run while holding the lock. Raises BookingError
    on any validation failure.
    """
    from plugins.installed.booking_marketplace.models import RoomType, StayBooking

    rt = RoomType.objects.select_for_update().get(pk=room_type.pk)
    if not rt.is_active:
        raise BookingError('This room type is not available.')

    quote = quote_stay(
        rt, check_in=check_in, check_out=check_out, rooms=rooms, adults=adults, children=children
    )
    available = room_availability(rt, quote['check_in'], quote['check_out'])
    if quote['rooms'] > available:
        raise BookingError(
            f'Only {available} room(s) left for those dates.'
            if available > 0
            else 'No rooms available for those dates.'
        )
    if not (customer_name and customer_email):
        raise BookingError('Your name and email are required.')

    # Phase 1: no payment step yet — the booking is 'confirmed' and holds
    # inventory immediately. Do NOT enable marketplace mode until the Phase 3
    # payment bridge gates this (listing mode books nothing — it enquires).
    return StayBooking.objects.create(
        room_type=rt,
        property=rt.property,
        customer=customer if (customer and getattr(customer, 'is_authenticated', False)) else None,
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        check_in=quote['check_in'],
        check_out=quote['check_out'],
        nights=quote['nights'],
        rooms=quote['rooms'],
        adults=quote['adults'],
        children=quote['children'],
        nightly_breakdown=[
            {'date': n['date'], 'rate': str(n['rate'].amount)} for n in quote['nightly']
        ],
        subtotal=quote['room_subtotal'],
        service_fee=quote['service_fee'],
        tourist_tax=quote['tourist_tax'],
        total=quote['total'],
        status='confirmed',
        notes=notes,
    )


def submit_stay_enquiry(
    *,
    property,
    room_type=None,
    customer=None,
    name='',
    email,
    phone='',
    check_in=None,
    check_out=None,
    rooms=None,
    adults=None,
    children=None,
    message='',
):
    """Capture a 'Contact for price' accommodation lead (listing mode; anon-allowed)."""
    from plugins.installed.booking_marketplace.models import StayEnquiry

    if not email:
        raise BookingError('An email is required to enquire.')

    def _opt_date(v):
        if v in ('', None):
            return None
        try:
            return _as_date(v)
        except BookingError:
            return None

    def _opt_int(v):
        if v in ('', None):
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    enquiry = StayEnquiry.objects.create(
        property=property,
        room_type=room_type,
        customer=customer if (customer and getattr(customer, 'is_authenticated', False)) else None,
        name=name or '',
        email=email,
        phone=phone or '',
        check_in=_opt_date(check_in),
        check_out=_opt_date(check_out),
        rooms=_opt_int(rooms),
        adults=_opt_int(adults),
        children=_opt_int(children),
        message=message or '',
    )
    try:
        from plugins.installed.booking_marketplace.email import notify_stay_enquiry

        notify_stay_enquiry(enquiry)
    except Exception:  # noqa: BLE001, S110 — best-effort notify; never block the enquiry
        pass
    return enquiry


def nearby_places(prop, *, limit=6):
    """Destination guides in this hotel's region.

    Internal links from a stay to the /places/ pages that rank for the region
    — the hub<->spoke the audit asked for (§4.2). Empty when the hotel has no
    region set."""
    from plugins.installed.booking_marketplace.models import Place

    if not prop.region:
        return []
    return list(Place.objects.filter(is_active=True, region=prop.region).order_by('name')[:limit])


def related_stays(prop, *, limit=6):
    """Other active hotels near this one: the same town first, then the wider
    region, never itself or an inactive vendor's.

    Ordered by star class — a real hotel attribute, not the guest rating this
    store stopped publishing — so the card shows ★, never a review number."""
    from plugins.installed.booking_marketplace.models import Property

    base = Property.objects.filter(is_active=True, vendor__is_active=True).exclude(pk=prop.pk)
    picked, seen = [], set()
    if prop.location:
        for p in base.filter(location__iexact=prop.location).order_by('-star_rating', 'name')[
            :limit
        ]:
            picked.append(p)
            seen.add(p.pk)
    if len(picked) < limit and prop.region:
        remaining = (
            base.filter(region=prop.region)
            .exclude(pk__in=seen)
            .order_by('-star_rating', 'name')[: limit - len(picked)]
        )
        picked.extend(remaining)
    return picked
