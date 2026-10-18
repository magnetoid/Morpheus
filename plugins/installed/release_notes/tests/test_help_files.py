"""Every app ships a guide for store staff, in one shape.

A guide is plugins/installed/<app>/help.md, read by the Help area, Linda's help
tools and the Apps catalogue (plugins/app_help.py). These tests keep the guides
present and in one shape; test_help_markers.py keeps their links true.
Spec: docs/superpowers/specs/2026-10-18-help-system-design.md.
"""

from __future__ import annotations

import re

from django.test import SimpleTestCase

from plugins import app_help

#: Apps whose guide is still being written. Every guide removes its app; Task 11
#: of the plan deletes the set, and from then on every app must have a guide.
_AWAITING_A_GUIDE = frozenset(
    {
        'audiobooks',
        'b2b',
        'book_product',
        'bookvault',
        'cms',
        'digital_products',
        'gdpr',
        'inventory',
        'localization',
        'markets',
        'media',
        'media_3d',
        'motion',
        'product_gallery',
        'product_stories',
        'product_videos',
        'pwa',
        'rails',
        'reviews',
        'save_for_later',
        'shipping',
        'smart_shipping',
        'storefront',
        'tax',
        'trust_signals',
        'ugc_reviews',
        'webstories',
        'wishlist',
    }
)

_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
_SENTENCE_END = re.compile(r'[.!?](\s|$)')


def _guides():
    for app in app_help.tree_apps():
        found = app_help.guide(app)
        if found is not None:
            yield found


def _prose(body: str) -> str:
    """The guide as a reader reads it: marker targets and URLs taken out."""
    body = app_help.MARKER_RE.sub(lambda m: m.group(1), body)
    return re.sub(r'\(https://[^)\s]+\)', '', body)


class GuideCoverageTests(SimpleTestCase):
    def test_every_app_has_a_guide(self):
        missing = [
            a
            for a in app_help.tree_apps()
            if a not in _AWAITING_A_GUIDE and app_help.guide(a) is None
        ]
        self.assertEqual(missing, [], 'apps without plugins/installed/<app>/help.md')

    def test_an_app_with_a_guide_is_not_still_awaiting_one(self):
        stale = sorted(a for a in _AWAITING_A_GUIDE if app_help.guide(a) is not None)
        self.assertEqual(stale, [], 'remove these from _AWAITING_A_GUIDE')

    def test_every_awaiting_app_exists(self):
        self.assertEqual(sorted(_AWAITING_A_GUIDE - set(app_help.tree_apps())), [])


class GuideFormatTests(SimpleTestCase):
    def test_the_front_matter_is_one_summary_sentence(self):
        for g in _guides():
            with self.subTest(app=g.app):
                self.assertEqual(g.keys, ('summary',))
                self.assertTrue(g.summary, 'summary is empty')
                self.assertLessEqual(len(g.summary), app_help.SUMMARY_MAX)
                self.assertRegex(g.summary, r'[.!?]$', 'the summary ends a sentence')
                self.assertEqual(len(_SENTENCE_END.findall(g.summary)), 1, 'one sentence')
                self.assertNotRegex(g.summary, r'[*`\[\]<>#]', 'the summary is plain text')

    def test_headings_come_from_the_set_in_order(self):
        for g in _guides():
            with self.subTest(app=g.app):
                self.assertTrue(g.headings, 'a guide has headings')
                self.assertEqual(g.headings[0], app_help.HEADINGS[0])
                self.assertLessEqual(set(g.headings), set(app_help.HEADINGS), g.headings)
                order = [app_help.HEADINGS.index(h) for h in g.headings]
                self.assertEqual(order, sorted(set(order)), 'each heading once, in order')
                self.assertNotRegex(g.body, r'(?m)^#\s', 'no top-level heading')

    def test_the_body_is_60_to_400_words(self):
        low, high = app_help.BODY_WORDS
        for g in _guides():
            with self.subTest(app=g.app):
                words = len(_WORD.findall(_prose(g.body)))
                self.assertGreaterEqual(words, low)
                self.assertLessEqual(words, high)

    def test_no_developer_words(self):
        jargon = re.compile(r'\b(' + '|'.join(app_help.JARGON) + r')\b', re.I)
        for g in _guides():
            with self.subTest(app=g.app):
                self.assertEqual(jargon.findall(_prose(g.body)), [])

    def test_no_link_to_the_stores_own_pages(self):
        for g in _guides():
            with self.subTest(app=g.app):
                self.assertNotRegex(g.body, r'\]\((/|http://)', 'link with a marker, not a URL')
