"""A `{# … #}` comment must fit on one line, or the page prints it.

Django's short comment syntax ends at the line break: a `{#` whose `#}` sits
on a later line is not a comment at all, so the visitor reads the template's
notes to itself. The product page of two themes shipped a note this way
("Facts near the CTA … Never a rate or a threshold this template cannot
know.") in the middle of the buy box; compiling the template does not catch
it, because to the engine it is ordinary text. Multi-line notes go in
`{% comment %}…{% endcomment %}`.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

_SKIP = {'.venv', 'node_modules', 'staticfiles', 'vendor', 'media', 'site', '.janus'}
_SHORT_COMMENT = re.compile(r'\{#(.*?)#\}', re.S)


class ShortCommentsStayOnOneLineTests(SimpleTestCase):
    def test_no_short_comment_spans_lines(self):
        offenders = []
        for path in Path(settings.BASE_DIR).rglob('*.html'):
            if _SKIP.intersection(path.parts):
                continue
            text = path.read_text(encoding='utf-8', errors='ignore')
            for match in _SHORT_COMMENT.finditer(text):
                if '\n' in match.group(1):
                    line = text[: match.start()].count('\n') + 1
                    offenders.append(f'{path.relative_to(settings.BASE_DIR)}:{line}')
        self.assertEqual(offenders, [], 'multi-line {# #} renders as text; use {% comment %}')
