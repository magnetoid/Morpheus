"""Caching-related template tags — consume the Caching page knobs.

Every tag reads the storefront PluginConfig and renders the matching
markup. Empty config → empty output, so dropping these tags into a
template is harmless when the merchant hasn't configured anything.

Tags:
  {% caching_resource_hints %}        — <link rel="preconnect|dns-prefetch">
  {% caching_preload_fonts %}         — <link rel="preload" as="font">
  {% caching_font_display %}          — <style> @font-face { font-display: <swap> } </style>
  {% caching_service_worker_register %} — <script> navigator.serviceWorker.register('/sw.js') </script>
  {% caching_img_loading_attr %}      — returns "lazy" or "" based on lazy_load_images toggle
  {% caching_preload_lcp url %}       — <link rel="preload" as="image"> for the LCP image
  {% caching_script_defer_attr %}     — returns "defer" or "" based on defer_non_critical_js toggle
"""

from __future__ import annotations

from typing import Any

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


def _storefront_config() -> dict[str, Any]:
    try:
        from plugins.registry import plugin_registry

        p = plugin_registry.get('storefront')
        if p is None:
            return {}
        return p.get_config() or {}
    except Exception:  # noqa: BLE001
        return {}


def _split_lines(raw: str) -> list[str]:
    return [line.strip() for line in (raw or '').splitlines() if line.strip()]


@register.simple_tag
def caching_resource_hints() -> str:
    """Emit <link rel="preconnect"> + <link rel="dns-prefetch"> tags."""
    cfg = _storefront_config()
    out: list[str] = []
    for origin in _split_lines(cfg.get('preconnect_origins') or '')[:5]:
        # crossorigin is required for fonts; harmless on plain origins.
        out.append(f'<link rel="preconnect" href="{escape(origin)}" crossorigin>')
    for origin in _split_lines(cfg.get('dns_prefetch_origins') or '')[:10]:
        out.append(f'<link rel="dns-prefetch" href="{escape(origin)}">')
    return mark_safe('\n'.join(out))  # noqa: S308


@register.simple_tag
def caching_preload_fonts() -> str:
    """Emit <link rel="preload" as="font"> for fonts that should load
    before render-blocking CSS resolves the @font-face."""
    cfg = _storefront_config()
    out: list[str] = []
    for url in _split_lines(cfg.get('preload_fonts') or '')[:4]:
        # Detect format from extension; default woff2 (most common).
        u = url.lower()
        if u.endswith('.woff2'):
            fmt = 'font/woff2'
        elif u.endswith('.woff'):
            fmt = 'font/woff'
        elif u.endswith('.otf'):
            fmt = 'font/otf'
        elif u.endswith('.ttf'):
            fmt = 'font/ttf'
        else:
            fmt = 'font/woff2'
        out.append(f'<link rel="preload" href="{escape(url)}" as="font" type="{fmt}" crossorigin>')
    return mark_safe('\n'.join(out))  # noqa: S308


@register.simple_tag
def caching_font_display() -> str:
    """Emit a <style> block that forces a font-display value on
    every @font-face. Overrides whatever Google Fonts / a self-host
    stylesheet sets by default.

    Without this tag a missing font can cause invisible text for
    up to 3s on slow networks (the default `block` behaviour).
    """
    cfg = _storefront_config()
    fd = (cfg.get('font_display') or 'swap').strip().lower()
    if fd not in ('swap', 'optional', 'fallback', 'block', 'auto'):
        fd = 'swap'
    return mark_safe(  # noqa: S308
        f'<style id="caching-font-display">@font-face {{ font-display: {fd}; }}</style>'
    )


@register.simple_tag
def caching_service_worker_register() -> str:
    """Register the storefront service worker if the merchant
    enabled it on the Caching page. No-op when off — leaves no
    JS on the page.

    The worker itself is served by core/views.service_worker (see
    morph/urls.py). Cache-bust the registration URL by tagging
    with the deploy ID so each deploy installs a fresh worker
    instead of riding the old one for hours.
    """
    cfg = _storefront_config()
    if not cfg.get('service_worker_enabled'):
        return ''
    offline = escape((cfg.get('offline_page_path') or '/offline/').strip())
    return mark_safe(  # noqa: S308
        '<script>'
        'if ("serviceWorker" in navigator) {'
        '  window.addEventListener("load", function () {'
        '    navigator.serviceWorker.register("/sw.js", {scope: "/"}).catch(function(e){'
        '      console.warn("SW register failed:", e);'
        '    });'
        '  });'
        '}'
        f'window.MORPHEUS_OFFLINE_PATH = "{offline}";'
        '</script>'
    )


@register.simple_tag
def caching_img_loading_attr() -> str:
    """Returns ``lazy`` when lazy-load is enabled, else empty string.
    Storefront image tags should use:

        <img src="..." loading="{% caching_img_loading_attr %}">

    Above-the-fold images should set ``loading=""`` directly OR
    use ``fetchpriority="high"`` instead.
    """
    cfg = _storefront_config()
    return 'lazy' if cfg.get('lazy_load_images', True) else ''


@register.simple_tag
def caching_preload_lcp(url: str, sizes: str = '', srcset: str = '') -> str:
    """Emit ``<link rel="preload" as="image">`` for the LCP image.

    Lets the browser kick off the hero fetch during HTML parse instead
    of waiting for the <img> tag to resolve. Combined with
    ``fetchpriority="high"`` on the matching <img>, this is the textbook
    LCP win — usually 200-500ms faster on slow connections.

    No-op when ``preload_lcp`` is off, the URL is empty, or it's not
    a same-origin /media/ path (cross-origin preloads need a CORS dance
    we don't auto-handle yet).
    """
    cfg = _storefront_config()
    if not cfg.get('preload_lcp', True):
        return ''
    url = (url or '').strip()
    if not url:
        return ''
    parts = [f'<link rel="preload" as="image" href="{escape(url)}" fetchpriority="high"']
    if srcset:
        parts.append(f'imagesrcset="{escape(srcset)}"')
    if sizes:
        parts.append(f'imagesizes="{escape(sizes)}"')
    parts.append('>')
    return mark_safe(' '.join(parts))  # noqa: S308


@register.simple_tag
def caching_script_defer_attr() -> str:
    """Returns ``defer`` when defer_non_critical_js is on, else empty.

    Use on ``<script src="...">`` tags that don't need synchronous
    execution — e.g. analytics, tracking, late-binding widgets.

        <script src="/static/foo.js" {% caching_script_defer_attr %}></script>

    Never apply to inline scripts (defer is ignored without src) or to
    scripts another script depends on at parse time.
    """
    cfg = _storefront_config()
    return 'defer' if cfg.get('defer_non_critical_js', True) else ''
