"""Storefront views OWNED by digital_products (ADR 0013).

Registered at the site root by ``register_urls`` in ``plugin.ready()`` — so the
route only exists while the plugin is enabled. Disabling digital_products makes
``/account/downloads/`` 404 (the disable test), instead of the storefront
querying a disabled plugin's tokens. Presentation stays in the theme template.
"""

# Lazy imports keep model access load-order-safe (the established plugin pattern).
# ruff: noqa: PLC0415
from __future__ import annotations

import logging

from morpheus.plugin.views import redirect, render

logger = logging.getLogger('morpheus.digital_products')


def account_downloads(request):
    """Active digital download links — token-protected, time-bound."""
    if not request.user.is_authenticated:
        return redirect('/auth/login/?next=/account/downloads/')
    tokens: list = []
    try:
        from django.utils import timezone

        from plugins.installed.digital_products.models import DownloadToken

        tokens = list(
            DownloadToken.objects.filter(order__customer=request.user, revoked_at__isnull=True)
            .select_related('product', 'order')
            .order_by('-created_at')[:50]
        )
        now = timezone.now()
        for t in tokens:
            t.is_expired = bool(t.expires_at and t.expires_at <= now)
            t.is_exhausted = t.downloads_used >= t.max_downloads
    except Exception as e:  # noqa: BLE001
        logger.warning('account_downloads.tokens failed: %s', e, exc_info=True)
    return render(request, 'storefront/account_downloads.html', {'tokens': tokens})
