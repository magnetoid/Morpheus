"""register_urls disable-safety (hunt #13).

A plugin's `register_urls` mounts stay in `_plugin_urls` across a deactivate
(like ready()-wired hooks), so `get_urlpatterns` must skip routes owned by an
inactive plugin — otherwise a disabled plugin's endpoints keep serving, failing
the disable litmus test. Untagged entries (plugin='') are always included.
"""

from __future__ import annotations

from django.test import TestCase


class RegisterUrlsDisableSafetyTests(TestCase):
    def _add_entry(self, owner: str, ns: str, prefix: str) -> dict:
        from plugins.registry import app_registry

        entry = {
            'urlconf': 'core.auth.urls',  # any valid urlconf module with urlpatterns
            'prefix': prefix,
            'namespace': ns,
            'plugin': owner,
        }
        app_registry._plugin_urls.append(entry)
        self.addCleanup(
            lambda: entry in app_registry._plugin_urls and app_registry._plugin_urls.remove(entry)
        )
        return entry

    def test_get_urlpatterns_skips_inactive_owner(self):
        from plugins.registry import app_registry

        self._add_entry('zztest_plugin', 'zztest_disable', 'zztest-disable/')
        self.addCleanup(lambda: app_registry._active.discard('zztest_plugin'))

        # Owner inactive → route excluded.
        n_inactive = len(app_registry.get_urlpatterns())
        # Owner active → the very same route is now included (exactly one more).
        app_registry._active.add('zztest_plugin')
        n_active = len(app_registry.get_urlpatterns())
        self.assertEqual(n_active, n_inactive + 1)

    def test_untagged_entry_always_included(self):
        from plugins.registry import app_registry

        before = len(app_registry.get_urlpatterns())
        self._add_entry('', 'zztest_untagged', 'zztest-untagged/')  # no owner
        after = len(app_registry.get_urlpatterns())
        self.assertEqual(after, before + 1)


class LiveResolverDisableTests(TestCase):
    """`get_urlpatterns()` skipping an inactive owner is necessary, not
    sufficient: the *live* resolver must forget the routes too. The root
    urlconf includes `plugins.chrome_urls` + `plugins.storefront_urls` (the
    ADR 0022 split), so a refresh that rebuilds only `plugins.urls` leaves every
    disabled plugin's endpoints serving until the next restart — and then a
    theme that still reverses one of them 500s on boot, with nothing tying the
    outage to a toggle flipped weeks earlier."""

    def test_deactivate_removes_routes_from_the_live_resolver_and_activate_restores(self):
        from django.urls import NoReverseMatch, reverse

        from plugins.registry import app_registry

        self.assertTrue(app_registry.is_active('seo'))
        self.assertEqual(reverse('seo:journal_rss'), '/journal/feed.xml')

        app_registry.deactivate('seo')
        try:
            with self.assertRaises(NoReverseMatch):
                reverse('seo:journal_rss')
            self.assertEqual(self.client.get('/journal/feed.xml').status_code, 404)
        finally:
            app_registry.activate('seo')

        self.assertEqual(reverse('seo:journal_rss'), '/journal/feed.xml')
        self.assertEqual(self.client.get('/journal/feed.xml').status_code, 200)
