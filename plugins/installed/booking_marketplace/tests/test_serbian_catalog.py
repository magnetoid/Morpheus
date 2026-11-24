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

import re
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

from django.conf import settings
from django.template import engines
from django.templatetags.i18n import BlockTranslateNode, TranslateNode
from django.test import Client, SimpleTestCase, TestCase
from django.utils.translation import trans_real, trim_whitespace
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.tests._i18n import serbian_enabled
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin

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


# -- the pages as a visitor gets them ---------------------------------------
_LATIN = re.compile(r'[A-Za-z]{3}')
_CYRILLIC = re.compile('[Ѐ-ӿ]')
_SHOWN_ATTRS = ('placeholder', 'aria-label', 'title', 'alt')
# Text that reads the same in both languages: names, the brand, the switcher.
_SAME_IN_BOTH = {
    'Montenegro Experience',
    'montenegro',  # the logo's wordmark
    'experience',
    'Morpheus Store',  # the test store's name
    'Blog',
    'Hotel',
    'Hostel',
    'Podgorica',
    '€ EUR',
    'EUR',
    # Blocks of apps the travel stores switch off (MORPHEUS_DISABLED_APPS), on in tests.
    '🌱 Book footprint',  # eco_impact
    '3D store',  # bookstore_3d
}
# Never read: hidden, or not shown as page text (the head's <link title>s).
_UNREAD = ('head', 'script', 'style', 'noscript', 'template')


class _Text(HTMLParser):
    """The text a visitor reads, minus what is marked as another language.

    A citation of an English article keeps its English title, marked `lang="en"`,
    and the switcher names each language in its own; neither is untranslated.
    """

    def __init__(self, language: str):
        super().__init__()
        self.language = language
        self.found: list[str] = []
        self._skip = 0
        self._foreign: list[str] = []

    def handle_starttag(self, tag, attrs):
        if self._foreign and tag == self._foreign[0]:
            self._foreign.append(tag)
        if tag in _UNREAD:
            self._skip += 1
        attrs = dict(attrs)
        lang = (attrs.get('lang') or '').lower()
        if lang and lang != self.language and not self._foreign:
            self._foreign = [tag]
        if self._skip or self._foreign:
            return
        for name in _SHOWN_ATTRS:
            value = (attrs.get(name) or '').strip()
            if value:
                self.found.append(value)

    def handle_endtag(self, tag):
        if tag in _UNREAD and self._skip:
            self._skip -= 1
        if self._foreign and tag == self._foreign[0]:
            self._foreign.pop()

    def handle_data(self, data):
        if not self._skip and not self._foreign and data.strip():
            self.found.append(' '.join(data.split()))


def _texts(response, language: str) -> list[str]:
    parser = _Text(language)
    parser.feed(response.content.decode('utf-8'))
    return parser.found


@serbian_enabled
class SerbianPagesTests(MontenegroThemeMixin, TestCase):
    """What a visitor on `/sr/` reads is Serbian, in Latin script.

    The catalog test above reads only this app's and the theme's templates, while a
    page also renders other apps' blocks: the cookie banner, the support chat, the
    legal footer, the language switcher, the story card. Each of those wrote its
    English straight into the markup, so `/sr/` showed it on every page with the
    whole suite green. These render the pages in both languages and compare: a
    string the English page shows and the Serbian page shows too is either a
    store's own content (the fixtures below) or a string nobody translated.

    Django's own `sr` catalog is Cyrillic, so `|date` month names and the language
    names read "окт." and "енглески" on a Latin page; the store's catalog
    overrides them.
    """

    maxDiff = None

    PATHS = (
        '/',
        '/bookings/',
        '/bookings/zeta-kajak/',
        '/hotels/',
        '/hotels/zeta-hotel/',
        '/places/',
        '/places/zeta-mjesto/',
        '/events/',
        '/events/zeta-festival/',
        '/regions/',
        '/vendors/',
        '/vendor/zeta-tura/',
        '/marketplace/',
        '/journal/',
        '/about/',
        '/contact/',
        '/shipping/',
        '/returns/',
        '/cart/',
        '/investors/',
        '/no-such-page/',
    )

    @classmethod
    def setUpTestData(cls):
        from plugins.installed.booking_marketplace.models import (
            REGIONS,
            Event,
            Place,
            Property,
            RoomType,
        )
        from plugins.installed.catalog.models import Vendor

        region = REGIONS[0][0]
        vendor = Vendor.objects.create(name='Zeta Tura', slug='zeta-tura', is_active=True)
        BookableService.objects.create(
            vendor=vendor,
            name='Zeta Kajak',
            slug='zeta-kajak',
            location='Zeta Grad',
            region=region,
            price=Money(Decimal('50.00'), 'EUR'),
            is_active=True,
        )
        place = Place.objects.create(
            name='Zeta Mjesto', slug='zeta-mjesto', region=region, summary='Zeta sažetak'
        )
        hotel = Property.objects.create(
            vendor=vendor, name='Zeta Hotel', slug='zeta-hotel', region=region, location='Zeta Grad'
        )
        RoomType.objects.create(property=hotel, name='Zeta Soba', slug='zeta-soba')
        Event.objects.create(
            name='Zeta Festival',
            slug='zeta-festival',
            place=place,
            summary='Zeta ljeto',
            when_label='Zeta jul',
            month=7,
        )

    def _content_values(self) -> set[str]:
        """Every text the fixtures store: content shows as written in both languages."""
        from django.apps import apps

        values: set[str] = set()
        for label in ('booking_marketplace', 'catalog'):
            for model in apps.get_app_config(label).get_models():
                fields = [f.attname for f in model._meta.concrete_fields]
                for row in model.objects.values_list(*fields):
                    values.update(v for v in row if isinstance(v, str) and v.strip())
        return values

    def _leftovers(self, path: str) -> tuple[list[str], list[str]]:
        english = Client().get(path)
        serbian = Client().get('/sr' + path)
        self.assertIn(serbian.status_code, (200, 404), path)
        shown_in_english = set(_texts(english, 'en'))
        content = self._content_values() | _SAME_IN_BOTH
        same = [
            text
            for text in dict.fromkeys(_texts(serbian, 'sr'))
            if text in shown_in_english
            and _LATIN.search(text)
            and not any(value in text for value in content)
        ]
        cyrillic = [text for text in _texts(serbian, 'sr') if _CYRILLIC.search(text)]
        return same, cyrillic

    def test_no_english_and_no_cyrillic_on_a_serbian_page(self):
        problems = []
        for path in self.PATHS:
            same, cyrillic = self._leftovers(path)
            problems += [f'{path}: English {text[:90]!r}' for text in same]
            problems += [f'{path}: Cyrillic {text[:90]!r}' for text in cyrillic]
        self.assertEqual(problems, [], f'{len(problems)} strings left untranslated')

    def test_every_template_a_serbian_page_renders_is_translated(self):
        catalog = trans_real.translation('sr')._catalog
        engine = engines['django'].engine
        missing = set()
        for path in self.PATHS:
            response = Client().get('/sr' + path)
            for template in response.templates:
                origin = getattr(template, 'origin', None)
                name = getattr(origin, 'name', '') or ''
                if not name.endswith('.html') or '/django/' in name:
                    continue
                source = Path(name).read_text()
                for msgid, plural in _msgids(engine.from_string(source)):
                    key = (msgid, 0) if plural else msgid
                    if msgid and key not in catalog:
                        missing.add(f'{template.name}: {msgid[:80]!r}')
        self.assertEqual(sorted(missing), [], f'{len(missing)} strings without Serbian')


class DjangoStringsInLatinTests(SimpleTestCase):
    """Django's own Serbian (form errors, time spans, dates) reads in Latin script.

    Its `sr` catalog is Cyrillic: a booking form left empty said "Ово поље се мора
    попунити." on a page written in Latin, and `timesince` said "1 месец". The
    store's catalog gives each of those strings in Latin (`locale/sr`), and this
    fails when a Django upgrade brings one it does not cover.
    """

    def test_no_django_string_reads_in_cyrillic_on_a_serbian_page(self):
        import django
        from babel.messages.pofile import read_po

        catalog = trans_real.translation('sr')._catalog
        django_dir = Path(django.__file__).parent
        cyrillic = []
        for domain in ('conf/locale', 'contrib/humanize/locale'):
            with open(django_dir / domain / 'sr/LC_MESSAGES/django.po', 'rb') as f:
                for message in read_po(f):
                    if not message.id:
                        continue
                    msgid = message.id if isinstance(message.id, str) else message.id[0]
                    key = f'{message.context}\x04{msgid}' if message.context else msgid
                    values = (
                        [catalog.get(key)]
                        if isinstance(message.id, str)
                        else [catalog.get((key, n)) for n in range(3)]
                    )
                    if any(v and _CYRILLIC.search(v) for v in values):
                        cyrillic.append(msgid)
        self.assertEqual(cyrillic, [])

    def test_a_form_error_and_a_month_read_in_latin(self):
        import datetime

        from django import forms
        from django.template import Context, Template
        from django.utils import translation

        class Contact(forms.Form):
            email = forms.EmailField()

        with translation.override('sr'):
            errors = list(Contact({'email': 'nope'}).errors['email'])
            when = Template('{{ d|date:"D j F Y" }}').render(
                Context({'d': datetime.date(2026, 10, 3)})
            )
        self.assertEqual(errors, ['Unesite ispravnu e-mail adresu.'])
        self.assertEqual(when, 'sub. 3 oktobar 2026')
