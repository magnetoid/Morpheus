"""core/text.py: plain text out of rich HTML or markdown, cut to fit (v0.163.0)."""

from __future__ import annotations

from django.test import SimpleTestCase

from core.text import body_images, clip, first_markdown_image, plain_text


class ClipTests(SimpleTestCase):
    def test_short_text_is_untouched(self):
        self.assertEqual(clip('  A short line.  ', 50), 'A short line.')

    def test_a_cut_ends_at_a_sentence(self):
        text = 'First sentence here. Second sentence is longer than the room.'
        self.assertEqual(clip(text, 40), 'First sentence here.')

    def test_else_at_a_word_with_an_ellipsis(self):
        out = clip('Montenegro has mountains rivers beaches and canyons everywhere', 30)
        self.assertLessEqual(len(out), 30)
        self.assertTrue(out.endswith('…'))
        self.assertTrue(out[:-1].endswith(('rivers', 'mountains', 'beaches')))


class PlainTextTests(SimpleTestCase):
    def test_markdown_markers_go(self):
        self.assertEqual(
            plain_text('## Head\n\n**Bold** and *it* with [a link](https://x.test) ![p](/a.jpg)'),
            'Head Bold and it with a link',
        )

    def test_html_blocks_end_words_and_entities_are_read(self):
        self.assertEqual(
            plain_text('<p>One</p><p>Two&nbsp;&amp;&nbsp;three</p><script>x()</script>'),
            'One Two & three',
        )


class ImageTests(SimpleTestCase):
    def test_first_markdown_image(self):
        self.assertEqual(first_markdown_image('text ![a](/m/1.jpg "t") ![b](/m/2.jpg)'), '/m/1.jpg')
        self.assertEqual(first_markdown_image('no picture'), '')

    def test_body_images_in_order_without_repeats(self):
        body = '![a](/m/1.jpg) <img alt="x" src="/m/2.jpg"> ![c](/m/1.jpg) <IMG src=\'/m/3.png\'>'
        self.assertEqual(body_images(body), ['/m/1.jpg', '/m/2.jpg', '/m/3.png'])
