"""The operator can see and work through booking enquiries.

Montenegro's listings have no owner accounts and alerts fell back to a sender
address nobody read, so 25 guest enquiries sat at 'new' for two months, seen
by nobody: there was no enquiry screen, stays had no screen at all, and an
enquiry's status could never change.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.booking_marketplace import email as E
from plugins.installed.booking_marketplace.models import (
    BookableService,
    Booking,
    Enquiry,
    Property,
    RoomType,
    StayBooking,
    StayEnquiry,
)

INBOX = '/dashboard/apps/booking_marketplace/enquiries/'
STAYS = '/dashboard/apps/booking_marketplace/stays/'


class _Listings(TestCase):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import Vendor

        vendor = Vendor.objects.create(name='Coast Tours', slug='coast-tours', is_active=True)
        cls.service = BookableService.objects.create(
            vendor=vendor, name='Kayak Budva', slug='kayak-budva', price=Money(50, 'EUR')
        )
        cls.property = Property.objects.create(
            vendor=vendor, name='Hotel Kotor', slug='hotel-kotor'
        )
        cls.room = RoomType.objects.create(
            property=cls.property,
            name='Double',
            slug='double',
            base_rate=Money(Decimal('90.00'), 'EUR'),
            max_occupancy=2,
            max_adults=2,
            max_children=0,
            room_count=3,
        )


class OperatorInboxTests(_Listings):
    def setUp(self):
        staff = get_user_model().objects.create_user(
            username='operator', email='operator@example.com', password='x', is_staff=True
        )
        self.client.force_login(staff)
        Enquiry.objects.create(
            service=self.service, name='Ana', email='ana@example.com', guests=2,
            message='Is Saturday free?',
        )  # fmt: skip
        self.stay_enquiry = StayEnquiry.objects.create(
            property=self.property, room_type=self.room, name='Ben', email='ben@example.com',
            adults=2, message='Late check-in?',
        )  # fmt: skip

    def test_the_inbox_lists_both_kinds_of_enquiry(self):
        body = self.client.get(INBOX).content.decode()
        for text in ('Kayak Budva', 'Hotel Kotor', 'ana@example.com', 'ben@example.com',
                     'Is Saturday free?', 'Late check-in?'):  # fmt: skip
            with self.subTest(text=text):
                self.assertIn(text, body)

    def test_an_enquiry_can_be_marked_contacted(self):
        self.client.post(INBOX, {'kind': 'stay', 'id': self.stay_enquiry.pk, 'status': 'contacted'})
        self.assertEqual(StayEnquiry.objects.get(pk=self.stay_enquiry.pk).status, 'contacted')
        body = self.client.get(INBOX).content.decode()  # the default view is the new ones
        self.assertNotIn('ben@example.com', body)
        self.assertIn('ana@example.com', body)

    def test_the_stays_screen_lists_stay_bookings(self):
        StayBooking.objects.create(
            room_type=self.room, property=self.property, customer_name='Cleo',
            customer_email='cleo@example.com', check_in=date.today() + timedelta(days=10),
            check_out=date.today() + timedelta(days=12), nights=2, rooms=1, adults=2, children=0,
            subtotal=Money(Decimal('180'), 'EUR'), service_fee=Money(0, 'EUR'),
            tourist_tax=Money(0, 'EUR'), total=Money(Decimal('180'), 'EUR'), status='confirmed',
        )  # fmt: skip
        body = self.client.get(STAYS).content.decode()
        self.assertIn('Cleo', body)
        self.assertIn('Hotel Kotor', body)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='noreply@example.com',
    BOOKING_ENQUIRY_NOTIFY_EMAIL='',
)
class EnquiryAlertTests(_Listings):
    def test_a_host_alert_replies_to_the_guest(self):
        E.send_enquiry_host_notification(
            Enquiry(service=self.service, name='Ana', email='ana@example.com')
        )
        self.assertEqual(mail.outbox[0].reply_to, ['ana@example.com'])

    def test_alerts_fall_back_to_the_store_contact_email(self):
        from core.models import StoreSettings

        row = StoreSettings.objects.first() or StoreSettings.objects.create()
        row.contact_email = 'hello@shop.example'
        row.save()
        E.send_enquiry_host_notification(
            Enquiry(service=self.service, name='Ana', email='ana@example.com')
        )
        self.assertEqual(mail.outbox[0].to, ['hello@shop.example'])

    def test_a_stay_enquiry_confirms_to_the_guest(self):
        E.notify_stay_enquiry(
            StayEnquiry(property=self.property, name='Ben', email='ben@example.com')
        )
        self.assertIn(['ben@example.com'], [m.to for m in mail.outbox])

    def test_a_booking_tells_the_guest_and_the_host(self):
        E.notify_booking(
            Booking(
                service=self.service, customer_name='Cleo', customer_email='cleo@example.com',
                booking_date=date.today() + timedelta(days=5), guests=2,
                total_price=Money(100, 'EUR'), status='confirmed',
            )
        )  # fmt: skip
        self.assertEqual(
            [m.to for m in mail.outbox], [['cleo@example.com'], ['noreply@example.com']]
        )
        self.assertEqual(mail.outbox[1].reply_to, ['cleo@example.com'])
