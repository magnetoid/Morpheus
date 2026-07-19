"""Dashboard surface for the self-improvement engine.

Single rich page at /dashboard/system/self-improvement/ with five
tabs: Backlog · Drift · Healing log · Settings · Cost.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

logger = logging.getLogger('morpheus.admin.self_improvement')


@staff_member_required
def overview(request: HttpRequest) -> HttpResponse:
    """Main /dashboard/system/self-improvement/ page."""
    from core.self_improvement.models import (  # noqa: PLC0415
        SiActionLog,
        SiIngestJob,
        SiRecommendation,
        SiSignal,
    )
    from core.self_improvement.policy import export_for_dashboard  # noqa: PLC0415

    now = timezone.now()
    since_7d = now - timedelta(days=7)
    since_30d = now - timedelta(days=30)

    backlog = SiRecommendation.objects.filter(status='proposed').order_by(
        '-impact_score', '-created_at'
    )[:200]

    counts = {
        'open': SiRecommendation.objects.filter(status='proposed').count(),
        'auto_applied_7d': SiRecommendation.objects.filter(
            status='applied', created_at__gte=since_7d
        ).count(),
        'rejected_7d': SiRecommendation.objects.filter(
            status__in=('rejected', 'suppressed'), created_at__gte=since_7d
        ).count(),
        'rollbacks_7d': SiActionLog.objects.filter(
            phase='rollback', outcome='ok', created_at__gte=since_7d
        ).count(),
    }

    cost_30d = (
        SiRecommendation.objects.filter(created_at__gte=since_30d)
        .aggregate(t=Sum('tokens_used'))
        .get('t')
        or 0
    )
    # $0.05 / cluster avg per the cost model.
    cost_estimate = round(cost_30d / 1_000_000 * 15, 2)

    drift_signals = SiSignal.objects.filter(
        source='upstream_drift', occurred_at__gte=since_30d
    ).order_by('-severity', '-occurred_at')[:100]

    last_runs = (
        SiIngestJob.objects.values('collector')
        .order_by('collector', '-started_at')
        .distinct('collector')
    )
    # Postgres-only `distinct(field)`; fall back if SQLite (dev).
    try:
        list(last_runs[:1])
    except Exception:  # noqa: BLE001
        last_runs = SiIngestJob.objects.order_by('-started_at')[:20]

    return render(
        request,
        'admin_dashboard/system/self_improvement/page.html',
        {
            'backlog': backlog,
            'counts': counts,
            'cost_30d_tokens': cost_30d,
            'cost_30d_usd': cost_estimate,
            'drift_signals': drift_signals,
            'policies': export_for_dashboard(),
            'last_runs': list(last_runs),
            'active_nav': 'system',
            'active_subnav': 'self_improvement',
        },
    )


@staff_member_required
@require_POST
def approve(request: HttpRequest, recommendation_id: int) -> HttpResponse:
    from core.self_improvement.models import SiRecommendation  # noqa: PLC0415

    SiRecommendation.objects.filter(pk=recommendation_id, status='proposed').update(
        status='approved', actor=request.user.username or 'staff'
    )
    return redirect('/dashboard/system/self-improvement/')


def _suppress_recommendation(rec, *, reason: str, created_by, expires_at=None):
    """Write si_suppression rows that actually match what the collectors emit.

    The signal layer (services.emit_signal) filters suppressions by the
    collector's own ``(source, fingerprint)``. A recommendation stores the
    *evidence signal ids*, so we resolve those rows and suppress each distinct
    ``(source, fingerprint)`` pair — NOT ``(rec.class_name, signal_pk)``, which
    never matched (class ≠ source, PK ≠ hash). Returns the last created/updated
    suppression, or None if the recommendation carried no evidence signals.
    """
    from core.self_improvement.models import SiSignal, SiSuppression  # noqa: PLC0415

    sigs = SiSignal.objects.filter(pk__in=list(rec.evidence_signal_ids or [])).values_list(
        'source', 'fingerprint'
    )
    suppression = None
    for source, fingerprint in set(sigs):
        suppression, _ = SiSuppression.objects.update_or_create(
            match_class=source,
            match_fingerprint=fingerprint,
            defaults={'reason': reason, 'expires_at': expires_at, 'created_by': created_by},
        )
    return suppression


@staff_member_required
@require_POST
def reject(request: HttpRequest, recommendation_id: int) -> HttpResponse:
    """Reject + write si_suppression rows so the same signal doesn't come back."""
    from core.self_improvement.models import SiRecommendation  # noqa: PLC0415

    reason = (request.POST.get('reason') or '').strip()[:1000]
    rec = SiRecommendation.objects.filter(pk=recommendation_id, status='proposed').first()
    if rec is None:
        return redirect('/dashboard/system/self-improvement/')

    suppression = _suppress_recommendation(
        rec, reason=reason or 'rejected from dashboard', created_by=request.user
    )
    rec.status = 'rejected'
    rec.suppressed_by = suppression
    rec.actor = request.user.username or 'staff'
    rec.save(update_fields=['status', 'suppressed_by', 'actor', 'updated_at'])
    return redirect('/dashboard/system/self-improvement/')


@staff_member_required
@require_POST
def snooze(request: HttpRequest, recommendation_id: int) -> HttpResponse:
    """Suppress for 30 days, then revisit."""
    from core.self_improvement.models import SiRecommendation  # noqa: PLC0415

    rec = SiRecommendation.objects.filter(pk=recommendation_id, status='proposed').first()
    if rec is None:
        return redirect('/dashboard/system/self-improvement/')

    suppression = _suppress_recommendation(
        rec,
        reason='snoozed 30 days',
        created_by=request.user,
        expires_at=timezone.now() + timedelta(days=30),
    )
    rec.status = 'suppressed'
    rec.suppressed_by = suppression
    rec.actor = request.user.username or 'staff'
    rec.save(update_fields=['status', 'suppressed_by', 'actor', 'updated_at'])
    return redirect('/dashboard/system/self-improvement/')
