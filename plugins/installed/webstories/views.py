"""Public views for Web Stories.

``story_page`` serves a valid AMP ``<amp-story>`` document at
``/story/<slug>/``. The HTML is rendered server-side from the
per-product ``WebStory.panels`` JSON — no client JS at build time.

Cache-Control + Last-Modified mirror the SEO plugin's pattern so
crawlers hit the document with normal HTTP caching.
"""

from __future__ import annotations

import contextlib
import logging

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.http import http_date
from django.views.decorators.clickjacking import xframe_options_sameorigin

logger = logging.getLogger('morpheus.webstories')

_CACHE_MAX_AGE = 900
_CACHE_S_MAX_AGE = 3600


def _cache_headers(response: HttpResponse, last_modified=None) -> HttpResponse:
    response['Cache-Control'] = f'public, max-age={_CACHE_MAX_AGE}, s-maxage={_CACHE_S_MAX_AGE}'
    if last_modified is not None:
        with contextlib.suppress(AttributeError, OSError):
            response['Last-Modified'] = http_date(last_modified.timestamp())
    return response


def _site_settings():
    try:
        from core.models import StoreSettings  # noqa: PLC0415

        return (
            StoreSettings.load()
            if hasattr(StoreSettings, 'load')
            else StoreSettings.objects.first()
        )
    except Exception:  # noqa: BLE001
        return None


def _site_base_url(request: HttpRequest) -> str:
    return f'{request.scheme}://{request.get_host()}'.rstrip('/')


_RASTER = ('.png', '.jpg', '.jpeg', '.gif')


def _square_raster_url(img) -> str:
    """`img`'s URL when Google accepts it as a story's publisher logo, else ``''``."""
    try:
        if img and img.name.lower().endswith(_RASTER) and img.width == img.height >= 96:
            return img.url
    except Exception:  # noqa: BLE001, S110 — a row whose file is gone
        pass
    return ''


def _publisher_logo_url(settings_row, base: str) -> str:
    """A square raster image of at least 96 px — Google's rule for a story's logo.

    The merchant's logo (or uploaded favicon) when it qualifies, else the
    store's app icon: the PNG the PWA manifest and apple-touch-icon already
    use. The old fallback, `/favicon.ico`, is an SVG on every store that never
    uploaded a favicon, so those stores' stories all carried a logo the rich
    results reject.
    """
    url = _square_raster_url(getattr(settings_row, 'logo', None)) or _square_raster_url(
        getattr(settings_row, 'favicon', None)
    )
    if not url:
        from django.templatetags.static import static  # noqa: PLC0415

        try:
            url = static('pwa/icon-192.png')
        except ValueError:  # the pwa app's files are not collected on this deployment
            url = '/favicon.ico'
    return url if url.startswith(('http://', 'https://')) else f'{base}{url}'


@xframe_options_sameorigin
def story_page(request: HttpRequest, slug: str) -> HttpResponse:
    """Render the AMP Web Story document for a product.

    Decorated with ``@xframe_options_sameorigin`` because the PDP embeds
    this page inside an ``<amp-story-player>`` iframe — Django's default
    ``X-Frame-Options: DENY`` middleware would otherwise produce the
    'dotbooks.store refused to connect' error customers see when they
    tap the story preview card.
    """
    from plugins.installed.catalog.models import Product  # noqa: PLC0415
    from plugins.installed.webstories.models import WebStory  # noqa: PLC0415

    product = get_object_or_404(Product, slug=slug, status='active')
    try:
        story = product.web_story
    except WebStory.DoesNotExist as e:
        raise Http404('No story for this product') from e

    if not story.is_published or not story.panels:
        raise Http404('Story is unpublished or empty')

    base = _site_base_url(request)
    settings_row = _site_settings()
    publisher_name = (
        getattr(settings_row, 'store_name', None) or getattr(settings_row, 'name', None) or 'Store'
    )
    # StoreSettings has `logo` (an ImageField), never `logo_url` — reading the
    # latter always missed, silently falling back to a static file that isn't
    # in the tree, so every story on every store pointed publisher-logo-src at
    # a 404. An empty ImageField is falsy, so the truthy check guards the
    # `.url` access (an empty FileField raises ValueError on `.url`).
    publisher_logo = _publisher_logo_url(settings_row, base)

    context = {
        'story': story,
        'product': product,
        'panels': story.panels or [],
        'canonical_url': f'{base}/products/{product.slug}/',
        'story_url': f'{base}/story/{product.slug}/',
        'publisher_name': publisher_name,
        'publisher_logo_url': publisher_logo,
        'poster_url': story.poster_portrait_url
        or (story.panels[0].get('image_url') if story.panels else ''),
    }
    response = render(request, 'webstories/story.html', context)
    response['Content-Type'] = 'text/html; charset=utf-8'
    return _cache_headers(response, last_modified=story.updated_at)


@xframe_options_sameorigin
def story_index(request: HttpRequest) -> HttpResponse:
    """List every published Web Story whose product is still active.

    Storefront-style HTML (extends the dot_books base), not AMP — this
    is a normal browse page, not an embedded story player. Cache + frame
    headers mirror ``story_page`` so the listing is share-safe.
    """
    from plugins.installed.webstories.models import WebStory  # noqa: PLC0415

    stories = list(
        WebStory.objects.filter(
            is_published=True,
            product__status='active',
        )
        .select_related('product')
        .order_by('-updated_at')[:60]
    )
    breadcrumb_items = [
        {'name': 'Home', 'url': request.build_absolute_uri('/')},
        {'name': 'Stories', 'url': request.build_absolute_uri(request.path)},
    ]
    last_modified = stories[0].updated_at if stories else None
    response = render(
        request,
        'webstories/story_index.html',
        {
            'stories': stories,
            'breadcrumb_items': breadcrumb_items,
        },
    )
    return _cache_headers(response, last_modified=last_modified)
