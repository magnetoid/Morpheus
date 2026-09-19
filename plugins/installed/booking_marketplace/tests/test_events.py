"""Events — the calendar of Montenegro fixtures (carnivals, festivals, seasons).

Events are deliberately a calendar entry, not a bookable product: they are run
by municipalities and festival bodies that sell through their own channels, and
their dates move every year. Two things follow, and both are guarded here:

1. **Grouping is by `month`, not by date.** An event nine months out normally
   has no announced date, so a date-ordered calendar would drop it. Events with
   no month at all sort last, never first.
2. **The schema.org Event node is emitted only when a real `start_date` exists.**
   `startDate` is required by schema.org and Google's Event rich result, so the
   tempting fix is to synthesise one from `month`. That would publish a date the
   organiser never announced. A regression here means the site starts asserting
   wrong dates to search engines, which is worse than no rich result at all.
"""

from __future__ import annotations

import datetime
import json

from django.test import Client, TestCase

from plugins.installed.booking_marketplace.models import Event, Place
from plugins.installed.booking_marketplace.sitemap import contribute_sitemap_urls


def _event(**kw):
    defaults = {
        'name': 'Test Fixture',
        'slug': 'test-fixture',
        'month': 7,
        'when_label': 'Mid-July',
        'summary': 'A summary.',
        'is_active': True,
    }
    return Event.objects.create(**{**defaults, **kw})


class EventPageTests(TestCase):
    def test_index_renders_and_lists_an_active_event(self):
        _event(name='Kotor Test Carnival', slug='kotor-test-carnival')
        html = Client().get('/events/').content.decode()
        self.assertIn('Kotor Test Carnival', html)

    def test_index_hides_inactive_events(self):
        _event(name='Cancelled Thing', slug='cancelled-thing', is_active=False)
        html = Client().get('/events/').content.decode()
        self.assertNotIn('Cancelled Thing', html)

    def test_detail_renders(self):
        _event(name='Boka Test Night', slug='boka-test-night')
        resp = Client().get('/events/boka-test-night/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Boka Test Night', resp.content.decode())

    def test_inactive_event_detail_404s(self):
        _event(slug='hidden-event', is_active=False)
        self.assertEqual(Client().get('/events/hidden-event/').status_code, 404)

    def test_category_filter_narrows_the_list(self):
        _event(name='Music Thing', slug='music-thing', category='music')
        _event(name='Food Thing', slug='food-thing', category='food')
        html = Client().get('/events/?category=music').content.decode()
        self.assertIn('Music Thing', html)
        self.assertNotIn('Food Thing', html)


class MonthGroupingTests(TestCase):
    def test_undated_events_group_last_not_first(self):
        """month=0 means "not announced yet" — it must never sort ahead of January."""
        _event(name='January Thing', slug='january-thing', month=1)
        _event(name='Unknown Thing', slug='unknown-thing', month=0, when_label='')
        groups = Client().get('/events/').context['month_groups']
        self.assertEqual(groups[0]['month'], 1)
        self.assertEqual(groups[-1]['month'], 0)

    def test_months_are_in_calendar_order(self):
        for m in (9, 2, 6):
            _event(name=f'Event {m}', slug=f'event-{m}', month=m)
        months = [g['month'] for g in Client().get('/events/').context['month_groups']]
        self.assertEqual(months, [2, 6, 9])


class EventJsonLdTests(TestCase):
    """The honest-dates guard. See the module docstring."""

    def _graph(self, slug):
        ctx = Client().get(f'/events/{slug}/').context
        return json.loads(ctx['event_jsonld'].replace('\\u003C', '<').replace('\\u003E', '>'))[
            '@graph'
        ]

    def test_event_node_emitted_when_a_real_date_exists(self):
        _event(
            slug='dated-event',
            start_date=datetime.date(2027, 2, 6),
            end_date=datetime.date(2027, 2, 9),
        )
        types = [n.get('@type') for n in self._graph('dated-event')]
        self.assertIn('Event', types)
        node = next(n for n in self._graph('dated-event') if n.get('@type') == 'Event')
        self.assertEqual(node['startDate'], '2027-02-06')
        self.assertEqual(node['endDate'], '2027-02-09')

    def test_no_event_node_when_the_date_is_unknown(self):
        """A month is not a date — never synthesise `startDate` from it."""
        _event(slug='undated-event', month=2, when_label='Early February', start_date=None)
        graph = self._graph('undated-event')
        self.assertNotIn('Event', [n.get('@type') for n in graph])
        dumped = json.dumps(graph)
        self.assertNotIn('startDate', dumped)
        # The page still ships breadcrumbs, so it is not schema-less.
        self.assertIn('BreadcrumbList', [n.get('@type') for n in graph])

    def test_faq_node_emitted_from_faqs(self):
        _event(slug='faq-event', faqs=[{'q': 'Is it free?', 'a': 'Yes, the street events are.'}])
        self.assertIn('FAQPage', [n.get('@type') for n in self._graph('faq-event')])


class EventSitemapTests(TestCase):
    def test_active_event_and_index_contributed(self):
        _event(slug='sitemap-event')
        urls = [e['loc'] for e in contribute_sitemap_urls([])]
        self.assertTrue(any(u.endswith('/events/') for u in urls))
        self.assertTrue(any('/events/sitemap-event/' in u for u in urls))

    def test_inactive_event_not_contributed(self):
        _event(slug='dead-sitemap-event', is_active=False)
        urls = [e['loc'] for e in contribute_sitemap_urls([])]
        self.assertFalse(any('dead-sitemap-event' in u for u in urls))


class PlaceEventsTests(TestCase):
    def test_place_page_lists_its_events(self):
        place = Place.objects.create(name='Testville', slug='testville', is_active=True)
        _event(name='Testville Fest', slug='testville-fest', place=place)
        html = Client().get('/places/testville/').content.decode()
        self.assertIn('Testville Fest', html)


class SeedEventsCommandTests(TestCase):
    def test_seed_is_idempotent(self):
        from django.core.management import call_command

        call_command('seed_events', verbosity=0)
        first = Event.objects.count()
        self.assertGreater(first, 0)
        call_command('seed_events', verbosity=0)
        self.assertEqual(Event.objects.count(), first)
