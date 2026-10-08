"""Dashboard cards — two apps' widgets on one page (docs/plans/dashboard-hubs-2026-10.md).

An app contributes `DashboardCard(section=…)`; the shell draws it on that
section's landing (the Marketing overview, the Products, Orders and
Customers lists, the Analytics report). These tests hold the contract:

* every in-tree card's data function runs on an empty store and returns the
  card shape (a card that raises is a card the merchant never sees work);
* the cards land on their pages, next to each other;
* a card that raises shows its error state and is logged — the page stays up;
* a card that returns None is left off;
* a disabled app's card leaves with it;
* under rbac `enforce` a card needs its capability, and every capability a
  card names is one a role can hold.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import contextlib
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase

from morpheus.app import DashboardCard
from plugins.installed.admin_dashboard import cards as card_module
from plugins.installed.admin_dashboard import navigation
from plugins.registry import app_registry

_KEYS = {'value', 'caption', 'rows', 'tone', 'empty', 'url'}


@contextlib.contextmanager
def disabled(name: str):
    assert app_registry.is_active(name), f'{name} must ship active for this test'
    app_registry.deactivate(name)
    cache.clear()
    try:
        yield
    finally:
        app_registry.activate(name)
        cache.clear()


@contextlib.contextmanager
def extra_card(card):
    app_registry._dashboard_cards.append(card)
    try:
        yield
    finally:
        app_registry._dashboard_cards.remove(card)


class _Staff(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='card-owner',
            email='card-owner@example.test',
            password='x',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)

    def request(self, path='/dashboard/'):
        request = RequestFactory().get(path)
        request.user = self.user
        return request


class InTreeCardsTests(_Staff):
    def test_every_card_runs_on_an_empty_store(self):
        contributed = app_registry.dashboard_cards()
        self.assertGreaterEqual(len(contributed), 10)
        for card in [*contributed, *card_module.CORE_CARDS]:
            with self.subTest(card=card.title):
                data = card_module._resolve(card.data)(self.request())
                self.assertIsInstance(data, dict)
                self.assertTrue(set(data) <= _KEYS, set(data) - _KEYS)
                self.assertIn(
                    navigation.main_section_key(card.section), navigation.card_section_keys()
                )

    def test_every_capability_a_card_names_is_one_a_role_holds(self):
        from plugins.installed.rbac.models import _DEFAULT_TEMPLATES

        vocabulary = {cap for caps in _DEFAULT_TEMPLATES.values() for cap in caps}
        for card in [*app_registry.dashboard_cards(), *card_module.CORE_CARDS]:
            if card.capability:
                self.assertIn(card.capability, vocabulary, card.title)

    def test_the_marketing_overview_carries_several_apps_cards(self):
        html = self.client.get('/dashboard/marketing/').content.decode()
        for marker in (
            'marketing:Coupons',
            'promotions:Promotions',
            'gift_cards:Gift cards',
            'newsletter:Newsletter',
            'affiliates:Affiliates',
            'eco_impact:Eco impact',
        ):
            self.assertIn(f'data-card="{marker}"', html)

    def test_list_landings_carry_their_cards(self):
        self.assertIn(
            'data-card="inventory:Stockout forecast"',
            self.client.get('/dashboard/products/').content.decode(),
        )
        self.assertIn(
            'data-card="core:Content audit"',
            self.client.get('/dashboard/products/').content.decode(),
        )
        self.assertIn(
            'data-card="loyalty_points:Loyalty points"',
            self.client.get('/dashboard/customers/').content.decode(),
        )
        self.assertIn(
            'data-card="post_purchase:NPS"',
            self.client.get('/dashboard/analytics/').content.decode(),
        )

    def test_a_filtered_list_is_about_the_list(self):
        self.assertNotIn(
            'data-card=', self.client.get('/dashboard/products/?q=anything').content.decode()
        )

    def test_a_card_shows_real_numbers(self):
        from decimal import Decimal

        from plugins.installed.marketing.models import Coupon

        Coupon.objects.create(
            code='LIVE10',
            name='Live',
            discount_type='percentage',
            discount_value=Decimal('10'),
            times_used=3,
        )
        Coupon.objects.create(code='OFF', name='Off', discount_type='percentage', is_active=False)
        drawn = next(
            c for c in card_module.cards_for('marketing', self.request()) if c['title'] == 'Coupons'
        )
        self.assertEqual(drawn['value'], '1')
        self.assertEqual(drawn['rows'][0]['label'], 'LIVE10')


class CardFailureTests(_Staff):
    def test_a_card_that_raises_shows_its_error_and_the_page_stays_up(self):
        def boom(request):
            raise RuntimeError('card data broke')

        card = DashboardCard(section='marketing', title='Broken', data=boom, plugin='_cards_test')
        with extra_card(card), self.assertLogs('morpheus.admin', level='ERROR') as logs:
            resp = self.client.get('/dashboard/marketing/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-card="_cards_test:Broken"')
        self.assertContains(resp, 'couldn’t load')
        self.assertTrue(any('Broken' in line for line in logs.output))

    def test_a_card_with_nothing_to_say_is_left_off(self):
        card = DashboardCard(
            section='marketing', title='Quiet', data=lambda request: None, plugin='_cards_test'
        )
        with extra_card(card):
            html = self.client.get('/dashboard/marketing/').content.decode()
        self.assertNotIn('_cards_test:Quiet', html)

    def test_legacy_section_keys_reach_their_landing(self):
        card = DashboardCard(
            section='growth',
            title='Old key',
            data=lambda request: {'value': '7'},
            plugin='_cards_test',
        )
        with extra_card(card):
            titles = [c['title'] for c in card_module.cards_for('marketing', self.request())]
        self.assertIn('Old key', titles)


class CardDisableAndAccessTests(_Staff):
    def test_a_disabled_apps_card_leaves(self):
        marker = 'data-card="gift_cards:Gift cards"'
        self.assertIn(marker, self.client.get('/dashboard/marketing/').content.decode())
        with disabled('gift_cards'):
            self.assertNotIn(marker, self.client.get('/dashboard/marketing/').content.decode())

    def test_enforce_mode_hides_a_card_its_user_may_not_see(self):
        staff = get_user_model().objects.create_user(
            username='card-staff', email='card-staff@example.test', password='x', is_staff=True
        )
        request = RequestFactory().get('/dashboard/marketing/')
        request.user = staff
        with (
            patch('core.authz.enforcement_mode', return_value='enforce'),
            patch('core.authz.has_capability', return_value=False),
        ):
            titles = [c['title'] for c in card_module.cards_for('marketing', request)]
        self.assertNotIn('Coupons', titles)
        # Log-only mode (the default) hides nothing.
        self.assertIn('Coupons', [c['title'] for c in card_module.cards_for('marketing', request)])


class AppsCatalogueTests(_Staff):
    def test_apps_are_grouped_the_way_the_menu_is(self):
        from plugins.installed.admin_dashboard.views_split.apps import is_system

        html = self.client.get('/dashboard/apps/').content.decode()
        for heading in ('Orders', 'Products', 'Marketing', 'Sales channels', 'Storefront'):
            self.assertIn(f'>{heading} <span', html)
        self.assertFalse(is_system('gift_cards'))

    def test_an_app_says_what_it_adds(self):
        described = navigation.describe_app(app_registry.get('gift_cards'))
        self.assertEqual(described['area'], 'marketing')
        self.assertIn('a page in Marketing', described['adds'])
        self.assertIn('a card on Marketing', described['adds'])
        self.assertIn('settings in Marketing', described['adds'])

    def test_an_app_that_is_off_still_says_what_it_would_add(self):
        with disabled('eco_impact'):
            described = navigation.describe_app(app_registry.get('eco_impact'))
        self.assertIn('a card on Marketing', described['adds'])
