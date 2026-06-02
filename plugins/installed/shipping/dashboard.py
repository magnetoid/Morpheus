"""Shipping dashboard pages (admin-only).

Minimal CRUD over ShippingZone and ShippingRate so merchants don't have
to drop into the Django admin to edit their rates. Model layer untouched.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseRedirect
from django.shortcuts import render

logger = logging.getLogger('morpheus.shipping')


def _trail(*items):
    trail = [
        {'label': 'Dashboard', 'url': '/dashboard/'},
        {'label': 'Shipping', 'url': '/dashboard/shipping/zones/'},
    ]
    for item in items:
        trail.append(item if isinstance(item, dict) else {'label': str(item)})
    return trail


def _parse_csv(raw: str) -> list[str]:
    """Split 'US, CA, *' into ['US', 'CA', '*']."""
    return [p.strip().upper() for p in (raw or '').split(',') if p.strip()]


def _create_zone(request) -> None:
    from plugins.installed.shipping.models import ShippingZone  # noqa: PLC0415

    name = (request.POST.get('name') or '').strip()
    if not name:
        messages.error(request, 'Zone name is required.')
        return
    try:
        ShippingZone.objects.create(
            name=name,
            countries=_parse_csv(request.POST.get('countries') or ''),
            regions=_parse_csv(request.POST.get('regions') or ''),
            is_default=bool(request.POST.get('is_default')),
        )
        messages.success(request, f'Zone "{name}" created.')
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f'Could not create zone: {exc}')


def _edit_zone(request, zone_id: str) -> None:
    from plugins.installed.shipping.models import ShippingZone  # noqa: PLC0415

    try:
        obj = ShippingZone.objects.get(pk=zone_id)
        obj.name = (request.POST.get('name') or obj.name).strip()
        obj.countries = _parse_csv(request.POST.get('countries') or '')
        obj.regions = _parse_csv(request.POST.get('regions') or '')
        obj.is_default = bool(request.POST.get('is_default'))
        obj.save()
        messages.success(request, f'Zone "{obj.name}" updated.')
    except ShippingZone.DoesNotExist:
        messages.error(request, 'Zone not found.')
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f'Could not save zone: {exc}')


def _delete_zone(request, zone_id: str) -> None:
    from plugins.installed.shipping.models import ShippingZone  # noqa: PLC0415

    try:
        obj = ShippingZone.objects.get(pk=zone_id)
        name = obj.name
        obj.delete()
        messages.success(request, f'Zone "{name}" deleted.')
    except ShippingZone.DoesNotExist:
        messages.error(request, 'Zone not found.')


@staff_member_required
def zones(request):
    """Unified Shipping settings — zones + rates on ONE page (ADR 0003: no
    duplicate settings surfaces; the merge lives in the owning plugin). Kept at
    the existing `zones` URL/name; the `rates` URL redirects here.
    """
    from plugins.installed.shipping.models import ShippingRate, ShippingZone  # noqa: PLC0415

    if request.method == 'POST':
        kind = (request.POST.get('kind') or '').strip()
        action = (request.POST.get('action') or '').strip()
        if kind == 'zone':
            zid = (request.POST.get('zone_id') or '').strip()
            if action == 'create':
                _create_zone(request)
            elif action == 'edit' and zid:
                _edit_zone(request, zid)
            elif action == 'delete' and zid:
                _delete_zone(request, zid)
        elif kind == 'rate':
            rid = (request.POST.get('rate_id') or '').strip()
            if action == 'create':
                _create_rate(request)
            elif action == 'edit' and rid:
                _edit_rate(request, rid)
            elif action == 'delete' and rid:
                _delete_rate(request, rid)
        return HttpResponseRedirect(request.get_full_path())

    edit_kind = (request.GET.get('edit_kind') or '').strip()
    edit_id = (request.GET.get('edit') or '').strip()
    edit_zone = (
        ShippingZone.objects.filter(pk=edit_id).first()
        if (edit_kind == 'zone' and edit_id)
        else None
    )
    edit_rate = (
        ShippingRate.objects.filter(pk=edit_id).first()
        if (edit_kind == 'rate' and edit_id)
        else None
    )
    zone_filter = (request.GET.get('zone') or '').strip()
    rate_qs = ShippingRate.objects.select_related('zone')
    if zone_filter:
        rate_qs = rate_qs.filter(zone_id=zone_filter)
    zone_rows = list(ShippingZone.objects.all().order_by('name'))
    return render(
        request,
        'shipping/dashboard/shipping.html',
        {
            'zones': zone_rows,
            'zone_rows': zone_rows,
            'rate_rows': list(rate_qs.order_by('zone', 'priority', 'name')),
            'computation_choices': ShippingRate.COMPUTATION_CHOICES,
            'zone_filter': zone_filter,
            'edit_zone': edit_zone,
            'edit_rate': edit_rate,
            'active_nav': 'shipping',
            'breadcrumb_trail': _trail({'label': 'Shipping'}),
        },
    )


def _create_rate(request) -> None:
    from plugins.installed.shipping.models import ShippingRate  # noqa: PLC0415

    name = (request.POST.get('name') or '').strip()
    zone_id = (request.POST.get('zone') or '').strip()
    if not name or not zone_id:
        messages.error(request, 'Name and zone are required.')
        return
    try:
        flat_raw = (request.POST.get('flat_amount') or '').strip()
        ShippingRate.objects.create(
            zone_id=zone_id,
            name=name,
            description=(request.POST.get('description') or '').strip(),
            computation=(request.POST.get('computation') or 'flat').strip(),
            flat_amount=Decimal(flat_raw) if flat_raw else None,
            is_active=bool(request.POST.get('is_active')),
            priority=int((request.POST.get('priority') or '50').strip() or 50),
        )
        messages.success(request, f'Rate "{name}" created.')
    except (InvalidOperation, ValueError):
        messages.error(request, 'Flat amount must be a decimal; priority must be an integer.')
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f'Could not create rate: {exc}')


def _edit_rate(request, rate_id: str) -> None:
    from plugins.installed.shipping.models import ShippingRate  # noqa: PLC0415

    try:
        obj = ShippingRate.objects.get(pk=rate_id)
        obj.name = (request.POST.get('name') or obj.name).strip()
        zone_id = (request.POST.get('zone') or '').strip()
        if zone_id:
            obj.zone_id = zone_id
        obj.description = (request.POST.get('description') or '').strip()
        comp = (request.POST.get('computation') or '').strip()
        if comp:
            obj.computation = comp
        flat_raw = (request.POST.get('flat_amount') or '').strip()
        if flat_raw:
            obj.flat_amount = Decimal(flat_raw)
        obj.is_active = bool(request.POST.get('is_active'))
        pr = (request.POST.get('priority') or '').strip()
        if pr:
            obj.priority = int(pr)
        obj.save()
        messages.success(request, f'Rate "{obj.name}" updated.')
    except ShippingRate.DoesNotExist:
        messages.error(request, 'Rate not found.')
    except (InvalidOperation, ValueError):
        messages.error(request, 'Flat amount must be a decimal; priority must be an integer.')
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f'Could not save rate: {exc}')


def _delete_rate(request, rate_id: str) -> None:
    from plugins.installed.shipping.models import ShippingRate  # noqa: PLC0415

    try:
        obj = ShippingRate.objects.get(pk=rate_id)
        name = obj.name
        obj.delete()
        messages.success(request, f'Rate "{name}" deleted.')
    except ShippingRate.DoesNotExist:
        messages.error(request, 'Rate not found.')


@staff_member_required
def rates(request):
    """Back-compat redirect: rates merged into the unified Shipping page
    (ADR 0003 — one settings surface per domain)."""
    zone = (request.GET.get('zone') or '').strip()
    base = '/dashboard/shipping/zones/'
    return HttpResponseRedirect(f'{base}?zone={zone}#rates' if zone else f'{base}#rates')
