"""The search engine finds what a visitor types (booking_marketplace/search.py).

Pure Python, no database: documents go in, ranked keys come out. Live on 2026-10-14
every multi-word query found nothing, "zabljak" missed Žabljak, "kajak" and "kayac"
missed the kayak tours, and results came in the same order whatever was typed.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from plugins.installed.booking_marketplace import search
from plugins.installed.booking_marketplace.search import Doc, Index, fold, one_edit, parse_query


def _doc(key, name, *, location='', region='', description='', kind='experience'):
    return Doc(key, kind, ((10, name), (6, location), (6, region), (1, description)))


DOCS = [
    _doc(
        'kotor-kayak',
        'Sunset Kayak Tour on the Bay of Kotor',
        location='Kotor',
        region='Kotor Bay Boka Kotorska',
    ),
    _doc(
        'budva-kayak',
        'Kayak and Snorkel Tour to Sveti Nikola Island',
        location='Budva',
        region='Budva Riviera',
    ),
    _doc(
        'kotor-walk',
        'Kotor Old Town Walk',
        location='Kotor',
        region='Kotor Bay Boka Kotorska',
        description='Ends at the kayak harbour.',
    ),
    _doc('zabljak-hike', 'Durmitor Day Hike', location='Žabljak', region='Durmitor & the North'),
    _doc(
        'tara-zipline',
        'Zipline across the Tara Canyon',
        location='Đurđevića Tara',
        region='Durmitor & the North',
    ),
    _doc(
        'biking', 'Mountain Biking above Kolašin', location='Kolašin', region='Durmitor & the North'
    ),
    _doc('honey', 'Wild Mountain Honey', kind='product'),
    _doc('kotor-place', 'Kotor', region='Kotor Bay Boka Kotorska', kind='place'),
]


def _find(q, kind='experience', **kwargs):
    return Index(DOCS).find(parse_query(q), kind=kind, **kwargs)


def _ranked(q, **kwargs):
    found = _find(q, **kwargs)
    return sorted(found.scores, key=lambda key: (-found.scores[key], key))


class FoldTests(SimpleTestCase):
    def test_accents_case_and_cyrillic_fold_to_one_word(self):
        self.assertEqual(fold('Žabljak'), 'zabljak')
        self.assertEqual(fold('ŽABLJAK'), 'zabljak')
        self.assertEqual(fold('Жабљак'), 'zabljak')
        self.assertEqual(fold('Đurđevića Tara'), 'durdevica tara')
        self.assertEqual(fold('Herceg Novi’s fortress, 3-day'), 'herceg novis fortress 3 day')

    def test_a_word_with_dj_is_indexed_both_ways(self):
        self.assertEqual(search.index_tokens('Đurđevića'), {'durdevica', 'djurdjevica'})

    def test_one_edit(self):
        for a, b in (
            ('kayac', 'kayak'),
            ('hikng', 'hiking'),
            ('rafitng', 'rafting'),
            ('kayaks', 'kayak'),
        ):
            with self.subTest(a=a, b=b):
                self.assertTrue(one_edit(a, b))
        for a, b in (('kayak', 'kayak'), ('kotor', 'budva'), ('kayac', 'kayaking'), ('ab', 'cd')):
            with self.subTest(a=a, b=b):
                self.assertFalse(one_edit(a, b))


class QueryTests(SimpleTestCase):
    def test_stopwords_and_repeats_are_dropped(self):
        words = [term.text for term in parse_query('Kayak tours in the Bay of Kotor, kayak')]
        self.assertEqual(words, ['kayak', 'bay', 'kotor'])

    def test_store_wide_words_are_stopwords(self):
        self.assertEqual(parse_query('Experiences in Montenegro'), [])
        self.assertEqual(parse_query('izleti u Crnoj Gori'), [])

    def test_a_long_query_is_capped(self):
        terms = parse_query(' '.join(f'word{i}' for i in range(500)))
        self.assertEqual(len(terms), search.MAX_TERMS)
        self.assertLessEqual(sum(len(term.text) for term in terms), search.MAX_QUERY_CHARS)

    def test_synonyms_and_singulars_are_variants(self):
        (term,) = parse_query('kajaks')
        self.assertEqual(term.text, 'kajaks')
        self.assertIn('kajak', term.variants)
        self.assertIn('kayak', term.variants)


class MatchingTests(SimpleTestCase):
    def test_every_word_must_match_in_any_order(self):
        self.assertEqual(_ranked('kayak kotor'), ['kotor-kayak', 'kotor-walk'])
        self.assertEqual(_ranked('kotor kayak'), ['kotor-kayak', 'kotor-walk'])

    def test_a_name_match_ranks_above_a_description_match(self):
        ranked = _ranked('kayak')
        self.assertEqual(set(ranked[:2]), {'kotor-kayak', 'budva-kayak'})
        self.assertEqual(ranked[2:], ['kotor-walk'])

    def test_accents_and_cyrillic(self):
        for q in ('zabljak', 'Žabljak', 'Жабљак'):
            with self.subTest(q=q):
                self.assertEqual(_ranked(q), ['zabljak-hike'])

    def test_dj_is_read_both_ways(self):
        for q in ('durdevica', 'djurdjevica', 'Đurđevića'):
            with self.subTest(q=q):
                self.assertEqual(_ranked(q), ['tara-zipline'])

    def test_a_serbian_word_finds_the_english_listing(self):
        self.assertEqual(set(_ranked('kajak')), {'kotor-kayak', 'budva-kayak', 'kotor-walk'})

    def test_a_typo_and_a_prefix(self):
        self.assertEqual(set(_ranked('kayac')), {'kotor-kayak', 'budva-kayak', 'kotor-walk'})
        self.assertEqual(set(_ranked('kay')), {'kotor-kayak', 'budva-kayak', 'kotor-walk'})

    def test_a_word_that_matches_is_not_read_as_a_typo(self):
        # "hiking" is one letter from "biking"; its synonym "hike" matches, so no typo is tried.
        self.assertEqual(_ranked('hiking'), ['zabljak-hike'])

    def test_close_matches_when_no_listing_has_every_word(self):
        found = _find('kayak ulcinj')
        self.assertTrue(found.close)
        self.assertEqual(set(found.scores), {'kotor-kayak', 'budva-kayak', 'kotor-walk'})

    def test_no_close_matches_without_the_fallback(self):
        self.assertEqual(_find('kayak ulcinj', fallback=False), search.Matches({}, close=False))

    def test_nothing_to_search_for(self):
        self.assertIsNone(_find('the tour'))
        self.assertIsNone(_find('  ?!  '))

    def test_kind_and_within_restrict_the_keys(self):
        self.assertEqual(_ranked('honey'), [])
        self.assertEqual(sorted(_find('honey', kind='product').scores), ['honey'])
        self.assertEqual(sorted(_find('med', kind='product').scores), ['honey'])
        self.assertEqual(sorted(_find('kotor', kind='place').scores), ['kotor-place'])
        self.assertEqual(_ranked('kayak', within={'budva-kayak'}), ['budva-kayak'])

    def test_a_possessive_is_one_word(self):
        # "Kotor's" split into "kotor" + a required "s", which no listing had.
        index = Index(
            [
                _doc('walk', 'Kotor Old Town Walk', location='Kotor'),
                _doc('mausoleum', 'Njegoš’s Mausoleum on Lovćen', location='Lovćen'),
            ]
        )
        for q, key in (
            ("Kotor's old town", 'walk'),
            ('Njegoš’s mausoleum', 'mausoleum'),
            ('njegos mausoleum', 'mausoleum'),
        ):
            with self.subTest(q=q):
                found = index.find(parse_query(q), kind='experience')
                self.assertEqual((set(found.scores), found.close), ({key}, False))
