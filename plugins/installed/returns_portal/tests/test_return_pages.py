"""The customer's return pages, owned by returns_portal (C4, v0.188.0)."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.template.loader import get_template
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.orders.models import Fulfillment, FulfillmentItem, Order, OrderItem
from plugins.installed.orders.refunds import ReturnRequest
from plugins.testing import set_app_settings

UA = {'HTTP_USER_AGENT': 'Mozilla/5.0 (Macintosh) Safari/605'}


def _usd(n):
    return Money(n, 'USD')


class _Base(TestCase):
    def setUp(self):
        cache.clear()  # the guest lookup's rate limit counts in the cache
        users = get_user_model()
        self.owner = users.objects.create_user(
            username='quillon', email='quillon@example.com', password='x'
        )
        self.other = users.objects.create_user(
            username='marrow', email='marrow@example.com', password='x'
        )
        self.book = Product.objects.create(
            name='Zephyr Atlas', slug='zephyr-atlas', sku='ZA', price=10, product_type='variable'
        )
        self.paperback = ProductVariant.objects.create(
            product=self.book, name='Paperback', sku='ZA-PB', price=_usd(10)
        )
        self.hardback = ProductVariant.objects.create(
            product=self.book, name='Hardback', sku='ZA-HB', price=_usd(10)
        )
        self.ebook = Product.objects.create(
            name='Quillon Ebook',
            slug='quillon-ebook',
            sku='QE',
            price=5,
            product_type='digital',
            requires_shipping=False,
        )
        self.order = self.make_order(customer=self.owner, email='quillon@example.com')

    def make_order(self, *, customer=None, email='guest@example.com'):
        order = Order.objects.create(
            customer=customer,
            email=email,
            subtotal=_usd(15),
            total=_usd(15),
            payment_status='paid',
        )
        self.item = OrderItem.objects.create(
            order=order,
            product=self.book,
            variant=self.paperback,
            product_name='Zephyr Atlas',
            quantity=1,
            unit_price=_usd(10),
            total_price=_usd(10),
        )
        self.ebook_item = OrderItem.objects.create(
            order=order,
            product=self.ebook,
            product_name='Quillon Ebook',
            quantity=1,
            unit_price=_usd(5),
            total_price=_usd(5),
        )
        parcel = Fulfillment.objects.create(
            order=order, shipped_at=timezone.now() - timedelta(days=3), delivered_at=timezone.now()
        )
        FulfillmentItem.objects.create(fulfillment=parcel, order_item=self.item, quantity=1)
        return order

    def form_url(self, order=None, token=None):
        order = order or self.order
        url = f'/account/orders/{order.order_number}/return/'
        return f'{url}?token={token}' if token else url

    def post_return(self, order=None, **extra):
        order = order or self.order
        item = order.items.get(product=self.book)
        data = {f'qty_{item.pk}': '1', 'reason': 'changed_mind', 'outcome': 'refund', **extra}
        return self.client.post(self.form_url(order), data, **UA)


class OwnerFormTests(_Base):
    def test_owner_sees_the_form_with_returnable_lines_only(self):
        self.client.force_login(self.owner)
        body = self.client.get(self.form_url(), **UA).content.decode()
        self.assertIn(f'data-return-line="{self.item.pk}"', body)
        self.assertNotIn(f'data-return-line="{self.ebook_item.pk}"', body)
        self.assertIn('data-return-form', body)

    def test_request_writes_the_return_and_its_resolution(self):
        from plugins.installed.returns_portal.models import ReturnResolution

        self.client.force_login(self.owner)
        response = self.post_return()
        rr = ReturnRequest.objects.get(order=self.order)
        self.assertRedirects(response, f'/account/returns/{rr.pk}/', fetch_redirect_response=False)
        self.assertEqual(rr.items, [{'order_item_id': str(self.item.pk), 'quantity': 1}])
        self.assertEqual(ReturnResolution.objects.get(request=rr).resolution, 'refund')

    def test_exchange_choice_must_be_an_offered_edition(self):
        from plugins.installed.returns_portal.models import ReturnResolution

        set_app_settings(self, 'returns_portal', refund_exchange=True)
        self.client.force_login(self.owner)
        self.post_return(outcome='exchange', **{f'edition_{self.item.pk}': str(self.paperback.pk)})
        self.assertFalse(ReturnRequest.objects.filter(order=self.order).exists())
        self.post_return(outcome='exchange', **{f'edition_{self.item.pk}': str(self.hardback.pk)})
        row = ReturnResolution.objects.get(request__order=self.order)
        self.assertEqual(row.resolution, 'exchange')
        self.assertEqual(
            row.exchange_choices,
            [{'order_item_id': str(self.item.pk), 'exchange_variant_id': str(self.hardback.pk)}],
        )

    def test_store_credit_not_offered_to_a_guest(self):
        set_app_settings(self, 'returns_portal', refund_store_credit=True)
        guest = self.make_order()
        self.post_return(guest)  # no access yet: nothing recorded
        response = self.client.get(self.form_url(guest, guest.public_token), **UA)
        self.assertNotIn('value="store_credit"', response.content.decode())
        self.post_return(guest, outcome='store_credit')
        self.assertFalse(ReturnRequest.objects.filter(order=guest).exists())

    def test_a_second_request_for_the_same_unit_is_refused(self):
        self.client.force_login(self.owner)
        self.post_return()
        response = self.post_return()
        self.assertEqual(ReturnRequest.objects.filter(order=self.order).count(), 1)
        self.assertEqual(response.status_code, 200)


class AccessTests(_Base):
    def test_guest_reaches_the_form_with_number_and_email(self):
        guest = self.make_order()
        response = self.client.post(
            '/returns/start/',
            {'order_number': guest.order_number, 'email': 'GUEST@example.com'},
            **UA,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(f'/account/orders/{guest.order_number}/return/', response['Location'])
        self.assertEqual(self.client.get(response['Location'], **UA).status_code, 200)

    def test_wrong_email_reads_like_an_unknown_order(self):
        guest = self.make_order()
        wrong = self.client.post(
            '/returns/start/', {'order_number': guest.order_number, 'email': 'x@example.com'}, **UA
        )
        unknown = self.client.post(
            '/returns/start/', {'order_number': 'NOPE-1', 'email': 'x@example.com'}, **UA
        )
        self.assertEqual(wrong.status_code, 200)
        self.assertIn('data-return-not-found', wrong.content.decode())
        self.assertIn('data-return-not-found', unknown.content.decode())

    def test_token_link_opens_the_form_and_status(self):
        guest = self.make_order()
        self.assertEqual(
            self.client.get(self.form_url(guest, guest.public_token), **UA).status_code, 200
        )
        self.post_return(guest)
        rr = ReturnRequest.objects.get(order=guest)
        self.client.logout()
        self.client.cookies.clear()
        status = self.client.get(f'/account/returns/{rr.pk}/?token={guest.public_token}', **UA)
        self.assertIn(f'data-return-status="{rr.rma_number}"', status.content.decode())

    def test_other_customer_and_wrong_token_get_404(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.form_url(), **UA).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(self.form_url(token='x' * 43), **UA).status_code, 404)

    def test_anonymous_without_a_link_goes_to_the_start_page(self):
        response = self.client.get(self.form_url(), **UA)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/returns/start/', response['Location'])

    def test_old_account_paths_still_answer(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get('/account/returns/', **UA).status_code, 200)


class SurfaceTests(_Base):
    def test_order_page_shows_the_action_only_when_something_can_come_back(self):
        self.client.force_login(self.owner)
        url = f'/account/orders/{self.order.order_number}/'
        self.assertIn('data-return-action', self.client.get(url, **UA).content.decode())
        self.post_return()
        self.assertNotIn('data-return-action', self.client.get(url, **UA).content.decode())

    def test_disabled_app_leaves_no_return_surface(self):
        from plugins.registry import app_registry

        self.client.force_login(self.owner)
        app_registry.deactivate('returns_portal')
        self.addCleanup(app_registry.activate, 'returns_portal')
        order_page = self.client.get(f'/account/orders/{self.order.order_number}/', **UA)
        self.assertNotIn('data-return-action', order_page.content.decode())
        self.assertNotIn(
            'href="/account/returns/"', self.client.get('/account/', **UA).content.decode()
        )
        self.assertEqual(self.client.get(self.form_url(), **UA).status_code, 404)
        self.assertEqual(self.client.get('/account/returns/', **UA).status_code, 404)
        self.assertNotIn('Return or exchange', [x['label'] for x in self.email_links(self.order)])

    def email_links(self, order):
        from core.hooks import MorpheusEvents, hook_registry

        return hook_registry.filter(
            MorpheusEvents.ORDER_EMAIL_LINKS, [], order=order, key='order_placed'
        )

    def test_order_email_links_the_return_form_by_token(self):
        links = self.email_links(self.order)
        url = f'/account/orders/{self.order.order_number}/return/?token={self.order.public_token}'
        self.assertTrue(any(link['url'].endswith(url) for link in links), links)
        self.assertIn('Return or exchange', [link['label'] for link in links])

    def test_order_email_skips_the_link_for_downloads_and_exchanges(self):
        digital = Order.objects.create(
            email='d@example.com', subtotal=_usd(5), total=_usd(5), payment_status='paid'
        )
        OrderItem.objects.create(
            order=digital,
            product=self.ebook,
            product_name='Quillon Ebook',
            quantity=1,
            unit_price=_usd(5),
            total_price=_usd(5),
        )
        self.assertNotIn('Return or exchange', [x['label'] for x in self.email_links(digital)])
        self.order.metadata = {'exchange_of': 'RMA-1'}
        self.order.save(update_fields=['metadata'])
        self.assertNotIn('Return or exchange', [x['label'] for x in self.email_links(self.order)])

    def test_every_theme_renders_the_pages(self):
        from themes.registry import theme_registry

        names = [
            'dot_books',
            'dawnchild',
            'supernatural_shop',
            'irving_survival',
            'montenegro',
            'croatia',
        ]
        templates = [
            'returns_portal/return_form.html',
            'returns_portal/returns_list.html',
            'returns_portal/return_status.html',
            'returns_portal/returns_start.html',
            'returns_portal/blocks/order_return.html',
        ]
        for name in names:
            self.assertIsNotNone(theme_registry.get(name), name)
        for template in templates:
            with self.subTest(template=template):
                get_template(template)
