"""The dashboard's Tailwind is a stylesheet built ahead of time (v0.136.0).

The Play CDN compiled classes in the browser, which needed ``'unsafe-eval'`` in
the dashboard's CSP. ``admin_dashboard/frontend`` now builds them from every
app's templates, Python and scripts, and CI rebuilds the file and fails when the
committed one differs. A class built from pieces (``'bg-' + tone``) appears in
no source, so no build has it: the rendered pages are checked too. Every class
on them that reads like a Tailwind utility must have a rule, in the stylesheet
or in the page's own CSS.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import TestCase

from plugins.installed.admin_dashboard import navigation

_REPO = Path(__file__).resolve().parents[4]
_STYLESHEET = 'admin_dashboard/tailwind.css'
_LINK = re.compile(r'<link rel="stylesheet" href="/static/([^"?]+)"')
_STYLE = re.compile(r'<style[^>]*>(.*?)</style>', re.S)
_CLASS_ATTR = re.compile(r'\sclass="([^"{}]*)"')
_SELECTOR_CLASS = re.compile(r'\.((?:\\[0-9a-fA-F]{1,6} ?|\\.|[A-Za-z0-9_-])+)')
_ESCAPE = re.compile(r'\\([0-9a-fA-F]{1,6}) ?|\\(.)')
# Tailwind's utility families. A token outside them (btn, card, js-*) is the
# shell's own class or a hook, and has no business in this check.
_UTILITY = re.compile(
    r'^(?:[a-z0-9-]+:)*-?(?:'
    r'p[xytrblse]?|m[xytrblse]?|space-[xy]|gap(?:-[xy])?|[wh]|min-[wh]|max-[wh]|size|'
    r'inset(?:-[xy])?|top|right|bottom|left|z|order|basis|grow|shrink|'
    r'flex|grid-cols|grid-rows|col-span|row-span|col-start|col-end|items|justify|self|place|content|'
    r'text|font|leading|tracking|line-clamp|whitespace|break|truncate|'
    r'bg|from|via|to|border(?:-[xytrbl])?|rounded(?:-[a-z]+)?|ring(?:-offset)?|divide(?:-[xy])?|'
    r'shadow|opacity|outline|decoration|underline-offset|'
    r'overflow(?:-[xy])?|object|aspect|cursor|select|pointer-events|'
    r'translate-[xy]|scale(?:-[xy])?|rotate|transition|duration|ease|delay|animate|'
    r'blur|backdrop-blur|fill|stroke|accent|list|columns'
    r')(?:-[^\s]+)?$'
    r'|^(?:[a-z0-9-]+:)*(?:hidden|block|inline|inline-block|inline-flex|inline-grid|grid|contents|'
    r'static|fixed|absolute|relative|sticky|visible|invisible|sr-only|not-sr-only|'
    r'uppercase|lowercase|capitalize|italic|underline|line-through|no-underline|'
    r'antialiased|tabular-nums|shrink-0|grow|truncate|container|mx-auto|resize|resize-none)$'
)


def _unescape(name: str) -> str:
    # A selector escapes a class's punctuation: `\:` and `\[`, a comma as `\2c `.
    return _ESCAPE.sub(lambda m: chr(int(m[1], 16)) if m[1] else m[2], name)


def _classes(css: str) -> set[str]:
    found = set()
    for selector in re.findall(r'([^{}]+)\{', css):
        if not selector.lstrip().startswith('@'):
            found.update(_unescape(c) for c in _SELECTOR_CLASS.findall(selector))
    return found


def _stylesheet() -> str:
    path = finders.find(_STYLESHEET)
    assert path, f'{_STYLESHEET} is missing: build it (admin_dashboard/frontend/README.md)'
    return Path(path).read_text()


class TailwindStylesheetTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='tw-owner',
            email='tw-owner@example.test',
            password='x',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)

    def test_the_dashboard_links_the_built_stylesheet(self):
        body = self.client.get('/dashboard/').content.decode()
        self.assertIn(f'/static/{_STYLESHEET}', body)
        self.assertNotIn('cdn.tailwindcss.com', body)

    def test_the_stylesheet_comes_last_in_the_head(self):
        # The CDN appended its styles to the end of the head, after the shell's
        # own rules, and those rules were written for that: `lg:hidden` beats the
        # shell's `display` on a control of the same weight. Linked first, the
        # stylesheet lost to them, and the mobile menu buttons showed on desktop.
        head = self.client.get('/dashboard/').content.decode().split('</head>')[0]
        tailwind = head.index(f'/static/{_STYLESHEET}')
        self.assertGreater(tailwind, head.rindex('<style'))
        self.assertEqual(head.rindex('<link rel="stylesheet"'), head.rindex('<link', 0, tailwind))

    def test_no_dashboard_template_loads_the_play_cdn(self):
        # The storefront's fallback base (no theme installed) keeps its own CDN
        # config; every theme ships a base of its own, and the storefront's CSP
        # only reports.
        allowed = {_REPO / 'plugins/installed/storefront/templates/storefront/base.html'}
        roots = [_REPO / 'plugins', _REPO / 'core', _REPO / 'templates']
        offenders = [
            str(path.relative_to(_REPO))
            for root in roots
            for path in root.rglob('*.html')
            if path not in allowed and 'cdn.tailwindcss.com' in path.read_text(errors='ignore')
        ]
        self.assertEqual(offenders, [])

    def test_every_utility_on_a_dashboard_page_has_a_rule(self):
        built = _classes(_stylesheet())
        urls = ['/dashboard/'] + [e.url for e in [*navigation.tabs(self.user), *navigation.tools()]]
        missing = []
        for url in dict.fromkeys(urls):
            resp = self.client.get(url)
            if resp.status_code != 200 or 'html' not in resp.get('Content-Type', ''):
                continue
            body = resp.content.decode()
            own = set()
            for css in _STYLE.findall(body):
                own |= _classes(css)
            for href in _LINK.findall(body):
                path = finders.find(href)
                if path and href != _STYLESHEET:
                    own |= _classes(Path(path).read_text(errors='ignore'))
            for attr in _CLASS_ATTR.findall(body):
                for token in attr.split():
                    if _UTILITY.match(token) and token not in built and token not in own:
                        missing.append((url, token))
        self.assertEqual(
            sorted(set(missing)),
            [],
            'a class with no CSS: write it whole in a template, Python or script, then '
            'rebuild (admin_dashboard/frontend/README.md)',
        )
