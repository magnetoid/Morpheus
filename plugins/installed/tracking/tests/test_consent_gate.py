"""Server-side GA4 and the Google Ads tag obey the consent app; one banner.

GA4 Measurement Protocol events (view_item, add_to_cart, purchase, …) went out
whatever the visitor chose, the Ads purchase tag rendered on every confirmation
page, and the tracking app shipped a second cookie banner of its own.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.template import Context, Template
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.registry import app_registry

_DELAY = 'plugins.installed.tracking.tasks.send_event_task.delay'
_BROWSER = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15'


def _set_gdpr(on: bool) -> None:
    from core.models import StoreSettings

    row = StoreSettings.objects.first() or StoreSettings()
    row.gdpr_enabled = on
    row.save()
    cache.delete('morph:gdpr_enabled')


def _order(consent, product=None):
    line = SimpleNamespace(
        product=product, variant=None, quantity=1, unit_price=Money(Decimal('5'), 'USD')
    )
    return SimpleNamespace(
        pk=1,
        order_number='ORD-C',
        items=SimpleNamespace(all=lambda: [line]),
        total=Money(Decimal('5'), 'USD'),
        shipping_total=None,
        tax_total=None,
        metadata={'consent': consent},
    )


class Ga4ConsentTests(TestCase):
    def setUp(self):
        _set_gdpr(True)
        self.product = Product.objects.create(
            name='Gate',
            slug='gate-probe',
            sku='GATE',
            price=Money(Decimal('4'), 'USD'),
            product_type='simple',
            status='active',
        )

    def test_a_visitor_with_no_decision_sends_no_view_item(self):
        # Review Focus 5: a crawler or a visitor who never answered the banner.
        with patch(_DELAY) as delay:
            self.client.get('/products/gate-probe/', HTTP_USER_AGENT=_BROWSER)
        delay.assert_not_called()

    def test_a_visitor_who_accepted_analytics_sends_view_item(self):
        self.client.cookies['morpheus_consent'] = json.dumps({'necessary': True, 'analytics': True})
        with patch(_DELAY) as delay:
            self.client.get('/products/gate-probe/', HTTP_USER_AGENT=_BROWSER)
        self.assertEqual(delay.call_args.kwargs['event_name'], 'view_item')

    def test_purchase_follows_the_orders_stamp(self):
        plugin = app_registry.get('tracking')
        with patch(_DELAY) as delay:
            plugin.on_order_paid(order=_order({'managed': True, 'analytics': False}, self.product))
        delay.assert_not_called()
        with patch(_DELAY) as delay:
            plugin.on_order_paid(order=_order({'managed': True, 'analytics': True}, self.product))
        self.assertEqual(delay.call_args.kwargs['event_name'], 'purchase')

    def test_the_debug_override_still_sends(self):
        # Settings → Tracking's "Ignore visitor consent (debug only)" promises
        # server-side events regardless; its own app honours it.
        from plugins.installed.tracking.models import TrackingSettings

        s = TrackingSettings.get_solo()
        s.consent_override = True
        s.save()
        with patch(_DELAY) as delay:
            self.client.get('/products/gate-probe/', HTTP_USER_AGENT=_BROWSER)
        self.assertEqual(delay.call_args.kwargs['event_name'], 'view_item')

    def test_an_unmanaged_store_sends_as_before(self):
        _set_gdpr(False)
        with patch(_DELAY) as delay:
            self.client.get('/products/gate-probe/', HTTP_USER_AGENT=_BROWSER)
        self.assertEqual(delay.call_args.kwargs['event_name'], 'view_item')


class AdsTagConsentTests(TestCase):
    def setUp(self):
        p = app_registry.get('tracking')
        p.set_config('google_ads_conversion_id', 'AW-123')
        p.set_config('google_ads_purchase_label', 'abc')
        self.addCleanup(p.set_config, 'google_ads_conversion_id', '')
        self.addCleanup(p.set_config, 'google_ads_purchase_label', '')
        self.order = _order({'managed': True})

    def _render(self, consent):
        ctx = {'order': self.order}
        if consent is not None:
            ctx['consent'] = consent
        return Template('{% load tracking %}{% gads_purchase_conversion order %}').render(
            Context(ctx)
        )

    def test_no_tag_without_marketing_consent(self):
        self.assertEqual(self._render({'managed': True, 'marketing': False}), '')

    def test_tag_with_marketing_consent(self):
        self.assertIn('"conversion"', self._render({'managed': True, 'marketing': True}))

    def test_tag_on_a_store_without_the_consent_app(self):
        self.assertIn('"conversion"', self._render(None))


class OneBannerTests(TestCase):
    def test_the_retired_banner_tag_renders_nothing(self):
        # Kept as a no-op for one release: a theme outside this repo that still
        # calls it must not fail every storefront page with TemplateSyntaxError.
        self.assertEqual(
            Template('{% load tracking %}{% tracking_consent_banner %}').render(Context()), ''
        )

    def test_no_theme_renders_it(self):
        root = Path(settings.BASE_DIR) / 'themes' / 'library'
        for base in root.glob('*/templates/storefront/base.html'):
            with self.subTest(theme=base.parts[-4]):
                self.assertNotIn('tracking_consent_banner', base.read_text())
