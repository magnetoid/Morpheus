"""Cloudflare API client + service helpers.

The HTTP layer is wrapped in a small `CloudflareClient` so tests can inject a
fake. Each public service function logs a `CacheInvalidation` audit row.
"""

# Lazy (in-function) imports are the established pattern in this plugin.
# ruff: noqa: PLC0415
from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from typing import Any

from django.db import DatabaseError
from django.utils import timezone

logger = logging.getLogger('morpheus.cloudflare')

# Cache-relevant zone settings surfaced + edited on the unified Caching page
# (admin_dashboard.settings_caching). zone_detail owns everything else
# (security / TLS / DNS / firewall + the advanced edge toggles). Single home
# per ADR 0003/0005: these six live ONLY on the Caching page.
CACHE_SETTINGS: list[tuple[str, str, str]] = [
    ('cache_level', 'Cache level', 'aggressive / basic / simplified'),
    ('browser_cache_ttl', 'Browser cache TTL (s)', 'seconds, 0 = respect origin'),
    ('brotli', 'Brotli', 'on / off — compress responses with Brotli'),
    ('early_hints', 'Early Hints', 'on / off — 103 hints for preload'),
    ('polish', 'Polish', 'off / lossless / lossy — image optimization (paid)'),
    ('mirage', 'Mirage', 'on / off — mobile image optimization (paid)'),
]
CACHE_SETTING_IDS = frozenset(sid for sid, _, _ in CACHE_SETTINGS)


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

    def _request(
        self, method: str, path: str, *, payload: dict | None = None, params: dict | None = None
    ) -> dict:
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
            raise CloudflareError(f'Cloudflare API error ({resp.status_code}): {errors}')
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

    def get_analytics_dashboard(
        self, zone_id: str, since: str = '-10080', until: str = '0'
    ) -> dict:
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
        return self._get(f'/zones/{zone_id}/security/events', params={'per_page': limit})

    # ── DNS ──────────────────────────────────────────────────────────────

    def list_dns_records(self, zone_id: str) -> dict:
        return self._get(f'/zones/{zone_id}/dns_records', params={'per_page': 100})

    def create_dns_record(
        self,
        zone_id: str,
        *,
        type: str,
        name: str,
        content: str,
        ttl: int = 1,
        proxied: bool = False,
    ) -> dict:
        """Create a new DNS record. ttl=1 means 'auto' per CF docs."""
        return self._post(
            f'/zones/{zone_id}/dns_records',
            {
                'type': type,
                'name': name,
                'content': content,
                'ttl': ttl,
                'proxied': proxied,
            },
        )

    def delete_dns_record(self, zone_id: str, record_id: str) -> dict:
        return self._request('DELETE', f'/zones/{zone_id}/dns_records/{record_id}')

    # ── Bot Fight Mode + always-use-HTTPS (one-line security wins) ───────

    def get_bot_fight_mode(self, zone_id: str) -> dict:
        return self._get(f'/zones/{zone_id}/bot_management')

    def patch_bot_fight_mode(self, zone_id: str, enabled: bool) -> dict:
        return self._request(
            'PUT',
            f'/zones/{zone_id}/bot_management',
            payload={
                'fight_mode': bool(enabled),
            },
        )

    # ── Speed / cache top-level toggles ──────────────────────────────────

    def get_tiered_cache(self, zone_id: str) -> dict:
        """Tiered Cache (smart topology) status."""
        return self._get(f'/zones/{zone_id}/cache/tiered_cache_smart_topology_enable')

    def patch_tiered_cache(self, zone_id: str, value: str) -> dict:
        """value: 'on' / 'off' — flips smart-topology Tiered Cache."""
        return self._patch(
            f'/zones/{zone_id}/cache/tiered_cache_smart_topology_enable',
            {'value': value},
        )

    def get_cache_reserve(self, zone_id: str) -> dict:
        """Cache Reserve status. Eligible objects need Content-Length + TTL ≥ 10h."""
        return self._get(f'/zones/{zone_id}/cache/cache_reserve')

    def patch_cache_reserve(self, zone_id: str, value: str) -> dict:
        """value: 'on' / 'off'. ALWAYS pair with Tiered Cache to keep write costs down."""
        return self._patch(
            f'/zones/{zone_id}/cache/cache_reserve',
            {'value': value},
        )

    def get_argo_smart_routing(self, zone_id: str) -> dict:
        return self._get(f'/zones/{zone_id}/argo/smart_routing')

    def patch_argo_smart_routing(self, zone_id: str, value: str) -> dict:
        return self._patch(f'/zones/{zone_id}/argo/smart_routing', {'value': value})

    # ── Cache Rules (Rulesets API — replaces legacy Page Rules) ─────────

    def get_cache_ruleset(self, zone_id: str) -> dict:
        """Read the http_request_cache_settings ruleset entrypoint."""
        return self._get(f'/zones/{zone_id}/rulesets/phases/http_request_cache_settings/entrypoint')

    def put_cache_ruleset(self, zone_id: str, rules: list[dict]) -> dict:
        """Replace the entire cache-settings ruleset with `rules`."""
        return self._request(
            'PUT',
            f'/zones/{zone_id}/rulesets/phases/http_request_cache_settings/entrypoint',
            payload={'rules': rules},
        )

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
) -> CacheInvalidation:  # noqa: F821
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
) -> CacheInvalidation:  # noqa: F821
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
) -> CacheInvalidation:  # noqa: F821
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
        zone=zone,
        scope=scope,
        targets=targets,
        triggered_by=triggered_by[:120],
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
        logger.warning('cloudflare: sync_zones failed for account %s: %s', account.label, e)
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
            account=account,
            zone_id=zone_id,
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
        is_active=True,
        auto_purge_on_product_update=True,
    ).select_related('account')
    # The routes the storefront actually serves. This used to purge
    # `/p/<slug>` and `/products/<slug>` — the first is the CMS page route and
    # the second is missing its trailing slash — and a Cloudflare file purge is
    # exact-URL, so product HTML had effectively never been purged.
    paths = [f'/products/{product.slug}/']
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
    """Tag-based companion to the URL-based hook in app.py.

    Tag namespace: `category:<slug>` + `category:<id>`. The plugin
    hook layer fires URL purges for /c/<slug>; this complements with
    tag purges that drop matching GraphQL responses.
    """
    from plugins.installed.cloudflare.models import CloudflareZone

    invalidations = []
    qs = CloudflareZone.objects.filter(
        is_active=True,
        auto_purge_on_collection_update=True,
    ).select_related('account')
    slug = getattr(category, 'slug', '') or ''
    pk = getattr(category, 'id', '') or getattr(category, 'pk', '') or ''
    tags = [t for t in (f'category:{slug}', f'category:{pk}') if not t.endswith(':')]
    if not tags:
        return invalidations

    for zone in qs:
        try:
            invalidations.append(purge_tags(zone=zone, tags=tags, triggered_by=f'category:{pk}'))
        except Exception as e:  # noqa: BLE001
            logger.warning('cloudflare: purge_for_category_update tag failed: %s', e)
    return invalidations


# --- Cloudflare Turnstile (bot protection for public forms) ----------------


def _turnstile_config() -> dict:
    """Cloudflare plugin config (Turnstile keys + toggle) from PluginConfig."""
    try:
        from plugins.registry import app_registry

        p = app_registry.get('cloudflare')
        return (p.get_config() if p else {}) or {}
    except Exception:  # noqa: BLE001
        return {}


def turnstile_site_key() -> str:
    """The Turnstile site key to render, or '' when disabled/unset."""
    cfg = _turnstile_config()
    if not cfg.get('turnstile_enabled'):
        return ''
    return (cfg.get('turnstile_site_key') or '').strip()


SITEVERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
# Cloudflare's longest token; anything longer is refused before the call.
TOKEN_MAX_LENGTH = 2048
_LOCAL_HOSTS = frozenset({'localhost', '127.0.0.1', '::1', '[::1]'})
# Cloudflare's published test secrets (always pass / always fail / token spent):
# their answers name no real page, so the hostname check cannot apply, and a live
# store set up with one is not protected at all (`turnstile_health`).
TEST_SECRETS = frozenset(
    {
        '1x0000000000000000000000000000000AA',
        '2x0000000000000000000000000000000AA',
        '3x0000000000000000000000000000000AA',
    }
)


def turnstile_action(form: str) -> str:
    """The widget's `data-action` for a kind of form; the answer must name it back."""
    return (form or '').replace('_', '-')[:32]


def _client_ip(request) -> str:
    return (
        (request.META.get('HTTP_CF_CONNECTING_IP') or request.META.get('REMOTE_ADDR', ''))
        .split(',')[0]
        .strip()
    )


def _expected_hostnames(request) -> set[str]:
    """The hosts a token may have been solved on: the one the form was posted to
    and the store's own address. Never a local host in production, because a
    widget set up with Spin allows localhost and 127.0.0.1 for development."""
    from urllib.parse import urlsplit  # noqa: PLC0415

    from django.conf import settings  # noqa: PLC0415

    hosts: set[str] = set()
    try:
        hosts.add(request.get_host().rsplit(':', 1)[0].lower())
    except Exception as e:  # noqa: BLE001 — a host Django refuses names nothing
        logger.debug('cloudflare: no request host for Turnstile: %s', e)
    try:
        from core.utils.site import site_base_url  # noqa: PLC0415

        base = (urlsplit(site_base_url()).hostname or '').lower()
        if base:
            hosts.add(base)
    except Exception as e:  # noqa: BLE001
        logger.debug('cloudflare: no store address for Turnstile: %s', e)
    if not settings.DEBUG:
        hosts -= _LOCAL_HOSTS
    return hosts


def _siteverify(secret: str, token: str, ip: str = '') -> dict:
    """One answer from siteverify, retried once with the same idempotency key
    when Cloudflare could not answer. Never raises: an unreachable siteverify is
    `success: False`, so an enforced form fails closed."""
    import time  # noqa: PLC0415
    import uuid  # noqa: PLC0415

    import requests  # noqa: PLC0415 — matches the lazy-import style in this module

    payload = {'secret': secret, 'response': token, 'idempotency_key': str(uuid.uuid4())}
    if ip:
        payload['remoteip'] = ip
    for attempt in (1, 2):
        try:
            resp = requests.post(SITEVERIFY_URL, data=payload, timeout=(5, 10))
            if resp.status_code < 500:
                data = resp.json() if resp.ok else {}
                codes = data.get('error-codes') or []
                if 'internal-error' not in codes or attempt == 2:
                    return (
                        data
                        if resp.ok
                        else {'success': False, 'error-codes': [f'http-{resp.status_code}']}
                    )
        except (requests.RequestException, ValueError) as e:
            logger.info('cloudflare: Turnstile siteverify attempt %s failed: %s', attempt, e)
        if attempt == 1:
            time.sleep(0.5)
    return {'success': False, 'error-codes': ['siteverify-unreachable']}


def verify_turnstile(request, action: str = '') -> bool:
    """Verify a Turnstile token server-side, the way Cloudflare's Spin wires it.

    True when Turnstile is off (not enforced). While it is on, the answer must say
    `success`, name the `action` the widget was rendered with (when given), and
    name a `hostname` this store answers on. Anything else, a missing or overlong
    token, or a siteverify that cannot be reached, is False: fail closed.
    """
    cfg = _turnstile_config()
    if not cfg.get('turnstile_enabled'):
        return True
    secret = (cfg.get('turnstile_secret_key') or '').strip()
    token = (request.POST.get('cf-turnstile-response') or '').strip()
    if not (secret and token) or len(token) > TOKEN_MAX_LENGTH:
        return False
    result = _siteverify(secret, token, _client_ip(request))
    if not result.get('success'):
        codes = result.get('error-codes') or []
        if {'invalid-input-secret', 'missing-input-secret'} & set(codes):
            logger.error('cloudflare: Turnstile refused the secret key (%s)', ', '.join(codes))
        else:
            logger.info('cloudflare: Turnstile token refused (%s)', ', '.join(codes) or 'no reason')
        return False
    if action and result.get('action') != action:
        logger.warning(
            'cloudflare: Turnstile token for action %r used on %r', result.get('action'), action
        )
        return False
    if secret not in TEST_SECRETS:
        hostname = (result.get('hostname') or '').lower()
        if hostname not in _expected_hostnames(request):
            logger.warning('cloudflare: Turnstile token solved on another host: %r', hostname)
            return False
    return True


def turnstile_health(value=None, **kwargs):
    """HEALTH_CHECKS: while Turnstile is on, Cloudflare accepts its secret key.

    A made-up token is sent: a working secret gets `invalid-input-response`, a
    wrong one `invalid-input-secret`, which would refuse every visitor on every
    protected form. A test secret passes every token, so it protects nothing.
    """
    value = list(value or [])
    cfg = _turnstile_config()
    if not cfg.get('turnstile_enabled'):
        return value
    name = 'Turnstile secret key works'
    secret = (cfg.get('turnstile_secret_key') or '').strip()
    if not secret or not (cfg.get('turnstile_site_key') or '').strip():
        value.append({'name': name, 'ok': False, 'detail': 'Turnstile is on but a key is missing.'})
        return value
    if secret in TEST_SECRETS:
        value.append(
            {
                'name': name,
                'ok': False,
                'detail': "The secret is one of Cloudflare's test keys: no form is protected.",
            }
        )
        return value
    codes = set(_siteverify(secret, 'health-check').get('error-codes') or [])
    if {'invalid-input-secret', 'missing-input-secret'} & codes:
        detail, ok = (
            'Cloudflare refused the secret key: every protected form refuses visitors.',
            False,
        )
    elif 'siteverify-unreachable' in codes:
        detail, ok = (
            'Cloudflare could not be reached: protected forms refuse visitors meanwhile.',
            False,
        )
    else:
        detail, ok = 'Cloudflare accepts the secret key.', True
    value.append({'name': name, 'ok': ok, 'detail': detail})
    return value


# The settings switch for each kind of public form (core/bot_check.py names the kinds).
# Spelled out, not built from the kind: core/tests/test_settings_keys_have_readers.py
# looks for each key's reader.
TURNSTILE_FORMS = {
    'contact': 'turnstile_contact',
    'newsletter': 'turnstile_newsletter',
    'sign_in': 'turnstile_sign_in',
    'affiliates': 'turnstile_affiliates',
}


def turnstile_protects(form: str) -> bool:
    """True when Turnstile is on, both keys are set and `form`'s switch is on.

    A missing key protects nothing: a widget that cannot render, or a secret that
    cannot verify, would refuse every real visitor.
    """
    cfg = _turnstile_config()
    key = TURNSTILE_FORMS.get(form)
    if not (key and cfg.get('turnstile_enabled')):
        return False
    if not (
        (cfg.get('turnstile_site_key') or '').strip()
        and (cfg.get('turnstile_secret_key') or '').strip()
    ):
        return False
    return bool(cfg.get(key, True))


def turnstile_widget(value='', form='', context=None, **kwargs):
    """BOT_CHECK_WIDGET: the Turnstile widget for a protected form.

    `interaction-only` keeps it invisible unless Cloudflare needs a click, so a
    footer form shows no box. The script tag is written once per page.
    """
    if not turnstile_protects(form):
        return value
    from django.utils.html import format_html  # noqa: PLC0415

    from core.security_headers import script_nonce  # noqa: PLC0415

    html = format_html(
        '<div class="cf-turnstile" data-sitekey="{}" data-action="{}" '
        'data-appearance="interaction-only"></div>',
        _turnstile_config().get('turnstile_site_key', '').strip(),
        turnstile_action(form),
    )
    request = context.get('request') if context is not None else None
    if request is None or not getattr(request, '_turnstile_script', False):
        if request is not None:
            request._turnstile_script = True
        html += format_html(
            '<script{} src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>',
            script_nonce(context) if context is not None else '',
        )
    return (value or '') + html


def turnstile_passes(value=True, request=None, form='', **kwargs):
    """BOT_CHECK_PASSES: verify the request's token when `form` is protected."""
    if not turnstile_protects(form) or request is None:
        return value
    return verify_turnstile(request, action=turnstile_action(form))
