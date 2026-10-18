"""Search across every installed app's help (the Help index's search box)."""

from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.installed.release_notes import help_search


class SearchTests(TestCase):
    def setUp(self):
        help_search.forget()
        self.addCleanup(help_search.forget)

    def _names(self, query: str) -> list[str]:
        return [hit['name'] for hit in help_search.search(query)]

    def test_a_word_in_a_guide_finds_its_app(self):
        hit = next(h for h in help_search.search('licence') if h['name'] == 'release_notes')
        self.assertIn('licence', hit['snippet'])

    def test_case_and_accents_fold(self):
        self.assertIn('release_notes', self._names('LICENCE'))
        self.assertIn('release_notes', self._names('licénce'))

    def test_every_word_must_match(self):
        self.assertNotIn('release_notes', self._names('licence qqqzzz'))

    def test_a_label_outranks_the_body(self):
        rows = [
            {'name': 'b', 'label': 'Beta', 'summary': '', 'headings': '', 'body': 'about refunds'},
            {'name': 'a', 'label': 'Refunds', 'summary': '', 'headings': '', 'body': ''},
        ]
        with mock.patch.object(help_search, '_index', return_value=rows):
            self.assertEqual(self._names('refunds'), ['a', 'b'])

    def test_a_snippet_starts_and_ends_on_whole_words(self):
        body = 'word ' * 60 + 'licence ' + 'more ' * 60
        rows = [{'name': 'a', 'label': 'A', 'summary': '', 'headings': '', 'body': body}]
        with mock.patch.object(help_search, '_index', return_value=rows):
            snippet = help_search.search('licence')[0]['snippet']
        words = snippet.strip('…').split()
        self.assertIn('licence', words)
        self.assertLessEqual(set(words), {'word', 'licence', 'more'}, snippet)

    def test_punctuation_is_just_text(self):
        for query in ('(', '*', '?', '[', ')', '\\'):
            with self.subTest(query=query):
                self.assertIsInstance(help_search.search(query), list)

    def test_an_empty_query_finds_nothing(self):
        self.assertEqual(help_search.search('   '), [])


class SearchPageTests(TestCase):
    def setUp(self):
        help_search.forget()
        self.addCleanup(help_search.forget)
        staff = get_user_model().objects.create_user(
            username='help-search', email='hs@example.test', password='pw', is_staff=True
        )
        self.client.force_login(staff)

    def test_results_lead_the_page(self):
        html = self.client.get('/dashboard/help/?q=licence').content.decode()
        results = html[html.index('data-help-results') :]
        self.assertIn(
            'href="/dashboard/help/release_notes/"', results[: results.index('</section>')]
        )

    def test_no_hits_says_so_and_keeps_the_index(self):
        html = self.client.get('/dashboard/help/?q=qqqzzz').content.decode()
        self.assertIn('No help mentions “qqqzzz”.', html)
        self.assertIn('data-help-area=', html)
