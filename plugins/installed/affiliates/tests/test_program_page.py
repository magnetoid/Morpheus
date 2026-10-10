"""The public affiliate program page, and what the apply page promises.

`/affiliates/` is what a store's menu links to: what each open program pays,
how it works, and a call to action that fits the visitor (sign in, apply, or
open the dashboard). Every term on it comes from the program row — the apply
page used to hard-code its own ("30 days", "under $25 carries over", "+10% for
store credit", books and ARCs) whatever the program said, and the payout
minimum it quoted was not even the model's default.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.affiliates.models import Affiliate, AffiliateProgram


def _cta(url: str) -> str:
    return f'<a href="{url}" class="btn btn-primary">'


class ProgramPageTests(TestCase):
    def setUp(self):
        self.program = AffiliateProgram.objects.create(
            name='Preparedness partners',
            slug='preparedness-partners',
            commission_type='percent',
            commission_value=Decimal('12.5'),
            cookie_window_days=45,
            minimum_payout=Money(Decimal('80.00'), 'USD'),
            is_active=True,
        )
        self.user = get_user_model().objects.create_user(
            username='reader', email='reader@example.test', password='pw'
        )

    def _page(self):
        resp = self.client.get('/affiliates/')
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def test_anyone_can_read_the_terms_of_each_open_program(self):
        html = self._page()
        self.assertIn('Preparedness partners', html)
        self.assertIn('12.5%', html)
        self.assertIn('45 days', html)
        self.assertIn('80', html)

    # The theme and other blocks may link to the apply page too, so the call to
    # action is asserted by its own markup, never by a bare href in the page.
    def test_a_visitor_is_asked_to_sign_in_to_apply(self):
        self.assertIn(_cta('/auth/login/?next=/affiliates/apply/'), self._page())

    def test_a_signed_in_customer_is_offered_the_application(self):
        self.client.force_login(self.user)
        self.assertIn(_cta('/affiliates/apply/'), self._page())

    def test_an_affiliate_is_sent_to_their_dashboard(self):
        Affiliate.objects.create(
            program=self.program, user=self.user, handle='reader', status='approved'
        )
        self.client.force_login(self.user)
        html = self._page()
        self.assertIn(_cta('/affiliates/me/'), html)
        self.assertNotIn(_cta('/affiliates/apply/'), html)

    def test_with_no_open_program_nobody_is_invited_to_apply(self):
        AffiliateProgram.objects.update(is_active=False)
        html = self._page()
        self.assertNotIn(_cta('/affiliates/apply/'), html)
        self.assertNotIn(_cta('/auth/login/?next=/affiliates/apply/'), html)
        self.assertIn('not taking applications', html)

    def test_the_page_has_its_own_title(self):
        self.assertRegex(self._page(), r'<title>[^<]*Affiliate program')


class ApplyPagePromisesTests(TestCase):
    def setUp(self):
        AffiliateProgram.objects.create(
            name='Partners',
            slug='partners',
            commission_type='percent',
            commission_value=Decimal('10'),
            cookie_window_days=45,
            minimum_payout=Money(Decimal('80.00'), 'USD'),
            is_active=True,
        )
        user = get_user_model().objects.create_user(
            username='applicant', email='applicant@example.test', password='pw'
        )
        self.client.force_login(user)

    def test_the_terms_come_from_the_program(self):
        html = self.client.get('/affiliates/apply/').content.decode()
        self.assertIn('45 days', html)
        self.assertIn('80', html)
        for invented in ('$25', '+10%', 'ARCs', 'on the 1st', '3 business days'):
            with self.subTest(claim=invented):
                self.assertNotIn(invented, html)
