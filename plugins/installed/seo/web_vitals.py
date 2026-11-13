"""Field Core Web Vitals: readings from shoppers' browsers (v0.159.1).

``record()`` keeps one reading from the beacon seo contributes to every theme
(``seo/blocks/web_vitals.html``). ``summary()`` is Google's measure: the 75th
percentile of each metric over the last 28 days. Readings used to be audit-log
rows with no end, crawlers and Lighthouse runs included, and only three themes
sent them.
"""

from __future__ import annotations

from datetime import timedelta

#: Google's window for field data.
WINDOW_DAYS = 28
#: Readings kept per metric per day; a busy store's p75 does not need more.
DAILY_CAP = 5000
#: What a browser can honestly report (anything else is a broken or forged beacon).
_LIMITS = {'LCP': 120_000.0, 'INP': 60_000.0, 'CLS': 50.0}


def device_for(user_agent: str) -> str:
    return 'mobile' if 'mobi' in (user_agent or '').lower() else 'desktop'


def record(*, metric: str, value, path: str = '', user_agent: str = '') -> bool:
    """Store one reading; False when it is not one (a crawler, a bad value, the
    day's cap reached)."""
    from django.core.cache import cache  # noqa: PLC0415

    from core.utils.crawlers import is_crawler_user_agent  # noqa: PLC0415
    from core.utils.site import store_today  # noqa: PLC0415
    from plugins.installed.seo.models import WebVitalSample  # noqa: PLC0415

    metric = (metric or '').upper()
    if metric not in _LIMITS or is_crawler_user_agent(user_agent):
        return False
    try:
        value = float(value)
    except (TypeError, ValueError):
        return False
    if not (0 <= value <= _LIMITS[metric]):
        return False
    day = store_today()
    counter = f'seo:web_vitals:{day.isoformat()}:{metric}'
    cache.add(counter, 0, 60 * 60 * 48)
    try:
        if cache.incr(counter) > DAILY_CAP:
            return False
    except ValueError:  # the counter expired between add and incr
        cache.set(counter, 1, 60 * 60 * 48)
    WebVitalSample.objects.create(
        day=day,
        metric=metric,
        value=value,
        device=device_for(user_agent),
        path=(path or '').split('?', 1)[0][:300],
    )
    return True


def _p75(qs) -> float | None:
    n = qs.count()
    if not n:
        return None
    return qs.order_by('value').values_list('value', flat=True)[int(0.75 * (n - 1))]


def summary(*, device: str = '') -> dict:
    """p75 of each metric over the last 28 days: LCP in seconds, INP in
    milliseconds, CLS unitless (Google's units), and how many readings."""
    from core.utils.site import store_today  # noqa: PLC0415
    from plugins.installed.seo.models import WebVitalSample  # noqa: PLC0415

    since = store_today() - timedelta(days=WINDOW_DAYS - 1)
    base = WebVitalSample.objects.filter(day__gte=since)
    if device:
        base = base.filter(device=device)
    out = {'lcp': None, 'inp': None, 'cls': None, 'samples': base.count()}
    for key, metric in (('lcp', 'LCP'), ('inp', 'INP'), ('cls', 'CLS')):
        p75 = _p75(base.filter(metric=metric))
        if p75 is None:
            continue
        if key == 'lcp':
            out[key] = round(p75 / 1000, 2)
        elif key == 'cls':
            out[key] = round(p75, 3)
        else:
            out[key] = round(p75)
    return out


def prune() -> int:
    """Delete readings older than the window; returns how many."""
    from core.utils.site import store_today  # noqa: PLC0415
    from plugins.installed.seo.models import WebVitalSample  # noqa: PLC0415

    cutoff = store_today() - timedelta(days=WINDOW_DAYS - 1)
    deleted, _ = WebVitalSample.objects.filter(day__lt=cutoff).delete()
    return deleted
