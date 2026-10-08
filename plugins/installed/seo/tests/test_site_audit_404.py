"""What the site audit now checks about not-found handling and alternates (v0.80.0).

The October crawl found things the audit could not: a 404 page naming a
canonical and hreflang alternates, and every page's hreflang echoing whatever
query string the visitor arrived with. Each is invisible in a browser; the
merchant's dashboard is the only place they could surface.
"""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.seo.services import site_audit


def _codes(report) -> list[str]:
    return [f['code'] for f in report['findings']]


class NotFoundProbeTests(TestCase):
    def test_a_store_that_answers_missing_pages_correctly_is_not_flagged(self):
        report = site_audit.collect(limit=5)
        self.assertNotIn('missing_pages_answer_200', _codes(report))
        self.assertNotIn('error_page_names_a_url', _codes(report))
        self.assertEqual(report['not_found_probe']['status'], 404)

    def test_a_store_that_answers_200_for_anything_is_critical(self):
        facts = site_audit.NotFoundFacts(path='/x/', status=200)
        findings = site_audit._not_found_findings(facts)
        self.assertEqual([f.code for f in findings], ['missing_pages_answer_200'])

    def test_a_404_that_names_a_url_is_reported(self):
        facts = site_audit.NotFoundFacts(
            path='/x/',
            status=404,
            canonical='https://shop.test/x/',
            hreflangs=['en'],
            has_jsonld=True,
        )
        findings = site_audit._not_found_findings(facts)
        self.assertEqual([f.code for f in findings], ['error_page_names_a_url'])


class AlternateChecksTests(TestCase):
    def test_alternates_carrying_a_query_the_canonical_drops_are_reported(self):
        page = site_audit.PageFacts(
            path='/',
            status=200,
            canonical='https://shop.test/',
            hreflang_hrefs=[
                ('en', 'https://shop.test/?utm_source=mail'),
                ('sr', 'https://shop.test/sr/?utm_source=mail'),
            ],
        )
        codes = [f.code for f in site_audit._analyse([page])]
        self.assertIn('hreflang_not_canonical', codes)

    def test_a_sitemap_page_whose_canonical_names_another_url_is_reported(self):
        page = site_audit.PageFacts(path='/a/', status=200, canonical='https://shop.test/b/')
        codes = [f.code for f in site_audit._analyse([page])]
        self.assertIn('sitemap_canonical_elsewhere', codes)
