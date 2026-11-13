"""Linda's markets tools: reads, and writes that ask first and use the dashboard's rules."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings
from djmoney.money import Money

from core.agents.registry import agent_registry
from core.assistant.gates import CAPABILITY_FOR_SCOPE, LINDA_SCOPES
from core.models import ExchangeRate
from morpheus.core import ToolError
from plugins.installed.agent_mcp.scopes import AVAILABLE_SCOPES
from plugins.installed.catalog.models import Product
from plugins.installed.markets.models import Market, ProductMarketPrice

READS = ('markets.list', 'markets.get')
WRITES = (
    'markets.save',
    'markets.delete',
    'markets.set_product_price',
    'markets.set_rate',
    'markets.refresh_rates',
)


def _run(name, **args):
    return agent_registry.get_tool(name).invoke(args)


class ToolShapeTests(TestCase):
    def test_the_markets_app_owns_every_tool(self):
        for name in (*READS, *WRITES):
            with self.subTest(name):
                self.assertEqual(agent_registry._tool_owners.get(name), 'markets')

    def test_reads_use_the_read_scope_and_writes_ask_first_under_the_write_scope(self):
        for name in READS:
            tool = agent_registry.get_tool(name)
            self.assertEqual(list(tool.scopes), ['markets.read'])
            self.assertFalse(tool.requires_approval, name)
        for name in WRITES:
            tool = agent_registry.get_tool(name)
            self.assertEqual(list(tool.scopes), ['markets.write'])
            self.assertTrue(tool.requires_approval, name)

    def test_the_scopes_are_in_the_vocabulary_and_in_lindas_profile(self):
        for scope, capability in (
            ('markets.read', 'catalog.read'),
            ('markets.write', 'catalog.write'),
        ):
            self.assertIn(scope, AVAILABLE_SCOPES)
            self.assertIn(scope, LINDA_SCOPES)
            self.assertEqual(CAPABILITY_FOR_SCOPE[scope], capability)


@override_settings(STORE_CURRENCY='USD')
class ReadToolTests(TestCase):
    def setUp(self):
        self.market = Market.objects.create(code='eu', label='Europe', currency='EUR')
        for i in range(7):
            Product.objects.create(
                name=f'P{i}',
                slug=f'p{i}',
                sku=f'P{i}',
                status='active',
                price=Money(Decimal('10'), 'USD'),
            )

    def test_list(self):
        out = _run('markets.list').output
        self.assertEqual(out['count'], 1)
        self.assertEqual(out['markets'][0]['rounding'], 'exact')

    def test_get_without_a_rate_says_so(self):
        out = _run('markets.get', code='eu').output
        self.assertIsNone(out['rate']['rate'])
        self.assertTrue(out['rate']['out_of_date'])
        self.assertEqual(len(out['preview']), 5)
        self.assertIsNone(out['preview'][0]['market_price'])

    def test_get_with_a_rate_prices_five_products(self):
        ExchangeRate.objects.create(
            base_currency='USD', quote_currency='EUR', rate=Decimal('0.92'), source='manual'
        )
        out = _run('markets.get', code='eu').output
        self.assertEqual(out['rate']['source'], 'manual')
        self.assertFalse(out['rate']['out_of_date'])
        self.assertIn('9.20', out['preview'][0]['market_price'])

    def test_get_unknown_code(self):
        with self.assertRaisesMessage(ToolError, 'no market with the code "xx"'):
            _run('markets.get', code='xx')


@override_settings(STORE_CURRENCY='USD')
class WriteToolTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Mug', slug='mug', sku='MUG', price=Money(Decimal('10'), 'USD')
        )
        ExchangeRate.objects.create(
            base_currency='USD', quote_currency='EUR', rate=Decimal('0.92'), source='ecb'
        )

    def test_save_creates_then_updates_only_what_is_given(self):
        out = _run(
            'markets.save', code='eu', label='Europe', currency='EUR', country_codes=['DE', 'fr']
        ).output
        self.assertTrue(out['created'])
        out = _run('markets.save', code='eu', rounding='ninety_nine').output
        self.assertFalse(out['created'])
        market = Market.objects.get(code='eu')
        self.assertEqual(market.country_codes, ['DE', 'FR'])
        self.assertEqual(market.rounding, 'ninety_nine')
        self.assertEqual(market.label, 'Europe')

    def test_save_refusal_comes_back_as_the_error_text(self):
        with self.assertRaisesMessage(ToolError, 'Add an exchange rate for JPY first.'):
            _run('markets.save', code='jp', label='Japan', currency='JPY')
        with self.assertRaisesMessage(ToolError, 'not a currency code'):
            _run('markets.save', code='x', label='X', currency='QQQ')
        self.assertFalse(Market.objects.exists())

    def test_delete(self):
        Market.objects.create(code='eu', label='Europe', currency='EUR')
        _run('markets.delete', code='eu')
        self.assertFalse(Market.objects.exists())
        with self.assertRaisesMessage(ToolError, 'no market'):
            _run('markets.delete', code='eu')

    def test_set_and_remove_a_fixed_price_by_slug_or_id(self):
        market = Market.objects.create(code='eu', label='Europe', currency='EUR')
        _run('markets.set_product_price', code='eu', product='mug', amount=9.5)
        self.assertEqual(
            ProductMarketPrice.objects.get(market=market).price, Money(Decimal('9.50'), 'EUR')
        )
        _run('markets.set_product_price', code='eu', product=str(self.product.pk), amount=8)
        self.assertEqual(ProductMarketPrice.objects.get().price, Money(Decimal('8.00'), 'EUR'))
        _run('markets.set_product_price', code='eu', product='mug', clear=True)
        self.assertFalse(ProductMarketPrice.objects.exists())

    def test_fixed_price_refusals(self):
        Market.objects.create(code='eu', label='Europe', currency='EUR')
        Market.objects.create(code='us', label='US', currency='USD')
        for args, text in (
            (dict(code='eu', product='nope', amount=5), 'no product'),
            (dict(code='nope', product='mug', amount=5), 'no market'),
            (dict(code='eu', product='mug', amount=0), 'more than zero'),
            (dict(code='eu', product='mug', amount=0.001), 'more than zero'),
            (dict(code='eu', product='mug'), 'clear: true'),
            (dict(code='eu', product='mug', amount=5, clear=True), 'clear: true'),
            (dict(code='eu', product='mug', amount='abc'), 'must be a number'),
            (dict(code='us', product='mug', amount=5), 'store currency'),
        ):
            with self.subTest(args), self.assertRaisesMessage(ToolError, text):
                _run('markets.set_product_price', **args)
        self.assertFalse(ProductMarketPrice.objects.exists())

    def test_set_rate_and_clear_it(self):
        _run('markets.set_rate', currency='chf', rate=0.88)
        row = ExchangeRate.objects.get(quote_currency='CHF')
        self.assertEqual((row.rate, row.source), (Decimal('0.88000000'), 'manual'))
        _run('markets.set_rate', currency='CHF', clear=True)
        self.assertFalse(ExchangeRate.objects.filter(quote_currency='CHF').exists())

    def test_set_rate_refusals(self):
        for args, text in (
            (dict(currency='EUR', rate=-1), 'more than zero'),
            (dict(currency='USD', rate=1), 'other than USD'),
            (dict(currency='EUR', rate='x'), 'must be a number'),
            (dict(currency='EUR'), 'clear: true'),
        ):
            with self.subTest(args), self.assertRaisesMessage(ToolError, text):
                _run('markets.set_rate', **args)

    def test_a_comma_rate_is_accepted(self):
        _run('markets.set_rate', currency='CHF', rate='0,88')
        self.assertEqual(ExchangeRate.objects.get(quote_currency='CHF').rate, Decimal('0.88'))

    def test_a_yen_price_that_rounds_to_zero_is_refused(self):
        Market.objects.create(code='jp', label='Japan', currency='JPY')
        with self.assertRaisesMessage(ToolError, 'more than zero'):
            _run('markets.set_product_price', code='jp', product='mug', amount=0.4)

    def test_clearing_a_rate_an_active_market_needs_is_refused_when_nothing_replaces_it(self):
        Market.objects.create(code='ch', label='Swiss', currency='CHF')
        ExchangeRate.objects.create(
            base_currency='USD', quote_currency='CHF', rate=Decimal('0.9'), source='manual'
        )
        with (
            mock.patch('plugins.installed.markets.rates.fetch_ecb', side_effect=OSError('x')),
            self.assertRaisesMessage(ToolError, 'Your rate stays'),
        ):
            _run('markets.set_rate', currency='CHF', clear=True)

    def test_refresh_rates_refuses_when_rates_are_typed_by_hand(self):
        with (
            mock.patch('plugins.installed.markets.tasks.rate_source', return_value='manual'),
            self.assertRaisesMessage(ToolError, 'set by hand'),
        ):
            _run('markets.refresh_rates')

    def test_refresh_rates(self):
        with mock.patch(
            'plugins.installed.markets.rates.fetch_ecb',
            return_value={'written': 3, 'kept_manual': [], 'date': '2026-11-13'},
        ):
            out = _run('markets.refresh_rates').output
        self.assertEqual(out['written'], 3)
        with (
            mock.patch('plugins.installed.markets.rates.fetch_ecb', side_effect=OSError('down')),
            self.assertRaisesMessage(ToolError, 'Could not fetch the rates just now: down'),
        ):
            _run('markets.refresh_rates')


class ModeReachTests(TestCase):
    """markets.list left system.read; every mode that reached it by that scope keeps it."""

    def test_markets_list_survives_the_modes_that_hold_catalog_read(self):
        from core.assistant.modes import filter_tools_by_mode

        tool = agent_registry.get_tool('markets.list')
        for mode in ('sales', 'support', 'ops', 'general'):
            with self.subTest(mode):
                self.assertIn(tool, filter_tools_by_mode([tool], mode))

    def test_only_ops_may_write_markets(self):
        from core.assistant.modes import filter_tools_by_mode

        tool = agent_registry.get_tool('markets.save')
        self.assertIn(tool, filter_tools_by_mode([tool], 'ops'))
        for mode in ('sales', 'support'):
            self.assertNotIn(tool, filter_tools_by_mode([tool], mode))

    def test_the_worker_holds_both_scopes(self):
        from core.agents.builtin.worker import Worker

        self.assertLessEqual({'markets.read', 'markets.write'}, set(Worker.scopes))
