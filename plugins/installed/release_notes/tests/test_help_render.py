"""A guide's Markdown as safe HTML, and as text for Linda and search."""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.release_notes.help_render import plain, readable, render
from plugins.registry import app_registry


class RenderTests(TestCase):
    def _html(self, body: str) -> str:
        return str(render(body, app='reviews'))

    def test_headings_paragraphs_and_lists(self):
        html = self._html(
            "## What it's for\n\nOne line\nand the next.\n\n- a\n- b\n\n1. first\n2. second\n\n### Detail"
        )
        self.assertIn('<h2>What it&#x27;s for</h2>', html)
        self.assertIn('<p>One line and the next.</p>', html)
        self.assertIn('<ul>\n<li>a</li>\n<li>b</li>\n</ul>', html)
        self.assertIn('<ol>\n<li>first</li>\n<li>second</li>\n</ol>', html)
        self.assertIn('<h3>Detail</h3>', html)

    def test_bold_code_and_outside_links(self):
        html = self._html('**Bold** and `code` and [Stripe](https://dashboard.stripe.com/apikeys).')
        self.assertIn('<strong>Bold</strong>', html)
        self.assertIn('<code>code</code>', html)
        self.assertIn(
            '<a href="https://dashboard.stripe.com/apikeys" rel="noopener" target="_blank">Stripe</a>',
            html,
        )

    def test_a_marker_becomes_a_link_to_the_live_place(self):
        self.assertIn(
            '<a href="/dashboard/reviews/">the Reviews tab</a>',
            self._html('Open [the Reviews tab](page:reviews).'),
        )

    def test_an_empty_marker_shows_the_live_label(self):
        self.assertIn(
            '<a href="/dashboard/reviews/">Products › Reviews</a>',
            self._html('Open [](page:reviews).'),
        )

    def test_a_marker_that_names_nothing_is_plain_text(self):
        html = self._html('See [the old page](page:gone).')
        self.assertIn('See the old page.', html)
        self.assertNotIn('<a', html)

    def test_a_place_in_an_app_that_is_off(self):
        app_registry.deactivate('reviews')
        self.addCleanup(app_registry.activate, 'reviews')
        self.assertIn(
            'the Reviews tab <span class="help-off">(when the app is on)</span>',
            self._html('Open [the Reviews tab](page:reviews).'),
        )

    def test_everything_else_is_escaped(self):
        html = self._html('<script>alert(1)</script> [x](javascript:alert(1)) & "quoted"')
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('href="javascript', html)
        self.assertIn('&amp; &quot;quoted&quot;', html)


class TextTests(TestCase):
    def test_plain_text_for_linda_names_the_paths(self):
        self.assertEqual(
            plain(
                '**Open** [the Reviews tab](page:reviews), then `Approve`. [Stripe](https://stripe.com).',
                app='reviews',
            ),
            'Open the Reviews tab (/dashboard/reviews/), then Approve. Stripe (https://stripe.com).',
        )

    def test_readable_text_for_search_has_no_paths(self):
        self.assertEqual(
            readable("## What it's for\n\nOpen [](page:reviews).", app='reviews'),
            "What it's for\n\nOpen Products › Reviews.",
        )
