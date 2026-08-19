"""The redirect engine's contract.

Redirects are the one SEO feature whose failure is *loud* for a visitor and
*silent* for the merchant: a rule that never fires just looks like a 404, and a
rule that fires wrongly sends people somewhere they did not ask for. Every case
below is a way that has actually happened somewhere.
"""

from __future__ import annotations

from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from plugins.installed.seo.models import Redirect, SiteSeoSettings
from plugins.installed.seo.services.redirects import (
    collapse_chain,
    export_redirects_csv,
    import_redirects_csv,
    normalise_path,
    resolve_redirect,
    validate_redirect,
)


class PrecedenceTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_exact_beats_prefix_and_prefix_beats_regex(self):
        """The whole reason match types are ordered.

        A broad prefix rule added first must not swallow the specific rule the
        merchant adds afterwards — the failure mode is a page quietly serving
        the wrong destination, with nothing anywhere to indicate why.
        """
        Redirect.objects.create(
            from_path='/books/', to_path='/shop/', match_type=Redirect.MATCH_PREFIX
        )
        Redirect.objects.create(
            from_path=r'^/books/.*$', to_path='/catalogue/', match_type=Redirect.MATCH_REGEX
        )
        Redirect.objects.create(
            from_path='/books/dune/', to_path='/products/dune/', match_type=Redirect.MATCH_EXACT
        )

        self.assertEqual(resolve_redirect('/books/dune/'), ('/products/dune/', 301))
        # No exact rule for this one → the prefix rule, carrying the remainder.
        self.assertEqual(resolve_redirect('/books/sci-fi/')[0], '/shop/sci-fi/')

    def test_longest_prefix_wins(self):
        Redirect.objects.create(
            from_path='/books/', to_path='/shop/', match_type=Redirect.MATCH_PREFIX
        )
        Redirect.objects.create(
            from_path='/books/fiction/', to_path='/fiction/', match_type=Redirect.MATCH_PREFIX
        )
        self.assertEqual(resolve_redirect('/books/fiction/dune/')[0], '/fiction/dune/')

    def test_regex_rule_can_capture_and_expand(self):
        Redirect.objects.create(
            from_path=r'^/old/(?P<rest>.*)$',
            to_path=r'/new/\g<rest>',
            match_type=Redirect.MATCH_REGEX,
        )
        self.assertEqual(resolve_redirect('/old/thing/')[0], '/new/thing/')

    def test_an_invalid_regex_costs_only_its_own_rule(self):
        """A merchant can type a broken pattern; every other request must live."""
        Redirect.objects.create(from_path='/a(/', to_path='/b/', match_type=Redirect.MATCH_REGEX)
        Redirect.objects.create(
            from_path='/works/', to_path='/fine/', match_type=Redirect.MATCH_EXACT
        )
        self.assertEqual(resolve_redirect('/works/'), ('/fine/', 301))

    def test_410_resolves_with_no_target(self):
        Redirect.objects.create(from_path='/gone/', to_path='', status_code=410)
        self.assertEqual(resolve_redirect('/gone/'), ('', 410))


class NormalisationTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_a_pasted_full_url_still_matches_the_path(self):
        """Merchants paste what their analytics gave them, which is a full URL."""
        r = Redirect.objects.create(
            from_path='https://example.test/old/?utm_source=x', to_path='/new/'
        )
        self.assertEqual(r.from_path, '/old/')
        self.assertEqual(resolve_redirect('/old/'), ('/new/', 301))

    def test_a_bare_slug_gets_a_leading_slash(self):
        self.assertEqual(normalise_path('old-page/'), '/old-page/')

    def test_a_regex_rule_is_not_normalised(self):
        """Normalising a pattern would eat the anchors that make it work."""
        r = Redirect.objects.create(
            from_path=r'^/old/(.*)$', to_path='/new/', match_type=Redirect.MATCH_REGEX
        )
        self.assertEqual(r.from_path, r'^/old/(.*)$')


class ChainTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_a_chain_is_collapsed_on_write(self):
        """A→B→C costs crawl budget and loses a little authority per hop, and it
        accumulates without anyone deciding it should — rename a product twice."""
        Redirect.objects.create(from_path='/a/', to_path='/b/')
        Redirect.objects.create(from_path='/b/', to_path='/c/')
        second = Redirect.objects.create(from_path='/x/', to_path='/a/')
        self.assertEqual(second.to_path, '/c/')

    def test_a_cycle_is_left_alone_rather_than_followed_forever(self):
        """Following A→B→A would spin; the merchant's own value is returned
        untouched so they can see and fix what they wrote."""
        Redirect.objects.create(from_path='/a/', to_path='/b/')
        Redirect.objects.create(from_path='/b/', to_path='/a/')
        self.assertEqual(collapse_chain('/start/', '/a/'), '/a/')


class ValidationTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_a_self_redirect_is_refused(self):
        problems = validate_redirect(from_path='/a/', to_path='/a/', status_code=301)
        self.assertTrue(any('itself' in p for p in problems))

    def test_redirecting_to_the_homepage_is_refused_by_default(self):
        """Bulk-redirecting dead URLs to / reads as a soft 404 and loses the
        page rather than moving it."""
        problems = validate_redirect(from_path='/a/', to_path='/', status_code=301)
        self.assertTrue(problems)

    def test_the_homepage_guard_can_be_turned_off(self):
        SiteSeoSettings.objects.create(block_homepage_redirects=False)
        problems = validate_redirect(from_path='/a/', to_path='/', status_code=301)
        self.assertEqual(problems, [])

    def test_a_410_needs_no_target(self):
        self.assertEqual(validate_redirect(from_path='/a/', to_path='', status_code=410), [])


class CacheInvalidationTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_editing_a_rule_takes_effect_immediately(self):
        """The resolver reads a cached ruleset. A merchant who edits a rule and
        watches the old one keep serving concludes the feature is broken."""
        row = Redirect.objects.create(from_path='/a/', to_path='/b/')
        self.assertEqual(resolve_redirect('/a/')[0], '/b/')  # populates the cache
        row.to_path = '/c/'
        row.save()
        self.assertEqual(resolve_redirect('/a/')[0], '/c/')

    def test_deleting_a_rule_stops_it_serving(self):
        row = Redirect.objects.create(from_path='/a/', to_path='/b/')
        self.assertIsNotNone(resolve_redirect('/a/'))
        row.delete()
        self.assertIsNone(resolve_redirect('/a/'))


class CsvTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_import_round_trips_and_reports_bad_rows(self):
        """A 500-row migration from another platform always has a few malformed
        lines; losing the other 495 over them helps nobody."""
        result = import_redirects_csv(
            'from_path,to_path,status_code,match_type,note\n'
            '/one/,/uno/,301,exact,first\n'
            '/two/,/two/,301,exact,self-redirect\n'
            '/three/,,410,exact,gone\n'
        )
        self.assertEqual(result['created'], 2)
        self.assertEqual(result['skipped'], 1)
        self.assertTrue(result['errors'])
        self.assertEqual(resolve_redirect('/one/'), ('/uno/', 301))
        self.assertEqual(resolve_redirect('/three/'), ('', 410))
        self.assertIn('/one/', export_redirects_csv())


@override_settings(LANGUAGES=[('en', 'English'), ('fr', 'French')])
class MiddlewareBehaviourTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_the_query_string_survives_the_redirect(self):
        """Dropping ?utm_source breaks campaign attribution for every link that
        was ever shared."""
        Redirect.objects.create(from_path='/old/', to_path='/new/')
        response = self.client.get('/old/', {'utm_source': 'newsletter'})
        self.assertEqual(response.status_code, 301)
        self.assertIn('utm_source=newsletter', response['Location'])

    def test_an_off_site_destination_is_refused(self):
        """`to_path` is staff- AND assistant-writable and went straight into a
        Location header: an open redirect turns the store into a phishing hop."""
        Redirect.objects.create(from_path='/evil/', to_path='https://evil.example/')
        response = self.client.get('/evil/')
        self.assertNotEqual(response.status_code, 301)

    def test_a_410_rule_returns_gone(self):
        Redirect.objects.create(from_path='/discontinued/', to_path='', status_code=410)
        self.assertEqual(self.client.get('/discontinued/').status_code, 410)

    def test_a_language_prefixed_request_matches_an_unprefixed_rule(self):
        """LocaleMiddleware leaves /fr/ in path_info, so a rule stored as
        /old/ never fired for anyone browsing in another language."""
        Redirect.objects.create(from_path='/old/', to_path='/new/')
        response = self.client.get('/fr/old/')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], '/fr/new/')

    def test_the_dashboard_is_never_redirected(self):
        Redirect.objects.create(from_path='/dashboard/products/', to_path='/nope/')
        self.assertNotEqual(self.client.get('/dashboard/products/').status_code, 301)
