"""ADR 0013 — the account-summary gift-card + downloads tiles are CONTRIBUTED by
their owning plugins via the ACCOUNT_SUMMARY_FIELDS hook, NOT hardcoded in the
storefront. So disabling gift_cards / digital_products makes the tile vanish
(the hook only fires while the plugin is enabled), instead of the storefront
querying a disabled plugin's models behind the merchant's back.
"""

# Lazy imports inside test methods are intentional (plugin load-order isolation).
# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

_ACCOUNT_PY = Path(settings.BASE_DIR) / 'plugins/installed/storefront/views/account.py'


class AccountSummaryModularityTests(TestCase):
    def test_account_summary_no_longer_imports_sibling_plugin_models(self):
        # Scope to the _account_summary function body — the dedicated account
        # sub-pages (orders list / credits / downloads) still query those
        # plugins directly; migrating whole pages to plugin-owned routes is a
        # separate increment.
        src = _ACCOUNT_PY.read_text(encoding='utf-8')
        start = src.index('def _account_summary')
        end = src.index('\ndef ', start + 1)
        body = src[start:end]
        for plugin in ('gift_cards', 'digital_products', 'orders'):
            self.assertNotIn(
                f'installed.{plugin}',
                body,
                f'_account_summary still imports {plugin} — it belongs in the plugin hook',
            )

    def test_fresh_user_has_no_plugin_tile_keys(self):
        # The keys appear ONLY when a plugin finds data — never defaulted by storefront.
        from plugins.installed.storefront.views.account import _account_summary

        user = get_user_model().objects.create_user(username='nodata', password='x')
        s = _account_summary(user)
        self.assertNotIn('gift_card_count', s)
        self.assertNotIn('download_count', s)

    def test_gift_cards_tile_contributed_end_to_end(self):
        # GiftCard present → the gift_cards subscriber folds the tile in via the hook.
        from plugins.installed.gift_cards.models import GiftCard
        from plugins.installed.storefront.views.account import _account_summary

        user = get_user_model().objects.create_user(username='hascard', password='x')
        GiftCard.objects.create(
            issued_to_customer=user,
            initial_value=Money(Decimal('25.00'), 'USD'),
            balance=Money(Decimal('25.00'), 'USD'),
            state='active',
        )
        s = _account_summary(user)
        self.assertEqual(s.get('gift_card_count'), 1)
        self.assertEqual(s.get('gift_card_total'), Money(Decimal('25.00'), 'USD'))

    def test_optional_plugins_are_subscribed(self):
        # Wiring guard: both contributing plugins (and loyalty, already migrated)
        # are registered on the ACCOUNT_SUMMARY_FIELDS filter.
        from morpheus.core import MorpheusEvents, hook_registry

        quals = {
            getattr(hook_registry._unpack(entry)[1], '__qualname__', '')
            for entry in hook_registry._handlers.get(MorpheusEvents.ACCOUNT_SUMMARY_FIELDS, [])
        }
        self.assertTrue(any('GiftCardsPlugin' in q for q in quals), 'gift_cards not subscribed')
        self.assertTrue(
            any('DigitalProductsPlugin' in q for q in quals), 'digital_products not subscribed'
        )
        self.assertTrue(any('OrdersPlugin' in q for q in quals), 'orders not subscribed')

    def test_orders_fields_contributed_end_to_end(self):
        # The orders subscriber folds count / returns / store credit in.
        from plugins.installed.orders.models import Order
        from plugins.installed.storefront.views.account import _account_summary

        user = get_user_model().objects.create_user(username='buyer', password='x')
        Order.objects.create(
            customer=user,
            email='buyer@example.com',
            subtotal=Money(Decimal('10.00'), 'USD'),
            total=Money(Decimal('10.00'), 'USD'),
        )
        s = _account_summary(user)
        self.assertEqual(s.get('orders_count'), 1)
        self.assertEqual(s.get('pending_returns'), 0)

    def test_downloads_route_is_owned_by_digital_products(self):
        # The /account/downloads/ route is registered BY the plugin, so disabling
        # digital_products makes it 404 (ADR 0013) — and the storefront no longer
        # owns it.
        from django.urls import NoReverseMatch, reverse

        self.assertEqual(
            reverse('digital_products_account:account_downloads'), '/account/downloads/'
        )
        with self.assertRaises(NoReverseMatch):
            reverse('storefront:account_downloads')
