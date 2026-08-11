"""Meta Pixel tag — gating, dynamic ViewContent, XSS safety."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.template import Context
from django.test import RequestFactory, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.meta_commerce.templatetags.meta_commerce import meta_pixel


def _plugin():
    from plugins.registry import app_registry

    for attr in ('get', 'get_plugin'):
        fn = getattr(app_registry, attr, None)
        if callable(fn):
            try:
                p = fn('meta_commerce')
            except Exception:  # noqa: BLE001
                p = None
            if p is not None:
                return p
    from plugins.installed.meta_commerce.app import MetaCommercePlugin

    return MetaCommercePlugin()


def _enable(pixel_id='123456789012345'):
    p = _plugin()
    p.set_config('pixel_enabled', True)
    p.set_config('pixel_id', pixel_id)
    p.invalidate_config_cache()


class PixelTests(TestCase):
    def setUp(self):
        _plugin().invalidate_config_cache()

    def tearDown(self):
        _plugin().invalidate_config_cache()

    def _ctx(self, path='/', product=None):
        c = {'request': RequestFactory().get(path)}
        if product is not None:
            c['product'] = product
        return Context(c)

    def test_disabled_by_default(self):
        self.assertEqual(meta_pixel(self._ctx()), '')

    def test_invalid_pixel_id_renders_nothing(self):
        _enable(pixel_id='not-numeric')
        self.assertEqual(meta_pixel(self._ctx()), '')

    def test_enabled_emits_fbq(self):
        _enable()
        html = meta_pixel(self._ctx())
        self.assertIn('fbevents.js', html)
        self.assertIn('"123456789012345"', html)
        self.assertIn('PageView', html)

    def test_pdp_emits_viewcontent_with_content_ids(self):
        _enable()
        p = Product.objects.create(
            name='Dune',
            slug='dune',
            sku='SKU-DUNE',
            price=Money(Decimal('12.50'), 'USD'),
            product_type='simple',
            status='active',
        )
        html = meta_pixel(self._ctx('/products/dune/', product=p))
        self.assertIn('ViewContent', html)
        self.assertIn('"content_ids": ["SKU-DUNE"]', html)  # matches feed id
        self.assertIn('"value": 12.5', html)

    def test_purchase_fires_on_confirmation_with_dedup_event_id(self):
        from decimal import Decimal

        from djmoney.money import Money

        _enable()

        class _Mgr:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        line = type('L', (), {'sku': 'SKU1', 'quantity': 1})()
        order = type(
            'O',
            (),
            {
                'order_number': 'A-100',
                'total': Money(Decimal('25.00'), 'USD'),
                'items': _Mgr([line]),
            },
        )()
        ctx = Context(
            {'request': RequestFactory().get('/order/confirmation/A-100/'), 'order': order}
        )
        html = meta_pixel(ctx)
        self.assertIn('"track","Purchase"', html.replace(' ', ''))
        self.assertIn('"content_ids": ["SKU1"]', html)
        self.assertIn('"value": 25.0', html)
        # eventID = order_number → dedupes against the CAPI Purchase.
        self.assertIn('"eventID": "A-100"', html)

    def test_purchase_does_not_fire_off_confirmation_path(self):
        _enable()
        order = type('O', (), {'order_number': 'A-1', 'total': None, 'items': []})()
        ctx = Context({'request': RequestFactory().get('/'), 'order': order})
        self.assertNotIn('Purchase', meta_pixel(ctx))

    def test_malicious_sku_cannot_break_out(self):
        _enable()
        p = Product.objects.create(
            name='Bad',
            slug='bad',
            sku='</script><img src=x onerror=alert(1)>',
            price=Money(Decimal('5'), 'USD'),
            product_type='simple',
            status='active',
        )
        html = meta_pixel(self._ctx('/products/bad/', product=p))
        self.assertNotIn('</script><img', html)
        self.assertIn('\\u003c/script\\u003e', html)
