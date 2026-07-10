"""Enquiry notifications — host/ops alert + guest confirmation (fail-soft)."""

from django.core import mail
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.booking_marketplace import services as S
from plugins.installed.booking_marketplace.models import BookableService


def _svc():
    from plugins.installed.catalog.models import Vendor

    v = Vendor.objects.create(name='Acme', slug='acme', is_active=True)
    return BookableService.objects.create(
        vendor=v, name='Kayak', slug='kayak', price=Money(50, 'EUR')
    )


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    BOOKING_ENQUIRY_NOTIFY_EMAIL='ops@example.com',
)
class EnquiryEmailTests(TestCase):
    def test_enquiry_sends_host_and_guest_emails(self):
        svc = _svc()
        mail.outbox = []
        S.submit_enquiry(svc, email='lead@x.io', name='Lead', message='hi', guests=2)
        self.assertEqual(len(mail.outbox), 2)
        recipients = {addr for m in mail.outbox for addr in m.to}
        self.assertIn('lead@x.io', recipients)  # guest confirmation
        self.assertIn('ops@example.com', recipients)  # host/ops notification

    def test_host_owner_email_preferred_over_ops(self):
        from django.contrib.auth import get_user_model

        from plugins.installed.catalog.models import Vendor

        U = get_user_model()
        owner = U.objects.create(**{U.USERNAME_FIELD: 'host@x.io', 'email': 'host@x.io'})
        v = Vendor.objects.create(name='Owned', slug='owned', is_active=True, owner=owner)
        svc = BookableService.objects.create(
            vendor=v, name='Sail', slug='sail', price=Money(9, 'EUR')
        )
        mail.outbox = []
        S.submit_enquiry(svc, email='lead2@x.io', name='L2')
        recipients = {addr for m in mail.outbox for addr in m.to}
        self.assertIn('host@x.io', recipients)  # vendor owner beats ops fallback

    def test_send_failure_never_breaks_capture(self):
        from plugins.installed.booking_marketplace.models import Enquiry

        svc = _svc()
        with override_settings(
            EMAIL_BACKEND='plugins.installed.booking_marketplace.tests.test_email.BoomBackend'
        ):
            e = S.submit_enquiry(svc, email='lead3@x.io', name='L3')
        self.assertIsNotNone(e)  # enquiry still created despite mail blowing up
        self.assertEqual(Enquiry.objects.filter(email='lead3@x.io').count(), 1)


class BoomBackend:
    """An email backend that raises, to prove notifications are fail-soft."""

    def __init__(self, *a, **k):
        pass

    def send_messages(self, messages):
        raise RuntimeError('smtp down')
