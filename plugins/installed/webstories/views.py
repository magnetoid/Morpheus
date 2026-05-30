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
    publisher_logo = getattr(settings_row, 'logo_url', '') or f'{base}/static/img/logo-1x1.png'

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
