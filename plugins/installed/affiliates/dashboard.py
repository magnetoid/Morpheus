"""Affiliate dashboard views (admin-only)."""

from __future__ import annotations

import csv
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.text import slugify


def _trail(*items):
    """Build a breadcrumb trail with Dashboard / Affiliates / <leaf> shape."""
    trail = [
        {'label': 'Dashboard', 'url': '/dashboard/'},
        {'label': 'Affiliates', 'url': '/dashboard/apps/affiliates/list/'},
    ]
    for item in items:
        trail.append(item if isinstance(item, dict) else {'label': str(item)})
    return trail


def _affiliate_commission_override(affiliate):
    """Per-affiliate override percent (stored as Metafield). Empty string when unset."""
    try:
        from django.contrib.contenttypes.models import ContentType  # noqa: PLC0415

        from plugins.installed.affiliates.models import Affiliate  # noqa: PLC0415
        from plugins.installed.metafields.models import Metafield  # noqa: PLC0415

        ct = ContentType.objects.get_for_model(Affiliate)
        m = Metafield.objects.filter(
            content_type=ct,
            object_id=str(affiliate.pk),
            namespace='affiliates',
            key='commission_percent_override',
        ).first()
        return (m.value or '').strip() if m else ''
    except Exception:  # noqa: BLE001 — metafields plugin may be disabled
        return ''


def _affiliate_apply_status(aff, action):
    """Mutate + save an Affiliate based on a status action. Returns True on hit."""
    status_map = {
        'approve': 'approved',
        'bulk_approve': 'approved',
        'suspend': 'suspended',
        'bulk_suspend': 'suspended',
        'reject': 'rejected',
        'bulk_reject': 'rejected',
        'reactivate': 'approved',
    }
    new_status = status_map.get(action)
    if new_status is None:
        return False
    aff.status = new_status
    if new_status == 'approved':
        aff.approved_at = timezone.now()
        aff.save(update_fields=['status', 'approved_at'])
    else:
        aff.save(update_fields=['status'])
    return True


def _affiliates_handle_post(request):
    from plugins.installed.affiliates.models import Affiliate  # noqa: PLC0415

    action = request.POST.get('action', '')

    if action in ('bulk_approve', 'bulk_reject', 'bulk_suspend'):
        ids = request.POST.getlist('affiliate_ids')
        ok = 0
        for aff in Affiliate.objects.filter(pk__in=ids):
            if _affiliate_apply_status(aff, action):
                ok += 1
        if ok:
            messages.success(request, f'{ok} affiliate(s) updated.')
        return

    affiliate_id = request.POST.get('affiliate_id', '')
    if not affiliate_id or action not in ('approve', 'suspend', 'reject', 'reactivate'):
        return
    try:
        aff = Affiliate.objects.get(pk=affiliate_id)
    except Affiliate.DoesNotExist:
        messages.error(request, 'Affiliate not found.')
        return
    _affiliate_apply_status(aff, action)
    messages.success(request, f'Affiliate {aff.handle} → {aff.status}.')


@staff_member_required
def affiliates_list(request):
    """List of affiliates ordered by lifetime payout, with bulk + per-row actions."""
    from plugins.installed.affiliates.models import Affiliate  # noqa: PLC0415

    if request.method == 'POST':
        _affiliates_handle_post(request)
        return HttpResponseRedirect(request.get_full_path())

    status_filter = (request.GET.get('status') or '').strip()
    qs = Affiliate.objects.select_related('user', 'program').order_by(
        '-lifetime_paid',
        '-created_at',
    )
    if status_filter:
        qs = qs.filter(status=status_filter)
    rows = list(qs[:200])

    counts = dict(
        Affiliate.objects.values_list('status')
        .annotate(c=Count('id'))
        .values_list(
            'status',
            'c',
        )
    )
    return render(
        request,
        'affiliates/dashboard/affiliates_list.html',
        {
            'affiliates': rows,
            'counts': counts,
            'status_filter': status_filter,
            'active_nav': 'growth',
            'breadcrumb_trail': _trail({'label': 'Affiliates list'}),
        },
    )


def _payouts_csv_response(qs):
    today = timezone.localdate().isoformat()
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="affiliate-payouts-{today}.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            'affiliate_id',
            'handle',
            'email',
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
                str(p.affiliate_id) if p.affiliate_id else '',
                p.affiliate.handle if p.affiliate_id else '',
                getattr(p.affiliate.user, 'email', '') if p.affiliate_id else '',
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


def _payouts_bulk_mark_paid(request):
    from plugins.installed.affiliates import services  # noqa: PLC0415
    from plugins.installed.affiliates.models import AffiliatePayout  # noqa: PLC0415

    ids = request.POST.getlist('payout_ids')
    ok = err = 0
    for pid in ids:
        try:
            p = AffiliatePayout.objects.get(pk=pid)
            services.mark_payout_paid(p)
            ok += 1
        except (AffiliatePayout.DoesNotExist, ValueError):
            err += 1
    if ok:
        messages.success(request, f'Marked {ok} payout(s) paid.')
    if err:
        messages.error(request, f'{err} payout(s) could not be marked paid.')


def _payouts_single_action(p, action):
    if action == 'mark_paid':
        if p.status == 'paid':
            return
        p.status = 'paid'
        p.paid_at = timezone.now()
        p.affiliate.lifetime_paid = (p.affiliate.lifetime_paid or 0) + p.amount
        p.affiliate.accrued_balance = max(
            (p.affiliate.accrued_balance or 0) - p.amount,
            0,
        )
        p.affiliate.save(update_fields=['lifetime_paid', 'accrued_balance'])
        p.save(update_fields=['status', 'paid_at'])
    elif action == 'mark_failed':
        p.status = 'failed'
        p.save(update_fields=['status'])
    elif action == 'mark_processing':
        p.status = 'processing'
        p.save(update_fields=['status'])


def _payouts_handle_post(request):
    from plugins.installed.affiliates.models import AffiliatePayout  # noqa: PLC0415

    action = request.POST.get('action', '')
    if action == 'bulk_mark_paid':
        _payouts_bulk_mark_paid(request)
        return

    payout_id = request.POST.get('payout_id', '')
    if not payout_id or action not in ('mark_paid', 'mark_failed', 'mark_processing'):
        return
    try:
        p = AffiliatePayout.objects.select_related('affiliate').get(pk=payout_id)
    except AffiliatePayout.DoesNotExist:
        messages.error(request, 'Payout not found.')
        return
    _payouts_single_action(p, action)
    messages.success(request, f'Payout → {p.get_status_display()}.')


@staff_member_required
def payouts_list(request):
    from plugins.installed.affiliates.models import AffiliatePayout  # noqa: PLC0415

    if request.method == 'POST':
        _payouts_handle_post(request)
        return HttpResponseRedirect(request.get_full_path())

    status_filter = (request.GET.get('status') or '').strip()
    qs = AffiliatePayout.objects.select_related('affiliate__user')
    if status_filter:
        qs = qs.filter(status=status_filter)

    if request.GET.get('export') == 'csv':
        return _payouts_csv_response(qs)

    rows = list(qs.order_by('-requested_at')[:200])
    totals = {
        'pending': AffiliatePayout.objects.filter(status='pending').count(),
        'processing': AffiliatePayout.objects.filter(status='processing').count(),
        'paid': AffiliatePayout.objects.filter(status='paid').count(),
    }
    return render(
        request,
        'affiliates/dashboard/payouts_list.html',
        {
            'payouts': rows,
            'totals': totals,
            'status_filter': status_filter,
            'active_nav': 'growth',
            'breadcrumb_trail': _trail({'label': 'Payouts'}),
        },
    )


@staff_member_required
def programs_list(request):
    """Manage AffiliateProgram rows — commission tiers."""
    from plugins.installed.affiliates.models import AffiliateProgram  # noqa: PLC0415

    if request.method == 'POST':
        action = request.POST.get('action', '')
        program_id = request.POST.get('program_id', '')

        if action == 'create':
            name = (request.POST.get('name') or '').strip()
            if name:
                ctype = request.POST.get('commission_type') or 'percent'
                try:
                    cvalue = Decimal(request.POST.get('commission_value') or '0')
                except (InvalidOperation, TypeError, ValueError):
                    cvalue = Decimal('0')
                try:
                    days = int(request.POST.get('cookie_window_days') or '30')
                except (TypeError, ValueError):
                    days = 30
                AffiliateProgram.objects.create(
                    name=name,
                    slug=slugify(name)[:100] or f'program-{int(timezone.now().timestamp())}',
                    commission_type=ctype,
                    commission_value=cvalue,
                    cookie_window_days=max(1, min(days, 365)),
                )
                messages.success(request, f'Created program "{name}".')

        elif action == 'toggle' and program_id:
            try:
                p = AffiliateProgram.objects.get(pk=program_id)
                p.is_active = not p.is_active
                p.save(update_fields=['is_active'])
                messages.success(
                    request,
                    f'{p.name} → {"active" if p.is_active else "paused"}.',
                )
            except AffiliateProgram.DoesNotExist:
                messages.error(request, 'Program not found.')

        elif action == 'delete' and program_id:
            try:
                p = AffiliateProgram.objects.get(pk=program_id)
                if p.affiliates.exists():
                    messages.error(request, 'Cannot delete a program that has affiliates.')
                else:
                    p.delete()
                    messages.success(request, 'Program deleted.')
            except AffiliateProgram.DoesNotExist:
                pass

        return HttpResponseRedirect(request.path)

    programs = list(
        AffiliateProgram.objects.annotate(affiliate_count=Count('affiliates')).order_by(
            '-is_active',
            'name',
        )
    )
    return render(
        request,
        'affiliates/dashboard/programs_list.html',
        {
            'programs': programs,
            'active_nav': 'growth',
            'breadcrumb_trail': _trail({'label': 'Programs'}),
        },
    )


def _links_csv_response(qs):
    today = timezone.localdate().isoformat()
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="affiliate-links-{today}.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            'code',
            'affiliate_handle',
            'affiliate_email',
            'program',
            'landing_url',
            'coupon_code',
            'clicks',
            'conversions',
            'is_active',
            'created_at',
        ]
    )
    for link in qs.order_by('-click_count'):
        writer.writerow(
            [
                link.code,
                link.affiliate.handle,
                getattr(link.affiliate.user, 'email', ''),
                link.affiliate.program.name if link.affiliate.program_id else '',
                link.landing_url,
                link.coupon_code or '',
                link.click_count,
                link.conversion_count,
                'yes' if link.is_active else 'no',
                link.created_at.isoformat() if link.created_at else '',
            ]
        )
    return response


@staff_member_required
def links_list(request):
    """Top affiliate links by clicks / conversions, filterable + CSV export."""
    from plugins.installed.affiliates.models import (  # noqa: PLC0415
        Affiliate,
        AffiliateLink,
        AffiliateProgram,
    )

    sort = (request.GET.get('sort') or 'clicks').strip()
    sort_field = {
        'clicks': '-click_count',
        'conversions': '-conversion_count',
        'recent': '-created_at',
    }.get(sort, '-click_count')

    affiliate_id = (request.GET.get('affiliate') or '').strip()
    program_id = (request.GET.get('program') or '').strip()

    qs = AffiliateLink.objects.select_related(
        'affiliate__user',
        'affiliate__program',
    )
    if affiliate_id:
        qs = qs.filter(affiliate_id=affiliate_id)
    if program_id:
        qs = qs.filter(affiliate__program_id=program_id)

    if request.GET.get('export') == 'csv':
        return _links_csv_response(qs)

    rows = list(qs.order_by(sort_field)[:200])
    affiliates = list(Affiliate.objects.select_related('user').order_by('handle')[:200])
    programs = list(AffiliateProgram.objects.order_by('name'))
    return render(
        request,
        'affiliates/dashboard/links_list.html',
        {
            'links': rows,
            'sort': sort,
            'affiliates': affiliates,
            'programs': programs,
            'affiliate_filter': affiliate_id,
            'program_filter': program_id,
            'active_nav': 'growth',
            'breadcrumb_trail': _trail({'label': 'Links'}),
        },
    )


def _conversions_csv_response(qs):
    today = timezone.localdate().isoformat()
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="affiliate-conversions-{today}.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            'order_number',
            'affiliate_handle',
            'affiliate_email',
            'link_code',
            'commission',
            'currency',
            'status',
            'created_at',
        ]
    )
    for c in qs.order_by('-created_at'):
        writer.writerow(
            [
                getattr(c.order, 'order_number', '') if c.order_id else '',
                c.affiliate.handle if c.affiliate_id else '',
                getattr(c.affiliate.user, 'email', '') if c.affiliate_id else '',
                c.link.code if c.link_id else '',
                str(c.commission.amount),
                str(c.commission.currency),
                c.status,
                c.created_at.isoformat() if c.created_at else '',
            ]
        )
    return response


@staff_member_required
def conversions_list(request):
    """Attributed orders — which affiliate earned which conversion."""
    from plugins.installed.affiliates.models import AffiliateConversion  # noqa: PLC0415

    if request.method == 'POST':
        conv_id = request.POST.get('conversion_id', '')
        action = request.POST.get('action', '')
        if conv_id and action in ('approve', 'reject'):
            try:
                c = AffiliateConversion.objects.get(pk=conv_id)
                c.status = 'approved' if action == 'approve' else 'rejected'
                c.save(update_fields=['status'])
                messages.success(request, f'Conversion → {c.get_status_display()}.')
            except AffiliateConversion.DoesNotExist:
                messages.error(request, 'Conversion not found.')
        return HttpResponseRedirect(request.get_full_path())

    status_filter = (request.GET.get('status') or '').strip()
    qs = AffiliateConversion.objects.select_related(
        'affiliate__user',
        'order',
        'link',
    )
    if status_filter:
        qs = qs.filter(status=status_filter)

    if request.GET.get('export') == 'csv':
        return _conversions_csv_response(qs)

    rows = list(qs.order_by('-created_at')[:200])
    counts = dict(
        AffiliateConversion.objects.values_list('status')
        .annotate(c=Count('id'))
        .values_list(
            'status',
            'c',
        )
    )
    return render(
        request,
        'affiliates/dashboard/conversions_list.html',
        {
            'conversions': rows,
            'counts': counts,
            'status_filter': status_filter,
            'active_nav': 'growth',
            'breadcrumb_trail': _trail({'label': 'Conversions'}),
        },
    )


@staff_member_required
def analytics(request):
    """KPI summary + trend table + top performers."""
    from plugins.installed.affiliates.models import (  # noqa: PLC0415
        Affiliate,
        AffiliateClick,
        AffiliateConversion,
        AffiliateLink,
        AffiliatePayout,
        AffiliateProgram,
    )

    try:
        days = max(1, min(int(request.GET.get('days') or 30), 365))
    except (TypeError, ValueError):
        days = 30
    since = timezone.now() - timedelta(days=days)

    summary = {
        'affiliates_total': Affiliate.objects.count(),
        'affiliates_approved': Affiliate.objects.filter(status='approved').count(),
        'affiliates_active': Affiliate.objects.filter(status='approved').count(),
        'programs_active': AffiliateProgram.objects.filter(is_active=True).count(),
        'links_total': AffiliateLink.objects.count(),
        'clicks_lifetime': AffiliateClick.objects.count(),
        'conversions_lifetime': AffiliateConversion.objects.count(),
        'commission_paid_lifetime': AffiliatePayout.objects.filter(
            status='paid',
        ).aggregate(t=Sum('amount'))['t']
        or Decimal('0'),
        'clicks_period': AffiliateClick.objects.filter(occurred_at__gte=since).count(),
        'conversions_period': AffiliateConversion.objects.filter(
            created_at__gte=since,
        ).count(),
        'commission_period': AffiliateConversion.objects.filter(
            created_at__gte=since,
        ).aggregate(t=Sum('commission'))['t']
        or Decimal('0'),
    }

    # 30-day trend table — daily buckets, clicks/conversions/earnings.
    buckets = []
    for i in range(days - 1, -1, -1):
        day_start = (timezone.now() - timedelta(days=i)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        day_end = day_start + timedelta(days=1)
        clicks = AffiliateClick.objects.filter(
            occurred_at__gte=day_start,
            occurred_at__lt=day_end,
        ).count()
        convs = AffiliateConversion.objects.filter(
            created_at__gte=day_start,
            created_at__lt=day_end,
        )
        earn = convs.aggregate(t=Sum('commission'))['t'] or Decimal('0')
        buckets.append(
            {
                'date': day_start.date().isoformat(),
                'clicks': clicks,
                'conversions': convs.count(),
                'earnings': earn,
            }
        )

    # Top 10 affiliates by earnings IN window.
    top_aff_rows = list(
        AffiliateConversion.objects.filter(created_at__gte=since)
        .values('affiliate_id')
        .annotate(earned=Sum('commission'), convs=Count('id'))
        .order_by('-earned')[:10]
    )
    aff_lookup = {
        a.id: a
        for a in Affiliate.objects.filter(
            id__in=[r['affiliate_id'] for r in top_aff_rows],
        ).select_related('user', 'program')
    }
    top_affiliates = [
        {
            'affiliate': aff_lookup.get(r['affiliate_id']),
            'earned': r['earned'] or Decimal('0'),
            'conversions': r['convs'],
        }
        for r in top_aff_rows
        if aff_lookup.get(r['affiliate_id']) is not None
    ]

    top_links = list(
        AffiliateLink.objects.select_related('affiliate__user').order_by(
            '-conversion_count',
        )[:10]
    )

    # Sparkline points for the last `days` of earnings.
    spark_vals = [float(b['earnings']) for b in buckets]
    spark_max = max(spark_vals, default=0.0) or 1.0
    spark_w, spark_h = 280, 40
    step = spark_w / max(1, len(spark_vals) - 1)
    spark_path = ' '.join(
        f'{i * step:.1f},{spark_h - (v / spark_max) * (spark_h - 4) - 2:.1f}'
        for i, v in enumerate(spark_vals)
    )

    return render(
        request,
        'affiliates/dashboard/analytics.html',
        {
            'summary': summary,
            'days': days,
            'buckets': buckets,
            'top_affiliates': top_affiliates,
            'top_links': top_links,
            'spark_path': spark_path,
            'spark_w': spark_w,
            'spark_h': spark_h,
            'active_nav': 'growth',
            'breadcrumb_trail': _trail({'label': 'Analytics'}),
        },
    )


@staff_member_required
def affiliate_detail(request, affiliate_id):
    """Per-affiliate drill-in: 30d KPIs + top links + recent conversions + edit form."""
    from django.contrib.contenttypes.models import ContentType  # noqa: PLC0415

    from plugins.installed.affiliates.models import (  # noqa: PLC0415
        Affiliate,
        AffiliateClick,
        AffiliateConversion,
        AffiliateLink,
    )
    from plugins.installed.metafields.models import Metafield  # noqa: PLC0415

    affiliate = get_object_or_404(
        Affiliate.objects.select_related('user', 'program'),
        pk=affiliate_id,
    )
    ct = ContentType.objects.get_for_model(Affiliate)

    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'save':
            # notes → field on the model (exists)
            notes = (request.POST.get('notes') or '').strip()
            affiliate.notes = notes
            affiliate.save(update_fields=['notes'])

            # commission override → metafield (no schema change)
            raw = (request.POST.get('commission_percent_override') or '').strip()
            if raw == '':
                Metafield.objects.filter(
                    content_type=ct,
                    object_id=str(affiliate.pk),
                    namespace='affiliates',
                    key='commission_percent_override',
                ).delete()
                messages.success(request, 'Saved (commission override cleared).')
            else:
                try:
                    val = Decimal(raw)
                    if val < 0 or val > 100:
                        raise InvalidOperation()
                    Metafield.objects.update_or_create(
                        content_type=ct,
                        object_id=str(affiliate.pk),
                        namespace='affiliates',
                        key='commission_percent_override',
                        defaults={'value': str(val), 'value_type': 'number'},
                    )
                    messages.success(request, f'Saved (override {val}%).')
                except (InvalidOperation, ValueError):
                    messages.error(
                        request,
                        'Commission override must be a number between 0 and 100.',
                    )
        return HttpResponseRedirect(request.path)

    now = timezone.now()
    since_30 = now - timedelta(days=30)

    convs_qs = AffiliateConversion.objects.filter(affiliate=affiliate)
    clicks_qs = AffiliateClick.objects.filter(link__affiliate=affiliate)

    clicks_30 = clicks_qs.filter(occurred_at__gte=since_30).count()
    convs_30_qs = convs_qs.filter(created_at__gte=since_30)
    convs_30 = convs_30_qs.count()
    earnings_30 = convs_30_qs.aggregate(t=Sum('commission'))['t'] or Decimal('0')

    refunded_30 = convs_30_qs.filter(status='rejected').count()
    conv_rate = (convs_30 / clicks_30 * 100.0) if clicks_30 else 0.0
    refund_rate = (refunded_30 / convs_30 * 100.0) if convs_30 else 0.0

    top_links = list(AffiliateLink.objects.filter(affiliate=affiliate).order_by('-click_count')[:5])
    recent_conversions = list(convs_qs.select_related('order', 'link').order_by('-created_at')[:20])

    return render(
        request,
        'affiliates/dashboard/affiliate_detail.html',
        {
            'affiliate': affiliate,
            'clicks_30': clicks_30,
            'conversions_30': convs_30,
            'earnings_30': earnings_30,
            'lifetime_earnings': affiliate.lifetime_paid,
            'conversion_rate': conv_rate,
            'refund_rate': refund_rate,
            'top_links': top_links,
            'recent_conversions': recent_conversions,
            'commission_override': _affiliate_commission_override(affiliate),
            'active_nav': 'growth',
            'breadcrumb_trail': _trail(
                {'label': 'Affiliates', 'url': '/dashboard/apps/affiliates/list/'},
                {'label': affiliate.handle},
            ),
        },
    )


def _parse_tiers(raw: str):
    """Parse + sanitise the tiers JSON textarea. Returns a clean list of
    {name, min_conversions, percent} dicts; drops malformed rows. Empty/invalid
    JSON → []."""
    import json  # noqa: PLC0415

    try:
        data = json.loads(raw) if raw.strip() else []
    except (json.JSONDecodeError, ValueError):
        return None  # signal a parse error to the caller
    if not isinstance(data, list):
        return None
    out = []
    for row in data:
        if not isinstance(row, dict):
            continue
        try:
            out.append(
                {
                    'name': str(row.get('name', ''))[:40],
                    'min_conversions': max(0, int(row.get('min_conversions', 0))),
                    'percent': float(Decimal(str(row.get('percent', 0)))),
                }
            )
        except (TypeError, ValueError, InvalidOperation):
            continue
    return out


def _parse_category_overrides(raw: str):
    """Parse + sanitise the per-category overrides JSON textarea. Returns a
    clean {slug: percent_float} dict; drops malformed entries. Invalid JSON →
    None (parse error)."""
    import json  # noqa: PLC0415

    try:
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    out = {}
    for k, v in data.items():
        try:
            pct = float(Decimal(str(v)))
        except (TypeError, ValueError, InvalidOperation):
            continue
        slug = slugify(str(k))[:200]
        if slug and 0 <= pct <= 100:
            out[slug] = pct
    return out


def _program_options_from_post(request):
    """Extract the advanced OPTIONS (tiers, category overrides, auto-approve)
    from POST. Returns ``(options_dict, error_or_None)``; ``options_dict`` is
    suitable for assigning straight onto an AffiliateProgram."""
    tiers = _parse_tiers(request.POST.get('tiers_json') or '')
    if tiers is None:
        return None, 'Commission tiers must be valid JSON (a list of objects).'
    overrides = _parse_category_overrides(request.POST.get('category_overrides_json') or '')
    if overrides is None:
        return None, 'Per-category overrides must be valid JSON (an object).'
    try:
        auto_approve = max(0, min(int(request.POST.get('auto_approve_after') or 0), 1000))
    except (TypeError, ValueError):
        auto_approve = 0
    return (
        {
            'tiers': tiers,
            'category_commission_overrides': overrides,
            'auto_approve_after': auto_approve,
        },
        None,
    )


def _program_stats(program):
    """30-day KPIs + top-10 affiliates for a program. ``(stats, top)``."""
    from plugins.installed.affiliates.models import (  # noqa: PLC0415
        Affiliate,
        AffiliateClick,
        AffiliateConversion,
        AffiliatePayout,
    )

    since_30 = timezone.now() - timedelta(days=30)
    stats = {
        'affiliates': Affiliate.objects.filter(program=program).count(),
        'clicks_30': AffiliateClick.objects.filter(
            link__affiliate__program=program, occurred_at__gte=since_30
        ).count(),
        'conversions_30': AffiliateConversion.objects.filter(
            affiliate__program=program, created_at__gte=since_30
        ).count(),
        'commission_paid_lifetime': AffiliatePayout.objects.filter(
            affiliate__program=program, status='paid'
        ).aggregate(t=Sum('amount'))['t']
        or Decimal('0'),
    }
    rows = list(
        AffiliateConversion.objects.filter(affiliate__program=program)
        .values('affiliate_id')
        .annotate(gross=Sum('commission'), convs=Count('id'))
        .order_by('-gross')[:10]
    )
    aff_lookup = {
        a.id: a
        for a in Affiliate.objects.filter(id__in=[r['affiliate_id'] for r in rows]).select_related(
            'user'
        )
    }
    top = [
        {
            'affiliate': aff_lookup.get(r['affiliate_id']),
            'gross': r['gross'] or Decimal('0'),
            'conversions': r['convs'],
        }
        for r in rows
        if aff_lookup.get(r['affiliate_id']) is not None
    ]
    return stats, top


def _save_program(request, program, *, is_new):
    """Create or update an AffiliateProgram from POST. Returns an
    HttpResponseRedirect on success, or a string error message."""
    name = (request.POST.get('name') or '').strip()
    if not name:
        return 'Name is required.'

    options, opt_err = _program_options_from_post(request)
    if opt_err:
        return opt_err

    slug_raw = (request.POST.get('slug') or '').strip()
    ctype = request.POST.get('commission_type') or 'percent'
    try:
        cvalue = Decimal(request.POST.get('commission_value') or '0')
    except (InvalidOperation, TypeError, ValueError):
        cvalue = Decimal('0')
    try:
        days = max(1, min(int(request.POST.get('cookie_window_days') or '30'), 365))
    except (TypeError, ValueError):
        days = 30
    is_active = request.POST.get('is_active') == 'on'
    description = (request.POST.get('description') or '').strip()

    if is_new:
        from plugins.installed.affiliates.models import AffiliateProgram  # noqa: PLC0415

        slug = slugify(slug_raw or name)[:100] or f'program-{int(timezone.now().timestamp())}'
        created = AffiliateProgram.objects.create(
            name=name,
            slug=slug,
            description=description,
            commission_type=ctype,
            commission_value=cvalue,
            cookie_window_days=days,
            is_active=is_active,
            **options,
        )
        messages.success(request, f'Created program "{name}".')
        return HttpResponseRedirect(f'/dashboard/affiliates/programs/{created.id}/')

    program.name = name
    program.slug = slugify(slug_raw or program.slug or name)[:100] or program.slug
    program.description = description
    program.commission_type = ctype
    program.commission_value = cvalue
    program.cookie_window_days = days
    program.is_active = is_active
    program.tiers = options['tiers']
    program.category_commission_overrides = options['category_commission_overrides']
    program.auto_approve_after = options['auto_approve_after']
    program.save(
        update_fields=[
            'name',
            'slug',
            'description',
            'commission_type',
            'commission_value',
            'cookie_window_days',
            'is_active',
            'tiers',
            'category_commission_overrides',
            'auto_approve_after',
        ]
    )
    messages.success(request, 'Program saved.')
    return HttpResponseRedirect(request.path)


@staff_member_required
def program_detail(request, program_id):
    """Per-program drill-in + edit form. `program_id is None` ⇒ create mode."""
    import json  # noqa: PLC0415

    from plugins.installed.affiliates.models import AffiliateProgram  # noqa: PLC0415

    program = None
    is_new = program_id is None
    if not is_new:
        program = get_object_or_404(AffiliateProgram, pk=program_id)

    if request.method == 'POST' and request.POST.get('action', '') in ('save', 'create'):
        result = _save_program(request, program, is_new=is_new)
        if isinstance(result, HttpResponseRedirect):
            return result
        messages.error(request, result)
        return HttpResponseRedirect(request.path)

    stats = {'affiliates': 0, 'clicks_30': 0, 'conversions_30': 0, 'commission_paid_lifetime': 0}
    top_affiliates = []
    if program is not None:
        stats, top_affiliates = _program_stats(program)

    breadcrumb = _trail(
        {'label': 'Programs', 'url': '/dashboard/apps/affiliates/programs/'},
        {'label': 'New program' if is_new else program.name},
    )
    return render(
        request,
        'affiliates/dashboard/program_detail.html',
        {
            'program': program,
            'is_new': is_new,
            'stats': stats,
            'top_affiliates': top_affiliates,
            'tiers_json': json.dumps(program.tiers, indent=2) if program and program.tiers else '',
            'category_overrides_json': (
                json.dumps(program.category_commission_overrides, indent=2)
                if program and program.category_commission_overrides
                else ''
            ),
            'active_nav': 'growth',
            'breadcrumb_trail': breadcrumb,
        },
    )


@staff_member_required
def creatives_list(request):
    """Merchant management of affiliate marketing creatives — upload images +
    swipe copy that affiliates grab from /affiliates/me/creatives/."""
    from plugins.installed.affiliates.models import AffiliateCreative

    if request.method == 'POST':
        if request.POST.get('action') == 'delete':
            AffiliateCreative.objects.filter(id=request.POST.get('id')).delete()
            messages.success(request, 'Creative deleted.')
        else:
            title = (request.POST.get('title') or '').strip()
            if not title:
                messages.error(request, 'A title is required.')
            else:
                AffiliateCreative.objects.create(
                    title=title[:200],
                    image=request.FILES.get('image'),
                    landing_url=(request.POST.get('landing_url') or '/').strip()[:500],
                    swipe_copy=(request.POST.get('swipe_copy') or '').strip(),
                    is_active=request.POST.get('is_active') != '0',
                )
                messages.success(request, 'Creative added.')
        return HttpResponseRedirect('/dashboard/apps/affiliates/creatives/')

    return render(
        request,
        'affiliates/dashboard/creatives_list.html',
        {
            'creatives': list(AffiliateCreative.objects.all()),
            'breadcrumb_trail': _trail('Creatives'),
            'active_nav': 'affiliates',
        },
    )
