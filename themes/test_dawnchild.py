"""The Dawnchild theme renders the store's own data, and only that.

The theme was built from six page designs that carry one imprint's four books,
their prices and its trade terms as placeholder content. A theme that shipped
those would sell books no store holds at prices no checkout charges, so the
tests here render every designed page against a real (test) catalogue and CMS
and assert both directions: what the store has appears, and what only the
design had does not.

Also here, because the shared theme suites name their themes in a list this
change must not edit: the head contract, the global slots, nonce-only scripts,
and the shop pages the design does not draw (product, basket, checkout,
account) answering under this theme.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.template.loader import get_template
from django.test import Client, SimpleTestCase, TestCase
from djmoney.money import Money

from themes.registry import theme_registry
from themes.test_head_contract import _activate_theme

THEME = 'dawnchild'
ROOT = Path(settings.BASE_DIR) / 'themes' / 'library' / THEME
TEMPLATES = ROOT / 'templates'

# Placeholder content of the design files. None of it may reach a page: the
# books and prices are the catalogue's, the terms are the merchant's.
DESIGN_ONLY = (
    'Daffy Goes to Sea',
    'The Family Week-End Book',
    'Good Food',
    '£18.00',
    '£12.00',
    '£39.00',
    '979-8-',
    '35%',
    'Thirty days',
    'thirty days',
    'at most five a year',
    'Vivian French',
    'hello@dawnchild.com',
    'trade@dawnchild.com',
    'Focal Point International',
    'data-cur="GBP"',
)

# Templates written for this theme (the designed pages and its chrome); the rest
# are the shared shop pages, carried over unchanged.
OWN_TEMPLATES = {
    'advanced_ecommerce/blocks/_recently_viewed_card.html',
    'advanced_ecommerce/blocks/recently_viewed.html',
    'cms/_menu.html',
    'cms/page.html',
    'storefront/_footer_fallback.html',
    'storefront/_footer_nav.html',
    'storefront/_home_card.html',
    'storefront/_lockup.html',
    'storefront/_product_card.html',
    'storefront/_shelf_item.html',
    'storefront/about.html',
    'storefront/base.html',
    'storefront/coming_soon.html',
    'storefront/contact.html',
    'storefront/home.html',
    'storefront/journal_index.html',
    'storefront/newsletter_thanks.html',
    'storefront/product_list.html',
    'storefront/returns.html',
    'storefront/sections/_stock_list.html',
    'storefront/shipping.html',
    'storefront/taxonomy_root.html',
}
PAYMENT_PAGE = re.compile(
    r'storefront/(cart|checkout\w*|account_payment_methods|_cart_drawer)\.html$'
)

HERO_REL = 'media/e8/15/e815f76677af4afd89f967416d4b578e/dawnchild-hero-beryl-irving.jpg'
HERO = f'/media/{HERO_REL}'
HERO_ALT = 'Illustration of a large bird beside a child, signed Beryl Irving.'
# The design's own banner words, which the owner chose to keep (2026-11-21).
HERO_WORDS = (
    'The Dawnchild · Chapter One',
    '“Something tapped at the window and called her name.”',
    'Mig creeps out of bed, past the snoring Cousin Belinda',
    'Read the first chapter',
    'Beryl Irving',
    'back for its centenary: 1926–2026.',
)

_COMMENTS = re.compile(r'{%\s*comment\s*%}.*?{%\s*endcomment\s*%}|{#.*?#}', re.S)


def _sources() -> dict[str, str]:
    return {
        str(p.relative_to(TEMPLATES)): _COMMENTS.sub('', p.read_text(encoding='utf-8'))
        for p in sorted(TEMPLATES.rglob('*.html'))
    }


def _gql_product(name: str, slug: str, category: tuple[str, str] | None, amount: str) -> dict:
    return {
        'id': str(uuid4()),
        'name': name,
        'slug': slug,
        'productType': 'simple',
        'shortDescription': f'<p>{name} opens with a knock at the door. Then more.</p>',
        'category': {'name': category[0], 'slug': category[1]} if category else None,
        'price': {'amount': amount, 'currency': 'GBP'},
        'priceStartsFrom': False,
        'primaryImage': {'url': f'https://example.com/{slug}.jpg', 'altText': f'{name}, cover'},
        'isOnSale': False,
        'discountPercentage': 0,
    }


class DawnchildFilesTests(SimpleTestCase):
    """What can be read off the disk, with no page rendered."""

    def test_the_theme_is_registered_and_is_nobodys_default(self):
        theme = theme_registry.get(THEME)
        self.assertIsNotNone(theme, 'themes/library/dawnchild was not discovered')
        self.assertEqual(theme.head_contract, 1)
        # Adding a theme changes no store: the default stays what it was.
        self.assertNotEqual(settings.MORPHEUS_ACTIVE_THEME, THEME)

    def test_every_template_compiles(self):
        _activate_theme(self, THEME)
        for name in _sources():
            with self.subTest(template=name):
                get_template(name)

    def test_no_template_carries_the_designs_placeholder_content(self):
        found = [
            f'{name}: {needle!r}'
            for name, text in _sources().items()
            for needle in DESIGN_ONLY
            if needle in text
        ]
        self.assertEqual(found, [])

    def test_the_head_is_one_storefront_head_call_and_all_four_slots(self):
        base = _sources()['storefront/base.html']
        self.assertEqual(len(re.findall(r'{%\s*storefront_head\b', base)), 1)
        for tag in ('<title', 'rel="canonical"', 'property="og:', 'application/ld+json'):
            self.assertNotIn(tag, base)
        for slot in ('global_head', 'global_below_body', 'footer_legal', 'footer_extra'):
            self.assertRegex(base, r'storefront_blocks\s+"' + slot + '"')

    def test_scripts_carry_the_nonce_and_nothing_is_an_inline_handler(self):
        """The basket and the checkout run under a nonce-only CSP.

        Checked for every template this theme wrote and for the payment pages.
        The other shop pages are the shared ones, unchanged, and run under the
        report-only policy like every theme's.
        """
        for name, text in _sources().items():
            if name not in OWN_TEMPLATES and not PAYMENT_PAGE.match(name):
                continue
            with self.subTest(template=name):
                for tag in re.findall(r'<script\b[^>]*>', text):
                    self.assertIn('nonce="{{ csp_nonce }}"', tag, tag)
                self.assertIsNone(re.search(r'\son[a-z]+\s*=\s*["\']', text), name)

    def test_public_forms_ask_the_bot_check(self):
        for name, text in _sources().items():
            for form in re.findall(r'<form\b.*?</form>', text, re.S):
                action = re.search(r'action="([^"]*)"', form)
                target = action.group(1) if action else ''
                if target.startswith('/newsletter/subscribe/'):
                    self.assertIn('{% bot_check "newsletter" %}', form, name)
                elif target == '/contact/':
                    self.assertIn('{% bot_check "contact" %}', form, name)

    def test_the_signup_script_prints_only_what_the_server_answered(self):
        """No success line of the theme's own: the newsletter app's words, or none."""
        js = (ROOT / 'static' / THEME / 'dawnchild.js').read_text(encoding='utf-8')
        self.assertIn('res.data.message', js)
        for name, text in _sources().items():
            for form in re.findall(r'<form\b[^>]*data-dc-signup[^>]*>', text):
                self.assertNotIn('data-ok=', form, name)

    def test_the_stylesheets_have_no_comment_that_ends_early(self):
        for css in (ROOT / 'static' / THEME).glob('*.css'):
            text = css.read_text(encoding='utf-8')
            self.assertEqual(text.count('/*'), text.count('*/'), css.name)
            self.assertNotIn('display:none!important}\n.memory-form', text)

    def test_the_stores_illustration_is_never_cropped_or_faded(self):
        compat = (ROOT / 'static' / THEME / 'compat.css').read_text(encoding='utf-8')
        img = re.search(r'#page-home \.home-banner-art--full img \{([^}]*)\}', compat).group(1)
        for rule in ('width: 100%', 'height: auto', 'object-fit: contain'):
            self.assertIn(rule, img)
        self.assertIn('#page-home .home-banner-art--full::after { content: none; }', compat)
        # It sits inside the banner, with the banner's colour round it and a soft
        # shadow under it (owner, 2026-11-21), on a phone too.
        self.assertIn('#page-home .home-banner-art--full { padding: clamp(', compat)
        self.assertRegex(
            compat, r'#page-home \.home-banner-art--full img \{\s*box-shadow: 0 22px 36px -16px'
        )
        phone = compat.split('@media (max-width: 599px) {', 1)[1].split('\n}', 1)[0]
        self.assertIn('padding: 28px clamp(28px, 12vw, 56px) 14px', phone)
        self.assertIn(
            'width: auto; max-width: 100%; max-height: 60svh; margin-inline: auto;', phone
        )

    def test_the_home_banner_meets_the_header(self):
        # compat's "#main > section.page" pads every page by 40px and outranks the
        # design's own "#page-home{padding-top:0}", so the home needs an id pair.
        compat = (ROOT / 'static' / THEME / 'compat.css').read_text(encoding='utf-8')
        self.assertIn('#main > #page-home { padding-top: 0; }', compat)
        # Under 700px the page is padded by the header's measured height
        # (dawnchild.js sets --head-h); a fixed 101px left a band under a 99px header.
        design = (ROOT / 'static' / THEME / 'dawnchild.css').read_text(encoding='utf-8')
        self.assertNotIn('body{padding-top:101px!important}', design)
        self.assertIn('body{padding-top:var(--head-h,101px)!important}', design)

    def test_theme_settings_all_have_a_reader(self):
        schema = theme_registry.get(THEME).get_config_schema()['properties']
        everything = '\n'.join(_sources().values())
        for key in schema:
            self.assertIn(f'theme_config.{key}', everything, f'{key} is read by no template')


class _Dawnchild(TestCase):
    def setUp(self):
        _activate_theme(self, THEME)
        self.addCleanup(cache.clear)

    def _get(self, path: str, client: Client | None = None, status: int = 200) -> str:
        response = (client or self.client).get(path)
        self.assertEqual(response.status_code, status, path)
        return response.content.decode()

    def assertNoDesignContent(self, body: str) -> None:
        for needle in DESIGN_ONLY:
            self.assertNotIn(needle, body)


class DawnchildHomeTests(_Dawnchild):
    def _home(self, products: list[dict]) -> str:
        data = {'featuredProducts': products, 'collections': [], 'categories': []}
        with (
            patch(
                'plugins.installed.personalisation.services.rank_for_visitor',
                side_effect=lambda request, products, surface: products,
            ),
            patch('plugins.installed.storefront.views.home.internal_graphql', return_value=data),
        ):
            return self._get('/')

    def test_the_shelves_are_the_stores_featured_books_under_their_categories(self):
        children = ('For children', 'for-children')
        family = ('For the whole family', 'family')
        owl = _gql_product('The Owl Lantern', 'owl-lantern', children, '14.50')
        tide = _gql_product('Tide Tables', 'tide-tables', children, '9.00')
        jam = _gql_product('A Year of Jam', 'year-of-jam', family, '21.00')
        body = self._home([owl, tide, jam])

        self.assertEqual(body.count('class="home-shelf '), 2)
        self.assertEqual(body.count('<article class="hs-card"'), 3)
        shelves = body.split('id="home-shelves"', 1)[1]
        first, second = shelves.split('class="home-shelf ')[1:3]
        self.assertIn('/category/for-children/', first)
        self.assertIn('/products/owl-lantern/', first)
        self.assertIn('/products/tide-tables/', first)
        self.assertIn('/products/year-of-jam/', second)
        # The catalogue's price, through the store's money format.
        self.assertIn('14.50', first)
        self.assertIn('21.00', second)
        # A real add-to-basket: the store's cart route for that product.
        self.assertIn(f'action="/cart/add/{owl["id"]}/"', first)
        # The banner is the design's own; the featured books stay on their shelves.
        banner = body.split('id="home-banner"', 1)[1].split('id="home-why"', 1)[0]
        self.assertNotIn('owl-lantern', banner)
        self.assertNotIn('Owl Lantern', banner)
        self.assertNotIn('&lt;p&gt;', body)
        self.assertNoDesignContent(body)

    def test_a_book_with_no_category_still_gets_a_shelf(self):
        body = self._home([_gql_product('Loose Leaf', 'loose-leaf', None, '5.00')])
        self.assertEqual(body.count('<article class="hs-card"'), 1)
        self.assertIn('More books', body)

    def test_a_store_with_nothing_featured_shows_no_invented_book(self):
        body = self._home([])
        self.assertNotIn('hs-card', body)
        self.assertNotIn('/cart/add/', body.split('id="cart-drawer', 1)[0])
        banner = self._banner(body)
        for words in HERO_WORDS:
            self.assertIn(words, banner)
        # With no page named, both of the banner's links lead to the shelf.
        self.assertEqual(banner.count('href="/products/"'), 2)
        self.assertNoDesignContent(body)

    def _illustration(self, url: str = HERO, alt: str = HERO_ALT, **more: str) -> None:
        """The store names its banner illustration (and link) in the theme's settings."""
        from themes.models import ThemeConfig

        config = {'hero_image_url': url, 'hero_image_alt': alt, **more}
        ThemeConfig.objects.update_or_create(theme_name=THEME, defaults={'config': config})
        theme = theme_registry.get(THEME)
        theme.invalidate_config_cache()
        self.addCleanup(theme.invalidate_config_cache)

    def _banner(self, body: str) -> str:
        return body.split('id="home-banner"', 1)[1].split('id="home-why"', 1)[0]

    def test_the_stores_illustration_shows_with_nothing_featured(self):
        self._illustration()
        body = self._home([])
        self.assertIn('class="home-banner" id="home-banner"', body)
        banner = self._banner(body)
        self.assertIn('home-banner-art--full', banner)
        self.assertIn(f'/img/webp/1200/{HERO_REL}', banner)
        self.assertIn(f'alt="{HERO_ALT}"', banner)
        self.assertIn('fetchpriority="high"', banner)
        # The picture first (left, or above on a phone), then the words.
        self.assertLess(banner.index('home-banner-art--full'), banner.index('home-banner-text'))
        self.assertIn(HERO_WORDS[1], banner)

    def test_the_banner_never_shows_a_featured_book(self):
        self._illustration()
        owl = _gql_product('The Owl Lantern', 'owl-lantern', ('For children', 'kids'), '14.50')
        body = self._home([owl])
        banner = self._banner(body)
        self.assertIn(f'/img/webp/1200/{HERO_REL}', banner)
        for words in HERO_WORDS:
            self.assertIn(words, banner)
        self.assertNotIn('owl-lantern', banner)
        self.assertNotIn('Owl Lantern', banner)
        # The book's cover stays on its shelf.
        self.assertIn('owl-lantern.jpg', body.split('id="home-shelves"', 1)[1])

    def test_without_an_illustration_the_banner_is_its_words_alone(self):
        owl = _gql_product('The Owl Lantern', 'owl-lantern', ('For children', 'kids'), '14.50')
        body = self._home([owl])
        self.assertIn('class="home-banner home-banner--plain" id="home-banner"', body)
        banner = self._banner(body)
        self.assertNotIn('<figure', banner)
        self.assertNotIn('owl-lantern.jpg', banner)
        self.assertIn(HERO_WORDS[1], banner)

    def test_the_banner_links_to_the_page_the_store_names(self):
        self._illustration(hero_link_url='/products/the-dawnchild/')
        banner = self._banner(self._home([]))
        self.assertEqual(banner.count('href="/products/the-dawnchild/"'), 2)
        self.assertNotIn('href="/products/"', banner)

    def test_the_banner_link_is_only_ever_a_page_on_this_store(self):
        for unsafe in ('javascript:alert(1)', '//elsewhere.example/', 'https://elsewhere.example/'):
            with self.subTest(unsafe):
                self._illustration(hero_link_url=unsafe)
                banner = self._banner(self._home([]))
                self.assertEqual(banner.count('href="/products/"'), 2)
                self.assertNotIn('elsewhere', banner)
                self.assertNotIn('javascript', banner)

    def test_one_title_and_the_page_is_the_designs_home(self):
        body = self._home([])
        self.assertEqual(len(re.findall(r'<title\b', body)), 1)
        self.assertIn('id="page-home"', body)
        self.assertIn('class="site-head"', body)
        self.assertIn('class="site-foot"', body)
        self.assertIn('dawnchild/dawnchild.css', body)

    def test_the_letter_form_posts_to_the_newsletter_app(self):
        body = self._home([])
        form = re.search(r'<form[^>]*id="signup-home".*?</form>', body, re.S).group(0)
        self.assertIn('action="/newsletter/subscribe/"', form)
        self.assertIn('name="email"', form)
        # The status line starts empty; only the server's answer fills it.
        self.assertRegex(form, r'data-signup-msg role="status">\s*</p>')


class DawnchildShelfTests(_Dawnchild):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import Category, Product, ProductVariant

        children = Category.objects.create(name='For children', slug='for-children')
        family = Category.objects.create(name='For the whole family', slug='family')
        cls.owl = Product.objects.create(
            name='The Owl Lantern',
            slug='owl-lantern',
            sku='OWL-1',
            price=Money(Decimal('14.50'), 'USD'),
            status='active',
            category=children,
        )
        ProductVariant.objects.create(
            product=cls.owl, name='Paperback', sku='978-1-TEST-PB', price=Money('14.50', 'USD')
        )
        ProductVariant.objects.create(
            product=cls.owl, name='Hardback', sku='978-1-TEST-HB', price=Money('31.25', 'USD')
        )
        Product.objects.create(
            name='A Year of Jam',
            slug='year-of-jam',
            sku='JAM-1',
            price=Money(Decimal('21.00'), 'USD'),
            status='active',
            category=family,
        )
        Product.objects.create(
            name='Loose Leaf',
            slug='loose-leaf',
            sku='LEAF-1',
            price=Money(Decimal('5.00'), 'USD'),
            status='active',
        )
        Product.objects.create(
            name='Not Yet',
            slug='not-yet',
            sku='DRAFT-1',
            price=Money(Decimal('99.00'), 'USD'),
            status='draft',
            category=family,
        )

    def test_books_sit_under_their_own_categories(self):
        body = self._get('/products/')
        page = body.split('id="page-books"', 1)[1].split('class="cartouche suggest"', 1)[0]
        groups = page.split('<div class="shelf-group">')[1:]
        self.assertEqual(len(groups), 3, 'two categories and the uncategorised shelf')
        by_heading = {re.search(r'shelf-head">(?:<a[^>]*>)?([^<]+)', g).group(1): g for g in groups}
        self.assertIn('/products/owl-lantern/', by_heading['For children'])
        self.assertIn('/products/year-of-jam/', by_heading['For the whole family'])
        self.assertIn('/products/loose-leaf/', by_heading['More books'])
        self.assertNotIn('year-of-jam', by_heading['For children'])
        self.assertIn('21.00', by_heading['For the whole family'])
        # Each book once, and a draft never.
        self.assertEqual(page.count('class="shelf-item"'), 3)
        self.assertNotIn('not-yet', body)
        self.assertNoDesignContent(body)

    def test_a_category_filter_shows_one_shelf_of_what_matched(self):
        body = self._get('/products/?category=family')
        page = body.split('id="page-books"', 1)[1].split('class="cartouche suggest"', 1)[0]
        self.assertEqual(page.count('<div class="shelf-group">'), 1)
        self.assertIn('year-of-jam', page)
        self.assertNotIn('owl-lantern', page)

    def test_a_search_with_no_match_says_so_and_lists_nothing(self):
        body = self._get('/products/?q=zzzzqqqq')
        page = body.split('id="page-books"', 1)[1].split('class="cartouche suggest"', 1)[0]
        self.assertNotIn('class="shelf-item"', page)
        self.assertIn('No book matches', page)

    def test_the_suggestion_form_is_the_stores_contact_form(self):
        body = self._get('/products/')
        form = re.search(r'<form[^>]*id="suggest-books".*?</form>', body, re.S).group(0)
        self.assertIn('action="/contact/"', form)
        self.assertIn('name="message"', form)
        self.assertIn('name="email"', form)
        self.assertIn('csrfmiddlewaretoken', form)

    def test_the_product_page_answers_and_can_be_bought_from(self):
        body = self._get('/products/owl-lantern/')
        self.assertIn('The Owl Lantern', body)
        self.assertIn('class="site-head"', body)
        self.assertIn('/cart/add/', body)
        self.assertEqual(len(re.findall(r'<title\b', body)), 1)

    def test_account_and_basket_are_named_icons_and_the_basket_counts(self):
        from plugins.installed.catalog.models import Product

        def tools(body: str) -> str:
            return body.split('<div class="head-tools">', 1)[1].split('</header>', 1)[0]

        empty = tools(self._get('/'))
        # Search, the account menu and the basket: one group of three icons.
        group = empty.split('</header>', 1)[0]
        self.assertEqual(group.count('<svg class="head-icon"'), 3)
        self.assertLess(group.index('id="quicksearch-toggle"'), group.index('data-acct-toggle'))
        self.assertLess(group.index('data-acct-toggle'), group.index('id="cart-icon-link"'))
        self.assertIn('<span class="sr-only">Search</span>', empty)
        self.assertIn('<span class="sr-only">Account</span>', empty)
        self.assertIn('<span class="sr-only">Basket</span>', empty)
        # Only the hidden names carry the words; the icons stand alone on screen.
        self.assertEqual(
            re.findall(r'>(Search|Account|Basket)\b', empty), ['Search', 'Account', 'Basket']
        )
        self.assertIn('id="cart-badge" hidden></span>', empty)

        jam = Product.objects.get(slug='year-of-jam')
        self.client.post(f'/cart/add/{jam.id}/', {'quantity': 2})
        full = tools(self._get('/'))
        self.assertIn('id="cart-badge">2</span>', full)

    def test_recently_viewed_is_a_shelf_with_titles_descriptions_and_prices(self):
        from plugins.installed.catalog.models import Product

        Product.objects.filter(slug='year-of-jam').update(
            short_description='<p>Jam for every month of the year. Then the rest.</p>'
        )
        # The app keeps no list for a crawler, and an empty user agent is one.
        self.client = Client(HTTP_USER_AGENT='Mozilla/5.0 (X11; Linux x86_64) Firefox/140.0')
        for slug in ('owl-lantern', 'year-of-jam'):
            self._get(f'/products/{slug}/')
        body = self._get('/')
        rail = body.split('class="home-shelf hs-recent"', 1)[1].split('</section>', 1)[0]
        self.assertIn('id="hs-recent-h">Recently viewed</h2>', rail)
        self.assertEqual(rail.count('<li class="hs-card"'), 2)
        # Newest first: the app keeps the list in the order the books were opened.
        self.assertLess(rail.index('year-of-jam'), rail.index('owl-lantern'))
        self.assertIn('>A Year of Jam</a></h3>', rail)
        self.assertIn('<p class="hs-hook">Jam for every month of the year.</p>', rail)
        self.assertIn('21.00', rail)
        self.assertIn(f'action="/cart/add/{Product.objects.get(slug="year-of-jam").id}/"', rail)
        self.assertNotIn('&lt;p&gt;', rail)
        # The buttons only scroll the row, and their script carries the nonce.
        self.assertIn('data-dc-rail-next', rail)
        self.assertRegex(
            body.split('class="home-shelf hs-recent"', 1)[1], r'<script nonce="[^"]+">'
        )

    def test_a_free_book_says_free_and_an_unpriced_edition_shows_no_price(self):
        from plugins.installed.catalog.models import Category, Product, ProductVariant

        # Built as the live store's books are (2026-11-21): a digital product
        # priced 0 with one free PDF, and a simple product priced 0.
        free = Product.objects.create(
            name='Free Rabbit',
            slug='free-rabbit',
            sku='RAB-1',
            price=Money(0, 'USD'),
            product_type='digital',
            status='active',
            category=Category.objects.get(slug='for-children'),
        )
        ProductVariant.objects.create(
            product=free,
            name='Digital PDF',
            sku='RAB-PDF',
            price=Money(0, 'USD'),
            variant_type='digital',
            requires_shipping=False,
        )
        # The live Dawnchild book: a paperback with no price yet beside a free audiobook.
        unpriced = Product.objects.create(
            name='Unpriced Bird',
            slug='unpriced-bird',
            sku='BIRD-1',
            price=Money(0, 'USD'),
            product_type='simple',
            status='active',
        )
        ProductVariant.objects.create(product=unpriced, name='Paperback', sku='BIRD-PB')
        ProductVariant.objects.create(
            product=unpriced,
            name='Audiobook',
            sku='BIRD-AB',
            price=Money(0, 'USD'),
            variant_type='digital',
            requires_shipping=False,
        )
        self.client = Client(HTTP_USER_AGENT='Mozilla/5.0 (X11; Linux x86_64) Firefox/140.0')
        pages = {slug: self._get(f'/products/{slug}/') for slug in ('free-rabbit', 'unpriced-bird')}
        # The book's own page says Free above its editions, never $0.00.
        headline = pages['free-rabbit'].split('<span data-pdp-price', 1)[1].split('</span>', 1)[0]
        self.assertIn('Free', headline)
        self.assertNotIn('0.00', headline)
        rail = self._get('/').split('class="home-shelf hs-recent"', 1)[1].split('</section>', 1)[0]
        cards = {
            c.split('href="/products/', 1)[1].split('/', 1)[0]: c
            for c in rail.split('<li class="hs-card"')[1:]
        }
        self.assertIn('<p class="hs-price"><span>Free</span></p>', cards['free-rabbit'])
        # A free book leads to its page to pick a copy; the basket would ask which.
        self.assertIn('Get it free<span class="sr-only">: Free Rabbit</span>', cards['free-rabbit'])
        self.assertNotIn('/cart/add/', cards['free-rabbit'])
        self.assertNotIn('hs-price', cards['unpriced-bird'])
        self.assertNotIn('0.00', rail)
        # The shelf on /products/ and the card on the category page say the same.
        for path in ('/products/', '/category/for-children/'):
            with self.subTest(path=path):
                page = self._get(path)
                card = page.split('href="/products/free-rabbit/"', 1)[1].split('</a>', 1)[0]
                self.assertIn('<span class="shelf-price"><span>Free</span>', card)
        # A featured free book on the home shelves (GraphQL's isFree) says Free too.
        Product.objects.filter(pk=free.pk).update(is_featured=True)
        cache.clear()
        home = self._get('/').split('class="home-shelf hs-recent"', 1)[0]
        card = home.split('<article class="hs-card"', 1)[1].split('</article>', 1)[0]
        self.assertIn('free-rabbit', card)
        self.assertIn('<p class="hs-price"><span>Free</span>', card)
        self.assertNotIn('0.00', card)
        self.assertIn('Get it free', card)

        # A store that gives print away (catalog's give_away_print): the printed
        # copy nothing prices is free too, so the whole book says Free.
        from plugins.testing import set_app_settings

        set_app_settings(self, 'catalog', give_away_print=True)
        cache.clear()
        page = self._get('/products/unpriced-bird/')
        self.assertIn('Free', page.split('<span data-pdp-price', 1)[1].split('</span>', 1)[0])
        rail = self._get('/').split('class="home-shelf hs-recent"', 1)[1].split('</section>', 1)[0]
        bird = rail.split('href="/products/unpriced-bird/"', 1)[1].split('</li>', 1)[0]
        self.assertIn('<p class="hs-price"><span>Free</span></p>', bird)

    def test_a_book_nothing_prices_shows_no_price_and_no_dead_button(self):
        # The live store (2026-11-21): The Dawnchild has an unpriced paperback
        # beside a free audiobook, and Daffy Goes to Sea has no edition yet, both
        # on a product priced 0. The basket refuses the paperback and Daffy, yet
        # the home shelf printed $0.00 with "Add to basket" for them.
        from plugins.installed.catalog.models import Category, Product, ProductVariant

        children = Category.objects.get(slug='for-children')
        quiet = Product.objects.create(
            name='Quiet Bird',
            slug='quiet-bird',
            sku='QB-1',
            price=Money(0, 'USD'),
            product_type='simple',
            status='active',
            category=children,
            is_featured=True,
        )
        paperback = ProductVariant.objects.create(
            product=quiet, name='Paperback', sku='QB-PB', sort_order=0
        )
        audio = ProductVariant.objects.create(
            product=quiet,
            name='Audiobook',
            sku='QB-AB',
            price=Money(0, 'USD'),
            variant_type='audiobook',
            requires_shipping=False,
            sort_order=1,
        )
        bare = Product.objects.create(
            name='Bare Book',
            slug='bare-book',
            sku='BARE-1',
            price=Money(0, 'USD'),
            product_type='simple',
            status='active',
            category=children,
            is_featured=True,
        )
        self.client = Client(HTTP_USER_AGENT='Mozilla/5.0 (X11; Linux x86_64) Firefox/140.0')

        # The book page selects the free audiobook, never the paperback the basket
        # refuses, and says Free above it; the paperback would send nothing.
        page = self._get('/products/quiet-bird/')
        headline = page.split('<span data-pdp-price', 1)[1].split('</span>', 1)[0]
        self.assertIn('Free', headline)
        self.assertNotIn('0.00', headline)
        self.assertIn(f'name="variant_id" value="{audio.pk}"', page)
        self.assertRegex(page, rf'data-variant-id="{paperback.pk}"[^>]*data-variant-for-sale="0"')
        self.assertRegex(page, rf'data-variant-id="{audio.pk}"[^>]*data-variant-for-sale="1"')
        self.assertIn(
            'data-pdp-cta data-unavailable-label="Not available yet">Add to cart</button>', page
        )
        # A book with nothing for sale yet: no price, and a button that sends nothing.
        page = self._get('/products/bare-book/')
        self.assertNotIn('0.00', page.split('<span data-pdp-price', 1)[1].split('</span>', 1)[0])
        self.assertIn(
            'data-pdp-cta data-unavailable-label="Not available yet" disabled>Not available yet</button>',
            page,
        )
        self.assertIn('data-pdp-sticky-cta disabled>Not available yet</button>', page)
        self.assertNotIn('data-pdp-sticky-price>$0.00', page)

        def card(html: str, slug: str, start: str, end: str) -> str:
            chunk = next(c for c in html.split(start)[1:] if f'href="/products/{slug}/"' in c)
            return chunk.split(end, 1)[0]

        cache.clear()
        home = self._get('/')
        featured, rail = home.split('class="home-shelf hs-recent"', 1)
        rail = rail.split('</section>', 1)[0]
        for shelf, start, end in (
            (featured, '<article class="hs-card"', '</article>'),
            (rail, '<li class="hs-card"', '</li>'),
        ):
            with self.subTest(shelf=start):
                q, b = card(shelf, 'quiet-bird', start, end), card(shelf, 'bare-book', start, end)
                for c in (q, b):
                    self.assertNotIn('hs-price', c)
                    self.assertNotIn('0.00', c)
                    self.assertNotIn('/cart/add/', c)
                    self.assertIn('>The book<', c)
                # The audiobook can be had, so the card leads to the page to pick it.
                self.assertIn('Choose a format', q)
                self.assertNotIn('Choose a format', b)
        # The shelf on /products/ and the card on the category page say the same.
        shelf = self._get('/products/')
        for slug in ('quiet-bird', 'bare-book'):
            item = shelf.split(f'href="/products/{slug}/"', 1)[1].split('</a>', 1)[0]
            self.assertNotIn('shelf-price', item)
        category = self._get('/category/for-children/')
        self.assertNotIn(f'/cart/add/{quiet.id}/', category)
        self.assertNotIn(f'/cart/add/{bare.id}/', category)
        self.assertIn('Choose a format<span class="sr-only">: Quiet Bird</span>', category)
        self.assertNotIn('Choose a format<span class="sr-only">: Bare Book</span>', category)

    def test_category_search_and_basket_pages_answer(self):
        for path in ('/category/for-children/', '/search/?q=owl', '/cart/', '/categories/'):
            with self.subTest(path=path):
                response = self.client.get(path, follow=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn('class="site-head"', response.content.decode())

    def test_the_trade_page_lists_the_catalogues_editions(self):
        # CMS loads the section bundle of the theme the process started with;
        # here that is another theme, so load Dawnchild's and put the registry
        # back as it was afterwards.
        import importlib

        from plugins.installed.cms.models import Page, PageSection
        from themes.sections import section_registry

        previous = dict(section_registry._by_id)
        self.addCleanup(setattr, section_registry, '_by_id', previous)
        importlib.reload(importlib.import_module('themes.library.dawnchild.sections'))
        self.assertIn('stock_list', section_registry)
        self.assertIn('hero', section_registry)

        page = Page.objects.create(
            title='Books for your shop',
            slug='trade',
            excerpt='Order direct from the imprint.',
            body='<p>Our terms, in our own words.</p>',
            state='published',
        )
        PageSection.objects.create(
            page=page, section_id='stock_list', settings={'heading': 'Stock list'}, sort_order=0
        )
        body = self._get('/p/trade/')
        self.assertIn('id="page-trade"', body)
        self.assertIn('Books for your shop', body)
        self.assertIn('Our terms, in our own words.', body)
        stock = body.split('id="trade-stock"', 1)[1].split('</table>', 1)[0]
        # One row per edition, with its own code and its own price.
        self.assertIn('978-1-TEST-PB', stock)
        self.assertIn('978-1-TEST-HB', stock)
        self.assertIn('31.25', stock)
        self.assertIn('rowspan="2"', stock)
        # A book sold in one form lists once, under its own SKU.
        self.assertIn('JAM-1', stock)
        self.assertNotIn('DRAFT-1', stock)
        self.assertNoDesignContent(body)


class DawnchildContentTests(_Dawnchild):
    def test_the_header_and_footer_are_the_cms_menus(self):
        from plugins.installed.cms.models import Menu, MenuItem

        header = Menu.objects.create(key='header', label='Header')
        books = MenuItem.objects.create(menu=header, label='Our shelf', url='/products/', order=0)
        MenuItem.objects.create(
            menu=header, parent=books, label='Picture books', url='/category/picture/', order=0
        )
        MenuItem.objects.create(menu=header, label='Letters home', url='/journal/', order=1)
        footer = Menu.objects.create(key='footer', label='Footer')
        help_group = MenuItem.objects.create(menu=footer, label='Help desk', url='', order=0)
        MenuItem.objects.create(
            menu=footer, parent=help_group, label='Postage', url='/shipping/', order=0
        )
        MenuItem.objects.create(menu=footer, label='Press room', url='/p/press/', order=1)
        cache.clear()

        body = self._get('/about/')
        nav = body.split('<nav class="nav"', 1)[1].split('</nav>', 1)[0]
        self.assertIn('Our shelf', nav)
        self.assertIn('Letters home', nav)
        # An entry with children gets the design's titles panel.
        self.assertIn('nav-item has-menu', nav)
        self.assertIn('href="/category/picture/"', nav)
        # The theme's own fallback links are gone once the store has a menu.
        self.assertNotIn('>Trade<', nav)
        self.assertNotIn('>Authors<', nav)

        foot = body.split('<footer class="site-foot"', 1)[1].split('</footer>', 1)[0]
        self.assertIn('Help desk', foot)
        self.assertIn('href="/shipping/"', foot)
        self.assertIn('Press room', foot)
        self.assertNotIn('footer-explore', foot)
        self.assertEqual(foot.count('<ul>'), foot.count('</ul>'))
        self.assertEqual(foot.count('<div'), foot.count('</div>'))

    def test_without_menus_the_fallback_links_all_answer(self):
        body = self._get('/about/')
        nav = body.split('<nav class="nav"', 1)[1].split('</nav>', 1)[0]
        foot = body.split('<footer class="site-foot"', 1)[1].split('</footer>', 1)[0]
        links = set(re.findall(r'href="(/[^"#]*)"', nav + foot))
        self.assertIn('/products/', links)
        self.assertIn('/journal/', links)
        for href in sorted(links - {'/p/trade/', '/account/', '/account/orders/'}):
            with self.subTest(href=href):
                self.assertEqual(self.client.get(href, follow=True).status_code, 200)
        # Account links send a visitor to sign in rather than failing.
        self.assertIn(self.client.get('/account/').status_code, (301, 302))

    def test_about_is_the_designs_page_on_cream_paper(self):
        body = self._get('/about/')
        self.assertIn('<body class="reading">', body)
        self.assertIn('id="page-about"', body)
        self.assertIn('Some books disappear. We go and fetch them back.', body)
        self.assertEqual(len(re.findall(r'<title\b', body)), 1)
        self.assertNoDesignContent(body)

    def test_the_notes_are_the_stores_journal_posts(self):
        from plugins.installed.cms.models import Page

        Page.objects.create(
            slug='how-the-owl-came-back',
            title='How the owl came back',
            excerpt='A typescript in a biscuit tin.',
            body='<p>It began in an attic.</p><img src="/media/owl-plate.jpg">',
            state='published',
            metadata={'category': 'journal'},
        )
        Page.objects.create(
            slug='unwritten',
            title='Unwritten',
            body='<p>Later.</p>',
            state='draft',
            metadata={'category': 'journal'},
        )
        body = self._get('/journal/')
        self.assertIn('id="page-notes"', body)
        self.assertEqual(body.count('<article class="nn-row'), 1)
        self.assertIn('href="/journal/how-the-owl-came-back/"', body)
        self.assertIn('A typescript in a biscuit tin.', body)
        self.assertIn('owl-plate.jpg', body)
        self.assertNotIn('Unwritten', body)
        self.assertNoDesignContent(body)
        post = self._get('/journal/how-the-owl-came-back/')
        self.assertIn('It began in an attic.', post)

    def test_an_empty_journal_shows_no_invented_note(self):
        body = self._get('/journal/')
        self.assertNotIn('<article class="nn-row', body)
        self.assertIn('The first notes are being written.', body)

    def test_the_authors_page_lists_the_book_apps_authors(self):
        from plugins.registry import app_registry

        if not app_registry.is_active('book_product'):
            self.skipTest('the book app is off in this process')
        body = self._get('/authors/')
        self.assertIn('id="page-authors"', body)
        self.assertIn('class="aa-hook"', body)
        self.assertNotIn('<article class="aa-row', body)  # no authors in this store
        self.assertNoDesignContent(body)

    def test_shipping_returns_and_contact_promise_nothing_of_their_own(self):
        for path in ('/shipping/', '/returns/', '/contact/'):
            with self.subTest(path=path):
                body = self._get(path)
                self.assertNoDesignContent(body)
                main = body.split('<main id="main"', 1)[1].split('</main>', 1)[0]
                self.assertIsNone(re.search(r'[$£€]\s*\d', main), 'a price in house copy')
                self.assertIsNone(re.search(r'\b\d+\s+(business |working )?days?\b', main))

    def test_a_plain_cms_page_renders_its_body(self):
        from plugins.installed.cms.models import Page

        Page.objects.create(
            title='Colophon',
            slug='colophon',
            body='<p>How the books are made.</p>',
            state='published',
        )
        body = self._get('/p/colophon/')
        self.assertIn('<body class="reading">', body)
        self.assertIn('How the books are made.', body)

    def test_the_account_pages_answer_for_a_signed_in_shopper(self):
        shopper = get_user_model().objects.create_user(
            username='dc-shopper', email='dc.shopper@example.com', password='x'
        )
        client = Client()
        client.force_login(shopper)
        for path in ('/account/', '/account/orders/', '/account/addresses/', '/account/profile/'):
            with self.subTest(path=path):
                body = self._get(path, client)
                self.assertIn('class="site-head"', body)
                self.assertIn('href="/auth/logout/"', body)
        # The menu names links, never the shopper: a cached page carries nothing personal.
        head = self._get('/about/', client).split('class="site-head"', 1)[1].split('</header>')[0]
        self.assertNotIn('dc.shopper@example.com', head)

    def test_the_checkout_answers_under_this_theme(self):
        response = self.client.get('/checkout/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('class="site-head"', response.content.decode())
