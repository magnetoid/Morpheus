"""Booking marketplace — server-side trusted operations.

All money + capacity logic lives here, never in views/templates/client:
- `available_dates` lists bookable dates (weekday availability − full days).
- `create_booking` derives subtotal/fee/total, checks capacity under a row
  lock, and sets status. Mirrors the reference site's create_booking RPC.
- `submit_enquiry` captures a "Contact for price" lead (listing mode).
"""

from __future__ import annotations

import contextlib
import datetime
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Avg, Count, Sum
from django.utils import timezone
from djmoney.money import Money

SERVICE_FEE_RATE = Decimal('0.12')  # 12% platform fee (matches reference)
ACTIVE_STATUSES = ('pending', 'confirmed')


class BookingError(ValueError):
    """Raised when a booking can't be made (bad input / no capacity)."""


def _validated_guest_count(svc, guests) -> int:
    """Coerce + bounds-check a flat guest count against the service limits."""
    try:
        guests = int(guests)
    except (TypeError, ValueError):
        raise BookingError('Please enter a valid number of guests.') from None
    if guests < 1:
        raise BookingError('At least one guest is required.')
    if svc.max_guests_per_booking and guests > svc.max_guests_per_booking:
        raise BookingError(f'Up to {svc.max_guests_per_booking} guests per booking.')
    return guests


def _weekdays(service) -> set[int]:
    days = {w.weekday for w in service.availability.all()}
    return days or set(range(7))  # no windows → runs every day (capacity-limited)


def booked_guests(service, date, time=None) -> int:
    """Guests already holding a spot on `date` (pending + confirmed).

    `time is None` counts every active booking that date (back-compat: the
    date-level capacity check). When `time` (an 'HH:MM' string) is given, only
    bookings on that departure are counted.
    """
    qs = service.bookings.filter(booking_date=date, status__in=ACTIVE_STATUSES)
    if time is not None:
        qs = qs.filter(time_slot=time)
    return qs.aggregate(n=Sum('guests'))['n'] or 0


def available_dates(service, *, days: int = 30, limit: int = 30) -> list[dict]:
    """Upcoming dates with remaining capacity, soonest first."""
    weekdays = _weekdays(service)
    today = timezone.localdate()
    out: list[dict] = []
    for d in range(days):
        date = today + datetime.timedelta(days=d)
        if date.weekday() not in weekdays:
            continue
        remaining = (service.daily_capacity or 0) - booked_guests(service, date)
        if remaining > 0:
            out.append({'date': date, 'remaining': remaining})
            if len(out) >= limit:
                break
    return out


def _start_times(service) -> list:
    """Sorted distinct 'HH:MM' departure strings, or [None] when the service
    runs with no explicit start times (a single any-time slot)."""
    times = sorted(
        {w.start_time.strftime('%H:%M') for w in service.availability.all() if w.start_time}
    )
    return times or [None]


def available_sessions(service, *, days: int = 30, limit: int = 30) -> list:
    """Upcoming dates, each with its bookable departures + remaining capacity."""
    weekdays = _weekdays(service)
    times = _start_times(service)
    today = timezone.localdate()
    out: list[dict] = []
    for d in range(days):
        date = today + datetime.timedelta(days=d)
        if date.weekday() not in weekdays:
            continue
        slots = []
        for t in times:
            remaining = (service.daily_capacity or 0) - booked_guests(service, date, t)
            if remaining > 0:
                slots.append({'time': t, 'remaining': remaining})
        if slots:
            out.append({'date': date, 'times': slots})
            if len(out) >= limit:
                break
    return out


@transaction.atomic
def create_booking(
    service,
    *,
    booking_date,
    guests: int = 0,
    name: str,
    email: str,
    phone: str = '',
    notes: str = '',
    time: str = '',
    tiers=None,
    addons=None,
    user=None,
):
    """Create a confirmed (or pending) booking with server-derived totals.

    Totals come from `price_quote` — either from the selected pricing tiers +
    add-ons, or (when none are given) the flat per-guest price. Capacity is
    checked while holding a row lock on the service so concurrent requests can't
    overbook. Raises BookingError on any validation failure.
    """
    from plugins.installed.booking_marketplace.models import BookableService, Booking

    # Lock the service row for the duration of the capacity check + insert.
    svc = BookableService.objects.select_for_update().get(pk=service.pk)
    if not svc.is_active:
        raise BookingError('This experience is not available for booking.')

    use_quote = bool(tiers) or bool(addons)
    if use_quote:
        quote = price_quote(svc, tiers=tiers or {}, addons=addons or {})
        guests = quote['guests']
    else:
        guests = _validated_guest_count(svc, guests)
        quote = price_quote(svc, tiers={'guests': guests}, addons={})

    if isinstance(booking_date, str):
        try:
            booking_date = datetime.date.fromisoformat(booking_date)
        except ValueError:
            raise BookingError('Please choose a valid date.') from None
    if booking_date < timezone.localdate():
        raise BookingError('That date has already passed.')
    if booking_date.weekday() not in _weekdays(svc):
        raise BookingError('This experience does not run on that day.')

    # If the experience runs at fixed departure times, a chosen time must be one
    # of them — never trust a client-supplied slot that was never offered.
    starts = _start_times(svc)
    if time and starts != [None] and time not in starts:
        raise BookingError('Please choose an available departure time.')

    remaining = (svc.daily_capacity or 0) - booked_guests(svc, booking_date, time or None)
    if guests > remaining:
        raise BookingError(
            f'Only {remaining} spot(s) left on that date.'
            if remaining > 0
            else 'That date is fully booked.'
        )

    if not (name and email):
        raise BookingError('Your name and email are required.')

    return Booking.objects.create(
        service=svc,
        customer=user if (user and user.is_authenticated) else None,
        customer_name=name,
        customer_email=email,
        customer_phone=phone,
        booking_date=booking_date,
        time_slot=time,
        guests=guests,
        subtotal=quote['subtotal'],
        service_fee=quote['fee'],
        total_price=quote['total'],
        status='pending' if svc.requires_approval else 'confirmed',
        notes=notes,
        tier_breakdown=quote['tier_breakdown'],
        addons=quote['addons'],
    )


def submit_enquiry(
    service,
    *,
    email: str,
    name: str = '',
    phone: str = '',
    preferred_date=None,
    guests=None,
    message: str = '',
    time: str = '',
    tiers=None,
    addons=None,
    user=None,
):
    """Capture a 'Contact for price' lead (listing mode). Anon-allowed.

    When a structured selection (tiers/add-ons/departure) is supplied it is
    snapshotted onto the enquiry so hosts receive a qualified lead — prices are
    never exposed to the client, so a bad selection just yields empty snapshots.
    """
    from plugins.installed.booking_marketplace.models import Enquiry

    if not email:
        raise BookingError('An email is required to enquire.')
    if isinstance(preferred_date, str):
        stamp = preferred_date.strip()
        try:
            preferred_date = datetime.date.fromisoformat(stamp) if stamp else None
        except ValueError:
            preferred_date = None
    if guests in ('', None):
        guests = None
    else:
        try:
            guests = int(guests)
        except (TypeError, ValueError):
            guests = None

    breakdown, addon_snap = [], []
    if tiers or addons:
        try:
            q = price_quote(service, tiers=tiers or {}, addons=addons or {})
            breakdown, addon_snap = q['tier_breakdown'], q['addons']
        except BookingError:
            breakdown, addon_snap = [], []

    enquiry = Enquiry.objects.create(
        service=service,
        customer=user if (user and user.is_authenticated) else None,
        name=name,
        email=email,
        phone=phone,
        preferred_date=preferred_date,
        guests=guests,
        message=message,
        time_slot=time or '',
        tier_breakdown=breakdown,
        addons=addon_snap,
    )
    # Notify host + confirm to guest — best-effort, never breaks capture.
    with contextlib.suppress(Exception):
        from plugins.installed.booking_marketplace.email import notify_enquiry

        notify_enquiry(enquiry)
    return enquiry


def _safe_qty(v) -> int:
    try:
        q = int(v)
    except (TypeError, ValueError):
        raise BookingError('Please enter a valid quantity.') from None
    if q < 0:
        raise BookingError('Quantity cannot be negative.')
    return q


def _addon_lines(service, addons: dict, *, guests: int, currency) -> tuple[Money, list]:
    """Validate the add-on selection and price it. Returns (total, snapshot)."""
    active_addons = {str(a.id): a for a in service.addons.filter(is_active=True)}
    total = Money(0, currency)
    snap = []
    for aid, raw_qty in addons.items():
        addon = active_addons.get(str(aid))
        if addon is None:
            raise BookingError('Unknown add-on selected.')
        qty = _safe_qty(raw_qty)
        if qty == 0:
            continue
        if addon.max_qty and qty > addon.max_qty:
            raise BookingError(f'Up to {addon.max_qty} × {addon.name}.')
        units = qty * guests if addon.price_type == 'per_person' else qty
        total += addon.price * units
        snap.append(
            {
                'addon_id': str(addon.id),
                'name': addon.name,
                'qty': qty,
                'unit_price': str(addon.price.amount),
                'price_type': addon.price_type,
            }
        )
    return total, snap


def price_quote(service, *, tiers: dict, addons: dict) -> dict:
    """Server-derived quote for a booking selection. Single source of truth.

    `tiers` maps PricingTier id → qty; the special key 'guests' uses the service
    flat price (fallback when the service defines no tiers). `addons` maps AddOn
    id → qty. Returns money + JSON snapshots. Raises BookingError on bad input.
    """

    tiers = tiers or {}
    addons = addons or {}
    currency = service.price.currency
    subtotal = Money(0, currency)
    guests = 0
    tier_breakdown = []

    active = {str(t.id): t for t in service.tiers.filter(is_active=True)}
    if active:
        for tid, raw_qty in tiers.items():
            if tid == 'guests':
                continue
            tier = active.get(str(tid))
            if tier is None:
                raise BookingError('Unknown ticket type selected.')
            qty = _safe_qty(raw_qty)
            if qty == 0:
                continue
            if tier.max_qty and qty > tier.max_qty:
                raise BookingError(f'Up to {tier.max_qty} × {tier.name}.')
            subtotal += tier.price * qty
            guests += qty
            tier_breakdown.append(
                {
                    'tier_id': str(tier.id),
                    'name': tier.name,
                    'qty': qty,
                    'unit_price': str(tier.price.amount),
                }
            )
    else:
        guests = _safe_qty(tiers.get('guests', 0))
        if guests == 0:
            raise BookingError('At least one guest is required.')
        subtotal += service.price * guests
        tier_breakdown.append(
            {
                'tier_id': None,
                'name': 'Guest',
                'qty': guests,
                'unit_price': str(service.price.amount),
            }
        )

    if guests < 1:
        raise BookingError('At least one guest is required.')

    addon_total, addon_snap = _addon_lines(service, addons, guests=guests, currency=currency)
    subtotal += addon_total

    fee_amount = (subtotal.amount * SERVICE_FEE_RATE).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )
    fee = Money(fee_amount, currency)
    return {
        'subtotal': subtotal,
        'fee': fee,
        'total': subtotal + fee,
        'guests': guests,
        'tier_breakdown': tier_breakdown,
        'addons': addon_snap,
    }


REVIEWABLE_STATUSES = ('confirmed', 'completed')


def can_review(service, user) -> bool:
    """True if `user` has a confirmed/completed booking for `service`."""
    from plugins.installed.booking_marketplace.models import Booking

    if not (user and getattr(user, 'is_authenticated', False)):
        return False
    return Booking.objects.filter(
        service=service, customer=user, status__in=REVIEWABLE_STATUSES
    ).exists()


def review_summary(service) -> dict:
    """{'avg': float|None, 'count': int} for a service's reviews."""
    agg = service.reviews.aggregate(avg=Avg('rating'), count=Count('id'))
    return {
        'avg': round(agg['avg'], 1) if agg['avg'] is not None else None,
        'count': agg['count'] or 0,
    }


def create_review(service, *, user, rating, title='', body=''):
    """Create/update a guest's review. Gated on a real booking (server-side)."""
    from plugins.installed.booking_marketplace.models import Booking, ServiceReview

    if not (user and getattr(user, 'is_authenticated', False)):
        raise BookingError('Please sign in to review.')
    booking = (
        Booking.objects.filter(service=service, customer=user, status__in=REVIEWABLE_STATUSES)
        .order_by('-booking_date')
        .first()
    )
    if booking is None:
        raise BookingError('Only guests who booked this experience can review it.')
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        raise BookingError('Please choose a rating.') from None
    if not 1 <= rating <= 5:
        raise BookingError('Rating must be between 1 and 5.')

    author = (getattr(user, 'get_full_name', lambda: '')() or '').strip()
    if not author:
        author = getattr(user, 'get_username', lambda: '')() or ''
    review, _ = ServiceReview.objects.update_or_create(
        service=service,
        customer=user,
        defaults={
            'booking': booking,
            'rating': rating,
            'title': (title or '').strip(),
            'body': (body or '').strip(),
            'author_name': author,
        },
    )
    return review
