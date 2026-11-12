"""A lead and a booking reach GA4 once (v0.162.0).

An enquiry is GA4's `generate_lead`, a confirmed booking its `purchase` with the
booking's reference as the transaction. One sender per event: with a Google tag on
the guest's page, the next page they load sends it (the push waits in their
session, and that page is never shared-cached); without one, the Measurement
Protocol. A booking a host confirms later is always sent from the server, joined
to the guest only by the GA ids stamped on it, and not at all without them.
booking_marketplace's tests run the same path from real bookings
(booking_marketplace/tests/test_conversions.py).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.cache import cache
from django.http import HttpResponse
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase, TestCase
from djmoney.money import Money

from core.storefront_cache import PRIVATE_VALUE, StorefrontCacheMiddleware, is_private, keep_private
from plugins.installed.tracking.models import GA4EventLog, TrackingSettings
from plugins.installed.tracking.services import event_mapping
from plugins.installed.tracking.services.measurement_protocol import send_event
from plugins.installed.tracking.templatetags.tracking import QUEUE_KEY
from plugins.registry import app_registry

_DELAY = 'plugins.installed.tracking.tasks.send_event_task.delay'
_BROWSER = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15'
_GA = 'GA1.1.1234567890.1700000000'
_ITEMS = [
    {
        'id': 'kotor-kayak',
        'name': 'Kotor Kayak',
        'category': 'Water Sports',
        'price': Money('112.00', 'EUR'),
        'quantity': 1,
    }
]
_QUEUED = Template('{% load tracking %}{% tracking_queued_events %}')


def _store(*, gdpr=False, **fields) -> TrackingSettings:
    from core.models import StoreSettings

    row = StoreSettings.objects.first() or StoreSettings()
    row.gdpr_enabled = gdpr
    row.save()
    cache.delete('morph:gdpr_enabled')
    s = TrackingSettings.get_solo()
    s.measurement_id = 'G-TEST1234'
    s.api_secret = 'secret'
    s.server_side_enabled = True
    s.client_side_enabled = False
    for key, value in fields.items():
        setattr(s, key, value)
    s.save()
    return s


def _request(*, session=True, path='/bookings/kotor-kayak/', **cookies):
    request = RequestFactory().post(path, HTTP_USER_AGENT=_BROWSER)
    request.COOKIES.update(cookies)
    if session:
        SessionMiddleware(lambda r: None).process_request(request)
    request.user = AnonymousUser()
    return request


def _next_page(request):
    """The guest's next page, on the same session."""
    request.session.save()
    page = RequestFactory().get('/bookings/kotor-kayak/', HTTP_USER_AGENT=_BROWSER)
    page.COOKIES[settings.SESSION_COOKIE_NAME] = request.session.session_key
    SessionMiddleware(lambda r: None).process_request(page)
    page.user = AnonymousUser()
    return page


def _plugin():
    return app_registry.get('tracking')


def _lead(request):
    _plugin().on_enquiry(
        enquiry=SimpleNamespace(pk=7, metadata=None, customer_id=None),
        kind='experience',
        items=[{**_ITEMS[0], 'price': None, 'quantity': 2}],
        value=None,
        request=request,
    )


def _confirmed(request, metadata=None):
    _plugin().on_booking_confirmed(
        booking=SimpleNamespace(pk=9, metadata=metadata, customer_id=None),
        reference='9',
        value=Money('112.00', 'EUR'),
        items=_ITEMS,
        request=request,
    )


class BuilderTests(SimpleTestCase):
    def test_generate_lead(self):
        name, params = event_mapping.generate_lead(
            kind='experience', items=[{**_ITEMS[0], 'price': None, 'quantity': 2}]
        )
        self.assertEqual(name, 'generate_lead')
        self.assertEqual(params['lead_source'], 'experience_enquiry')
        self.assertEqual(
            params['items'],
            [
                {
                    'item_id': 'kotor-kayak',
                    'item_name': 'Kotor Kayak',
                    'quantity': 2,
                    'item_category': 'Water Sports',
                }
            ],
        )
        self.assertNotIn('value', params, 'an enquiry has no price')

    def test_booking_purchase(self):
        name, params = event_mapping.booking_purchase(
            reference='9', value=Money('112.00', 'EUR'), items=_ITEMS
        )
        self.assertEqual(name, 'purchase')
        self.assertEqual(
            (params['transaction_id'], params['currency'], params['value']), ('9', 'EUR', 112.0)
        )
        self.assertEqual(params['items'][0]['price'], 112.0)


class ServerSideTests(TestCase):
    """No Google tag in the browser: the Measurement Protocol is the one sender."""

    def test_a_lead_carries_the_guests_ids(self):
        _store()
        with patch(_DELAY) as delay:
            _lead(_request(_ga=_GA))
        kwargs = delay.call_args.kwargs
        self.assertEqual(kwargs['event_name'], 'generate_lead')
        self.assertEqual(kwargs['client_id'], '1234567890.1700000000')

    def test_no_lead_without_the_visitors_consent(self):
        _store(gdpr=True)
        with patch(_DELAY) as delay:
            _lead(_request(_ga=_GA))
        delay.assert_not_called()

    def test_a_later_confirmation_uses_the_ids_and_consent_stamped_on_the_booking(self):
        _store(gdpr=True)
        stamp = {
            'ga': {'client_id': '111.222', 'session_id': '333'},
            'consent': {'managed': True, 'analytics': True, 'marketing': False},
        }
        with patch(_DELAY) as delay:
            _confirmed(None, metadata=stamp)
        kwargs = delay.call_args.kwargs
        self.assertEqual((kwargs['event_name'], kwargs['transaction_id']), ('purchase', '9'))
        self.assertEqual((kwargs['client_id'], kwargs['session_id']), ('111.222', '333'))
        self.assertEqual(kwargs['params']['transaction_id'], '9')
        self.assertEqual(kwargs['consent']['ad_user_data'], 'DENIED')

    def test_a_later_confirmation_without_ids_or_consent_sends_nothing(self):
        _store(gdpr=True)
        refused = {'managed': True, 'analytics': False, 'marketing': False}
        for metadata in (
            None,
            {'consent': {'managed': True, 'analytics': True, 'marketing': True}},
            {'ga': {'client_id': '111.222'}, 'consent': refused},
        ):
            with patch(_DELAY) as delay:
                _confirmed(None, metadata=metadata)
            delay.assert_not_called()

    def test_a_search_without_words_is_not_sent(self):
        _store()
        with patch(_DELAY) as delay:
            _plugin().on_search(query='', request=_request(_ga=_GA))
            _plugin().on_search(query='   ', request=_request(_ga=_GA))
        delay.assert_not_called()
        with patch(_DELAY) as delay:
            _plugin().on_search(query='kayak', request=_request(_ga=_GA))
        self.assertEqual(delay.call_args.kwargs['params'], {'search_term': 'kayak'})

    def test_the_lead_switch_stops_the_server_send(self):
        s = _store()
        s.event_firing = {**(s.event_firing or {}), 'generate_lead': False}
        s.save()
        with patch('plugins.installed.tracking.services.measurement_protocol._urlrequest') as http:
            row = send_event(event_name='generate_lead', params={})
        self.assertEqual(row.status, GA4EventLog.STATUS_DISABLED)
        http.urlopen.assert_not_called()

    def test_the_switch_is_on_the_settings_page(self):
        _store()
        staff = get_user_model().objects.create_user(
            username='staff', email='staff@example.com', is_staff=True
        )
        self.client.force_login(staff)
        page = self.client.get('/dashboard/tracking/settings/?tab=events')
        self.assertContains(page, 'name="event_generate_lead" checked')


class BrowserPushTests(TestCase):
    """A Google tag on the guest's page: their next page sends it, once."""

    def setUp(self):
        self.s = _store(client_side_enabled=True)

    def test_a_lead_waits_for_the_next_page_then_is_gone(self):
        request = _request(_ga=_GA)
        with patch(_DELAY) as delay:
            _lead(request)
        delay.assert_not_called()
        self.assertEqual(request.session[QUEUE_KEY][0]['event'], 'generate_lead')

        page = _next_page(request)
        html = _QUEUED.render(Context({'request': page}))
        self.assertEqual(html.count('gtag("event","generate_lead"'), 1)
        self.assertIn('"lead_source": "experience_enquiry"', html)
        self.assertTrue(is_private(page))
        again = _next_page(page)
        self.assertEqual(_QUEUED.render(Context({'request': again})), '')
        self.assertFalse(is_private(again))

    def test_a_purchase_in_the_guests_request_goes_to_the_browser(self):
        request = _request(_ga=_GA)
        with patch(_DELAY) as delay:
            _confirmed(request)
        delay.assert_not_called()
        [queued] = request.session[QUEUE_KEY]
        self.assertEqual(queued['event'], 'purchase')
        self.assertEqual(queued['params']['transaction_id'], '9')

    def test_a_later_confirmation_still_goes_from_the_server(self):
        with patch(_DELAY) as delay:
            _confirmed(None, metadata={'ga': {'client_id': '111.222'}})
        self.assertEqual(delay.call_args.kwargs['event_name'], 'purchase')

    def test_without_a_session_the_server_sends_it(self):
        with patch(_DELAY) as delay:
            _lead(_request(session=False, _ga=_GA))
        self.assertEqual(delay.call_args.kwargs['event_name'], 'generate_lead')

    def test_nothing_waits_without_consent_or_with_the_switch_off(self):
        _store(gdpr=True, client_side_enabled=True)
        request = _request(_ga=_GA)
        with patch(_DELAY) as delay:
            _lead(request)
        delay.assert_not_called()
        self.assertNotIn(QUEUE_KEY, request.session)

        _store(client_side_enabled=True, event_firing={'generate_lead': False})
        request = _request(_ga=_GA)
        with patch(_DELAY) as delay:
            _lead(request)
        delay.assert_not_called()
        self.assertNotIn(QUEUE_KEY, request.session)

    def test_a_visitor_without_a_session_cookie_is_not_read(self):
        page = RequestFactory().get('/')
        SessionMiddleware(lambda r: None).process_request(page)
        self.assertEqual(_QUEUED.render(Context({'request': page})), '')
        self.assertFalse(page.session.accessed)


class PrivatePageTests(SimpleTestCase):
    def test_both_cache_layers_answer_private(self):
        from plugins.installed.storefront.middleware import StorefrontCacheControlMiddleware

        def view(request):
            keep_private(request)
            return HttpResponse('ok')

        for middleware in (StorefrontCacheMiddleware, StorefrontCacheControlMiddleware):
            response = middleware(view)(RequestFactory().get('/'))
            self.assertEqual(response['Cache-Control'], PRIVATE_VALUE, middleware.__name__)
