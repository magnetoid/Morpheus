"""A "Request to book" captured as an enquiry must keep what the guest chose.

With prices visible but no payment step (`BOOKING_LISTING_MODE=False`,
`BOOKING_PAYMENTS_READY=False` — the live configuration), the experience page
renders the marketplace booking form and every submit becomes an `Enquiry`
(see test_no_free_booking.py). That form posts its date as `booking_date` and,
for ticket-tier experiences, its party as `tier_<id>` quantities — while the
enquiry path read only `preferred_date` and `guests`. The host's enquiry list
and notification email therefore showed a lead with no date and no party size.
"""

from __future__ import annotations

import datetime

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService, Enquiry, PricingTier
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin


@override_settings(
    BOOKING_LISTING_MODE=False,
    BOOKING_PAYMENTS_READY=False,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class BookingFormEnquiryTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        from plugins.installed.catalog.models import Vendor

        vendor = Vendor.objects.create(name='Bay Host', slug='bay-host', is_active=True)
        self.svc = BookableService.objects.create(
            vendor=vendor,
            name='Kotor Bay Kayak',
            slug='kotor-bay-kayak-enquiry',
            price=Money(50, 'EUR'),
            daily_capacity=10,
            is_active=True,
        )
        self.adult = PricingTier.objects.create(
            service=self.svc, name='Adult', price=Money(50, 'EUR')
        )
        self.child = PricingTier.objects.create(
            service=self.svc, name='Child', price=Money(25, 'EUR')
        )
        self.url = f'/bookings/{self.svc.slug}/'

    def test_the_rendered_form_posts_booking_date(self):
        body = self.client.get(self.url).content.decode()
        self.assertIn('id="booking-form"', body)
        self.assertIn('name="booking_date"', body)
        self.assertNotIn('name="preferred_date"', body)

    def test_enquiry_keeps_the_forms_date_and_party_size(self):
        target = timezone.localdate() + datetime.timedelta(days=5)
        self.client.post(
            self.url,
            {
                'booking_date': target.isoformat(),
                'time_slot': '',
                f'tier_{self.adult.id}': '2',
                f'tier_{self.child.id}': '1',
                'name': 'Ana',
                'email': 'ana@example.com',
            },
        )
        enquiry = Enquiry.objects.get()
        self.assertEqual(enquiry.preferred_date, target)
        self.assertEqual(enquiry.guests, 3)
        host_mail = next(m for m in mail.outbox if m.subject.startswith('New enquiry'))
        self.assertIn(f'Preferred date: {target:%a %d %b %Y}', host_mail.body)
