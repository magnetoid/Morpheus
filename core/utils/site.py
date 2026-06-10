"""Site-wide base-URL helper.

Foundational (emails, feeds, sitemaps all need an absolute URL root), so
it lives in core — plugins import it from here, never the reverse.
"""

from __future__ import annotations

from django.conf import settings


def site_base_url() -> str:
    """Public site root with a trailing slash.

    ``SITE_BASE_URL`` when set, else the first ``ALLOWED_HOSTS`` entry.
    """
    base = getattr(settings, 'SITE_BASE_URL', '').rstrip('/')
    if base:
        return base + '/'
    hosts = getattr(settings, 'ALLOWED_HOSTS', []) or ['localhost']
    return f'https://{hosts[0]}/'
