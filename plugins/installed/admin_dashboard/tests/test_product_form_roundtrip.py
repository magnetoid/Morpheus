"""Saving the product editor unchanged must leave the product unchanged.

The editor renders one card per product type and shows/hides them with
``el.hidden`` (``data-pt-show``). Hidden is not disabled: the browser still
submits every control in a hidden card. So the POST carries the Inventory
card's checkboxes AND the Digital-delivery card's copies of the same names —
and Django reads the LAST value of a repeated key. The digital card ended with
``<input type="hidden" name="track_inventory" value="">`` (and the same for
``requires_shipping``), so every save of a simple/bundle product wrote both
flags False: stock stopped being reserved, availability read "in stock" at
zero, and shipping stopped applying. The duplicated Featured/Taxable boxes
meant a merchant could never untick either one.

These tests serialize the REAL rendered page the way a browser builds its
form data set (tree order, hidden cards included, unchecked boxes omitted) and
post it back, so they fail on exactly what the merchant's browser sends.
"""

from __future__ import annotations

from decimal import Decimal
from html.parser import HTMLParser

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from djmoney.money import Money

_AJAX = {'X-Requested-With': 'XMLHttpRequest'}


class _FormDataSet(HTMLParser):
    """Build the entry list a browser submits for ``<form id=form_id>``.

    Implements the parts of the HTML "construct the entry list" algorithm the
    dashboard uses: controls owned by the form (descendants, or ``form=`` the
    form's id), in tree order; disabled/nameless/button controls skipped;
    checkboxes/radios only when checked (default value ``on``); a select sends
    its selected option (the first option when none is marked); textarea its
    text. Controls inside ``<template>`` are inert and never submitted. File
    inputs are skipped (an empty upload is ignored by the view anyway).
    """

    def __init__(self, form_id: str):
        super().__init__(convert_charrefs=True)
        self.form_id = form_id
        self.entries: list[tuple[str, str]] = []
        self._form_depth = 0  # >0 while inside the target <form>
        self._template_depth = 0
        self._select: dict | None = None
        self._option: dict | None = None
        self._textarea: dict | None = None

    def _owned(self, attrs: dict) -> bool:
        if self._template_depth:
            return False
        if 'form' in attrs:
            return attrs['form'] == self.form_id
        return self._form_depth > 0

    def handle_starttag(self, tag, attrs_list):
        attrs = {k: (v if v is not None else '') for k, v in attrs_list}
        if tag == 'template':
            self._template_depth += 1
        elif tag == 'form':
            if self._form_depth:
                self._form_depth += 1
            elif attrs.get('id') == self.form_id:
                self._form_depth = 1
        elif tag == 'input':
            if not self._owned(attrs) or 'disabled' in attrs or not attrs.get('name'):
                return
            kind = (attrs.get('type') or 'text').lower()
            if kind in ('submit', 'button', 'reset', 'image', 'file'):
                return
            if kind in ('checkbox', 'radio'):
                if 'checked' in attrs:
                    self.entries.append((attrs['name'], attrs.get('value') or 'on'))
                return
            self.entries.append((attrs['name'], attrs.get('value', '')))
        elif tag == 'select':
            if self._owned(attrs) and 'disabled' not in attrs and attrs.get('name'):
                self._select = {'name': attrs['name'], 'options': []}
        elif tag == 'option' and self._select is not None:
            self._option = {
                'value': attrs.get('value'),
                'selected': 'selected' in attrs,
                'text': '',
            }
            self._select['options'].append(self._option)
        elif (
            tag == 'textarea'
            and self._owned(attrs)
            and 'disabled' not in attrs
            and attrs.get('name')
        ):
            self._textarea = {'name': attrs['name'], 'text': ''}

    def handle_endtag(self, tag):
        if tag == 'template' and self._template_depth:
            self._template_depth -= 1
        elif tag == 'form' and self._form_depth:
            self._form_depth -= 1
        elif tag == 'option':
            self._option = None
        elif tag == 'select' and self._select is not None:
            options = self._select['options']
            chosen = [o for o in options if o['selected']] or options[:1]
            for o in chosen:
                value = o['value'] if o['value'] is not None else o['text'].strip()
                self.entries.append((self._select['name'], value))
            self._select = None
        elif tag == 'textarea' and self._textarea is not None:
            text = self._textarea['text']
            if text.startswith('\n'):
                text = text[1:]
            self.entries.append((self._textarea['name'], text))
            self._textarea = None

    def handle_data(self, data):
        if self._option is not None:
            self._option['text'] += data
        elif self._textarea is not None:
            self._textarea['text'] += data


def browser_form_data(html: str, form_id: str) -> dict[str, list[str]]:
    parser = _FormDataSet(form_id)
    parser.feed(html)
    parser.close()
    data: dict[str, list[str]] = {}
    for name, value in parser.entries:
        data.setdefault(name, []).append(value)
    return data


class ProductEditorRoundTripTests(TestCase):
    def setUp(self):
        from plugins.installed.catalog.models import Product

        staff = get_user_model().objects.create_user(
            username='roundtrip', email='roundtrip@x.test', password='pw', is_staff=True
        )
        self.client.force_login(staff)
        self.product = Product.objects.create(
            name='Round Trip Candle',
            slug='round-trip-candle',
            sku='RTC-1',
            status='active',
            product_type='simple',
            price=Money(Decimal('12.00'), 'USD'),
            is_featured=True,
            is_taxable=True,
            track_inventory=True,
            requires_shipping=True,
        )
        self.url = reverse('admin_dashboard:product_edit', kwargs={'product_id': self.product.id})

    def _submitted(self) -> dict[str, list[str]]:
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        return browser_form_data(resp.content.decode(), 'product-form')

    def _save(self, data):
        resp = self.client.post(self.url, data, headers=_AJAX)
        self.assertEqual(resp.status_code, 200, resp.content[:500])
        self.assertTrue(resp.json()['ok'])
        from plugins.installed.catalog.models import Product

        return Product.objects.get(pk=self.product.pk)

    def test_unchanged_save_keeps_inventory_and_shipping_flags(self):
        saved = self._save(self._submitted())
        self.assertTrue(saved.track_inventory, 'saving the editor switched stock tracking off')
        self.assertTrue(saved.requires_shipping, 'saving the editor switched shipping off')
        self.assertTrue(saved.is_featured)
        self.assertTrue(saved.is_taxable)

    def test_unchanged_save_keeps_category_vendor_and_extra_categories(self):
        # The selects compared the form's value (a string: UUIDField renders
        # its value with str()) against the row's UUID, so no option was ever
        # marked selected. Every save then posted an empty category and vendor
        # and cleared both (2026-06-13 to 2026-10-11).
        from plugins.installed.catalog.models import Category, Product, Vendor

        top = Category.objects.create(name='Aromatherapy', slug='aromatherapy', is_active=True)
        sub = Category.objects.create(name='Oils', slug='oils', parent=top, is_active=True)
        extra = Category.objects.create(name='Gifts', slug='gifts', is_active=True)
        vendor = Vendor.objects.create(name='Hearth Supply', slug='hearth-supply')
        Product.objects.filter(pk=self.product.pk).update(category=sub, vendor=vendor)
        self.product.additional_categories.set([extra])

        saved = self._save(self._submitted())
        self.assertEqual(saved.category_id, sub.id, 'saving the editor cleared the category')
        self.assertEqual(saved.vendor_id, vendor.id, 'saving the editor cleared the vendor')
        self.assertEqual(list(saved.additional_categories.all()), [extra])

    def test_each_product_flag_is_submitted_once(self):
        data = self._submitted()
        for name in ('is_featured', 'is_taxable', 'track_inventory', 'requires_shipping'):
            with self.subTest(field=name):
                self.assertEqual(len(data.get(name, [])), 1, f'{name} submitted {data.get(name)}')

    def test_unticking_featured_and_taxable_persists(self):
        data = self._submitted()
        # The merchant unticks the box they can see — for a simple product the
        # first one in tree order (the Inventory card). Any copy in a hidden
        # card is still submitted, exactly as the browser would.
        for name in ('is_featured', 'is_taxable'):
            data[name] = data[name][1:]
        saved = self._save(data)
        self.assertFalse(saved.is_featured, 'Featured could not be switched off')
        self.assertFalse(saved.is_taxable, 'Taxable could not be switched off')

    def test_digital_product_still_drops_inventory_and_shipping(self):
        from plugins.installed.catalog.models import Product

        Product.objects.filter(pk=self.product.pk).update(product_type='digital')
        data = self._submitted()
        self.assertEqual(data['product_type'], ['digital'])
        saved = self._save(data)
        self.assertFalse(saved.requires_shipping)
        self.assertFalse(saved.track_inventory)

    def test_a_service_product_stays_a_service_and_unshipped(self):
        # A booking listing's product (product_type='service'). The type select
        # offered no 'service' option, so the browser posted the first one and an
        # unchanged save turned the experience into a stocked, shippable, cartable
        # simple product.
        from plugins.installed.catalog.models import Product

        Product.objects.filter(pk=self.product.pk).update(product_type='service')
        data = self._submitted()
        self.assertEqual(data['product_type'], ['service'])
        saved = self._save(data)
        self.assertEqual(saved.product_type, 'service')
        self.assertFalse(saved.requires_shipping)
        self.assertFalse(saved.track_inventory)
        # Another type is not on offer for a listing's product, and is refused.
        data['product_type'] = ['simple']
        resp = self.client.post(self.url, data, headers=_AJAX)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Product.objects.get(pk=self.product.pk).product_type, 'service')

    def test_an_unchanged_save_keeps_the_products_currency(self):
        # _money() defaulted to USD, so saving a EUR product (every Montenegro
        # experience) re-priced it in dollars: the booking's EUR group prices then
        # failed to add up ("different currencies") and the page showed USD.
        from djmoney.money import Money

        from plugins.installed.catalog.models import Product

        Product.objects.filter(pk=self.product.pk).update(
            price=Money(Decimal('50'), 'EUR'), compare_at_price=Money(Decimal('60'), 'EUR')
        )
        saved = self._save(self._submitted())
        self.assertEqual(str(saved.price.currency), 'EUR')
        self.assertEqual(str(saved.compare_at_price.currency), 'EUR')

    def test_a_variant_is_priced_in_its_products_currency(self):
        from djmoney.money import Money

        from plugins.installed.admin_dashboard.forms.products import VariantForm
        from plugins.installed.catalog.models import Product

        Product.objects.filter(pk=self.product.pk).update(price=Money(Decimal('50'), 'EUR'))
        product = Product.objects.get(pk=self.product.pk)
        form = VariantForm(data={'name': 'Large', 'sku': 'L-1', 'price': '55'}, product=product)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(str(form.save().price.currency), 'EUR')
