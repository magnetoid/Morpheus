"""Markets smoke test — context processor never raises, even if the
Market table is empty."""

from __future__ import annotations

from django.test import RequestFactory, TestCase


class MarketsContextProcessorSmoke(TestCase):
    def test_blank_context_when_no_markets(self):
        from plugins.installed.markets.services import market_context

        req = RequestFactory().get('/')
        ctx = market_context(req)
        self.assertIn('active_market', ctx)
        # No Market rows → resolve_market returns None.
        self.assertIsNone(ctx['active_market'])
        self.assertEqual(ctx['market_currency'], '')
        self.assertEqual(ctx['market_locale'], '')

    def test_resolves_default_market(self):
        from plugins.installed.markets.models import Market

        Market.objects.create(
            code='us',
            label='United States',
            country_codes=['US'],
            currency='USD',
            default_locale='en-us',
            is_active=True,
            is_default=True,
        )
        from plugins.installed.markets.services import market_context

        req = RequestFactory().get('/')
        ctx = market_context(req)
        self.assertIsNotNone(ctx['active_market'])
        self.assertEqual(ctx['market_currency'], 'USD')
