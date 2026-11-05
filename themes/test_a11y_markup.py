"""Markup the live axe audit flagged on the storefronts.

`.github/workflows/accessibility.yml` runs axe-core against the four live stores
after every deploy. Its structural findings are guarded here, before a deploy,
by reading the templates and rendering the real pages:

* ``image-redundant-alt`` — a product card's cover sat inside the same link as
  the title with ``alt`` equal to that title, so a screen reader announced every
  product twice ("Peter Pan, Peter Pan"). Inside the card link the cover is
  decorative (``alt=""``); the link's accessible name is the title.
* ``aria-allowed-role`` — the home hero's panels were
  ``<article role="tabpanel">``, and ``article`` does not permit that role.
* ``select-name`` / ``label`` — a form control with no label is read out as
  "combo box" or "spin button" and nothing else (Montenegro's booking date, time
  and guests; its stay filters).
* ``heading-order`` — a heading one level deeper than the one before it at most
  (Montenegro's footer titles were ``h4`` under the page's ``h2``).
* ``landmark-unique`` — two ``<nav>`` without a name cannot be told apart.
* ``region`` — Irving's status bar sat outside every landmark.

Colour contrast is left to the live audit: it depends on the computed styles.
Montenegro's pages need the booking app, so its rendered checks live in
``booking_marketplace/tests/test_montenegro_a11y.py`` and reuse the readers here.
"""

from __future__ import annotations

import re
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from djmoney.money import Money

from themes.registry import theme_registry

_IMG = re.compile(r'<img\b[^>]*>', re.I)
_ALT = re.compile(r'\balt="([^"]*)"', re.I)
_TABPANEL_ARTICLE = re.compile(r'<article\b[^>]*role="tabpanel"', re.I)
_CARD = re.compile(r'<[a-z]+\b[^>]*\bdata-product-card\b[^>]*>', re.I)

_VOID = frozenset(
    {
        'area',
        'base',
        'br',
        'col',
        'embed',
        'hr',
        'img',
        'input',
        'link',
        'meta',
        'source',
        'track',
        'wbr',
    }
)
#: Inputs that carry their own name (a button's text or value) or none at all.
_UNLABELLED_INPUT_TYPES = frozenset({'hidden', 'submit', 'button', 'reset', 'image'})


class _PageOutline(HTMLParser):
    """Headings, form controls and navs of a rendered page, in document order.

    Anything under ``hidden``, ``aria-hidden="true"``, ``<template>`` or
    ``<noscript>`` is skipped, as axe skips it.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.headings: list[tuple[int, str]] = []
        self.controls: list[dict] = []
        self.label_for: set[str] = set()
        self.navs: list[dict] = []
        self._stack: list[tuple[str, bool]] = []
        self._heading: list | None = None

    def _hidden(self) -> bool:
        return any(hidden for _tag, hidden in self._stack)

    def handle_starttag(self, tag, attrs):
        a = {k: (v or '') for k, v in attrs}
        hidden = 'hidden' in a or a.get('aria-hidden') == 'true' or tag in ('template', 'noscript')
        in_label = any(t == 'label' for t, _h in self._stack)
        if not (hidden or self._hidden()):
            if tag == 'label' and a.get('for'):
                self.label_for.add(a['for'])
            elif tag in ('select', 'textarea') or (
                tag == 'input' and a.get('type', 'text').lower() not in _UNLABELLED_INPUT_TYPES
            ):
                self.controls.append({'tag': tag, 'attrs': a, 'in_label': in_label})
            elif tag == 'nav':
                self.navs.append(a)
            elif re.fullmatch(r'h[1-6]', tag):
                self._heading = [int(tag[1]), '']
                self.headings.append(self._heading)
        if tag not in _VOID:
            self._stack.append((tag, hidden))

    def handle_endtag(self, tag):
        if re.fullmatch(r'h[1-6]', tag):
            self._heading = None
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                del self._stack[i:]
                break

    def handle_data(self, data):
        if self._heading is not None:
            self._heading[1] += data


def _outline(html: str) -> _PageOutline:
    parser = _PageOutline()
    parser.feed(html)
    return parser


def heading_skips(html: str) -> list[str]:
    """Each heading that goes more than one level deeper than the one before it."""
    out, previous = [], None
    for level, text in _outline(html).headings:
        if previous is not None and level > previous + 1:
            out.append(f'h{previous} → h{level} "{" ".join(text.split())[:60]}"')
        previous = level
    return out


def unlabelled_controls(html: str) -> list[str]:
    """Each select, textarea or input with no name: no label (wrapped or by ``for``), no
    ``aria-label``, no ``title`` and, for a text field, no placeholder (as axe reads it)."""
    page = _outline(html)
    out = []
    for c in page.controls:
        a = c['attrs']
        if c['in_label'] or a.get('aria-label', '').strip() or a.get('aria-labelledby'):
            continue
        # axe takes a title, and for a text field a placeholder, as the name.
        if a.get('title', '').strip() or (
            c['tag'] != 'select' and a.get('placeholder', '').strip()
        ):
            continue
        if a.get('id') and a['id'] in page.label_for:
            continue
        out.append(f'<{c["tag"]} name="{a.get("name", "")}" type="{a.get("type", "")}">')
    return out


def unnamed_navs(html: str) -> list[dict]:
    """The ``<nav>`` elements without a name; more than one cannot be told apart."""
    return [a for a in _outline(html).navs if not (a.get('aria-label') or a.get('aria-labelledby'))]


# ── Templates ─────────────────────────────────────────────────────────────────

_THEMES = Path(settings.BASE_DIR) / 'themes' / 'library'
#: App templates a shopper sees that are not a theme's: the review form under a
#: product, the booking page's fallback, the affiliate application, CMS forms.
_STOREFRONT_APP_TEMPLATES = (
    'plugins/installed/reviews/templates/reviews/blocks/write_review.html',
    'plugins/installed/booking_marketplace/templates/booking_marketplace/detail.html',
    'plugins/installed/affiliates/templates/affiliates/_apply_form.html',
    'plugins/installed/cms/templates/cms/_form.html',
)
_SELECT = re.compile(r'<select\b([^>]*)>', re.I | re.S)
_NAV = re.compile(r'<nav\b([^>]*)>', re.I | re.S)
_LABEL_FOR = re.compile(r'<label\b[^>]*\bfor="([^"]+)"', re.I)
_ID = re.compile(r'\bid="([^"]+)"', re.I)
_NAMED = re.compile(r'\baria-label(?:ledby)?="[^"]', re.I)
_COMMENT = re.compile(r'{% comment %}.*?{% endcomment %}|{#.*?#}|<!--.*?-->', re.S)


def _strip_comments(text: str) -> str:
    """Blank out template and HTML comments, keeping line numbers."""
    return _COMMENT.sub(lambda m: '\n' * m.group(0).count('\n'), text)


def _storefront_templates():
    yield from sorted(_THEMES.glob('*/templates/**/*.html'))
    for rel in _STOREFRONT_APP_TEMPLATES:
        yield Path(settings.BASE_DIR) / rel


class TemplateLabelTests(SimpleTestCase):
    """Read every storefront template, so a control nothing renders in a test is covered too."""

    def test_every_select_has_a_label(self):
        missing = []
        for path in _storefront_templates():
            text = _strip_comments(path.read_text(encoding='utf-8'))
            fors = set(_LABEL_FOR.findall(text))
            for m in _SELECT.finditer(text):
                attrs = m.group(1)
                if _NAMED.search(attrs):
                    continue
                ident = _ID.search(attrs)
                if ident and ident.group(1) in fors:
                    continue
                before = text[: m.start()]
                if before.rfind('<label') > before.rfind('</label>'):
                    continue  # wrapped in its label
                line = before.count('\n') + 1
                missing.append(f'{path.relative_to(settings.BASE_DIR)}:{line}')
        self.assertEqual(missing, [], 'a <select> needs aria-label, or an id its <label for> names')

    def test_every_theme_nav_has_a_name(self):
        missing = []
        for path in sorted(_THEMES.glob('*/templates/**/*.html')):
            text = _strip_comments(path.read_text(encoding='utf-8'))
            for m in _NAV.finditer(text):
                if not _NAMED.search(m.group(1)):
                    line = text[: m.start()].count('\n') + 1
                    missing.append(f'{path.relative_to(settings.BASE_DIR)}:{line}')
        self.assertEqual(
            missing, [], 'a theme <nav> needs aria-label (header, drawer, breadcrumb…)'
        )


# ── Rendered pages ────────────────────────────────────────────────────────────


class _ThemeA11yTests:
    """Rendered under one theme; mixed into a TestCase per theme below."""

    theme = ''
    hero_tabs = False

    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import Category, Product, ProductImage

        category = Category.objects.create(name='A11y Category', slug='a11y-cat')
        for i in (1, 2):
            product = Product.objects.create(
                name=f'A11y Probe {i}',
                slug=f'a11y-probe-{i}',
                sku=f'A11Y-{i}',
                price=Money(Decimal('9.00'), 'USD'),
                product_type='simple',
                status='active',
                is_featured=True,
                category=category,
            )
            # A stored path is enough: the card renders the URL, never the bytes.
            ProductImage.objects.create(
                product=product, image=f'products/a11y-probe-{i}.jpg', is_primary=True
            )

    def setUp(self):
        cache.clear()
        override = override_settings(MORPHEUS_ACTIVE_THEME=self.theme)
        override.enable()
        self.addCleanup(override.disable)
        previous = theme_registry._active_name
        theme_registry.set_active(self.theme)
        self.addCleanup(setattr, theme_registry, '_active_name', previous)

    def _body(self, path):
        resp = self.client.get(path)
        self.assertEqual(resp.status_code, 200, path)
        return resp.content.decode()

    @staticmethod
    def _card_links(body: str) -> list[str]:
        """The hit link of every product card — cover and title share one <a>.

        Only an element carrying ``data-product-card`` starts a card: the cart
        drawer's script names the attribute in a selector too.
        """
        return [body[m.end() :].split('</a>', 1)[0] for m in _CARD.finditer(body)]

    def test_card_cover_is_decorative_inside_the_title_link(self):
        for path in ('/', '/products/'):
            with self.subTest(path=path):
                links = self._card_links(self._body(path))
                self.assertTrue(links, f'{path}: no product card rendered — fixture drift')
                covers = [img for link in links for img in _IMG.findall(link)]
                self.assertTrue(covers, f'{path}: no cover rendered in a card — fixture drift')
                for img in covers:
                    alt = _ALT.search(img)
                    self.assertIsNotNone(alt, f'{path}: cover has no alt attribute: {img}')
                    self.assertEqual(
                        alt.group(1), '', f'{path}: cover alt repeats the title: {img}'
                    )

    def test_hero_panels_use_an_element_that_permits_tabpanel(self):
        if not self.hero_tabs:
            self.skipTest(f'{self.theme} has no tabbed hero')
        body = self._body('/')
        self.assertIn('role="tabpanel"', body, 'hero did not render as tabs — fixture drift')
        self.assertIsNone(_TABPANEL_ARTICLE.search(body), '<article> does not permit role=tabpanel')

    def test_pages_name_every_control_and_nav_and_skip_no_heading_level(self):
        for path in (
            '/',
            '/products/',
            '/products/a11y-probe-1/',
            '/cart/',
            '/checkout/',
            '/checkout/quick/',
        ):
            with self.subTest(path=path):
                resp = self.client.get(path, follow=True)
                self.assertEqual(resp.status_code, 200, path)
                body = resp.content.decode()
                self.assertEqual(heading_skips(body), [], f'{path}: heading order')
                self.assertEqual(unlabelled_controls(body), [], f'{path}: unlabelled control')
                self.assertLessEqual(len(unnamed_navs(body)), 1, f'{path}: navs without a name')


class DotBooksA11yMarkupTests(_ThemeA11yTests, TestCase):
    theme = 'dot_books'
    hero_tabs = True


class SupernaturalA11yMarkupTests(_ThemeA11yTests, TestCase):
    theme = 'supernatural_shop'
    hero_tabs = True


class IrvingA11yMarkupTests(_ThemeA11yTests, TestCase):
    theme = 'irving_survival'

    def test_the_status_bar_is_a_landmark(self):
        body = self._body('/')
        self.assertIn('class="statusbar"', body, 'status bar did not render — fixture drift')
        self.assertRegex(body, r'<aside class="statusbar" aria-label="[^"]+"')
