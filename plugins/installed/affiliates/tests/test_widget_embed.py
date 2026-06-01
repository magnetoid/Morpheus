"""Public, cross-origin embeddable-widget endpoint tests.

The three embed endpoints are anonymous + cross-origin by design, so the
load-bearing assertions are: anon gets 200, the framing/CORS relaxations are
correctly SCOPED, and NO customer/order/PII data leaks through the public
surface.

Also covers the new AffiliateProgram OPTIONS — commission tiers, per-category
overrides, and the auto-approve threshold — at the service layer.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from djmoney.money import Money

from plugins.installed.affiliates.models import (
    Affiliate,
    AffiliateConversion,
    AffiliateLink,
    AffiliateProgram,
    AffiliateWidget,
)
from plugins.installed.affiliates.services import (
    _calculate_commission,
    effective_tier,
    maybe_auto_approve,
)
from plugins.installed.catalog.models import Category, Product
from plugins.installed.orders.models import Order

Customer = get_user_model()


class _Base(TestCase):
    def setUp(self):
        self.client = Client()
        self.program = AffiliateProgram.objects.create(
            name='Default',
            slug='default',
            commission_type='percent',
            commission_value=Decimal('10'),
        )
        # PII we assert never leaks through the public surface.
        self.user = Customer.objects.create(
            email='secret-affiliate@example.com',
            username='secret-affiliate@example.com',
        )
        self.affiliate = Affiliate.objects.create(
            program=self.program,
            user=self.user,
            handle='secrethandle',
            status='approved',
            payout_email='payme-secret@example.com',
        )
        self.link = AffiliateLink.objects.create(
            affiliate=self.affiliate, code='refcode1', landing_url='/'
        )
        # bulk_create skips post_save signals — the catalog search /
        # webhooks_ui / cache-invalidation hooks that fire on a normal
        # Product/Category .create() are irrelevant to the public embed
        # surface and only slow the suite down (they reach for Redis/Celery).
        # The endpoints under test are still driven through the real view +
        # serializer stack via self.client.get below.
        # Category is an MPTTModel — bulk_create skips MPTT's lft/rght/tree_id
        # population, so set a valid single-node tree explicitly (avoids both
        # the NOT NULL violation AND the post_save cache-invalidation hook).
        self.cat = Category(
            name='Signed Editions', slug='signed-editions', lft=1, rght=2, tree_id=1, level=0
        )
        Category.objects.bulk_create([self.cat])
        self.product = Product(
            name='A Public Book',
            slug='a-public-book',
            sku='SKU-PUBLIC-1',  # unique — bulk_create skips the blank-sku default
            status='active',
            is_featured=True,
            category=self.cat,
            price=Money(20, 'USD'),
            cost_price=Money(3, 'USD'),  # internal — must never leak
        )
        Product.objects.bulk_create([self.product])
        self.widget = AffiliateWidget.objects.create(
            affiliate=self.affiliate,
            link=self.link,
            title='My Picks',
            source='featured',
            limit=6,
            theme='dark',
        )


class WidgetIframeTests(_Base):
    def test_anon_gets_200_and_product_card(self):
        url = reverse('affiliates:embed_iframe', args=[self.widget.key])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('A Public Book', body)
        # Card links through the affiliate /r/<code> redirect for attribution.
        self.assertIn(f'/r/{self.link.code}', body)

    def test_framing_relaxation_is_scoped_to_this_response(self):
        url = reverse('affiliates:embed_iframe', args=[self.widget.key])
        resp = self.client.get(url)
        # X-Frame-Options must NOT be DENY here (xframe_options_exempt).
        self.assertNotEqual(resp.get('X-Frame-Options', ''), 'DENY')
        # CSP on THIS response allows framing anywhere.
        self.assertIn('frame-ancestors *', resp.get('Content-Security-Policy', ''))
        # The iframe document is NOT a CORS-fetched resource — no ACAO header.
        self.assertIsNone(resp.get('Access-Control-Allow-Origin'))

    def test_no_pii_in_iframe(self):
        url = reverse('affiliates:embed_iframe', args=[self.widget.key])
        body = self.client.get(url).content.decode()
        for leak in (
            'secret-affiliate@example.com',
            'payme-secret@example.com',
            'secrethandle',
            'buyer@',
        ):
            self.assertNotIn(leak, body)

    def test_inactive_widget_404(self):
        self.widget.is_active = False
        self.widget.save(update_fields=['is_active'])
        url = reverse('affiliates:embed_iframe', args=[self.widget.key])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_bad_key_404(self):
        url = reverse('affiliates:embed_iframe', args=['nope-not-a-real-key'])
        self.assertEqual(self.client.get(url).status_code, 404)


class WidgetJsonTests(_Base):
    def test_anon_200_cors_and_public_fields_only(self):
        url = reverse('affiliates:widget_json', args=[self.widget.key])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Access-Control-Allow-Origin'], '*')
        data = resp.json()
        self.assertEqual(data['title'], 'My Picks')
        self.assertEqual(len(data['products']), 1)
        prod = data['products'][0]
        # Whitelist — exactly the public fields, nothing more.
        self.assertEqual(
            set(prod.keys()),
            {'name', 'slug', 'price', 'compare_at_price', 'on_sale', 'image', 'url'},
        )
        self.assertIn(f'/r/{self.link.code}', prod['url'])

    def test_no_pii_or_internal_fields_in_json(self):
        url = reverse('affiliates:widget_json', args=[self.widget.key])
        raw = self.client.get(url).content.decode()
        for leak in (
            'secret-affiliate@example.com',
            'payme-secret@example.com',
            'secrethandle',
            'cost_price',
            '3.00',  # the cost price amount
        ):
            self.assertNotIn(leak, raw)

    def test_options_preflight_204_with_cors(self):
        url = reverse('affiliates:widget_json', args=[self.widget.key])
        resp = self.client.options(url)
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(resp['Access-Control-Allow-Origin'], '*')


class WidgetJsTests(_Base):
    def test_anon_200_js_content_type_and_cors(self):
        url = reverse('affiliates:embed_js', args=[self.widget.key])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('javascript', resp['Content-Type'])
        self.assertEqual(resp['Access-Control-Allow-Origin'], '*')
        body = resp.content.decode()
        # Snippet points at the JSON endpoint and is XSS-safe by construction.
        self.assertIn(f'/api/affiliates/widget/{self.widget.key}.json', body)
        self.assertIn('textContent', body)
        self.assertNotIn('innerHTML', body)

    def test_no_pii_in_js(self):
        url = reverse('affiliates:embed_js', args=[self.widget.key])
        body = self.client.get(url).content.decode()
        for leak in ('secret-affiliate@example.com', 'payme-secret@example.com', 'secrethandle'):
            self.assertNotIn(leak, body)


class WidgetSourceResolutionTests(_Base):
    def test_category_source_resolves_only_that_category(self):
        other = Product(
            name='Other Book',
            slug='other-book',
            sku='SKU-OTHER-1',
            status='active',
            price=Money(9, 'USD'),
        )
        Product.objects.bulk_create([other])
        self.widget.source = 'category'
        self.widget.category_slug = 'signed-editions'
        self.widget.save(update_fields=['source', 'category_slug'])
        url = reverse('affiliates:widget_json', args=[self.widget.key])
        data = self.client.get(url).json()
        slugs = {p['slug'] for p in data['products']}
        self.assertIn('a-public-book', slugs)
        self.assertNotIn(other.slug, slugs)

    def test_draft_products_never_served(self):
        Product.objects.bulk_create(
            [
                Product(
                    name='Draft Book',
                    slug='draft-book',
                    status='draft',
                    is_featured=True,
                    price=Money(5, 'USD'),
                )
            ]
        )
        url = reverse('affiliates:widget_json', args=[self.widget.key])
        data = self.client.get(url).json()
        self.assertNotIn('draft-book', {p['slug'] for p in data['products']})

    def test_limit_is_hard_capped(self):
        self.widget.limit = 999
        self.assertLessEqual(self.widget.effective_limit, 24)


class ProgramOptionsServiceTests(TestCase):
    """Commission tiers, per-category overrides, auto-approve threshold."""

    def setUp(self):
        self.user = Customer.objects.create(email='a@example.com', username='a@example.com')

    def _affiliate(self, program, status='approved'):
        return Affiliate.objects.create(program=program, user=self.user, handle='h1', status=status)

    def test_effective_tier_picks_highest_reached(self):
        program = AffiliateProgram.objects.create(
            name='Tiered',
            slug='tiered',
            commission_value=Decimal('10'),
            tiers=[
                {'name': 'Bronze', 'min_conversions': 0, 'percent': 10},
                {'name': 'Silver', 'min_conversions': 10, 'percent': 15},
                {'name': 'Gold', 'min_conversions': 50, 'percent': 20},
            ],
        )
        self.assertEqual(effective_tier(program, 0)['name'], 'Bronze')
        self.assertEqual(effective_tier(program, 12)['name'], 'Silver')
        self.assertEqual(effective_tier(program, 500)['name'], 'Gold')

    def test_tier_rate_applied_to_commission(self):
        program = AffiliateProgram.objects.create(
            name='Tiered2',
            slug='tiered2',
            commission_value=Decimal('10'),
            tiers=[{'name': 'Gold', 'min_conversions': 1, 'percent': 20}],
        )
        aff = self._affiliate(program)
        # Give the affiliate 2 approved conversions so they sit in the Gold tier.
        for i in range(2):
            o = Order.objects.create(
                email=f'b{i}@x.com', subtotal=Money(50, 'USD'), total=Money(50, 'USD')
            )
            AffiliateConversion.objects.create(
                affiliate=aff, order=o, commission=Money(5, 'USD'), status='approved'
            )
        order = Order.objects.create(
            email='c@x.com', subtotal=Money(100, 'USD'), total=Money(100, 'USD')
        )
        commission = _calculate_commission(program=program, order=order, affiliate=aff)
        # 20% of $100 = $20 (Gold), not the 10% base.
        self.assertEqual(commission, Money(Decimal('20.00'), 'USD'))

    def test_auto_approve_promotes_pending_affiliate(self):
        program = AffiliateProgram.objects.create(
            name='Auto', slug='auto', commission_value=Decimal('10'), auto_approve_after=2
        )
        aff = self._affiliate(program, status='pending')
        for i in range(2):
            o = Order.objects.create(
                email=f'd{i}@x.com', subtotal=Money(10, 'USD'), total=Money(10, 'USD')
            )
            AffiliateConversion.objects.create(
                affiliate=aff, order=o, commission=Money(1, 'USD'), status='pending'
            )
        self.assertTrue(maybe_auto_approve(aff))
        aff.refresh_from_db()
        self.assertEqual(aff.status, 'approved')

    def test_auto_approve_noop_below_threshold(self):
        program = AffiliateProgram.objects.create(
            name='Auto2', slug='auto2', commission_value=Decimal('10'), auto_approve_after=5
        )
        aff = self._affiliate(program, status='pending')
        self.assertFalse(maybe_auto_approve(aff))
        aff.refresh_from_db()
        self.assertEqual(aff.status, 'pending')
