"""Reddit Ads dashboard (campaign management + reporting)."""

from __future__ import annotations

from core.authz import require_capability
from morpheus.app.views import render, staff_member_required


@staff_member_required
@require_capability('marketing.write')
def ads_dashboard(request):
    from plugins.installed.reddit_ads.services.ads_api import (
        campaign_report,
        create_campaign,
        list_campaigns,
        set_campaign_status,
    )
    from plugins.installed.reddit_ads.services.api import ads_connected
    from plugins.installed.reddit_ads.services.oauth import is_connected

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
                'Campaign created (paused — finish setup in Reddit Ads).'
                if res.get('ok')
                else f'Create failed: {res.get("reason")}'
            )
        elif action == 'verify':
            from plugins.installed.reddit_ads.services.api import verify_connection

            verify = verify_connection()
        else:
            cid = request.POST.get('campaign_id', '')
            if cid and action in ('ACTIVE', 'PAUSED'):
                res = set_campaign_status(cid, action)
                msg = 'Campaign updated.' if res.get('ok') else f'Failed: {res.get("reason")}'

    try:
        days = int(request.GET.get('days', 30))
    except (TypeError, ValueError):
        days = 30
    report = (
        campaign_report(days=days) if ads_connected() else {'ok': False, 'reason': 'not_connected'}
    )
    campaigns = list_campaigns() if ads_connected() else {'ok': False, 'campaigns': []}

    from plugins.installed.reddit_ads.services.book_communities import BOOK_COMMUNITIES

    return render(
        request,
        'reddit_ads/dashboard.html',
        {
            'active_nav': 'reddit_ads',
            'connected': ads_connected(),
            'has_token': is_connected(),
            'report': report,
            'campaigns': campaigns.get('campaigns', []),
            'days': days,
            'msg': msg,
            'verify': verify,
            'book_communities': BOOK_COMMUNITIES,
        },
    )
