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

    if request.method == 'POST' and request.POST.get('action') == 'rebuild':
        from plugins.installed.google_shopping.services.feed import build_feed

        xml, _ = build_feed()
        cache.set(FEED_CACHE_KEY, xml, _FEED_TTL)

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
        },
    )
