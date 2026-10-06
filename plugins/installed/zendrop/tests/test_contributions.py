"""What the app contributes elsewhere — all via the bus — and its manifest."""

from __future__ import annotations

from django.http import QueryDict
from django.test import TestCase

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.zendrop.tests._fixtures import paid_order, physical_product


class ProductFormCardTests(TestCase):
    def setUp(self):
        self.product, self.variant = physical_product()

    def test_card_is_contributed_with_a_row_per_variant(self):
        cards = hook_registry.filter(
            MorpheusEvents.PRODUCT_FORM_CARDS, value=[], product=self.product
        )
        ours = [c for c in cards if c.get('template', '').startswith('zendrop/')]
        self.assertEqual(len(ours), 1)
        rows = ours[0]['context']['zendrop_rows']
        self.assertEqual([r['key'] for r in rows], [f'variant:{self.variant.pk}'])

    def test_saving_writes_and_clears_links(self):
        from plugins.installed.zendrop.models import ZendropLink

        key = f'variant:{self.variant.pk}'
        post = QueryDict(mutable=True)
        post[f'zendrop_product__{key}'] = '8421'
        post[f'zendrop_variant__{key}'] = '77'
        post[f'zendrop_url__{key}'] = 'https://app.zendrop.com/products/8421'
        hook_registry.fire(
            MorpheusEvents.PRODUCT_FORM_SAVED, product=self.product, post=post, files={}
        )
        link = ZendropLink.objects.get(product=self.product, variant=self.variant)
        self.assertEqual((link.zendrop_product_id, link.zendrop_variant_id), ('8421', '77'))

        post = QueryDict(mutable=True)
        for field in ('zendrop_product', 'zendrop_variant', 'zendrop_url'):
            post[f'{field}__{key}'] = ''
        hook_registry.fire(
            MorpheusEvents.PRODUCT_FORM_SAVED, product=self.product, post=post, files={}
        )
        self.assertFalse(ZendropLink.objects.filter(product=self.product).exists())


class CancelAfterPlacingTests(TestCase):
    def test_cancelling_a_placed_order_flags_it(self):
        from plugins.installed.zendrop.models import ZendropOrder
        from plugins.installed.zendrop.services.orders import mark_placed

        product, variant = physical_product()
        order = paid_order([(product, variant, 1)])
        mark_placed(order, 'ZD-9')
        order.cancel(reason='changed mind')
        order.save()
        self.assertEqual(ZendropOrder.objects.get(order=order).status, 'cancelled')


class ManifestTests(TestCase):
    def test_manifest_migrations_and_settings_keys(self):
        import pathlib

        from plugins.installed.zendrop.app import ZendropPlugin

        self.assertEqual(ZendropPlugin.name, 'zendrop')
        self.assertEqual(set(ZendropPlugin.requires), {'orders', 'catalog'})
        here = pathlib.Path(__file__).resolve().parents[1]
        self.assertTrue((here / 'migrations' / '__init__.py').exists())
        self.assertTrue(list((here / 'migrations').glob('0001_*.py')), 'no initial migration')
        schema = ZendropPlugin().get_config_schema()['properties']
        self.assertEqual(
            set(schema), {'access_token', 'tracking_url_template', 'mark_processing_when_placed'}
        )
        self.assertEqual(
            schema['access_token']['format'], 'password'
        )  # write-only in the dashboard
