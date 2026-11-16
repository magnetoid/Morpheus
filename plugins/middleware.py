"""Every request runs on the apps the store has switched on.

A switch flipped in one web worker reaches this one here, before the request
is resolved: `AppRegistry.reconcile()` costs one cache read while nothing
changed, and otherwise applies the stored switches (URLs, hooks, dashboard
pages, settings panels, storefront blocks) before the view runs. Celery tasks
get the same through `task_prerun` (`morph/celery.py`).

It sits after `RestoreGateMiddleware`, because a reconcile may read the
database, and before every middleware that asks an app for anything
(`core/tests/test_registry_reconcile.py::MiddlewareOrderTests`).
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.plugins')


class PluginMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            from plugins.registry import app_registry

            app_registry.reconcile()
        except Exception:  # noqa: BLE001 — a request is served on the apps it has
            logger.warning('plugins: could not follow the stored switches', exc_info=True)
        return self.get_response(request)
