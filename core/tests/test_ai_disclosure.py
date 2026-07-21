"""EU AI Act Art. 50(1) — the core AI-disclosure tag is a legal floor.

The `{% ai_disclosure %}` tag must ALWAYS render a non-empty "you're talking to
an AI" label with a machine-readable marker, using the core default wording
unless a subscriber overrides it. It lives in core precisely so it can't vanish
when a plugin is toggled off — disabling a plugin must never create a
compliance gap.
"""

from __future__ import annotations

from django.template import Context, Template
from django.test import TestCase

from core.templatetags.morph import _AI_DISCLOSURE_DEFAULT


def _render(surface: str = 'ai_stylist') -> str:
    return Template("{% load morph %}{% ai_disclosure surface='" + surface + "' %}").render(
        Context()
    )


class AiDisclosureTagTests(TestCase):
    def test_default_wording_is_a_real_disclosure(self):
        # Guards against anyone blanking the legal floor.
        self.assertTrue(_AI_DISCLOSURE_DEFAULT.strip())
        self.assertIn('AI', _AI_DISCLOSURE_DEFAULT)

    def test_tag_renders_default_and_machine_readable_markers(self):
        html = _render('ai_stylist')
        # Human-visible disclosure text.
        self.assertIn('AI assistant', html)
        # Machine-readable markers for downstream/agent consumers.
        self.assertIn('data-ai-disclosure', html)
        self.assertIn('data-ai-surface="ai_stylist"', html)
        self.assertIn('role="note"', html)

    def test_tag_never_renders_empty(self):
        # Even with no surface arg, the disclosure must be present. (Assert on an
        # apostrophe-free fragment — format_html HTML-escapes the "You're".)
        html = _render('')
        self.assertIn('class="ai-disclosure"', html)
        self.assertIn('chatting with an AI assistant', html)
