"""Auto-build heuristic for product Web Stories.

``build_panels_for(product)`` turns a Product + its images + optional
book metafields into a 4-7 panel story:

  1. Cover image with product name overlay
  2. Short description over second image (when available)
  3. Each additional image with its alt-text caption
  4. Optional 'About this book' panel from book.synopsis metafield
  5. Final 'Shop now' CTA panel linking back to the PDP

``ensure_story(product)`` get-or-creates the WebStory row and
regenerates panels on every call (idempotent; cheap).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger('morpheus.webstories')

_MAX_IMAGE_PANELS = 5
_CAPTION_MAX = 160
_TITLE_MAX = 80


def _image_url_for(image_row) -> str:
    """Prefer the WebP variant (smaller, AMP-friendly) when present."""
    if getattr(image_row, 'webp_image', None) and image_row.webp_image.name:
        return image_row.webp_image.url
    if getattr(image_row, 'image', None) and image_row.image.name:
        return image_row.image.url
    return ''


def _book_metafields(product) -> dict[str, str]:
    """Book attributes (synopsis / author / …) for the story panels.

    Model-first (BookProduct) with a legacy book.* metafield fallback; empty
    when book_product/metafields aren't available."""
    try:
        from plugins.installed.book_product.compat import book_attrs  # noqa: PLC0415

        return book_attrs(product)
    except Exception as e:  # noqa: BLE001
        logger.debug('webstories: book attrs skipped: %s', e)
        return {}


def build_panels_for(product) -> list[dict[str, Any]]:
    """Generate panels for ``product``. Idempotent + side-effect-free."""
    panels: list[dict[str, Any]] = []
    images = list(product.images.order_by('-is_primary', 'sort_order')[:_MAX_IMAGE_PANELS])

    pdp_url = f'/products/{product.slug}/'
    name = (product.name or '').strip()
    short = (product.short_description or '').strip()
    book = _book_metafields(product)
    author = (book.get('author') or '').strip()

    # Panel 1 — cover image + product name + author byline
    if images:
        cover_caption = f'by {author}' if author else (short[:_CAPTION_MAX] if short else '')
        panels.append(
            {
                'image_url': _image_url_for(images[0]),
                'title': name[:_TITLE_MAX],
                'caption': cover_caption,
            }
        )

    # Panel 2 — short description over the second image (or cover if only one)
    if short:
        bg = images[1] if len(images) > 1 else (images[0] if images else None)
        panels.append(
            {
                'image_url': _image_url_for(bg) if bg else '',
                'title': '',
                'caption': short[:_CAPTION_MAX],
            }
        )

    # Panels 3-N — remaining images with alt-text captions
    for img in images[2:]:
        alt = (getattr(img, 'alt_text', '') or '').strip()
        panels.append(
            {
                'image_url': _image_url_for(img),
                'title': '',
                'caption': alt[:_CAPTION_MAX],
            }
        )

    # Optional 'About this book' panel from synopsis
    synopsis = (book.get('synopsis') or book.get('description') or '').strip()
    if synopsis and len(panels) < 6:
        panels.append(
            {
                'image_url': _image_url_for(images[0]) if images else '',
                'title': 'About this book',
                'caption': synopsis[:240],
            }
        )

    # Final CTA panel — always present so users can tap through
    panels.append(
        {
            'image_url': _image_url_for(images[0]) if images else '',
            'title': 'Shop now',
            'caption': short[:120] if short else name[:120],
            'cta_url': pdp_url,
            'cta_label': 'View product',
        }
    )

    return panels


def ensure_story(product) -> tuple[Any, bool]:
    """Get-or-create the WebStory for ``product`` and refresh panels.

    Returns ``(story, changed)`` where ``changed`` is True when panels
    were regenerated (always True today; here as a future hook for
    diff-based skips)."""
    from plugins.installed.webstories.models import WebStory  # noqa: PLC0415

    panels = build_panels_for(product)
    poster = panels[0]['image_url'] if panels else ''

    story, _created = WebStory.objects.get_or_create(
        product=product,
        defaults={
            'title': (product.name or '')[:120],
            'summary': (product.short_description or '')[:280],
            'panels': panels,
            'poster_portrait_url': poster,
        },
    )

    story.title = (product.name or '')[:120]
    story.summary = (product.short_description or '')[:280]
    story.panels = panels
    story.poster_portrait_url = poster
    story.save(update_fields=['title', 'summary', 'panels', 'poster_portrait_url', 'updated_at'])
    return story, True


def story_path(product_slug: str) -> str:
    return f'/story/{product_slug}/'
