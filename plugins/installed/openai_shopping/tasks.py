"""Push the feed to the endpoint OpenAI allow-listed, every six hours."""

from __future__ import annotations

import logging

from celery import shared_task
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('morpheus.openai_shopping')


@shared_task(name='openai_shopping.push_feed', time_limit=300, soft_time_limit=240)
def push_feed() -> dict:
    """POST the JSONL feed with the configured bearer token. No endpoint → no-op."""
    from plugins.installed.openai_shopping.feed import build_rows, config, render_jsonl
    from plugins.installed.openai_shopping.views import LAST_PUSH_KEY

    cfg = config()
    if not (cfg.enabled and cfg.push_endpoint and cfg.push_token):
        return {'pushed': False, 'reason': 'no endpoint configured'}
    if not cfg.push_endpoint.lower().startswith('https://'):
        return {'pushed': False, 'reason': 'endpoint must be https'}

    import requests

    rows = build_rows()
    body = render_jsonl(rows)
    result: dict = {'pushed': False, 'rows': len(rows), 'at': timezone.now().isoformat()}
    try:
        resp = requests.post(
            cfg.push_endpoint,
            data=body.encode('utf-8'),
            headers={
                'Authorization': f'Bearer {cfg.push_token}',
                'Content-Type': 'application/x-ndjson; charset=utf-8',
            },
            timeout=120,
        )
        result['status'] = resp.status_code
        result['pushed'] = 200 <= resp.status_code < 300
        if not result['pushed']:
            result['error'] = resp.text[:300]
    except Exception as e:  # noqa: BLE001 — recorded for the dashboard, never raised into beat
        result['error'] = f'{type(e).__name__}: {e}'[:300]
    cache.set(LAST_PUSH_KEY, result, timeout=60 * 60 * 24 * 14)
    if not result['pushed']:
        logger.warning('openai_shopping: feed push failed: %s', result.get('error'))
    return result
