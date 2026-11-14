"""Pages where a shopper types an address or a card enforce a nonce-based CSP (v0.137.0).

A script on those pages runs only when its tag carries the response's nonce, so
these tests render every payment page under every theme, with every app that
writes a script switched on, and check each <script> against the header the
same response sent. docs/CHECKOUT_SCRIPTS.md is the PCI DSS 6.4.3 inventory of
what those scripts are; the tests keep it and the policy in step.
"""

from __future__ import annotations

import json
import re
from contextlib import ExitStack
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from djmoney.money import Money

from core.security_headers import (
    _PAYMENT_PAGE_CSP,
    PAYMENT_PAGE_FORM_TARGETS,
    PAYMENT_PAGE_SCRIPT_ORIGINS,
)

_DOC = Path(__file__).resolve().parents[2] / 'docs' / 'CHECKOUT_SCRIPTS.md'
# Script types a browser runs, and so the policy governs. Any other type is a
# data block (JSON-LD, a JSON config) that needs no nonce.
_RUN_TYPES = {
    '',
    'text/javascript',
    'application/javascript',
    'module',
    'importmap',
    'speculationrules',
}
# A script URL written inside an inline script (a pixel's loader, a module import).
_SCRIPT_URL = re.compile(
    r'(?:https?:)?//([a-z0-9.-]+\.[a-z]{2,})(/[^\s"\'`)]*?(?:\.m?js|/\+esm|/js))\b'
)


class _Scripts(HTMLParser):
    """Every <script> with its attributes and body, and every inline handler."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.scripts: list[dict] = []
        self.handlers: list[str] = []
        self._open: dict | None = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for name, value in attrs.items():
            if name.startswith('on'):
                self.handlers.append(f'<{tag} {name}="{(value or "")[:60]}">')
        for name in ('href', 'action', 'formaction', 'src'):
            if (attrs.get(name) or '').strip().lower().startswith('javascript:'):
                self.handlers.append(f'<{tag} {name}="{attrs[name][:60]}">')
        if tag == 'script':
            self._open = {'attrs': attrs, 'body': ''}
            self.scripts.append(self._open)

    def handle_data(self, data):
        if self._open is not None:
            self._open['body'] += data

    def handle_endtag(self, tag):
        if tag == 'script':
            self._open = None


def parse(html: str) -> _Scripts:
    parser = _Scripts()
    parser.feed(html)
    return parser


def runs(script: dict) -> bool:
    return (script['attrs'].get('type') or '').strip().lower() in _RUN_TYPES


def origin_allowed(host: str) -> bool:
    for origin in PAYMENT_PAGE_SCRIPT_ORIGINS:
        allowed = origin.removeprefix('https://')
        if host == allowed or (allowed.startswith('*.') and host.endswith(allowed[1:])):
            return True
    return False


class PaymentPagePolicyTests(SimpleTestCase):
    def test_scripts_run_by_nonce_only(self):
        script_src = _PAYMENT_PAGE_CSP['script-src']
        self.assertIn("'strict-dynamic'", script_src)
        self.assertNotIn("'unsafe-inline'", script_src)
        self.assertNotIn("'unsafe-eval'", script_src)
        self.assertEqual(_PAYMENT_PAGE_CSP['object-src'], ["'none'"])
        self.assertIn('/api/csp-report/', _PAYMENT_PAGE_CSP['report-uri'])

    def test_the_inventory_lists_every_origin_the_policy_names(self):
        doc = _DOC.read_text()
        listed = set(re.findall(r'^\| `(https://[^`]+)` \|', doc, flags=re.M))
        self.assertEqual(listed, set(PAYMENT_PAGE_SCRIPT_ORIGINS))
        for target in PAYMENT_PAGE_FORM_TARGETS:
            self.assertIn(urlsplit(target).hostname.split('.')[-2], doc.lower())

    def test_the_parser_sees_what_the_page_check_relies_on(self):
        page = parse(
            '<script nonce="n">a()</script><script type="application/ld+json">{}</script>'
            '<script type="speculationrules">{}</script>'
            '<button onclick="x()">x</button><a href="javascript:y()">y</a>'
        )
        self.assertEqual([runs(s) for s in page.scripts], [True, False, True])
        self.assertEqual(len(page.handlers), 2)
        self.assertTrue(origin_allowed('js.stripe.com'))
        self.assertTrue(origin_allowed('b.js.stripe.com'))
        self.assertFalse(origin_allowed('evil.example'))
        self.assertFalse(origin_allowed('notjs.stripe.com.evil.example'))


THEMES = ['dot_books', 'supernatural_shop', 'irving_survival']
if apps.is_installed('plugins.installed.booking_marketplace'):
    THEMES += ['montenegro', 'croatia']

# Every app that writes a script into a storefront page, switched on with a
# value its own validation accepts.
_APP_CONFIG = {
    'meta_commerce': {'pixel_enabled': True, 'pixel_id': '123456789012345'},
    'tiktok_commerce': {'pixel_enabled': True, 'pixel_code': 'C4ABCDEF123'},
    'pinterest_commerce': {'tag_enabled': True, 'tag_id': '2612345678901'},
    'snapchat_commerce': {'pixel_enabled': True, 'pixel_id': 'abc-123-def-456'},
    'reddit_ads': {'pixel_enabled': True, 'pixel_id': 't2_abc123'},
    'microsoft_commerce': {'uet_enabled': True, 'uet_tag_id': '123456789'},
    'google_shopping': {'remarketing_enabled': True, 'remarketing_id': 'AW-123456789'},
    'storefront': {'service_worker_enabled': True},
    'localization': {'suggest_language': True},
    # Turnstile on the footer's newsletter form (the checkout itself asks for none).
    'cloudflare': {
        'turnstile_enabled': True,
        'turnstile_site_key': '0x4AAAAAAATEST',
        'turnstile_secret_key': '0x4AAAAAAATESTSECRET',
    },
}
# What the switched-on apps write, so a setup that silently stopped enabling
# one fails here instead of passing on a page with fewer scripts.
_EXPECTED_ON_THE_CART = (
    'connect.facebook.net',
    'analytics.tiktok.com',
    's.pinimg.com',
    'sc-static.net',
    'www.redditstatic.com',
    'bat.bing.com',
    'www.googletagmanager.com',
    'js.stripe.com',
    'serviceWorker',
    'challenges.cloudflare.com',
    'morpheus-language-bar',
)
_TRACKING = {
    'gtm': {'gtm_container_id': 'GTM-ABC1234', 'measurement_id': ''},
    'gtag': {'gtm_container_id': '', 'measurement_id': 'G-ABC1234567'},
}
_STRIPE = 'plugins.installed.payments.services.stripe'
_NONCE = re.compile(r"'nonce-([^']+)'")
_JSDELIVR_PINNED = re.compile(r'^/npm/(@[a-z0-9-]+/)?[a-z0-9.-]+@\d+\.\d+\.\d+(/|$)')


@override_settings(
    STRIPE_PUBLIC_KEY='pk_test_x',
    GOOGLE_PLACES_API_KEY='places-test-key',
    LANGUAGES=[('en', 'English'), ('sr', 'Srpski')],
)
class PaymentPageRenderTests(TestCase):
    def setUp(self):
        from core.models import StoreSettings
        from plugins.installed.catalog.models import Product
        from plugins.installed.newsletter.models import SignupPopup
        from plugins.installed.subscriptions.models import Plan
        from plugins.installed.tracking.models import TrackingSettings
        from plugins.registry import app_registry

        cache.clear()
        StoreSettings.objects.create(country='US')
        for name, values in _APP_CONFIG.items():
            app = app_registry.get(name)
            for key, value in values.items():
                app.set_config(key, value)
            app.invalidate_config_cache()
            self.addCleanup(app.invalidate_config_cache)
        SignupPopup.objects.create(enabled=True)
        self.tracking = TrackingSettings.get_solo()

        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(
            mock.patch(f'{_STRIPE}.PaymentService.get_stripe_public_key', return_value='pk_test_x')
        )
        stack.enter_context(mock.patch(f'{_STRIPE}.create_setup_intent', return_value='seti_x'))
        stack.enter_context(
            mock.patch(
                f'{_STRIPE}.list_payment_methods',
                return_value=[
                    {
                        'id': 'pm_x',
                        'brand': 'visa',
                        'last4': '4242',
                        'exp_month': 1,
                        'exp_year': 2030,
                    }
                ],
            )
        )
        stack.enter_context(
            mock.patch(
                'plugins.installed.subscriptions.billing.stripe_adapter._stripe_key',
                return_value='sk_test_x',
            )
        )
        stack.enter_context(
            mock.patch(
                'plugins.installed.payments.express.cart_offer',
                return_value={'config': {'key': 'pk_test_x', 'amount': 1200, 'currency': 'usd'}},
            )
        )

        user = get_user_model().objects.create_user(
            username='shopper', email='shopper@example.test', password='pw', is_staff=True
        )
        self.client.force_login(user)
        self.client.cookies['morpheus_consent'] = json.dumps(
            {'necessary': True, 'analytics': True, 'marketing': True, 'functional': True}
        )
        product = Product.objects.create(
            name='Nonce Book',
            slug='nonce-book',
            sku='NB-1',
            price=Money(Decimal('12.00'), 'USD'),
            status='active',
        )
        self.client.post(f'/cart/add/{product.id}/', {'quantity': 1})
        session = self.client.session
        session['checkout_address'] = {
            'email': 'shopper@example.test',
            'first_name': 'Ana',
            'last_name': 'Shopper',
            'address_line1': '1 Main St',
            'city': 'Springfield',
            'state': 'IL',
            'postal_code': '62701',
            'country': 'US',
        }
        session['checkout_order_number'] = 'ORD-NONCE'
        session['checkout_client_secret'] = 'pi_x_secret_y'
        session.save()
        plan = Plan.objects.create(
            name='Reader',
            slug='reader',
            price=Money(Decimal('9.99'), 'USD'),
            interval='month',
            provider='stripe',
        )
        self.pages = [
            '/cart/',
            '/checkout/quick/',
            '/checkout/',
            '/checkout/shipping/',
            '/checkout/review/',
            '/checkout/payment/',
            '/account/payment-methods/',
            f'/membership/subscribe/{plan.id}/',
        ]

    def use_theme(self, name):
        from themes.registry import theme_registry

        override = override_settings(MORPHEUS_ACTIVE_THEME=name)
        override.enable()
        self.addCleanup(override.disable)
        previous = theme_registry._active_name
        self.addCleanup(setattr, theme_registry, '_active_name', previous)
        theme_registry.set_active(name)

    def use_tracking(self, variant):
        for field, value in _TRACKING[variant].items():
            setattr(self.tracking, field, value)
        self.tracking.save()
        cache.clear()

    def check(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, f'{url} answered {response.status_code}')
        self.assertFalse(response.has_header('Content-Security-Policy-Report-Only'))
        nonces = _NONCE.findall(response.get('Content-Security-Policy', ''))
        self.assertEqual(len(nonces), 1, 'the payment page sends one enforced, nonced policy')
        html = response.content.decode()
        page = parse(html)
        self.assertEqual(page.handlers, [], 'inline handlers do not run under the policy')
        loaded = []
        for script in filter(runs, page.scripts):
            tag = f'<script {script["attrs"]}> {script["body"][:80]!r}'
            self.assertEqual(script['attrs'].get('nonce'), nonces[0], tag)
            src = script['attrs'].get('src') or ''
            if src.startswith(('http:', 'https:', '//')):
                loaded.append(urlsplit(src if ':' in src.split('/')[0] else f'https:{src}'))
            for host, path in _SCRIPT_URL.findall(script['body']):
                loaded.append(urlsplit(f'https://{host}{path}'))
        for url_parts in loaded:
            self.assertTrue(
                origin_allowed(url_parts.hostname),
                f'{url_parts.hostname} is not in PAYMENT_PAGE_SCRIPT_ORIGINS',
            )
            if url_parts.hostname == 'cdn.jsdelivr.net':
                self.assertRegex(url_parts.path, _JSDELIVR_PINNED)
        return html

    def test_every_script_on_every_payment_page_carries_the_nonce(self):
        for theme in THEMES:
            for variant in _TRACKING:
                self.use_theme(theme)
                self.use_tracking(variant)
                for url in self.pages:
                    with self.subTest(theme=theme, tracking=variant, page=url):
                        html = self.check(url)
                        if url == '/cart/':
                            for marker in _EXPECTED_ON_THE_CART:
                                self.assertIn(marker, html)

    def test_other_pages_keep_the_report_only_policy(self):
        response = self.client.get('/')
        self.assertTrue(response.has_header('Content-Security-Policy-Report-Only'))
        self.assertFalse(response.has_header('Content-Security-Policy'))
