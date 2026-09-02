"""TikTok Commerce HTTP surface: public catalog feed + dashboards."""

from __future__ import annotations

from django.core.cache import cache
from django.http import HttpResponse

from core.authz import require_capability
from morpheus.app.views import render, staff_member_required

FEED_CACHE_KEY = 'tiktok_commerce:feed:v1'
_FEED_TTL = 60 * 60


def tiktok_catalog_feed(request):
    """Public TikTok catalog feed at /feeds/tiktok-catalog.xml (cached)."""
    from plugins.installed.tiktok_commerce.services.settings import tiktok_settings

    if not tiktok_settings().enabled:
        return HttpResponse('Feed disabled', status=404, content_type='text/plain')
    xml = cache.get(FEED_CACHE_KEY)
    if xml is None:
        from plugins.installed.tiktok_commerce.services.feed import build_feed

        xml, _ = build_feed()
        cache.set(FEED_CACHE_KEY, xml, _FEED_TTL)
    return HttpResponse(xml, content_type='application/xml; charset=utf-8')


@staff_member_required
@require_capability('marketing.write')
def dashboard(request):
    from morpheus.core import site_base_url
    from plugins.installed.tiktok_commerce.models import TiktokSyncLog
    from plugins.installed.tiktok_commerce.services.api import has_token
    from plugins.installed.tiktok_commerce.services.coverage import coverage_report
    from plugins.installed.tiktok_commerce.services.settings import tiktok_settings

    if request.method == 'POST' and request.POST.get('action') == 'rebuild':
        from plugins.installed.tiktok_commerce.services.feed import build_feed

        xml, _ = build_feed()
        cache.set(FEED_CACHE_KEY, xml, _FEED_TTL)

    verify = None
    if request.method == 'POST' and request.POST.get('action') == 'verify':
        from plugins.installed.tiktok_commerce.services.api import verify_connection

        verify = verify_connection()

    diagnostics = None
    from plugins.installed.tiktok_commerce.services.api import catalog_connected

    if catalog_connected():
        from plugins.installed.tiktok_commerce.services.diagnostics import catalog_diagnostics

        d = catalog_diagnostics()
        diagnostics = d if d.get('ok') else None

    return render(
        request,
        'tiktok_commerce/dashboard.html',
        {
            'active_nav': 'tiktok_commerce',
            'settings': tiktok_settings(),
            'report': coverage_report(),
            'feed_url': site_base_url().rstrip('/') + '/feeds/tiktok-catalog.xml',
            'recent_logs': TiktokSyncLog.objects.all()[:10],
            'has_token': has_token(),
            'verify': verify,
            'diagnostics': diagnostics,
        },
    )


@staff_member_required
@require_capability('marketing.write')
def ads_dashboard(request):
    from plugins.installed.tiktok_commerce.services.ads_api import (
        campaign_report,
        create_campaign,
        set_campaign_status,
    )
    from plugins.installed.tiktok_commerce.services.api import ads_connected

    msg = ''
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            try:
                budget = float(request.POST.get('budget') or 0)
            except (TypeError, ValueError):
                budget = 0.0
            res = create_campaign(
                name=(request.POST.get('name') or '').strip()[:120], budget=budget
            )
            msg = (
                'Campaign created (paused — finish setup in TikTok Ads Manager).'
                if res.get('ok')
                else f'Create failed: {res.get("reason")}'
            )
        else:
            cid = request.POST.get('campaign_id', '')
            if cid and action in ('ENABLE', 'DISABLE'):
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
        'tiktok_commerce/ads.html',
        {
            'active_nav': 'tiktok_commerce',
            'connected': ads_connected(),
            'report': report,
            'days': days,
            'msg': msg,
        },
    )
