"""Dashboard contributions (ADR 0023): the product-list column, its bulk
action, and the fulfilment form card arrive via PRODUCT_LIST_COLUMNS /
PRODUCT_FORM_CARDS — admin_dashboard imports nothing from bookvault, so both
surfaces vanish when the plugin is disabled. Before this, the hard-coded
column survived disable-while-configured, and a boot-disabled bookvault
NoReverseMatch-500'd the whole product list."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.bookvault.models import BookvaultProductLink
from plugins.installed.bookvault.tests.test_services import _seed_config
from plugins.installed.catalog.models import Product
from plugins.registry import plugin_registry


def _product(slug: str) -> Product:
    return Product.objects.create(
        name=f'Book {slug}',
        slug=slug,
        sku=f'SKU-{slug}',
        status='active',
        price=Money(Decimal('9.00'), 'USD'),
    )


class ListColumnContributionTests(TestCase):
    def _columns(self, products):
        return hook_registry.filter(
            MorpheusEvents.PRODUCT_LIST_COLUMNS, value=[], products=products, request=None
        )

    def test_unauthed_contributes_nothing(self):
        self.assertEqual(self._columns([_product('quiet')]), [])

    def test_authed_contributes_column_and_annotates_products(self):
        _seed_config()
        linked, bare = _product('linked'), _product('bare')
        BookvaultProductLink.objects.create(product=linked, is_linked=True)
        cols = self._columns([linked, bare])
        self.assertEqual(len(cols), 1)
        self.assertEqual(cols[0]['label'], 'BV')
        self.assertEqual(cols[0]['cell_template'], 'bookvault/_product_list_cell.html')
        self.assertEqual(cols[0]['bulk_action']['field'], 'ids')
        self.assertEqual(cols[0]['bulk_action']['url'], reverse('bookvault:bulk_link'))
        self.assertEqual(linked.bv_link_status, 'Linked')
        self.assertEqual(bare.bv_link_status, 'Unlinked')

    def test_disabled_plugin_contributes_nothing(self):
        _seed_config()  # configured — the disabled-while-configured leak case
        was_active = 'bookvault' in plugin_registry._active
        plugin_registry._active.discard('bookvault')
        try:
            self.assertEqual(self._columns([_product('gated')]), [])
        finally:
            if was_active:
                plugin_registry._active.add('bookvault')


class FormCardContributionTests(TestCase):
    def _bv_cards(self, product):
        cards = hook_registry.filter(MorpheusEvents.PRODUCT_FORM_CARDS, value=[], product=product)
        return [c for c in cards if c.get('template') == 'bookvault/_product_form_card.html']

    def test_no_product_or_unauthed_contributes_nothing(self):
        self.assertEqual(self._bv_cards(None), [])
        _seed_config(authenticated=False)
        self.assertEqual(self._bv_cards(_product('no-card')), [])

    def test_authed_card_contributes_and_renders(self):
        _seed_config()
        p = _product('carded')
        BookvaultProductLink.objects.create(product=p, is_linked=False)
        cards = self._bv_cards(p)
        self.assertEqual(len(cards), 1)
        html = render_to_string(cards[0]['template'], {**cards[0]['context'], 'product': p})
        self.assertIn('Bookvault fulfilment', html)
        self.assertIn('Pending', html)  # the unlinked row's pill
        self.assertIn('Edit on Bookvault', html)


class ProductsPageEndToEndTests(TestCase):
    """Full round trip: subscriber → _collect_product_list_columns →
    products.html. Header, per-row pill, and bulk button render while active;
    every trace disappears — with a 200, not the old NoReverseMatch 500 —
    when the plugin is disabled."""

    def setUp(self):
        u = get_user_model().objects.create_user(
            username='bvstaff', email='bv@x.test', password='pw', is_staff=True
        )
        self.client.force_login(u)

    def test_column_and_bulk_action_render_when_authed(self):
        _seed_config()
        p = _product('page')
        BookvaultProductLink.objects.create(product=p, is_linked=True)
        resp = self.client.get(reverse('admin_dashboard:products'))
        self.assertContains(resp, '<th>BV</th>', html=True)
        self.assertContains(resp, 'pill-success')
        self.assertContains(resp, 'Send to Bookvault')
        self.assertContains(resp, 'data-bulk-ext-form')

    def test_everything_vanishes_when_disabled(self):
        _seed_config()
        _product('page2')
        was_active = 'bookvault' in plugin_registry._active
        plugin_registry._active.discard('bookvault')
        try:
            resp = self.client.get(reverse('admin_dashboard:products'))
            self.assertEqual(resp.status_code, 200)
            self.assertNotContains(resp, 'Send to Bookvault')
            self.assertNotContains(resp, '<th>BV</th>', html=True)
        finally:
            if was_active:
                plugin_registry._active.add('bookvault')
