"""Leads and bookings, funnel presets and filtered searches (v0.162.0).

An enquiry is recorded as a `lead`, a booking as a `booking`, with its kind,
reference, value and lead time in the payload and never as revenue: the store's
sales stay its orders. The Funnel page offers every app's preset
(ANALYTICS_FUNNELS), and the searches that found nothing are grouped by the
filters they were made with. booking_marketplace's own tests fire the events
from real bookings (booking_marketplace/tests/test_conversions.py).
"""

from __future__ import annotations

import datetime
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone
from djmoney.money import Money

from core.agents.registry import agent_registry
from core.utils.site import store_today
from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.analytics.app import _payload
from plugins.installed.analytics.models import AnalyticsEvent, AnalyticsSession, DailyMetric
from plugins.installed.analytics.services import (
    default_funnel,
    funnel_for,
    funnel_presets,
    no_results_by_filter,
    record_event,
    roll_daily,
)
from plugins.installed.analytics.visits import search_terms

_CONSENT = '{"necessary": true, "analytics": true}'
_REGION = {'key': 'region', 'label': 'Region', 'value': 'kotor', 'value_label': 'Kotor Bay'}
_DATE = {'key': 'date', 'label': 'Date', 'value': '2026-12-01', 'value_label': 'Tue 1 Dec'}


def _visitor(cookie='guest-1'):
    request = RequestFactory().post('/bookings/kotor-kayak/')
    request.COOKIES.update({'morph_aid': cookie, 'morpheus_consent': _CONSENT})
    from plugins.installed.analytics.services import get_or_create_session

    return request, get_or_create_session(request)


def _row(**kw):
    return SimpleNamespace(**{'pk': 7, 'created_at': timezone.now(), 'metadata': None, **kw})


def _with_preset(test, preset):
    """Offer one more funnel for the test, ahead of any other app's (the shop's
    own still comes first); the real handlers come back after it."""
    event = MorpheusEvents.ANALYTICS_FUNNELS
    saved = list(hook_registry._handlers[event])
    test.addCleanup(hook_registry._handlers.__setitem__, event, saved)
    hook_registry.register(event, lambda value, **kw: [*(value or []), preset], priority=5)


class RecordingTests(TestCase):
    def test_a_lead_is_recorded_on_the_visit_and_is_no_sale(self):
        request, visit = _visitor()
        hook_registry.fire(
            MorpheusEvents.ENQUIRY_CREATED,
            enquiry=_row(),
            kind='experience',
            reference='7',
            value=None,
            items=[],
            product=None,
            customer=None,
            service_date=store_today() + datetime.timedelta(days=4),
            request=request,
        )
        lead = AnalyticsEvent.objects.get(name='enquiry.created')
        self.assertEqual((lead.kind, lead.session_id), ('lead', visit.pk))
        self.assertIsNone(lead.revenue)
        self.assertEqual(lead.payload['kind'], 'experience')
        self.assertEqual(lead.payload['reference'], '7')
        self.assertEqual(lead.payload['lead_days'], 4)
        self.assertNotIn('value', lead.payload)

    def test_a_confirmation_without_a_request_joins_the_stamped_visit(self):
        _, visit = _visitor()
        booking = _row(metadata={'analytics': {'visitor': str(visit.pk)}})
        hook_registry.fire(
            MorpheusEvents.BOOKING_CONFIRMED,
            booking=booking,
            kind='stay',
            reference='7',
            value=Money('240.00', 'EUR'),
            items=[],
            product=None,
            customer=None,
            service_date=None,
            request=None,
        )
        evt = AnalyticsEvent.objects.get(name='booking.confirmed')
        self.assertEqual((evt.kind, evt.session_id), ('booking', visit.pk))
        self.assertIsNone(evt.revenue)
        self.assertEqual((evt.payload['value'], evt.payload['currency']), ('240.00', 'EUR'))
        self.assertNotIn('lead_days', evt.payload)

    def test_bookings_are_not_in_the_days_sales(self):
        _, visit = _visitor()
        record_event(name='booking.confirmed', kind='booking', session=visit)
        today = store_today()
        roll_daily(day=today)
        self.assertEqual(DailyMetric.objects.get(day=today, metric='orders').value_int, 0)
        self.assertFalse(DailyMetric.objects.filter(day=today, metric='revenue').exists())

    def test_filters_are_kept_as_short_text(self):
        payload = _payload({'filters': [_REGION, {'key': 'guests', 'value': 3}, 'junk', {}]})
        self.assertEqual(
            payload['filters'],
            [_REGION, {'key': 'guests', 'label': '', 'value': '3', 'value_label': ''}],
        )
        self.assertNotIn('filters', _payload({'filters': []}))


class FunnelPresetTests(TestCase):
    def test_steps_may_be_names_lists_or_labelled_groups(self):
        _, a = _visitor('a')
        _, b = _visitor('b')
        for visit, names in ((a, ('search.performed', 'enquiry.created')), (b, ('pageview',))):
            for name in names:
                record_event(name=name, session=visit)
        rows = funnel_for(
            steps=[
                ['search.performed', 'pageview'],
                {'label': 'Enquired or booked', 'events': ['enquiry.created', 'booking.created']},
            ],
            days=30,
        )
        self.assertEqual([r['sessions'] for r in rows], [2, 1])
        self.assertEqual(rows[1]['step'], 'Enquired or booked')
        self.assertEqual(rows[1]['events'], ['enquiry.created', 'booking.created'])
        self.assertEqual(funnel_for(steps=['pageview'], days=30)[0]['step'], 'pageview')

    def test_the_shop_preset_and_the_default(self):
        presets = funnel_presets()
        self.assertEqual(presets[0]['key'], 'shop')
        self.assertEqual(default_funnel([p for p in presets if p['key'] == 'shop'])['key'], 'shop')
        _with_preset(self, {'key': 'leads', 'label': 'Leads', 'steps': ['pageview'], 'default': 1})
        self.assertEqual(default_funnel(funnel_presets())['key'], 'leads')

    def test_a_malformed_preset_is_left_out(self):
        _with_preset(self, {'key': 'shop', 'label': 'Twice', 'steps': ['pageview']})
        _with_preset(self, {'key': 'empty', 'steps': []})
        presets = funnel_presets()
        self.assertEqual([p['label'] for p in presets if p['key'] == 'shop'], ['Shop'])
        self.assertNotIn('empty', [p['key'] for p in presets])

    def test_the_page(self):
        _with_preset(self, {'key': 'leads', 'label': 'Leads', 'steps': ['pageview']})
        staff = get_user_model().objects.create_user(
            username='staff', email='staff@test.local', is_staff=True
        )
        self.client.force_login(staff)
        url = '/dashboard/analytics/v2/funnel/'
        shop = self.client.get(url, {'preset': 'shop'})
        self.assertContains(shop, 'data-funnel-presets')
        self.assertContains(shop, 'Started checkout')
        self.assertEqual(shop.context['preset']['key'], 'shop')
        leads = self.client.get(url, {'preset': 'leads'})
        self.assertEqual(leads.context['preset']['key'], 'leads')
        unknown = self.client.get(url, {'preset': 'nope'})
        self.assertEqual(unknown.context['preset'], default_funnel(funnel_presets()))
        custom = self.client.get(url, {'steps': 'pageview,product.viewed', 'preset': 'leads'})
        self.assertIsNone(custom.context['preset'])
        self.assertEqual(custom.context['steps'], ['pageview', 'product.viewed'])

    def test_lindas_tool_takes_a_preset(self):
        _with_preset(self, {'key': 'leads', 'label': 'Leads', 'steps': ['pageview']})
        tool = agent_registry.get_tool('analytics.funnel')
        out = tool.invoke({'preset': 'leads'}).output
        self.assertEqual(out['preset'], 'leads')
        self.assertIn({'key': 'shop', 'label': 'Shop'}, out['presets'])
        self.assertEqual(len(out['funnel']), 1)
        self.assertEqual(tool.invoke({}).output['preset'], default_funnel(funnel_presets())['key'])
        self.assertIsNone(tool.invoke({'steps': ['pageview']}).output['preset'])


class FilteredSearchTests(TestCase):
    def _search(self, query, results, *filters, days_ago=0):
        evt = record_event(
            name='search.performed',
            kind='search',
            search_query=query,
            payload={'results': results, **({'filters': list(filters)} if filters else {})},
        )
        AnalyticsEvent.objects.filter(pk=evt.pk).update(
            created_at=timezone.now() - datetime.timedelta(days=days_ago)
        )

    def test_searches_that_found_nothing_by_filter(self):
        self._search('', 0, _REGION, _DATE)
        self._search('kayak', 0, _REGION)
        self._search('', 3, _REGION)  # found something
        self._search('', 0, _DATE, days_ago=40)  # before the period
        rows = no_results_by_filter(days=30)
        self.assertEqual(
            [(r['key'], r['value'], r['value_label'], r['count']) for r in rows],
            [('region', 'kotor', 'Kotor Bay', 2), ('date', '2026-12-01', 'Tue 1 Dec', 1)],
        )
        self.assertEqual(rows[0]['label'], 'Region')
        self.assertIsNotNone(rows[0]['last_seen'])

    def test_a_search_with_no_words_is_no_search_term(self):
        self._search('', 0, _REGION)
        roll_daily(day=store_today())
        self.assertEqual(search_terms(days=1, kind='top'), [])
        self.assertEqual(search_terms(days=1, kind='no_results'), [])

    def test_the_page_and_the_tool(self):
        self._search('', 0, _REGION)
        staff = get_user_model().objects.create_user(
            username='staff', email='staff@test.local', is_staff=True
        )
        self.client.force_login(staff)
        page = self.client.get('/dashboard/apps/analytics/search-terms/')
        self.assertContains(page, 'data-no-results-by-filter')
        self.assertContains(page, 'Region: Kotor Bay')
        out = agent_registry.get_tool('analytics.search_trends').invoke({'kind': 'no_results'})
        self.assertEqual(out.output['filters'][0]['value'], 'kotor')
        self.assertIsInstance(out.output['filters'][0]['last_seen'], str)
        top = agent_registry.get_tool('analytics.search_trends').invoke({'kind': 'top'})
        self.assertNotIn('filters', top.output)


class NoVisitorTests(TestCase):
    def test_a_lead_from_nobody_is_kept_without_a_visit(self):
        hook_registry.fire(
            MorpheusEvents.ENQUIRY_CREATED,
            enquiry=_row(),
            kind='stay',
            reference='7',
            value=None,
            items=[],
            product=None,
            customer=None,
            service_date=None,
            request=None,
        )
        evt = AnalyticsEvent.objects.get(name='enquiry.created')
        self.assertIsNone(evt.session_id)
        self.assertFalse(AnalyticsSession.objects.exists())
