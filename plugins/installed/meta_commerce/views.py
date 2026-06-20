"""Meta Commerce HTTP surface: public catalog feed + dashboards."""

from __future__ import annotations

from django.core.cache import cache
from django.http import HttpResponse

from morpheus.views import render, staff_member_required

FEED_CACHE_KEY = 'meta_commerce:feed:v1'
_FEED_TTL = 60 * 60


def meta_catalog_feed(request):
    """Public Meta catalog feed at /feeds/meta-catalog.xml (cached)."""
    from plugins.installed.meta_commerce.services.settings import meta_settings

    if not meta_settings().enabled:
        return HttpResponse('Feed disabled', status=404, content_type='text/plain')
    xml = cache.get(FEED_CACHE_KEY)
    if xml is None:
        from plugins.installed.meta_commerce.services.feed import build_feed

        xml, _ = build_feed()
        cache.set(FEED_CACHE_KEY, xml, _FEED_TTL)
    return HttpResponse(xml, content_type='application/xml; charset=utf-8')


@staff_member_required
def dashboard(request):
    """Catalog feed status + coverage + connection + push."""
    from core.utils.site import site_base_url
    from plugins.installed.meta_commerce.models import MetaSyncLog
    from plugins.installed.meta_commerce.services.coverage import coverage_report
    from plugins.installed.meta_commerce.services.graph import catalog_connected, has_token
    from plugins.installed.meta_commerce.services.settings import meta_settings

    msg = ''
    if request.method == 'POST' and request.POST.get('action') == 'rebuild':
        from plugins.installed.meta_commerce.services.feed import build_feed

        xml, _ = build_feed()
        cache.set(FEED_CACHE_KEY, xml, _FEED_TTL)
    elif request.method == 'POST' and request.POST.get('action') == 'catalog_push':
        from plugins.installed.meta_commerce.services.catalog_api import push_products

        stats = push_products()
        msg = (
            f'Catalog API: sent {stats.get("sent", 0)} items'
            if stats.get('ok')
            else f'Catalog push not run ({stats.get("reason", "error")}).'
        )

    verify = None
    if request.method == 'POST' and request.POST.get('action') == 'verify':
        from plugins.installed.meta_commerce.services.graph import verify_connection

        verify = verify_connection()

    diagnostics = None
    if catalog_connected():
        from plugins.installed.meta_commerce.services.catalog_api import product_diagnostics

        d = product_diagnostics()
        diagnostics = d if d.get('ok') else None

    return render(
        request,
        'meta_commerce/dashboard.html',
        {
            'active_nav': 'meta_commerce',
            'settings': meta_settings(),
            'report': coverage_report(),
            'feed_url': site_base_url().rstrip('/') + '/feeds/meta-catalog.xml',
            'recent_logs': MetaSyncLog.objects.all()[:10],
            'msg': msg,
            'has_token': has_token(),
            'catalog_connected': catalog_connected(),
            'diagnostics': diagnostics,
            'verify': verify,
        },
    )


@staff_member_required
def ads_dashboard(request):
    """Meta Ads campaign reporting + management."""
    from plugins.installed.meta_commerce.services.ads_api import (
        campaign_report,
        create_catalog_campaign,
        set_campaign_status,
    )
    from plugins.installed.meta_commerce.services.graph import ads_connected

    msg = ''
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            try:
                budget = float(request.POST.get('daily_budget') or 0)
            except (TypeError, ValueError):
                budget = 0.0
            res = create_catalog_campaign(
                name=(request.POST.get('name') or '').strip()[:120], daily_budget=budget
            )
            msg = (
                'Catalog campaign created (paused — review it in Ads Manager).'
                if res.get('ok')
                else f'Create failed: {res.get("reason")}'
            )
        elif action == 'sync_audience':
            from plugins.installed.meta_commerce.services.audiences import sync_audience

            res = sync_audience(request.POST.get('segment', ''))
            msg = (
                f'Synced {res["uploaded"]} hashed emails to the {res["segment"]} audience.'
                if res.get('ok')
                else f'Audience sync failed: {res.get("reason")}'
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
        'meta_commerce/ads.html',
        {
            'active_nav': 'meta_commerce',
            'connected': ads_connected(),
            'report': report,
            'days': days,
            'msg': msg,
        },
    )
