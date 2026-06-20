"""Booking slot computation — turn weekly availability into concrete slots."""

from __future__ import annotations

import datetime

from django.utils import timezone


def upcoming_slots(service, *, days: int = 14, limit: int = 40) -> list[datetime.datetime]:
    """Concrete bookable start times for the next `days`, excluding ones already
    booked (pending/confirmed). Derived from the service's AvailabilityWindows
    and duration. Returns aware datetimes, soonest first."""
    now = timezone.localtime()
    windows: dict[int, list[tuple]] = {}
    for w in service.availability.all():
        windows.setdefault(w.weekday, []).append((w.start_time, w.end_time))
    if not windows:
        return []

    booked = {
        timezone.localtime(b.start_at).replace(second=0, microsecond=0)
        for b in service.bookings.filter(status__in=['pending', 'confirmed'], start_at__gte=now)
    }
    dur = datetime.timedelta(minutes=service.duration_minutes or 60)
    slots: list[datetime.datetime] = []
    for d in range(days):
        date = (now + datetime.timedelta(days=d)).date()
        for start_t, end_t in windows.get(date.weekday(), []):
            cursor = timezone.make_aware(datetime.datetime.combine(date, start_t))
            window_end = timezone.make_aware(datetime.datetime.combine(date, end_t))
            while cursor + dur <= window_end:
                norm = cursor.replace(second=0, microsecond=0)
                if cursor > now and norm not in booked:
                    slots.append(cursor)
                    if len(slots) >= limit:
                        return slots
                cursor += dur
    return slots
