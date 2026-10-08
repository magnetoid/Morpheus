"""The head contract a theme signs up to with `head_contract = 1`.

A theme cannot be trusted to keep SEO correct by inspection: the failure is
invisible in the browser. A page with two `<title>` elements looks perfect, a
page whose canonical points at the wrong URL looks perfect, and a theme that
quietly re-adds `<meta name="robots">` next to the kernel's looks perfect too —
right up until half the catalogue drops out of the index.

So every theme declaring the contract is rendered here, for each page kind, and
checked mechanically:

* exactly one `<title>`, one canonical, one robots meta, one JSON-LD block;
* no brand string hardcoded into the markup (it comes from settings);
* and with the seo app DISABLED the page still renders with exactly one title —
  the disable litmus test applied to the head.
"""

from __future__ import annotations

import re
from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.registry import app_registry
from themes.registry import theme_registry

_TITLE = re.compile(r'<title[^>]*>', re.I)
_CANONICAL = re.compile(r'<link[^>]+rel=["\']canonical["\']', re.I)
_ROBOTS = re.compile(r'<meta[^>]+name=["\']robots["\']', re.I)
_JSONLD = re.compile(r'<script[^>]+application/ld\+json', re.I)

_SLUG = 'head-contract-probe'


class HeadContractTests(TestCase):
    """Runs only when the active theme declares `head_contract >= 1`."""

    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import Category, Product
        from plugins.installed.cms.models import Page

        cls.category = Category.objects.create(name='Contract Category', slug=f'{_SLUG}-cat')
        cls.product = Product.objects.create(
            name='Head Contract Probe',
            slug=_SLUG,
            sku='HCP-1',
            price=Money(Decimal('9.00'), 'USD'),
            product_type='simple',
            status='active',
            category=cls.category,
            description='A product that exists so the contract test has a PDP to render.',
        )
        Page.objects.create(
            slug=f'{_SLUG}-post',
            title='Contract journal entry',
            state='published',
            publish_at=timezone.now() - timedelta(minutes=1),
            body='<p>An entry for the contract test.</p>',
            metadata={'category': 'journal'},
        )

    def setUp(self):
        cache.clear()
        theme = theme_registry.active
        if theme is None or getattr(theme, 'head_contract', 0) < 1:
            self.skipTest('active theme does not declare head_contract >= 1')
        self.theme = theme

    def _paths(self):
        return (
            '/',
            '/products/',
            f'/products/{_SLUG}/',
            f'/category/{_SLUG}-cat/',
            '/journal/',
            f'/journal/{_SLUG}-post/',
            '/about/',
            '/search/',
            '/cart/',
        )

    def test_each_page_emits_exactly_one_of_each_head_element(self):
        for path in self._paths():
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, path)
                body = response.content.decode()
                self.assertEqual(len(_TITLE.findall(body)), 1, f'{path}: <title> count')
                self.assertLessEqual(len(_CANONICAL.findall(body)), 1, f'{path}: canonical count')
                self.assertEqual(len(_ROBOTS.findall(body)), 1, f'{path}: robots meta count')
                self.assertLessEqual(len(_JSONLD.findall(body)), 1, f'{path}: JSON-LD block count')

    def test_private_pages_are_noindex_and_public_pages_are_not(self):
        public = self.client.get(f'/products/{_SLUG}/').content.decode()
        self.assertIn('index, follow', public)

        private = self.client.get('/cart/').content.decode()
        self.assertRegex(private, r'name=["\']robots["\'] content=["\']noindex, nofollow')

        # Internal search: crawl the links, don't index the query permutations.
        search = self.client.get('/search/').content.decode()
        self.assertRegex(search, r'name=["\']robots["\'] content=["\']noindex, follow')

    def test_the_theme_does_not_hardcode_the_brand_in_the_head(self):
        """The brand belongs in settings, not in markup.

        A theme that writes its own name into `<title>` cannot be used by a
        second merchant, which is the entire point of a theme.
        """
        brand_in_markup = re.compile(r'dot books', re.I)
        for path in ('/products/', f'/products/{_SLUG}/', '/about/'):
            with self.subTest(path=path):
                body = self.client.get(path).content.decode()
                head = body[: body.lower().find('</head>')]
                title = re.search(r'<title[^>]*>(.*?)</title>', head, re.I | re.S)
                self.assertIsNotNone(title, f'{path}: no title')
                # The brand may legitimately appear because the merchant CONFIGURED
                # it — what must not happen is the theme supplying it. In tests no
                # store name is configured, so any occurrence is hardcoded.
                self.assertIsNone(
                    brand_in_markup.search(title.group(1)),
                    f'{path}: theme hardcodes the brand in <title>: {title.group(1)!r}',
                )

    def test_head_survives_the_seo_app_being_disabled(self):
        """Disable litmus test, applied to the head.

        With the SEO app off the page loses its canonical and structured data —
        that is the app's surface disappearing, as it should — but it must still
        render, and still have exactly one title. A store that turns off SEO gets
        a plainer head, not a broken storefront.
        """
        self.assertTrue(app_registry.is_active('seo'))
        app_registry.deactivate('seo')
        cache.clear()
        try:
            for path in ('/', f'/products/{_SLUG}/', '/about/'):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200, f'{path} with seo disabled')
                    body = response.content.decode()
                    self.assertEqual(len(_TITLE.findall(body)), 1, f'{path}: <title> count')
                    self.assertNotIn('application/ld+json', body)
        finally:
            app_registry.activate('seo')
            cache.clear()


class EveryContractThemeTests(TestCase):
    """The contract must be checked for EVERY theme that signs it.

    `HeadContractTests` renders only the ACTIVE theme, so a second theme can
    declare `head_contract = 1` and never be looked at — which is what happened:
    montenegro signed the contract in v0.69.0 and went on shipping a 404 that
    carried two `<meta name="robots">`, because CI only ever runs with dot_books
    active. This needs no request cycle; it reads each theme's own templates for
    the tags the head document owns.
    """

    _OWNED = (
        (re.compile(r'<meta[^>]+name=["\']robots["\']', re.I), 'robots meta'),
        (re.compile(r'<link[^>]+rel=["\']canonical["\']', re.I), 'canonical link'),
    )
    # A Django comment may legitimately QUOTE the markup it is warning about.
    _COMMENTS = re.compile(r'{%\s*comment\s*%}.*?{%\s*endcomment\s*%}|{#.*?#}', re.S)

    @staticmethod
    def _is_amp(path) -> bool:
        """AMP pages are exempt: the spec REQUIRES each to carry its own
        `<link rel="canonical">` back to the non-AMP URL."""
        return path.stem.endswith('_amp') or path.stem.startswith('amp_')

    def test_no_contract_theme_hardcodes_a_tag_the_head_document_owns(self):
        import pathlib

        repo = pathlib.Path(__file__).resolve().parents[1]
        # The shared error templates render INSIDE whichever theme is active,
        # so they are bound by the same contract. `templates/404.html` used to
        # override `{% block seo %}` with its own <title> and robots meta,
        # which replaced the theme's entire head: no canonical, no Open Graph,
        # one store's brand on every other store, and the error-page `noindex`
        # rule could not reach it because the head document never ran.
        for shared in sorted((repo / 'templates').glob('*.html')):
            markup = self._COMMENTS.sub('', shared.read_text(errors='ignore'))
            if '<!DOCTYPE' in markup and '{% extends' not in markup:
                continue  # 500.html stands alone by design (empty context)
            for pattern, label in self._OWNED:
                with self.subTest(template=f'templates/{shared.name}'):
                    self.assertEqual(
                        pattern.findall(markup),
                        [],
                        f'templates/{shared.name} hardcodes a {label}; it renders '
                        'inside the active theme, so the head document owns it',
                    )

        root = repo / 'themes' / 'library'
        checked = 0
        for theme_dir in sorted(root.iterdir()):
            theme_py = theme_dir / 'theme.py'
            if not theme_py.is_file() or 'head_contract' not in theme_py.read_text():
                continue
            checked += 1
            for template in theme_dir.rglob('*.html'):
                if self._is_amp(template):
                    continue
                markup = self._COMMENTS.sub('', template.read_text(errors='ignore'))
                for pattern, label in self._OWNED:
                    with self.subTest(theme=theme_dir.name, template=template.name):
                        self.assertEqual(
                            pattern.findall(markup),
                            [],
                            f'{theme_dir.name}/{template.name} hardcodes a {label}; '
                            'the head document emits it (ADR 0036)',
                        )
        self.assertGreater(checked, 1, 'expected more than one contract theme to check')


def _activate_theme(testcase, name: str) -> None:
    """Render with theme `name` active; the previous VALUE is restored on cleanup.

    Both halves, as in booking_marketplace's mixin: `ThemeMiddleware` re-reads
    `MORPHEUS_ACTIVE_THEME` on every request, and a direct `get_template()`
    reads the registry. The registry is process-global, so the previous name is
    put back rather than assumed (CLAUDE.md: restore values, not removals).
    """
    from django.test import override_settings

    override = override_settings(MORPHEUS_ACTIVE_THEME=name)
    override.enable()
    testcase.addCleanup(override.disable)
    previous = theme_registry._active_name
    theme_registry.set_active(name)
    testcase.addCleanup(setattr, theme_registry, '_active_name', previous)
    cache.clear()


def _contract_themes() -> list[str]:
    """Every theme that signs the head contract and can run in this process."""
    names = []
    for theme in theme_registry.all_themes():
        if getattr(theme, 'head_contract', 0) < 1:
            continue
        if any(app_registry.get(app) is None for app in theme.requires_plugins):
            continue  # its vertical is not installed in this run
        names.append(theme.name)
    return sorted(names)


class ErrorHeadEveryThemeTests(TestCase):
    """A 404 names no URL and describes no entity — under EVERY contract theme.

    The live 404s of all three stores carried a self-canonical, `og:url`,
    hreflang alternates pointing at the dead URL and a WebPage graph, beside a
    correct `noindex`. The default-theme render was the only one any test ever
    looked at; montenegro's own 404 template had been wrong for months.
    """

    _CANONICAL = re.compile(r'<link[^>]+rel=["\']canonical["\']', re.I)

    def test_a_missing_page_carries_a_bare_head_under_every_theme(self):
        checked = []
        for name in _contract_themes():
            _activate_theme(self, name)
            with self.subTest(theme=name):
                response = self.client.get('/no-such-page-under-any-theme/')
                self.assertEqual(response.status_code, 404)
                head = response.content.decode().split('</head>', 1)[0]
                self.assertEqual(len(_TITLE.findall(head)), 1)
                self.assertEqual(len(_ROBOTS.findall(head)), 1)
                self.assertIn('noindex, follow', head)
                self.assertIsNone(self._CANONICAL.search(head))
                self.assertNotIn('hreflang=', head)
                self.assertNotIn('application/ld+json', head)
                self.assertNotIn('og:url', head)
                checked.append(name)
        self.assertGreater(len(checked), 1, f'only {checked} could run')


class ThemeMarkupContractTests(TestCase):
    """What a contract theme's templates may not contain at all.

    `EveryContractThemeTests` scanned for robots and canonical only, so twelve
    raw `ld+json` blocks in montenegro's booking templates and a raw hreflang
    loop in dot_books' product page passed it. The head document owns both.
    """

    _FORBIDDEN = (
        (re.compile(r'application/ld\+json', re.I), 'a JSON-LD block'),
        (re.compile(r'hreflang=', re.I), 'an hreflang alternate'),
        (re.compile(r'<html lang=["\']en["\']', re.I), 'a hardcoded <html lang="en">'),
    )
    _COMMENTS = EveryContractThemeTests._COMMENTS

    def test_contract_themes_and_storefront_plugin_templates_emit_none(self):
        import pathlib

        repo = pathlib.Path(__file__).resolve().parents[1]
        roots = [
            repo / 'themes' / 'library' / name / 'templates'
            for name in (t.name for t in theme_registry.all_themes())
            if getattr(theme_registry.get(name), 'head_contract', 0) >= 1
        ]
        roots += sorted((repo / 'plugins' / 'installed').glob('*/templates'))
        offenders = []
        for root in roots:
            for template in root.rglob('*.html'):
                if EveryContractThemeTests._is_amp(template):
                    continue
                markup = self._COMMENTS.sub('', template.read_text(errors='ignore'))
                # Only pages rendered inside a storefront theme are bound by the
                # contract; standalone documents (AMP stories, emails) are not.
                if 'storefront/base.html' not in markup:
                    continue
                for pattern, label in self._FORBIDDEN:
                    if pattern.search(markup):
                        offenders.append(f'{template.relative_to(repo)}: {label}')
        for theme in theme_registry.all_themes():
            if getattr(theme, 'head_contract', 0) < 1:
                continue
            base = (
                repo / 'themes' / 'library' / theme.name / 'templates' / 'storefront' / 'base.html'
            )
            if base.is_file() and self._FORBIDDEN[2][0].search(base.read_text()):
                offenders.append(f'{base.relative_to(repo)}: a hardcoded <html lang="en">')
        self.assertEqual(
            offenders, [], 'the head document owns these:\n  ' + '\n  '.join(offenders)
        )


class DeadBlockTests(TestCase):
    """No template overrides a block that nothing above it renders.

    ~190 storefront templates carried `{% block title %}…{% endblock %}` — and
    no theme's `storefront/base.html` defines a `title` block. Every one of
    them was dead: montenegro's translated 404 title, its "Cancellations &
    refunds", every "— dot books" suffix. They read as working code to anyone
    editing a page, and nothing ever rendered them.
    """

    @staticmethod
    def _dead_blocks(name: str) -> list[str]:
        from django.template import Context
        from django.template.loader import get_template
        from django.template.loader_tags import BlockNode, ExtendsNode

        template = get_template(name).template
        extends = next((n for n in template.nodelist if isinstance(n, ExtendsNode)), None)
        if extends is None:
            return []
        own = [n.name for n in extends.nodelist if isinstance(n, BlockNode)]
        available: set[str] = set()
        node = extends
        while node is not None:
            parent_name = node.parent_name.resolve(Context())
            if not isinstance(parent_name, str):
                return []  # a dynamic parent — cannot be checked statically
            parent = get_template(parent_name).template
            available |= {b.name for b in parent.nodelist.get_nodes_by_type(BlockNode)}
            node = next((n for n in parent.nodelist if isinstance(n, ExtendsNode)), None)
        return [b for b in own if b not in available]

    def _scan(self, root, offenders, label) -> int:
        checked = 0
        for path in root.rglob('*.html'):
            name = str(path.relative_to(root))
            try:
                dead = self._dead_blocks(name)
            except Exception:  # noqa: BLE001, S112 — a template another test compiles
                continue
            checked += 1
            if dead:
                offenders.append(f'{label}/{name}: {", ".join(dead)}')
        return checked

    def test_no_template_overrides_a_block_its_base_never_renders(self):
        import pathlib

        repo = pathlib.Path(__file__).resolve().parents[1]
        offenders: list[str] = []
        checked = 0
        for name in _contract_themes():
            _activate_theme(self, name)
            checked += self._scan(repo / 'themes' / 'library' / name / 'templates', offenders, name)
        _activate_theme(self, 'dot_books')
        for root in [
            repo / 'templates',
            *sorted((repo / 'plugins' / 'installed').glob('*/templates')),
        ]:
            checked += self._scan(root, offenders, str(root.relative_to(repo)))
        self.assertGreater(checked, 200, 'the scan found almost nothing to check')
        self.assertEqual(
            offenders, [], 'blocks no base template renders:\n  ' + '\n  '.join(offenders)
        )
