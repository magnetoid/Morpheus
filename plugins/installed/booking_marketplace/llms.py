"""SEO_LLMS_SECTIONS filter subscriber.

seo's `/llms.txt` can only enumerate `catalog.Product`, and this marketplace's
catalogue is `BookableService` (experiences) and `Property` (stays). So the live
file shipped a bare "## Products" heading with nothing under it while 244
bookable listings were in the sitemap — the commercial catalogue was invisible
to exactly the AI crawlers robots.txt goes out of its way to welcome.

Same inversion as `sitemap.py`: the owner answers a filter rather than seo
importing this plugin. Registered with `plugin='booking_marketplace'`
ownership, so the bus skips it while the plugin is disabled.
"""

from __future__ import annotations


def _money(value) -> str:
    """`' — 45.00 EUR'`, or '' for a free/unpriced row.

    Money is a claim a crawler may quote back at a shopper, so an absent or
    zero amount says nothing rather than "0".
    """
    try:
        amount = getattr(value, 'amount', None)
        if amount is None or amount <= 0:
            return ''
        return f' — {amount} {value.currency}'
    except Exception:  # noqa: BLE001
        return ''


def contribute_llms_sections(value, **kwargs):
    """SEO_LLMS_SECTIONS subscriber — appends Experiences + Stays sections."""
    from plugins.installed.booking_marketplace.models import BookableService, Property

    base = (kwargs.get('base') or '').rstrip('/')
    full = bool(kwargs.get('full'))
    limit = 200 if full else 50
    sections = list(value or [])

    experiences = [
        f'- [{svc.name}]({base}/bookings/{svc.slug}/)'
        f'{_money(svc.price)}'
        + (f': {svc.short_description}' if full and svc.short_description else '')
        for svc in BookableService.objects.filter(
            is_active=True, vendor__is_active=True
        ).select_related('vendor')[:limit]
    ]
    if experiences:
        sections.append({'title': 'Experiences', 'lines': experiences})

    stays = [
        f'- [{prop.name}]({base}/hotels/{prop.slug}/)'
        + (f' — {prop.location}' if prop.location else '')
        + (f': {prop.short_description}' if full and prop.short_description else '')
        for prop in Property.objects.filter(is_active=True, vendor__is_active=True).select_related(
            'vendor'
        )[:limit]
    ]
    if stays:
        sections.append({'title': 'Stays', 'lines': stays})

    return sections
