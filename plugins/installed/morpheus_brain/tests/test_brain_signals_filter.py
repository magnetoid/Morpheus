"""BRAIN_SIGNALS filter — the Brain aggregator is core, its data slices are
contributed by plugins (arch-debt refactor, Phase 8a).

core/brain/signals.py used to import seo/catalog/ai_assistant/morpheus_brain
models directly. It now seeds the core-owned sections and fires the
BRAIN_SIGNALS filter; each plugin merges ITS OWN read-only slice. These tests
prove the inversion is behaviour-preserving AND disable-safe:

  * the four plugins each register a BRAIN_SIGNALS handler (owned → bus-gated);
  * gather_all() surfaces every contributed slice with all plugins active;
  * deactivating a contributor makes ITS slice vanish — the litmus test that the
    kernel imports no plugin model, so a disabled plugin's Brain panel goes away.
"""

from __future__ import annotations

from django.test import TestCase

from core.brain import signals
from morpheus.core import MorpheusEvents, hook_registry
from plugins.registry import app_registry

_OWNERS = {'seo', 'catalog', 'ai_assistant', 'morpheus_brain'}


class BrainSignalsFilterTests(TestCase):
    def _fresh(self) -> dict:
        # gather_all() is cached; recompute so a mid-test disable is reflected.
        signals.invalidate_signals_cache()
        return signals.gather_all()

    def _seed_insight(self):
        from plugins.installed.ai_assistant.models import MerchantInsight

        return MerchantInsight.objects.create(
            insight_type='opportunity', priority='high', title='Ship it', body='x'
        )

    def test_four_plugins_own_a_brain_signals_handler(self):
        owners = {
            (entry[3] if len(entry) > 3 else None)
            for entry in hook_registry._handlers.get(MorpheusEvents.BRAIN_SIGNALS, [])
        }
        self.assertTrue(owners >= _OWNERS, f'missing: {_OWNERS - owners}')

    def test_all_seven_sections_present_and_dicts(self):
        data = self._fresh()
        for key in (
            'plugins',
            'errors',
            'code',
            'content',
            'storefront',
            'improvements',
            'reports',
        ):
            self.assertIn(key, data)
            self.assertIsInstance(data[key], dict)

    def test_contributed_slices_present_when_active(self):
        # ai_assistant's slice is otherwise indistinguishable from the core seed
        # (both []), so seed one unread insight to make it observable.
        self._seed_insight()
        data = self._fresh()
        # seo slice — queries succeed on an empty DB, so the keys are present.
        self.assertIn('low_seo', data['content'])
        self.assertIn('seo_total', data['content'])
        self.assertIn('cwv', data['storefront'])
        self.assertIn('seo_flags', data['storefront'])
        # catalog slice
        self.assertIn('catalog', data['content'])
        # ai_assistant slice — the seeded insight surfaces
        self.assertIn('Ship it', [i['title'] for i in data['improvements']['insights']])
        # morpheus_brain slice — publishing flips available True
        self.assertTrue(data['reports']['available'])

    def test_seo_slice_vanishes_when_seo_disabled(self):
        self.addCleanup(app_registry.activate, 'seo')
        self.assertIn('cwv', self._fresh()['storefront'])
        app_registry.deactivate('seo')
        data = self._fresh()
        self.assertNotIn('cwv', data['storefront'])
        self.assertNotIn('seo_flags', data['storefront'])
        self.assertNotIn('low_seo', data['content'])

    def test_catalog_slice_vanishes_when_catalog_disabled(self):
        self.addCleanup(app_registry.activate, 'catalog')
        self.assertIn('catalog', self._fresh()['content'])
        app_registry.deactivate('catalog')
        self.assertNotIn('catalog', self._fresh()['content'])

    def test_reports_unavailable_when_morpheus_brain_disabled(self):
        self.addCleanup(app_registry.activate, 'morpheus_brain')
        self.assertTrue(self._fresh()['reports']['available'])
        app_registry.deactivate('morpheus_brain')
        self.assertFalse(self._fresh()['reports']['available'])

    def test_ai_insight_slice_vanishes_when_ai_assistant_disabled(self):
        self._seed_insight()
        self.addCleanup(app_registry.activate, 'ai_assistant')
        self.assertIn('Ship it', [i['title'] for i in self._fresh()['improvements']['insights']])
        app_registry.deactivate('ai_assistant')
        # Falls back to the core seed (empty list), not the seeded insight.
        self.assertEqual(self._fresh()['improvements']['insights'], [])
