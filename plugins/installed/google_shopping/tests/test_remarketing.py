"""Google Ads dynamic remarketing tag — gating, page types, XSS safety."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.template import Context
from django.test import RequestFactory, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.google_shopping.templatetags.google_shopping import gads_remarketing


def _ctx(path='/'):
    return Context({'request': RequestFactory().get(path)})


def _gs_plugin():
    """The registry's live plugin instance — the one feed_settings() reads."""
    from plugins.registry import app_registry

    for attr in ('get', 'get_plugin'):
        fn = getattr(app_registry, attr, None)
        if callable(fn):
            try:
                p = fn('google_shopping')
            except Exception:  # noqa: BLE001
                p = None
            if p is not None:
                return p
    from plugins.installed.google_shopping.app import GoogleShoppingPlugin

    return GoogleShoppingPlugin()


def _enable(cid='AW-123456789'):
    p = _gs_plugin()
    p.set_config('remarketing_enabled', True)
    p.set_config('remarketing_id', cid)
    p.invalidate_config_cache()


class _CacheIsolation:
    """The registry plugin instance is long-lived across the whole test run, so
    its config cache must be cleared before AND after each test — otherwise an
    enabled-remarketing state leaks into sibling plugins' storefront tests
    (the block renders on every page)."""

    def setUp(self):
        _gs_plugin().invalidate_config_cache()

    def tearDown(self):
        _gs_plugin().invalidate_config_cache()


class RemarketingGatingTests(_CacheIsolation, TestCase):
    def test_disabled_by_default_renders_nothing(self):
        self.assertEqual(gads_remarketing(_ctx()), '')

    def test_enabled_without_id_renders_nothing(self):
        p = _gs_plugin()
        p.set_config('remarketing_enabled', True)
        p.invalidate_config_cache()
        self.assertEqual(gads_remarketing(_ctx()), '')

    def test_invalid_id_renders_nothing(self):
        _enable(cid='not-an-aw-id')
        self.assertEqual(gads_remarketing(_ctx()), '')

    def test_enabled_emits_gtag(self):
        _enable()
        html = gads_remarketing(_ctx('/'))
        self.assertIn('AW-123456789', html)
        self.assertIn('gtag', html)
        self.assertIn('"ecomm_pagetype": "home"', html)


class RemarketingPayloadTests(_CacheIsolation, TestCase):
    def setUp(self):
        super().setUp()
        _enable()

    def test_product_page_carries_prodid_and_value(self):
        p = Product.objects.create(
            name='Dune',
            slug='dune',
            sku='SKU-DUNE',
            price=Money(Decimal('12.50'), 'USD'),
            product_type='simple',
            status='active',
        )
        ctx = Context({'request': RequestFactory().get('/products/dune/'), 'product': p})
        html = gads_remarketing(ctx)
        self.assertIn('"ecomm_pagetype": "product"', html)
        self.assertIn('"ecomm_prodid": "SKU-DUNE"', html)  # matches feed g:id
        self.assertIn('"ecomm_totalvalue": 12.5', html)

    def test_xss_safe_id_is_regex_gated(self):
        # A malicious id never reaches the page — the AW- regex rejects it.
        _enable(cid='AW-1"/></script><script>alert(1)</script>')
        self.assertEqual(gads_remarketing(_ctx()), '')

    def test_malicious_sku_cannot_break_out_of_script(self):
        # The unique-identifier sink: a SKU with </script> must be neutralised.
        p = Product.objects.create(
            name='Bad',
            slug='bad',
            sku='</script><img src=x onerror=alert(1)>',
            price=Money(Decimal('5.00'), 'USD'),
            product_type='simple',
            status='active',
        )
        ctx = Context({'request': RequestFactory().get('/products/bad/'), 'product': p})
        html = gads_remarketing(ctx)
        # No literal closing-script or raw tag survives into the page.
        self.assertNotIn('</script><img', html)
        self.assertIn('\\u003c/script\\u003e', html)
