"""Host form saves listing_kind + logistics fields."""

from django.contrib.auth import get_user_model
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase

from plugins.installed.booking_marketplace import host
from plugins.installed.booking_marketplace.models import BookableService


class HostKindTests(TestCase):
    def setUp(self):
        from plugins.installed.catalog.models import Vendor
        U = get_user_model()
        self.user = U.objects.create(**{U.USERNAME_FIELD: 'host2@x.io'})
        self.vendor = Vendor.objects.create(name='V', slug='v', is_active=True, owner=self.user)

    def _req(self, data):
        req = RequestFactory().post('/bookings/host/new/', data)
        SessionMiddleware(lambda r: None).process_request(req)
        MessageMiddleware(lambda r: None).process_request(req)
        req.user = self.user
        return req

    def test_saves_product_kind_and_languages(self):
        data = {
            'name': 'Vranac', 'listing_kind': 'product', 'price': '18',
            'languages': 'English, Montenegrin', 'is_active': 'on',
        }
        resp = host.host_service_form(self._req(data))
        self.assertEqual(resp.status_code, 302)
        svc = BookableService.objects.get(name='Vranac')
        self.assertEqual(svc.listing_kind, 'product')
        self.assertEqual(svc.languages, ['English', 'Montenegrin'])

    def test_saves_experience_meeting_point(self):
        data = {
            'name': 'Kayak', 'listing_kind': 'experience', 'price': '50',
            'meeting_point': 'Old pier', 'latitude': '42.42', 'longitude': '18.77',
            'is_active': 'on',
        }
        host.host_service_form(self._req(data))
        svc = BookableService.objects.get(name='Kayak')
        self.assertEqual(svc.meeting_point, 'Old pier')
        self.assertEqual(str(svc.latitude), '42.420000')

    def test_saves_tiers_and_addons(self):
        data = {
            'name': 'Kayak', 'listing_kind': 'experience', 'price': '50', 'is_active': 'on',
            'tier_name': ['Adult', 'Child'], 'tier_price': ['50', '25'],
            'addon_name': ['Pickup'], 'addon_price': ['10'], 'addon_type': ['per_booking'],
        }
        host.host_service_form(self._req(data))
        svc = BookableService.objects.get(name='Kayak')
        self.assertEqual(svc.tiers.count(), 2)
        self.assertEqual(svc.addons.first().name, 'Pickup')
        self.assertEqual(str(svc.tiers.get(name='Adult').price.amount), '50.00')
