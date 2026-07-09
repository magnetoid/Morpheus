"""Surface-takeover tests — the STOREFRONT_PRODUCTS hook (M1 of the plan)."""

from __future__ import annotations

from decimal import Decimal

from django.test import RequestFactory, TestCase
from djmoney.money import Money

from core.hooks import MorpheusEvents, hook_registry
from plugins.installed.catalog.models import Product
from plugins.installed.dynamics.models import DynamicBlock


def _product(slug, name=None):
    return Product.objects.create(
        name=name or slug.title(),
        slug=slug,
        sku=slug,
        status='active',
        price=Money(Decimal('10'), 'USD'),
    )


def _fire(value, surface, limit=8):
    return hook_registry.filter(
        MorpheusEvents.STOREFRONT_PRODUCTS,
        value=value,
        surface=surface,
        request=RequestFactory().get('/'),
        limit=limit,
    )


class FreePickTests(TestCase):
    def setUp(self):
        self.p1 = _product('older')
        self.p2 = _product('newer')

    def test_no_block_leaves_default_untouched(self):
        self.assertIsNone(_fire(None, 'home_featured'))

    def test_block_takes_over_with_strategy_picks(self):
        DynamicBlock.objects.create(
            name='Featured takeover',
            surface='home_featured',
            strategy='new_arrivals',
            limit=8,
        )
        picks = _fire(None, 'home_featured')
        self.assertEqual([p.slug for p in picks], ['newer', 'older'])

    def test_disabled_block_is_ignored(self):
        DynamicBlock.objects.create(
            name='Off', surface='home_featured', strategy='new_arrivals', enabled=False
        )
        self.assertIsNone(_fire(None, 'home_featured'))

    def test_limit_caps_free_pick(self):
        DynamicBlock.objects.create(
            name='Hero', surface='home_hero', strategy='new_arrivals', limit=8
        )
        picks = _fire(None, 'home_hero', limit=1)
        self.assertEqual(len(picks), 1)


class ReorderTests(TestCase):
    def setUp(self):
        self.a = _product('aaa')
        self.b = _product('bbb')
        self.c = _product('ccc')

    def test_no_block_passes_list_through(self):
        items = [self.a, self.b]
        self.assertEqual(_fire(items, 'plp_default'), items)

    def test_reorder_never_introduces_new_items(self):
        DynamicBlock.objects.create(
            name='PLP', surface='plp_default', strategy='new_arrivals', limit=24
        )
        out = _fire([self.a, self.b], 'plp_default')
        self.assertEqual({p.pk for p in out}, {self.a.pk, self.b.pk})
        # new_arrivals ranks newest first → b before a.
        self.assertEqual([p.slug for p in out], ['bbb', 'aaa'])

    def test_pins_outrank_ranking_and_excludes_drop(self):
        DynamicBlock.objects.create(
            name='PLP',
            surface='plp_default',
            strategy='new_arrivals',
            limit=24,
            pinned_product_ids=[str(self.a.pk)],
            excluded_product_ids=[str(self.b.pk)],
        )
        out = _fire([self.a, self.b, self.c], 'plp_default')
        self.assertEqual([p.slug for p in out], ['aaa', 'ccc'])

    def test_dict_items_supported(self):
        # Home featured items arrive as GraphQL dicts; reorder must handle them.
        DynamicBlock.objects.create(
            name='SP', surface='home_staff_picks', strategy='new_arrivals', limit=24
        )
        items = [{'id': str(self.a.pk), 'name': 'A'}, {'id': str(self.c.pk), 'name': 'C'}]
        out = _fire(items, 'home_staff_picks')
        self.assertEqual({d['id'] for d in out}, {str(self.a.pk), str(self.c.pk)})


class DisableGatingTests(TestCase):
    def test_inactive_dynamics_reverts_to_default(self):
        from plugins.registry import plugin_registry

        DynamicBlock.objects.create(
            name='Featured', surface='home_featured', strategy='new_arrivals'
        )
        _product('one')
        was_active = plugin_registry.is_active('dynamics')
        try:
            plugin_registry._active.discard('dynamics')
            # Bus gates on active-state (ADR 0023): handler skipped → default stands.
            self.assertIsNone(_fire(None, 'home_featured'))
        finally:
            if was_active:
                plugin_registry._active.add('dynamics')
