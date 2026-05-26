"""On-demand product image variant generator.

Backs ``/img/<fmt>/<width>/<path>`` — Pillow resizes the source image
and writes a cached WebP / AVIF variant.
"""
from __future__ import annotations


#: Whitelisted image variant widths. Restricted to a small set so the
# cache doesn't explode with arbitrary widths from crawlers.
ALLOWED_IMAGE_WIDTHS = (200, 400, 600, 800, 1200, 1600, 2000)
ALLOWED_IMAGE_FORMATS = ('webp', 'avif')


def parse_image_variant_path(fmt: str, width: int, path: str):
    """Validate + resolve a public image variant request.

    Returns ``(src_abs, cache_abs)`` when the request is valid + the
    source image exists. Returns ``None`` for any invalid input —
    caller serves 404.
    """
    from django.conf import settings
    import os
    if fmt not in ALLOWED_IMAGE_FORMATS:
        return None
    if width not in ALLOWED_IMAGE_WIDTHS:
        return None
    # Strip leading slashes; never honour `..` traversal.
    rel = (path or '').lstrip('/')
    if '..' in rel.split('/'):
        return None
    src_abs = os.path.join(str(settings.MEDIA_ROOT), rel)
    if not os.path.isfile(src_abs):
        return None
    cache_rel = os.path.join('seo_img_cache', f'w{width}', fmt, rel + f'.{fmt}')
    cache_abs = os.path.join(str(settings.MEDIA_ROOT), cache_rel)
    return src_abs, cache_abs


def generate_image_variant(src_abs: str, cache_abs: str, *, width: int, fmt: str) -> str:
    """Pillow-resize ``src_abs`` to ``width`` px wide at quality 80,
    write to ``cache_abs`` as ``fmt`` (webp/avif). Idempotent: skips
    when the cache already exists. Returns the cache absolute path.
    """
    import os
    if os.path.isfile(cache_abs):
        return cache_abs
    os.makedirs(os.path.dirname(cache_abs), exist_ok=True)
    from PIL import Image
    with Image.open(src_abs) as im:
        # Keep aspect ratio; only downscale.
        if im.width > width:
            ratio = width / im.width
            new = (width, int(im.height * ratio))
            im = im.resize(new, Image.LANCZOS)
        # Flatten transparency for AVIF (no alpha at high quality on
        # some encoders); WebP preserves it.
        if fmt == 'avif' and im.mode in ('P', 'RGBA'):
            im = im.convert('RGB')
        if fmt == 'webp':
            im.save(cache_abs, 'WEBP', quality=80, method=4)
        else:  # avif
            im.save(cache_abs, 'AVIF', quality=68)
    return cache_abs
