"""TikTok catalog diagnostics — product review/audit status + reject reasons.

    GET /catalog/product/get/  (catalog_id [, bc_id], page, page_size)

TikTok's catalog product payload varies by catalog type, so this parses
DEFENSIVELY across the likely status/reason field names and fails soft to a
graceful empty result rather than crashing or asserting a shape. The TikTok
parallel of the Meta/Pinterest catalog-diagnostics loop. No-op when unconnected.
"""

from __future__ import annotations

import logging

from .api import catalog_connected, creds, get

logger = logging.getLogger('morpheus.tiktok_commerce')

_APPROVED = ('approve', 'active', 'normal', 'pass', 'available')
_REJECTED = ('reject', 'fail', 'disapprove', 'invalid', 'error')
_PENDING = ('pending', 'review', 'audit', 'processing', 'in_progress')


def _bucket(status: str) -> str:
    s = (status or '').lower()
    if any(k in s for k in _REJECTED):
        return 'rejected'
    if any(k in s for k in _PENDING):
        return 'pending'
    if any(k in s for k in _APPROVED):
        return 'approved'
    return 'other'


def _reasons(product: dict):
    """Pull reject/error reasons out of whichever field TikTok used."""
    raw = (
        product.get('reject_reason')
        or product.get('audit_fail_reasons')
        or product.get('reasons')
        or product.get('errors')
        or []
    )
    if isinstance(raw, str):
        raw = [raw]
    out = []
    for r in raw or []:
        if isinstance(r, str):
            out.append(r)
        elif isinstance(r, dict):
            out.append(r.get('message') or r.get('reason') or r.get('description') or 'issue')
    return out


def catalog_diagnostics(*, max_pages: int = 4) -> dict:
    c = creds()
    if not catalog_connected():
        return {'ok': False, 'reason': 'not_connected'}

    counts = {'approved': 0, 'rejected': 0, 'pending': 0, 'other': 0, 'total': 0}
    issues: dict[str, dict] = {}
    page = 1
    for _ in range(max_pages):
        params = {'catalog_id': c['catalog_id'], 'page': page, 'page_size': 100}
        if c.get('bc_id'):
            params['bc_id'] = c['bc_id']
        r = get('catalog/product/get/', params)
        if not r.get('ok'):
            return {'ok': False, 'reason': r.get('reason')}
        data = r['data'] or {}
        products = data.get('products') or data.get('list') or data.get('items') or []
        for p in products:
            counts['total'] += 1
            status = p.get('status') or p.get('audit_status') or p.get('review_status') or ''
            counts[_bucket(str(status))] += 1
            for reason in _reasons(p):
                issues.setdefault(reason, {'description': reason, 'count': 0})['count'] += 1
        page_info = data.get('page_info') or {}
        total_page = page_info.get('total_page')
        if not total_page or page >= total_page:
            break
        page += 1

    top = sorted(issues.values(), key=lambda x: x['count'], reverse=True)[:20]
    return {'ok': True, 'counts': counts, 'issues': top}
