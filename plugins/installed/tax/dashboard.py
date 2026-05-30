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
def regions(request):
    from plugins.installed.tax.models import TaxRegion  # noqa: PLC0415

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        region_id = (request.POST.get('region_id') or '').strip()

        if action == 'create':
            name = (request.POST.get('name') or '').strip()
            country = _norm_country(request.POST.get('country') or '')
            region = _norm_region(request.POST.get('region') or '')
            is_default = bool(request.POST.get('is_default'))
            if not name or not country:
                messages.error(request, 'Name and country are required.')
            else:
                try:
                    TaxRegion.objects.create(
                        name=name,
                        country=country,
                        region=region,
                        is_default=is_default,
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
                name = obj.name
                obj.delete()
                messages.success(request, f'Region "{name}" deleted.')
            except TaxRegion.DoesNotExist:
                messages.error(request, 'Region not found.')

        return HttpResponseRedirect(request.path)

    edit_id = (request.GET.get('edit') or '').strip()
    edit_obj = None
    if edit_id:
        edit_obj = TaxRegion.objects.filter(pk=edit_id).first()

    rows = list(TaxRegion.objects.all().order_by('country', 'region', 'name'))
    return render(
        request,
        'tax/dashboard/regions.html',
        {
            'rows': rows,
            'edit_obj': edit_obj,
            'active_nav': 'tax',
            'breadcrumb_trail': _trail({'label': 'Regions'}),
        },
    )


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
    from plugins.installed.tax.models import TaxCategory, TaxRate, TaxRegion  # noqa: PLC0415

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        rate_id = (request.POST.get('rate_id') or '').strip()
        if action == 'create':
            _create_rate(request)
        elif action == 'edit' and rate_id:
            _edit_rate(request, rate_id)
        elif action == 'delete' and rate_id:
            _delete_rate(request, rate_id)
        return HttpResponseRedirect(request.get_full_path())

    region_filter = (request.GET.get('region') or '').strip()
    qs = TaxRate.objects.select_related('region', 'category')
    if region_filter:
        qs = qs.filter(region_id=region_filter)
    rows = list(qs.order_by('region', 'priority', 'category'))

    edit_id = (request.GET.get('edit') or '').strip()
    edit_obj = TaxRate.objects.filter(pk=edit_id).first() if edit_id else None

    return render(
        request,
        'tax/dashboard/rates.html',
        {
            'rows': rows,
            'regions': list(TaxRegion.objects.all().order_by('country', 'region', 'name')),
            'categories': list(TaxCategory.objects.all().order_by('name')),
            'region_filter': region_filter,
            'edit_obj': edit_obj,
            'active_nav': 'tax',
            'breadcrumb_trail': _trail({'label': 'Rates'}),
        },
    )
