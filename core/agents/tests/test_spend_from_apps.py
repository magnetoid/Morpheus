"""An app's own model calls count toward the daily spend cap.

The cap summed only agent runs and Linda's replies, so every other model call in
the platform (dashboard "Generate" buttons, the Pulse rewrite, catalog
classification, store bootstrap) spent without limit. Core cannot import an app,
so an app contributes its usage today through the ``AI_USAGE_TODAY`` filter.
"""

from __future__ import annotations

from django.test import TestCase

from core.agents import guardrails
from core.hooks import MorpheusEvents, hook_registry


class SpendFromAppsTests(TestCase):
    def setUp(self):
        saved = list(hook_registry._handlers.get(MorpheusEvents.AI_USAGE_TODAY, []))
        self.addCleanup(hook_registry._handlers.__setitem__, MorpheusEvents.AI_USAGE_TODAY, saved)
        hook_registry._handlers[MorpheusEvents.AI_USAGE_TODAY] = []

    def test_usage_an_app_reports_is_added_to_the_spend(self):
        before = guardrails.daily_spend_usd()

        def report(value, **kwargs):
            return [*value, {'model': 'gpt-4o', 'pt': 1_000_000, 'ct': 0}]

        hook_registry.register(MorpheusEvents.AI_USAGE_TODAY, report)
        self.assertGreater(guardrails.daily_spend_usd(), before)

    def test_a_broken_reporter_never_lifts_the_cap_for_everyone(self):
        def broken(value, **kwargs):
            raise RuntimeError('reporter down')

        hook_registry.register(MorpheusEvents.AI_USAGE_TODAY, broken)
        self.assertEqual(guardrails.daily_spend_usd(), 0.0)
