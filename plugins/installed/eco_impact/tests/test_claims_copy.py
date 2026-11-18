"""eco_impact's own copy makes no claim EU law bans (v0.178.0).

Directive (EU) 2024/825, from 27 September 2026, bans climate claims based on
offsetting and generic environmental claims. The app used to offer to "offset this
order's footprint", count "kg CO2 offset" on its public page and call that page "Save
the planet". Every shopper-facing surface now passes the same check the site scan
runs (seo's green_claims), the footprint reads as an estimate that links to its
method, and a tree is a pledge to plant, never an offset of the order.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase

from plugins.installed.seo.services.green_claims import Matcher

TEMPLATES = Path(__file__).resolve().parent.parent / 'templates' / 'eco_impact'
BLOCKS = ('blocks/pdp_badge.html', 'blocks/cart_optin.html', 'blocks/footer_link.html')


def _shown(source: str) -> str:
    """What a shopper reads in a template: no comments, template tags or markup."""
    source = re.sub(r'{%\s*comment\s*%}.*?{%\s*endcomment\s*%}', ' ', source, flags=re.S)
    source = re.sub(r'{#.*?#}|{%.*?%}|{{.*?}}', ' ', source, flags=re.S)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', source)).strip()


class ShopperCopyTests(TestCase):
    def test_no_block_makes_a_banned_claim_or_offers_an_offset(self):
        for name in BLOCKS:
            with self.subTest(block=name):
                text = _shown((TEMPLATES / name).read_text())
                self.assertEqual(Matcher().find(text), [], text)
                self.assertNotIn('offset', text.lower())
                self.assertNotIn('save the planet', text.lower())

    def test_the_badge_is_an_estimate_that_links_to_its_method(self):
        source = (TEMPLATES / 'blocks/pdp_badge.html').read_text()
        self.assertIn('estimate', _shown(source).lower())
        self.assertIn('/save-the-planet/#method', source)

    def test_the_cart_offers_a_pledge(self):
        text = _shown((TEMPLATES / 'blocks/cart_optin.html').read_text())
        self.assertIn('tree-planting pledge', text.lower())
        self.assertIn('does not cancel out', text)

    def test_the_public_page_makes_no_banned_claim(self):
        for trees in (0, 3):
            totals = {'trees': trees, 'contributors': trees, 'co2_offset_kg': 63.0 * trees}
            with (
                self.subTest(trees=trees),
                patch(
                    'plugins.installed.eco_impact.views.services.store_totals',
                    return_value=totals,
                ),
            ):
                response = self.client.get('/save-the-planet/')
                self.assertEqual(response.status_code, 200)
                body = response.content.decode()
                start = body.index('Our books&rsquo; footprint')
                end = body.index('Browse books', start)
                page = html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', body[start:end])))
                self.assertEqual(Matcher().find(page), [], page)
                self.assertNotIn('offsets', page)
                self.assertNotIn('63', page)  # what the trees absorb stays on the dashboard
                self.assertIn('A pledge is not an offset', page)
                self.assertIn('estimates', page)
                self.assertIn('id="method"', body)
                self.assertIn('id="pledge"', body)
