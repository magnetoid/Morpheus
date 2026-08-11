"""Snapchat Commerce HTTP surface: public catalog feed + dashboards."""

from __future__ import annotations

from django.core.cache import cache
from django.http import HttpResponse

from morpheus.app.views import render, staff_member_required

FEED_CACHE_KEY = 'snapchat_commerce:feed:v1'
_FEED_TTL = 60 * 60


def snapchat_catalog_feed(request):
    """Public Snapchat catalog feed at /feeds/snapchat-catalog.xml (cached)."""
    from plugins.installed.snapchat_commerce.services.settings import snapchat_settings

    if not snapchat_settings().enabled:
        return HttpResponse('Feed disabled', status=404, content_type='text/plain')
    xml = cache.get(FEED_CACHE_KEY)
    if xml is None:
        from plugins.installed.snapchat_commerce.services.feed import build_feed

        xml, _ = build_feed()
        cache.set(FEED_CACHE_KEY, xml, _FEED_TTL)
    return HttpResponse(xml, content_type='application/xml; charset=utf-8')


@staff_member_required
def dashboard(request):
    from core.utils.site import site_base_url
    from plugins.installed.snapchat_commerce.models import SnapchatSyncLog
    from plugins.installed.snapchat_commerce.services.coverage import coverage_report
    from plugins.installed.snapchat_commerce.services.oauth import is_connected
    from plugins.installed.snapchat_commerce.services.settings import snapchat_settings

    if request.method == 'POST' and request.POST.get('action') == 'rebuild':
        from plugins.installed.snapchat_commerce.services.feed import build_feed

        xml, _ = build_feed()
        cache.set(FEED_CACHE_KEY, xml, _FEED_TTL)

    verify = None
    if request.method == 'POST' and request.POST.get('action') == 'verify':
        from plugins.installed.snapchat_commerce.services.api import verify_connection

        verify = verify_connection()

    return render(
        request,
        'snapchat_commerce/dashboard.html',
        {
            'active_nav': 'snapchat_commerce',
            'settings': snapchat_settings(),
            'report': coverage_report(),
            'feed_url': site_base_url().rstrip('/') + '/feeds/snapchat-catalog.xml',
            'recent_logs': SnapchatSyncLog.objects.all()[:10],
            'has_token': is_connected(),
            'verify': verify,
        },
    )


@staff_member_required
def ads_dashboard(request):
    from plugins.installed.snapchat_commerce.services.ads_api import (
        campaign_report,
        create_campaign,
        list_campaigns,
        set_campaign_status,
    )
    from plugins.installed.snapchat_commerce.services.api import ads_connected

    msg = ''
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
                'Campaign created (paused — finish setup in Snapchat Ads Manager).'
                if res.get('ok')
                else f'Create failed: {res.get("reason")}'
            )
        else:
            cid = request.POST.get('campaign_id', '')
            if cid and action in ('ACTIVE', 'PAUSED'):
                res = set_campaign_status(cid, action)
                msg = 'Campaign updated.' if res.get('ok') else f'Failed: {res.get("reason")}'

    try:
        days = int(request.GET.get('days', 30))
    except (TypeError, ValueError):
        days = 30

    connected = ads_connected()
    listing = list_campaigns() if connected else {'ok': False, 'campaigns': []}
    report = campaign_report(days=days) if connected else {'ok': False, 'reason': 'not_connected'}

    return render(
        request,
        'snapchat_commerce/ads.html',
        {
            'active_nav': 'snapchat_commerce',
            'connected': connected,
            'campaigns': listing.get('campaigns', []),
            'report': report,
            'days': days,
            'msg': msg,
        },
    )
