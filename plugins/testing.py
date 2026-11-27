"""Helpers for tests that compare an app's work across several requests, or follow app switches."""

from __future__ import annotations

from unittest import mock


def hold_app_settings(test) -> None:
    """Keep every app's and theme's cached settings for the rest of ``test``.

    An app with ``config_fresh_s`` reads its settings again once that window has
    passed since its last read (storefront and payments 10 s, book_product 30 s),
    and so does a theme (10 s, four queries: the read runs in a savepoint). A test
    that compares the queries of two pages saw the read land in one of them on a
    slow runner: the product list cost 67 queries for one book and 63 for four
    (CI, PR #166), then 65 and 61 once themes had the window too (PR #218).
    Holding the windows keeps the warm-up's reads.
    """
    from plugins.registry import app_registry
    from themes.registry import theme_registry

    for owner in (*app_registry.all_plugins(), *theme_registry.all_themes()):
        if owner.config_fresh_s is not None:
            patcher = mock.patch.object(owner, 'config_fresh_s', None)
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


def follow_app_switches(test) -> None:
    """Let this process follow the stored app switches for the rest of ``test``.

    Under tests `AppRegistry.reconcile()` does nothing unless a test asks (see
    `AppRegistry.follow_switches`). This starts in step with the current token, so
    only what the test itself flips is followed, and the cleanup puts back every
    app the test switched in this process (its stored rows roll back with it).
    """
    from plugins.registry import app_registry

    active = set(app_registry._active)
    app_registry.follow_switches = True
    app_registry._seen_version = app_registry._version()

    def restore():
        app_registry.follow_switches = None
        changed = False
        for name in sorted(app_registry._active - active):
            app_registry._apply_inactive(name)
            changed = True
        for name in app_registry._topo_sort(sorted(active & set(app_registry._classes))):
            if name not in app_registry._active:
                changed |= app_registry._apply_active(name)
        if changed:
            app_registry._refresh_urlconf()

    test.addCleanup(restore)
