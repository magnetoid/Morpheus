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
