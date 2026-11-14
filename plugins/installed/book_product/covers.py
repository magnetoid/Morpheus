"""A book's cover file: a PDF, or a PNG or JPEG image (``BookProduct.cover_pdf``).

The 3D preview draws it on the front of the book: page 1 of a PDF, or the image
itself. The field keeps its name, and GraphQL its ``coverPdfUrl``, because both are
already read outside this app; ``cover_type`` says which kind a stored file is.

An upload is checked here before it is stored: its name, its size and its first
bytes must agree, and an image must open with Pillow within a pixel limit (a small
file can decode to a huge image).
"""

from __future__ import annotations

import os

MAX_BYTES = 50 * 1024 * 1024
MAX_PIXELS = 40_000_000
# What the file input offers, by type and by name (some systems send no type).
ACCEPT = 'application/pdf,image/png,image/jpeg,.pdf,.png,.jpg,.jpeg'

_KIND_BY_EXTENSION = {'.pdf': 'pdf', '.png': 'png', '.jpg': 'jpeg', '.jpeg': 'jpeg'}
_SIGNATURES = {'pdf': b'%PDF-', 'png': b'\x89PNG\r\n\x1a\n', 'jpeg': b'\xff\xd8\xff'}
_PILLOW_FORMAT = {'png': 'PNG', 'jpeg': 'JPEG'}


def cover_type(file) -> str:
    """``'pdf'`` or ``'image'`` for a stored cover, ``''`` when there is none."""
    name = getattr(file, 'name', '') or ''
    kind = _KIND_BY_EXTENSION.get(os.path.splitext(name)[1].lower())
    if not kind:
        return ''
    return 'pdf' if kind == 'pdf' else 'image'


def check_upload(upload) -> str:
    """Why ``upload`` cannot be the cover, or ``''`` when it can."""
    kind = _KIND_BY_EXTENSION.get(os.path.splitext(upload.name or '')[1].lower())
    if not kind:
        return 'the cover must be a PDF, PNG or JPG file.'
    if (upload.size or 0) > MAX_BYTES:
        return f'the cover is over {MAX_BYTES // (1024 * 1024)} MB.'
    upload.seek(0)
    head = upload.read(8)
    upload.seek(0)
    if not head.startswith(_SIGNATURES[kind]):
        return f'{upload.name} is not the kind of file its name says.'
    if kind == 'pdf':
        return ''
    return _check_image(upload, _PILLOW_FORMAT[kind])


def _check_image(upload, expected_format: str) -> str:
    from PIL import Image, UnidentifiedImageError  # noqa: PLC0415

    try:
        with Image.open(upload) as image:
            width, height = image.size
            if width * height > MAX_PIXELS:
                return 'the cover image is too large; use one under 40 megapixels.'
            if image.format != expected_format:
                return f'{upload.name} is not the kind of file its name says.'
            image.verify()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError):
        return f'{upload.name} could not be read as an image.'
    finally:
        upload.seek(0)
    return ''
