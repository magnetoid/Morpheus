"""Core context processors — store settings and cart into every template."""

from django.conf import settings as django_settings


def store_settings(request):
    return {
        'STORE_NAME': django_settings.STORE_NAME,
        'STORE_CURRENCY': django_settings.STORE_CURRENCY,
        'STORE_COUNTRY': django_settings.STORE_COUNTRY,
        'DEBUG': django_settings.DEBUG,
        'MORPHEUS_VERSION': getattr(django_settings, 'MORPHEUS_VERSION', 'v0.1.0'),
        'GOOGLE_PLACES_API_KEY': getattr(django_settings, 'GOOGLE_PLACES_API_KEY', ''),
    }


def cart_context(request):
    """Lightweight cart item count for the nav bar."""
    count = 0
    try:
        if request.user.is_authenticated:
            from plugins.installed.orders.models import Cart

            cart = Cart.objects.filter(customer=request.user).order_by('-updated_at').first()
            if cart:
                count = cart.item_count
        else:
            session_key = request.session.session_key
            if session_key:
                from plugins.installed.orders.models import Cart

                cart = Cart.objects.filter(session_key=session_key).order_by('-updated_at').first()
                if cart:
                    count = cart.item_count
    except Exception:
        import logging

        logging.getLogger(__name__).warning('Suppressed exception', exc_info=True)
    return {'cart_item_count': count}


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
