"""save_market: the one write path, with its refusals."""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core.models import ExchangeRate
from plugins.installed.markets.models import Market
from plugins.installed.markets.services import delete_market, save_market


def _ok(**extra):
    return {'code': 'us', 'label': 'United States', 'currency': 'USD', **extra}


@override_settings(STORE_CURRENCY='USD')
class SaveMarketTests(TestCase):
    def refuses(self, data, text, market=None):
        with self.assertRaises(ValidationError) as ctx:
            save_market(data, market)
        self.assertIn(text, ' '.join(ctx.exception.messages))

    def test_creates_and_normalises(self):
        m = save_market(_ok(code='US', country_codes='us, ca\nus', rounding='whole'))
        self.assertEqual(m.code, 'us')
        self.assertEqual(m.country_codes, ['US', 'CA'])
        self.assertEqual(m.rounding, 'whole')

    def test_refusals(self):
        self.refuses(_ok(code='not a slug'), 'code')
        self.refuses(_ok(label=' '), 'name')
        self.refuses(_ok(currency='ZZZ'), 'currency')
        self.refuses(_ok(country_codes=['USA']), 'country')
        self.refuses(_ok(country_codes=['ZZ']), 'country')
        self.refuses(_ok(country_codes=['001']), 'country')
        self.refuses(_ok(base_price_adjustment_pct='-91'), 'between')
        self.refuses(_ok(base_price_adjustment_pct='501'), 'between')
        self.refuses(_ok(base_price_adjustment_pct='abc'), 'number')
        self.refuses(_ok(rounding='up'), 'Rounding')

    def test_code_is_unique_but_not_against_itself(self):
        m = save_market(_ok())
        self.refuses(_ok(), 'already a market')
        self.assertEqual(save_market({'label': 'Renamed'}, m).label, 'Renamed')

    def test_update_keeps_missing_keys(self):
        m = save_market(_ok(country_codes=['US'], base_price_adjustment_pct='10'))
        m = save_market({'rounding': 'ninety_nine'}, m)
        self.assertEqual(m.country_codes, ['US'])
        self.assertEqual(m.base_price_adjustment_pct, Decimal('10.00'))

    def test_one_default(self):
        a = save_market(_ok(is_default=True))
        save_market(_ok(code='b', is_default=True))
        a.refresh_from_db()
        self.assertFalse(a.is_default)
        self.assertEqual(Market.objects.filter(is_default=True).count(), 1)

    def test_foreign_currency_needs_a_rate_to_be_active(self):
        self.refuses(_ok(code='eu', currency='EUR'), 'Add an exchange rate for EUR first')
        self.assertFalse(Market.objects.filter(code='eu').exists())
        draft = save_market(_ok(code='eu', currency='EUR', is_active=False))
        self.refuses({'is_active': True}, 'EUR', draft)
        ExchangeRate.objects.create(base_currency='USD', quote_currency='EUR', rate=Decimal('0.9'))
        self.assertTrue(save_market({'is_active': True}, draft).is_active)

    def test_inverse_rate_also_counts(self):
        ExchangeRate.objects.create(base_currency='EUR', quote_currency='USD', rate=Decimal('1.1'))
        self.assertTrue(save_market(_ok(code='eu', currency='EUR')).is_active)

    def test_delete(self):
        m = save_market(_ok())
        delete_market(m)
        self.assertFalse(Market.objects.exists())
