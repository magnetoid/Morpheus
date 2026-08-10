"""Core context processors — store settings and cart into every template."""

from django.conf import settings as django_settings


def _store_identity() -> dict:
    """Merchant-editable store identity, from the DB row they actually edit.

    Settings → General writes a `StoreSettings` row, but the storefront read
    these values from env vars — so editing the store name, description, logo or
    social links changed nothing on the storefront. DB first, env as the
    fallback so an unconfigured install behaves exactly as before.

    (Currency / language / timezone stay env-driven for now: those need real
    djmoney / i18n_patterns / TIME_ZONE work, not a context-processor line.
    Tracked in the localization plan.)
    """
    try:
        from core.models import StoreSettings

        row = StoreSettings.objects.first()
    except Exception:  # noqa: BLE001 — DB unavailable must not break rendering
        row = None
    if row is None:
        return {}

    def _url(field):
        img = getattr(row, field, None)
        try:
            return img.url if img else ''
        except Exception:  # noqa: BLE001 — a missing file must not 500 a page
            return ''

    return {
        'STORE_NAME': (row.store_name or '').strip(),
        'STORE_DESCRIPTION': (row.store_description or '').strip(),
        'STORE_LOGO_URL': _url('logo'),
        'STORE_FAVICON_URL': _url('favicon'),
        'STORE_SOCIAL_LINKS': row.social_links if isinstance(row.social_links, dict) else {},
    }


def store_settings(request):
    identity = _store_identity()
    return {
        'STORE_NAME': identity.get('STORE_NAME') or django_settings.STORE_NAME,
        'STORE_DESCRIPTION': identity.get('STORE_DESCRIPTION', ''),
        'STORE_LOGO_URL': identity.get('STORE_LOGO_URL', ''),
        'STORE_FAVICON_URL': identity.get('STORE_FAVICON_URL', ''),
        'STORE_SOCIAL_LINKS': identity.get('STORE_SOCIAL_LINKS', {}),
        'STORE_CURRENCY': django_settings.STORE_CURRENCY,
        'STORE_COUNTRY': django_settings.STORE_COUNTRY,
        'DEBUG': django_settings.DEBUG,
        'MORPHEUS_VERSION': getattr(django_settings, 'MORPHEUS_VERSION', 'v0.1.0'),
        'GOOGLE_PLACES_API_KEY': getattr(django_settings, 'GOOGLE_PLACES_API_KEY', ''),
        # Storefront fallback cover for products with no image (Settings → General).
        'PRODUCT_PLACEHOLDER_IMAGE': _product_placeholder_url(),
        # GDPR/ePrivacy master switch — gates the cookie banner + data-rights
        # links on every storefront page (Settings → General).
        'GDPR_ENABLED': _gdpr_enabled(),
    }


def _gdpr_enabled() -> bool:
    """Cached read of the GDPR master switch (runs on every storefront page)."""
    from django.core.cache import cache

    val = cache.get('morph:gdpr_enabled')
    if val is None:
        import contextlib

        from core.models import StoreSettings

        val = bool(StoreSettings.get('gdpr_enabled', True))
        with contextlib.suppress(Exception):  # cache outage must not break rendering
            cache.set('morph:gdpr_enabled', val, timeout=60)
    return val


def _product_placeholder_url() -> str:
    """URL of the configured product placeholder image, or '' if unset/unavailable."""
    try:
        from core.models import StoreSettings

        img = StoreSettings.get('product_placeholder_image')
        return img.url if img else ''
    except Exception:
        return ''


def display_currency(request):
    """Resolve the visitor's preferred display currency.

    Resolution order: `?currency=` query param → session → channel currency
    → `STORE_CURRENCY`. The visitor can pin a currency via `/?currency=EUR`.
    Templates render prices in the channel/store currency by default;
    multi-currency-aware templates use `{{ price|convert:DISPLAY_CURRENCY }}`.
    """
    cur = (request.GET.get('currency') or '').upper()[:3]
    if cur:
        request.session['display_currency'] = cur
    if not cur:
        cur = request.session.get('display_currency')
    if not cur:
        try:
            from core.channels import current_channel

            ch = current_channel(request)
            cur = getattr(ch, 'currency', '') or django_settings.STORE_CURRENCY
        except Exception:
            cur = django_settings.STORE_CURRENCY
    return {'DISPLAY_CURRENCY': cur}


def channel_context(request):
    """Expose the resolved StoreChannel + its currency/country to every template."""
    try:
        from core.channels import current_channel

        channel = current_channel(request)
        return {
            'CURRENT_CHANNEL': channel,
            'CHANNEL_CURRENCY': getattr(channel, 'currency', None)
            or django_settings.STORE_CURRENCY,
            'CHANNEL_COUNTRY': getattr(channel, 'default_country', None)
            or django_settings.STORE_COUNTRY,
        }
    except Exception:
        return {
            'CURRENT_CHANNEL': None,
            'CHANNEL_CURRENCY': django_settings.STORE_CURRENCY,
            'CHANNEL_COUNTRY': django_settings.STORE_COUNTRY,
        }
