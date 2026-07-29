"""Amazon Ads dashboard (campaign management + reporting metrics)."""

from __future__ import annotations

from morpheus.plugin.views import render, staff_member_required


@staff_member_required
def ads_dashboard(request):
    from plugins.installed.amazon_ads.services.ads_api import (
        create_campaign,
        list_campaigns,
        set_campaign_budget,
        set_campaign_status,
    )
    from plugins.installed.amazon_ads.services.api import ads_connected
    from plugins.installed.amazon_ads.services.oauth import is_connected
    from plugins.installed.amazon_ads.services.reporting import cached_metrics

    msg = ''
    verify = None
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            try:
                budget = float(request.POST.get('budget') or 0)
            except (TypeError, ValueError):
                budget = 0.0
            res = create_campaign(
                name=(request.POST.get('name') or '').strip()[:120], daily_budget=budget
            )
            msg = (
                'Campaign created (paused — finish setup in Amazon Ads).'
                if res.get('ok')
                else f'Create failed: {res.get("reason")}'
            )
        elif action == 'refresh_metrics':
            from plugins.installed.amazon_ads.tasks import fetch_report

            try:
                fetch_report.delay(30)
                msg = 'Fetching performance metrics in the background — refresh in a minute.'
            except Exception:  # noqa: BLE001
                msg = 'Could not queue the metrics fetch (background worker unavailable).'
        elif action == 'verify':
            from plugins.installed.amazon_ads.services.api import verify_connection

            verify = verify_connection()
        elif action == 'set_budget':
            cid = request.POST.get('campaign_id', '')
            try:
                budget = float(request.POST.get('budget') or 0)
            except (TypeError, ValueError):
                budget = 0.0
            res = set_campaign_budget(cid, budget)
            msg = 'Budget updated.' if res.get('ok') else f'Failed: {res.get("reason")}'
        else:
            cid = request.POST.get('campaign_id', '')
            if cid and action in ('ENABLED', 'PAUSED'):
                res = set_campaign_status(cid, action)
                msg = 'Campaign updated.' if res.get('ok') else f'Failed: {res.get("reason")}'

    report = (
        list_campaigns()
        if ads_connected()
        else {'ok': False, 'reason': 'not_connected', 'campaigns': []}
    )
    metrics = cached_metrics() if ads_connected() else None
    by_id = (metrics or {}).get('metrics', {}) if metrics else {}
    for c in report.get('campaigns', []):
        m = by_id.get(str(c.get('id')))
        if m:
            c['metrics'] = m

    return render(
        request,
        'amazon_ads/dashboard.html',
        {
            'active_nav': 'amazon_ads',
            'connected': ads_connected(),
            'has_token': is_connected(),
            'report': report,
            'msg': msg,
            'verify': verify,
            'has_metrics': bool(by_id),
        },
    )
