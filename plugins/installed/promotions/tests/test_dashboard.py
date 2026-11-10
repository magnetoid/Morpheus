"""Promotions are created and changed on the dashboard (until v0.150.0 the
page only listed them, and only Linda could add a percent-off one)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from plugins.installed.promotions.models import Promotion

from ._fixtures import category, product, promotion


def _user(staff):
    return get_user_model().objects.create_user(
        username=f'u{staff}', email=f'u{staff}@example.com', password='x', is_staff=staff
    )


class PromotionPagesGateTests(TestCase):
    """Anonymous → sign-in, a customer → refused, staff → the page."""

    def setUp(self):
        self.promo = promotion('Ten', {'kind': 'percent_off', 'value': 10})
        self.urls = [
            reverse('promotions:new'),
            reverse('promotions:edit', kwargs={'promotion_id': self.promo.pk}),
        ]

    def test_anonymous_is_sent_to_sign_in(self):
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 302, url)

    def test_a_customer_is_refused(self):
        self.client.force_login(_user(False))
        for url in self.urls:
            self.assertIn(self.client.get(url).status_code, (302, 403), url)

    def test_staff_get_the_pages(self):
        self.client.force_login(_user(True))
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_a_customer_cannot_toggle(self):
        self.client.force_login(_user(False))
        self.client.post(reverse('promotions:toggle', kwargs={'promotion_id': self.promo.pk}))
        self.promo.refresh_from_db()
        self.assertTrue(self.promo.is_active)


class PromotionFormTests(TestCase):
    def setUp(self):
        self.client.force_login(_user(True))
        self.fiction = category('fiction')
        self.book = product('book', 20)
        self.bookmark = product('bookmark', 3)

    def _post(self, url, **fields):
        data = {'name': 'Spring sale', 'kind': 'percent_off', 'value': '15', 'priority': '50'}
        data.update(fields)
        return self.client.post(url, data)

    def test_create_a_percent_off_promotion_with_conditions(self):
        resp = self._post(
            reverse('promotions:new'),
            is_active='on',
            min_subtotal='30',
            countries='de, at',
            products='BOOK',
            categories=['fiction'],
            first_order='on',
        )
        promo = Promotion.objects.get(slug='spring-sale')
        self.assertRedirects(resp, reverse('promotions:edit', kwargs={'promotion_id': promo.pk}))
        rule = promo.rules.get()
        self.assertEqual(rule.action, {'kind': 'percent_off', 'value': 15.0})
        self.assertEqual(
            rule.predicates,
            {
                'min_subtotal': 30.0,
                'countries': ['DE', 'AT'],
                'product_ids': [str(self.book.pk)],
                'category_slugs': ['fiction'],
                'first_order': True,
            },
        )
        self.assertTrue(promo.is_active)
        self.assertFalse(promo.combinable)  # unticked box
        self.assertEqual(promo.priority, 50)

    def test_create_a_gift_promotion(self):
        self._post(reverse('promotions:new'), kind='gift', value='', gift_product='bookmark')
        rule = Promotion.objects.get().rules.get()
        self.assertEqual(rule.action, {'kind': 'gift', 'product_id': str(self.bookmark.pk)})

    def test_an_unknown_product_is_refused(self):
        resp = self._post(reverse('promotions:new'), products='NOPE')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'No product with SKU or slug: NOPE.')
        self.assertFalse(Promotion.objects.exists())

    def test_a_percent_over_100_is_refused(self):
        self._post(reverse('promotions:new'), value='150')
        self.assertFalse(Promotion.objects.exists())

    def test_tiers(self):
        self._post(reverse('promotions:new'), kind='tiered', value='', tiers='3:10, 5:15')
        self.assertEqual(
            Promotion.objects.get().rules.get().action,
            {
                'kind': 'tiered',
                'tiers': [{'min_qty': 3, 'percent': 10.0}, {'min_qty': 5, 'percent': 15.0}],
            },
        )

    def test_edit_keeps_the_rule_and_round_trips_the_page(self):
        promo = promotion(
            'Ten',
            {'kind': 'percent_off', 'value': 10},
            {'category_slugs': ['fiction'], 'product_ids': [str(self.book.pk)]},
        )
        url = reverse('promotions:edit', kwargs={'promotion_id': promo.pk})
        page = self.client.get(url).content.decode()
        self.assertIn('value="BOOK"', page)
        self.assertIn('<option value="fiction" selected>', page)
        self._post(
            url,
            name='Ten',
            slug='ten',
            value='12',
            products='BOOK',
            categories=['fiction'],
            is_active='on',
            combinable='on',
        )
        promo.refresh_from_db()
        rule = promo.rules.get()
        self.assertEqual(rule.action['value'], 12.0)
        self.assertEqual(rule.predicates['category_slugs'], ['fiction'])
        self.assertTrue(promo.combinable)

    def test_toggle_switches_it_off_and_on(self):
        promo = promotion('Ten', {'kind': 'percent_off', 'value': 10})
        url = reverse('promotions:toggle', kwargs={'promotion_id': promo.pk})
        self.client.post(url)
        promo.refresh_from_db()
        self.assertFalse(promo.is_active)
        self.client.post(url)
        promo.refresh_from_db()
        self.assertTrue(promo.is_active)

    def test_the_list_links_to_each_promotion(self):
        promo = promotion('Ten', {'kind': 'percent_off', 'value': 10})
        page = self.client.get(reverse('promotions:index'))
        self.assertContains(page, reverse('promotions:edit', kwargs={'promotion_id': promo.pk}))
        self.assertContains(page, reverse('promotions:new'))
