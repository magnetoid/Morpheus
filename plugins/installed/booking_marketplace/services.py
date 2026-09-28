"""Booking marketplace — server-side trusted operations.

All money + capacity logic lives here, never in views/templates/client:
- `available_dates` lists bookable dates (weekday availability − full days).
- `create_booking` derives subtotal/fee/total, checks capacity under a row
  lock, and sets status. Mirrors the reference site's create_booking RPC.
- `submit_enquiry` captures a "Contact for price" lead (listing mode).
"""

from __future__ import annotations

import datetime
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from djmoney.money import Money

SERVICE_FEE_RATE = Decimal('0.12')  # 12% platform fee (matches reference)
ACTIVE_STATUSES = ('pending', 'confirmed')


class BookingError(ValueError):
    """Raised when a booking can't be made (bad input / no capacity)."""


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
    """Upcoming dates with remaining capacity, soonest first.

    Derived from `available_sessions`: capacity is per departure, so a date
    stays bookable while any departure has a seat, and its `remaining` is the
    seats left across the day's departures.
    """
    return [
        {'date': s['date'], 'remaining': sum(t['remaining'] for t in s['times'])}
        for s in available_sessions(service, days=days, limit=limit)
    ]


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
def create_booking(  # noqa: PLR0912 — one branch per validated booking field
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
        try:
            guests = int(guests)
        except (TypeError, ValueError):
            raise BookingError('Please enter a valid number of guests.') from None
        if guests < 1:
            raise BookingError('At least one guest is required.')
        quote = price_quote(svc, tiers={'guests': guests}, addons={})
    # The party cap holds however the party was counted — tier quantities too.
    if svc.max_guests_per_booking and guests > svc.max_guests_per_booking:
        raise BookingError(f'Up to {svc.max_guests_per_booking} guests per booking.')

    if isinstance(booking_date, str):
        try:
            booking_date = datetime.date.fromisoformat(booking_date)
        except ValueError:
            raise BookingError('Please choose a valid date.') from None
    if booking_date < timezone.localdate():
        raise BookingError('That date has already passed.')
    if booking_date.weekday() not in _weekdays(svc):
        raise BookingError('This experience does not run on that day.')

    # If the experience runs at fixed departure times, a booking must name one
    # of them — never trust a client-supplied slot that was never offered, and
    # never take one with no slot (no per-departure count would include it).
    starts = _start_times(svc)
    if starts != [None] and time not in starts:
        raise BookingError('Please choose an available departure time.')

    # Without fixed departures the capacity is the whole day's: a client-sent
    # time is only a label, never a separate pool of seats.
    slot = time if starts != [None] else None
    remaining = (svc.daily_capacity or 0) - booked_guests(svc, booking_date, slot)
    if guests > remaining:
        raise BookingError(
            f'Only {remaining} spot(s) left on that date.'
            if remaining > 0
            else 'That date is fully booked.'
        )

    if not (name and email):
        raise BookingError('Your name and email are required.')

    booking = Booking.objects.create(
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
    from plugins.installed.booking_marketplace.email import notify_booking

    transaction.on_commit(lambda: notify_booking(booking))
    return booking


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
            # A ticket-tier form sends no `guests` field: its party is the
            # sum of the tier quantities, which the quote already counted.
            if guests is None:
                guests = q['guests']
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
    try:
        from plugins.installed.booking_marketplace.email import notify_enquiry

        notify_enquiry(enquiry)
    except Exception:  # noqa: BLE001, S110 — best-effort notify; never block the enquiry
        pass
    return enquiry


def _safe_qty(v) -> int:
    try:
        q = int(v)
    except (TypeError, ValueError):
        raise BookingError('Please enter a valid quantity.') from None
    if q < 0:
        raise BookingError('Quantity cannot be negative.')
    return q


def price_quote(service, *, tiers: dict, addons: dict) -> dict:  # noqa: PLR0912 — one branch per priceable component
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

    active_addons = {str(a.id): a for a in service.addons.filter(is_active=True)}
    addon_snap = []
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
        subtotal += addon.price * units
        addon_snap.append(
            {
                'addon_id': str(addon.id),
                'name': addon.name,
                'qty': qty,
                'unit_price': str(addon.price.amount),
                'price_type': addon.price_type,
            }
        )

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


def _verified(prefix: str = '') -> Q:
    """The booking is the evidence a review is a guest's: `create_review`
    refuses to write one without a confirmed/completed booking, and
    `seed_reviews` writes rows with none. `prefix` applies the same rule
    across the relation, for a listing's annotation."""
    return Q(**{f'{prefix}booking__isnull': False})


def verified_reviews(service):
    """The reviews a public claim may rest on.

    Structured data — the experience page's Product node, `/ai/products.json`
    — states a rating to Google and AI crawlers as fact. The denormalised
    `rating`/`review_count` columns cannot back that: `seed_reviews` and
    `create_review` both sync them over *every* row, seeded or real. Showing
    a review on the page is the merchant's content; claiming it in markup is
    ours, and Google requires it to come from a real customer.
    """
    return service.reviews.filter(_verified())


def with_verified_rating(qs):
    """Annotate `verified_count` / `verified_avg` on a BookableService
    queryset — one query for a whole listing instead of one per row."""
    rule = _verified('reviews__')
    return qs.annotate(
        verified_count=Count('reviews', filter=rule),
        verified_avg=Avg('reviews__rating', filter=rule),
    )


def verified_rating(service) -> tuple[int, float | None]:
    """(count, average) over `verified_reviews` — the only rating structured
    data may state. Reads a `with_verified_rating` annotation when present."""
    if hasattr(service, 'verified_count'):
        return service.verified_count or 0, service.verified_avg
    agg = verified_reviews(service).aggregate(n=Count('id'), avg=Avg('rating'))
    return agg['n'] or 0, agg['avg']


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
    # Keep the denormalised fields in sync the same way seed_reviews does —
    # otherwise a live review never moves the storefront's rating/count.
    agg = service.reviews.aggregate(n=Count('id'), avg=Avg('rating'))
    type(service).objects.filter(pk=service.pk).update(
        review_count=agg['n'] or 0,
        rating=round(agg['avg'] or 0, 1),
    )
    return review


def active_categories():
    """Categories that currently have ≥1 active experience, with counts.

    The single source for every category surface on the storefront (home
    band, hero pills, filter chips, nav mega-menu) so the front can never
    drift from the catalog. Fails soft to [] on a fresh/mid-migration DB.
    """
    try:
        from django.db.models import Count, Q

        from plugins.installed.catalog.models import Category

        rows = (
            Category.objects.annotate(
                svc_count=Count(
                    'bookable_services',
                    filter=Q(
                        bookable_services__is_active=True,
                        bookable_services__vendor__is_active=True,
                        bookable_services__listing_kind='experience',
                    ),
                )
            )
            .filter(is_active=True, svc_count__gt=0)
            .order_by('-svc_count', 'name')
        )
        return [{'name': c.name, 'count': c.svc_count} for c in rows]
    except Exception:  # noqa: BLE001 — table missing / not migrated yet
        return []
