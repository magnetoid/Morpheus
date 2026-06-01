"""Shared SEO service primitives.

The ``ResolvedMeta`` dataclass + site-wide accessors live here so each
feature-area module (meta, jsonld, sitemaps, …) can import them
without pulling in everything else.
"""

# ruff: noqa: PLR0912, PLC0415, S112, S110
# Inline imports avoid circular deps with seo.models / plugins.registry;
# the broad try/except guards keep meta resolution working during early
# boot + tests. Same convention as views_split/products.py.

from __future__ import annotations

import html as _html
import json
import logging
import re as _re
from dataclasses import dataclass

from django.conf import settings
from django.utils.html import escape, strip_tags

logger = logging.getLogger('morpheus.seo')


def strip_html(text) -> str:
    """Flatten HTML to plain text for meta tags, JSON-LD, and data-attrs.

    ``short_description`` is a rich-text (HTML) field, so plain-text
    consumers must not leak literal ``<p>`` tags or ``&#x27;`` entities.
    """
    if not text:
        return ''
    plain = _html.unescape(strip_tags(str(text)))
    return _re.sub(r'\s+', ' ', plain).strip()


@dataclass(slots=True)
class ResolvedMeta:
    """Concrete, fallback-resolved meta values ready for rendering."""

    title: str = ''
    description: str = ''
    og_title: str = ''
    og_description: str = ''
    og_image: str = ''
    og_type: str = 'website'
    twitter_card: str = 'summary_large_image'
    canonical_url: str = ''
    robots: str = 'index, follow'
    keywords: str = ''
    structured_data: dict = None  # type: ignore[assignment]

    def to_html(self) -> str:
        """Render the meta tags as an HTML fragment for the <head>."""
        parts: list[str] = []
        if self.title:
            parts.append(f'<title>{escape(self.title)}</title>')
        if self.description:
            parts.append(f'<meta name="description" content="{escape(self.description)}">')
        if self.keywords:
            parts.append(f'<meta name="keywords" content="{escape(self.keywords)}">')
        if self.robots:
            # Append AI-snippet directives unless the merchant explicitly
            # set noindex — these unlock full AI Overview snippets +
            # large image previews without changing index behaviour.
            ai_directives = 'max-snippet:-1, max-image-preview:large, max-video-preview:-1'
            robots = self.robots if 'noindex' in self.robots else f'{self.robots}, {ai_directives}'
            parts.append(f'<meta name="robots" content="{escape(robots)}">')
        if self.canonical_url:
            parts.append(f'<link rel="canonical" href="{escape(self.canonical_url)}">')

        og_title = self.og_title or self.title
        og_desc = self.og_description or self.description
        if og_title:
            parts.append(f'<meta property="og:title" content="{escape(og_title)}">')
        if og_desc:
            parts.append(f'<meta property="og:description" content="{escape(og_desc)}">')
        parts.append(f'<meta property="og:type" content="{escape(self.og_type)}">')
        # og:locale — matches the Content-Language header the markets
        # middleware emits; falls back to en_US.
        try:
            from django.conf import settings as _s

            locale = (getattr(_s, 'LANGUAGE_CODE', 'en-US') or 'en-US').replace('-', '_')
        except Exception:  # noqa: BLE001
            locale = 'en_US'
        parts.append(f'<meta property="og:locale" content="{escape(locale)}">')
        if self.og_image:
            parts.append(f'<meta property="og:image" content="{escape(self.og_image)}">')
            parts.append(f'<meta property="og:image:secure_url" content="{escape(self.og_image)}">')
            parts.append('<meta property="og:image:width" content="1200">')
            parts.append('<meta property="og:image:height" content="630">')
            if og_title:
                parts.append(f'<meta property="og:image:alt" content="{escape(og_title)}">')

        parts.append(f'<meta name="twitter:card" content="{escape(self.twitter_card)}">')
        if og_title:
            parts.append(f'<meta name="twitter:title" content="{escape(og_title)}">')
        if og_desc:
            parts.append(f'<meta name="twitter:description" content="{escape(og_desc)}">')
        if self.og_image:
            parts.append(f'<meta name="twitter:image" content="{escape(self.og_image)}">')

        if self.structured_data:
            parts.append(
                '<script type="application/ld+json">'
                + json.dumps(self.structured_data, separators=(',', ':'))
                + '</script>'
            )
        return '\n'.join(parts)


def _site_base_url() -> str:
    base = getattr(settings, 'SITE_BASE_URL', '').rstrip('/')
    if base:
        return base + '/'
    hosts = getattr(settings, 'ALLOWED_HOSTS', []) or ['localhost']
    return f'https://{hosts[0]}/'


def site_settings():
    """Return SiteSeoSettings singleton, fallback to fresh in-memory if DB empty."""
    try:
        from plugins.installed.seo.models import SiteSeoSettings

        return SiteSeoSettings.objects.first() or SiteSeoSettings(
            organization_name='',
            twitter_card_default='summary_large_image',
        )
    except Exception:  # noqa: BLE001
        from plugins.installed.seo.models import SiteSeoSettings

        return SiteSeoSettings(organization_name='')


def _seo_plugin_cfg() -> dict:
    """Read seo plugin's PluginConfig JSON. Used for fields that don't
    warrant a model migration (return policy, shipping fee, IndexNow
    key, AI crawler matrix, etc.). Returns ``{}`` when the plugin is
    not loaded yet (early boot / tests)."""
    try:
        from plugins.registry import plugin_registry

        p = plugin_registry.get('seo')
        if p is None:
            return {}
        return p.get_config() or {}
    except Exception:  # noqa: BLE001
        return {}


def _jsonld_dump(obj: dict) -> str:
    return json.dumps(obj, separators=(',', ':'), ensure_ascii=False)


def _seo_plugin():
    """Resolve the live SEO plugin instance via the plugin registry.

    Wrapper around the two registry accessor names (legacy ``get`` vs
    new ``get_plugin``) so callers don't have to repeat the
    fallback dance. Returns ``None`` when the registry isn't ready —
    every caller has to treat that as "config not available, use
    defaults"."""
    try:
        from plugins.registry import plugin_registry

        for attr in ('get', 'get_plugin'):
            fn = getattr(plugin_registry, attr, None)
            if callable(fn):
                try:
                    p = fn('seo')
                except Exception:  # noqa: BLE001
                    continue
                if p is not None:
                    return p
    except Exception:  # noqa: BLE001
        pass
    return None
