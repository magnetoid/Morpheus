"""Site-wide base-URL and store-identity helpers.

Foundational (emails, feeds, sitemaps all need an absolute URL root, and
every agent-facing manifest needs the merchant's name), so it lives in
core — plugins import it from here, never the reverse.
"""

from __future__ import annotations

from django.conf import settings
from django.utils.text import slugify


def site_base_url() -> str:
    """Public site root with a trailing slash.

    ``SITE_BASE_URL`` when set, else the first ``ALLOWED_HOSTS`` entry.
    """
    base = getattr(settings, 'SITE_BASE_URL', '').rstrip('/')
    if base:
        return base + '/'
    hosts = getattr(settings, 'ALLOWED_HOSTS', []) or ['localhost']
    return f'https://{hosts[0]}/'


def store_name() -> str:
    """The merchant's brand — what the *business* is called.

    Morpheus is the engine; this is the name on the door. Anything that
    presents the store's identity to a customer or an AI agent (agent
    manifests, feeds, emails) must use this, never a hardcoded product
    name. ``core.StoreSettings.store_name`` → ``settings.STORE_NAME``.

    Fails soft to ``''`` — the settings row (or its table) may not exist
    yet during a migration or a fresh install, and no manifest should 500
    over a missing brand.
    """
    try:
        from core.models import StoreSettings

        name = (getattr(StoreSettings.objects.first(), 'store_name', '') or '').strip()
        if name:
            return name
    except Exception:  # noqa: BLE001, S110 — table/row may be absent; fall through
        pass
    return (getattr(settings, 'STORE_NAME', '') or '').strip()


def store_slug(suffix: str = '') -> str:
    """Machine-readable form of :func:`store_name`, for manifest ``name``
    fields that want an identifier rather than a display string.

    ``store_slug('ucp')`` → ``'dot-books-ucp'``. Falls back to ``'store'``
    so the identifier is never empty or a bare dash.
    """
    base = slugify(store_name()) or 'store'
    return f'{base}-{suffix}' if suffix else base


def store_contact_email() -> str:
    """Public contact address for the store, or ``''`` when unset.

    Only ``core.StoreSettings.contact_email`` — deliberately NOT
    ``DEFAULT_FROM_EMAIL``, which is a *sending* identity and is usually
    ``noreply@…``. Publishing that as a contact tells an agent to mail an
    address nobody reads, which is worse than publishing none; callers
    omit the field when this is empty.
    """
    try:
        from core.models import StoreSettings

        return (getattr(StoreSettings.objects.first(), 'contact_email', '') or '').strip()
    except Exception:  # noqa: BLE001 — table/row may be absent
        return ''


def store_logo_url() -> str:
    """Absolute URL of the merchant's logo, or ``''`` when none is set.

    Callers must omit the field when this is empty — advertising a logo
    URL that 404s is worse than advertising none.
    """
    try:
        from core.models import StoreSettings

        store = StoreSettings.objects.first()
        img = getattr(store, 'logo', None) or getattr(store, 'default_social_image', None)
        if img:
            return absolutize(img.url)
    except Exception:  # noqa: BLE001, S110 — table/row/file may be absent
        pass
    return ''


def absolutize(url: str) -> str:
    """Make a site-relative URL (``/media/…``) absolute against
    :func:`site_base_url`. Absolute, protocol-relative, and empty URLs
    pass through unchanged. OG scrapers, social cards, and JSON-LD all
    require absolute URLs, so emitters route through this one helper.
    """
    if url and url.startswith('/') and not url.startswith('//'):
        return site_base_url().rstrip('/') + url
    return url
