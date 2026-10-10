"""EU AI Act evidence export — merchant dashboard page + CSV download.

A staff page under /dashboard/apps/agent_core/compliance/ that shows the AI
decision + approval trail for a date window and downloads it as CSV
(?export=csv). Read-only over the audit tables; the report itself is built by
compliance.build_ai_act_report so the page and the management command agree.
"""

from __future__ import annotations

import csv
from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from core.authz import require_capability
from plugins.installed.agent_core.compliance import build_ai_act_report


def _window(request):
    """Resolve [since, until) from ?days=N (default 30). Bounded 1..365."""
    try:
        days = max(1, min(365, int(request.GET.get('days', '30'))))
    except (TypeError, ValueError):
        days = 30
    until = timezone.now()
    return until - timedelta(days=days), until, days


@staff_member_required
@require_capability('system.read')
def ai_act_report_view(request):
    since, until, days = _window(request)
    report = build_ai_act_report(since=since, until=until)

    if request.GET.get('export') == 'csv':
        resp = HttpResponse(content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="ai-act-decisions-{days}d.csv"'
        w = csv.writer(resp)
        w.writerow(['section', 'timestamp', 'agent_or_tool', 'target_or_state', 'model', 'actor'])
        for d in report['decisions']:
            w.writerow(['decision', d['timestamp'], d['tool'], d['target'], d['model'], d['actor']])
        for a in report['approvals']:
            w.writerow(['approval', a['timestamp'], a['tool'], a['state'], '', a['decided_by']])
        for c in report['consents']:
            w.writerow([c['kind'], c['timestamp'], c['tool'], c['outcome'], '', c['actor']])
        return resp

    return render(
        request,
        'agent_core/dashboard/compliance_report.html',
        {
            'report': report,
            'days': days,
            'active_nav': 'main',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'AI Act evidence'},
            ],
        },
    )
