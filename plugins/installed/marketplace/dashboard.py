"""Marketplace dashboard pages (admin-only)."""

from __future__ import annotations

import csv
import logging
from collections import Counter
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.text import slugify

from morpheus.plugin import dashboard_trail

logger = logging.getLogger('morpheus.marketplace')


def _trail(*items):
    return dashboard_trail('Marketplace', '/dashboard/apps/marketplace/vendors/', *items)


def _default_commission_percent() -> Decimal:
    """Read the platform's default commission percent from plugin config."""
    try:
        from plugins.registry import plugin_registry  # noqa: PLC0415

        plugin = plugin_registry.get('marketplace')
        if plugin is not None:
            cfg = plugin.get_config() or {}
            raw = cfg.get('default_commission_percent', 15)
            return Decimal(str(raw))
    except Exception as exc:  # noqa: BLE001 — fall through to schema default
        logger.debug('marketplace: default commission lookup failed: %s', exc)
    return Decimal('15')


def _vendor_commission_percent(vendor) -> Decimal:
    """Effective commission % for a vendor.

    Per-vendor override is stored as a `marketplace.commission_percent_override`
    metafield on the catalog.Vendor content type so we don't have to add a
    column to catalog (which would cross plugin boundaries). Falls back to
    the marketplace plugin's `default_commission_percent` config when unset.
    """
    try:
        from django.contrib.contenttypes.models import ContentType  # noqa: PLC0415

        from plugins.installed.metafields.models import Metafield  # noqa: PLC0415

        ct = ContentType.objects.get_for_model(type(vendor))
        m = Metafield.objects.filter(
            content_type=ct,
            object_id=str(vendor.pk),
            namespace='marketplace',
            key='commission_percent_override',
        ).first()
        if m is not None and (m.value or '').strip():
            return Decimal(str(m.value))
    except Exception as exc:  # noqa: BLE001 — metafields may be disabled
        logger.debug('marketplace: commission override lookup failed: %s', exc)
    return _default_commission_percent()


@staff_member_required
def vendors_list(request):
    from plugins.installed.catalog.models import Vendor  # noqa: PLC0415
    from plugins.installed.marketplace.models import VendorOrder  # noqa: PLC0415

    status_filter = (request.GET.get('status') or '').strip()
    qs = Vendor.objects.all().order_by('-created_at')
    if status_filter == 'active':
        qs = qs.filter(is_active=True)
    elif status_filter == 'inactive':
        qs = qs.filter(is_active=False)

    # Roll up GMV per vendor (sum of vendor_order gross).
    gross_by_vendor = dict(
        VendorOrder.objects.values_list('vendor')
        .annotate(total=Sum('gross'))
        .values_list('vendor', 'total')
    )

    vendors = []
    for v in qs[:200]:
        vendors.append(
            {
                'obj': v,
                'gross': gross_by_vendor.get(v.id, 0),
            }
        )
    return render(
        request,
        'marketplace/dashboard/vendors_list.html',
        {
            'vendors': vendors,
            'status_filter': status_filter,
            'active_nav': 'marketplace',
            'breadcrumb_trail': _trail({'label': 'Vendors'}),
        },
    )


@staff_member_required
def applications_list(request):
    """Approve / reject incoming vendor applications. On approval,
    materialise a catalog.Vendor row and link it back via vendor_fk
    style (we use Vendor.owner = application.user as the canonical link).
    """
    from plugins.installed.catalog.models import Vendor  # noqa: PLC0415
    from plugins.installed.marketplace.models import VendorApplication  # noqa: PLC0415

    if request.method == 'POST':
        app_id = request.POST.get('application_id', '') or request.GET.get('application_id', '')
        action = request.POST.get('action', '') or request.GET.get('action', '')
        if app_id and action in ('approve', 'reject', 'review'):
            try:
                app = VendorApplication.objects.get(pk=app_id)
                created_vendor = None
                if action == 'approve':
                    app.status = 'approved'
                    app.decided_at = timezone.now()
                    # Materialise the catalog.Vendor if not yet present.
                    existing = Vendor.objects.filter(owner=app.user).first()
                    if existing is None:
                        created_vendor = Vendor.objects.create(
                            name=app.business_name,
                            slug=slugify(app.business_name)[:200] or f'vendor-{app.pk.hex[:8]}',
                            description=app.description,
                            owner=app.user,
                            is_active=True,
                        )
                    else:
                        created_vendor = existing
                elif action == 'reject':
                    app.status = 'rejected'
                    app.decided_at = timezone.now()
                else:
                    app.status = 'reviewing'
                app.save(update_fields=['status', 'decided_at'])
                if action == 'approve':
                    messages.success(request, f'Approved {app.business_name}.')
                    if created_vendor is not None:
                        return HttpResponseRedirect(
                            f'/dashboard/marketplace/vendors/{created_vendor.id}/'
                        )
                else:
                    messages.success(request, f'Application → {app.get_status_display()}.')
            except VendorApplication.DoesNotExist:
                messages.error(request, 'Application not found.')
        return HttpResponseRedirect(request.path)

    status_filter = (request.GET.get('status') or '').strip()
    qs = VendorApplication.objects.select_related('user')
    if status_filter:
        qs = qs.filter(status=status_filter)
    apps = list(qs.order_by('-submitted_at')[:200])

    counts = dict(
        VendorApplication.objects.values_list('status')
        .annotate(c=Count('id'))
        .values_list('status', 'c')
    )
    return render(
        request,
        'marketplace/dashboard/applications_list.html',
        {
            'applications': apps,
            'counts': counts,
            'status_filter': status_filter,
            'active_nav': 'marketplace',
            'breadcrumb_trail': _trail({'label': 'Applications'}),
        },
    )


def _handle_commission_post(request, vendor, ct) -> bool:
    """Process commission set/clear POST. Returns True if redirect needed."""
    from plugins.installed.metafields.models import Metafield  # noqa: PLC0415

    action = request.POST.get('action', '')
    if action == 'set_commission':
        raw = (request.POST.get('commission_percent') or '').strip()
        try:
            val = Decimal(raw)
            if val < 0 or val > 100:
                raise InvalidOperation()
            Metafield.objects.update_or_create(
                content_type=ct,
                object_id=str(vendor.pk),
                namespace='marketplace',
                key='commission_percent_override',
                defaults={'value': str(val), 'value_type': 'number'},
            )
            messages.success(request, f'Commission override set to {val}%.')
        except (InvalidOperation, ValueError):
            messages.error(request, 'Commission must be a number between 0 and 100.')
        return True
    if action == 'clear_commission':
        Metafield.objects.filter(
            content_type=ct,
            object_id=str(vendor.pk),
            namespace='marketplace',
            key='commission_percent_override',
        ).delete()
        messages.success(request, 'Commission override cleared — using platform default.')
        return True
    return False


def _top_skus_from_snapshots(vorders) -> list[tuple[str, int]]:
    """Flatten items_snapshot rows and return the top-10 sku/name by quantity."""
    sku_counter: Counter = Counter()
    for snap in vorders.values_list('items_snapshot', flat=True):
        if not isinstance(snap, list):
            continue
        for item in snap:
            if not isinstance(item, dict):
                continue
            key = item.get('sku') or item.get('name') or item.get('slug') or ''
            if not key:
                continue
            qty = item.get('quantity') or 1
            try:
                sku_counter[key] += int(qty)
            except (TypeError, ValueError):
                sku_counter[key] += 1
    return sku_counter.most_common(10)


@staff_member_required
def vendor_detail(request, vendor_id):
    """Per-vendor analytics + commission override editor."""
    from django.contrib.contenttypes.models import ContentType  # noqa: PLC0415

    from plugins.installed.catalog.models import Product, Vendor  # noqa: PLC0415
    from plugins.installed.marketplace.models import (  # noqa: PLC0415
        VendorOrder,
        VendorPayout,
        VendorPayoutAccount,
    )
    from plugins.installed.metafields.models import Metafield  # noqa: PLC0415

    vendor = get_object_or_404(Vendor, pk=vendor_id)
    ct = ContentType.objects.get_for_model(Vendor)

    if request.method == 'POST':
        _handle_commission_post(request, vendor, ct)
        return HttpResponseRedirect(request.path)

    now = timezone.now()
    vorders = VendorOrder.objects.filter(vendor=vendor)

    gross_30 = vorders.filter(created_at__gte=now - timedelta(days=30)).aggregate(
        t=Sum('gross'),
    )['t'] or Decimal('0')
    gross_7 = vorders.filter(created_at__gte=now - timedelta(days=7)).aggregate(
        t=Sum('gross'),
    )['t'] or Decimal('0')

    status_counts = dict(
        vorders.values_list('status').annotate(c=Count('id')).values_list('status', 'c')
    )
    total_orders = sum(status_counts.values())
    top_skus = _top_skus_from_snapshots(vorders)
    active_products = Product.objects.filter(vendor=vendor, status='active').count()

    acct = VendorPayoutAccount.objects.filter(vendor=vendor).first()
    pending_balance = acct.accrued_balance.amount if acct else Decimal('0')
    payout_method = acct.method if acct else ''

    override = Metafield.objects.filter(
        content_type=ct,
        object_id=str(vendor.pk),
        namespace='marketplace',
        key='commission_percent_override',
    ).first()

    return render(
        request,
        'marketplace/dashboard/vendor_detail.html',
        {
            'vendor': vendor,
            'gross_30': gross_30,
            'gross_7': gross_7,
            'total_orders': total_orders,
            'status_counts': status_counts,
            'top_skus': top_skus,
            'active_products': active_products,
            'pending_balance': pending_balance,
            'payout_method': payout_method,
            'override_value': override.value if override else '',
            'effective_commission': _vendor_commission_percent(vendor),
            'default_commission': _default_commission_percent(),
            'recent_orders': list(
                vorders.select_related('parent_order').order_by('-created_at')[:10]
            ),
            'recent_payouts': list(
                VendorPayout.objects.filter(vendor=vendor).order_by('-requested_at')[:10]
            ),
            'active_nav': 'marketplace',
            'breadcrumb_trail': _trail(
                {'label': 'Vendors', 'url': '/dashboard/apps/marketplace/vendors/'},
                {'label': vendor.name},
            ),
        },
    )


@staff_member_required
def vendor_orders(request):
    from plugins.installed.marketplace.models import VendorOrder  # noqa: PLC0415

    status_filter = (request.GET.get('status') or '').strip()
    qs = VendorOrder.objects.select_related('vendor', 'parent_order')
    if status_filter:
        qs = qs.filter(status=status_filter)
    rows = list(qs.order_by('-created_at')[:200])

    counts = dict(
        VendorOrder.objects.values_list('status').annotate(c=Count('id')).values_list('status', 'c')
    )
    return render(
        request,
        'marketplace/dashboard/vendor_orders.html',
        {
            'orders': rows,
            'counts': counts,
            'status_filter': status_filter,
            'active_nav': 'marketplace',
            'breadcrumb_trail': _trail({'label': 'Vendor orders'}),
        },
    )


def _handle_payouts_bulk_paid(request):
    from plugins.installed.marketplace import services  # noqa: PLC0415
    from plugins.installed.marketplace.models import VendorPayout  # noqa: PLC0415

    ids = request.POST.getlist('payout_ids')
    ok = err = 0
    for pid in ids:
        try:
            p = VendorPayout.objects.get(pk=pid)
            services.mark_vendor_payout_paid(p)
            ok += 1
        except (VendorPayout.DoesNotExist, ValueError):
            err += 1
    if ok:
        messages.success(request, f'Marked {ok} payout(s) paid.')
    if err:
        messages.error(request, f'{err} payout(s) could not be marked paid.')


def _handle_payout_single_action(request):
    from plugins.installed.marketplace.models import VendorPayout  # noqa: PLC0415

    payout_id = request.POST.get('payout_id', '')
    action = request.POST.get('action', '')
    if not payout_id or action not in ('mark_paid', 'mark_failed', 'mark_processing'):
        return
    try:
        p = VendorPayout.objects.get(pk=payout_id)
    except VendorPayout.DoesNotExist:
        messages.error(request, 'Payout not found.')
        return
    status_map = {'mark_paid': 'paid', 'mark_failed': 'failed', 'mark_processing': 'processing'}
    p.status = status_map[action]
    update_fields = ['status']
    if action == 'mark_paid' and hasattr(p, 'paid_at'):
        p.paid_at = timezone.now()
        update_fields.append('paid_at')
    p.save(update_fields=update_fields)
    messages.success(request, f'Payout → {p.get_status_display()}.')


def _payouts_csv_response(qs):
    today = timezone.localdate().isoformat()
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="payouts-{today}.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            'vendor_id',
            'vendor_name',
            'status',
            'amount',
            'currency',
            'method',
            'external_reference',
            'requested_at',
            'paid_at',
        ]
    )
    for p in qs.order_by('-requested_at'):
        writer.writerow(
            [
                str(p.vendor_id) if p.vendor_id else '',
                p.vendor.name if p.vendor_id else '',
                p.status,
                str(p.amount.amount),
                str(p.amount.currency),
                p.method or '',
                p.external_reference or '',
                p.requested_at.isoformat() if p.requested_at else '',
                p.paid_at.isoformat() if p.paid_at else '',
            ]
        )
    return response


@staff_member_required
def payouts(request):
    from plugins.installed.marketplace.models import VendorPayout  # noqa: PLC0415

    status_filter = (request.GET.get('status') or '').strip()

    if request.method == 'POST':
        if request.POST.get('action') == 'bulk_mark_paid':
            _handle_payouts_bulk_paid(request)
        else:
            _handle_payout_single_action(request)
        return HttpResponseRedirect(request.get_full_path())

    qs = VendorPayout.objects.select_related('vendor')
    if status_filter:
        qs = qs.filter(status=status_filter)

    if request.GET.get('export') == 'csv':
        return _payouts_csv_response(qs)

    rows = list(qs.order_by('-requested_at')[:200])
    counts = dict(
        VendorPayout.objects.values_list('status')
        .annotate(c=Count('id'))
        .values_list('status', 'c')
    )
    return render(
        request,
        'marketplace/dashboard/payouts.html',
        {
            'payouts': rows,
            'counts': counts,
            'status_filter': status_filter,
            'active_nav': 'marketplace',
            'breadcrumb_trail': _trail({'label': 'Payouts'}),
        },
    )


@staff_member_required
def payout_accounts(request):
    """Manage VendorPayoutAccount rows — how each vendor gets paid."""
    from plugins.installed.marketplace.models import VendorPayoutAccount  # noqa: PLC0415

    if request.method == 'POST':
        acct_id = request.POST.get('account_id', '')
        action = request.POST.get('action', '')
        if acct_id and action == 'toggle':
            try:
                a = VendorPayoutAccount.objects.get(pk=acct_id)
                a.is_active = not a.is_active
                a.save(update_fields=['is_active'])
                messages.success(
                    request, f'{a.vendor.name} payout → {"active" if a.is_active else "paused"}.'
                )
            except VendorPayoutAccount.DoesNotExist:
                messages.error(request, 'Payout account not found.')
        return HttpResponseRedirect(request.path)

    accounts = list(
        VendorPayoutAccount.objects.select_related('vendor').order_by('-updated_at')[:200]
    )
    return render(
        request,
        'marketplace/dashboard/payout_accounts.html',
        {
            'accounts': accounts,
            'active_nav': 'marketplace',
            'breadcrumb_trail': _trail({'label': 'Payout accounts'}),
        },
    )


@staff_member_required
def reports(request):
    """Vendor performance — GMV per vendor, recent activity, sparkline."""
    from plugins.installed.catalog.models import Vendor  # noqa: PLC0415
    from plugins.installed.marketplace.models import (  # noqa: PLC0415
        VendorApplication,
        VendorOrder,
        VendorPayout,
    )

    try:
        days = max(1, min(int(request.GET.get('days') or 30), 365))
    except (TypeError, ValueError):
        days = 30
    now = timezone.now()
    since = now - timedelta(days=days)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    gross_by_vendor = (
        VendorOrder.objects.filter(created_at__gte=since)
        .values('vendor', 'vendor__name')
        .annotate(
            gross=Sum('gross'),
            commission=Sum('commission'),
            net=Sum('net'),
            order_count=Count('id'),
        )
        .order_by('-gross')
    )
    top = [
        {
            'vendor_id': row['vendor'],
            'name': row['vendor__name'] or '—',
            'gross': row['gross'] or Decimal('0'),
            'commission': row['commission'] or Decimal('0'),
            'net': row['net'] or Decimal('0'),
            'orders': row['order_count'] or 0,
        }
        for row in gross_by_vendor[:25]
    ]

    # KPIs
    gmv_month = VendorOrder.objects.filter(created_at__gte=month_start).aggregate(
        t=Sum('gross'),
    )['t'] or Decimal('0')
    payouts_pending = VendorPayout.objects.filter(
        status__in=('pending', 'processing'),
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    top_vendor_30 = (
        VendorOrder.objects.filter(created_at__gte=now - timedelta(days=30))
        .values('vendor', 'vendor__name')
        .annotate(g=Sum('gross'))
        .order_by('-g')
        .first()
    )

    summary = {
        'active_vendors': Vendor.objects.filter(is_active=True).count(),
        'total_vendors': Vendor.objects.count(),
        'orders_period': VendorOrder.objects.filter(created_at__gte=since).count(),
        'gross_period': VendorOrder.objects.filter(created_at__gte=since).aggregate(t=Sum('gross'))[
            't'
        ]
        or Decimal('0'),
        'commission_period': VendorOrder.objects.filter(created_at__gte=since).aggregate(
            t=Sum('commission')
        )['t']
        or Decimal('0'),
        'paid_period': VendorPayout.objects.filter(
            created_at__gte=since,
            status='paid',
        ).aggregate(t=Sum('amount'))['t']
        or Decimal('0'),
        'gmv_month': gmv_month,
        'payouts_pending': payouts_pending,
        'top_vendor_name': (top_vendor_30 or {}).get('vendor__name') or '—',
        'top_vendor_id': (top_vendor_30 or {}).get('vendor'),
        'top_vendor_gross': (top_vendor_30 or {}).get('g') or Decimal('0'),
    }

    # Recent activity — last ~20 events across applications, payouts.
    activity: list[dict] = []
    for a in VendorApplication.objects.order_by('-submitted_at')[:20]:
        activity.append(
            {
                'when': a.submitted_at,
                'kind': 'application_submitted',
                'label': f'New application: {a.business_name}',
                'url': '/dashboard/apps/marketplace/applications/',
            }
        )
        if a.decided_at and a.status in ('approved', 'rejected'):
            activity.append(
                {
                    'when': a.decided_at,
                    'kind': f'application_{a.status}',
                    'label': f'Application {a.status}: {a.business_name}',
                    'url': '/dashboard/apps/marketplace/applications/',
                }
            )
    for p in VendorPayout.objects.select_related('vendor').order_by('-requested_at')[:20]:
        activity.append(
            {
                'when': p.requested_at,
                'kind': 'payout_requested',
                'label': f'Payout requested: {p.vendor.name} ({p.amount})',
                'url': '/dashboard/apps/marketplace/payouts/',
            }
        )
        if p.paid_at and p.status == 'paid':
            activity.append(
                {
                    'when': p.paid_at,
                    'kind': 'payout_paid',
                    'label': f'Payout paid: {p.vendor.name} ({p.amount})',
                    'url': '/dashboard/apps/marketplace/payouts/',
                }
            )
    activity.sort(key=lambda e: e['when'], reverse=True)
    activity = activity[:20]

    # Sparkline — last 6 months of gross.
    months: list[dict] = []
    cursor = month_start
    for _ in range(6):
        prev = (cursor - timedelta(days=1)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        months.append({'start': prev, 'end': cursor})
        cursor = prev
    months.reverse()
    months.append({'start': month_start, 'end': month_start + timedelta(days=32)})
    spark_points: list[dict] = []
    for m in months:
        total = VendorOrder.objects.filter(
            created_at__gte=m['start'],
            created_at__lt=m['end'],
        ).aggregate(t=Sum('gross'))['t'] or Decimal('0')
        spark_points.append({'month': m['start'].strftime('%b'), 'value': float(total or 0)})
    spark_max = max((p['value'] for p in spark_points), default=0.0) or 1.0
    spark_w, spark_h = 240, 40
    step = spark_w / max(1, len(spark_points) - 1)
    spark_path = ' '.join(
        f'{i * step:.1f},{spark_h - (p["value"] / spark_max) * (spark_h - 4) - 2:.1f}'
        for i, p in enumerate(spark_points)
    )

    return render(
        request,
        'marketplace/dashboard/reports.html',
        {
            'top': top,
            'summary': summary,
            'days': days,
            'activity': activity,
            'spark_points': spark_points,
            'spark_path': spark_path,
            'spark_w': spark_w,
            'spark_h': spark_h,
            'active_nav': 'marketplace',
            'breadcrumb_trail': _trail({'label': 'Reports'}),
        },
    )
