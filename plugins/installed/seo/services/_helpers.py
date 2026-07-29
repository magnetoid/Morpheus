"""Shared SEO service primitives.

The ``ResolvedMeta`` dataclass + site-wide accessors live here so each
feature-area module (meta, jsonld, sitemaps, …) can import them
without pulling in everything else.
"""

# ruff: noqa: PLR0912, PLC0415, S112, S110, I001, SIM105
# Inline imports avoid circular deps with seo.models / plugins.registry;
# the broad try/except guards keep meta resolution working during early
# boot + tests. Same convention as views_split/products.py.

from __future__ import annotations

import html as _html
import json
import logging
import re as _re
from dataclasses import dataclass


from morpheus.core import site_base_url
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
    document_title: str = ''  # branded <title> (title_template applied); falls back to title
    description: str = ''
    og_title: str = ''
    og_description: str = ''
    og_image: str = ''
    og_type: str = 'website'
    twitter_card: str = 'summary_large_image'
    canonical_url: str = ''
    robots: str = 'index, follow'
    keywords: str = ''
    # Site identity, resolved ONCE by resolve_meta (og:site_name / twitter:site).
    # to_html renders from these fields — it must never query the DB itself,
    # since it runs on every storefront <head>.
    site_name: str = ''
    twitter_site: str = ''
    structured_data: dict = None  # type: ignore[assignment]
    # Standalone JSON-LD blocks (visual schema editor): each emitted as its own
    # <script>, separate from the single merged structured_data dict above.
    extra_blocks: list = None  # type: ignore[assignment]

    def to_html(self) -> str:  # noqa: PLR0915 — linear list of head-meta appends; splitting hurts readability
        """Render the meta tags as an HTML fragment for the <head>."""
        parts: list[str] = []
        doc_title = self.document_title or self.title
        if doc_title:
            parts.append(f'<title>{escape(doc_title)}</title>')
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
        # og:image is already absolute — resolve_meta absolutizes it (social/AI
        # link previews reject relative /media/… paths), so both these tags and
        # the JSON-LD image get the same absolute URL with zero work here.
        og_image_abs = self.og_image
        if og_title:
            parts.append(f'<meta property="og:title" content="{escape(og_title)}">')
        if og_desc:
            parts.append(f'<meta property="og:description" content="{escape(og_desc)}">')
        parts.append(f'<meta property="og:type" content="{escape(self.og_type)}">')
        if self.canonical_url:
            parts.append(f'<meta property="og:url" content="{escape(self.canonical_url)}">')
        if self.site_name:
            parts.append(f'<meta property="og:site_name" content="{escape(self.site_name)}">')
        # og:locale — matches the Content-Language header the markets
        # middleware emits; falls back to en_US.
        try:
            from django.conf import settings as _s

            locale = (getattr(_s, 'LANGUAGE_CODE', 'en-US') or 'en-US').replace('-', '_')
        except Exception:  # noqa: BLE001
            locale = 'en_US'
        parts.append(f'<meta property="og:locale" content="{escape(locale)}">')
        if og_image_abs:
            parts.append(f'<meta property="og:image" content="{escape(og_image_abs)}">')
            parts.append(f'<meta property="og:image:secure_url" content="{escape(og_image_abs)}">')
            parts.append('<meta property="og:image:width" content="1200">')
            parts.append('<meta property="og:image:height" content="630">')
            if og_title:
                parts.append(f'<meta property="og:image:alt" content="{escape(og_title)}">')

        parts.append(f'<meta name="twitter:card" content="{escape(self.twitter_card)}">')
        if self.twitter_site:
            handle = (
                self.twitter_site if self.twitter_site.startswith('@') else f'@{self.twitter_site}'
            )
            parts.append(f'<meta name="twitter:site" content="{escape(handle)}">')
        if og_title:
            parts.append(f'<meta name="twitter:title" content="{escape(og_title)}">')
        if og_desc:
            parts.append(f'<meta name="twitter:description" content="{escape(og_desc)}">')
        if og_image_abs:
            parts.append(f'<meta name="twitter:image" content="{escape(og_image_abs)}">')

        if self.structured_data:
            parts.append(
                '<script type="application/ld+json">'
                + json.dumps(self.structured_data, separators=(',', ':'))
                + '</script>'
            )
        for block in self.extra_blocks or []:
            if block:
                parts.append(
                    '<script type="application/ld+json">'
                    + json.dumps(block, separators=(',', ':'))
                    + '</script>'
                )
        return '\n'.join(parts)


def _site_base_url() -> str:
    return site_base_url()


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


# Same escaping Django's json_script applies: neutralise the three characters
# that can break out of a <script type="application/ld+json"> element, plus the
# two line separators that are invalid raw in a <script> body. json.dumps
# escapes quotes/backslashes but passes </script> through verbatim, so free-text
# fields (product name/description) could otherwise inject a closing tag + script.
_JSONLD_ESCAPES = {
    0x3C: '\\u003C',  # <
    0x3E: '\\u003E',  # >
    0x26: '\\u0026',  # &
    0x2028: '\\u2028',  # line separator (invalid raw in a <script> body)
    0x2029: '\\u2029',  # paragraph separator
}


def _jsonld_dump(obj: dict) -> str:
    return json.dumps(obj, separators=(',', ':'), ensure_ascii=False).translate(_JSONLD_ESCAPES)


def ai_answer_for(obj) -> str:
    """Return the merchant's quotable TL;DR / key-answer for ``obj``.

    Stored as a metafield ``namespace='seo', key='ai_answer'`` — the
    same convention as ``seo.same_as``. This is the concise, factual
    summary AI engines can lift verbatim into an answer ("AEO answer").
    Empty string when unset or the metafields plugin is uninstalled.
    """
    if obj is None:
        return ''
    try:
        from django.contrib.contenttypes.models import ContentType
        from plugins.installed.metafields.models import Metafield

        ct = ContentType.objects.get_for_model(type(obj))
        m = Metafield.objects.filter(
            content_type=ct,
            object_id=str(obj.pk),
            namespace='seo',
            key='ai_answer',
        ).first()
        return strip_html(m.value) if (m and m.value) else ''
    except Exception:  # noqa: BLE001 — never break a render/audit over a missing plugin
        return ''


def _plugin(name: str):
    """Resolve any live plugin instance by name via the registry.

    Wrapper around the two registry accessor names (legacy ``get`` vs
    new ``get_plugin``). Returns ``None`` when the registry isn't ready
    or the plugin is absent — callers treat that as "use defaults"."""
    try:
        from plugins.registry import plugin_registry

        for attr in ('get', 'get_plugin'):
            fn = getattr(plugin_registry, attr, None)
            if callable(fn):
                try:
                    p = fn(name)
                except Exception:  # noqa: BLE001
                    continue
                if p is not None:
                    return p
    except Exception:  # noqa: BLE001
        pass
    return None


def _seo_plugin():
    """Resolve the live SEO plugin instance via the plugin registry."""
    return _plugin('seo')


def _return_window_days() -> int:
    """The store's real return window (days) from the returns_portal plugin, or
    0 if that plugin is absent, inactive, or unconfigured.

    Lets Product JSON-LD carry the merchant's ACTUAL return policy (Google 2026
    merchant-listing recommendation) sourced from the plugin that owns returns —
    never a fabricated value. Disable-safe: a disabled returns_portal contributes
    no return policy to the markup."""
    try:
        from plugins.registry import plugin_registry

        is_active = getattr(plugin_registry, 'is_active', None)
        if callable(is_active) and not is_active('returns_portal'):
            return 0
    except Exception:  # noqa: BLE001
        pass
    rp = _plugin('returns_portal')
    if rp is None:
        return 0
    try:
        return int(rp.get_config_value('return_window_days', 0) or 0)
    except Exception:  # noqa: BLE001
        return 0
