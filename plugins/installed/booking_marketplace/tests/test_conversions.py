"""A booking is a conversion, and its owner says so once (v0.162.0).

booking_marketplace announces an enquiry (ENQUIRY_CREATED), a booking
(BOOKING_CREATED) and its confirmation (BOOKING_CONFIRMED) after each commits, once
per row. analytics records them as leads and bookings, never as sales; tracking
sends GA4 one generate_lead and one purchase; the Conversions page and Linda's
`bookings.conversions` count them. Until v0.162.0 an enquiry or a booking left no
trace in analytics or GA4, the experience page reported no product view, and a
search by region or date alone was not a search.
"""

from __future__ import annotations

import datetime
import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.cache import cache
from django.db import transaction
from django.test import RequestFactory, TestCase
from django.utils import timezone
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.booking_marketplace import conversion_report, conversions, country, stays
from plugins.installed.booking_marketplace import services as S
from plugins.installed.booking_marketplace.models import (
    BookableService,
    Booking,
    Enquiry,
    Property,
    RoomType,
    StayEnquiry,
)
from plugins.installed.booking_marketplace.products import ensure_product
from plugins.installed.catalog.models import Category, Product, Vendor
from plugins.registry import app_registry

_BROWSER = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15'
_GA = 'GA1.1.1234567890.1700000000'
_DELAY = 'plugins.installed.tracking.tasks.send_event_task.delay'
_CONSENT = json.dumps({'necessary': True, 'analytics': True, 'marketing': False})
PAGE = '/dashboard/apps/booking_marketplace/conversions/'
ENQUIRY = MorpheusEvents.ENQUIRY_CREATED
CREATED = MorpheusEvents.BOOKING_CREATED
CONFIRMED = MorpheusEvents.BOOKING_CONFIRMED


def _future(days=10):
    return timezone.localdate() + datetime.timedelta(days=days)


def _request(**cookies):
    """The guest's POST, as the experience page receives it."""
    request = RequestFactory().post('/bookings/kotor-kayak/', HTTP_USER_AGENT=_BROWSER)
    request.COOKIES.update(cookies)
    SessionMiddleware(lambda r: None).process_request(request)
    request.user = AnonymousUser()
    return request


def _unmanaged_store():
    from core.models import StoreSettings

    row = StoreSettings.objects.first() or StoreSettings()
    row.gdpr_enabled = False
    row.save()
    cache.delete('morph:gdpr_enabled')


def _ga4(**fields):
    from plugins.installed.tracking.models import TrackingSettings

    _unmanaged_store()
    s = TrackingSettings.get_solo()
    s.measurement_id = 'G-TEST1234'
    s.api_secret = 'secret'
    s.server_side_enabled = True
    s.client_side_enabled = False
    for key, value in fields.items():
        setattr(s, key, value)
    s.save()
    return s


class Listings:
    def setUp(self):
        super().setUp()
        self.vendor = Vendor.objects.create(name='Coast Tours', slug='coast-tours', is_active=True)
        self.water = Category.objects.create(name='Water Sports', slug='water-sports')
        self.service = BookableService.objects.create(
            vendor=self.vendor,
            name='Kotor Kayak',
            slug='kotor-kayak',
            region='kotor',
            category=self.water,
            price=Money(Decimal('50.00'), 'EUR'),
            daily_capacity=10,
            max_guests_per_booking=10,
            is_active=True,
        )
        ensure_product(self.service)
        self.service.refresh_from_db()
        self.property = Property.objects.create(
            vendor=self.vendor, name='Hotel Kotor', slug='hotel-kotor', region='kotor'
        )
        self.room = RoomType.objects.create(
            property=self.property,
            name='Double',
            slug='double',
            base_rate=Money(Decimal('90.00'), 'EUR'),
            max_occupancy=2,
            max_adults=2,
            max_children=0,
            room_count=3,
        )

    def _watch(self):
        return mock.patch.object(hook_registry, 'fire', wraps=hook_registry.fire)

    @staticmethod
    def _fired(fire, *names):
        names = names or (ENQUIRY, CREATED, CONFIRMED)
        return [(c.args[0], c.kwargs) for c in fire.call_args_list if c.args and c.args[0] in names]

    def _book(self, *, approval=False, request=None, **kw):
        BookableService.objects.filter(pk=self.service.pk).update(requires_approval=approval)
        self.service.refresh_from_db()
        return S.create_booking(
            self.service,
            booking_date=kw.pop('booking_date', _future()),
            guests=kw.pop('guests', 2),
            name='Ana',
            email='ana@example.com',
            request=request,
            **kw,
        )


class AnnouncedOnceTests(Listings, TestCase):
    def test_an_enquiry_is_announced_after_it_commits(self):
        with self._watch() as fire, self.captureOnCommitCallbacks(execute=True):
            enquiry = S.submit_enquiry(
                self.service,
                email='ana@example.com',
                name='Ana',
                preferred_date=_future(5).isoformat(),
                guests='2',
                request=_request(),
            )
            self.assertEqual(self._fired(fire), [], 'nothing before the commit')
        [(name, kw)] = self._fired(fire)
        self.assertEqual(name, ENQUIRY)
        self.assertEqual(kw['enquiry'], enquiry)
        self.assertEqual((kw['kind'], kw['reference']), ('experience', str(enquiry.pk)))
        self.assertIsNone(kw['value'])
        self.assertEqual(kw['product'], self.service.product)
        self.assertEqual(kw['service_date'], _future(5))
        self.assertIsNotNone(kw['request'])
        self.assertEqual(
            kw['items'],
            [
                {
                    'id': self.service.product.slug,
                    'name': 'Kotor Kayak',
                    'category': 'Water Sports',
                    'price': None,
                    'quantity': 2,
                }
            ],
        )

    def test_an_instant_booking_is_created_then_confirmed(self):
        with self._watch() as fire, self.captureOnCommitCallbacks(execute=True):
            booking = self._book(request=_request())
        fired = self._fired(fire)
        self.assertEqual([name for name, _ in fired], [CREATED, CONFIRMED])
        kw = fired[1][1]
        self.assertEqual(kw['booking'], booking)
        self.assertEqual(kw['value'], booking.total_price)
        self.assertEqual(kw['items'][0]['price'], booking.total_price)
        self.assertEqual(kw['service_date'], _future())
        self.assertIn('consent', booking.metadata)

    def test_a_booking_that_rolls_back_is_never_announced(self):
        with self._watch() as fire, self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    self._book(request=_request())
                    raise RuntimeError('payment step failed')
            except RuntimeError:
                pass
        self.assertEqual(self._fired(fire), [])
        self.assertFalse(Booking.objects.exists())

    def test_a_pending_booking_is_confirmed_once_by_its_host(self):
        host = get_user_model().objects.create_user(username='host', email='h@example.com')
        Vendor.objects.filter(pk=self.vendor.pk).update(owner=host)
        with self._watch() as fire, self.captureOnCommitCallbacks(execute=True):
            booking = self._book(approval=True, request=_request())
        self.assertEqual([name for name, _ in self._fired(fire)], [CREATED])

        self.client.force_login(host)
        for action, announced in (('confirm', 1), ('confirm', 0), ('complete', 0), ('cancel', 0)):
            with self._watch() as fire, self.captureOnCommitCallbacks(execute=True):
                self.client.post(
                    '/bookings/host/bookings/', {'booking_id': booking.pk, 'action': action}
                )
            fired = self._fired(fire)
            self.assertEqual(len(fired), announced, action)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')

    def test_a_confirmation_carries_no_request(self):
        with self.captureOnCommitCallbacks(execute=True):
            booking = self._book(approval=True, request=_request())
        with self._watch() as fire, self.captureOnCommitCallbacks(execute=True):
            S.set_booking_status(booking, 'confirmed')
        [(name, kw)] = self._fired(fire)
        self.assertEqual(name, CONFIRMED)
        self.assertIsNone(kw['request'], 'the guest is not there')
        self.assertEqual(kw['reference'], str(booking.pk))

    def test_stays_are_announced_as_stays(self):
        with self._watch() as fire, self.captureOnCommitCallbacks(execute=True):
            stay = stays.create_stay_booking(
                room_type=self.room,
                customer_name='Ben',
                customer_email='ben@example.com',
                check_in=_future(30),
                check_out=_future(32),
                request=_request(),
            )
            stays.submit_stay_enquiry(
                property=self.property, room_type=self.room, email='cy@example.com', rooms='2'
            )
            # A hotel with no rooms on file takes an enquiry for the hotel itself.
            stays.submit_stay_enquiry(
                property=self.property, email='di@example.com', check_in=_future(40)
            )
        fired = self._fired(fire)
        self.assertEqual([name for name, _ in fired], [CREATED, CONFIRMED, ENQUIRY, ENQUIRY])
        booked = fired[1][1]
        self.assertEqual(booked['kind'], 'stay')
        self.assertEqual(booked['value'], stay.total)
        self.assertEqual(booked['items'][0]['id'], 'hotel-kotor/double')
        self.assertEqual(booked['items'][0]['name'], 'Hotel Kotor · Double')
        self.assertIsNone(booked['product'])
        self.assertEqual(fired[2][1]['items'][0]['quantity'], 2)
        roomless = fired[3][1]
        self.assertEqual((roomless['kind'], roomless['value']), ('stay', None))
        self.assertEqual(
            [(i['id'], i['name']) for i in roomless['items']], [('hotel-kotor', 'Hotel Kotor')]
        )
        self.assertEqual(roomless['service_date'], _future(40))

    def test_items_name_the_listing_as_stored_not_as_shown(self):
        """A /sr/ or /hr/ page overlays a translation on the same instance
        (core.i18n keeps the original in `_morph_untranslated`); GA4 gets the
        default-language name."""
        product = self.service.product
        product.__dict__['_morph_untranslated'] = {'name': product.name}
        product.name = 'Kajak u Kotoru'
        self.assertEqual(conversions._experience_item(self.service)['name'], 'Kotor Kayak')


class PageEventsTests(Listings, TestCase):
    def test_the_experience_page_reports_one_product_view(self):
        from plugins.installed.analytics.models import AnalyticsEvent

        with self._watch() as fire:
            response = self.client.get('/bookings/kotor-kayak/', HTTP_USER_AGENT=_BROWSER)
        self.assertEqual(response.status_code, 200)
        views = self._fired(fire, MorpheusEvents.PRODUCT_VIEWED)
        self.assertEqual(len(views), 1)
        self.assertEqual(views[0][1]['product'].pk, self.service.product_id)
        self.assertEqual(
            AnalyticsEvent.objects.filter(
                name='product.viewed', product_slug=self.service.product.slug
            ).count(),
            1,
        )

    def test_a_listing_without_a_product_reports_none(self):
        BookableService.objects.filter(pk=self.service.pk).update(product=None)
        with self._watch() as fire:
            self.client.get('/bookings/kotor-kayak/', HTTP_USER_AGENT=_BROWSER)
        self.assertEqual(self._fired(fire, MorpheusEvents.PRODUCT_VIEWED), [])

    def test_a_search_by_filters_alone_is_reported_with_them(self):
        day = _future(7)
        with self._watch() as fire:
            self.client.get(
                '/bookings/',
                {
                    'region': 'kotor',
                    'date': day.isoformat(),
                    'category': 'water-sports',
                    'guests': '2',
                },
            )
            self.client.get('/bookings/', {'region': 'kotor', 'page': '2'})
            self.client.get('/bookings/')
        [(_, kw)] = self._fired(fire, MorpheusEvents.SEARCH_PERFORMED)
        self.assertEqual(kw['query'], '')
        self.assertEqual(
            [(f['key'], f['value']) for f in kw['filters']],
            [('region', 'kotor'), ('date', day.isoformat()), ('category', 'water-sports'),
             ('guests', '2')],
        )  # fmt: skip
        self.assertEqual(kw['filters'][0]['value_label'], dict(country.regions())['kotor'])


class ConversionsReportTests(Listings, TestCase):
    def _at(self, row, days_ago):
        type(row).objects.filter(pk=row.pk).update(
            created_at=timezone.now() - datetime.timedelta(days=days_ago)
        )

    def _booking(self, total, *, status='confirmed', date=None, days_ago=0, currency='EUR'):
        row = Booking.objects.create(
            service=self.service,
            customer_name='Ana',
            customer_email='ana@example.com',
            booking_date=date or _future(10),
            guests=2,
            subtotal=Money(total, currency),
            service_fee=Money(0, currency),
            total_price=Money(total, currency),
            status=status,
        )
        self._at(row, days_ago)
        return row

    def test_an_empty_store(self):
        result = conversion_report.report(days=30)
        self.assertEqual(result['totals']['enquiries'], 0)
        self.assertEqual(result['totals']['value'], Money(0, result['currency']))
        self.assertEqual(result['top'], [])
        self.assertEqual(result['change'], {'enquiries': None, 'bookings': None, 'value': None})

    def test_counts_lead_time_comparison_and_currency(self):
        Enquiry.objects.create(
            service=self.service, email='a@example.com', preferred_date=_future(1)
        )
        StayEnquiry.objects.create(
            property=self.property, email='b@example.com', check_in=_future(45)
        )
        Enquiry.objects.create(service=self.service, email='c@example.com')  # no date
        self._booking(Decimal('100'), date=_future(5))
        self._booking(Decimal('60'), status='pending', date=_future(120))
        self._booking(Decimal('999'), status='cancelled')
        self._booking(Decimal('20'), currency='USD')
        self._booking(Decimal('80'), days_ago=40)  # the 30 days before

        with mock.patch('plugins.dropshipping.importer.store_currency', return_value='EUR'):
            result = conversion_report.report(days=30)
        totals = result['totals']
        self.assertEqual((totals['enquiries'], totals['bookings']), (3, 3))
        self.assertEqual(totals['value'], Money(Decimal('160'), 'EUR'))
        self.assertEqual(totals['other'], [Money(Decimal('20'), 'USD')])
        self.assertEqual(result['before']['bookings'], 1)
        self.assertEqual(result['change']['bookings'], 200.0)
        self.assertEqual(result['change']['value'], 100.0)
        lead = {row['label']: (row['enquiries'], row['bookings']) for row in result['lead_time']}
        self.assertEqual(lead['0–2 days'], (1, 0))
        self.assertEqual(lead['3–7 days'], (0, 1))
        self.assertEqual(lead['8–30 days'], (0, 1))
        self.assertEqual(lead['31–90 days'], (1, 0))
        self.assertEqual(lead['Over 90 days'], (0, 1))
        self.assertEqual(lead['No date given'], (1, 0))
        self.assertEqual(result['top'][0]['label'], 'Kotor Kayak')
        self.assertEqual(result['top'][0]['value'], Money(Decimal('160'), 'EUR'))
        self.assertEqual(result['top'][1]['label'], 'Hotel Kotor')
        [region] = result['regions']
        self.assertEqual(region['label'], dict(country.regions())['kotor'])
        self.assertEqual((region['enquiries'], region['bookings']), (3, 3))

    def test_the_page(self):
        staff = get_user_model().objects.create_user(
            username='op', email='op@example.com', is_staff=True
        )
        self.client.force_login(staff)
        empty = self.client.get(PAGE)
        self.assertEqual(empty.status_code, 200)
        self.assertContains(empty, 'No enquiries or bookings in this period.')
        self._booking(Decimal('100'))
        body = self.client.get(PAGE, {'days': '7'}).content.decode()
        self.assertIn('data-booking-value', body)
        self.assertIn('Kotor Kayak', body)
        self.assertIn('aria-current="page">7 days', body)

    def test_the_page_asks_for_analytics_read(self):
        self.assertEqual(self.client.get(PAGE).status_code, 302)
        staff = get_user_model().objects.create_user(
            username='clerk', email='clerk@example.com', is_staff=True
        )
        self.client.force_login(staff)
        for granted, status in ((False, 403), (True, 200)):
            with (
                mock.patch('core.authz.enforcement_mode', return_value='enforce'),
                mock.patch(
                    'core.authz.has_capability',
                    side_effect=lambda user, cap, granted=granted, **kw: (
                        granted or cap != 'analytics.read'
                    ),
                ),
            ):
                self.assertEqual(self.client.get(PAGE).status_code, status, granted)

    def test_lindas_tool(self):
        from core.agents.registry import agent_registry

        self._booking(Decimal('100'))
        tool = agent_registry.get_tool('bookings.conversions')
        self.assertEqual(tool.scopes, ['analytics.read'])
        out = tool.invoke({'days': 7}).output
        self.assertEqual(out['days'], 7)
        self.assertEqual(out['this_period']['bookings'], 1)
        self.assertEqual(out['this_period']['booking_value']['amount'], '100.00')
        self.assertEqual(out['top_listings'][0]['name'], 'Kotor Kayak')
        self.assertEqual(out['by_region'][0]['region'], dict(country.regions())['kotor'])


class AnalyticsTests(Listings, TestCase):
    def _visitor(self):
        from plugins.installed.analytics.services import get_or_create_session

        request = _request(morph_aid='guest-1', morpheus_consent=_CONSENT)
        return request, get_or_create_session(request)

    def test_a_booking_is_on_the_guests_visit_and_is_no_sale(self):
        from plugins.installed.analytics.models import AnalyticsEvent, DailyMetric
        from plugins.installed.analytics.services import roll_daily, summary_for
        from plugins.installed.analytics.visits import sources_report

        _unmanaged_store()
        request, visit = self._visitor()
        with self.captureOnCommitCallbacks(execute=True):
            booking = self._book(approval=True, request=request)
        created = AnalyticsEvent.objects.get(name='booking.created')
        self.assertEqual((created.kind, created.session_id), ('booking', visit.pk))
        self.assertIsNone(created.revenue)
        self.assertEqual(created.payload['value'], str(booking.total_price.amount))
        self.assertEqual(created.payload['currency'], 'EUR')
        self.assertEqual(created.payload['kind'], 'experience')
        self.assertEqual(created.payload['reference'], str(booking.pk))
        self.assertEqual(created.payload['lead_days'], 10)
        booking.refresh_from_db()
        self.assertEqual(booking.metadata['analytics'], {'visitor': str(visit.pk)})

        # The host confirms days later: the event joins the visit stamped on the booking.
        with self.captureOnCommitCallbacks(execute=True):
            S.set_booking_status(booking, 'confirmed')
        confirmed = AnalyticsEvent.objects.get(name='booking.confirmed')
        self.assertEqual((confirmed.kind, confirmed.session_id), ('booking', visit.pk))

        today = timezone.localdate()
        roll_daily(day=today)
        self.assertEqual(DailyMetric.objects.get(day=today, metric='orders').value_int, 0)
        self.assertFalse(DailyMetric.objects.filter(day=today, metric='revenue').exists())
        self.assertEqual(summary_for(days=1)['orders'], 0)
        totals = sources_report(days=1)['totals']
        self.assertEqual((totals['purchases'], totals['sales']), (0, None))

    def test_an_enquiry_is_a_lead(self):
        from plugins.installed.analytics.models import AnalyticsEvent

        request, visit = self._visitor()
        with self.captureOnCommitCallbacks(execute=True):
            S.submit_enquiry(
                self.service, email='a@example.com', preferred_date=_future(3), request=request
            )
        lead = AnalyticsEvent.objects.get(name='enquiry.created')
        self.assertEqual((lead.kind, lead.session_id), ('lead', visit.pk))
        self.assertEqual(lead.payload['lead_days'], 3)
        self.assertNotIn('value', lead.payload)

    def test_the_bookings_funnel(self):
        from plugins.installed.analytics.services import (
            default_funnel,
            funnel_for,
            funnel_presets,
            record_event,
        )

        presets = funnel_presets()
        self.assertEqual([p['key'] for p in presets], ['shop', 'bookings'])
        # Every product on this store is an experience: the page opens on bookings.
        self.assertEqual(default_funnel(presets)['key'], 'bookings')
        _, visit = self._visitor()
        for name in ('search.performed', 'product.viewed', 'booking.created'):
            record_event(name=name, session=visit)
        bookings = next(p for p in presets if p['key'] == 'bookings')
        rows = funnel_for(steps=bookings['steps'], days=30)
        self.assertEqual([r['sessions'] for r in rows], [1, 1, 1])
        self.assertEqual(rows[2]['step'], 'Enquired or booked')

        Product.objects.create(
            name='Honey', slug='honey', price=Money(5, 'EUR'), product_type='simple',
            status='active',
        )  # fmt: skip
        self.assertEqual(default_funnel(funnel_presets())['key'], 'shop')

    def test_switched_off_the_bookings_funnel_leaves_with_the_app(self):
        from plugins.installed.analytics.services import funnel_presets

        app_registry._active.discard('booking_marketplace')
        self.addCleanup(app_registry._active.add, 'booking_marketplace')
        self.assertEqual([p['key'] for p in funnel_presets()], ['shop'])


class GA4Tests(Listings, TestCase):
    def test_a_pending_booking_reaches_ga4_once_when_its_host_confirms(self):
        _ga4()
        with mock.patch(_DELAY) as delay, self.captureOnCommitCallbacks(execute=True):
            booking = self._book(approval=True, request=_request(_ga=_GA))
        self.assertNotIn('purchase', [c.kwargs['event_name'] for c in delay.call_args_list])
        booking.refresh_from_db()
        self.assertEqual(booking.metadata['ga'], {'client_id': '1234567890.1700000000'})

        with mock.patch(_DELAY) as delay, self.captureOnCommitCallbacks(execute=True):
            S.set_booking_status(booking, 'confirmed')
        self.assertEqual(delay.call_count, 1)
        kwargs = delay.call_args.kwargs
        self.assertEqual(kwargs['event_name'], 'purchase')
        self.assertEqual(kwargs['transaction_id'], str(booking.pk))
        self.assertEqual(kwargs['client_id'], '1234567890.1700000000')
        params = kwargs['params']
        self.assertEqual((params['transaction_id'], params['currency']), (str(booking.pk), 'EUR'))
        self.assertEqual(params['value'], float(booking.total_price.amount))
        self.assertEqual(params['items'][0]['item_id'], self.service.product.slug)
        # Confirmed again (a second click): nothing more.
        with mock.patch(_DELAY) as delay, self.captureOnCommitCallbacks(execute=True):
            S.set_booking_status(booking, 'confirmed')
        delay.assert_not_called()

    def test_a_booking_without_ga_ids_is_not_sent_later(self):
        _ga4()
        with self.captureOnCommitCallbacks(execute=True):
            booking = self._book(approval=True, request=_request())
        with mock.patch(_DELAY) as delay, self.captureOnCommitCallbacks(execute=True):
            S.set_booking_status(booking, 'confirmed')
        delay.assert_not_called()

    def test_an_enquiry_is_a_lead_from_the_server_without_a_browser_tag(self):
        _ga4()
        with mock.patch(_DELAY) as delay, self.captureOnCommitCallbacks(execute=True):
            S.submit_enquiry(self.service, email='a@example.com', request=_request(_ga=_GA))
        self.assertEqual(delay.call_args.kwargs['event_name'], 'generate_lead')
        self.assertEqual(delay.call_args.kwargs['params']['lead_source'], 'experience_enquiry')

    def test_with_a_browser_tag_the_next_page_sends_the_lead_once(self):
        _ga4(client_side_enabled=True)
        now = lambda fn, *a, **kw: fn()  # noqa: E731 — the enquiry commits inside the request
        with (
            mock.patch(_DELAY) as delay,
            mock.patch('django.db.transaction.on_commit', side_effect=now),
        ):
            posted = self.client.post(
                '/bookings/kotor-kayak/',
                {'name': 'Ana', 'email': 'ana@example.com', 'guests': '2'},
                HTTP_USER_AGENT=_BROWSER,
            )
        self.assertEqual(posted.status_code, 302)
        delay.assert_not_called()
        self.assertTrue(Enquiry.objects.exists())

        page = self.client.get(posted['Location'], HTTP_USER_AGENT=_BROWSER)
        body = page.content.decode()
        self.assertEqual(body.count('"generate_lead"'), 1)
        self.assertEqual(page['Cache-Control'], 'private, no-store')
        again = self.client.get(posted['Location'], HTTP_USER_AGENT=_BROWSER)
        self.assertNotIn('generate_lead', again.content.decode())
        self.assertNotEqual(again.get('Cache-Control'), 'private, no-store')

    def test_switched_off_tracking_sends_nothing(self):
        _ga4()
        app_registry._active.discard('tracking')
        self.addCleanup(app_registry._active.add, 'tracking')
        with mock.patch(_DELAY) as delay, self.captureOnCommitCallbacks(execute=True):
            self._book(request=_request(_ga=_GA))
        delay.assert_not_called()

    def test_switched_off_analytics_records_nothing(self):
        from plugins.installed.analytics.models import AnalyticsEvent

        app_registry._active.discard('analytics')
        self.addCleanup(app_registry._active.add, 'analytics')
        with self.captureOnCommitCallbacks(execute=True):
            self._book(request=_request())
        self.assertTrue(Booking.objects.exists())
        self.assertFalse(AnalyticsEvent.objects.filter(name__startswith='booking.').exists())
