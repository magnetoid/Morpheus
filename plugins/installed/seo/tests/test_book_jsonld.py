"""Google Book structured data builder — Work → Edition → ReadAction.

Pure dict-in/dict-out (the PDP view assembles the dict), so these never touch
the ORM or a deferred field. Spec:
https://developers.google.com/search/docs/appearance/structured-data/book
"""

from django.test import TestCase

from plugins.installed.seo.services.jsonld import _to_isbn13, book_jsonld

_BASE = {
    'name': 'Utopia',
    'path': '/products/utopia/',
    'authors': ['Thomas More'],
    'isbn13': '978-0-14-044910-8',
    'book_format': 'paperback',
    'language': 'en',
    'date_published': '1516',
    'price': '8.00',
    'currency': 'USD',
}


class BookJsonldTests(TestCase):
    def test_work_and_edition_shape(self):
        d = book_jsonld(_BASE, base_url='https://shop.test/')
        self.assertEqual(d['@type'], 'Book')
        self.assertEqual(d['@id'], 'https://shop.test/products/utopia/#work')
        self.assertEqual(d['name'], 'Utopia')
        self.assertEqual(d['author'], {'@type': 'Person', 'name': 'Thomas More'})
        self.assertEqual(d['url'], 'https://shop.test/products/utopia/')
        ed = d['workExample']
        self.assertEqual(ed['@type'], 'Book')
        self.assertEqual(ed['isbn'], '9780140449108')
        self.assertEqual(ed['bookFormat'], 'https://schema.org/Paperback')
        self.assertEqual(ed['inLanguage'], 'en')
        self.assertEqual(ed['datePublished'], '1516')

    def test_read_action_offer(self):
        ed = book_jsonld(_BASE, base_url='https://shop.test/')['workExample']
        act = ed['potentialAction']
        self.assertEqual(act['@type'], 'ReadAction')
        self.assertEqual(act['target']['@type'], 'EntryPoint')
        self.assertEqual(act['target']['urlTemplate'], 'https://shop.test/products/utopia/')
        self.assertIn('https://schema.org/DesktopWebPlatform', act['target']['actionPlatform'])
        offer = act['expectsAcceptanceOf']
        self.assertEqual(offer['@type'], 'Offer')
        self.assertEqual(offer['category'], 'purchase')
        self.assertEqual(offer['eligibleRegion'], {'@type': 'Country', 'name': 'US'})
        self.assertEqual(offer['price'], '8.00')
        self.assertEqual(offer['priceCurrency'], 'USD')

    def test_multiple_authors(self):
        d = book_jsonld({**_BASE, 'authors': ['A. One', 'B. Two']}, base_url='https://shop.test/')
        self.assertEqual(
            d['author'],
            [{'@type': 'Person', 'name': 'A. One'}, {'@type': 'Person', 'name': 'B. Two'}],
        )

    def test_isbn10_is_converted_to_13(self):
        d = book_jsonld(
            {**_BASE, 'isbn13': None, 'isbn10': '0140449108'}, base_url='https://shop.test/'
        )
        isbn = d['workExample']['isbn']
        self.assertEqual(len(isbn), 13)
        self.assertTrue(isbn.startswith('978'))

    def test_isbn13_helper(self):
        self.assertEqual(_to_isbn13('978-0-14-044910-8', None), '9780140449108')
        # ISBN-10 → ISBN-13 recomputes the check digit (978 prefix, mod-10).
        self.assertEqual(_to_isbn13(None, '0140449108'), '9780140449105')
        self.assertIsNone(_to_isbn13(None, None))
        self.assertIsNone(_to_isbn13('garbage', None))

    def test_no_author_returns_empty(self):
        self.assertEqual(book_jsonld({**_BASE, 'authors': []}), {})
        self.assertEqual(book_jsonld({'name': '', 'authors': ['x']}), {})

    def test_non_dict_safe(self):
        self.assertEqual(book_jsonld(None), {})
