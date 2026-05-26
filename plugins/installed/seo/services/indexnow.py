"""IndexNow protocol — instant indexation on Bing, Yandex, Naver, Seznam, Yep.

Two surfaces: key minting (idempotent across workers via PluginConfig)
and the push endpoint.
"""
from __future__ import annotations

from ._helpers import _site_base_url


def get_or_create_indexnow_key() -> str:
    """IndexNow key — a UUID stored in plugin config, surfaced at
    ``/<key>.txt`` for verification + sent with every push.

    Reads + writes PluginConfig directly (bypassing the in-process
    plugin cache) so the key is consistent across gunicorn workers
    and management-command shells. Otherwise: worker A generates a
    key, worker B reads its stale empty cache, generates a *new*
    key, overwrites A's value, and /<oldkey>.txt returns 404.
    """
    import uuid
    try:
        from plugins.models import PluginConfig
        row, _ = PluginConfig.objects.get_or_create(plugin_name='seo')
        existing = (row.config or {}).get('indexnow_key', '')
        if existing:
            return existing
        key = uuid.uuid4().hex
        row.config = {**(row.config or {}), 'indexnow_key': key}
        row.save(update_fields=['config', 'updated_at'])
        # Best-effort: keep the in-process plugin cache aligned.
        try:
            from plugins.registry import plugin_registry
            p = plugin_registry.get('seo')
            if p is not None:
                p.invalidate_config_cache()
        except Exception:  # noqa: BLE001
            pass
        return key
    except Exception:  # noqa: BLE001
        return ''


def ping_indexnow(urls: list[str]) -> dict:
    """POST one or many URLs to IndexNow — instant indexation on Bing,
    Yandex, Naver, Seznam, Yep. Fire-and-forget on the server; failures
    are silent so a slow IndexNow doesn't slow product saves.
    """
    import json as _json
    import urllib.request
    base = _site_base_url().rstrip('/')
    host = base.replace('https://', '').replace('http://', '').strip('/')
    key = get_or_create_indexnow_key()
    body = {
        'host': host,
        'key': key,
        'keyLocation': f'{base}/{key}.txt',
        'urlList': [u for u in urls if u][:10_000],
    }
    try:
        req = urllib.request.Request(
            'https://api.indexnow.org/IndexNow',
            data=_json.dumps(body).encode('utf-8'),
            headers={'Content-Type': 'application/json; charset=utf-8'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return {'ok': 200 <= resp.status < 300, 'status': resp.status}
    except Exception as exc:  # noqa: BLE001
        return {'ok': False, 'error': str(exc)}
