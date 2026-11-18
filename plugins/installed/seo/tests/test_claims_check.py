"""The site audit lists environmental claims a page shows (v0.178.0).

Directive (EU) 2024/825 bans, from 27 September 2026, generic environmental claims
("eco-friendly") and climate claims based on offsetting ("climate neutral"). The
matcher must find each phrase in every language the stores write (English, Croatian,
Serbian in Latin and Cyrillic, with or without diacritics), stay quiet on a clean
page and on look-alikes ("offset printing"), and the audit must name the page and
the phrase, read the translated copies a page names in hreflang, and stop when the
merchant switches the check off.
"""

from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from plugins.installed.seo.services import site_audit
from plugins.installed.seo.services.green_claims import GENERIC, OFFSET, Matcher, matcher
from plugins.testing import set_app_settings

HOST = 'testserver'

PHRASES = {
    'en': [
        (GENERIC, 'Our eco-friendly packaging', 'eco-friendly'),
        (GENERIC, 'An environmentally friendly choice', 'environmentally friendly'),
        (GENERIC, "Nature's friend since 1990", "Nature's friend"),
        (GENERIC, 'Gentle on the environment', 'Gentle on the environment'),
        (GENERIC, 'A climate friendly tour', 'climate friendly'),
        (GENERIC, 'Fully biodegradable cups', 'biodegradable'),
        (GENERIC, 'An ecological product', 'ecological'),
        (GENERIC, 'Energy efficient lamps', 'Energy efficient'),
        (OFFSET, 'This store is climate neutral', 'climate neutral'),
        (OFFSET, 'CO₂-neutral delivery', 'CO₂-neutral'),
        (OFFSET, 'Carbon positive since 2020', 'Carbon positive'),
        (OFFSET, 'Climate compensated shipping', 'Climate compensated'),
        (OFFSET, 'Offset this order’s footprint', 'Offset this order’s footprint'),
        (OFFSET, 'We compensate CO2 emissions', 'compensate CO2 emissions'),
        (OFFSET, 'Net-zero by design', 'Net-zero'),
    ],
    'hr': [
        (GENERIC, 'Ekološki prihvatljiva ambalaža', 'Ekološki prihvatljiva'),
        (GENERIC, 'Proizvod prihvatljiv za okoliš', 'prihvatljiv za okoliš'),
        (GENERIC, 'Prijatelj prirode', 'Prijatelj prirode'),
        (GENERIC, 'Nježan prema okolišu', 'Nježan prema okolišu'),
        (GENERIC, 'Biorazgradivo pakiranje', 'Biorazgradivo'),
        (GENERIC, 'Energetski učinkovit uređaj', 'Energetski učinkovit'),
        (OFFSET, 'Klimatski neutralna dostava', 'Klimatski neutralna'),
        (OFFSET, 'Ugljično neutralan izlet', 'Ugljično neutralan'),
        (OFFSET, 'Kompenziramo emisije CO2', 'Kompenziramo emisije CO2'),
    ],
    'sr-Latn': [
        (GENERIC, 'Ekološki prihvatljiv proizvod', 'Ekološki prihvatljiv'),
        (GENERIC, 'Prihvatljiv za životnu sredinu', 'Prihvatljiv za životnu sredinu'),
        (GENERIC, 'Energetski efikasan bojler', 'Energetski efikasan'),
        (GENERIC, 'ekoloski prihvatljiva kesa', 'ekoloski prihvatljiva'),
        (OFFSET, 'Ugljenično neutralan smeštaj', 'Ugljenično neutralan'),
        (OFFSET, 'Klimatski pozitivna firma', 'Klimatski pozitivna'),
    ],
    'sr-Cyrl': [
        (GENERIC, 'Еколошки прихватљив производ', 'Еколошки прихватљив'),
        (GENERIC, 'Пријатељ природе', 'Пријатељ природе'),
        (GENERIC, 'Енергетски ефикасан уређај', 'Енергетски ефикасан'),
        (OFFSET, 'Угљенично неутралан смештај', 'Угљенично неутралан'),
        (OFFSET, 'Климатски неутрална достава', 'Климатски неутрална'),
    ],
}


class MatcherTests(SimpleTestCase):
    def test_each_language_finds_each_phrase_as_the_page_shows_it(self):
        found = Matcher()
        for language, cases in PHRASES.items():
            for kind, text, phrase in cases:
                with self.subTest(language=language, text=text):
                    hits = found.find(f'Intro words. {text}. Closing words.')
                    self.assertEqual([(h.kind, h.phrase) for h in hits], [(kind, phrase)])
                    self.assertIn(phrase, hits[0].snippet)

    def test_a_clean_page_is_silent(self):
        clean = (
            'Offset printing on 80 gsm paper. The Green Mile, a novel. Organic cotton, '
            'GOTS certified. Recycled paper. We compensate you for delays. Zelena kuća. '
            'Ekonomična dostava. Зелена трава.'
        )
        self.assertEqual(Matcher().find(clean), [])

    def test_a_phrase_is_reported_once_per_page(self):
        hits = Matcher().find('Eco-friendly bags. More eco friendly bags. Ecofriendly!')
        self.assertEqual(len(hits), 1)

    def test_an_offset_claim_is_not_also_a_generic_one(self):
        hits = Matcher().find('Our climate neutral and climate-friendly store')
        self.assertEqual(
            [(h.kind, h.phrase) for h in hits],
            [(OFFSET, 'climate neutral'), (GENERIC, 'climate-friendly')],
        )

    def test_the_merchants_own_words_are_looked_for_in_any_script(self):
        own = Matcher(['earth positive', 'zeleni izbor planete'])
        self.assertEqual([h.phrase for h in own.find('We are Earth-Positive.')], ['Earth-Positive'])
        self.assertEqual(
            [h.phrase for h in own.find('Зелени избор планете!')], ['Зелени избор планете']
        )
        self.assertEqual(Matcher(['', '  ']).find('nothing here'), [])

    def test_the_snippet_is_cut_at_words(self):
        text = 'word ' * 40 + 'our ecofriendly bag' + ' end' * 40
        snippet = Matcher().find(text)[0].snippet
        self.assertTrue(snippet.startswith('…word'), snippet)
        self.assertTrue(snippet.endswith('end…'), snippet)
        self.assertLess(len(snippet), 140)


class MatcherSettingTests(TestCase):
    def test_on_by_default(self):
        self.assertIsNotNone(matcher())

    def test_the_switch_turns_it_off(self):
        set_app_settings(self, 'seo', claims_check=False)
        self.assertIsNone(matcher())

    def test_extra_words_come_from_settings(self):
        set_app_settings(self, 'seo', claims_extra_words=['planet hero'])
        self.assertEqual([h.phrase for h in matcher().find('A planet hero bag')], ['planet hero'])


def _page(body: str, head: str = '', lang: str = 'en') -> str:
    return (
        f'<!doctype html><html lang="{lang}"><head><title>A page</title>{head}</head>'
        f'<body><h1>A page</h1>{body}<script>var x = "eco-friendly";</script>'
        '<style>/* climate neutral */</style></body></html>'
    )


def _finding(report, code) -> dict | None:
    return next((f for f in report['findings'] if f['code'] == code), None)


@override_settings(SITE_BASE_URL=f'https://{HOST}')
class AuditClaimsTests(TestCase):
    def setUp(self):
        cache.clear()

    def audit(self, pages: dict[str, str], copies: dict[str, str] | None = None) -> dict:
        copies = copies or {}

        def facts(client, path, host):
            return site_audit.page_facts(path, 200, pages[path], host)

        def body(extra, path, *, counter, cap):
            extra.counts[counter] += 1
            return (200, copies[path]) if path in copies else (404, '')

        with (
            patch.object(site_audit, '_paths', return_value=list(pages)),
            patch.object(site_audit, '_facts', side_effect=facts),
            patch.object(site_audit._Extra, 'body', autospec=True, side_effect=body),
        ):
            return site_audit.collect()

    def test_a_claim_names_the_page_and_the_phrase(self):
        report = self.audit(
            {
                '/green/': _page('<p>Our <b>eco-friendly</b> mugs.</p>'),
                '/neutral/': _page('<p>Shipping is climate neutral.</p>'),
                '/clean/': _page('<p>Mugs made of stoneware.</p>'),
            }
        )
        generic = _finding(report, 'environmental_claim_generic')
        offset = _finding(report, 'environmental_claim_offset')
        self.assertEqual(generic['severity'], 'notice')
        self.assertEqual(offset['severity'], 'warning')
        self.assertEqual(
            generic['examples'], ['/green/: “eco-friendly” in “A page Our eco-friendly mugs.”']
        )
        self.assertEqual(
            offset['examples'],
            ['/neutral/: “climate neutral” in “A page Shipping is climate neutral.”'],
        )

    def test_scripts_styles_and_a_clean_store_are_silent(self):
        report = self.audit({'/': _page('<p>Mugs.</p>'), '/b/': _page('<p>Plates.</p>')})
        self.assertIsNone(_finding(report, 'environmental_claim_generic'))
        self.assertIsNone(_finding(report, 'environmental_claim_offset'))

    def test_shared_copy_is_one_line(self):
        footer = '<footer>All our parcels are carbon neutral.</footer>'
        pages = {f'/p{i}/': _page(f'<p>Page {i}</p>{footer}') for i in range(5)}
        offset = _finding(self.audit(pages), 'environmental_claim_offset')
        self.assertEqual(offset['count'], 1)
        self.assertTrue(offset['examples'][0].startswith('“carbon neutral” on 5 pages'))

    def test_a_translated_copy_named_in_hreflang_is_read(self):
        head = (
            f'<link rel="alternate" href="https://{HOST}/tour/" hreflang="en">'
            f'<link rel="alternate" href="https://{HOST}/hr/tour/" hreflang="hr">'
            f'<link rel="alternate" href="https://{HOST}/tour/" hreflang="x-default">'
        )
        report = self.audit(
            {'/tour/': _page('<p>A boat tour.</p>', head=head)},
            copies={'/hr/tour/': _page('<p>Ekološki prihvatljiv izlet.</p>', lang='hr')},
        )
        generic = _finding(report, 'environmental_claim_generic')
        self.assertEqual(
            generic['examples'],
            ['/hr/tour/: “Ekološki prihvatljiv” in “A page Ekološki prihvatljiv izlet.”'],
        )
        self.assertEqual(report['checks']['translation_fetches'], 1)

    def test_switched_off_the_audit_reads_no_claims_and_no_copies(self):
        set_app_settings(self, 'seo', claims_check=False)
        head = f'<link rel="alternate" href="https://{HOST}/hr/a/" hreflang="hr">'
        report = self.audit(
            {'/a/': _page('<p>Eco-friendly and climate neutral.</p>', head=head)},
            copies={'/hr/a/': _page('<p>Klimatski neutralno.</p>')},
        )
        self.assertIsNone(_finding(report, 'environmental_claim_generic'))
        self.assertIsNone(_finding(report, 'environmental_claim_offset'))
        self.assertEqual(report['checks']['translation_fetches'], 0)


@override_settings(SITE_BASE_URL=f'https://{HOST}')
class TranslatedCopyFetchTests(TestCase):
    """`_Extra.body`, which the audit tests above replace, against the real URLconf."""

    def test_a_page_answers_with_its_html_a_missing_one_with_none_and_the_cap_holds(self):
        import time

        from django.test import Client

        extra = site_audit._Extra(client=Client(), host=HOST, deadline=time.monotonic() + 60)
        status, html = extra.body('/', counter='translation_fetches', cap=2)
        self.assertEqual(status, 200)
        self.assertIn('</head>', html)
        self.assertEqual(
            extra.body('/no-such-page-xyz/', counter='translation_fetches', cap=2), (404, '')
        )
        with self.assertRaises(site_audit._Capped):
            extra.body('/', counter='translation_fetches', cap=2)
        self.assertTrue(extra.capped['translation_fetches'])
