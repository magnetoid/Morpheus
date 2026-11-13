"""Currency conversion: one reader of ExchangeRate, with the store currency as the pivot."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase, override_settings
from djmoney.money import Money

from core.models import ExchangeRate
from core.pricing import convert, exchange_rate, quantize, store_currency
from core.templatetags.morph import convert_money


def _rate(base, quote, rate):
    ExchangeRate.objects.create(base_currency=base, quote_currency=quote, rate=Decimal(rate))


@override_settings(STORE_CURRENCY='usd')
class ConvertTests(TestCase):
    def test_store_currency_is_upper_case(self):
        self.assertEqual(store_currency(), 'USD')

    def test_direct(self):
        _rate('USD', 'EUR', '0.9')
        self.assertEqual(exchange_rate('USD', 'EUR'), Decimal('0.9'))

    def test_inverse(self):
        _rate('USD', 'EUR', '0.5')
        self.assertEqual(exchange_rate('EUR', 'USD'), Decimal(2))

    def test_cross_through_store_currency(self):
        _rate('USD', 'EUR', '0.5')
        _rate('USD', 'RSD', '100')
        self.assertEqual(exchange_rate('EUR', 'RSD'), Decimal(200))

    def test_same_currency_and_missing(self):
        self.assertEqual(exchange_rate('EUR', 'EUR'), Decimal(1))
        self.assertIsNone(exchange_rate('USD', 'EUR'))
        _rate('USD', 'EUR', '0.5')
        self.assertIsNone(exchange_rate('EUR', 'RSD'))
        self.assertIsNone(convert(Money(5, 'USD'), 'RSD'))

    def test_convert_rounds_to_minor_unit(self):
        _rate('USD', 'EUR', '0.333333')
        self.assertEqual(convert(Money('10', 'USD'), 'EUR'), Money('3.33', 'EUR'))

    def test_yen_has_no_decimals(self):
        _rate('USD', 'JPY', '151.5')
        out = convert(Money('10.00', 'USD'), 'JPY')
        self.assertEqual(out.amount, Decimal(1515))
        self.assertEqual(quantize(Decimal('2.5'), 'JPY'), Decimal(3))
        self.assertEqual(str(quantize(Decimal('2.5'), 'JPY')), '3')

    def test_filter_returns_input_without_a_rate(self):
        price = Money('10', 'USD')
        self.assertEqual(convert_money(price, 'EUR'), price)
        _rate('USD', 'EUR', '0.9')
        self.assertEqual(convert_money(price, 'EUR'), Money('9.00', 'EUR'))
