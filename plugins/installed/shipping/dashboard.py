"""Shipping dashboard pages (admin-only).

Minimal CRUD over ShippingZone and ShippingRate so merchants don't have
to drop into the Django admin to edit their rates. Model layer untouched.
"""

from __future__ import annotations

import json
import logging

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.authz import require_capability
from morpheus.app import dashboard_trail

logger = logging.getLogger('morpheus.shipping')

# Tier rows the rate form shows: the rate's own, then blanks up to this many.
MIN_TIER_ROWS = 4


def _trail(*items):
    return dashboard_trail('Shipping', '/dashboard/shipping/zones/', *items)


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


def _load_config() -> dict:
    """Carrier config as the quote path sees it (PluginConfig.config)."""
    from plugins.installed.shipping.services import _shipping_config  # noqa: PLC0415

    return _shipping_config()


def _save_config(request) -> None:
    """Persist carrier credentials + the tax-on-shipping flag to the shipping
    plugin's PluginConfig.config — the same dict services.quote_rate reads.
    Folds the old SettingsPanel into the page (ADR 0003)."""
    from plugins.registry import app_registry  # noqa: PLC0415

    instance = app_registry.get('shipping')
    if instance is None:
        messages.error(request, 'Shipping plugin unavailable.')
        return
    # Validate the JSON origin addresses up front so a bad paste can't half-save.
    addresses: dict[str, dict] = {}
    for field in ('shippo_default_address', 'easypost_default_address'):
        raw = (request.POST.get(field) or '').strip()
        if not raw:
            addresses[field] = {}
            continue
        try:
            parsed = json.loads(raw)
        except ValueError:
            messages.error(request, f'{field.replace("_", " ")}: must be valid JSON.')
            return
        if not isinstance(parsed, dict):
            messages.error(request, f'{field.replace("_", " ")}: must be a JSON object.')
            return
        addresses[field] = parsed
    # The keys are write-only: the page never shows them, so a blank field
    # keeps the saved key and only a ticked box removes it.
    for key in ('shippo_api_key', 'easypost_api_key'):
        typed = (request.POST.get(key) or '').strip()
        if typed:
            instance.set_config(key, typed)
        elif request.POST.get(f'clear_{key}'):
            instance.set_config(key, '')
    for field, val in addresses.items():
        instance.set_config(field, val)
    messages.success(request, 'Carrier settings saved.')


@staff_member_required
@require_capability('shipping.write')
def zones(request):
    """Unified Shipping settings — zones + rates on ONE page (ADR 0003: no
    duplicate settings surfaces; the merge lives in the owning plugin). Kept at
    the existing `zones` URL/name; the `rates` URL redirects here.
    """
    from plugins.installed.shipping.models import ShippingRate, ShippingZone  # noqa: PLC0415
    from plugins.installed.shipping.rates import (  # noqa: PLC0415
        MAX_TIERS,
        describe,
        store_currency,
    )

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
        elif kind == 'config':
            _save_config(request)
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
    rate_rows = list(rate_qs.order_by('zone', 'priority', 'name'))
    for row in rate_rows:
        row.charges = describe(row)
    tiers = list(edit_rate.tiers or []) if edit_rate else []
    tier_rows = tiers + [{}] * max(MIN_TIER_ROWS - len(tiers), 1)
    cfg = _load_config()
    return render(
        request,
        'shipping/dashboard/shipping.html',
        {
            'zones': zone_rows,
            'zone_rows': zone_rows,
            'rate_rows': rate_rows,
            'computation_choices': ShippingRate.COMPUTATION_CHOICES,
            'tier_rows': tier_rows[:MAX_TIERS],
            'store_currency': store_currency(),
            'zone_filter': zone_filter,
            'edit_zone': edit_zone,
            'edit_rate': edit_rate,
            'shipping_config': cfg,
            'shippo_address_json': (
                json.dumps(cfg.get('shippo_default_address'), indent=2)
                if cfg.get('shippo_default_address')
                else ''
            ),
            'easypost_address_json': (
                json.dumps(cfg.get('easypost_default_address'), indent=2)
                if cfg.get('easypost_default_address')
                else ''
            ),
            'active_nav': 'shipping',
            'breadcrumb_trail': _trail({'label': 'Shipping'}),
        },
    )


def _rate_fields(request) -> dict:
    """The posted rate as model fields; raises ``RateError`` for the merchant."""
    from plugins.installed.shipping.models import ShippingZone  # noqa: PLC0415
    from plugins.installed.shipping.rates import RateError, priority, rate_values  # noqa: PLC0415

    post = request.POST
    name = (post.get('name') or '').strip()[:120]
    zone = ShippingZone.objects.filter(pk=(post.get('zone') or '').strip() or None).first()
    if not name or zone is None:
        raise RateError('Name and zone are required.')
    values = rate_values(
        computation=(post.get('computation') or 'flat').strip(),
        flat_amount=post.get('flat_amount'),
        free_threshold=post.get('free_threshold'),
        tiers=list(zip(post.getlist('tier_threshold'), post.getlist('tier_amount'), strict=False)),
        estimated_days_min=post.get('estimated_days_min'),
        estimated_days_max=post.get('estimated_days_max'),
    )
    values.update(
        name=name,
        zone=zone,
        description=(post.get('description') or '').strip()[:240],
        is_active=bool(post.get('is_active')),
        priority=priority(post.get('priority')),
    )
    return values


def _create_rate(request) -> None:
    from plugins.installed.shipping.models import ShippingRate  # noqa: PLC0415
    from plugins.installed.shipping.rates import RateError  # noqa: PLC0415

    try:
        rate = ShippingRate.objects.create(**_rate_fields(request))
    except RateError as exc:
        messages.error(request, str(exc))
        return
    messages.success(request, f'Rate "{rate.name}" created.')


def _edit_rate(request, rate_id: str) -> None:
    """Save the whole form: a field left blank is cleared, not kept."""
    from plugins.installed.shipping.models import ShippingRate  # noqa: PLC0415
    from plugins.installed.shipping.rates import RateError  # noqa: PLC0415

    obj = ShippingRate.objects.filter(pk=rate_id).first()
    if obj is None:
        messages.error(request, 'Rate not found.')
        return
    try:
        fields = _rate_fields(request)
    except RateError as exc:
        messages.error(request, str(exc))
        return
    for field, value in fields.items():
        setattr(obj, field, value)
    obj.save()
    messages.success(request, f'Rate "{obj.name}" updated.')


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
@require_capability('shipping.read')
def rates(request):
    """Back-compat redirect: rates merged into the unified Shipping page
    (ADR 0003 — one settings surface per domain)."""
    zone = (request.GET.get('zone') or '').strip()
    base = '/dashboard/shipping/zones/'
    return HttpResponseRedirect(f'{base}?zone={zone}#rates' if zone else f'{base}#rates')


@staff_member_required
@require_capability('shipping.write')
@require_POST
def buy_label(request, order_number: str):
    """Buy a carrier label for one of the order's parcels, or for everything
    still open on it (``shipping/labels.py``), from the order page's panel."""
    from plugins.installed.orders.models import Order  # noqa: PLC0415
    from plugins.installed.shipping.labels import (  # noqa: PLC0415
        LabelError,
        label_for_parcel,
        parcel_on,
        ship_with_label,
    )

    order = get_object_or_404(Order, order_number=order_number)
    provider = (request.POST.get('provider') or '').strip() or None
    parcel_id = (request.POST.get('fulfillment') or '').strip()
    try:
        if parcel_id:
            parcel = parcel_on(order, parcel_id)
            if parcel is None:
                raise Http404('No such parcel on this order.')
            label = label_for_parcel(parcel, provider=provider)
        else:
            label = ship_with_label(order, provider=provider)
    except LabelError as exc:
        messages.error(request, str(exc))
    else:
        tracking = f', tracking {label.tracking_number}' if label.tracking_number else ''
        messages.success(request, f'Label bought from {label.get_provider_display()}{tracking}.')
    return redirect(reverse('admin_dashboard:order_detail', args=[order.order_number]))
