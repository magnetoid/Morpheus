"""Dashboard nav section registry (core/nav.py) + grouping resolution.

Guards ADR 0012: every DashboardPage.section resolves to a canonical registry
key; unknown values land in 'apps' and never mint a stray top-level header.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from core.nav import CATCH_ALL, ordered_keys, resolve_section, section_meta
from plugins.context_processors import _group_by_section
from plugins.contributions import DashboardPage


class ResolveSectionTests(SimpleTestCase):
    def test_known_key_resolves_to_itself(self):
        self.assertEqual(resolve_section('products'), 'products')
        self.assertEqual(resolve_section('settings'), 'settings')

    def test_legacy_alias_maps_to_canonical(self):
        self.assertEqual(resolve_section('catalog'), 'products')
        self.assertEqual(resolve_section('sales'), 'orders')
        self.assertEqual(resolve_section('crm'), 'customers')
        self.assertEqual(resolve_section('cms'), 'content')
        self.assertEqual(resolve_section('seo'), 'content')
        self.assertEqual(resolve_section('growth'), 'marketing')
        self.assertEqual(resolve_section('marketplace'), 'marketing')
        self.assertEqual(resolve_section('plugins'), 'apps')

    def test_unknown_or_empty_falls_to_apps(self):
        self.assertEqual(resolve_section('b2b'), CATCH_ALL)
        self.assertEqual(resolve_section('totally-made-up'), CATCH_ALL)
        self.assertEqual(resolve_section(''), CATCH_ALL)
        self.assertEqual(resolve_section(None), CATCH_ALL)

    def test_ordered_keys_are_sorted_and_apps_last(self):
        keys = ordered_keys()
        self.assertEqual(keys[0], 'home')
        self.assertEqual(keys[-1], 'apps')
        self.assertIn('ai', keys)

    def test_section_meta_label_and_icon(self):
        self.assertEqual(section_meta('products').label, 'Products')
        self.assertEqual(section_meta('apps').key, 'apps')


class GroupBySectionTests(SimpleTestCase):
    def _page(self, section, slug='p'):
        return DashboardPage(
            label=slug, slug=slug, view=lambda r: None, section=section, plugin='x'
        )

    def test_unknown_section_never_makes_stray_header(self):
        groups = _group_by_section([self._page('b2b'), self._page('totally-made-up')])
        keys = [g['key'] for g in groups]
        self.assertEqual(keys, ['apps'])  # both collapsed into apps, no 'b2b' header

    def test_aliases_merge_into_canonical_group(self):
        groups = _group_by_section(
            [self._page('cms', 'a'), self._page('seo', 'b'), self._page('catalog', 'c')]
        )
        by_key = {g['key']: g for g in groups}
        self.assertIn('content', by_key)
        self.assertIn('products', by_key)
        self.assertEqual(len(by_key['content']['pages']), 2)  # cms + seo
        self.assertNotIn('cms', by_key)
        self.assertNotIn('seo', by_key)

    def test_groups_render_in_registry_order(self):
        groups = _group_by_section(
            [self._page('analytics', 'a'), self._page('orders', 'b'), self._page('ai', 'c')]
        )
        keys = [g['key'] for g in groups]
        self.assertEqual(keys, ['ai', 'orders', 'analytics'])  # ai(15) < orders(20) < analytics(70)

    def test_every_group_label_and_icon_populated(self):
        groups = _group_by_section([self._page('orders'), self._page('zzz-unknown')])
        for g in groups:
            self.assertTrue(g['label'])
            self.assertTrue(g['icon'])
