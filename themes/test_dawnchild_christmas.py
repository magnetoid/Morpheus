"""Dawnchild's Christmas look (v0.186.0).

Three theme settings decide it: `christmas_look` (off, dates or on) and the two
days, written DD-MM, between which `dates` shows it every year on the store's
clock. The rule lives in `themes/library/dawnchild/christmas.py`; the theme's
`christmas_on()` reads it for the templates.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import re
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from core.tests.test_payment_page_csp import _RUN_TYPES
from plugins import config_schema
from themes.library.dawnchild.christmas import is_on, parse_day
from themes.registry import theme_registry
from themes.test_dawnchild import _Dawnchild

DATES = {'christmas_look': 'dates'}


class ChristmasDayRuleTests(SimpleTestCase):
    def test_the_default_is_off(self):
        self.assertIs(is_on({}, date(2026, 12, 25)), False)

    def test_on_shows_it_any_day(self):
        self.assertIs(is_on({'christmas_look': 'on'}, date(2026, 7, 1)), True)

    def test_dates_use_the_default_range_across_new_year(self):
        for day, expected in (
            (date(2026, 11, 30), False),
            (date(2026, 12, 1), True),
            (date(2026, 12, 31), True),
            (date(2027, 1, 1), True),
            (date(2027, 1, 6), True),
            (date(2027, 1, 7), False),
        ):
            with self.subTest(day=day):
                self.assertIs(is_on(DATES, day), expected)

    def test_dates_inside_one_year(self):
        config = {**DATES, 'christmas_from': '10-12', 'christmas_until': '24-12'}
        for day, expected in (
            (date(2026, 12, 9), False),
            (date(2026, 12, 10), True),
            (date(2026, 12, 24), True),
            (date(2026, 12, 25), False),
        ):
            with self.subTest(day=day):
                self.assertIs(is_on(config, day), expected)

    def test_a_date_that_is_not_a_day_falls_back_to_its_default(self):
        for bad in ('31-02', '1 Dec', '', '00-12', '12-13'):
            with self.subTest(bad=bad):
                config = {**DATES, 'christmas_from': bad}
                self.assertIs(is_on(config, date(2026, 12, 1)), True)
                self.assertIs(is_on(config, date(2026, 11, 30)), False)
        self.assertEqual(parse_day('29-02'), (2, 29))
        self.assertEqual(parse_day('01-12'), (12, 1))
        self.assertIsNone(parse_day('31-02'))

    def test_an_unknown_mode_is_off(self):
        self.assertIs(is_on({'christmas_look': 'yes'}, date(2026, 12, 25)), False)

    def test_the_schema_declares_the_three_settings(self):
        props = theme_registry.get('dawnchild').get_config_schema()['properties']
        self.assertEqual(props['christmas_look']['enum'], ['off', 'dates', 'on'])
        self.assertEqual(props['christmas_look']['default'], 'off')
        self.assertEqual(props['christmas_from']['default'], '01-12')
        self.assertEqual(props['christmas_until']['default'], '06-01')
        for key, example in (('christmas_from', '01-12'), ('christmas_until', '06-01')):
            self.assertEqual(props[key]['pattern'], r'\d{2}-\d{2}')
            self.assertEqual(props[key]['examples'], [example])

    def test_linda_cannot_store_a_date_not_written_dd_mm(self):
        prop = theme_registry.get('dawnchild').get_config_schema()['properties']['christmas_from']
        with self.assertRaises(config_schema.SettingError) as ctx:
            config_schema.clean('christmas_from', prop, '1 Dec')
        self.assertIn('01-12', str(ctx.exception))
        self.assertEqual(config_schema.clean('christmas_from', prop, '24-12'), '24-12')


class ChristmasStoreClockTests(TestCase):
    def test_the_store_clock_decides_the_day(self):
        theme = theme_registry.get('dawnchild')
        theme.invalidate_config_cache()
        self.addCleanup(theme.invalidate_config_cache)
        theme.set_config('christmas_look', 'dates')
        late = datetime(2026, 11, 30, 23, 30, tzinfo=UTC)
        with (
            patch('core.utils.site.store_timezone', return_value=ZoneInfo('Europe/Belgrade')),
            patch('django.utils.timezone.now', return_value=late),
        ):
            self.assertIs(theme.christmas_on(), True)


# ── The look on the pages (Task 3) ───────────────────────────────────────────

ROOT = Path(settings.BASE_DIR) / 'themes' / 'library' / 'dawnchild'
STATIC = ROOT / 'static' / 'dawnchild'
PIECES = ('hero', 'garland', 'frost', 'drift', 'cap', 'scenery', 'window', 'smoke', 'letter')
PAUSE = re.compile(r'<button[^>]*data-xmas-pause[^>]*>')


class ChristmasPagesTests(_Dawnchild):
    def _look(self, mode: str) -> None:
        theme = theme_registry.get('dawnchild')
        theme.set_config('christmas_look', mode)
        theme.invalidate_config_cache()
        self.addCleanup(theme.invalidate_config_cache)

    def _home(self) -> str:
        data = {'featuredProducts': [], 'collections': [], 'categories': []}
        with (
            patch(
                'plugins.installed.personalisation.services.rank_for_visitor',
                side_effect=lambda request, products, surface: products,
            ),
            patch('plugins.installed.storefront.views.home.internal_graphql', return_value=data),
        ):
            return self._get('/')

    def test_off_renders_nothing_of_it(self):
        for body in (self._home(), self._get('/products/')):
            for needle in ('data-christmas', 'christmas.css', 'christmas.js', 'data-xmas'):
                self.assertNotIn(needle, body)

    def test_on_renders_every_piece_on_the_home_page(self):
        self._look('on')
        body = self._home()
        head = body.split('</head>', 1)[0]
        self.assertRegex(head, r'<link rel="stylesheet" href="[^"]*dawnchild/christmas\.css')
        self.assertRegex(
            body, r'<script nonce="[^"]+" src="[^"]*dawnchild/christmas\.js" defer></script>'
        )
        self.assertRegex(body, r'<body [^>]*data-christmas')
        for piece in PIECES:
            with self.subTest(piece=piece):
                self.assertEqual(body.count(f'data-xmas="{piece}"'), 1)
        self.assertIn('<canvas data-xmas-snow="hero"', body)
        self.assertIn('<canvas data-xmas-snow="footer"', body)
        plaque = body.split('class="hw-plaque"', 1)[1].split('</h2>', 1)[0]
        self.assertIn('data-xmas="cap"', plaque)
        buttons = PAUSE.findall(body)
        self.assertEqual(len(buttons), 2)
        for button in buttons:
            self.assertIn(' hidden', button)
            self.assertIn('aria-pressed="false"', button)
            self.assertIn('data-label-pause="Pause the snow"', button)
            self.assertIn('data-label-play="Let it snow"', button)
            self.assertIn('aria-label="Pause the snow"', button)

    def test_on_other_pages_has_the_footer_and_header_but_no_hero(self):
        self._look('on')
        body = self._get('/products/')
        self.assertRegex(body, r'<body [^>]*data-christmas')
        self.assertIn('data-xmas="scenery"', body)
        self.assertEqual(len(PAUSE.findall(body)), 1)
        self.assertNotIn('data-xmas="hero"', body)

    def test_dates_mode_follows_the_store_day(self):
        self._look('dates')
        with patch('core.utils.site.store_today', return_value=date(2026, 12, 15)):
            self.assertRegex(self._home(), r'<body [^>]*data-christmas')
        with patch('core.utils.site.store_today', return_value=date(2026, 11, 15)):
            self.assertNotIn('data-christmas', self._home())

    def test_the_basket_under_the_look_keeps_the_payment_page_policy(self):
        self._look('on')
        body = self._get('/cart/')
        self.assertIn('data-christmas', body)
        for tag in re.findall(r'<script\b[^>]*>', body):
            kind = re.search(r'\stype="([^"]*)"', tag)
            if kind and kind.group(1) not in _RUN_TYPES:
                continue  # a data block (JSON-LD, a JSON config) never runs
            self.assertIn('nonce="', tag, tag)
        self.assertIsNone(re.search(r'\son[a-z]+\s*=\s*["\']', body))


def _rules(css: str) -> list[tuple[str, str]]:
    """(selector, body) of each innermost rule, comments removed."""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    return [(s.strip(), b) for s, b in re.findall(r'([^{}]+)\{([^{}]*)\}', css)]


class ChristmasFilesTests(SimpleTestCase):
    def test_the_stylesheet_holds_still_without_script_or_with_reduced_motion(self):
        css = (STATIC / 'christmas.css').read_text(encoding='utf-8')
        rules = _rules(css)
        for selector, body in rules:
            if re.search(r'(^|[;\s])animation\s*:', body) and 'animation: none' not in body:
                for part in selector.split(','):
                    self.assertTrue(part.strip().startswith('.js [data-christmas]'), selector)
        reduced = css.split('@media (prefers-reduced-motion: reduce)', 1)
        self.assertEqual(len(reduced), 2, 'no reduced-motion block')
        block = reduced[1].split('\n}', 1)[0]
        self.assertIn('animation: none', block)
        self.assertRegex(block, r'\[data-xmas-snow\][^{]*\{[^}]*display: none')
        self.assertRegex(block, r'\.xmas-pause[^{]*\{[^}]*display: none')
        paused = [b for s, b in rules if '[data-christmas-paused]' in s]
        self.assertTrue(paused)
        self.assertTrue(all('animation-play-state: paused' in b for b in paused))
        phone = css.split('@media (max-width: 600px)', 1)
        self.assertEqual(len(phone), 2, 'no phone block')
        self.assertRegex(phone[1].split('\n}', 1)[0], r'\.foot-inner[^{]*\{[^}]*padding-bottom')

    def test_the_script_waits_for_the_picture_and_stops_when_unseen(self):
        js = (STATIC / 'christmas.js').read_text(encoding='utf-8')
        for needle in (
            'addEventListener',
            'IntersectionObserver',
            'visibilitychange',
            'MutationObserver',
            'prefers-reduced-motion',
            '.complete',
        ):
            self.assertIn(needle, js)
        for needle in ('innerHTML', 'eval(', 'document.write', 'onclick'):
            self.assertNotIn(needle, js)
        key = 'dawnchild:christmas-paused'
        self.assertIn(key, js)
        for line in (ln for ln in js.splitlines() if key in ln):
            self.assertIn('try {', line, line)
