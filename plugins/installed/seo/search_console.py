"""Google Search Console for this store (v0.159.0).

The store reads its own Search Console property with a Google service account.
The merchant creates one in Google Cloud, adds its email as a user of the
property in Search Console, and pastes the account's JSON key on Settings → SEO
(``search_console_key``, write-only). A service account needs no sign-in page
and no callback address per store, and its access does not lapse after a week
the way a refresh token from an unpublished OAuth app does.

``pull()`` runs nightly (``seo.search_console_pull``): Google's clicks,
impressions and positions for each day, query and page, kept 16 months as
Google keeps them, then each tracked keyword's position. ``report()`` reads
them for the Search performance page and Linda's ``seo.search_performance``;
``inspect_url()`` asks Google how it sees one of the store's pages.

Every address here is Google's own and fixed; the key's ``token_uri`` is never
used, so a pasted key cannot send a signed request anywhere else.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import defaultdict
from datetime import date, timedelta
from urllib.parse import quote, urlsplit

import requests

logger = logging.getLogger('morpheus.seo.search_console')

_TOKEN_URL = 'https://oauth2.googleapis.com/token'
_API = 'https://searchconsole.googleapis.com'
_SCOPE = 'https://www.googleapis.com/auth/webmasters.readonly'
_TIMEOUT = 20
#: Google keeps 16 months of search data; so does the store.
KEEP_DAYS = 486
#: How far back the first pull reaches.
BACKFILL_DAYS = 90
#: Google's numbers for a day settle about two days later.
SETTLE_DAYS = 2
#: Rows per request (Google's maximum is 25,000).
_PAGE_ROWS = 25000
#: Rows of each kind kept per day, most clicked first.
MAX_ROWS_PER_DAY = 5000
_STATUS_KEY = 'seo:search_console:status'
_KINDS = (('total', ['date']), ('query', ['date', 'query']), ('page', ['date', 'page']))


class SearchConsoleError(Exception):
    """Google refused or did not answer; the message is fit for the merchant."""


def _http(method: str, url: str, **kwargs):
    return requests.request(method, url, timeout=_TIMEOUT, **kwargs)


def read_config() -> dict:
    """The seo app's settings, read fresh (the merchant saves in another worker)."""
    from plugins.registry import app_registry  # noqa: PLC0415

    seo = app_registry.get('seo')
    if seo is None:
        return {}
    seo.invalidate_config_cache()
    return seo.get_config() or {}


def key_state(cfg: dict | None = None) -> str:
    """'missing', 'invalid' (pasted, but not a service-account JSON key) or 'ok'."""
    raw = ((read_config() if cfg is None else cfg).get('search_console_key') or '').strip()
    if not raw:
        return 'missing'
    return 'ok' if service_account(cfg) else 'invalid'


def service_account(cfg: dict | None = None) -> dict | None:
    """The pasted service-account key, or None when none is set or it is not one."""
    raw = ((read_config() if cfg is None else cfg).get('search_console_key') or '').strip()
    if not raw:
        return None
    try:
        key = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(key, dict) or key.get('type') != 'service_account':
        return None
    if not (key.get('client_email') and key.get('private_key')):
        return None
    return key


def account_email(cfg: dict | None = None) -> str:
    """The address the merchant adds as a user in Search Console (not a secret)."""
    key = service_account(cfg)
    return str(key['client_email']) if key else ''


def _google_message(resp) -> str:
    try:
        data = resp.json()
    except ValueError:
        return (resp.reason or '')[:200]
    err = data.get('error') if isinstance(data, dict) else None
    if isinstance(err, dict):
        return str(err.get('message') or err.get('status') or '')[:200]
    return str(data.get('error_description') or err or '')[:200]


def _access_token(key: dict) -> str:
    import jwt  # noqa: PLC0415
    from django.core.cache import cache  # noqa: PLC0415

    ident = f'{key["client_email"]}:{key.get("private_key_id", "")}'
    cache_key = 'seo:search_console:token:' + hashlib.sha256(ident.encode()).hexdigest()[:16]
    token = cache.get(cache_key)
    if token:
        return token
    now = int(time.time())
    claims = {'iss': key['client_email'], 'scope': _SCOPE, 'aud': _TOKEN_URL}
    try:
        assertion = jwt.encode(
            {**claims, 'iat': now, 'exp': now + 3600},
            key['private_key'],
            algorithm='RS256',
            headers={'kid': key['private_key_id']} if key.get('private_key_id') else None,
        )
    except Exception as e:  # noqa: BLE001 — a malformed private key
        raise SearchConsoleError(
            'The service-account key could not sign in; paste its JSON key again.'
        ) from e
    try:
        resp = _http(
            'POST',
            _TOKEN_URL,
            data={
                'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                'assertion': assertion,
            },
        )
    except requests.RequestException as e:
        raise SearchConsoleError('Google did not answer the sign-in.') from e
    if resp.status_code != 200:
        raise SearchConsoleError(
            f'Google refused the service account ({resp.status_code}): {_google_message(resp)}'
        )
    data = resp.json()
    token = data.get('access_token') if isinstance(data, dict) else None
    if not token:
        raise SearchConsoleError('Google signed the service account in without a token.')
    cache.set(cache_key, token, max(60, int(data.get('expires_in') or 3600) - 300))
    return token


def _call(key: dict, method: str, path: str, payload: dict | None = None) -> dict:
    token = _access_token(key)
    try:
        resp = _http(
            method, f'{_API}{path}', json=payload, headers={'Authorization': f'Bearer {token}'}
        )
    except requests.RequestException as e:
        raise SearchConsoleError('Google Search Console did not answer.') from e
    if resp.status_code >= 400:
        raise SearchConsoleError(
            f'Search Console answered {resp.status_code}: {_google_message(resp)}'
        )
    try:
        data = resp.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _store_host() -> str:
    from core.utils.site import site_base_url  # noqa: PLC0415

    return (urlsplit(site_base_url()).hostname or '').lower()


def property_url(key: dict, cfg: dict) -> str:
    """The Search Console property this store reads: the one set on Settings →
    SEO, else the domain or address property the account can see for this host."""
    chosen = (cfg.get('search_console_property') or '').strip()
    if chosen:
        return chosen
    host = _store_host()
    bare = host.removeprefix('www.')
    data = _call(key, 'GET', '/webmasters/v3/sites')
    seen = [
        str(s['siteUrl'])
        for s in data.get('siteEntry') or []
        if isinstance(s, dict)
        and s.get('siteUrl')
        and s.get('permissionLevel') != 'siteUnverifiedUser'
    ]
    if f'sc-domain:{bare}' in seen:
        return f'sc-domain:{bare}'
    for site in seen:
        site_host = (urlsplit(site).hostname or '').lower()
        if site_host and site_host.removeprefix('www.') == bare:
            return site
    for site in seen:
        if site.startswith('sc-domain:') and bare.endswith('.' + site.removeprefix('sc-domain:')):
            return site
    raise SearchConsoleError(
        f'{key["client_email"]} cannot see a Search Console property for {host or "this store"}. '
        'Add it as a user of the property in Search Console.'
    )


def _rows(key: dict, site: str, start: date, end: date, dimensions: list) -> list:
    path = f'/webmasters/v3/sites/{quote(site, safe="")}/searchAnalytics/query'
    cap = MAX_ROWS_PER_DAY * ((end - start).days + 1)
    out: list = []
    while True:
        data = _call(
            key,
            'POST',
            path,
            {
                'startDate': start.isoformat(),
                'endDate': end.isoformat(),
                'dimensions': dimensions,
                'type': 'web',
                'rowLimit': _PAGE_ROWS,
                'startRow': len(out),
            },
        )
        rows = [r for r in data.get('rows') or [] if isinstance(r, dict)]
        out.extend(rows)
        if len(rows) < _PAGE_ROWS or len(out) >= cap:
            return out


def _page_key(url: str, bare: str) -> str:
    """A page's path when Google's address for it is on this store (its host,
    with or without www), else '': a domain property also holds every other
    subdomain's pages. The query string goes, because analytics files a visit
    under its landing page's path."""
    parts = urlsplit(url)
    if (parts.hostname or '').lower().removeprefix('www.') != bare:
        return ''
    return parts.path or '/'


def _to_rows(fetched: dict) -> list:
    """Google's rows as ``SearchConsoleRow``s. A page row is one of the store's
    paths: www and the bare host, and every query string, are one row. The
    totals and queries are the property's, other subdomains included."""
    from plugins.installed.seo.models import SearchConsoleRow  # noqa: PLC0415

    bare = _store_host().removeprefix('www.')
    merged: dict = {}
    for kind, rows in fetched.items():
        for row in rows:
            keys = row.get('keys') or []
            try:
                day = date.fromisoformat(str(keys[0]))
            except (IndexError, ValueError):
                continue
            name = '' if kind == 'total' else str(keys[1] if len(keys) > 1 else '')
            if kind == 'page':
                name = _page_key(name, bare)
            if kind != 'total' and not name:
                continue
            impressions = int(row.get('impressions') or 0)
            bucket = merged.setdefault((day, kind, name[:500]), [0, 0, 0.0])
            bucket[0] += int(row.get('clicks') or 0)
            bucket[1] += impressions
            bucket[2] += float(row.get('position') or 0) * impressions
    per_day: dict = defaultdict(list)
    for (day, kind, name), (clicks, impressions, weighted) in merged.items():
        per_day[(day, kind)].append(
            SearchConsoleRow(
                day=day,
                kind=kind,
                key=name,
                clicks=clicks,
                impressions=impressions,
                position=round(weighted / impressions, 2) if impressions else 0,
            )
        )
    out: list = []
    for rows in per_day.values():
        rows.sort(key=lambda r: (-r.clicks, -r.impressions, r.key))
        out.extend(rows[:MAX_ROWS_PER_DAY])
    return out


def _remember(status: dict) -> dict:
    from django.core.cache import cache  # noqa: PLC0415
    from django.utils import timezone  # noqa: PLC0415

    status = {**status, 'at': timezone.now().isoformat()}
    cache.set(_STATUS_KEY, status, None)
    return status


def last_pull() -> dict | None:
    """What the last pull did: {'ok', 'detail' | 'property', 'start', 'end', 'rows', 'at'}."""
    from django.core.cache import cache  # noqa: PLC0415

    return cache.get(_STATUS_KEY)


def pull(*, today: date | None = None) -> dict:
    """Fetch the days Google has settled since the last pull (90 the first time)
    and replace them; then drop rows older than 16 months and refresh the
    tracked keywords. A store with no key does nothing."""
    from django.db import transaction  # noqa: PLC0415
    from django.db.models import Max  # noqa: PLC0415

    from core.utils.site import store_today  # noqa: PLC0415
    from plugins.installed.seo.models import SearchConsoleRow  # noqa: PLC0415

    cfg = read_config()
    key = service_account(cfg)
    if key is None:
        return {'ok': False, 'connected': False}
    today = today or store_today()
    end = today - timedelta(days=SETTLE_DAYS)
    floor = end - timedelta(days=BACKFILL_DAYS - 1)
    latest = SearchConsoleRow.objects.filter(kind='total').aggregate(d=Max('day'))['d']
    start = (
        floor
        if latest is None
        else max(floor, min(latest - timedelta(days=SETTLE_DAYS), end - timedelta(days=6)))
    )
    site = ''
    try:
        site = property_url(key, cfg)
        fetched = {kind: _rows(key, site, start, end, dims) for kind, dims in _KINDS}
    except SearchConsoleError as e:
        logger.error('seo.search_console_pull: %s', e)
        return _remember({'ok': False, 'detail': str(e), 'property': site})
    rows = _to_rows(fetched)
    with transaction.atomic():
        SearchConsoleRow.objects.filter(day__gte=start, day__lte=end).delete()
        SearchConsoleRow.objects.bulk_create(rows, batch_size=1000)
        SearchConsoleRow.objects.filter(day__lt=today - timedelta(days=KEEP_DAYS)).delete()
    keywords = refresh_tracked_keywords(today=today)
    return _remember(
        {
            'ok': True,
            'property': site,
            'start': start.isoformat(),
            'end': end.isoformat(),
            'rows': len(rows),
            'keywords': keywords,
        }
    )


def _weighted():
    from django.db.models import ExpressionWrapper, F, FloatField  # noqa: PLC0415

    return ExpressionWrapper(F('position') * F('impressions'), output_field=FloatField())


def _figures(clicks, impressions, weighted) -> dict:
    clicks, impressions = int(clicks or 0), int(impressions or 0)
    return {
        'clicks': clicks,
        'impressions': impressions,
        'ctr': round(clicks / impressions * 100, 1) if impressions else 0.0,
        'position': round(float(weighted or 0) / impressions, 1) if impressions else None,
    }


def _total(qs) -> dict:
    from django.db.models import Sum  # noqa: PLC0415

    agg = qs.aggregate(c=Sum('clicks'), i=Sum('impressions'), w=Sum(_weighted()))
    return _figures(agg['c'], agg['i'], agg['w'])


def refresh_tracked_keywords(*, today: date | None = None, days: int = 7) -> int:
    """Each tracked keyword's position over Google's last settled week (None
    when Google showed the store for it nowhere); returns how many were checked."""
    from django.db.models import Sum  # noqa: PLC0415
    from django.utils import timezone  # noqa: PLC0415

    from core.utils.site import store_today  # noqa: PLC0415
    from plugins.installed.seo.models import SearchConsoleRow, TrackedKeyword  # noqa: PLC0415

    tracked = list(TrackedKeyword.objects.all())
    if not tracked:
        return 0
    end = (today or store_today()) - timedelta(days=SETTLE_DAYS)
    wanted = {k.keyword.strip().lower() for k in tracked}
    stats = {
        row['key'].lower(): row
        for row in SearchConsoleRow.objects.filter(
            kind='query', key__in=wanted, day__gt=end - timedelta(days=days), day__lte=end
        )
        .values('key')
        .annotate(i=Sum('impressions'), w=Sum(_weighted()))
    }
    now = timezone.now()
    for keyword in tracked:
        row = stats.get(keyword.keyword.strip().lower())
        keyword.last_position = (
            max(1, min(32767, round(float(row['w'] or 0) / row['i']))) if row and row['i'] else None
        )
        keyword.last_checked_at = now
        keyword.save(update_fields=['last_position', 'last_checked_at'])
    return len(tracked)


def keyword_figures(keywords, *, days: int = 28) -> dict:
    """{keyword (lowercased): figures} over the last ``days`` days Google has settled."""
    from django.db.models import Max, Sum  # noqa: PLC0415

    from plugins.installed.seo.models import SearchConsoleRow  # noqa: PLC0415

    end = SearchConsoleRow.objects.filter(kind='total').aggregate(d=Max('day'))['d']
    wanted = {str(k).strip().lower() for k in keywords if str(k).strip()}
    if end is None or not wanted:
        return {}
    rows = (
        SearchConsoleRow.objects.filter(
            kind='query', key__in=wanted, day__gt=end - timedelta(days=days), day__lte=end
        )
        .values('key')
        .annotate(c=Sum('clicks'), i=Sum('impressions'), w=Sum(_weighted()))
    )
    return {r['key'].lower(): _figures(r['c'], r['i'], r['w']) for r in rows}


def _landing_traffic(paths: list, start: date, end: date) -> dict:
    """Visits Google's organic results sent to each path and what they bought,
    from whichever app answers (analytics)."""
    from core.hooks import MorpheusEvents, hook_registry  # noqa: PLC0415

    try:
        out = hook_registry.filter(
            MorpheusEvents.LANDING_PAGE_TRAFFIC,
            {},
            paths=paths,
            since=start,
            until=end,
            channel='organic',
            source='google',
        )
    except Exception:  # noqa: BLE001 — Google's numbers still show
        logger.warning('seo: landing-page traffic failed', exc_info=True)
        return {}
    return out if isinstance(out, dict) else {}


def report(*, days: int = 28, by: str = 'query', limit: int = 50) -> dict:
    """Google's clicks, impressions, click-through rate and average position
    over the last ``days`` days it has settled, against the days before, and
    the top queries or pages; a page row also carries the visits Google sent
    to it and their sales."""
    from django.db.models import Max, Sum  # noqa: PLC0415

    from plugins.installed.seo.models import SearchConsoleRow  # noqa: PLC0415

    days = max(1, min(int(days or 28), KEEP_DAYS))
    by = by if by in ('query', 'page') else 'query'
    limit = max(1, min(int(limit or 50), 500))
    end = SearchConsoleRow.objects.filter(kind='total').aggregate(d=Max('day'))['d']
    out = {'days': days, 'by': by, 'has_data': end is not None, 'rows': []}
    if end is None:
        return out
    start = end - timedelta(days=days - 1)
    before_end = start - timedelta(days=1)
    totals = SearchConsoleRow.objects.filter(kind='total')
    out.update(
        start=start,
        end=end,
        totals=_total(totals.filter(day__gte=start, day__lte=end)),
        before=_total(
            totals.filter(day__gte=before_end - timedelta(days=days - 1), day__lte=before_end)
        ),
    )
    groups = (
        SearchConsoleRow.objects.filter(kind=by, day__gte=start, day__lte=end)
        .values('key')
        .annotate(c=Sum('clicks'), i=Sum('impressions'), w=Sum(_weighted()))
        .order_by('-c', '-i', 'key')[:limit]
    )
    rows = [{'key': g['key'], **_figures(g['c'], g['i'], g['w'])} for g in groups]
    if by == 'page' and rows:
        traffic = _landing_traffic([r['key'] for r in rows], start, end)
        for r in rows:
            seen = traffic.get(r['key']) or {}
            r['visits'] = seen.get('visits', 0)
            r['purchases'] = seen.get('purchases', 0)
            r['sales'] = seen.get('sales')
    out['rows'] = rows
    return out


def inspect_url(url: str) -> dict:
    """How Google sees one of the store's pages (Search Console's URL inspection)."""
    from core.utils.site import site_base_url  # noqa: PLC0415

    cfg = read_config()
    key = service_account(cfg)
    if key is None:
        raise SearchConsoleError(
            'Search Console is not connected. Paste the key on Settings → SEO.'
        )
    target = (url or '').strip()
    if target.startswith('/'):
        target = site_base_url().rstrip('/') + target
    parts = urlsplit(target)
    host = (parts.hostname or '').lower().removeprefix('www.')
    if parts.scheme not in ('http', 'https') or host != _store_host().removeprefix('www.'):
        raise SearchConsoleError("Only the store's own pages can be inspected.")
    site = property_url(key, cfg)
    data = _call(
        key, 'POST', '/v1/urlInspection/index:inspect', {'inspectionUrl': target, 'siteUrl': site}
    )
    result = data.get('inspectionResult') or {}
    index = result.get('indexStatusResult') or {}
    link = str(result.get('inspectionResultLink') or '')
    return {
        'url': target,
        'verdict': index.get('verdict', ''),
        'coverage': index.get('coverageState', ''),
        'indexing': index.get('indexingState', ''),
        'robots': index.get('robotsTxtState', ''),
        'fetch': index.get('pageFetchState', ''),
        'last_crawl': index.get('lastCrawlTime', ''),
        'google_canonical': index.get('googleCanonical', ''),
        'user_canonical': index.get('userCanonical', ''),
        'link': link if link.startswith('https://search.google.com/') else '',
    }
