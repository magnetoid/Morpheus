"""Whole-branch review fixes: the rate setting, stale config, currency changes, outcomes,
races, rounding, bounds and the app's settings panel."""

from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from djmoney.money import Money

from core.models import ExchangeRate
from morpheus.core import ToolError
from plugins.installed.catalog.models import Product
from plugins.installed.markets import rates, tasks
from plugins.installed.markets.models import Market, ProductMarketPrice
from plugins.installed.markets.pricing import market_price
from plugins.installed.markets.services import removed_prices_note, save_market
from plugins.registry import app_registry


def _product(price='10.00', slug='thing'):
    return Product.objects.create(
        name=slug, slug=slug, sku=slug, price=Money(price, 'USD'), status='active'
    )


def _rate(quote, rate, source='ecb'):
    ExchangeRate.objects.create(
        base_currency='USD', quote_currency=quote, rate=Decimal(rate), source=source
    )


class RateSourceOnTheMarketsPageTests(TestCase):
    """One place for markets: the rate source is chosen on the Markets page."""

    def setUp(self):
        plugin = app_registry.get('markets')
        self.addCleanup(plugin.invalidate_config_cache)
        self.url = reverse('markets:rate_source')

    def test_no_separate_settings_panel(self):
        self.assertIsNone(app_registry.get('markets').contribute_settings_panel())

    def test_the_page_offers_the_choice_and_saves_it(self):
        user = get_user_model().objects.create_superuser('s', 's@x.test', 'pw')
        self.client.force_login(user)
        page = self.client.get(reverse('markets:index')).content.decode()
        self.assertIn('name="rate_source"', page)
        self.client.post(self.url, {'rate_source': 'manual'})
        self.assertEqual(tasks.rate_source(), 'manual')
        page = self.client.get(reverse('markets:index')).content.decode()
        self.assertNotIn('Fetch rates now', page)
        self.client.post(self.url, {'rate_source': 'ecb'})
        self.assertEqual(tasks.rate_source(), 'ecb')

    def test_an_unknown_source_is_refused(self):
        user = get_user_model().objects.create_superuser('s', 's@x.test', 'pw')
        self.client.force_login(user)
        r = self.client.post(self.url, {'rate_source': 'cloudflare'})
        self.assertIn('Choose where', ' '.join(str(m) for m in get_messages(r.wsgi_request)))
        self.assertEqual(tasks.rate_source(), 'ecb')

    def test_anonymous_is_sent_to_sign_in(self):
        r = self.client.post(self.url, {'rate_source': 'manual'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(tasks.rate_source(), 'ecb')


class RateSourceFreshTests(TestCase):
    def test_a_stored_change_is_followed_in_the_same_process(self):
        plugin = app_registry.get('markets')
        self.addCleanup(plugin.invalidate_config_cache)
        plugin.set_config('rate_source', 'ecb')
        self.assertEqual(tasks.rate_source(), 'ecb')
        plugin.set_config('rate_source', 'manual')
        # The in-process cache still holds 'ecb' until it is invalidated.
        plugin._config_cache = {'rate_source': 'ecb'}
        self.assertEqual(tasks.rate_source(), 'manual')


@override_settings(STORE_CURRENCY='USD')
class CurrencyChangeTests(TestCase):
    def setUp(self):
        _rate('EUR', '0.9')
        _rate('JPY', '150')
        self.product = _product()
        self.market = Market.objects.create(code='x', label='X', currency='EUR')
        ProductMarketPrice.objects.create(
            market=self.market, product=self.product, price=Money('8.50', 'EUR')
        )

    def test_a_fixed_price_in_another_currency_is_not_used(self):
        # A row left in EUR on a JPY market (as an older save could leave it).
        Market.objects.filter(pk=self.market.pk).update(currency='JPY')
        self.market.refresh_from_db()
        price = market_price(self.product, self.market)
        self.assertEqual(price, Money('1500', 'JPY'))

    def test_changing_currency_removes_the_fixed_prices_and_says_so(self):
        saved = save_market({'currency': 'JPY'}, self.market)
        self.assertFalse(ProductMarketPrice.objects.exists())
        self.assertEqual(saved.removed_fixed_prices, 1)
        self.assertEqual(
            removed_prices_note(saved),
            'Removed 1 fixed price in EUR, since the market now uses JPY.',
        )

    def test_the_same_currency_keeps_them(self):
        saved = save_market({'label': 'Renamed'}, self.market)
        self.assertEqual(ProductMarketPrice.objects.count(), 1)
        self.assertEqual(saved.removed_fixed_prices, 0)
        self.assertEqual(removed_prices_note(saved), '')

    def test_the_tool_text_names_the_removal(self):
        from core.agents.registry import agent_registry

        tool = agent_registry.get_tool('markets.save')
        out = tool.handler(code='x', currency='JPY')
        self.assertIn('Removed 1 fixed price in EUR', out.display)
        self.assertEqual(out.output['removed_fixed_prices'], 1)


@override_settings(STORE_CURRENCY='USD')
class OutcomeTests(TestCase):
    def test_no_manual_row_is_none_and_deletes_nothing(self):
        _rate('EUR', '0.9')
        Market.objects.create(code='eu', label='EU', currency='EUR')
        self.assertEqual(rates.set_manual_rate('EUR', None), 'none')
        self.assertEqual(ExchangeRate.objects.get(quote_currency='EUR').source, 'ecb')

    def test_a_rate_that_still_resolves_is_daily_whatever_the_source(self):
        # The inverse row (EUR -> USD) still answers once the manual one is gone.
        ExchangeRate.objects.create(
            base_currency='EUR', quote_currency='USD', rate=Decimal('1.1'), source='ecb'
        )
        rates.set_manual_rate('EUR', Decimal('0.5'))
        self.assertEqual(rates.set_manual_rate('EUR', None), 'daily')

    def test_rates_typed_by_hand_never_promise_a_daily_rate(self):
        plugin = app_registry.get('markets')
        self.addCleanup(plugin.invalidate_config_cache)
        plugin.set_config('rate_source', 'manual')
        ExchangeRate.objects.create(
            base_currency='EUR', quote_currency='USD', rate=Decimal('1.1'), source='manual'
        )
        rates.set_manual_rate('EUR', Decimal('0.5'))
        outcome = rates.set_manual_rate('EUR', None)
        self.assertEqual(outcome, 'daily')
        text = rates.removed_rate_text('EUR', outcome)
        self.assertIn('another rate on file', text)
        self.assertNotIn('daily', text)

    def test_page_says_nothing_was_removed(self):
        _rate('EUR', '0.9')
        market = Market.objects.create(code='eu', label='EU', currency='EUR')
        user = get_user_model().objects.create_superuser('s', 's@x.test', 'pw')
        self.client.force_login(user)
        r = self.client.post(reverse('markets:rate', args=[market.pk]), {'rate': ''})
        text = ' '.join(str(m) for m in get_messages(r.wsgi_request))
        self.assertIn('no rate of yours for EUR', text)
        self.assertNotIn('Removed your rate', text)

    def test_the_tool_says_none(self):
        from core.agents.registry import agent_registry

        out = agent_registry.get_tool('markets.set_rate').handler(currency='EUR', clear=True)
        self.assertEqual(out.output['result'], 'none')
        self.assertIn('no rate of yours', out.display)

    def test_no_fetch_runs_inside_a_transaction(self):
        from django.db import connection

        Market.objects.create(code='eu', label='EU', currency='EUR')
        rates.set_manual_rate('EUR', Decimal('0.5'))
        outer = len(connection.savepoint_ids)
        seen = []

        def fetch():
            # TestCase wraps the test in one atomic block; the fetch must add no level.
            seen.append(len(connection.savepoint_ids))
            raise OSError('down')

        with (
            mock.patch.object(rates, 'fetch_ecb', side_effect=fetch),
            self.assertRaisesMessage(ValidationError, 'Your rate stays'),
        ):
            rates.set_manual_rate('EUR', None)
        self.assertEqual(seen, [outer])
        row = ExchangeRate.objects.get(quote_currency='EUR')
        self.assertEqual((row.rate, row.source), (Decimal('0.5'), 'manual'))


@override_settings(STORE_CURRENCY='USD')
class FetchRaceTests(TestCase):
    def test_a_manual_row_present_at_write_time_is_kept(self):
        from plugins.installed.markets.tests.test_rates import _patch_ecb

        _rate('EUR', '0.9')
        real = ExchangeRate.objects.filter

        # A manual rate saved after the table was read but before the write: the
        # row the fetch sees as 'ecb' turns manual just before its update.
        calls = {'n': 0}

        def filter_(*a, **kw):
            qs = real(*a, **kw)
            if kw.get('quote_currency') == 'EUR' and not calls['n']:
                calls['n'] += 1
                real(quote_currency='EUR').update(source='manual', rate=Decimal('0.5'))
            return qs

        with _patch_ecb(), mock.patch.object(ExchangeRate.objects, 'filter', side_effect=filter_):
            out = rates.fetch_ecb()
        row = ExchangeRate.objects.get(quote_currency='EUR')
        self.assertEqual((row.source, row.rate), ('manual', Decimal('0.5')))
        self.assertIn('EUR', out['kept_manual'])


@override_settings(STORE_CURRENCY='USD')
class RoundingTests(TestCase):
    def test_a_tiny_price_is_never_free(self):
        _rate('JPY', '150')
        _rate('EUR', '0.9')
        cheap = _product('0.0001', 'cheap')
        for currency, minimum in (('JPY', Decimal(1)), ('EUR', Decimal('0.01'))):
            for rounding in ('exact', 'whole', 'ninety_nine'):
                m = Market.objects.create(
                    code=f'{currency}-{rounding}'.lower(),
                    label='m',
                    currency=currency,
                    rounding=rounding,
                )
                with self.subTest(currency=currency, rounding=rounding):
                    self.assertGreaterEqual(market_price(cheap, m).amount, minimum)

    def test_the_jpy_example(self):
        from plugins.installed.markets.pricing import _round

        self.assertEqual(_round(Decimal('0.4'), 'JPY', 'exact'), Decimal(1))
        self.assertEqual(_round(Decimal('0'), 'JPY', 'exact'), Decimal(0))


@override_settings(STORE_CURRENCY='USD')
class BoundsAndNamesTests(TestCase):
    def test_non_countries_are_refused(self):
        for code in ('EU', 'EZ', 'UN', 'QO', 'XA', 'XB'):
            with self.subTest(code), self.assertRaisesMessage(ValidationError, 'country'):
                save_market({'code': 'a', 'label': 'A', 'currency': 'USD', 'country_codes': [code]})
        m = save_market(
            {'code': 'xk', 'label': 'Kosovo', 'currency': 'USD', 'country_codes': ['XK']}
        )
        self.assertEqual(m.country_codes, ['XK'])

    def test_rate_bounds(self):
        with self.assertRaisesMessage(ValidationError, '1,000,000,000'):
            rates.set_manual_rate('JPY', Decimal('1000000001'))
        rates.set_manual_rate('JPY', Decimal('1000000000'))
        with self.assertRaisesMessage(ValidationError, 'more than zero'):
            rates.set_manual_rate('EUR', Decimal('0.000000001'))

    def test_a_huge_rate_is_refused_not_a_500(self):
        with self.assertRaisesMessage(ValidationError, '1,000,000,000'):
            rates.set_manual_rate('EUR', Decimal('1e30'))
        market = Market.objects.create(code='eu', label='EU', currency='EUR')
        user = get_user_model().objects.create_superuser('s', 's@x.test', 'pw')
        self.client.force_login(user)
        r = self.client.post(reverse('markets:rate', args=[market.pk]), {'rate': '1e30'})
        self.assertEqual(r.status_code, 302)
        text = ' '.join(str(m) for m in get_messages(r.wsgi_request))
        self.assertIn('1,000,000,000', text)
        self.assertFalse(ExchangeRate.objects.exists())

    def test_a_rate_needs_a_real_currency(self):
        with self.assertRaisesMessage(ValidationError, 'not a currency code'):
            rates.set_manual_rate('QQQ', Decimal(1))
        with self.assertRaisesMessage(ValidationError, 'not a currency code'):
            rates.set_manual_rate('QQQ', None)

    def test_fixed_price_bound(self):
        from core.agents.registry import agent_registry

        _product(slug='mug')
        Market.objects.create(code='jp', label='JP', currency='JPY')
        tool = agent_registry.get_tool('markets.set_product_price')
        with self.assertRaisesMessage(ToolError, '1,000,000,000,000'):
            tool.handler(code='jp', product='mug', amount=10**12)
        with self.assertRaisesMessage(ToolError, '1,000,000,000,000'):
            tool.handler(code='jp', product='mug', amount=1e30)
        tool.handler(code='jp', product='mug', amount=10**12 - 1)
        self.assertEqual(ProductMarketPrice.objects.get().price.amount, Decimal(10**12 - 1))

    def test_price_for_is_gone(self):
        from plugins.installed.markets import services

        self.assertFalse(hasattr(services, 'price_for'))


@override_settings(STORE_CURRENCY='USD')
class StoredPrecisionTests(TestCase):
    """What the page and Linda show is exactly what a save writes back."""

    def test_a_three_decimal_price_is_stored_as_reported(self):
        from core.agents.registry import agent_registry

        _product(slug='mug')
        Market.objects.create(code='kw', label='Kuwait', currency='KWD')
        tool = agent_registry.get_tool('markets.set_product_price')
        out = tool.handler(code='kw', product='mug', amount=1.234)
        stored = ProductMarketPrice.objects.get().price
        self.assertEqual(stored.amount, Decimal('1.23'))
        self.assertEqual(out.output['fixed_price'], str(stored))
        with self.assertRaisesMessage(ToolError, 'more than zero'):
            tool.handler(code='kw', product='mug', amount=0.001)

    def test_a_zero_fixed_price_is_not_a_price(self):
        _rate('EUR', '0.9')
        product = _product()
        market = Market.objects.create(code='eu', label='EU', currency='EUR')
        ProductMarketPrice.objects.create(market=market, product=product, price=Money('0', 'EUR'))
        self.assertEqual(market_price(product, market), Money('9.00', 'EUR'))

    def test_an_eight_decimal_rate_survives_the_edit_box(self):
        rates.set_manual_rate('IDR', Decimal('0.00000149'))
        market = Market.objects.create(code='id', label='ID', currency='IDR', is_active=False)
        user = get_user_model().objects.create_superuser('s', 's@x.test', 'pw')
        self.client.force_login(user)
        page = self.client.get(reverse('markets:edit', args=[market.pk])).content.decode()
        self.assertIn('value="0.00000149"', page)
        self.client.post(reverse('markets:rate', args=[market.pk]), {'rate': '0.00000149'})
        self.assertEqual(ExchangeRate.objects.get(quote_currency='IDR').rate, Decimal('0.00000149'))
