"""Every core transactional email template can be found.

``core/emails/templates`` sat on no template loader path (``core.emails`` is
not an installed app), so every order email — placed, paid, shipped,
cancelled, refund, download links, welcome — was skipped with a "template
missing" warning on every store. The one test that sent a confirmation email
is skipped on SQLite, so nothing ever ran into it; this one always runs.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.template.loader import get_template
from django.test import SimpleTestCase

HANDLERS = Path(__file__).resolve().parents[1] / 'emails' / 'handlers.py'


class CoreEmailTemplatesTests(SimpleTestCase):
    def test_every_template_the_handlers_send_resolves(self):
        bases = sorted(set(re.findall(r"template_base='(emails/[a-z_]+)'", HANDLERS.read_text())))
        self.assertGreaterEqual(len(bases), 7)
        for base in bases:
            with self.subTest(base=base):
                get_template(f'{base}.txt')
                get_template(f'{base}.html')
