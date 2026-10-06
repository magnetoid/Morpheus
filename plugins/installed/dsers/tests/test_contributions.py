"""What the app contributes to the rest of the dashboard — all via the bus."""

from __future__ import annotations

from django.http import QueryDict
from django.test import TestCase

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.dsers.tests._fixtures import paid_order, physical_product


class ProductFormCardTests(TestCase):
    def setUp(self):
        self.product, self.variant = physical_product()

    def test_card_is_contributed_with_a_row_per_variant(self):
        cards = hook_registry.filter(
            MorpheusEvents.PRODUCT_FORM_CARDS, value=[], product=self.product
        )
        ours = [c for c in cards if c.get('template', '').startswith('dsers/')]
        self.assertEqual(len(ours), 1, cards)
        rows = ours[0]['context']['dsers_rows']
        self.assertEqual([r['sku'] for r in rows], [self.variant.sku])
        self.assertEqual(rows[0]['key'], f'variant:{self.variant.pk}')

    def test_saving_the_form_writes_and_clears_links(self):
        from plugins.installed.dsers.models import SupplierLink

        post = QueryDict(mutable=True)
        post[f'dsers_url__variant:{self.variant.pk}'] = 'https://www.aliexpress.com/item/1.html'
        post[f'dsers_sku__variant:{self.variant.pk}'] = 'Black'
        hook_registry.fire(
            MorpheusEvents.PRODUCT_FORM_SAVED, product=self.product, post=post, files={}
        )
        link = SupplierLink.objects.get(product=self.product, variant=self.variant)
        self.assertEqual(link.supplier_url, 'https://www.aliexpress.com/item/1.html')
        self.assertEqual(link.supplier_sku, 'Black')

        post = QueryDict(mutable=True)
        post[f'dsers_url__variant:{self.variant.pk}'] = ''
        post[f'dsers_sku__variant:{self.variant.pk}'] = ''
        hook_registry.fire(
            MorpheusEvents.PRODUCT_FORM_SAVED, product=self.product, post=post, files={}
        )
        self.assertFalse(SupplierLink.objects.filter(product=self.product).exists())

    def test_a_product_without_variants_gets_one_product_row(self):
        from plugins.installed.catalog.models import ProductVariant

        ProductVariant.objects.filter(product=self.product).delete()
        cards = hook_registry.filter(
            MorpheusEvents.PRODUCT_FORM_CARDS, value=[], product=self.product
        )
        rows = [c for c in cards if c.get('template', '').startswith('dsers/')][0]['context'][
            'dsers_rows'
        ]
        self.assertEqual([r['key'] for r in rows], ['product'])


class CancelAfterExportTests(TestCase):
    def test_cancelling_an_exported_order_flags_it(self):
        from plugins.installed.dsers.models import OrderSync

        product, variant = physical_product()
        order = paid_order([(product, variant, 1)], status='processing')
        OrderSync.objects.create(order=order, status='exported')

        order.cancel(reason='customer changed mind')
        order.save()

        self.assertEqual(OrderSync.objects.get(order=order).status, 'cancelled')


class ManifestTests(TestCase):
    def test_manifest_and_migrations_package(self):
        import pathlib

        from plugins.installed.dsers.app import DsersPlugin

        self.assertEqual(DsersPlugin.name, 'dsers')
        self.assertIn('orders', DsersPlugin.requires)
        self.assertIn('catalog', DsersPlugin.requires)
        here = pathlib.Path(__file__).resolve().parents[1]
        self.assertTrue((here / 'migrations' / '__init__.py').exists())
        self.assertTrue(list((here / 'migrations').glob('0001_*.py')), 'no initial migration')

    def test_settings_panel_declares_only_keys_the_code_reads(self):
        from plugins.installed.dsers.app import DsersPlugin

        keys = set(DsersPlugin().get_config_schema()['properties'])
        self.assertEqual(keys, {'order_memo', 'tracking_url_template', 'mark_processing_on_export'})
