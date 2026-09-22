"""`first_sentence` — the product-card excerpt filter — lives in core.

It began in book_product's `book_extras`, but the shared storefront card in
every theme uses it, and a store can disable the book vertical
(MORPHEUS_DISABLED_APPS). A book-plugin filter in a shared template 500s the
moment that plugin is off, so it moved to core (always loaded via `{% load
morph %}`). It also has to turn stored markup + entities into clean prose:
one live product's short_description is `<ul><li>…&#8217;s…</li></ul>`.
"""

from __future__ import annotations

from django.template import Context, Template
from django.test import SimpleTestCase

from core.templatetags.morph import first_sentence


class FirstSentenceTests(SimpleTestCase):
    def test_decodes_entities_and_strips_markup(self):
        raw = '<ul><li>So good we had to bring it back&#8230;</li><li>It&#8217;s been 5 years</li></ul>'
        out = first_sentence(raw)
        self.assertNotIn('&#', out)
        self.assertNotIn('<', out)
        self.assertIn('…', out)  # &#8230; -> ellipsis
        self.assertIn('It’s', out)  # &#8217; -> right single quote

    def test_double_escaped_copy_is_normalised(self):
        # some stored copy arrived pre-escaped, and template plumbing escapes again
        self.assertEqual(first_sentence('&lt;p&gt;A pitch&#x27;s end.&lt;/p&gt;'), "A pitch's end.")

    def test_takes_the_first_sentence(self):
        self.assertEqual(first_sentence('One. Two. Three.'), 'One.')

    def test_no_sentence_break_falls_back_to_capped_string(self):
        long = 'word ' * 60  # 300 chars, no . ! ?
        self.assertLessEqual(len(first_sentence(long)), 180)

    def test_none_and_blank_are_safe(self):
        self.assertEqual(first_sentence(None), '')
        self.assertEqual(first_sentence('   '), '')

    def test_registered_on_the_morph_library(self):
        rendered = Template('{% load morph %}{{ v|first_sentence }}').render(
            Context({'v': 'Hi&#8217;there. More.'})
        )
        self.assertEqual(rendered, 'Hi’there.')
