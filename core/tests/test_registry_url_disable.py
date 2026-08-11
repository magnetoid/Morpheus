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
