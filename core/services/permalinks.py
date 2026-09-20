"""Safe, SEO-compatible storefront permalink resolution.

This module is deliberately a *path generator*, not a URL router.  Changing a
stored template cannot silently move an indexed page: views and SEO redirect
rules must opt in separately.  This keeps navigation, canonicals and sitemap
contributors on one contract while protecting existing URLs.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import quote

DEFAULT_TEMPLATES: dict[str, str] = {
    'product': '/products/{slug}/',
    'category': '/category/{slug}/',
    'booking': '/bookings/{slug}/',
    'place': '/places/{slug}/',
    'hotel': '/hotels/{slug}/',
    'event': '/events/{slug}/',
    'journal': '/journal/{slug}/',
    'vendor': '/vendors/{slug}/',
    'cms_page': '/p/{slug}/',
}
_SLUG_TYPES = frozenset(DEFAULT_TEMPLATES)
_TOKEN_RE = re.compile(r'\{([a-z_]+)\}')


class PermalinkError(ValueError):
    """A merchant permalink setting is unsafe or cannot produce a URL."""


@dataclass(frozen=True)
class PermalinkResolver:
    templates: Mapping[str, str]

    @classmethod
    def from_settings(cls, settings) -> PermalinkResolver:
        stored = getattr(settings, 'permalink_templates', None) or {}
        if not isinstance(stored, dict):
            stored = {}
        merged = {**DEFAULT_TEMPLATES, **{k: v for k, v in stored.items() if k in _SLUG_TYPES}}
        return cls(merged)

    def path(self, kind: str, *, slug: str) -> str:
        if kind not in _SLUG_TYPES:
            raise PermalinkError(f'Unknown permalink type: {kind}')
        template = self.templates.get(kind, DEFAULT_TEMPLATES[kind])
        validate_template(kind, template)
        if not slug:
            raise PermalinkError(f'{kind} permalink requires a slug')
        return template.format(slug=quote(str(slug).strip('/'), safe='-._~'))


def validate_template(kind: str, template: str) -> None:
    """Accept only normalized local slug paths safe for SEO canonical use."""
    if kind not in _SLUG_TYPES:
        raise PermalinkError(f'Unknown permalink type: {kind}')
    if not isinstance(template, str) or not template.startswith('/') or not template.endswith('/'):
        raise PermalinkError('Permalink must be a local path starting and ending with /.')
    if (
        '//' in template
        or '?' in template
        or '#' in template
        or '\\' in template
        or '://' in template
    ):
        raise PermalinkError(
            'Permalink must be a clean local path without query, fragment or host.'
        )
    tokens = set(_TOKEN_RE.findall(template))
    if tokens != {'slug'} or template.count('{slug}') != 1:
        raise PermalinkError('Permalink must contain exactly one {slug} placeholder.')
    if _TOKEN_RE.sub('', template).find('{') >= 0:
        raise PermalinkError('Permalink has an invalid placeholder.')


def resolver_for_settings(settings=None) -> PermalinkResolver:
    if settings is None:
        from core.models import StoreSettings

        settings = StoreSettings.objects.first()
    return PermalinkResolver.from_settings(settings)
