"""Affiliate dashboard views (admin-only)."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone


def _trail(*items):
    """Build a breadcrumb trail with Dashboard / Affiliates / <leaf> shape."""
    trail = [
        {'label': 'Dashboard', 'url': '/dashboard/'},
        {'label': 'Affiliates', 'url': '/dashboard/apps/affiliates/list/'},
    ]
    for item in items:
        trail.append(item if isinstance(item, dict) else {'label': str(item)})
    return trail


@staff_member_required
def affiliates_list(request):
    """List of affiliates ordered by lifetime payout."""
    from plugins.installed.affiliates.models import Affiliate

    if request.method == 'POST':
        affiliate_id = request.POST.get('affiliate_id', '')
        action = request.POST.get('action', '')
        if affiliate_id and action in ('approve', 'suspend', 'reject', 'reactivate'):
            try:
                aff = Affiliate.objects.get(pk=affiliate_id)
                if action == 'approve':
                    aff.status = 'approved'
                    aff.approved_at = timezone.now()
                elif action == 'suspend':
                    aff.status = 'suspended'
                elif action == 'reject':
                    aff.status = 'rejected'
                elif action == 'reactivate':
                    aff.status = 'approved'
                aff.save(update_fields=['status', 'approved_at'])
                messages.success(request, f'Affiliate {aff.handle} → {aff.status}.')
            except Affiliate.DoesNotExist:
                messages.error(request, 'Affiliate not found.')
        return HttpResponseRedirect(request.path)

    status_filter = (request.GET.get('status') or '').strip()
    qs = Affiliate.objects.select_related('user', 'program').order_by('-lifetime_paid', '-created_at')
    if status_filter:
        qs = qs.filter(status=status_filter)
    rows = list(qs[:200])

    counts = dict(
        Affiliate.objects.values_list('status').annotate(c=Count('id')).values_list('status', 'c')
    )
    return render(request, 'affiliates/dashboard/affiliates_list.html', {
        'affiliates': rows,
        'counts': counts,
        'status_filter': status_filter,
        'active_nav': 'growth',
        'breadcrumb_trail': _trail({'label': 'Affiliates list'}),
    })


@staff_member_required
def payouts_list(request):
    from plugins.installed.affiliates.models import AffiliatePayout

    if request.method == 'POST':
        payout_id = request.POST.get('payout_id', '')
        action = request.POST.get('action', '')
        if payout_id and action in ('mark_paid', 'mark_failed', 'mark_processing'):
            try:
                p = AffiliatePayout.objects.select_related('affiliate').get(pk=payout_id)
                if action == 'mark_paid':
                    if p.status != 'paid':
                        p.status = 'paid'
                        p.paid_at = timezone.now()
                        p.affiliate.lifetime_paid = (p.affiliate.lifetime_paid or 0) + p.amount
                        p.affiliate.accrued_balance = max(
                            (p.affiliate.accrued_balance or 0) - p.amount, 0,
                        )
                        p.affiliate.save(update_fields=['lifetime_paid', 'accrued_balance'])
                        p.save(update_fields=['status', 'paid_at'])
                elif action == 'mark_failed':
                    p.status = 'failed'
                    p.save(update_fields=['status'])
                elif action == 'mark_processing':
                    p.status = 'processing'
                    p.save(update_fields=['status'])
                messages.success(request, f'Payout → {p.get_status_display()}.')
            except AffiliatePayout.DoesNotExist:
                messages.error(request, 'Payout not found.')
        return HttpResponseRedirect(request.path)

    rows = list(
        AffiliatePayout.objects
        .select_related('affiliate__user')
        .order_by('-requested_at')[:200]
    )
    totals = {
        'pending': AffiliatePayout.objects.filter(status='pending').count(),
        'processing': AffiliatePayout.objects.filter(status='processing').count(),
        'paid': AffiliatePayout.objects.filter(status='paid').count(),
    }
    return render(request, 'affiliates/dashboard/payouts_list.html', {
        'payouts': rows,
        'totals': totals,
        'active_nav': 'growth',
        'breadcrumb_trail': _trail({'label': 'Payouts'}),
    })


@staff_member_required
def programs_list(request):
    """Manage AffiliateProgram rows — commission tiers."""
    from plugins.installed.affiliates.models import AffiliateProgram
    from django.utils.text import slugify

    if request.method == 'POST':
        action = request.POST.get('action', '')
        program_id = request.POST.get('program_id', '')

        if action == 'create':
            name = (request.POST.get('name') or '').strip()
            if name:
                ctype = request.POST.get('commission_type') or 'percent'
                try:
                    cvalue = Decimal(request.POST.get('commission_value') or '0')
                except Exception:
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
                messages.success(request, f'{p.name} → {"active" if p.is_active else "paused"}.')
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
        AffiliateProgram.objects
        .annotate(affiliate_count=Count('affiliates'))
        .order_by('-is_active', 'name')
    )
    return render(request, 'affiliates/dashboard/programs_list.html', {
        'programs': programs,
        'active_nav': 'growth',
        'breadcrumb_trail': _trail({'label': 'Programs'}),
    })


@staff_member_required
def links_list(request):
    """Top affiliate links by clicks / conversions."""
    from plugins.installed.affiliates.models import AffiliateLink

    sort = (request.GET.get('sort') or 'clicks').strip()
    sort_field = {
        'clicks': '-click_count',
        'conversions': '-conversion_count',
        'recent': '-created_at',
    }.get(sort, '-click_count')

    rows = list(
        AffiliateLink.objects
        .select_related('affiliate__user')
        .order_by(sort_field)[:200]
    )
    return render(request, 'affiliates/dashboard/links_list.html', {
        'links': rows,
        'sort': sort,
        'active_nav': 'growth',
        'breadcrumb_trail': _trail({'label': 'Links'}),
    })


@staff_member_required
def conversions_list(request):
    """Attributed orders — which affiliate earned which conversion."""
    from plugins.installed.affiliates.models import AffiliateConversion

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
        return HttpResponseRedirect(request.path)

    status_filter = (request.GET.get('status') or '').strip()
    qs = AffiliateConversion.objects.select_related('affiliate__user', 'order', 'link')
    if status_filter:
        qs = qs.filter(status=status_filter)
    rows = list(qs.order_by('-created_at')[:200])

    counts = dict(
        AffiliateConversion.objects.values_list('status').annotate(c=Count('id')).values_list('status', 'c')
    )
    return render(request, 'affiliates/dashboard/conversions_list.html', {
        'conversions': rows,
        'counts': counts,
        'status_filter': status_filter,
        'active_nav': 'growth',
        'breadcrumb_trail': _trail({'label': 'Conversions'}),
    })


@staff_member_required
def analytics(request):
    """Performance summary — top affiliates, conversion totals, time series."""
    from plugins.installed.affiliates.models import (
        Affiliate, AffiliateClick, AffiliateConversion, AffiliateLink,
    )

    try:
        days = max(1, min(int(request.GET.get('days') or 30), 365))
    except (TypeError, ValueError):
        days = 30
    since = timezone.now() - timedelta(days=days)

    summary = {
        'affiliates_total': Affiliate.objects.count(),
        'affiliates_approved': Affiliate.objects.filter(status='approved').count(),
        'links_total': AffiliateLink.objects.count(),
        'clicks_period': AffiliateClick.objects.filter(occurred_at__gte=since).count(),
        'conversions_period': AffiliateConversion.objects.filter(created_at__gte=since).count(),
        'commission_period': AffiliateConversion.objects
            .filter(created_at__gte=since)
            .aggregate(t=Sum('commission'))['t'] or Decimal('0'),
    }

    top_affiliates = list(
        Affiliate.objects
        .filter(status='approved')
        .select_related('user', 'program')
        .order_by('-lifetime_paid')[:10]
    )

    top_links = list(
        AffiliateLink.objects
        .select_related('affiliate__user')
        .order_by('-conversion_count')[:10]
    )

    # Last 14 days conversion buckets — quick sparkline data.
    buckets = []
    for i in range(13, -1, -1):
        day_start = (timezone.now() - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        buckets.append({
            'date': day_start.date().isoformat(),
            'conversions': AffiliateConversion.objects.filter(
                created_at__gte=day_start, created_at__lt=day_end,
            ).count(),
        })

    return render(request, 'affiliates/dashboard/analytics.html', {
        'summary': summary,
        'days': days,
        'top_affiliates': top_affiliates,
        'top_links': top_links,
        'buckets': buckets,
        'active_nav': 'growth',
        'breadcrumb_trail': _trail({'label': 'Analytics'}),
    })
