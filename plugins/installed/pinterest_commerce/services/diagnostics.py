"""Pinterest catalog feed diagnostics — why feed items fail ingestion/validation.

    GET /catalogs/feeds/{feed_id}/processing_results

Summarises the latest processing run: product counts + the top item-level
errors. Defensive parsing (the response shape varies by feed type), graceful
no-op when not connected. The Pinterest parallel of Meta catalog diagnostics.
"""

from __future__ import annotations

import logging

from .api import creds, get, has_token

logger = logging.getLogger('morpheus.pinterest_commerce')


def feed_diagnostics() -> dict:
    feed_id = creds()['catalog_feed_id']
    if not (has_token() and feed_id):
        return {'ok': False, 'reason': 'not_connected'}
    r = get(f'catalogs/feeds/{feed_id}/processing_results', {'page_size': 25})
    if not r.get('ok'):
        return {'ok': False, 'reason': r.get('reason')}

    items = (r['data'] or {}).get('items') or []
    if not items:
        return {'ok': True, 'counts': {}, 'issues': []}
    latest = items[0]

    counts = {}
    pc = latest.get('product_counts') or {}
    for key in ('original', 'ingested', 'in_stock', 'out_of_stock'):
        if key in pc:
            counts[key] = pc[key]

    issues: dict[str, dict] = {}
    for section in ('ingestion_details', 'validation_details'):
        errs = (latest.get(section) or {}).get('errors') or {}
        # errors is a dict of {code: {message, count, ...}} or a list — handle both.
        if isinstance(errs, dict):
            for code, info in errs.items():
                msg = (info or {}).get('message') if isinstance(info, dict) else None
                cnt = (info or {}).get('count', 0) if isinstance(info, dict) else 0
                key = msg or code
                issues.setdefault(key, {'description': key, 'count': 0})['count'] += (
                    int(cnt or 0) or 1
                )
        elif isinstance(errs, list):
            for e in errs:
                key = (e or {}).get('message') or (e or {}).get('code') or 'error'
                issues.setdefault(key, {'description': key, 'count': 0})['count'] += 1

    top = sorted(issues.values(), key=lambda x: x['count'], reverse=True)[:20]
    return {'ok': True, 'counts': counts, 'issues': top, 'status': latest.get('status', '')}
