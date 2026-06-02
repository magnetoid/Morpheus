"""Tax dashboard pages (admin-only).

Minimal CRUD over TaxRegion and TaxRate so merchants don't have to drop
into the Django admin (or call agent tools) to edit their rates. Keeps
the model layer untouched — this is pure UI on top.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseRedirect
from django.shortcuts import render

logger = logging.getLogger('morpheus.tax')


def _trail(*items):
    trail = [
        {'label': 'Dashboard', 'url': '/dashboard/'},
        {'label': 'Tax', 'url': '/dashboard/tax/regions/'},
    ]
    for item in items:
        trail.append(item if isinstance(item, dict) else {'label': str(item)})
    return trail


def _norm_country(raw: str) -> str:
    return (raw or '').strip().upper()[:2]


def _norm_region(raw: str) -> str:
    return (raw or '').strip().upper()[:10]


@staff_member_required
def regions(request):  # noqa: PLR0912, PLR0915 — flat region+rate dispatch view
    """Unified Tax settings — regions + rates on ONE page (ADR 0003: no
    duplicate settings surfaces; the merge lives in the owning plugin). Kept at
    the existing `regions` URL/name; the `rates` URL redirects here.
    """
    from plugins.installed.tax.models import (  # noqa: PLC0415
        TaxCategory,
        TaxConfiguration,
        TaxRate,
        TaxRegion,
    )

    if request.method == 'POST':
        kind = (request.POST.get('kind') or '').strip()
        action = (request.POST.get('action') or '').strip()
        if kind == 'region':
            region_id = (request.POST.get('region_id') or '').strip()
            if action == 'create':
                name = (request.POST.get('name') or '').strip()
                country = _norm_country(request.POST.get('country') or '')
                region = _norm_region(request.POST.get('region') or '')
                if not name or not country:
                    messages.error(request, 'Name and country are required.')
                else:
                    try:
                        TaxRegion.objects.create(
                            name=name,
                            country=country,
                            region=region,
                            is_default=bool(request.POST.get('is_default')),
                        )
                        messages.success(request, f'Region "{name}" created.')
                    except Exception as exc:  # noqa: BLE001
                        messages.error(request, f'Could not create region: {exc}')
            elif action == 'edit' and region_id:
                try:
                    obj = TaxRegion.objects.get(pk=region_id)
                    obj.name = (request.POST.get('name') or obj.name).strip()
                    obj.country = _norm_country(request.POST.get('country') or obj.country)
                    obj.region = _norm_region(request.POST.get('region') or '')
                    obj.is_default = bool(request.POST.get('is_default'))
                    obj.save()
                    messages.success(request, f'Region "{obj.name}" updated.')
                except TaxRegion.DoesNotExist:
                    messages.error(request, 'Region not found.')
                except Exception as exc:  # noqa: BLE001
                    messages.error(request, f'Could not save region: {exc}')
            elif action == 'delete' and region_id:
                try:
                    obj = TaxRegion.objects.get(pk=region_id)
                    nm = obj.name
                    obj.delete()
                    messages.success(request, f'Region "{nm}" deleted.')
                except TaxRegion.DoesNotExist:
                    messages.error(request, 'Region not found.')
        elif kind == 'rate':
            rate_id = (request.POST.get('rate_id') or '').strip()
            if action == 'create':
                _create_rate(request)
            elif action == 'edit' and rate_id:
                _edit_rate(request, rate_id)
            elif action == 'delete' and rate_id:
                _delete_rate(request, rate_id)
        elif kind == 'config':
            _save_config(request)
        return HttpResponseRedirect(request.get_full_path())

    edit_kind = (request.GET.get('edit_kind') or '').strip()
    edit_id = (request.GET.get('edit') or '').strip()
    edit_region = (
        TaxRegion.objects.filter(pk=edit_id).first()
        if (edit_kind == 'region' and edit_id)
        else None
    )
    edit_rate = (
        TaxRate.objects.filter(pk=edit_id).first() if (edit_kind == 'rate' and edit_id) else None
    )
    region_filter = (request.GET.get('region') or '').strip()
    rate_qs = TaxRate.objects.select_related('region', 'category')
    if region_filter:
        rate_qs = rate_qs.filter(region_id=region_filter)
    region_rows = list(TaxRegion.objects.all().order_by('country', 'region', 'name'))
    return render(
        request,
        'tax/dashboard/tax.html',
        {
            'region_rows': region_rows,
            'regions': region_rows,
            'rate_rows': list(rate_qs.order_by('region', 'priority', 'category')),
            'categories': list(TaxCategory.objects.all().order_by('name')),
            'region_filter': region_filter,
            'edit_region': edit_region,
            'edit_rate': edit_rate,
            'tax_config': TaxConfiguration.objects.first(),
            'active_nav': 'tax',
            'breadcrumb_trail': _trail({'label': 'Tax'}),
        },
    )


def _save_config(request) -> None:
    from plugins.installed.tax.models import TaxConfiguration  # noqa: PLC0415

    config = TaxConfiguration.objects.first() or TaxConfiguration()
    provider = (request.POST.get('provider') or 'local').strip()
    config.provider = provider if provider in {'local', 'stripe', 'none'} else 'local'
    config.prices_include_tax = bool(request.POST.get('prices_include_tax'))
    region_id = (request.POST.get('default_region') or '').strip()
    config.default_region_id = region_id or None
    try:
        config.save()
        messages.success(request, 'Tax settings saved.')
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f'Could not save tax settings: {exc}')


def _create_rate(request) -> None:
    from plugins.installed.tax.models import TaxRate  # noqa: PLC0415

    name = (request.POST.get('name') or '').strip()
    region_id = (request.POST.get('region') or '').strip()
    rate_percent_raw = (request.POST.get('rate_percent') or '').strip()
    if not name or not region_id or not rate_percent_raw:
        messages.error(request, 'Name, region, and rate are required.')
        return
    try:
        TaxRate.objects.create(
            name=name,
            region_id=region_id,
            category_id=(request.POST.get('category') or '').strip() or None,
            rate_percent=Decimal(rate_percent_raw),
            is_compound=bool(request.POST.get('is_compound')),
            priority=int((request.POST.get('priority') or '0').strip() or 0),
        )
        messages.success(request, f'Rate "{name}" created.')
    except (InvalidOperation, ValueError):
        messages.error(request, 'Rate must be a decimal; priority must be an integer.')
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f'Could not create rate: {exc}')


def _edit_rate(request, rate_id: str) -> None:
    from plugins.installed.tax.models import TaxRate  # noqa: PLC0415

    try:
        obj = TaxRate.objects.get(pk=rate_id)
        obj.name = (request.POST.get('name') or obj.name).strip()
        region_id = (request.POST.get('region') or '').strip()
        if region_id:
            obj.region_id = region_id
        obj.category_id = (request.POST.get('category') or '').strip() or None
        rp = (request.POST.get('rate_percent') or '').strip()
        if rp:
            obj.rate_percent = Decimal(rp)
        obj.is_compound = bool(request.POST.get('is_compound'))
        pr = (request.POST.get('priority') or '').strip()
        if pr:
            obj.priority = int(pr)
        obj.save()
        messages.success(request, f'Rate "{obj.name}" updated.')
    except TaxRate.DoesNotExist:
        messages.error(request, 'Rate not found.')
    except (InvalidOperation, ValueError):
        messages.error(request, 'Rate must be a decimal; priority must be an integer.')
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f'Could not save rate: {exc}')


def _delete_rate(request, rate_id: str) -> None:
    from plugins.installed.tax.models import TaxRate  # noqa: PLC0415

    try:
        obj = TaxRate.objects.get(pk=rate_id)
        name = obj.name
        obj.delete()
        messages.success(request, f'Rate "{name}" deleted.')
    except TaxRate.DoesNotExist:
        messages.error(request, 'Rate not found.')


@staff_member_required
def rates(request):
    """Back-compat redirect: rates merged into the unified Tax page (ADR 0003)."""
    region = (request.GET.get('region') or '').strip()
    base = '/dashboard/tax/regions/'
    return HttpResponseRedirect(f'{base}?region={region}#rates' if region else f'{base}#rates')
