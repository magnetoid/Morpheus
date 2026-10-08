"""Every string montenegro's pages mark for translation has a Serbian one (v0.80.1).

montenegro-experience.me serves `/sr/`, and 520-odd of the strings its theme
and this app wrap in `{% trans %}` had no Serbian entry: the booking form, the
stay page, sign-in, the footer and the account pages all rendered in English
under a Serbian URL. Nothing failed — a missing translation falls back to the
source text silently.

The templates are parsed with the real engine because that is what decides the
msgid: `makemessages` cuts `{% trans "…\\"…" %}` at the escaped quote, so a
check built on its output reports strings that are in fact translated.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.template import engines
from django.templatetags.i18n import BlockTranslateNode, TranslateNode
from django.test import SimpleTestCase
from django.utils.translation import trans_real, trim_whitespace

_ROOTS = (
    Path(settings.BASE_DIR) / 'themes' / 'library' / 'montenegro' / 'templates',
    Path(__file__).resolve().parents[1] / 'templates',
)


def _msgids(template):
    nodelist = template.nodelist
    for node in nodelist.get_nodes_by_type(TranslateNode):
        literal = getattr(node.filter_expression.var, 'literal', None)
        if literal is not None:
            yield str(literal).replace('%', '%%'), False
    for node in nodelist.get_nodes_by_type(BlockTranslateNode):
        msgid, _vars = node.render_token_list(node.singular)
        if node.trimmed:
            msgid = trim_whitespace(msgid)
        yield msgid, bool(node.plural and node.countervar)


class SerbianCatalogTests(SimpleTestCase):
    def test_every_translatable_string_has_a_serbian_translation(self):
        catalog = trans_real.translation('sr')._catalog
        engine = engines['django'].engine
        missing = []
        for root in _ROOTS:
            for path in sorted(root.rglob('*.html')):
                template = engine.from_string(path.read_text())
                for msgid, plural in _msgids(template):
                    key = (msgid, 0) if plural else msgid
                    if msgid and key not in catalog:
                        missing.append(f'{path.relative_to(root)}: {msgid[:80]!r}')
        self.assertEqual(missing, [], f'{len(missing)} strings without a Serbian translation')

    def test_the_booking_labels_are_translated(self):
        from django.utils import translation

        from plugins.installed.booking_marketplace import models

        same_in_serbian = {'Podgorica', 'Hotel', 'Hostel'}
        choice_lists = (
            models.REGIONS,
            models.PLACE_TYPES,
            models.PROPERTY_TYPES,
            models.EVENT_CATEGORIES,
        )
        for choices in choice_lists:
            for _key, label in choices:
                with translation.override('en'):
                    english = str(label)
                if english in same_in_serbian:
                    continue
                with translation.override('sr'), self.subTest(label=english):
                    self.assertNotEqual(str(label), english)
