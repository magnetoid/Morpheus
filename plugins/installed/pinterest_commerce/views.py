"""Pinterest Commerce HTTP surface: public catalog feed + dashboards."""

from __future__ import annotations

from django.core.cache import cache
from django.http import HttpResponse

from morpheus.views import render, staff_member_required

FEED_CACHE_KEY = 'pinterest_commerce:feed:v1'
_FEED_TTL = 60 * 60


def pinterest_catalog_feed(request):
    """Public Pinterest catalog feed at /feeds/pinterest-catalog.xml (cached)."""
    from plugins.installed.pinterest_commerce.services.settings import pinterest_settings

    if not pinterest_settings().enabled:
        return HttpResponse('Feed disabled', status=404, content_type='text/plain')
    xml = cache.get(FEED_CACHE_KEY)
    if xml is None:
        from plugins.installed.pinterest_commerce.services.feed import build_feed

        xml, _ = build_feed()
        cache.set(FEED_CACHE_KEY, xml, _FEED_TTL)
    return HttpResponse(xml, content_type='application/xml; charset=utf-8')


@staff_member_required
def dashboard(request):
    from core.utils.site import site_base_url
    from plugins.installed.pinterest_commerce.models import PinterestSyncLog
    from plugins.installed.pinterest_commerce.services.api import has_token
    from plugins.installed.pinterest_commerce.services.coverage import coverage_report
    from plugins.installed.pinterest_commerce.services.settings import pinterest_settings

    if request.method == 'POST' and request.POST.get('action') == 'rebuild':
        from plugins.installed.pinterest_commerce.services.feed import build_feed

        xml, _ = build_feed()
        cache.set(FEED_CACHE_KEY, xml, _FEED_TTL)

    verify = None
    if request.method == 'POST' and request.POST.get('action') == 'verify':
        from plugins.installed.pinterest_commerce.services.api import verify_connection

        verify = verify_connection()

    diagnostics = None
    from plugins.installed.pinterest_commerce.services.api import creds

    if has_token() and creds().get('catalog_feed_id'):
        from plugins.installed.pinterest_commerce.services.diagnostics import feed_diagnostics

        d = feed_diagnostics()
        diagnostics = d if d.get('ok') else None

    return render(
        request,
        'pinterest_commerce/dashboard.html',
        {
            'active_nav': 'pinterest_commerce',
            'settings': pinterest_settings(),
            'report': coverage_report(),
            'feed_url': site_base_url().rstrip('/') + '/feeds/pinterest-catalog.xml',
            'recent_logs': PinterestSyncLog.objects.all()[:10],
            'has_token': has_token(),
            'verify': verify,
            'diagnostics': diagnostics,
        },
    )


@staff_member_required
def ads_dashboard(request):
    from plugins.installed.pinterest_commerce.services.ads_api import (
        campaign_report,
        create_campaign,
        set_campaign_status,
    )
    from plugins.installed.pinterest_commerce.services.api import ads_connected

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
                'Campaign created (paused — finish setup in Pinterest Ads Manager).'
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
    report = (
        campaign_report(days=days) if ads_connected() else {'ok': False, 'reason': 'not_connected'}
    )

    return render(
        request,
        'pinterest_commerce/ads.html',
        {
            'active_nav': 'pinterest_commerce',
            'connected': ads_connected(),
            'report': report,
            'days': days,
            'msg': msg,
        },
    )
