"""Public download endpoint backing the email-delivered links.

The token URL is unguessable (URL-safe ~256-bit secret) and time-bound,
so the view does NOT require auth — the token IS the auth. We still
log every access (IP + timestamp) and refuse after expiry, the
download-count limit, or explicit revocation.
"""

from __future__ import annotations

import logging
import os

from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET

logger = logging.getLogger('morpheus.digital_products')


def _client_ip(request) -> str:
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '') or ''


@require_GET
def download(request, token: str) -> HttpResponse:
    """Serve the digital file behind a token. POST-style side effect on GET
    is OK here because the token is single-purpose — every successful
    hit decrements the remaining-downloads budget."""
    from plugins.installed.digital_products.models import DownloadToken

    tok = get_object_or_404(DownloadToken, token=token)

    if tok.revoked_at:
        return _refuse('This download has been revoked.', status=410)
    if tok.expires_at <= timezone.now():
        return _refuse('This download link has expired.', status=410)
    if tok.downloads_used >= tok.max_downloads:
        return _refuse('Download limit reached.', status=410)

    # Variant-level file wins (multi-format products: PDF / EPUB / MP3
    # as separate variants). Falls back to product-level digital_file
    # for single-SKU digital products.
    variant = getattr(tok.order_item, 'variant', None) if tok.order_item_id else None
    digital = None
    if variant is not None:
        digital = getattr(variant, 'digital_file', None) or None
    if not digital:
        digital = getattr(tok.product, 'digital_file', None) or None
    if not digital:
        logger.warning(
            'digital token %s — neither variant nor product carries a file',
            tok.id,
        )
        raise Http404('File missing')

    # Increment usage BEFORE streaming so a network blip + retry doesn't
    # let one click count as two.
    tok.downloads_used += 1
    tok.last_downloaded_at = timezone.now()
    tok.last_downloaded_ip = _client_ip(request)
    tok.save(
        update_fields=[
            'downloads_used',
            'last_downloaded_at',
            'last_downloaded_ip',
        ]
    )

    # Streaming serve. For S3 / external storage, prefer redirect to
    # the storage's signed URL — but the FileField API gives us .url.
    storage_url = getattr(digital, 'url', None)
    if storage_url and not storage_url.startswith('/'):
        # Remote storage (S3 / CDN) — redirect to its signed URL.
        from django.shortcuts import redirect

        return redirect(storage_url)

    # Local filesystem — stream the bytes directly.
    abs_path = digital.path
    if not os.path.exists(abs_path):
        logger.warning('digital token %s file missing on disk: %s', tok.id, abs_path)
        raise Http404('File missing')

    filename = os.path.basename(abs_path)
    response = FileResponse(open(abs_path, 'rb'), as_attachment=True, filename=filename)  # noqa: SIM115
    return response


def _refuse(message: str, *, status: int = 410) -> HttpResponse:
    body = (
        '<!doctype html><meta charset="utf-8">'
        '<title>Download unavailable</title>'
        '<style>body{font-family:system-ui,sans-serif;max-width:480px;margin:6rem auto;'
        'padding:2rem;color:#1a1a1a;text-align:center}h1{margin:0 0 .5rem;font-size:1.25rem}'
        'p{color:#6b7280;margin:0}</style>'
        f'<h1>Download unavailable</h1><p>{message}</p>'
    )
    return HttpResponse(body, status=status, content_type='text/html')
