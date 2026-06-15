"""Google Shopping HTTP surface: public feed endpoint + dashboard."""

from __future__ import annotations

from django.core.cache import cache
from django.http import HttpResponse

from morpheus.views import render, staff_member_required

FEED_CACHE_KEY = 'google_shopping:feed:v1'
_FEED_TTL = 60 * 60  # 1h; busted on product change via the cache key bump


def google_merchant_feed(request):
    """Public Merchant Center feed at /feeds/google-merchant.xml (cached)."""
    from plugins.installed.google_shopping.services.settings import feed_settings

    if not feed_settings().enabled:
        return HttpResponse('Feed disabled', status=404, content_type='text/plain')

    xml = cache.get(FEED_CACHE_KEY)
    if xml is None:
        from plugins.installed.google_shopping.services.feed import build_feed

        xml, _stats = build_feed()
        cache.set(FEED_CACHE_KEY, xml, _FEED_TTL)
    return HttpResponse(xml, content_type='application/xml; charset=utf-8')


@staff_member_required
def dashboard(request):
    """Feed status + coverage report + submit URL."""
    from core.utils.site import site_base_url
    from plugins.installed.google_shopping.models import GoogleSyncLog
    from plugins.installed.google_shopping.services.coverage import coverage_report
    from plugins.installed.google_shopping.services.settings import feed_settings

    sync_msg = ''
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'rebuild':
            from plugins.installed.google_shopping.services.feed import build_feed

            xml, _ = build_feed()
            cache.set(FEED_CACHE_KEY, xml, _FEED_TTL)
        elif action == 'content_push':
            from plugins.installed.google_shopping.services.content_api import push_products

            stats = push_products()
            sync_msg = (
                f'Content API: sent {stats.get("sent", 0)} products'
                if stats.get('ok')
                else f'Content API not run ({stats.get("reason", "error")}). Connect Google in settings.'
            )

    report = coverage_report()
    return render(
        request,
        'google_shopping/dashboard.html',
        {
            'active_nav': 'google_shopping',
            'settings': feed_settings(),
            'report': report,
            'feed_url': site_base_url().rstrip('/') + '/feeds/google-merchant.xml',
            'recent_logs': GoogleSyncLog.objects.all()[:10],
            'sync_msg': sync_msg,
            'content_connected': _content_connected(),
        },
    )


def _content_connected() -> bool:
    from plugins.installed.google_shopping.services.google_auth import is_connected
    from plugins.installed.google_shopping.services.settings import raw_config

    return bool(is_connected() and (raw_config().get('merchant_id') or '').strip())


@staff_member_required
def ads_dashboard(request):
    """Google Ads campaign reporting + management."""
    from plugins.installed.google_shopping.services.ads_api import (
        ads_connected,
        campaign_report,
        set_campaign_status,
    )

    msg = ''
    if request.method == 'POST':
        cid = request.POST.get('campaign_id', '')
        action = request.POST.get('action')
        if cid and action in ('ENABLED', 'PAUSED'):
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
        'google_shopping/ads.html',
        {
            'active_nav': 'google_shopping',
            'connected': ads_connected(),
            'report': report,
            'days': days,
            'msg': msg,
        },
    )
