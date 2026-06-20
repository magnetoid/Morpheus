"""Meta Custom Audiences — push hashed customer segments for retargeting +
lookalike seeding.

Builds an email segment from our own data, SHA-256 hashes each address (Meta
requires EMAIL_SHA256 — we never send plaintext), find-or-creates the named
Custom Audience on the ad account, and uploads in batches. Reuses the existing
Graph helpers + token. Fail-soft: every path returns {ok, reason}.

Privacy: the merchant enables this deliberately; only hashed emails leave the
system, and a Custom Audience is a USER_PROVIDED_ONLY first-party upload.
"""

from __future__ import annotations

import json
import logging

from .capi import _sha256  # reuse the trimmed+lowercased SHA-256 email hasher
from .graph import ads_connected, creds, get, post

logger = logging.getLogger('morpheus.meta_commerce')

# segment key → Custom Audience display name (stable, so re-syncs update in place)
SEGMENTS = {
    'all_customers': 'Morpheus — All customers',
    'purchasers': 'Morpheus — Purchasers (180d)',
}
_BATCH = 5000


def _segment_emails(segment: str) -> list[str]:
    if segment == 'all_customers':
        from django.contrib.auth import get_user_model  # noqa: PLC0415

        return list(get_user_model().objects.exclude(email='').values_list('email', flat=True))
    if segment == 'purchasers':
        from datetime import timedelta  # noqa: PLC0415

        from django.utils import timezone  # noqa: PLC0415

        from plugins.installed.orders.models import Order  # noqa: PLC0415

        since = timezone.now() - timedelta(days=180)
        return list(
            Order.objects.filter(placed_at__gte=since)
            .exclude(status__in=['pending', 'cancelled'])
            .exclude(email='')
            .values_list('email', flat=True)
        )
    return []


def _find_or_create_audience(name: str) -> str | None:
    acct = creds()['ad_account_id']
    res = get(f'act_{acct}/customaudiences', {'fields': 'name', 'limit': 500})
    if res.get('ok'):
        for a in (res['data'] or {}).get('data', []) or []:
            if a.get('name') == name:
                return str(a.get('id'))
    res = post(
        f'act_{acct}/customaudiences',
        {
            'name': name,
            'subtype': 'CUSTOM',
            'description': 'Synced by Morpheus',
            'customer_file_source': 'USER_PROVIDED_ONLY',
        },
    )
    if res.get('ok'):
        return str((res['data'] or {}).get('id') or '') or None
    logger.warning('meta_commerce: audience create failed: %s', res.get('reason'))
    return None


def sync_audience(segment: str) -> dict:
    """Build + upload one segment's hashed emails to its Custom Audience."""
    if segment not in SEGMENTS:
        return {'ok': False, 'reason': 'unknown_segment'}
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}

    hashed = sorted({_sha256(e) for e in _segment_emails(segment) if e})
    if not hashed:
        return {'ok': False, 'reason': 'empty_segment'}

    aud_id = _find_or_create_audience(SEGMENTS[segment])
    if not aud_id:
        return {'ok': False, 'reason': 'audience_unavailable'}

    uploaded = 0
    for i in range(0, len(hashed), _BATCH):
        batch = hashed[i : i + _BATCH]
        res = post(
            f'{aud_id}/users',
            {'payload': json.dumps({'schema': ['EMAIL_SHA256'], 'data': [[h] for h in batch]})},
        )
        if not res.get('ok'):
            _log(segment, ok=False, count=uploaded, reason=res.get('reason'))
            return {'ok': False, 'reason': res.get('reason'), 'uploaded': uploaded}
        uploaded += len(batch)

    _log(segment, ok=True, count=uploaded)
    return {'ok': True, 'audience_id': aud_id, 'uploaded': uploaded, 'segment': segment}


def _log(segment: str, *, ok: bool, count: int, reason=None) -> None:
    try:
        from plugins.installed.meta_commerce.models import MetaSyncLog  # noqa: PLC0415

        MetaSyncLog.objects.create(
            kind=MetaSyncLog.KIND_ADS,
            status=MetaSyncLog.STATUS_OK if ok else MetaSyncLog.STATUS_ERROR,
            item_count=count,
            errors=[] if ok else [str(reason)[:300]],
            message=f'Custom audience: {segment}',
        )
    except Exception as e:  # noqa: BLE001
        logger.debug('meta_commerce: audience log failed: %s', e)
