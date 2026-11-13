"""market_price: fixed price, typed price, then the converted one."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase, override_settings
from djmoney.money import Money

from core.models import ExchangeRate
from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.markets.models import Market, ProductMarketPrice
from plugins.installed.markets.pricing import market_price


def _rate(quote, rate, base='USD'):
    ExchangeRate.objects.create(base_currency=base, quote_currency=quote, rate=Decimal(rate))


def _product(price='10.00', slug='thing', **extra):
    return Product.objects.create(
        name=slug, slug=slug, sku=slug, price=Money(price, 'USD'), status='active', **extra
    )


def _market(currency='EUR', **extra):
    return Market.objects.create(code=currency.lower(), label=currency, currency=currency, **extra)


@override_settings(STORE_CURRENCY='USD')
class MarketPriceTests(TestCase):
    def test_store_currency_is_the_store_price(self):
        p = _product()
        self.assertEqual(market_price(p, _market('USD')), Money('10.00', 'USD'))

    def test_variant_price_and_fallback(self):
        p = _product()
        v = ProductVariant.objects.create(product=p, name='L', sku='L', price=Money('12', 'USD'))
        w = ProductVariant.objects.create(product=p, name='S', sku='S')
        m = _market('USD')
        self.assertEqual(market_price(p, m, v).amount, Decimal(12))
        self.assertEqual(market_price(p, m, w).amount, Decimal(10))

    def test_fixed_price_wins_and_is_not_rounded(self):
        p = _product(localized_prices={'EUR': '7'})
        m = _market(rounding='whole')
        _rate('EUR', '0.9')
        ProductMarketPrice.objects.create(market=m, product=p, price=Money('8.37', 'EUR'))
        self.assertEqual(market_price(p, m), Money('8.37', 'EUR'))

    def test_typed_price_is_used_without_a_rate(self):
        p = _product(localized_prices={'EUR': '8.5'})
        self.assertEqual(market_price(p, _market(rounding='ninety_nine')), Money('8.50', 'EUR'))

    def test_variant_typed_price_before_product(self):
        p = _product(localized_prices={'EUR': '8'})
        v = ProductVariant.objects.create(
            product=p, name='L', sku='L', price=Money('12', 'USD'), localized_prices={'EUR': '11'}
        )
        self.assertEqual(market_price(p, _market(), v).amount, Decimal(11))

    def test_zero_is_not_a_price(self):
        p = _product(localized_prices={'EUR': '0'})
        m = _market()
        self.assertIsNone(market_price(p, m))  # no rate, and 0 is ignored
        _rate('EUR', '0.9')
        self.assertEqual(market_price(p, m), Money('9.00', 'EUR'))

    def test_supernatural_shape(self):
        p = _product('9.00', localized_prices={'RSD': '1050'})
        m = _market('RSD')
        self.assertEqual(market_price(p, m), Money('1050.00', 'RSD'))
        gift = _product('5.00', slug='gift', localized_prices={'RSD': '0'})
        self.assertIsNone(market_price(gift, m))

    def test_converted_and_adjusted(self):
        _rate('EUR', '0.9')
        p = _product()
        self.assertEqual(market_price(p, _market()), Money('9.00', 'EUR'))
        m = Market.objects.get(code='eur')
        m.base_price_adjustment_pct = Decimal(10)
        m.save()
        self.assertEqual(market_price(p, m), Money('9.90', 'EUR'))

    def test_no_rate_is_none(self):
        self.assertIsNone(market_price(_product(), _market()))

    def test_rounding(self):
        _rate('EUR', '0.9')
        p = _product('10.40')  # 9.36
        self.assertEqual(market_price(p, _market(rounding='exact')).amount, Decimal('9.36'))
        m = Market.objects.get(code='eur')
        m.rounding = 'whole'
        m.save()
        self.assertEqual(market_price(p, m).amount, Decimal(9))
        m.rounding = 'ninety_nine'
        m.save()
        self.assertEqual(market_price(p, m).amount, Decimal('9.99'))

    def test_whole_never_rounds_to_free(self):
        _rate('EUR', '0.9')
        m = _market(rounding='whole')
        self.assertEqual(market_price(_product('0.20'), m).amount, Decimal(1))

    def test_yen(self):
        _rate('JPY', '151.5')
        p = _product('10.00')
        m = _market('JPY', rounding='ninety_nine')
        self.assertEqual(market_price(p, m), Money(1515, 'JPY'))
        self.assertEqual(market_price(p, m).amount, Decimal(1515))
        m.rounding = 'exact'
        m.save()
        self.assertEqual(market_price(p, m).amount, Decimal(1515))

    def test_ninety_nine_never_turns_free_into_99_cents(self):
        _rate('EUR', '0.9')
        m = _market(rounding='ninety_nine')
        self.assertEqual(market_price(_product('0.00'), m).amount, Decimal('0.00'))

    def test_yen_never_rounds_a_positive_price_to_zero(self):
        _rate('JPY', '151.5')
        for rounding in ('whole', 'ninety_nine'):
            with self.subTest(rounding):
                m = _market('JPY', rounding=rounding)
                p = _product('0.001', slug=f'cheap-{rounding}')
                self.assertEqual(market_price(p, m).amount, Decimal(1))
                m.delete()
        free = _product('0.00', slug='free-yen')
        self.assertEqual(market_price(free, _market('JPY', rounding='ninety_nine')).amount, 0)
