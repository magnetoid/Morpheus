"""Every app answers the dashboard's search box with the records it owns, and each
answer opens a page that exists.

The search box fires DASHBOARD_SEARCH and the hook bus isolates a handler that
raises, so a misspelt field would only make that app's records vanish without a
word. ``EveryAppAnswersTests`` calls each handler directly, where it would raise;
``RecordsOpenTheirPageTests`` finds one row of every kind and resolves its link.
"""

from __future__ import annotations

import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import Client, TestCase
from django.urls import resolve
from django.utils import timezone
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins import dashboard_search as ds

#: The apps that answer (booking_marketplace is opt-in; its own suite covers it).
ANSWERING = {
    'affiliates',
    'audiobooks',
    'b2b',
    'book_product',
    'catalog',
    'cloudflare',
    'cms',
    'crm',
    'customers',
    'draft_orders',
    'dynamics',
    'feedback',
    'gift_cards',
    'live_commerce',
    'marketing',
    'marketplace',
    'markets',
    'media',
    'newsletter',
    'orders',
    'promotions',
    'rbac',
    'release_notes',
    'seo',
    'shipping',
    'subscriptions',
    'tax',
    'webhooks_ui',
    'workflows',
}


def search(client, q):
    return json.loads(client.get('/dashboard/palette/search/', {'q': q}).content)['hits']


class EveryAppAnswersTests(TestCase):
    def test_every_app_is_listening(self):
        owners = {e[3] for e in hook_registry._handlers[MorpheusEvents.DASHBOARD_SEARCH]}
        self.assertLessEqual(ANSWERING, owners)

    def test_every_answer_runs_on_an_empty_store(self):
        for _, handler, _, owner in hook_registry._handlers[MorpheusEvents.DASHBOARD_SEARCH]:
            for q in ('zebra finch', '#1042', 'Čačak'):
                with self.subTest(app=owner, q=q):
                    value = handler([], query=q, words=ds.words(q), user=None)
                    self.assertIsInstance(value, list)


class RecordsOpenTheirPageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='finder', email='finder@example.com', password='x'
        )
        self.client = Client()
        self.client.force_login(self.user)

    def assertFinds(self, q, section, url):
        hits = [h for h in search(self.client, q) if h['section'] == section]
        self.assertIn(url, [h['url'] for h in hits], f'{q!r} in {section}: {hits}')
        resolve(url.split('?')[0].split('#')[0])

    def _product(self, name='Zebrafinch Atlas', slug='zebrafinch-atlas'):
        from plugins.installed.catalog.models import Product

        return Product.objects.create(name=name, slug=slug, sku=slug, price=Money(10, 'USD'))

    def test_catalog(self):
        from plugins.installed.catalog.models import Category, Collection, ProductVariant

        p = self._product()
        ProductVariant.objects.create(product=p, name='Hardback', sku='ZQV-HARD-77')
        c = Category.objects.create(name='Zebrafinch shelf', slug='zf-shelf')
        col = Collection.objects.create(name='Zebrafinch picks', slug='zf-picks')
        self.assertFinds('zebrafinch atlas', 'Products', f'/dashboard/products/{p.pk}/')
        self.assertFinds('ZQV-HARD', 'Products', f'/dashboard/products/{p.pk}/')
        self.assertFinds('zebrafinch shelf', 'Categories', f'/dashboard/categories/{c.pk}/edit/')
        self.assertFinds(
            'zebrafinch picks', 'Collections', f'/dashboard/collections/{col.pk}/edit/'
        )

    def test_orders_and_returns(self):
        from plugins.installed.orders.models import Order
        from plugins.installed.orders.refunds import ReturnRequest

        o = Order.objects.create(
            order_number='ZQ1042',
            email='buyer@example.com',
            subtotal=Money(10, 'USD'),
            total=Money(10, 'USD'),
            shipping_address={'first_name': 'Zorana', 'last_name': 'Quillfeather'},
        )
        rr = ReturnRequest.objects.create(order=o)
        self.assertFinds('#ZQ1042', 'Orders', '/dashboard/orders/ZQ1042/')
        self.assertFinds('quillfeather', 'Orders', '/dashboard/orders/ZQ1042/')
        self.assertFinds(rr.rma_number, 'Returns', f'/dashboard/returns/{rr.pk}/')

    def test_customers(self):
        c = get_user_model().objects.create_user(
            username='zq', email='zq@example.com', first_name='Zelda', last_name='Quorn'
        )
        self.assertFinds('zelda quorn', 'Customers', f'/dashboard/customers/{c.pk}/')

    def test_content(self):
        from plugins.installed.cms.models import Menu, Page

        page = Page.objects.create(title='Zebrafinch care', slug='zebrafinch-care')
        menu = Menu.objects.create(key='zf-footer', label='Zebrafinch footer')
        self.assertFinds('zebrafinch care', 'Content', f'/dashboard/cms/pages/{page.pk}/edit/')
        self.assertFinds('zebrafinch footer', 'Content', f'/dashboard/cms/menus/{menu.pk}/edit/')

    def test_marketing(self):
        from plugins.installed.gift_cards.models import GiftCard
        from plugins.installed.marketing.models import Coupon
        from plugins.installed.newsletter.models import SignupPopup
        from plugins.installed.promotions.models import Promotion

        coupon = Coupon.objects.create(code='ZQSAVE10', name='Spring', discount_type='percentage')
        promo = Promotion.objects.create(name='Zebrafinch week', slug='zf-week')
        card = GiftCard.objects.create(
            code='ZQGIFT-1', initial_value=Money(20, 'USD'), balance=Money(20, 'USD')
        )
        popup = SignupPopup.objects.create(name='Zebrafinch popup')
        self.assertFinds('zqsave', 'Coupons', f'/dashboard/marketing/coupons/{coupon.pk}/')
        self.assertFinds('zebrafinch week', 'Promotions', f'/dashboard/promotions/{promo.pk}/')
        self.assertFinds('ZQGIFT', 'Gift cards', f'/dashboard/gift-cards/{card.pk}/')
        self.assertFinds(
            'zebrafinch popup', 'Newsletter', f'/dashboard/newsletter/popups/{popup.pk}/'
        )

    def test_sales_partners(self):
        from plugins.installed.affiliates.models import Affiliate, AffiliateProgram
        from plugins.installed.b2b.models import PriceList
        from plugins.installed.catalog.models import Vendor
        from plugins.installed.draft_orders.models import DraftOrder

        program = AffiliateProgram.objects.create(name='Zebrafinch partners', slug='zfp')
        aff = Affiliate.objects.create(program=program, user=self.user, handle='zqhandle')
        vendor = Vendor.objects.create(name='Zebrafinch press', slug='zf-press')
        plist = PriceList.objects.create(name='Zebrafinch wholesale')
        DraftOrder.objects.create(number='ZQD-7')
        self.assertFinds('zqhandle', 'Affiliates', f'/dashboard/affiliates/affiliates/{aff.pk}/')
        self.assertFinds(
            'zebrafinch partners', 'Affiliates', f'/dashboard/affiliates/programs/{program.pk}/'
        )
        self.assertFinds(
            'zebrafinch press', 'Vendors', f'/dashboard/marketplace/vendors/{vendor.pk}/'
        )
        self.assertFinds(
            'zebrafinch wholesale', 'Price lists', f'/dashboard/b2b/pricelists/{plist.pk}/'
        )
        self.assertFinds('ZQD-7', 'Draft orders', '/dashboard/draft-orders/ZQD-7/')

    def test_crm(self):
        from plugins.installed.crm.models import ChatThread, Lead, MailAccount, MailMessage

        Lead.objects.create(email='zq.lead@example.com', company='Zebrafinch ltd')
        account = MailAccount.objects.create(label='Shop', email_address='shop@example.com')
        mail = MailMessage.objects.create(
            account=account, direction='inbound', from_address='a@example.com', subject='ZQ query'
        )
        chat = ChatThread.objects.create(email='chat@example.com', subject='Zebrafinch chat')
        self.assertFinds('zebrafinch ltd', 'CRM', '/dashboard/crm/leads/?q=zq.lead%40example.com')
        self.assertFinds('zq query', 'CRM', f'/dashboard/crm/inbox/{mail.pk}/')
        self.assertFinds('zebrafinch chat', 'CRM', f'/dashboard/crm/chat/{chat.pk}/')

    def test_shipping_tax_markets(self):
        from plugins.installed.markets.models import Market
        from plugins.installed.shipping.models import ShippingRate, ShippingZone
        from plugins.installed.tax.models import TaxRate, TaxRegion

        zone = ShippingZone.objects.create(name='Zebrafinch zone')
        rate = ShippingRate.objects.create(zone=zone, name='Zebrafinch post')
        region = TaxRegion.objects.create(name='Zebrafinch land', country='ZQ')
        tax = TaxRate.objects.create(name='Zebrafinch VAT', region=region, rate_percent=20)
        market = Market.objects.create(code='zq', label='Zebrafinch market')
        self.assertFinds(
            'zebrafinch zone',
            'Shipping',
            f'/dashboard/shipping/zones/?edit_kind=zone&edit={zone.pk}',
        )
        self.assertFinds(
            'zebrafinch post',
            'Shipping',
            f'/dashboard/shipping/zones/?edit_kind=rate&edit={rate.pk}',
        )
        self.assertFinds(
            'zebrafinch land', 'Tax', f'/dashboard/tax/regions/?edit_kind=region&edit={region.pk}'
        )
        self.assertFinds(
            'zebrafinch vat', 'Tax', f'/dashboard/tax/regions/?edit_kind=rate&edit={tax.pk}'
        )
        self.assertFinds('zebrafinch market', 'Markets', f'/dashboard/markets/{market.pk}/')

    def test_store_setup(self):
        from core.models import WebhookEndpoint
        from plugins.installed.dynamics.models import DynamicBlock
        from plugins.installed.media.models import MediaAsset
        from plugins.installed.rbac.models import Role
        from plugins.installed.seo.models import Redirect
        from plugins.installed.workflows.models import Workflow

        redirect = Redirect.objects.create(from_path='/zebrafinch-old/', to_path='/new/')
        media = MediaAsset.objects.create(
            file=ContentFile(b'x', name='zebrafinch.txt'), filename='zebrafinch.txt'
        )
        block = DynamicBlock.objects.create(name='Zebrafinch block')
        flow = Workflow.objects.create(name='Zebrafinch flow', trigger='order.placed')
        hook = WebhookEndpoint.objects.create(
            name='Zebrafinch hook', url='https://example.com/hook'
        )
        Role.objects.create(name='Zebrafinch clerk', slug='zf-clerk')
        self.assertFinds(
            'zebrafinch-old', 'Redirects', f'/dashboard/seo/redirects/?edit={redirect.pk}'
        )
        self.assertFinds('zebrafinch.txt', 'Media', f'/dashboard/media/{media.pk}/edit/')
        self.assertFinds('zebrafinch block', 'Product blocks', f'/dashboard/dynamics/{block.pk}/')
        self.assertFinds('zebrafinch flow', 'Workflows', f'/dashboard/workflows/{flow.pk}/')
        self.assertFinds('zebrafinch hook', 'Webhooks', f'/dashboard/webhooks/{hook.pk}/edit/')
        self.assertFinds('zebrafinch clerk', 'Roles', '/dashboard/apps/rbac/roles/#zf-clerk')

    def test_books_and_audiobooks(self):
        from plugins.installed.audiobooks.models import Audiobook
        from plugins.installed.book_product.models import BookProduct, BookTaxonomyTerm, Genre
        from plugins.installed.catalog.models import ProductVariant

        p = self._product('Quiet Atlas', 'quiet-atlas')
        BookProduct.objects.create(product=p, author='Zorica Quillfeather')
        Genre.objects.create(name='Zebrafinch fiction', slug='zf-fiction')
        BookTaxonomyTerm.objects.create(
            taxonomy='publisher', name='Zebrafinch house', slug='zf-house'
        )
        variant = ProductVariant.objects.create(product=p, name='Audio', sku='QA-AUDIO')
        Audiobook.objects.create(variant=variant, narrator='Zeno Quark')
        self.assertFinds('quillfeather', 'Books', f'/dashboard/products/{p.pk}/')
        self.assertFinds(
            'zebrafinch fiction',
            'Books',
            '/dashboard/book-taxonomies/curated/genre/zf-fiction/edit/',
        )
        self.assertFinds(
            'zebrafinch house', 'Books', '/dashboard/book-taxonomies/publisher/zf-house/edit/'
        )
        self.assertFinds('zeno quark', 'Audiobooks', f'/dashboard/products/{p.pk}/')

    def test_the_rest(self):
        from plugins.installed.cloudflare.models import CloudflareAccount, CloudflareZone
        from plugins.installed.feedback.models import FeedbackTicket
        from plugins.installed.live_commerce.models import LiveEvent
        from plugins.installed.subscriptions.models import Plan

        zone = CloudflareZone.objects.create(
            account=CloudflareAccount.objects.create(),
            zone_id='zq1',
            domain='zebrafinch.example',
        )
        ticket = FeedbackTicket.objects.create(message='Zebrafinch button is broken')
        now = timezone.now()
        live = LiveEvent.objects.create(
            title='Zebrafinch live',
            slug='zf-live',
            scheduled_start=now,
            scheduled_end=now + timedelta(hours=1),
            embed_url='https://example.com/embed',
        )
        Plan.objects.create(name='Zebrafinch club', slug='zf-club', price=Money(5, 'USD'))
        self.assertFinds(
            'zebrafinch.example', 'Cloudflare', f'/dashboard/cloudflare/zones/{zone.pk}/'
        )
        self.assertFinds(
            'zebrafinch button', 'Feedback', f'/dashboard/apps/feedback/tickets/{ticket.pk}/'
        )
        self.assertFinds('zebrafinch live', 'Live events', f'/dashboard/live/{live.pk}/')
        self.assertFinds('zebrafinch club', 'Subscriptions', '/dashboard/subscriptions/#zf-club')
