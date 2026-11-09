"""Storefront views OWNED by digital_products (ADR 0013).

Registered at the site root by ``register_urls`` in ``plugin.ready()`` — so the
route only exists while the plugin is enabled. Disabling digital_products makes
``/account/downloads/`` 404 (the disable test), instead of the storefront
querying a disabled plugin's tokens. Presentation stays in the theme template.

``/account/downloads/`` is the customer's library (``library.py``): every digital
line of their orders, with its state, and a file the signed-in buyer can fetch as
often as they like. The emailed token links keep their expiry and count limits;
the library does not need them.
"""

# Lazy imports keep model access load-order-safe (the established plugin pattern).
# ruff: noqa: PLC0415
from __future__ import annotations

import logging
import mimetypes
import os
import re

from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse

from morpheus.app.views import redirect, render

logger = logging.getLogger('morpheus.digital_products')

_RANGE = re.compile(r'^bytes=(\d*)-(\d*)$')
_CHUNK = 64 * 1024


def account_downloads(request):
    """The customer's library: digital purchases listed like orders."""
    if not request.user.is_authenticated:
        return redirect('/auth/login/?next=/account/downloads/')
    items: list = []
    try:
        from plugins.installed.digital_products.library import library

        items = library(request.user)
    except Exception as e:  # noqa: BLE001
        logger.warning('account library failed: %s', e, exc_info=True)
    return render(request, 'storefront/account_downloads.html', {'items': items})


def account_library_file(request, item_id):
    """A delivered digital line's file, for the buyer who owns it.

    ``?play=1`` answers inline with byte ranges, so the library's audio player can
    seek through a many-hour audiobook; otherwise the file downloads.
    """
    if not request.user.is_authenticated:
        return redirect(f'/auth/login/?next=/account/library/{item_id}/file/')
    from plugins.installed.digital_products.library import delivery_file, owned_line

    line = owned_line(request.user, item_id)
    digital = delivery_file(line) if line is not None else None
    if not digital:
        raise Http404('Not in your library')
    response = _file_response(request, digital, inline=request.GET.get('play') == '1')
    response['Cache-Control'] = 'private, no-store'
    return response


def _file_response(request, digital, *, inline: bool) -> HttpResponse:
    """Serve the file through its storage, whichever storage that is: a disk path
    would miss a file kept anywhere else, and the file's own /media/ address under
    digital/ answers staff only."""
    storage, name = digital.storage, digital.name
    if not storage.exists(name):
        logger.warning('library file missing: %s', name)
        raise Http404('File missing')
    size = storage.size(name)
    filename = os.path.basename(name)
    content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    span = _byte_range(request.headers.get('Range', ''), size) if inline else None
    if span == 'unsatisfiable':
        response = HttpResponse(status=416)
        response['Content-Range'] = f'bytes */{size}'
        return response
    handle = storage.open(name, 'rb')
    if span is None:
        response = FileResponse(
            handle, as_attachment=not inline, filename=filename, content_type=content_type
        )
        response['Content-Length'] = str(size)
    else:
        start, end = span
        handle.seek(start)
        response = StreamingHttpResponse(
            _read(handle, end - start + 1), status=206, content_type=content_type
        )
        response['Content-Range'] = f'bytes {start}-{end}/{size}'
        response['Content-Length'] = str(end - start + 1)
        disposition = 'inline' if inline else 'attachment'
        response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    response['Accept-Ranges'] = 'bytes'
    return response


def _byte_range(header: str, size: int):
    """(start, end) for one ``bytes=`` range, None for no range, or 'unsatisfiable'."""
    match = _RANGE.match(header.strip())
    if not match or size <= 0:
        return None
    first, last = match.groups()
    if not first and not last:
        return None
    if first:
        start = int(first)
        end = min(int(last), size - 1) if last else size - 1
    else:  # the last N bytes
        start = max(size - int(last), 0)
        end = size - 1
    if start >= size or start > end:
        return 'unsatisfiable'
    return start, end


def _read(handle, length: int):
    try:
        while length > 0:
            chunk = handle.read(min(_CHUNK, length))
            if not chunk:
                break
            length -= len(chunk)
            yield chunk
    finally:
        handle.close()
