"""dynamics — anonymous, PII-free visitor segmentation for the bandit.

A segment is a coarse ``device : day-part : auth-state`` bucket derived entirely
from the request (no cookies, no stored profile, no PII). The same visitor maps
to the same bandit arms within a day-part, keeping the bandit "semi-personalized"
— a few dozen segments, each with enough feedback to actually learn, which the
research flags as the sweet spot for a lean stack (full per-user personalization
starves each arm). The nightly rebuild derives the identical segment from an
AnalyticsSession + event timestamp via ``segment_of`` so serve-time and training
agree.
"""

from __future__ import annotations


def _daypart(hour: int) -> str:
    if hour < 5 or hour >= 22:  # noqa: PLR2004 — 22:00–04:59
        return 'night'
    if hour < 12:  # noqa: PLR2004
        return 'morning'
    if hour < 17:  # noqa: PLR2004
        return 'afternoon'
    return 'evening'


def _device_from_ua(ua: str) -> str:
    ua = (ua or '').lower()
    if 'ipad' in ua or 'tablet' in ua:
        return 'tablet'
    if 'mobile' in ua or 'android' in ua or 'iphone' in ua:
        return 'mobile'
    return 'desktop'


def segment_for(request) -> str:
    """Serve-time segment for the visitor behind ``request`` — 'device:daypart:auth'."""
    from django.utils import timezone

    ua = request.META.get('HTTP_USER_AGENT', '') if request is not None else ''
    hour = timezone.localtime(timezone.now()).hour
    authed = bool(getattr(getattr(request, 'user', None), 'is_authenticated', False))
    return segment_of(_device_from_ua(ua), hour, authed)


def segment_of(device: str, hour: int, authed: bool) -> str:
    """Segment from explicit parts — used by the nightly rebuild to bucket a
    historical AnalyticsEvent exactly the way serve-time does."""
    dev = device if device in ('mobile', 'tablet', 'desktop') else 'desktop'
    return f'{dev}:{_daypart(hour)}:{"known" if authed else "anon"}'
