"""A dashboard confirmation must stop the action until the merchant says yes.

Owner's report, 2026-10-11: the product page's Delete button deleted at once,
while a "Delete this product?" popup opened over a product that was already
gone. The dashboard body is `hx-boost`, and htmx's own submit listener on each
form ignores a submit event another listener cancelled: the confirm handler
called preventDefault(), htmx sent the POST anyway. The same held for all 28
forms that carry `data-confirm`, and the 19 submit buttons carrying it were
not read at all ("Update now", "Purge everything"), so they acted at once too.

The handler now stops the event in the capture phase, before htmx sees it, and
reads `data-confirm` from the clicked button as well as from the form. These
tests pin both halves, and check that every `data-confirm` in a template sits
where the handler reads it. The behaviour itself was checked in a browser.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

_ROOT = Path(settings.BASE_DIR)
_JS = _ROOT / 'plugins/installed/admin_dashboard/static/admin_dashboard/dashboard.js'
# type="button" controls that call Morph.confirm from their own script.
_OWN_HANDLER = {'plugins/installed/admin_dashboard/templates/admin_dashboard/theme_builder.html'}


def _function_body(src: str, name: str) -> str:
    start = src.index(f'function {name}(')
    end = src.index('\n  }\n', start)
    return src[start:end]


class ConfirmDialogContractTests(SimpleTestCase):
    def test_the_confirm_handler_stops_the_event_before_asking(self):
        body = _function_body(_JS.read_text(encoding='utf-8'), 'attachConfirmDelegation')
        self.assertIn("addEventListener('submit'", body)
        self.assertIn('}, true);', body)  # capture phase: ahead of htmx on the form
        self.assertLess(body.index('e.stopPropagation();'), body.index('Morph.confirm('))

    def test_a_confirm_on_the_clicked_button_is_read(self):
        body = _function_body(_JS.read_text(encoding='utf-8'), 'attachConfirmDelegation')
        self.assertIn("e.submitter.hasAttribute('data-confirm')", body)

    def test_an_ajax_save_marks_the_button_that_submitted(self):
        # Focus is no stand-in for the submitter: Safari never focuses a clicked
        # button, so a focused type="button" control (the category picker)
        # showed "Saving" and was disabled in place of Save.
        src = _JS.read_text(encoding='utf-8')
        self.assertIn('_submit(form, ev.submitter ||', src)

    def test_every_data_confirm_sits_where_the_handler_reads_it(self):
        misplaced = []
        for path in sorted(_ROOT.glob('plugins/**/templates/**/*.html')):
            rel = str(path.relative_to(_ROOT))
            src = path.read_text(encoding='utf-8', errors='ignore')
            for match in re.finditer(r'<(\w+)\b[^>]*?\sdata-confirm=', src, re.S):
                tag = match.group(1).lower()
                if tag == 'form':
                    continue
                if tag == 'button':
                    kind = re.search(r'\stype="(\w+)"', match.group(0))
                    if not kind or kind.group(1) == 'submit' or rel in _OWN_HANDLER:
                        continue
                misplaced.append(f'{rel}: <{tag}>')
        self.assertEqual(misplaced, [], 'data-confirm that nothing would ever ask about')

    def test_no_dashboard_form_asks_with_an_inline_confirm(self):
        # `onsubmit="return confirm(…)"` only cancels the event, and htmx sends a
        # boosted form whose submit was cancelled: until v0.99.0, Cancel still
        # deleted the redirect, sent the newsletter campaign or turned off
        # two-factor on 21 dashboard forms. Ask with data-confirm. Storefront
        # pages are not boosted, so their inline confirms work.
        inline = []
        for base in ('core', 'plugins'):
            for path in sorted((_ROOT / base).glob('**/templates/**/*.html')):
                rel = str(path.relative_to(_ROOT))
                if '/templates/storefront/' in rel:
                    continue
                src = path.read_text(encoding='utf-8', errors='ignore')
                if re.search(r'\sonsubmit="[^"]*confirm\(', src):
                    inline.append(rel)
        self.assertEqual(inline, [])
