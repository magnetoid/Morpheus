"""A product page names who makes and answers for the goods (EU GPSR, v0.134.0).

Both directions, like every public claim in the store's markup: details the product
or the store gave are shown on the page and the manufacturer in its structured data;
a product with none shows nothing, and the store's details are never claimed for a
service or a download.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import QueryDict
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse
from djmoney.money import Money

from core.agents.registry import agent_registry
from core.hooks import MorpheusEvents, hook_registry
from core.seo_page import KIND_PRODUCT, SeoPage
from plugins.installed.admin_dashboard.tests.test_product_form_roundtrip import (
    _AJAX,
    browser_form_data,
)
from plugins.installed.catalog.models import Product
from plugins.installed.metafields.models import Metafield
from plugins.installed.product_safety.safety import NAMESPACE, effective, stored
from plugins.installed.seo.schema import build_graph
from plugins.registry import app_registry

STORE = {
    'manufacturer_name': 'Lumen Works d.o.o.',
    'manufacturer_address': 'Njegoševa 1, 81000 Podgorica, Montenegro',
    'manufacturer_contact': 'safety@lumen.test',
    'responsible_name': 'Lumen EU GmbH',
    'responsible_address': 'Hauptstraße 5, 10115 Berlin, Germany',
    'responsible_contact': 'https://lumen-eu.test/contact',
}


def _product(**extra) -> Product:
    fields = {
        'name': 'Lantern',
        'slug': 'lantern',
        'sku': 'LAN-1',
        'status': 'active',
        'price': Money(Decimal('20'), 'USD'),
    }
    fields.update(extra)
    return Product.objects.create(**fields)


def _own(product, **values):
    for key, value in values.items():
        Metafield.objects.set(product, namespace=NAMESPACE, key=key, value=value)


def _call(tool_name: str, args: dict):
    return agent_registry.get_tool(tool_name).invoke(args, agent=None, context={})


def _graph(product) -> dict:
    return build_graph(
        SeoPage(
            kind=KIND_PRODUCT,
            obj=product,
            rendered={
                'slug': product.slug,
                'name': product.name,
                'description': product.description,
                'price': {'amount': '20.00', 'currency': 'USD'},
            },
            path=f'/products/{product.slug}/',
            title=product.name,
        )
    )


def _product_node(graph) -> dict:
    return next(n for n in graph['@graph'] if 'Product' in str(n.get('@type', '')))


class _StoreDetails:
    """Set the store's own details; the plugin's per-process config cache is reset after."""

    def set_store(self, **values):
        plugin = app_registry.get('product_safety')
        for key, value in values.items():
            plugin.set_config(key, value)
        self.addCleanup(plugin.invalidate_config_cache)


class WhatThePageShowsTests(_StoreDetails, TestCase):
    def test_a_product_with_nothing_shows_nothing(self):
        info = effective(_product())
        self.assertEqual(
            info, {'manufacturer': None, 'responsible': None, 'warnings': '', 'safety_url': ''}
        )

    def test_goods_show_the_stores_details(self):
        self.set_store(**STORE)
        info = effective(_product())
        self.assertEqual(info['manufacturer']['name'], 'Lumen Works d.o.o.')
        self.assertEqual(info['manufacturer']['href'], 'mailto:safety@lumen.test')
        self.assertEqual(info['responsible']['href'], 'https://lumen-eu.test/contact')

    def test_a_service_or_a_download_never_claims_the_stores_details(self):
        self.set_store(**STORE)
        service = _product(slug='tour', sku='T-1', product_type='service')
        download = _product(slug='ebook', sku='E-1', product_type='digital')
        unshipped = _product(slug='voucher', sku='V-1', requires_shipping=False)
        for product in (service, download, unshipped):
            with self.subTest(product=product.slug):
                self.assertIsNone(effective(product)['manufacturer'])
                self.assertIsNone(effective(product)['responsible'])

    def test_a_product_naming_its_own_manufacturer_takes_none_of_the_stores(self):
        # A party comes whole from one source: never the product's name beside the
        # store's address.
        self.set_store(**STORE)
        p = _product()
        _own(p, manufacturer_name='Other Maker Ltd')
        info = effective(p)
        self.assertEqual(
            info['manufacturer'],
            {'name': 'Other Maker Ltd', 'address': '', 'contact': '', 'href': ''},
        )
        # The responsible person is a party of its own: still the store's.
        self.assertEqual(info['responsible']['name'], 'Lumen EU GmbH')

    def test_a_service_shows_its_own_details(self):
        p = _product(product_type='service')
        _own(p, manufacturer_name='Boat Co', warnings='Wear a life jacket.')
        info = effective(p)
        self.assertEqual(info['manufacturer']['name'], 'Boat Co')
        self.assertEqual(info['warnings'], 'Wear a life jacket.')

    def test_only_an_email_or_a_web_address_becomes_a_link(self):
        p = _product()
        _own(
            p,
            manufacturer_name='A',
            manufacturer_contact='javascript:alert(1)',
            responsible_name='B',
            responsible_contact='call +382 20 000 000',
            safety_url='javascript:alert(1)',
        )
        info = effective(p)
        self.assertEqual(info['manufacturer']['href'], '')
        self.assertEqual(info['responsible']['href'], '')
        self.assertEqual(info['safety_url'], '')


class ProductPageTests(_StoreDetails, TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _block(self, product) -> str:
        return render_to_string(
            'product_safety/blocks/safety_info.html', {'product': {'id': str(product.pk)}}
        )

    def test_the_products_details_are_on_its_page(self):
        p = _product()
        _own(
            p,
            manufacturer_name='Lumen Works',
            manufacturer_address='Njegoševa 1\n81000 Podgorica',
            manufacturer_contact='safety@lumen.test',
            warnings='Keep away from children.\nHot when lit.',
            safety_url='https://lumen.test/lantern-safety.pdf',
        )
        html = self._block(p)
        self.assertIn('data-product-safety', html)
        self.assertIn('Lumen Works', html)
        self.assertIn('Njegoševa 1<br>81000 Podgorica', html)
        self.assertIn('href="mailto:safety@lumen.test"', html)
        self.assertIn('Keep away from children.<br>Hot when lit.', html)
        self.assertIn('href="https://lumen.test/lantern-safety.pdf"', html)
        self.assertNotIn('Responsible person in the EU', html)

    def test_a_product_with_nothing_has_no_section(self):
        self.assertNotIn('data-product-safety', self._block(_product()))

    def test_details_are_escaped(self):
        p = _product()
        _own(p, manufacturer_name='<script>alert(1)</script>')
        html = self._block(p)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_the_product_page_carries_the_section_and_the_manufacturer(self):
        self.set_store(**STORE)
        p = _product()
        body = self.client.get(f'/products/{p.slug}/').content.decode()
        self.assertIn('data-product-safety', body)
        self.assertIn('Lumen EU GmbH', body)
        self.assertIn('"manufacturer"', body)

    def test_a_product_page_without_details_carries_neither(self):
        p = _product()
        body = self.client.get(f'/products/{p.slug}/').content.decode()
        self.assertNotIn('data-product-safety', body)
        self.assertNotIn('"manufacturer"', body)


class StructuredDataTests(_StoreDetails, TestCase):
    def test_the_manufacturer_is_an_organization_on_the_product(self):
        p = _product()
        _own(
            p,
            manufacturer_name='Lumen Works',
            manufacturer_address='Njegoševa 1\n81000 Podgorica',
            manufacturer_contact='safety@lumen.test',
        )
        self.assertEqual(
            _product_node(_graph(p))['manufacturer'],
            {
                '@type': 'Organization',
                'name': 'Lumen Works',
                'address': 'Njegoševa 1, 81000 Podgorica',
                'email': 'safety@lumen.test',
            },
        )

    def test_a_website_contact_is_the_url(self):
        p = _product()
        _own(p, manufacturer_name='Lumen Works', manufacturer_contact='https://lumen.test')
        self.assertEqual(_product_node(_graph(p))['manufacturer']['url'], 'https://lumen.test')

    def test_the_stores_details_are_said_for_goods(self):
        self.set_store(**STORE)
        self.assertEqual(
            _product_node(_graph(_product()))['manufacturer']['name'], 'Lumen Works d.o.o.'
        )

    def test_nothing_is_said_without_a_manufacturer_name(self):
        p = _product()
        _own(p, manufacturer_contact='safety@lumen.test', warnings='Hot.')
        self.assertNotIn('manufacturer', _product_node(_graph(p)))

    def test_nothing_is_said_for_a_product_with_none(self):
        self.assertNotIn('manufacturer', _product_node(_graph(_product())))


class EditorCardTests(_StoreDetails, TestCase):
    def setUp(self):
        staff = get_user_model().objects.create_user(
            username='gpsr', email='gpsr@x.test', password='pw', is_staff=True
        )
        self.client.force_login(staff)
        self.product = _product()
        self.url = reverse('admin_dashboard:product_edit', kwargs={'product_id': self.product.id})

    def _form(self) -> dict:
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        return browser_form_data(resp.content.decode(), 'product-form')

    def _save(self, data):
        resp = self.client.post(self.url, data, headers=_AJAX)
        self.assertEqual(resp.status_code, 200, resp.content[:500])

    def test_the_card_lists_every_field_with_the_stores_details_as_placeholders(self):
        self.set_store(**STORE)
        _own(self.product, warnings='Hot when lit.')
        data = self._form()
        self.assertEqual(data.get('gpsr_submitted'), ['1'])
        self.assertEqual(data.get('gpsr_warnings'), ['Hot when lit.'])
        self.assertEqual(data.get('gpsr_manufacturer_name'), [''])
        body = self.client.get(self.url).content.decode()
        self.assertIn('placeholder="Lumen Works d.o.o."', body)

    def test_saving_the_card_stores_the_details(self):
        data = self._form()
        data['gpsr_manufacturer_name'] = ['Lumen Works']
        data['gpsr_warnings'] = ['Hot when lit.\r\nKeep away from children.']
        self._save(data)
        self.assertEqual(
            stored(self.product),
            {
                'manufacturer_name': 'Lumen Works',
                'warnings': 'Hot when lit.\nKeep away from children.',
            },
        )

    def test_an_unchanged_save_keeps_the_details(self):
        _own(self.product, manufacturer_name='Lumen Works', warnings='Hot.')
        self._save(self._form())
        self.assertEqual(
            stored(self.product), {'manufacturer_name': 'Lumen Works', 'warnings': 'Hot.'}
        )

    def test_emptying_a_field_clears_it(self):
        _own(self.product, manufacturer_name='Lumen Works', warnings='Hot.')
        data = self._form()
        data['gpsr_manufacturer_name'] = ['']
        self._save(data)
        self.assertEqual(stored(self.product), {'warnings': 'Hot.'})

    def test_a_save_without_the_card_changes_nothing(self):
        _own(self.product, manufacturer_name='Lumen Works')
        hook_registry.fire(
            MorpheusEvents.PRODUCT_FORM_SAVED, product=self.product, post=QueryDict(''), files=None
        )
        self.assertEqual(stored(self.product), {'manufacturer_name': 'Lumen Works'})


class LindaToolTests(_StoreDetails, TestCase):
    def test_linda_reads_what_the_page_shows_and_where_it_comes_from(self):
        self.set_store(**STORE)
        p = _product()
        _own(p, warnings='Hot.')
        result = _call('products.safety_info', {'slug': p.slug})
        self.assertEqual(result.output['own'], {'warnings': 'Hot.'})
        self.assertEqual(result.output['shown']['manufacturer']['name'], 'Lumen Works d.o.o.')
        self.assertIn("(the store's)", result.display)

    def test_linda_sets_and_clears_fields_and_keeps_the_rest(self):
        p = _product()
        _own(p, warnings='Hot.')
        _call(
            'products.set_safety_info',
            {
                'sku': p.sku,
                'manufacturer_name': 'Lumen Works',
                'safety_url': 'https://lumen.test/s.pdf',
            },
        )
        self.assertEqual(
            stored(p),
            {
                'manufacturer_name': 'Lumen Works',
                'safety_url': 'https://lumen.test/s.pdf',
                'warnings': 'Hot.',
            },
        )
        _call('products.set_safety_info', {'id': str(p.pk), 'warnings': ''})
        self.assertNotIn('warnings', stored(p))

    def test_a_contact_or_link_that_is_not_an_address_is_refused(self):
        from core.agents.tools import ToolError

        p = _product()
        for args in (
            {'manufacturer_contact': 'javascript:alert(1)'},
            {'responsible_contact': 'ring the bell'},
            {'safety_url': 'javascript:alert(1)'},
            {},
        ):
            with self.subTest(args=args), self.assertRaises(ToolError):
                _call('products.set_safety_info', {'slug': p.slug, **args})
        self.assertEqual(stored(p), {})

    def test_the_tools_scopes(self):
        read = agent_registry.get_tool('products.safety_info')
        write = agent_registry.get_tool('products.set_safety_info')
        self.assertEqual(list(read.scopes), ['catalog.read'])
        self.assertEqual(list(write.scopes), ['catalog.write'])
        # An everyday catalog write, like catalog.update_product: Linda's edge asks the
        # merchant before any write, and a flag would stop a Worker filling a catalogue.
        self.assertFalse(write.requires_approval)


class DisabledTests(_StoreDetails, TestCase):
    """With the app off nothing is shown, said or offered in the editor."""

    def setUp(self):
        cache.clear()
        app_registry.deactivate('product_safety')
        self.addCleanup(cache.clear)
        self.addCleanup(app_registry.activate, 'product_safety')

    def test_nothing_is_published(self):
        p = _product()
        _own(p, manufacturer_name='Lumen Works')
        body = self.client.get(f'/products/{p.slug}/').content.decode()
        self.assertNotIn('data-product-safety', body)
        self.assertNotIn('"manufacturer"', body)

    def test_the_editor_has_no_card(self):
        staff = get_user_model().objects.create_user(
            username='gpsr-off', email='gpsr-off@x.test', password='pw', is_staff=True
        )
        self.client.force_login(staff)
        p = _product()
        body = self.client.get(
            reverse('admin_dashboard:product_edit', kwargs={'product_id': p.id})
        ).content.decode()
        self.assertNotIn('gpsr_submitted', body)
