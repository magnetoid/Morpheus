"""The investor page: Montenegro's visitor economy and the marketplace built for it (v0.138.0).

The page states public market figures, each cited in its Sources, and what the
public catalogue lists today, counted live so it never goes stale. It names no
figure from the store's own operations: no bookings, enquiries, revenue or
traffic, and nothing about which steps of the booking flow are switched on
(owner, 2026-11-06). The scenarios multiply public arrivals by a share, the
catalogue's median price and the service fee; they are labelled illustrations.

The copy is the theme's (`booking_marketplace/investors.html`): a store whose theme
ships no investor page answers 404 here. It is shared by link, so it stays out
of the index and the sitemap.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from statistics import median

from babel.numbers import format_compact_currency, format_decimal
from django.http import Http404
from django.shortcuts import render
from django.template import TemplateDoesNotExist
from django.template.loader import select_template
from django.utils.translation import get_language, gettext

from plugins.installed.booking_marketplace.services import SERVICE_FEE_RATE, live_regions

TEMPLATE = 'booking_marketplace/investors.html'

# MONSTAT, "Arrivals and overnight stays of tourists, total, 2025" (source 1 on the page).
ARRIVALS_2025 = 2_728_564
SCENARIO_SHARES = (Decimal('0.01'), Decimal('0.03'), Decimal('0.05'))
# Used only while the catalogue has no priced experience.
FALLBACK_PRICE = Decimal('60')


def _locale() -> str:
    # Babel's Latin-script Montenegrin, as search_page.date_label: Django's own
    # `sr` catalog is Cyrillic.
    return 'sr_Latn_ME' if (get_language() or '').startswith('sr') else 'en'


def _catalogue() -> dict:
    from plugins.installed.booking_marketplace.models import BookableService, Property

    experiences = BookableService.objects.filter(
        is_active=True, vendor__is_active=True, listing_kind='experience'
    )
    # The same filter as the stays index (stay_views.stays_index).
    stays = Property.objects.filter(is_active=True, vendor__is_active=True)
    prices = [p for p in experiences.values_list('price', flat=True) if p and p > 0]
    # A host is anyone with a public experience or stay; a guesthouse with no
    # experience is still a host on the site.
    hosts = set(experiences.values_list('vendor_id', flat=True))
    hosts |= set(stays.values_list('vendor_id', flat=True))
    return {
        'experiences': experiences.count(),
        'stays': stays.count(),
        'regions': len(live_regions()),
        'hosts': len(hosts),
        'median_price': Decimal(median(prices)) if prices else FALLBACK_PRICE,
    }


def _scenarios(price: Decimal, locale: str) -> list[dict]:
    rows = []
    for share in SCENARIO_SHARES:
        guests = int((ARRIVALS_2025 * share).quantize(Decimal('1'), ROUND_HALF_UP))
        value = guests * price
        fee = value * SERVICE_FEE_RATE
        rows.append(
            {
                'share': format_decimal(share * 100, format='0', locale=locale) + '%',
                'guests': format_decimal(guests, locale=locale),
                'value': format_compact_currency(value, 'EUR', locale=locale, fraction_digits=1),
                'fee': format_compact_currency(fee, 'EUR', locale=locale, fraction_digits=1),
            }
        )
    return rows


def investors(request):
    try:
        template = select_template([TEMPLATE])
    except TemplateDoesNotExist:
        raise Http404 from None

    locale = _locale()
    catalogue = _catalogue()
    price = catalogue['median_price'].quantize(Decimal('1'), ROUND_HALF_UP)
    fee_pct = int(SERVICE_FEE_RATE * 100)
    return render(
        request,
        template.template.name,
        {
            'catalogue': catalogue,
            'median_price': format_compact_currency(price, 'EUR', locale=locale),
            'median_price_value': int(price),
            'fee_pct': fee_pct,
            'arrivals': ARRIVALS_2025,
            'scenarios': _scenarios(price, locale),
            'number_locale': 'sr-Latn-ME' if locale.startswith('sr') else 'en',
            'breadcrumb_items': [
                {'name': gettext('Home'), 'url': request.build_absolute_uri('/')},
                {'name': gettext('Investors'), 'url': request.build_absolute_uri(request.path)},
            ],
            'seo_title': gettext('Investors'),
            'seo_description': gettext(
                'Montenegro Experience: the marketplace for the country’s experiences, '
                'stays and local products, and the market it serves.'
            ),
            'seo_og_type': 'website',
            # Shared with investors by link; travellers have no reason to land here.
            'seo_noindex_reason': 'investor page, shared by link',
        },
    )
