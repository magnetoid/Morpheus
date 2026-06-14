"""Audit-log operating surface — a filterable view over core.audit.AuditEvent.

Gives staff one place to review what happened on the platform, with a quick
filter for AI actions (agents.*, selfdev.*) and security events (rbac.*, auth.*)
— the F10 "audit-log operating surfaces" gap.
"""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.shortcuts import render

_AI_PREFIXES = ('agents.', 'selfdev.', 'ai.')
_SECURITY_PREFIXES = ('rbac.', 'auth.', 'login', 'mfa.', 'token.', 'consent.')


def _prefix_q(prefixes):
    q = Q()
    for p in prefixes:
        q |= Q(event_type__startswith=p)
    return q


@staff_member_required
def audit_log_view(request):
    from core.audit.models import AuditEvent

    category = (request.GET.get('category') or 'all').strip()
    q = (request.GET.get('q') or '').strip()
    severity = (request.GET.get('severity') or '').strip()

    events = AuditEvent.objects.select_related('actor').all()
    if category == 'ai':
        events = events.filter(_prefix_q(_AI_PREFIXES))
    elif category == 'security':
        events = events.filter(_prefix_q(_SECURITY_PREFIXES))
    if q:
        events = events.filter(Q(event_type__icontains=q) | Q(target__icontains=q))
    if severity in ('info', 'warning', 'error', 'critical'):
        events = events.filter(severity=severity)

    return render(
        request,
        'observability/audit_log.html',
        {
            'events': events[:200],
            'category': category,
            'q': q,
            'severity': severity,
            'active_nav': 'developer',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Audit log'},
            ],
        },
    )
