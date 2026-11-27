"""Uploaded media, with sold files kept back.

A digital product's file (catalog's ``digital_file``, under ``digital/``) is what
the customer pays for. Buyers get it through a download token
(digital_products), which reads it from disk; served under /media/ like any
other upload, it downloaded for anyone who knew or guessed the name, and the
flipbook preview printed that name in its page (live on dotbooks, 2026-10-12).
Staff keep access, so the dashboard's links to the current file still work.
"""

from __future__ import annotations

import posixpath

from django.conf import settings
from django.http import Http404
from django.views.static import serve

from core.not_found import page_not_found

#: Paths under MEDIA_ROOT only staff may fetch over HTTP.
PRIVATE_PREFIXES = ('digital/',)


def is_private(path: str) -> bool:
    return posixpath.normpath(path).lstrip('/').startswith(PRIVATE_PREFIXES)


def serve_media(request, path, document_root=None, show_indexes=False):
    root = document_root or settings.MEDIA_ROOT
    if not is_private(path):
        return serve(request, path, document_root=root)
    # A CDN in front of /media/ caches a PDF, MP3 or ZIP by its extension, and a
    # 404 too, so no answer here may be kept by a shared cache.
    try:
        if not getattr(getattr(request, 'user', None), 'is_staff', False):
            raise Http404
        response = serve(request, path, document_root=root)
    except Http404:
        response = page_not_found(request)
    response['Cache-Control'] = 'private, no-store'
    return response
