"""The "Days of raw event log to retain" setting is what the nightly trim uses.

The setting existed; the trim task kept its hard-coded 90 days whatever the
merchant chose.
"""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from plugins.installed.analytics.models import AnalyticsEvent
from plugins.registry import app_registry


def _event(days_old: int) -> AnalyticsEvent:
    event = AnalyticsEvent.objects.create(name='pageview', kind='pageview')
    AnalyticsEvent.objects.filter(pk=event.pk).update(
        created_at=timezone.now() - timedelta(days=days_old)
    )
    return event


class RetentionSettingTests(TestCase):
    def setUp(self):
        self.plugin = app_registry.get('analytics')
        self.addCleanup(setattr, self.plugin, '_config_cache', None)

    def test_the_trim_uses_the_merchant_setting(self):
        from plugins.installed.analytics.tasks import trim_old_events_task

        self.plugin._config_cache = {'keep_event_days': 30}
        old, recent = _event(40), _event(20)
        trim_old_events_task()
        self.assertFalse(AnalyticsEvent.objects.filter(pk=old.pk).exists())
        self.assertTrue(AnalyticsEvent.objects.filter(pk=recent.pk).exists())

    def test_without_a_setting_it_keeps_ninety_days(self):
        from plugins.installed.analytics.tasks import trim_old_events_task

        self.plugin._config_cache = {}
        old, recent = _event(100), _event(80)
        trim_old_events_task()
        self.assertFalse(AnalyticsEvent.objects.filter(pk=old.pk).exists())
        self.assertTrue(AnalyticsEvent.objects.filter(pk=recent.pk).exists())
