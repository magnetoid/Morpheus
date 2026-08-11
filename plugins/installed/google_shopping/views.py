"""Google Shopping HTTP surface: public feed endpoint + dashboard."""

from __future__ import annotations

from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import redirect

from morpheus.app.views import render, staff_member_required

_OAUTH_CALLBACK_PATH = '/dashboard/apps/google_shopping/oauth-callback/'

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
    from morpheus.core import site_base_url
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
    diagnostics = None
    if _content_connected():
        from plugins.installed.google_shopping.services.content_api import product_statuses

        d = product_statuses()
        diagnostics = d if d.get('ok') else None
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
            'diagnostics': diagnostics,
            'connect': _connect_state(),
        },
    )


def _content_connected() -> bool:
    from plugins.installed.google_shopping.services.google_auth import is_connected
    from plugins.installed.google_shopping.services.settings import raw_config

    return bool(is_connected() and (raw_config().get('merchant_id') or '').strip())


def _connect_state() -> dict:
    """Where the merchant is in the connect flow, for the dashboard CTA."""
    from plugins.installed.google_shopping.services.google_auth import has_client, is_connected

    return {'has_client': has_client(), 'is_connected': is_connected()}


@staff_member_required
def ads_dashboard(request):
    """Google Ads campaign reporting + management."""
    from plugins.installed.google_shopping.services.ads_api import (
        ads_connected,
        campaign_report,
        create_shopping_campaign,
        set_campaign_status,
    )
    from plugins.installed.google_shopping.services.settings import raw_config

    msg = ''
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            try:
                budget = float(request.POST.get('daily_budget') or 0)
            except (TypeError, ValueError):
                budget = 0.0
            res = create_shopping_campaign(
                name=(request.POST.get('name') or '').strip()[:120],
                daily_budget=budget,
                merchant_id=(raw_config().get('merchant_id') or '').strip(),
            )
            msg = (
                'Shopping campaign created (paused — review it in Google Ads).'
                if res.get('ok')
                else f'Create failed: {res.get("reason")}'
            )
        else:
            cid = request.POST.get('campaign_id', '')
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


@staff_member_required
def oauth_start(request):
    """Kick off the Google consent flow (Content API + Ads)."""
    import secrets

    from plugins.installed.google_shopping.services.google_auth import authorize_url

    state = secrets.token_urlsafe(24)
    request.session['gs_oauth_state'] = state
    url = authorize_url(request.build_absolute_uri(_OAUTH_CALLBACK_PATH), state=state)
    if not url:
        return redirect('/dashboard/settings/channels/')
    return redirect(url)


@staff_member_required
def oauth_callback(request):
    """Google redirects here with ?code=… — exchange it for a refresh token.

    The `state` must match the value we stored in the session at oauth_start,
    or we refuse — this blocks login-CSRF (connecting the store to an
    attacker-controlled Google account)."""
    from plugins.installed.google_shopping.services.google_auth import exchange_code

    dest = '/dashboard/apps/google_shopping/overview/'
    expected = request.session.pop('gs_oauth_state', None)
    got = request.GET.get('state', '')
    if not expected or got != expected:
        return redirect(f'{dest}?connected=0&error=state')

    code = request.GET.get('code', '')
    res = (
        exchange_code(code, request.build_absolute_uri(_OAUTH_CALLBACK_PATH))
        if code
        else {'ok': False, 'reason': request.GET.get('error', 'no_code')}
    )
    return redirect(f'{dest}?connected={"1" if res.get("ok") else "0"}')
