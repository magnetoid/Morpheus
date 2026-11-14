"""Structured data opens as a dialog from the SEO card (v0.166.1).

The product page had a Structured data card of its own beside the SEO card,
holding a link to a separate editor page and the extra JSON-LD box. Both now
live in a dialog inside the SEO card, so they post with the page's own Save:
the blocks as JSON in `seo_schema_blocks` (seo stores them) and the extra
JSON-LD as `structured_data` (the product form validates and stores it).
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from djmoney.money import Money

from plugins.installed.admin_dashboard.tests.test_product_form_roundtrip import browser_form_data
from plugins.installed.catalog.models import Category, Product
from plugins.installed.seo.models import SeoMeta

_AJAX = {'X-Requested-With': 'XMLHttpRequest'}
_FAQ = {'type': 'FAQPage', 'data': {'items': [{'question': 'Signed?', 'answer': 'Yes.'}]}}
_RETIRED = {'type': 'HowTo', 'data': {'name': 'Old'}}


class _Base(TestCase):
    def setUp(self):
        staff = get_user_model().objects.create_user(
            username='sd-dialog', email='sd-dialog@x.test', password='pw', is_staff=True
        )
        self.client.force_login(staff)
        self.product = Product.objects.create(
            name='Dialog Book',
            slug='dialog-book',
            sku='DLG-1',
            status='active',
            product_type='simple',
            price=Money(Decimal('12.00'), 'USD'),
            structured_data={'brand': 'Acme'},
        )
        self.url = reverse('admin_dashboard:product_edit', kwargs={'product_id': self.product.id})

    def _meta(self, obj=None):
        obj = obj or self.product
        ct = ContentType.objects.get_for_model(type(obj))
        return SeoMeta.objects.filter(content_type=ct, object_id=str(obj.pk)).first()

    def _store_blocks(self, blocks):
        # A product gets its SeoMeta row when it is created (autofill).
        ct = ContentType.objects.get_for_model(Product)
        SeoMeta.objects.update_or_create(
            content_type=ct, object_id=str(self.product.pk), defaults={'schema_blocks': blocks}
        )

    def _page(self) -> str:
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def _save(self, data):
        resp = self.client.post(self.url, data, headers=_AJAX)
        self.assertEqual(resp.status_code, 200, resp.content[:500])
        self.assertTrue(resp.json()['ok'], resp.content[:500])
        return Product.objects.get(pk=self.product.pk)


class ProductPageTests(_Base):
    def test_one_place_for_structured_data(self):
        html = self._page()
        self.assertNotIn('product-schema-details', html, 'the separate card is gone')
        self.assertEqual(html.count('<dialog class="morph-modal" data-seo-sd-dialog'), 1)
        self.assertIn('data-seo-sd-open', html)
        self.assertEqual(html.count('name="structured_data"'), 1)
        self.assertIn('name="seo_schema_blocks"', html)
        # The dialog is inside the product form, so its fields post with Save.
        data = browser_form_data(html, 'product-form')
        self.assertIn('seo_schema_blocks', data)
        self.assertEqual(json.loads(data['structured_data'][0]), {'brand': 'Acme'})

    def test_an_unchanged_save_keeps_blocks_and_json_ld(self):
        self._store_blocks([_FAQ, _RETIRED])
        html = self._page()
        self.assertIn('Structured data · 1', html, 'the button counts the blocks that show')
        self.assertIn('1 saved block no longer shows on any page', html)
        saved = self._save(browser_form_data(html, 'product-form'))
        self.assertEqual(saved.structured_data, {'brand': 'Acme'})
        self.assertEqual(self._meta().schema_blocks, [_FAQ, _RETIRED])

    def test_blocks_from_the_dialog_are_stored_and_refused_ones_dropped(self):
        data = browser_form_data(self._page(), 'product-form')
        written_by_store = {
            'type': 'Custom',
            'data': {'custom_type': 'Product', 'props': [{'property': 'name', 'value': 'X'}]},
        }
        data['seo_schema_blocks'] = [json.dumps([_FAQ, written_by_store, {'type': 'FAQPage'}])]
        self._save(data)
        self.assertEqual(self._meta().schema_blocks, [_FAQ])

    def test_removing_every_block_keeps_the_retired_ones(self):
        self._store_blocks([_FAQ, _RETIRED])
        data = browser_form_data(self._page(), 'product-form')
        data['seo_schema_blocks'] = ['[]']
        self._save(data)
        self.assertEqual(self._meta().schema_blocks, [_RETIRED])

    def test_json_ld_from_the_dialog_is_saved(self):
        data = browser_form_data(self._page(), 'product-form')
        data['structured_data'] = ['{"gtin": "0123456789012"}']
        saved = self._save(data)
        self.assertEqual(saved.structured_data, {'gtin': '0123456789012'})

    def test_bad_json_ld_stops_the_save_and_names_the_box(self):
        data = browser_form_data(self._page(), 'product-form')
        data['structured_data'] = ['[1, 2]']
        resp = self.client.post(self.url, data, headers=_AJAX)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('structured_data', resp.json()['errors'])
        # Without JavaScript the page re-renders: the banner says where the box
        # is, and the box keeps what was typed.
        resp = self.client.post(self.url, data)
        html = resp.content.decode()
        self.assertIn('Extra JSON-LD (SEO → Structured data)', html)
        self.assertIn('[1, 2]</textarea>', html)
        self.assertEqual(Product.objects.get(pk=self.product.pk).structured_data, {'brand': 'Acme'})

    def test_a_save_without_the_box_leaves_the_json_ld_alone(self):
        # With seo switched off there is no box: the column must survive a save.
        data = browser_form_data(self._page(), 'product-form')
        del data['structured_data']
        saved = self._save(data)
        self.assertEqual(saved.structured_data, {'brand': 'Acme'})

    def test_a_new_product_gets_its_blocks(self):
        url = reverse('admin_dashboard:product_new')
        data = browser_form_data(self.client.get(url).content.decode(), 'product-form')
        data.update(
            {
                'name': ['Fresh Book'],
                'slug': ['fresh-book'],
                'sku': ['FRESH-1'],
                'price': ['9.00'],
                'seo_schema_blocks': [json.dumps([_FAQ])],
            }
        )
        resp = self.client.post(url, data, headers=_AJAX)
        self.assertEqual(resp.status_code, 200, resp.content[:500])
        product = Product.objects.get(slug='fresh-book')
        self.assertEqual(self._meta(product).schema_blocks, [_FAQ])


class SeoOffTests(_Base):
    def setUp(self):
        super().setUp()
        from plugins.registry import app_registry

        self.assertTrue(app_registry.is_active('seo'))
        app_registry.deactivate('seo')
        cache.clear()
        self.addCleanup(cache.clear)
        self.addCleanup(app_registry.activate, 'seo')

    def test_no_dialog_and_the_json_ld_survives_a_save(self):
        html = self._page()
        self.assertNotIn('data-seo-sd-dialog', html)
        self.assertNotIn('name="structured_data"', html)
        saved = self._save(browser_form_data(html, 'product-form'))
        self.assertEqual(saved.structured_data, {'brand': 'Acme'})


class OtherFormsTests(_Base):
    def test_a_category_gets_the_dialog_without_the_json_ld_box(self):
        cat = Category.objects.create(name='Mysteries', slug='mysteries', is_active=True)
        url = reverse('admin_dashboard:category_edit', kwargs={'category_id': cat.id})
        html = self.client.get(url).content.decode()
        self.assertIn('data-seo-sd-dialog', html)
        self.assertNotIn('name="structured_data"', html)


class SchemaPageTests(_Base):
    def test_the_page_still_saves_through_the_shared_editor(self):
        self._store_blocks([_RETIRED])
        url = reverse(
            'seo_dashboard:schema_editor', args=['catalog', 'product', str(self.product.pk)]
        )
        html = self.client.get(url).content.decode()
        self.assertIn('window.MorphSchemaBlocks', html)
        resp = self.client.post(url, {'blocks_json': json.dumps([_FAQ])}, follow=True)
        self.assertContains(resp, 'Structured data saved (1 block(s)).')
        self.assertEqual(self._meta().schema_blocks, [_FAQ, _RETIRED])
