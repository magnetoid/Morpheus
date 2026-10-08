"""Keep a visitor in their language: internal links on a language-prefixed page.

The storefront is language-routed (`i18n_patterns`, the default language
unprefixed). `{% url %}` adds the prefix, but themes, apps and the merchant's
own CMS copy write links as plain paths (`href="/bookings/"`). On
montenegro-experience.me 106 of the 108 internal links on `/sr/` pointed into
the English tree: a Serbian visitor left Serbian on the first click, and the
Serbian pages linked only to English ones.

On a page served under a language prefix, every `<a href>` and `<form action>`
whose path is a language-routed page gets that prefix. The test is the URL
resolver itself, so anything outside the language tree — `/auth/`,
`/dashboard/`, files, feeds, the language switcher's endpoint — stays exactly
as written. `<link>` tags are machine references (manifest, feeds, hreflang
alternates that must keep naming the other language) and are never touched.
"""

from __future__ import annotations

import re
from functools import lru_cache

_TAG = re.compile(r'<(?:a|form)\b[^>]*>', re.IGNORECASE)
_TARGET = re.compile(r'(\s(?:href|action)=")(/(?!/)[^"]*)(")', re.IGNORECASE)
# A link that declares its language (a switcher's "English") names that tree.
_DECLARES_LANGUAGE = re.compile(r'\s(?:hreflang|lang)=', re.IGNORECASE)


@lru_cache(maxsize=4096)
def _language_routed(language: str, path: str) -> bool:
    """Whether `/<language><path>` is a page (a route under `i18n_patterns`)."""
    from django.urls import Resolver404, resolve
    from django.utils import translation

    with translation.override(language):
        try:
            resolve(f'/{language}{path}')
        except Resolver404:
            return False
    return True


def localize_links(html: str, language: str) -> str:
    """`html` with its internal page links moved into `language`'s tree."""
    prefix = f'/{language}'

    def swap(match: re.Match) -> str:
        url = match.group(2)
        if url == prefix or url.startswith((f'{prefix}/', f'{prefix}?')):
            return match.group(0)
        path = url.split('#', 1)[0].split('?', 1)[0]
        if not path or not _language_routed(language, path):
            return match.group(0)
        return f'{match.group(1)}{prefix}{url}{match.group(3)}'

    def tag(match: re.Match) -> str:
        if _DECLARES_LANGUAGE.search(match.group(0)):
            return match.group(0)
        return _TARGET.sub(swap, match.group(0), count=1)

    return _TAG.sub(tag, html)


def page_language(request) -> str:
    """The prefixed language this request is served in, or `''`."""
    from django.conf import settings

    language = (getattr(request, 'LANGUAGE_CODE', '') or '').split('-')[0]
    default = (getattr(settings, 'LANGUAGE_CODE', '') or '').split('-')[0]
    if not language or language == default:
        return ''
    path = getattr(request, 'path_info', '') or ''
    return language if path.startswith(f'/{language}/') else ''


class LocalizedLinksMiddleware:
    """Rewrite internal links on HTML pages served under a language prefix.

    Sits inside GZip (it reads the body) and after LocaleMiddleware (it reads
    `request.LANGUAGE_CODE`).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        language = page_language(request)
        if not language or getattr(response, 'streaming', False):
            return response
        if 'text/html' not in (response.get('Content-Type') or ''):
            return response
        charset = response.charset or 'utf-8'
        content = response.content.decode(charset)
        rewritten = localize_links(content, language)
        if rewritten != content:
            response.content = rewritten.encode(charset)
            if response.has_header('Content-Length'):
                response['Content-Length'] = str(len(response.content))
        return response
