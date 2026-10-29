"""Price history and the EU prior price (v0.128.0).

Every save that changes a price appends a row, whichever path made it; the
prior price is the lowest price of the 30 days before the current reduction,
and is left out whenever the history cannot prove it.
"""

from __future__ import annotations

import importlib
import json
from datetime import timedelta
from decimal import Decimal

from django.apps import apps
from django.template.loader import render_to_string
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.catalog.agent_tools import (
    products_price_history_tool,
    products_update_price_tool,
)
from plugins.installed.catalog.models import PriceHistory, Product, ProductVariant
from plugins.installed.catalog.price_history import lowest_prior_price

NOTE = 'Lowest price in the 30 days before this reduction'


def _product(price='10', **extra):
    fields = {'name': 'Map', 'slug': 'map', 'sku': 'MAP', 'status': 'active'}
    fields.update(extra)
    return Product.objects.create(price=Money(Decimal(price), 'USD'), **fields)


def _sale(obj, price, compare_at):
    obj.price = Money(Decimal(price), 'USD')
    obj.compare_at_price = Money(Decimal(compare_at), 'USD')
    obj.save()


def _age(product, days_by_amount, variant=None):
    """Re-date rows by amount, oldest change first, as if they happened then."""
    now = timezone.now()
    for amount, days in days_by_amount.items():
        PriceHistory.objects.filter(
            product=product, variant=variant, amount=Decimal(amount)
        ).update(changed_at=now - timedelta(days=days))


class RecordingTests(TestCase):
    def test_creating_a_product_records_its_price(self):
        p = _product('10')
        row = PriceHistory.objects.get(product=p)
        self.assertEqual((row.amount, row.currency, row.source), (Decimal('10'), 'USD', 'created'))

    def test_a_save_that_changes_no_price_records_nothing(self):
        p = _product('10')
        p.name = 'Atlas'
        p.save()
        self.assertEqual(PriceHistory.objects.filter(product=p).count(), 1)

    def test_a_price_change_records_a_row(self):
        p = _product('10')
        _sale(p, '8', '10')
        newest = PriceHistory.objects.filter(product=p).first()
        self.assertEqual(
            (newest.amount, newest.compare_at_amount, newest.source),
            (Decimal('8'), Decimal('10'), 'changed'),
        )

    def test_a_save_of_other_fields_only_is_skipped(self):
        p = _product('10')
        p.price = Money(Decimal('9'), 'USD')
        p.save(update_fields=['name'])  # the price is not written, so not recorded
        self.assertEqual(PriceHistory.objects.filter(product=p).count(), 1)

    def test_linda_price_change_is_recorded(self):
        p = _product('10')
        products_update_price_tool.invoke({'id': str(p.id), 'price': '7', 'confirmed': True})
        self.assertEqual(PriceHistory.objects.filter(product=p).first().amount, Decimal('7'))

    def test_a_variant_with_its_own_price_has_its_own_history(self):
        p = _product('0', product_type='variable')
        v = ProductVariant.objects.create(
            product=p, name='Hardcover', sku='MAP-HC', price=Money(Decimal('20'), 'USD')
        )
        _sale(v, '15', '20')
        self.assertEqual(PriceHistory.objects.filter(variant=v).count(), 2)
        # A variable product's own price is a placeholder and never recorded.
        self.assertFalse(PriceHistory.objects.filter(product=p, variant=None).exists())

    def test_a_variant_without_its_own_price_records_nothing(self):
        p = _product('10')
        v = ProductVariant.objects.create(product=p, name='Paperback', sku='MAP-PB')
        self.assertFalse(PriceHistory.objects.filter(variant=v).exists())

    def test_the_migration_records_every_current_price_as_initial(self):
        p = _product('10')
        PriceHistory.objects.all().delete()
        migration = importlib.import_module(
            'plugins.installed.catalog.migrations.0021_price_history'
        )
        migration.record_current_prices(apps, None)
        row = PriceHistory.objects.get(product=p)
        self.assertEqual(row.source, 'initial')
        self.assertEqual(row.changed_at, Product.objects.get(pk=p.pk).updated_at)


class PriorPriceTests(TestCase):
    def test_lowest_price_of_the_30_days_before_the_reduction(self):
        p = _product('12')
        p.price = Money(Decimal('10'), 'USD')
        p.save()
        _sale(p, '8', '12')
        _age(p, {'12': 40, '10': 20, '8': 0})
        self.assertEqual(lowest_prior_price(p), Money(Decimal('10'), 'USD'))

    def test_a_price_older_than_the_window_still_counts_while_in_effect(self):
        p = _product('12')
        _sale(p, '8', '12')
        _age(p, {'12': 90, '8': 0})
        self.assertEqual(lowest_prior_price(p), Money(Decimal('12'), 'USD'))

    def test_not_on_sale_has_no_prior_price(self):
        p = _product('12')
        p.price = Money(Decimal('8'), 'USD')
        p.save()
        self.assertIsNone(lowest_prior_price(p))

    def test_history_that_begins_inside_the_window_proves_nothing(self):
        p = _product('12')
        PriceHistory.objects.filter(product=p).update(source='initial')
        _sale(p, '8', '12')
        _age(p, {'12': 10, '8': 0})
        self.assertIsNone(lowest_prior_price(p))

    def test_history_that_covers_the_window_from_its_start_counts(self):
        p = _product('12')
        PriceHistory.objects.filter(product=p).update(source='initial')
        _sale(p, '8', '12')
        _age(p, {'12': 60, '8': 0})
        self.assertEqual(lowest_prior_price(p), Money(Decimal('12'), 'USD'))

    def test_a_sale_older_than_the_history_has_no_prior_price(self):
        p = _product('8', compare_at_price=Money(Decimal('12'), 'USD'))
        self.assertIsNone(lowest_prior_price(p))  # created at the sale price

    def test_a_price_written_around_the_save_is_not_trusted(self):
        p = _product('12')
        _sale(p, '8', '12')
        Product.objects.filter(pk=p.pk).update(price=Decimal('6'))  # no post_save
        p.refresh_from_db()
        self.assertIsNone(lowest_prior_price(p))

    def test_the_same_number_in_another_currency_is_another_price(self):
        p = _product('20')
        p.price = Money(Decimal('10'), 'EUR')
        p.save()
        p.price = Money(Decimal('10'), 'USD')
        p.compare_at_price = Money(Decimal('20'), 'USD')
        p.save()
        now = timezone.now()
        rows = list(PriceHistory.objects.filter(product=p).order_by('id'))
        for row, days in zip(rows, (40, 10, 0), strict=True):
            PriceHistory.objects.filter(pk=row.pk).update(changed_at=now - timedelta(days=days))
        self.assertIsNone(lowest_prior_price(p))  # the EUR period proves nothing in USD

    def test_a_variant_reduction(self):
        p = _product('0', product_type='variable')
        v = ProductVariant.objects.create(
            product=p, name='Hardcover', sku='MAP-HC', price=Money(Decimal('20'), 'USD')
        )
        _sale(v, '15', '20')
        _age(p, {'20': 45, '15': 0}, variant=v)
        self.assertEqual(lowest_prior_price(v), Money(Decimal('20'), 'USD'))


class SurfaceTests(TestCase):
    def _reduced(self):
        p = _product('12')
        _sale(p, '8', '12')
        _age(p, {'12': 40, '8': 0})
        return p

    def test_the_pdp_block_prints_the_prior_price(self):
        p = self._reduced()
        out = render_to_string(
            'catalog/blocks/prior_price.html',
            {'product': {'id': str(p.pk), 'compareAtPrice': {'amount': '12.00'}}},
        )
        self.assertIn(NOTE, out)
        self.assertIn('12.00', out)

    def test_a_product_page_with_nothing_on_sale_runs_no_query(self):
        p = _product('12')
        with self.assertNumQueries(0):
            out = render_to_string(
                'catalog/blocks/prior_price.html',
                {'product': {'id': str(p.pk), 'compareAtPrice': None, 'variants': []}},
            )
        self.assertNotIn(NOTE, out)

    def test_the_pdp_block_prints_nothing_without_proof(self):
        p = _product('12')
        out = render_to_string('catalog/blocks/prior_price.html', {'product': {'id': str(p.pk)}})
        self.assertNotIn(NOTE, out)

    def test_the_pdp_block_keys_each_variant(self):
        p = _product('0', product_type='variable')
        v = ProductVariant.objects.create(
            product=p, name='Hardcover', sku='MAP-HC', price=Money(Decimal('20'), 'USD')
        )
        _sale(v, '15', '20')
        _age(p, {'20': 45, '15': 0}, variant=v)
        out = render_to_string(
            'catalog/blocks/prior_price.html',
            {'product': {'id': str(p.pk), 'variants': [{'id': str(v.pk), 'isOnSale': True}]}},
        )
        self.assertIn(f'data-prior-for="{v.pk}"', out)
        self.assertIn('MutationObserver', out)
        # The slot sits above the picker in every theme: start once it is parsed.
        self.assertIn('DOMContentLoaded', out)

    def test_the_product_page_renders_the_note(self):
        p = self._reduced()
        body = self.client.get(f'/products/{p.slug}/').content.decode()
        self.assertIn('data-prior-prices', body)
        self.assertIn(NOTE, body)

    def test_graphql_exposes_the_prior_price(self):
        p = self._reduced()
        resp = self.client.post(
            '/graphql/',
            json.dumps(
                {'query': f'{{ product(slug: "{p.slug}") {{ lowestPriorPrice {{ amount }} }} }}'}
            ),
            content_type='application/json',
        )
        self.assertEqual(resp.json()['data']['product']['lowestPriorPrice']['amount'], '12.00')

    def test_linda_reads_the_history(self):
        p = self._reduced()
        out = products_price_history_tool.invoke({'slug': p.slug}).output
        self.assertEqual([r['price'] for r in out['prices']], ['8.00', '12.00'])
        self.assertEqual(out['lowest_prior_price'], '12.00')
