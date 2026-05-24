"""Cloudflare API client + service helpers.

The HTTP layer is wrapped in a small `CloudflareClient` so tests can inject a
fake. Each public service function logs a `CacheInvalidation` audit row.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable, Sequence

from django.db import DatabaseError
from django.utils import timezone

logger = logging.getLogger('morpheus.cloudflare')


class CloudflareError(RuntimeError):
    """Raised when the Cloudflare API returns a non-success response."""


class CloudflareClient:
    """Thin Cloudflare API v4 client, scoped to a single account.

    Methods follow the same shape: hit `_request`, raise CloudflareError
    on non-success, return the full JSON body. Callers pull `result`,
    `result_info`, etc. as needed. Session injectable for tests.
    """

    BASE_URL = 'https://api.cloudflare.com/client/v4'

    def __init__(self, *, api_token: str, session: Any | None = None) -> None:
        self._token = api_token
        self._session = session

    def _request(self, method: str, path: str,
                 *, payload: dict | None = None, params: dict | None = None) -> dict:
        if self._session is not None:
            return self._session.request(method, path, payload=payload, params=params)
        import requests

        resp = requests.request(
            method,
            f'{self.BASE_URL}{path}',
            headers={
                'Authorization': f'Bearer {self._token}',
                'Content-Type': 'application/json',
            },
            json=payload,
            params=params,
            timeout=15,
        )
        body = resp.json() if resp.content else {}
        if not body.get('success', False):
            errors = body.get('errors') or [{'message': f'HTTP {resp.status_code}'}]
            raise CloudflareError(
                f'Cloudflare API error ({resp.status_code}): {errors}'
            )
        return body

    def _get(self, path: str, params: dict | None = None) -> dict:
        return self._request('GET', path, params=params)

    def _post(self, path: str, payload: dict | None) -> dict:
        return self._request('POST', path, payload=payload or {})

    def _patch(self, path: str, payload: dict | None) -> dict:
        return self._request('PATCH', path, payload=payload or {})

    # ── Token / account ──────────────────────────────────────────────────

    def verify_token(self) -> dict:
        """Confirms the API token is valid and returns its scope summary."""
        return self._get('/user/tokens/verify')

    def list_accounts(self) -> dict:
        return self._get('/accounts', params={'per_page': 50})

    # ── Zones ────────────────────────────────────────────────────────────

    def list_zones(self, account_id: str | None = None) -> dict:
        params = {'per_page': 50}
        if account_id:
            params['account.id'] = account_id
        return self._get('/zones', params=params)

    def get_zone(self, zone_id: str) -> dict:
        return self._get(f'/zones/{zone_id}')

    def get_zone_settings(self, zone_id: str) -> dict:
        return self._get(f'/zones/{zone_id}/settings')

    def patch_zone_setting(self, zone_id: str, setting_id: str, value: Any) -> dict:
        return self._patch(f'/zones/{zone_id}/settings/{setting_id}', {'value': value})

    # ── Analytics ────────────────────────────────────────────────────────

    def get_analytics_dashboard(self, zone_id: str, since: str = '-10080',
                                until: str = '0') -> dict:
        """Dashboard summary (requests, bandwidth, threats, cache stats).

        `since` / `until` are negative minutes-from-now per CF docs:
          since=-1440 → last 24h; since=-10080 → last 7 days.
        """
        return self._get(
            f'/zones/{zone_id}/analytics/dashboard',
            params={'since': since, 'until': until, 'continuous': 'true'},
        )

    # ── Firewall / WAF events ───────────────────────────────────────────

    def list_firewall_events(self, zone_id: str, limit: int = 50) -> dict:
        # GraphQL is the modern endpoint but the legacy REST one works
        # for an overview and doesn't require account-scoped tokens.
        return self._get(f'/zones/{zone_id}/security/events',
                          params={'per_page': limit})

    # ── DNS ──────────────────────────────────────────────────────────────

    def list_dns_records(self, zone_id: str) -> dict:
        return self._get(f'/zones/{zone_id}/dns_records', params={'per_page': 100})

    # ── Cache ────────────────────────────────────────────────────────────

    def purge_cache(
        self,
        zone_id: str,
        *,
        urls: Sequence[str] | None = None,
        tags: Sequence[str] | None = None,
        hosts: Sequence[str] | None = None,
        purge_everything: bool = False,
    ) -> dict:
        if purge_everything:
            payload = {'purge_everything': True}
        else:
            payload = {}
            if urls:
                payload['files'] = list(urls)
            if tags:
                payload['tags'] = list(tags)
            if hosts:
                payload['hosts'] = list(hosts)
            if not payload:
                raise ValueError('At least one of urls / tags / hosts must be provided.')
        return self._post(f'/zones/{zone_id}/purge_cache', payload)


def _client_for(zone) -> CloudflareClient:
    return CloudflareClient(api_token=zone.account.api_token)


def purge_urls(
    *,
    zone,
    urls: Iterable[str],
    triggered_by: str = '',
    client: CloudflareClient | None = None,
) -> 'CacheInvalidation':  # noqa: F821
    return _record_purge(
        zone=zone,
        scope='urls',
        targets=list(urls),
        triggered_by=triggered_by,
        client=client,
    )


def purge_tags(
    *,
    zone,
    tags: Iterable[str],
    triggered_by: str = '',
    client: CloudflareClient | None = None,
) -> 'CacheInvalidation':  # noqa: F821
    return _record_purge(
        zone=zone,
        scope='tags',
        targets=list(tags),
        triggered_by=triggered_by,
        client=client,
    )


def purge_everything(
    *,
    zone,
    triggered_by: str = '',
    client: CloudflareClient | None = None,
) -> 'CacheInvalidation':  # noqa: F821
    return _record_purge(
        zone=zone,
        scope='purge_everything',
        targets=[],
        triggered_by=triggered_by,
        client=client,
    )


def _record_purge(*, zone, scope, targets, triggered_by, client):
    from plugins.installed.cloudflare.models import CacheInvalidation

    inv = CacheInvalidation.objects.create(
        zone=zone, scope=scope, targets=targets, triggered_by=triggered_by[:120],
        status='pending',
    )

    cf = client or _client_for(zone)
    try:
        if scope == 'purge_everything':
            response = cf.purge_cache(zone.zone_id, purge_everything=True)
        elif scope == 'urls':
            response = cf.purge_cache(zone.zone_id, urls=targets)
        elif scope == 'tags':
            response = cf.purge_cache(zone.zone_id, tags=targets)
        elif scope == 'hosts':
            response = cf.purge_cache(zone.zone_id, hosts=targets)
        else:
            raise ValueError(f'Unknown scope: {scope}')
    except CloudflareError as e:
        inv.status = 'failed'
        inv.error_message = str(e)[:1000]
        inv.save(update_fields=['status', 'error_message'])
        logger.warning('cloudflare: purge failed for %s: %s', zone.domain, e)
        return inv
    except Exception as e:  # noqa: BLE001 — logged with traceback; never block hook chain
        inv.status = 'failed'
        inv.error_message = str(e)[:1000]
        inv.save(update_fields=['status', 'error_message'])
        logger.error('cloudflare: unexpected purge error for %s: %s', zone.domain, e, exc_info=True)
        return inv

    inv.status = 'succeeded'
    inv.response = response
    inv.save(update_fields=['status', 'response'])

    try:
        zone.last_purge_at = timezone.now()
        zone.save(update_fields=['last_purge_at'])
    except DatabaseError:
        pass

    return inv


def sync_zones(account) -> dict:
    """Pull every zone the account's token can see from the CF API and
    upsert into our `CloudflareZone` table. Returns a summary dict.

    Idempotent — re-running updates existing rows with the latest
    metadata (status, type, paused) and inserts any new zones.
    """
    from plugins.installed.cloudflare.models import CloudflareZone

    cf = CloudflareClient(api_token=account.api_token)
    try:
        body = cf.list_zones(account_id=account.account_id or None)
    except CloudflareError as e:
        logger.warning('cloudflare: sync_zones failed for account %s: %s',
                       account.label, e)
        raise

    zones = body.get('result') or []
    created = 0
    updated = 0
    for z in zones:
        zone_id = z.get('id') or ''
        domain = z.get('name') or ''
        if not zone_id or not domain:
            continue
        obj, was_created = CloudflareZone.objects.update_or_create(
            account=account, zone_id=zone_id,
            defaults={'domain': domain, 'is_active': True},
        )
        if was_created:
            created += 1
        else:
            updated += 1
    return {'total': len(zones), 'created': created, 'updated': updated}


def zone_settings_map(zone) -> dict:
    """Return zone settings as `{setting_id: value}` for easy template
    consumption. Caller should wrap in a try (auth errors raise)."""
    cf = _client_for(zone)
    body = cf.get_zone_settings(zone.zone_id)
    return {s['id']: s.get('value') for s in (body.get('result') or [])}


def patch_zone_setting(zone, setting_id: str, value: Any) -> dict:
    """Toggle / set one zone-level feature. Returns the API response."""
    cf = _client_for(zone)
    return cf.patch_zone_setting(zone.zone_id, setting_id, value)


def analytics_summary(zone, days: int = 7) -> dict:
    """Return a flat summary of the dashboard metrics over the last N
    days. Falls back to empty dict on auth error so the template can
    still render gracefully."""
    cf = _client_for(zone)
    since = -int(max(1, days) * 24 * 60)
    try:
        body = cf.get_analytics_dashboard(zone.zone_id, since=str(since), until='0')
    except CloudflareError as e:
        logger.warning('cloudflare: analytics failed for %s: %s', zone.domain, e)
        return {'error': str(e)}
    totals = (body.get('result') or {}).get('totals') or {}
    return {
        'requests_total': (totals.get('requests') or {}).get('all', 0),
        'requests_cached': (totals.get('requests') or {}).get('cached', 0),
        'bandwidth_bytes': (totals.get('bandwidth') or {}).get('all', 0),
        'threats': (totals.get('threats') or {}).get('all', 0),
        'pageviews': (totals.get('pageviews') or {}).get('all', 0),
        'uniques': (totals.get('uniques') or {}).get('all', 0),
    }


def purge_for_product_update(product) -> list:
    """Auto-purge cache for any zone with `auto_purge_on_product_update=True`.

    Fires TWO purges per zone:

      1. URL purge for /p/<slug> and /products/<slug> — invalidates the
         storefront PDP HTML responses CF cached.
      2. Tag purge for `product:<slug>` (and `product:<id>`) —
         invalidates every GraphQL response that mentioned this product
         identifier. The tags come from
         MorpheusGraphQLView._extract_entity_tags, which emits
         `Cache-Tag: product:<slug>` on every query whose AST resolved
         a productBySlug / productById field referencing this product.
    """
    from plugins.installed.cloudflare.models import CloudflareZone

    invalidations = []
    qs = CloudflareZone.objects.filter(
        is_active=True, auto_purge_on_product_update=True,
    ).select_related('account')
    paths = [f'/p/{product.slug}', f'/products/{product.slug}']
    tags = [f'product:{product.slug}']
    if getattr(product, 'id', None):
        tags.append(f'product:{product.id}')

    for zone in qs:
        urls = [f'https://{zone.domain}{path}' for path in paths]
        try:
            invalidations.append(
                purge_urls(zone=zone, urls=urls, triggered_by=f'product:{product.id}')
            )
        except Exception as e:  # noqa: BLE001 — never raise from a hook
            logger.warning('cloudflare: purge_for_product_update URL failed: %s', e)
        try:
            invalidations.append(
                purge_tags(zone=zone, tags=tags, triggered_by=f'product:{product.id}')
            )
        except Exception as e:  # noqa: BLE001
            logger.warning('cloudflare: purge_for_product_update tag failed: %s', e)
    return invalidations


def purge_for_category_update(category) -> list:
    """Tag-based companion to the URL-based hook in plugin.py.

    Tag namespace: `category:<slug>` + `category:<id>`. The plugin
    hook layer fires URL purges for /c/<slug>; this complements with
    tag purges that drop matching GraphQL responses.
    """
    from plugins.installed.cloudflare.models import CloudflareZone

    invalidations = []
    qs = CloudflareZone.objects.filter(
        is_active=True, auto_purge_on_collection_update=True,
    ).select_related('account')
    slug = getattr(category, 'slug', '') or ''
    pk = getattr(category, 'id', '') or getattr(category, 'pk', '') or ''
    tags = [t for t in (f'category:{slug}', f'category:{pk}') if not t.endswith(':')]
    if not tags:
        return invalidations

    for zone in qs:
        try:
            invalidations.append(
                purge_tags(zone=zone, tags=tags, triggered_by=f'category:{pk}')
            )
        except Exception as e:  # noqa: BLE001
            logger.warning('cloudflare: purge_for_category_update tag failed: %s', e)
    return invalidations
