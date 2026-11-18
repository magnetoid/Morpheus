"""On-demand product image variant generator.

Backs ``/img/<fmt>/<width>/<path>`` — Pillow resizes the source image
and writes a cached WebP / AVIF variant.

A copy keeps no metadata of its source but one: when the source's XMP says a
trained model made or changed the image (IPTC ``DigitalSourceType``), the copy
carries that statement in an XMP packet of its own (EU AI Act Art. 50; Google
Merchant Center asks for it). Such a copy is cached under its own name, and the
storefront's image tag adds ``?ai=1`` to its address, so a copy cached before the
statement was carried is never served again.
"""

# ruff: noqa: PLC0415, E402, I001, PLW2901 — imports are deliberately local (optional
# Pillow; avoid import-time Django settings access); the Pillow in-place reassigns are fine.
from __future__ import annotations

import functools
import re


#: Whitelisted image variant widths. Restricted to a small set so the
# cache doesn't explode with arbitrary widths from crawlers.
# 240: a desktop book grid shows a cover about 224px wide (dot_books' card).
ALLOWED_IMAGE_WIDTHS = (200, 240, 400, 600, 800, 1200, 1600, 2000)
ALLOWED_IMAGE_FORMATS = ('webp', 'avif')


#: The IPTC digital source types that say a trained model made or changed an image.
AI_SOURCE_TYPES = ('trainedAlgorithmicMedia', 'compositeWithTrainedAlgorithmicMedia')

#: schema.org's name for each, for an ImageObject's ``digitalSourceType``.
SCHEMA_SOURCE_TYPES = {
    'trainedAlgorithmicMedia': 'https://schema.org/TrainedAlgorithmicMediaDigitalSource',
    'compositeWithTrainedAlgorithmicMedia': (
        'https://schema.org/CompositeWithTrainedAlgorithmicMediaDigitalSource'
    ),
}

_NEWSCODES = 'http://cv.iptc.org/newscodes/digitalsourcetype/'
_SOURCE_TYPE_RE = re.compile(
    rb'digitalsourcetype/(' + b'|'.join(t.encode() for t in AI_SOURCE_TYPES) + rb')(?![A-Za-z])'
)


def source_type_of(packet: bytes | str) -> str:
    """The AI source type an XMP packet declares (one of ``AI_SOURCE_TYPES``), or ''."""
    if isinstance(packet, str):
        packet = packet.encode('utf-8', 'replace')
    if not packet or b'DigitalSourceType' not in packet:
        return ''
    found = _SOURCE_TYPE_RE.search(packet)
    return found.group(1).decode() if found else ''


def _xmp_of(im) -> bytes:
    """The XMP packet Pillow read from an opened image (every format it reads), or b''."""
    for key in ('xmp', 'XML:com.adobe.xmp'):
        raw = im.info.get(key)
        if raw:
            return raw.encode('utf-8', 'replace') if isinstance(raw, str) else bytes(raw)
    return b''


def xmp_packet(source_type: str) -> bytes:
    """An XMP packet saying only that the image's digital source type is ``source_type``."""
    return (
        '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" '
        'xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/" '
        f'Iptc4xmpExt:DigitalSourceType="{_NEWSCODES}{source_type}"/>'
        '</rdf:RDF></x:xmpmeta><?xpacket end="w"?>'
    ).encode()


@functools.lru_cache(maxsize=4096)
def _read_source_type(path: str, mtime_ns: int, size: int) -> str:
    from PIL import Image

    try:
        with Image.open(path) as im:  # reads the header and its metadata only
            return source_type_of(_xmp_of(im))
    except Exception:  # noqa: BLE001 — not an image Pillow can read
        return ''


def ai_source_type(path: str) -> str:
    """The AI source type the image file at ``path`` declares, or ''.

    Cached per file and its modification time, like ``image_size``."""
    import os

    try:
        st = os.stat(path)
    except (OSError, TypeError, ValueError):
        return ''
    return _read_source_type(str(path), st.st_mtime_ns, st.st_size)


def image_source_type(url: str) -> str:
    """The AI source type one of the store's own images declares, or ''."""
    path = _local_image_path(url)
    return ai_source_type(path) if path else ''


def variant_cache_abs(rel: str, width: int, fmt: str) -> str:
    """Absolute path of the cached variant for ``(rel, width, fmt)``.

    The same on-disk layout ``parse_image_variant_path`` resolves —
    exposed so the ``optimize_images`` batch warmer writes to exactly the
    paths the ``/img/`` view later reads. A source that declares an AI source type
    gets a name of its own (``….ai.webp``), so a copy cached before the copies
    carried the statement is never reused.
    """
    import os

    from django.conf import settings

    rel = rel.lstrip('/')
    tagged = ai_source_type(os.path.join(str(settings.MEDIA_ROOT), rel))
    suffix = f'.ai.{fmt}' if tagged else f'.{fmt}'
    cache_rel = os.path.join('seo_img_cache', f'w{width}', fmt, rel + suffix)
    return os.path.join(str(settings.MEDIA_ROOT), cache_rel)


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
    return src_abs, variant_cache_abs(rel, width, fmt)


def generate_image_variant(src_abs: str, cache_abs: str, *, width: int, fmt: str) -> str:
    """Pillow-resize ``src_abs`` to ``width`` px wide at quality 80,
    write to ``cache_abs`` as ``fmt`` (webp/avif). Idempotent: skips
    when the cache already exists. Returns the cache absolute path.
    """
    import os

    if os.path.isfile(cache_abs):
        return cache_abs
    os.makedirs(os.path.dirname(cache_abs), exist_ok=True)
    from PIL import Image, ImageOps

    with Image.open(src_abs) as im:
        # The one statement a copy keeps: that a trained model made the image.
        source_type = source_type_of(_xmp_of(im))
        extra = {'xmp': xmp_packet(source_type)} if source_type else {}
        # A phone photo stores its rotation in EXIF, which a browser applies to the
        # original but WebP/AVIF re-encoding drops: turn the pixels upright first.
        im = ImageOps.exif_transpose(im)
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
            im.save(cache_abs, 'WEBP', quality=80, method=4, **extra)
        else:  # avif
            im.save(cache_abs, 'AVIF', quality=68, **extra)
    return cache_abs


def _local_image_path(url: str) -> str:
    """The file on disk behind a media or static URL of this store, or ''.

    Only the store's own files: an off-site address, a path with ``..`` or a
    file that is not there gives ''."""
    import os
    from urllib.parse import unquote, urlsplit

    from django.conf import settings

    path = unquote(urlsplit(str(url or '')).path or '')
    if not path or '..' in path.split('/'):
        return ''
    media_url = str(getattr(settings, 'MEDIA_URL', '/media/') or '/media/')
    static_url = str(getattr(settings, 'STATIC_URL', '/static/') or '/static/')
    found = ''
    if path.startswith(media_url):
        found = os.path.join(str(settings.MEDIA_ROOT), path[len(media_url) :])
    elif path.startswith(static_url):
        name = path[len(static_url) :]
        try:
            from django.contrib.staticfiles import finders
            from django.contrib.staticfiles.storage import staticfiles_storage

            found = staticfiles_storage.path(name)
            if not os.path.isfile(found):
                found = finders.find(name) or ''
        except Exception:  # noqa: BLE001 — a storage without paths, or no such file
            found = ''
    return found if found and os.path.isfile(found) else ''


@functools.lru_cache(maxsize=4096)
def _measure(path: str, mtime_ns: int, size: int) -> tuple[int, int] | None:
    from PIL import Image

    try:
        with Image.open(path) as im:  # reads the header only
            w, h = im.size
            orientation = im.getexif().get(0x0112)  # EXIF Orientation
    except Exception:  # noqa: BLE001 — not an image Pillow can read
        return None
    if orientation in (5, 6, 7, 8):  # turned a quarter: shown (and re-encoded) on its side
        w, h = h, w
    return (int(w), int(h)) if w > 0 and h > 0 else None


def image_size(url: str) -> tuple[int, int] | None:
    """Width and height of one of the store's own images, read from its file.

    Cached per file and its modification time, so a replaced file is measured
    again. ``None`` for anything that is not a local image."""
    import os

    path = _local_image_path(url)
    if not path:
        return None
    try:
        st = os.stat(path)
    except OSError:
        return None
    return _measure(path, st.st_mtime_ns, st.st_size)
