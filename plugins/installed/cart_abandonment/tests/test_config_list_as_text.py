"""A list setting stored as text still reads (v0.173.0).

Before v0.173.0 the settings panel saved a list as the text it rendered,
`[60, 1440, 4320]`. Reading it failed, so the drip fell back to its defaults
and also ignored the settings read after the list.
"""

from __future__ import annotations

from django.test import TestCase

from plugins.registry import app_registry


class ListStoredAsTextTests(TestCase):
    def test_cart_recovery_reads_its_delays_and_what_follows(self):
        from plugins.installed.cart_abandonment.tasks import _config

        plugin = app_registry.get('cart_abandonment')
        self.addCleanup(plugin.invalidate_config_cache)
        plugin.set_config('step_delays_minutes', '[30, 90]')
        plugin.set_config('require_marketing_consent', False)
        cfg = _config()
        self.assertEqual(cfg['step_delays_minutes'], [30, 90])
        self.assertIs(cfg['require_marketing_consent'], False)
