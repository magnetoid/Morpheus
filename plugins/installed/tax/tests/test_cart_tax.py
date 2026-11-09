"""Tax on a real cart, through the whole CART_CALCULATE_BREAKDOWN chain.

Until v0.149.0 the tax handler read ``product.tax_category_code``, a field the
catalog never had, so no category rate could ever apply; it taxed lines marked
not taxable, taxed the price before discounts, never taxed shipping, ignored
"prices include tax", and charged only the first of several standard rates. Each
test below fails on that code.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.http import QueryDict
from django.template.loader import render_to_string
from django.test import TestCase
from djmoney.money import Money

from morpheus.core import MorpheusEvents, agent_registry, hook_registry
from plugins.installed.admin_dashboard.views_split.orders import _EXPORT_HEADER, _order_export_row
from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.orders.models import Cart, CartItem
from plugins.installed.orders.services import OrderService
from plugins.installed.tax.models import (
    ProductTaxCategory,
    TaxCategory,
    TaxConfiguration,
    TaxRate,
    TaxRegion,
)
from plugins.installed.tax.services import delete_category
from plugins.installed.tracking.services.event_mapping import purchase


def _eur(n):
    return Money(Decimal(str(n)), 'EUR')


class CartTaxTests(TestCase):
    def setUp(self):
        self.region = TaxRegion.objects.create(name='Germany', country='DE')
        self.standard = TaxRate.objects.create(
            name='VAT 20%', region=self.region, rate_percent=Decimal('20')
        )
        self.book = Product.objects.create(
            name='A Book', slug='a-book', sku='BOOK-1', price=_eur(50), status='active'
        )
        self.lamp = Product.objects.create(
            name='A Lamp', slug='a-lamp', sku='LAMP-1', price=_eur(50), status='active'
        )
        self.cart = Cart.objects.create(session_key='cart-tax')

    def _add(self, product, amount, quantity=1, variant=None):
        CartItem.objects.create(
            cart=self.cart,
            product=product,
            variant=variant,
            quantity=quantity,
            unit_price=_eur(amount),
        )

    def _breakdown(self, **kwargs):
        return OrderService.calculate_cart_breakdown(
            cart=self.cart, address={'country': 'DE'}, **kwargs
        )

    def _with_discount(self, amount):
        """A merchandise discount from an earlier handler, as a coupon gives."""

        def discount(value, **kwargs):
            value['discount'] = _eur(amount)
            return value

        hook_registry.register(MorpheusEvents.CART_CALCULATE_BREAKDOWN, discount, priority=10)
        self.addCleanup(hook_registry.unregister, MorpheusEvents.CART_CALCULATE_BREAKDOWN, discount)

    def test_a_product_in_a_category_pays_its_rate(self):
        books = TaxCategory.objects.create(code='books', name='Books')
        TaxRate.objects.create(
            name='VAT 5%', region=self.region, category=books, rate_percent=Decimal('5')
        )
        ProductTaxCategory.objects.create(product=self.book, category=books)
        self._add(self.book, 50)
        self._add(self.lamp, 50)
        result = self._breakdown()
        self.assertEqual(result['tax'].amount, Decimal('12.50'))  # 2.50 + 10.00
        labels = {line['label'] for line in result['meta']['tax_lines']}
        self.assertEqual(labels, {'VAT 5%', 'VAT 20%'})

    def test_a_category_with_no_rate_in_the_region_pays_the_standard_rate(self):
        food = TaxCategory.objects.create(code='food', name='Food')
        ProductTaxCategory.objects.create(product=self.book, category=food)
        self._add(self.book, 50)
        self.assertEqual(self._breakdown()['tax'].amount, Decimal('10.00'))

    def test_a_product_or_variant_marked_not_taxable_pays_nothing(self):
        self.book.is_taxable = False
        self.book.save(update_fields=['is_taxable'])
        variant = ProductVariant.objects.create(
            product=self.lamp, name='Gift card', sku='LAMP-GC', price=_eur(50), is_taxable=False
        )
        self._add(self.book, 50)
        self._add(self.lamp, 50, variant=variant)
        self._add(self.lamp, 10)
        self.assertEqual(self._breakdown()['tax'].amount, Decimal('2.00'))

    def test_tax_is_charged_after_discounts(self):
        self._add(self.book, 60)
        self._add(self.lamp, 40)
        self._with_discount(10)
        result = self._breakdown()
        self.assertEqual(result['tax'].amount, Decimal('18.00'))  # 20% of 90
        self.assertEqual(result['total'].amount, Decimal('108.00'))

    def test_a_discount_is_shared_out_over_taxed_and_untaxed_lines(self):
        self.book.is_taxable = False
        self.book.save(update_fields=['is_taxable'])
        self._add(self.book, 50)
        self._add(self.lamp, 50)
        self._with_discount(20)  # 10 off each line
        self.assertEqual(self._breakdown()['tax'].amount, Decimal('8.00'))  # 20% of 40

    def test_shipping_is_taxed_only_when_the_store_says_so(self):
        self._add(self.lamp, 50)
        quote = {'amount': _eur(10), 'name': 'Flat'}
        with patch('plugins.installed.shipping.services.quote_rate', return_value=quote):
            self.assertEqual(self._breakdown(shipping_rate_id='r1')['tax'].amount, Decimal('10.00'))
            TaxConfiguration.objects.create(shipping_taxable=True)
            result = self._breakdown(shipping_rate_id='r1')
        self.assertEqual(result['tax'].amount, Decimal('12.00'))
        self.assertEqual(result['total'].amount, Decimal('72.00'))

    def test_prices_that_include_tax_are_charged_as_shown(self):
        TaxConfiguration.objects.create(prices_include_tax=True)
        self._add(self.lamp, 120)
        result = self._breakdown()
        self.assertEqual(result['total'].amount, Decimal('120.00'))
        self.assertEqual(result['tax'].amount, Decimal('0.00'))
        self.assertEqual(result['meta']['tax_included'], [{'label': 'VAT 20%', 'amount': '20.00'}])
        self.assertNotIn('tax_lines', result['meta'])

    def test_every_standard_rate_applies_and_a_compound_one_on_top(self):
        self.standard.delete()
        TaxRate.objects.create(name='GST', region=self.region, rate_percent=Decimal('5'))
        TaxRate.objects.create(
            name='QST',
            region=self.region,
            rate_percent=Decimal('10'),
            is_compound=True,
            priority=1,
        )
        self._add(self.lamp, 100)
        result = self._breakdown()
        self.assertEqual(result['tax'].amount, Decimal('15.50'))  # 5 + 10% of 105
        lines = {line['label']: line['amount'] for line in result['meta']['tax_lines']}
        self.assertEqual(lines, {'GST': '5.00', 'QST': '10.50'})

    def test_a_gift_card_or_store_credit_does_not_lower_the_tax(self):
        mine = [entry for entry in hook_registry._handlers[MorpheusEvents.CART_CALCULATE_BREAKDOWN]]
        priorities = {entry[3]: entry[0] for entry in mine if entry[3]}
        self.assertGreater(priorities['tax'], priorities['shipping'])
        self.assertGreater(priorities['tax'], priorities['subscriptions'])
        self.assertLess(priorities['tax'], priorities['loyalty_points'])
        self.assertLess(priorities['tax'], priorities['gift_cards'])

    def test_an_inclusive_order_says_how_much_of_its_total_is_tax(self):
        TaxConfiguration.objects.create(prices_include_tax=True)
        self._add(self.lamp, 120)
        address = {'country': 'DE'}
        order = OrderService.create_from_cart(self.cart, 'buyer@example.com', address, address)
        self.assertEqual(order.total, _eur(120))
        self.assertEqual(order.tax_lines, [])
        self.assertEqual(order.tax_included_lines, [{'label': 'VAT 20%', 'amount': _eur('20.00')}])
        # Reports count the included tax, though checkout added none.
        self.assertEqual(order.total_tax, _eur('20.00'))
        row = _order_export_row(order)
        self.assertEqual(row[_EXPORT_HEADER.index('Tax')], '20.00')
        self.assertEqual(purchase(order)[1]['tax'], 20.0)
        html = render_to_string('emails/order_placed.html', {'order': order})
        text = render_to_string('emails/order_placed.txt', {'order': order})
        for body in (html, text):
            self.assertIn('Includes VAT 20%', body)
            self.assertNotIn('Tax:', body.replace('<td>Tax</td>', 'Tax:'))


class CategoryTests(TestCase):
    def test_deleting_a_category_takes_its_rates_with_it(self):
        region = TaxRegion.objects.create(name='Germany', country='DE')
        books = TaxCategory.objects.create(code='books', name='Books')
        TaxRate.objects.create(name='VAT 20%', region=region, rate_percent=Decimal('20'))
        TaxRate.objects.create(name='VAT 5%', region=region, category=books, rate_percent=5)
        self.assertTrue(delete_category('books'))
        # Left behind, SET_NULL would have made it a second standard rate.
        self.assertEqual(list(TaxRate.objects.values_list('name', flat=True)), ['VAT 20%'])


class ProductFormCardTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='A Book', slug='card-book', sku='CARD-1', price=_eur(10), status='active'
        )

    def _cards(self):
        cards = hook_registry.filter(
            MorpheusEvents.PRODUCT_FORM_CARDS, value=[], product=self.product
        )
        return [c for c in cards if c.get('template') == 'tax/blocks/product_form_card.html']

    def _save(self, data):
        post = QueryDict(mutable=True)
        post.update(data)
        hook_registry.fire(MorpheusEvents.PRODUCT_FORM_SAVED, product=self.product, post=post)

    def test_the_card_appears_once_the_store_has_a_category(self):
        self.assertEqual(self._cards(), [])
        TaxCategory.objects.create(code='books', name='Books')
        self.assertEqual(len(self._cards()), 1)

    def test_saving_the_card_sets_and_clears_the_category(self):
        TaxCategory.objects.create(code='books', name='Books')
        self._save({'tax_category_submitted': '1', 'tax_category': 'books'})
        self.assertEqual(ProductTaxCategory.objects.get(product=self.product).category_id, 'books')
        self._save({'name': 'A form without the card'})
        self.assertTrue(ProductTaxCategory.objects.filter(product=self.product).exists())
        self._save({'tax_category_submitted': '1', 'tax_category': ''})
        self.assertFalse(ProductTaxCategory.objects.filter(product=self.product).exists())


class TaxToolTests(TestCase):
    def test_every_tax_write_waits_for_a_yes(self):
        tools = {t.name: t for t in agent_registry.platform_tools() if t.name.startswith('tax.')}
        self.assertLessEqual(
            {'tax.set_category', 'tax.set_product_category', 'tax.update_settings'}, set(tools)
        )
        for name, t in tools.items():
            if 'tax.write' in t.scopes:
                self.assertTrue(t.requires_approval, name)

    def test_the_tools_change_what_checkout_charges(self):
        product = Product.objects.create(
            name='A Book', slug='tool-book', sku='TOOL-1', price=_eur(10), status='active'
        )
        agent_registry.get_tool('tax.set_category').handler(name='Books')
        agent_registry.get_tool('tax.set_product_category').handler(
            category_code='books', sku='TOOL-1'
        )
        agent_registry.get_tool('tax.update_settings').handler(shipping_taxable=True)
        self.assertEqual(ProductTaxCategory.objects.get(product=product).category_id, 'books')
        self.assertTrue(TaxConfiguration.objects.get().shipping_taxable)
