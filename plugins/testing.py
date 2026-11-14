"""Helpers for tests that compare an app's work across several requests."""

from __future__ import annotations

from unittest import mock


def hold_app_settings(test) -> None:
    """Keep every app's cached settings for the rest of ``test``.

    An app with ``config_fresh_s`` reads its settings again once that window has
    passed since its last read (storefront and payments 10 s, book_product 30 s),
    so a test that compares the queries of two pages saw the read land in one of
    them on a slow runner: the product list cost 67 queries for one book and 63
    for four (CI, PR #166). Holding the windows keeps the warm-up's reads.
    """
    from plugins.registry import app_registry

    for plugin in app_registry.all_plugins():
        if plugin.config_fresh_s is not None:
            patcher = mock.patch.object(plugin, 'config_fresh_s', None)
            patcher.start()
            test.addCleanup(patcher.stop)


def set_app_settings(test, app: str, **values) -> None:
    """Store ``values`` as ``app``'s settings for the rest of ``test``.

    The database write rolls back with the test, but each app also keeps its settings
    in memory, so the cleanup writes back what was there before (or the schema's
    default) and a later test never sees this one's values.
    """
    from plugins.registry import app_registry

    plugin = app_registry.get(app)
    defaults = (plugin.get_config_schema() or {}).get('properties') or {}
    for key, value in values.items():
        before = plugin.get_config_value(key, (defaults.get(key) or {}).get('default'))
        plugin.set_config(key, value)
        test.addCleanup(plugin.set_config, key, before)
