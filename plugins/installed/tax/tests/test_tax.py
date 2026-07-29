"""Tax plugin tests."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from morpheus.core import agent_registry
from plugins.installed.tax.models import TaxCategory, TaxRate, TaxRegion
from plugins.installed.tax.services import compute_tax


class TaxComputationTests(TestCase):
    def test_default_region_no_rate_returns_none(self):
        result = compute_tax(line_items=[{'amount': '100', 'currency': 'USD'}], country='ZZ')
        # No-rate region → unambiguous zero (compute_tax dropped None; callers
        # do `value + result['total']`, which would TypeError on None).
        self.assertEqual(result['total'].amount, Decimal('0'))

    def test_flat_rate_in_region(self):
        region = TaxRegion.objects.create(name='New York', country='US', region='NY')
        TaxRate.objects.create(region=region, name='NY Sales', rate_percent=Decimal('8.875'))
        result = compute_tax(
            line_items=[{'amount': '100', 'currency': 'USD'}],
            country='US',
            region='NY',
        )
        self.assertEqual(result['total'].amount, Decimal('8.88'))
        self.assertEqual(result['lines'][0]['rate_name'], 'NY Sales')

    def test_country_only_falls_through_when_region_missing(self):
        region = TaxRegion.objects.create(name='United States', country='US', region='')
        TaxRate.objects.create(region=region, name='Default US', rate_percent=Decimal('5'))
        result = compute_tax(
            line_items=[{'amount': '50', 'currency': 'USD'}],
            country='US',
            region='XX',
        )
        self.assertEqual(result['total'].amount, Decimal('2.50'))

    def test_category_specific_rate_wins(self):
        cat = TaxCategory.objects.create(code='books', name='Books')
        region = TaxRegion.objects.create(name='UK', country='GB', region='')
        TaxRate.objects.create(region=region, name='Std VAT', rate_percent=Decimal('20'))
        TaxRate.objects.create(
            region=region, name='Books VAT', rate_percent=Decimal('0'), category=cat
        )
        result = compute_tax(
            line_items=[{'amount': '100', 'currency': 'GBP', 'category_code': 'books'}],
            country='GB',
        )
        self.assertEqual(result['total'].amount, Decimal('0'))  # 0% → zero tax

    def test_agent_tools_registered(self):
        names = {t.name for t in agent_registry.platform_tools()}
        self.assertIn('tax.list_rates', names)
        self.assertIn('tax.set_rate', names)
