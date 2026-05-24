"""Cloudflare admin dashboard views.

URL roots all live under /dashboard/cloudflare/ via register_urls in
plugin.py. Sidebar surfaces via DashboardPage entries with url= set so
they go through the canonical /dashboard/cloudflare/* path.
"""
from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render

logger = logging.getLogger('morpheus.cloudflare')


def _install_graphql_cache_rule(zone) -> None:
    """Idempotently install a CF Cache Rule that caches anonymous
    POST /graphql/ responses. Without this rule, the s-maxage header
    we emit from the GraphQL view is ignored (CF doesn't cache POST
    by default).

    The expression matches POST /graphql/ with no Authorization
    header AND no sessionid cookie, so logged-in dashboard queries
    stay uncached. Per-response cache-key includes the body so
    different queries don't collide.
    """
    from plugins.installed.cloudflare.services import _client_for, CloudflareError

    cf = _client_for(zone)
    DESC = 'Morpheus — cache anonymous GraphQL POSTs'
    rule_body = {
        'description': DESC,
        'expression': (
            '(http.request.uri.path eq "/graphql/" and '
            'http.request.method eq "POST" and '
            'not http.request.headers["authorization"][0] in {"present"})'
        ),
        'action': 'set_cache_settings',
        'action_parameters': {
            'cache': True,
            'edge_ttl': {'mode': 'respect_origin', 'default': 300},
            'browser_ttl': {'mode': 'override_origin', 'default': 0},
            'cache_key': {
                'ignore_query_strings_order': True,
                'cache_deception_armor': True,
            },
            'origin_cache_control': True,
            'respect_strong_etags': True,
        },
        'enabled': True,
    }

    # Read existing ruleset, replace any rule with the same description,
    # or append.
    try:
        existing = (cf.get_cache_ruleset(zone.zone_id).get('result') or {}).get('rules') or []
    except CloudflareError:
        existing = []
    rules = [r for r in existing if r.get('description') != DESC]
    rules.append(rule_body)
    cf.put_cache_ruleset(zone.zone_id, rules)


def _trail(*items):
    trail = [
        {'label': 'Dashboard', 'url': '/dashboard/'},
        {'label': 'Cloudflare', 'url': '/dashboard/cloudflare/'},
    ]
    for item in items:
        trail.append(item if isinstance(item, dict) else {'label': str(item)})
    return trail


@staff_member_required
def overview(request):
    """Account list + last-purge feed. Entry point for the CF surface."""
    from plugins.installed.cloudflare.models import (
        CacheInvalidation, CloudflareAccount, CloudflareZone,
    )

    if request.method == 'POST' and request.POST.get('action') == 'add_account':
        label = (request.POST.get('label') or 'default').strip()[:100]
        token = (request.POST.get('api_token') or '').strip()
        if not token:
            messages.error(request, 'API token is required.')
        else:
            from plugins.installed.cloudflare.services import (
                CloudflareClient, CloudflareError,
            )
            try:
                CloudflareClient(api_token=token).verify_token()
            except CloudflareError as e:
                messages.error(request, f'Token verify failed: {e}')
                return HttpResponseRedirect(request.path)
            CloudflareAccount.objects.create(
                label=label, api_token=token,
                account_id=(request.POST.get('account_id') or '').strip(),
            )
            messages.success(request, f'Account "{label}" added — token verified.')
        return HttpResponseRedirect(request.path)

    accounts = list(CloudflareAccount.objects.prefetch_related('zones').order_by('label'))
    recent_purges = list(
        CacheInvalidation.objects.select_related('zone')
        .order_by('-created_at')[:20]
    )
    return render(request, 'cloudflare/overview.html', {
        'accounts': accounts,
        'recent_purges': recent_purges,
        'zone_count': CloudflareZone.objects.filter(is_active=True).count(),
        'active_nav': 'cloudflare',
        'breadcrumb_trail': _trail(),
    })


@staff_member_required
def account_sync(request, account_id):
    """Pull zones for one account from the CF API and upsert into our DB."""
    from plugins.installed.cloudflare.models import CloudflareAccount
    from plugins.installed.cloudflare.services import (
        CloudflareError, sync_zones,
    )

    acct = get_object_or_404(CloudflareAccount, pk=account_id)
    if request.method != 'POST':
        return HttpResponseRedirect('/dashboard/cloudflare/')
    try:
        summary = sync_zones(acct)
        messages.success(
            request,
            f'Synced {summary["total"]} zone(s) from Cloudflare '
            f'({summary["created"]} new, {summary["updated"]} updated).',
        )
    except CloudflareError as e:
        messages.error(request, f'Cloudflare sync failed: {e}')
    return HttpResponseRedirect('/dashboard/cloudflare/')


@staff_member_required
def zones_list(request):
    """List every zone known to Morpheus across all accounts."""
    from plugins.installed.cloudflare.models import CloudflareZone

    zones = list(
        CloudflareZone.objects.select_related('account', 'channel')
        .order_by('domain')[:200]
    )
    return render(request, 'cloudflare/zones_list.html', {
        'zones': zones,
        'active_nav': 'cloudflare',
        'breadcrumb_trail': _trail({'label': 'Zones'}),
    })


@staff_member_required
def zone_detail(request, zone_id):
    """Per-zone dashboard: settings + recent purges + analytics summary."""
    from plugins.installed.cloudflare.models import CloudflareZone
    from plugins.installed.cloudflare.services import (
        CloudflareError, analytics_summary, patch_zone_setting,
        zone_settings_map,
    )

    zone = get_object_or_404(CloudflareZone, pk=zone_id)

    if request.method == 'POST':
        action = request.POST.get('action') or 'toggle_setting'
        try:
            if action == 'toggle_setting':
                setting_id = (request.POST.get('setting_id') or '').strip()
                raw_value = (request.POST.get('value') or '').strip()
                patch_zone_setting(zone, setting_id, raw_value)
                messages.success(request, f'Set {setting_id} = {raw_value}.')
            elif action == 'toggle_tiered_cache':
                from plugins.installed.cloudflare.services import _client_for
                _client_for(zone).patch_tiered_cache(zone.zone_id, request.POST.get('value', 'on'))
                messages.success(request, f'Tiered Cache → {request.POST.get("value")}.')
            elif action == 'toggle_cache_reserve':
                from plugins.installed.cloudflare.services import _client_for
                _client_for(zone).patch_cache_reserve(zone.zone_id, request.POST.get('value', 'on'))
                messages.success(request, f'Cache Reserve → {request.POST.get("value")}.')
            elif action == 'toggle_argo':
                from plugins.installed.cloudflare.services import _client_for
                _client_for(zone).patch_argo_smart_routing(zone.zone_id, request.POST.get('value', 'on'))
                messages.success(request, f'Argo Smart Routing → {request.POST.get("value")}.')
            elif action == 'install_graphql_cache_rule':
                _install_graphql_cache_rule(zone)
                messages.success(
                    request,
                    'Cache Rule installed — anonymous POST /graphql/ is now '
                    'cached at the edge.',
                )
        except CloudflareError as e:
            messages.error(request, f'CF API error: {e}')
        return HttpResponseRedirect(request.path)

    # Pull live settings + analytics; fall through gracefully on API errors
    # so a busted token doesn't 500 the page.
    settings_map: dict = {}
    settings_error: str = ''
    try:
        settings_map = zone_settings_map(zone)
    except CloudflareError as e:
        settings_error = str(e)
    except Exception as e:  # noqa: BLE001
        settings_error = f'{type(e).__name__}: {e}'

    summary = analytics_summary(zone, days=7) if not settings_error else {}

    # Top-level toggles — Tiered Cache + Cache Reserve + Argo. These live on
    # their own endpoints, not /zones/{id}/settings, so they need separate
    # reads.
    from plugins.installed.cloudflare.services import _client_for
    tiered_cache_state = ''
    cache_reserve_state = ''
    argo_state = ''
    graphql_rule_installed = False
    if not settings_error:
        try:
            cf = _client_for(zone)
            r = cf.get_tiered_cache(zone.zone_id)
            tiered_cache_state = ((r.get('result') or {}).get('value') or '')
        except Exception:  # noqa: BLE001
            pass
        try:
            r = cf.get_cache_reserve(zone.zone_id)
            cache_reserve_state = ((r.get('result') or {}).get('value') or '')
        except Exception:  # noqa: BLE001
            pass
        try:
            r = cf.get_argo_smart_routing(zone.zone_id)
            argo_state = ((r.get('result') or {}).get('value') or '')
        except Exception:  # noqa: BLE001
            pass
        try:
            existing = (cf.get_cache_ruleset(zone.zone_id).get('result') or {}).get('rules') or []
            graphql_rule_installed = any(
                'GraphQL' in (r.get('description') or '') for r in existing
            )
        except Exception:  # noqa: BLE001
            pass

    # Curated subset of settings the merchant actually wants to see.
    # Full list is 50+ — we just expose the load-bearing ones.
    notable_settings = [
        ('always_use_https', 'Always use HTTPS', 'on/off — redirect HTTP → HTTPS'),
        ('automatic_https_rewrites', 'Automatic HTTPS rewrites', 'on/off — rewrite mixed content'),
        ('brotli', 'Brotli', 'on/off — compress responses with Brotli'),
        ('http3', 'HTTP/3', 'on/off — QUIC for the storefront'),
        ('early_hints', 'Early Hints', 'on/off — 103 hints for preload'),
        ('0rtt', '0-RTT', 'on/off — TLS 1.3 0-RTT (reduces handshake latency)'),
        ('ipv6', 'IPv6 Compatibility', 'on/off'),
        ('opportunistic_encryption', 'Opportunistic Encryption', 'on/off'),
        ('min_tls_version', 'Minimum TLS version', '1.0 / 1.1 / 1.2 / 1.3'),
        ('security_level', 'Security level', 'off / essentially_off / low / medium / high / under_attack'),
        ('cache_level', 'Cache level', 'aggressive / basic / simplified'),
        ('browser_cache_ttl', 'Browser cache TTL (s)', 'seconds, 0 = respect origin'),
        ('challenge_ttl', 'Challenge TTL (s)', 'how long a CAPTCHA pass lasts'),
        ('rocket_loader', 'Rocket Loader', 'on/off (mostly deprecated)'),
        ('mirage', 'Mirage', 'on/off — mobile image optimization (paid)'),
        ('polish', 'Polish', 'off / lossless / lossy (paid)'),
        ('hotlink_protection', 'Hotlink protection', 'on/off'),
        ('email_obfuscation', 'Email obfuscation', 'on/off'),
        ('server_side_exclude', 'Server-side excludes', 'on/off'),
    ]
    settings_rows = [
        {'id': sid, 'label': label, 'help': help_text,
         'value': settings_map.get(sid, '—')}
        for sid, label, help_text in notable_settings
    ]

    recent_purges = list(
        zone.invalidations.order_by('-created_at')[:15]
    )

    return render(request, 'cloudflare/zone_detail.html', {
        'zone': zone,
        'settings_rows': settings_rows,
        'settings_error': settings_error,
        'summary': summary,
        'recent_purges': recent_purges,
        'tiered_cache_state': tiered_cache_state,
        'cache_reserve_state': cache_reserve_state,
        'argo_state': argo_state,
        'graphql_rule_installed': graphql_rule_installed,
        'active_nav': 'cloudflare',
        'breadcrumb_trail': _trail({'label': zone.domain}),
    })


@staff_member_required
def purge_form(request, zone_id):
    """Manual cache-purge UI: URL list, host list, or purge everything."""
    from plugins.installed.cloudflare.models import CloudflareZone
    from plugins.installed.cloudflare.services import (
        CloudflareError, purge_everything, purge_tags, purge_urls,
    )

    zone = get_object_or_404(CloudflareZone, pk=zone_id)

    if request.method == 'POST':
        mode = request.POST.get('mode') or 'urls'
        try:
            if mode == 'everything':
                purge_everything(
                    zone=zone, triggered_by=f'dashboard:{request.user.username}',
                )
                messages.success(request, f'Purged ALL cache for {zone.domain}.')
            elif mode == 'urls':
                raw = (request.POST.get('urls') or '').strip()
                urls = [line.strip() for line in raw.splitlines() if line.strip()][:30]
                if not urls:
                    messages.warning(request, 'No URLs supplied.')
                else:
                    purge_urls(
                        zone=zone, urls=urls,
                        triggered_by=f'dashboard:{request.user.username}',
                    )
                    messages.success(request, f'Purged {len(urls)} URL(s).')
            elif mode == 'tags':
                # CF Cache Tags — set by MorpheusGraphQLView for GraphQL
                # responses (product:<slug>, category:<slug>, graphql:query).
                # Tag-based purges require Enterprise plan OR a Cache Tag
                # rule on the zone configuration in CF.
                raw = (request.POST.get('tags') or '').strip()
                tags = [t.strip() for t in raw.replace('\n', ',').split(',') if t.strip()][:30]
                if not tags:
                    messages.warning(request, 'No tags supplied.')
                else:
                    purge_tags(
                        zone=zone, tags=tags,
                        triggered_by=f'dashboard:{request.user.username}',
                    )
                    messages.success(request, f'Purged tag(s): {", ".join(tags)}.')
            elif mode == 'hosts':
                # Wire host-level purge by reusing the underlying client.
                from plugins.installed.cloudflare.services import _record_purge
                hosts = [h.strip() for h in (request.POST.get('hosts') or '').split(',') if h.strip()][:5]
                if not hosts:
                    messages.warning(request, 'No hosts supplied.')
                else:
                    _record_purge(
                        zone=zone, scope='hosts', targets=hosts,
                        triggered_by=f'dashboard:{request.user.username}',
                        client=None,
                    )
                    messages.success(request, f'Purged host(s): {", ".join(hosts)}.')
        except CloudflareError as e:
            messages.error(request, f'CF API error: {e}')
        return HttpResponseRedirect(
            f'/dashboard/cloudflare/zones/{zone.id}/'
        )

    return render(request, 'cloudflare/purge_form.html', {
        'zone': zone,
        'active_nav': 'cloudflare',
        'breadcrumb_trail': _trail(
            {'label': zone.domain, 'url': f'/dashboard/cloudflare/zones/{zone.id}/'},
            {'label': 'Purge cache'},
        ),
    })


@staff_member_required
def analytics(request, zone_id):
    """Full analytics page for a zone (configurable window)."""
    from plugins.installed.cloudflare.models import CloudflareZone
    from plugins.installed.cloudflare.services import (
        CloudflareError, analytics_summary,
    )

    zone = get_object_or_404(CloudflareZone, pk=zone_id)
    try:
        days = max(1, min(int(request.GET.get('days') or 7), 30))
    except (TypeError, ValueError):
        days = 7

    summary = {}
    error = ''
    try:
        summary = analytics_summary(zone, days=days)
        if 'error' in summary:
            error = summary['error']
            summary = {}
    except CloudflareError as e:
        error = str(e)
    except Exception as e:  # noqa: BLE001
        error = f'{type(e).__name__}: {e}'

    # Derived metrics
    cache_hit_ratio = 0
    if summary.get('requests_total'):
        cache_hit_ratio = round(
            100 * (summary.get('requests_cached') or 0) / summary['requests_total'], 1,
        )
    bw_gb = (summary.get('bandwidth_bytes') or 0) / (1024 ** 3)

    return render(request, 'cloudflare/analytics.html', {
        'zone': zone,
        'days': days,
        'summary': summary,
        'cache_hit_ratio': cache_hit_ratio,
        'bandwidth_gb': round(bw_gb, 2),
        'error': error,
        'active_nav': 'cloudflare',
        'breadcrumb_trail': _trail(
            {'label': zone.domain, 'url': f'/dashboard/cloudflare/zones/{zone.id}/'},
            {'label': 'Analytics'},
        ),
    })


@staff_member_required
def invalidations_log(request):
    """Cross-zone purge audit log."""
    from plugins.installed.cloudflare.models import CacheInvalidation

    rows = list(
        CacheInvalidation.objects.select_related('zone')
        .order_by('-created_at')[:200]
    )
    return render(request, 'cloudflare/invalidations.html', {
        'rows': rows,
        'active_nav': 'cloudflare',
        'breadcrumb_trail': _trail({'label': 'Purge log'}),
    })
