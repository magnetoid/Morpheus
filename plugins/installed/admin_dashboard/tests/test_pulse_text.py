"""Linda's Pulse shows formatted text, never raw markdown, and never a script link.

The daily digest writes `**Orders yesterday:** 0`, and the home page printed the
asterisks. Insight text can come from a model, so the converter keeps only links a
browser cannot run (http, https, mailto, a path on this site).
"""

from __future__ import annotations

from django.test import SimpleTestCase

from core.templatetags.morph import markdown_to_html


class PulseMarkdownTests(SimpleTestCase):
    def test_bold_renders_as_bold(self):
        self.assertIn(
            '<strong>Orders yesterday:</strong> 0', markdown_to_html('**Orders yesterday:** 0')
        )

    def test_a_script_link_is_shown_as_text(self):
        html = markdown_to_html('[open](javascript:alert(1)) and [here](data:text/html,x)')
        self.assertNotIn('href="javascript', html)
        self.assertNotIn('href="data', html)
        self.assertIn('open', html)

    def test_site_and_web_links_still_work(self):
        html = markdown_to_html('[analytics](/dashboard/analytics/) [docs](https://example.com/x)')
        self.assertIn('href="/dashboard/analytics/"', html)
        self.assertIn('href="https://example.com/x"', html)
