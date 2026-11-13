"""Markets dashboard — list, create, edit, delete, exchange rates."""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.authz import _forbidden, check, require_capability
from core.pricing import store_currency
from morpheus.app.views import staff_member_required
from plugins.installed.markets import rates
from plugins.installed.markets.models import Market
from plugins.installed.markets.pricing import preview
from plugins.installed.markets.services import delete_market, save_market

logger = logging.getLogger('morpheus.markets.views')

PREVIEW_COUNT = 10


def currency_choices() -> list[tuple[str, str]]:
    """Every currency Babel knows, as (code, "EUR — Euro")."""
    from babel.numbers import get_currency_name, list_currencies

    return [
        (code, f'{code} — {get_currency_name(code, locale="en")}')
        for code in sorted(list_currencies())
    ]


def _rate_status(currency: str) -> dict | None:
    """What the page says about one currency's rate; ``None`` for the store's own."""
    if currency == store_currency():
        return None
    row = rates.rate_row(currency)
    rate, age = row['rate'], row['fetched_at']
    return {
        **row,
        'rate_text': format(rate.quantize(Decimal('0.000001')).normalize(), 'f') if rate else '',
        'age_days': (timezone.now() - age).days if age else None,
    }


@staff_member_required
@require_capability('catalog.read')
def index(request: HttpRequest) -> HttpResponse:
    markets = list(Market.objects.all())
    for m in markets:
        m.rate_status = _rate_status(m.currency.upper())
    return render(
        request,
        'markets/list.html',
        {
            'markets': markets,
            'store_currency': store_currency(),
            'active_nav': 'markets',
        },
    )


def _form_data(post) -> dict:
    return {
        'code': post.get('code', ''),
        'label': post.get('label', ''),
        'currency': post.get('currency', ''),
        'default_locale': post.get('default_locale', 'en'),
        'country_codes': post.get('country_codes', ''),
        'base_price_adjustment_pct': post.get('base_price_adjustment_pct', '0'),
        'rounding': post.get('rounding', 'exact'),
        'is_active': post.get('is_active') == 'on',
        'is_default': post.get('is_default') == 'on',
    }


@staff_member_required
@require_capability('catalog.read')
def market_form(request: HttpRequest, market_id=None) -> HttpResponse:
    market = get_object_or_404(Market, pk=market_id) if market_id else None
    posted = None

    if request.method == 'POST':
        if not check(request.user, 'catalog.write', target=request.path):
            return _forbidden(request, 'catalog.write')
        posted = _form_data(request.POST)
        if market is not None:
            posted['code'] = market.code  # the code never changes
        try:
            saved = save_market(posted, market)
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages))
        else:
            messages.success(request, f'Saved market "{saved.label}".')
            return redirect('markets:edit', market_id=saved.pk)

    currency = (posted or {}).get('currency') or (market.currency if market else 'USD')
    currency = currency.strip().upper()
    values = posted or {
        'label': market.label if market else '',
        'default_locale': market.default_locale if market else 'en',
        'base_price_adjustment_pct': market.base_price_adjustment_pct if market else 0,
        'rounding': market.rounding if market else 'exact',
    }
    ctx = {
        'market': market,
        'values': values,
        'currency_choices': currency_choices(),
        'rounding_choices': Market.ROUNDING_CHOICES,
        'selected_currency': currency,
        'country_codes_str': (
            posted['country_codes'] if posted else ', '.join(market.country_codes) if market else ''
        ),
        'store_currency': store_currency(),
        'active_nav': 'markets',
    }
    if market is not None:
        ctx['rate'] = _rate_status(market.currency.upper())
        ctx['preview'] = preview(market, PREVIEW_COUNT)
    return render(request, 'markets/edit.html', ctx)


@staff_member_required
@require_capability('catalog.write')
@require_POST
def market_delete(request: HttpRequest, market_id) -> HttpResponse:
    market = get_object_or_404(Market, pk=market_id)
    label = market.label
    delete_market(market)
    messages.success(request, f'Deleted market "{label}".')
    return redirect('markets:index')


@staff_member_required
@require_capability('catalog.write')
@require_POST
def rate(request: HttpRequest, market_id) -> HttpResponse:
    """Set (or, with an empty box, clear) the manual rate for the market's currency."""
    market = get_object_or_404(Market, pk=market_id)
    raw = (request.POST.get('rate') or '').strip()
    try:
        if raw:
            try:
                value = Decimal(raw)
            except InvalidOperation:
                raise ValidationError('The rate must be a number.') from None
            rates.set_manual_rate(market.currency, value)
            messages.success(request, f'Saved your rate for {market.currency.upper()}.')
        else:
            rates.set_manual_rate(market.currency, None)
            messages.success(
                request,
                f'Removed your rate for {market.currency.upper()}; the daily rate applies again.',
            )
    except ValidationError as e:
        messages.error(request, ' '.join(e.messages))
    return redirect('markets:edit', market_id=market.pk)


@staff_member_required
@require_capability('catalog.write')
@require_POST
def rates_refresh(request: HttpRequest) -> HttpResponse:
    """Fetch the ECB's rates now."""
    try:
        result = rates.fetch_ecb()
    except Exception as e:  # noqa: BLE001 — shown to the merchant, not a crash
        logger.warning('rate fetch failed: %s', e, exc_info=True)
        messages.error(request, f'Could not fetch the rates just now: {e}')
    else:
        text = f'Fetched {result["written"]} exchange rates dated {result["date"] or "today"}.'
        if result['kept_manual']:
            text += f' Kept your own rate for {", ".join(result["kept_manual"])}.'
        messages.success(request, text)
    target = request.POST.get('next') or ''
    return redirect(target if target.startswith('/dashboard/markets/') else 'markets:index')
