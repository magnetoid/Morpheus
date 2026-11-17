"""A list setting stored as text still reads (v0.173.0).

Before v0.173.0 the settings panel saved a list as the text it rendered,
`[1, 3, 7]`. Reading it failed, so dunning fell back to its defaults and also
ignored the settings read after the list.
"""

from __future__ import annotations

from django.test import TestCase

from plugins.registry import app_registry


class ListStoredAsTextTests(TestCase):
    def test_dunning_reads_its_days_and_what_follows(self):
        from plugins.installed.subscriptions.tasks import _config

        plugin = app_registry.get('subscriptions')
        self.addCleanup(plugin.invalidate_config_cache)
        plugin.set_config('dunning_step_days', '[1, 4]')
        plugin.set_config('require_marketing_consent', False)
        cfg = _config()
        self.assertEqual(cfg['dunning_step_days'], [1, 4])
        self.assertIs(cfg['require_marketing_consent'], False)
