"""Microsoft Commerce HTTP surface: public catalog feed + dashboard."""

from __future__ import annotations

from django.core.cache import cache
from django.http import HttpResponse

from morpheus.views import render, staff_member_required

FEED_CACHE_KEY = 'microsoft_commerce:feed:v1'
_FEED_TTL = 60 * 60


def microsoft_catalog_feed(request):
    """Public Microsoft Merchant Center feed at /feeds/microsoft-catalog.xml."""
    from plugins.installed.microsoft_commerce.services.settings import microsoft_settings

    if not microsoft_settings().enabled:
        return HttpResponse('Feed disabled', status=404, content_type='text/plain')
    xml = cache.get(FEED_CACHE_KEY)
    if xml is None:
        from plugins.installed.microsoft_commerce.services.feed import build_feed

        xml, _ = build_feed()
        cache.set(FEED_CACHE_KEY, xml, _FEED_TTL)
    return HttpResponse(xml, content_type='application/xml; charset=utf-8')


@staff_member_required
def dashboard(request):
    from core.utils.site import site_base_url
    from plugins.installed.microsoft_commerce.models import MicrosoftSyncLog
    from plugins.installed.microsoft_commerce.services.coverage import coverage_report
    from plugins.installed.microsoft_commerce.services.settings import (
        microsoft_settings,
        raw_config,
    )

    if request.method == 'POST' and request.POST.get('action') == 'rebuild':
        from plugins.installed.microsoft_commerce.services.feed import build_feed

        xml, _ = build_feed()
        cache.set(FEED_CACHE_KEY, xml, _FEED_TTL)

    return render(
        request,
        'microsoft_commerce/dashboard.html',
        {
            'active_nav': 'microsoft_commerce',
            'settings': microsoft_settings(),
            'report': coverage_report(),
            'feed_url': site_base_url().rstrip('/') + '/feeds/microsoft-catalog.xml',
            'recent_logs': MicrosoftSyncLog.objects.all()[:10],
            'uet_set': bool((raw_config().get('uet_tag_id') or '').strip()),
        },
    )


@staff_member_required
def ads_dashboard(request):
    """Microsoft Advertising campaign management (SOAP). Control only — no metrics."""
    from plugins.installed.microsoft_commerce.services.ads_api import (
        create_campaign,
        list_campaigns,
        set_campaign_status,
    )
    from plugins.installed.microsoft_commerce.services.soap import ads_connected

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
                'Campaign created (paused — finish setup in Microsoft Advertising).'
                if res.get('ok')
                else f'Create failed: {res.get("reason")}'
            )
        else:
            cid = request.POST.get('campaign_id', '')
            if cid and action in ('Active', 'Paused'):
                res = set_campaign_status(cid, action)
                msg = 'Campaign updated.' if res.get('ok') else f'Failed: {res.get("reason")}'

    report = (
        list_campaigns()
        if ads_connected()
        else {'ok': False, 'reason': 'not_connected', 'campaigns': []}
    )
    return render(
        request,
        'microsoft_commerce/ads.html',
        {
            'active_nav': 'microsoft_commerce',
            'connected': ads_connected(),
            'report': report,
            'msg': msg,
        },
    )
