"""Markets dashboard — list, create, edit, delete."""

from __future__ import annotations

import logging

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from morpheus.app.views import staff_member_required
from plugins.installed.markets.models import Market

logger = logging.getLogger('morpheus.markets.views')


@staff_member_required
def index(request: HttpRequest) -> HttpResponse:
    markets = list(Market.objects.all())
    return render(
        request,
        'markets/list.html',
        {
            'markets': markets,
            'active_nav': 'markets',
        },
    )


@staff_member_required
def market_form(request: HttpRequest, market_id=None) -> HttpResponse:
    market = get_object_or_404(Market, pk=market_id) if market_id else None

    if request.method == 'POST':
        code = (request.POST.get('code') or '').strip().lower()[:40]
        label = (request.POST.get('label') or '').strip()[:120]
        currency = (request.POST.get('currency') or '').strip().upper()[:3]
        default_locale = (request.POST.get('default_locale') or 'en').strip()[:10]
        countries_raw = (request.POST.get('country_codes') or '').strip()
        country_codes = [
            c.strip().upper()[:2] for c in countries_raw.replace('\n', ',').split(',') if c.strip()
        ]
        adj_raw = (request.POST.get('base_price_adjustment_pct') or '0').strip()
        try:
            from decimal import Decimal

            adj = Decimal(adj_raw)
        except Exception:  # noqa: BLE001
            adj = 0
        is_active = request.POST.get('is_active') == 'on'
        is_default = request.POST.get('is_default') == 'on'

        if not (code and label and currency):
            messages.error(request, 'Code, label, and currency are required.')
        else:
            data = {
                'code': code,
                'label': label,
                'currency': currency,
                'default_locale': default_locale,
                'country_codes': country_codes,
                'base_price_adjustment_pct': adj,
                'is_active': is_active,
                'is_default': is_default,
            }
            try:
                if market is None:
                    market = Market.objects.create(**data)
                else:
                    for k, v in data.items():
                        setattr(market, k, v)
                    market.save()
                # Only one default at a time — clear the flag elsewhere.
                if is_default:
                    Market.objects.exclude(pk=market.pk).update(is_default=False)
                messages.success(request, f'Saved market "{market.label}".')
                return redirect('markets:index')
            except Exception as e:  # noqa: BLE001
                logger.warning('market save failed: %s', e, exc_info=True)
                messages.error(request, f'Save failed: {e}')

    return render(
        request,
        'markets/edit.html',
        {
            'market': market,
            'country_codes_str': ', '.join(market.country_codes) if market else '',
            'active_nav': 'markets',
        },
    )


@staff_member_required
def market_delete(request: HttpRequest, market_id) -> HttpResponse:
    market = get_object_or_404(Market, pk=market_id)
    if request.method == 'POST':
        label = market.label
        market.delete()
        messages.success(request, f'Deleted market "{label}".')
    return redirect('markets:index')
