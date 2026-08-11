"""Maintenance mode — make the switch actually close the shop.

`storefront` has always exposed `maintenance_mode` + `maintenance_message` in
its settings panel with **zero consumers**: a merchant flipped "maintenance
mode" and the store stayed wide open. A control shaped like a safety mechanism
that does nothing is worse than no control at all.

Deliberately narrow:
  * staff/superusers pass through, so the merchant can work on the store they
    just closed;
  * `/dashboard/`, the APIs, payment webhooks and the health probes are never
    touched — closing the shop must not take down the admin, break an in-flight
    payment callback, or make the orchestrator think the container is unhealthy
    and recycle it;
  * returns 503 + `Retry-After` so crawlers treat it as temporary rather than
    de-indexing the catalogue.
"""

from __future__ import annotations

import logging

from django.http import HttpResponse

logger = logging.getLogger('morpheus.storefront')

#: Never gated — admin, machine surfaces, and the probes the platform runs on.
_ALWAYS_OPEN = (
    '/dashboard/',
    '/admin/',
    '/api/',
    '/graphql',
    '/mcp/',
    '/acp/',
    '/payments/',
    '/auth/',
    '/healthz',
    '/readyz',
    '/static/',
    '/media/',
    '/.well-known/',
    '/favicon.ico',
)


class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_close(request):
            message = self._config('maintenance_message') or (
                'We are briefly closed for maintenance. Please check back shortly.'
            )
            resp = HttpResponse(
                f'<!doctype html><meta charset="utf-8">'
                f'<title>Back shortly</title>'
                f'<div style="font-family:system-ui;max-width:34rem;margin:14vh auto;'
                f'padding:0 1.25rem;text-align:center;line-height:1.6">'
                f'<h1 style="font-size:1.5rem;margin:0 0 .75rem">Back shortly</h1>'
                f'<p style="color:#555;margin:0">{message}</p></div>',
                content_type='text/html; charset=utf-8',
                status=503,
            )
            resp['Retry-After'] = '3600'
            resp['Cache-Control'] = 'no-store'
            return resp
        return self.get_response(request)

    def _should_close(self, request) -> bool:
        path = request.path or '/'
        if path.startswith(_ALWAYS_OPEN):
            return False
        user = getattr(request, 'user', None)
        if user is not None and (
            getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False)
        ):
            return False
        return bool(self._config('maintenance_mode', False))

    @staticmethod
    def _config(key: str, default=None):
        """Read the storefront plugin's config, fail-soft.

        NB the plugin `_config_cache` is per-process, so a worker can lag a
        dashboard toggle until its cache is refreshed. Accepted here: the cost
        of a late close/open is a page or two, and paying a DB read on every
        storefront request to avoid it is the worse trade.
        """
        try:
            from plugins.registry import app_registry

            plugin = app_registry.get('storefront')
            return plugin.get_config_value(key, default) if plugin else default
        except Exception:  # noqa: BLE001 — a config problem must not close the shop
            return default
