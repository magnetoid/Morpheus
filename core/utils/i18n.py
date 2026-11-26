"""The language prefix of the page being served, for urls built by hand.

Storefront pages are language-routed (`i18n_patterns`, the default language
unprefixed). A url assembled as a string — a redirect target, an ItemList entry,
a breadcrumb — must carry the visitor's prefix, or a Serbian visitor is sent back
to English and a crawler is told the two trees are one page. Every hardcoded
`/genres/`, `/products/?q=` and `/journal/<slug>/` redirect did exactly that.
"""

from __future__ import annotations


def language_prefix(request) -> str:
    """`/sr` while serving the Serbian tree, `''` in the default language."""
    from django.conf import settings
    from django.utils.translation import get_language

    language = (get_language() or '').split('-')[0]
    default = (getattr(settings, 'LANGUAGE_CODE', '') or '').split('-')[0]
    codes = {code.split('-')[0] for code, _ in (getattr(settings, 'LANGUAGES', None) or [])}
    if not language or language == default or language not in codes:
        return ''
    path = getattr(request, 'path', '') or ''
    return f'/{language}' if path.startswith(f'/{language}/') else ''


def path_in_language(path: str, language: str) -> str:
    """`path` in a language's tree: `/journal/x/` in `sr` → `/sr/journal/x/`.

    The default language is unprefixed (`i18n_patterns(prefix_default_language=False)`);
    a language the store does not serve leaves the path as it is.
    """
    from django.conf import settings

    if not language or not path.startswith('/') or path.startswith('//'):
        return path
    codes = [code for code, _name in (getattr(settings, 'LANGUAGES', None) or [])]
    wanted = language.lower()
    # The code as LANGUAGES writes it (`zh-hans` stays `zh-hans`), else its base.
    code = next((c for c in codes if c.lower() == wanted), '') or next(
        (c for c in codes if c.lower() == wanted.split('-')[0]), ''
    )
    default = (getattr(settings, 'LANGUAGE_CODE', '') or '').lower()
    if not code or code.lower() in (default, default.split('-')[0]):
        return path
    if path.startswith(f'/{code}/'):
        return path
    return f'/{code}{path}'


def localized_path(request, path: str) -> str:
    """`path` in the visitor's language tree (`/hotels/x/` → `/sr/hotels/x/`)."""
    if not path.startswith('/') or path.startswith('//'):
        return path
    prefix = language_prefix(request)
    if not prefix or path.startswith(f'{prefix}/'):
        return path
    return f'{prefix}{path}'
