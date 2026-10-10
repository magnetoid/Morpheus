"""Story text is plain text, and a story says each thing once.

The bug (2026-10-10, live on three stores): a product's short description is
rich text from the editor, and the builder cut it raw — ``<p><span>A study of
alcohol…</span></p>`` — into the panels, so the story showed the tags as text
(``&lt;p&gt;``), in the captions, the image alt text and the meta description.
Supernatural's ``<ul><li>`` descriptions read as a wall of markup. The same
builder also put the same sentence on three pages (the cover, a page of its
own and the closing page).
"""

from __future__ import annotations

from django.test import SimpleTestCase

from plugins.installed.webstories.services import clip, extract, plain_text


class PlainTextTests(SimpleTestCase):
    def test_tags_go_and_entities_become_characters(self):
        self.assertEqual(
            plain_text('<p><span>A study of alcohol &amp; its place&nbsp;in life.</span></p>'),
            'A study of alcohol & its place in life.',
        )

    def test_paragraphs_and_list_items_keep_their_boundaries(self):
        html = '<p>Cold-pressed in Canada.</p><ul><li>Light</li><li>Non-greasy</li></ul>'
        self.assertEqual(plain_text(html), 'Cold-pressed in Canada. Light. Non-greasy.')
        text = extract(html)
        self.assertEqual(text.paragraphs, ['Cold-pressed in Canada.'])
        self.assertEqual(text.items, ['Light', 'Non-greasy'])

    def test_inline_tags_do_not_split_words(self):
        self.assertEqual(plain_text('Crambe <em>abyssinica</em> oil'), 'Crambe abyssinica oil')

    def test_scripts_and_styles_are_dropped(self):
        self.assertEqual(plain_text('<style>p{}</style><p>Kept</p><script>x()</script>'), 'Kept')

    def test_plain_text_input_keeps_its_paragraphs_and_bullets(self):
        text = extract('First line.\n\nSecond paragraph.\n- one\n- two')
        self.assertEqual(text.paragraphs, ['First line.', 'Second paragraph.'])
        self.assertEqual(text.items, ['one', 'two'])

    def test_empty_and_none(self):
        self.assertEqual(plain_text(''), '')
        self.assertEqual(plain_text(None), '')


class ClipTests(SimpleTestCase):
    def test_short_text_is_untouched(self):
        self.assertEqual(clip('Short.', 50), 'Short.')

    def test_cuts_at_a_sentence_end_when_one_is_close(self):
        text = 'The first sentence is here. The second one runs on for quite a while longer.'
        self.assertEqual(clip(text, 40), 'The first sentence is here.')

    def test_cuts_at_a_word_with_an_ellipsis(self):
        out = clip('abcdefgh ijklmnop qrstuvwx yz', 20)
        self.assertEqual(out, 'abcdefgh ijklmnop…')
        self.assertLessEqual(len(out), 20)

    def test_never_returns_half_an_entity_or_tag(self):
        out = clip(plain_text('<p>' + 'word ' * 60 + '</p>'), 30)
        self.assertNotIn('<', out)
        self.assertNotIn('&', out)
