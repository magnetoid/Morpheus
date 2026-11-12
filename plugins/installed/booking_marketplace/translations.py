"""What of this app a shopper reads can be translated, and showing the translations.

Places, hotels and events are this app's own text (`TRANSLATABLE_CONTENT`). An
experience's text is its catalog Product's (catalog registers it), so a listing
shows the Product's reviewed translation, copied onto the in-memory listing the way
`products.sync_from_product` copies the English text: plain and clipped. Nothing is
shown on a default-language page, and an object not fully translated keeps its own
text (`core.i18n.services.overlay_translation`).
"""

from __future__ import annotations

#: The Product fields a listing keeps a copy of.
_LISTING_FIELDS = ('name', 'short_description', 'description')


def on_translatable_content(value, **kwargs):
    """TRANSLATABLE_CONTENT — places, hotels and events."""
    from plugins.installed.booking_marketplace.models import Event, Place, Property

    return [
        *(value or []),
        {
            'key': 'booking_marketplace.place',
            'model': Place,
            'label': 'Places',
            'fields': {
                'name': 'text',
                'summary': 'text',
                'description': 'text',
                'overview': 'text',
            },
            'queryset': lambda: Place.objects.filter(is_active=True),
            'url': lambda place: f'/places/{place.slug}/',
        },
        {
            'key': 'booking_marketplace.property',
            'model': Property,
            'label': 'Hotels',
            'fields': {'name': 'text', 'short_description': 'text', 'description': 'text'},
            'queryset': lambda: Property.objects.filter(is_active=True, vendor__is_active=True),
            'url': lambda prop: f'/hotels/{prop.slug}/',
        },
        {
            'key': 'booking_marketplace.event',
            'model': Event,
            'label': 'Events',
            'fields': {
                'name': 'text',
                'summary': 'text',
                'description': 'text',
                'when_label': 'text',
            },
            'queryset': lambda: Event.objects.filter(is_active=True),
            'url': lambda event: f'/events/{event.slug}/',
        },
    ]


def show(objs):
    """Overlay the page language's reviewed translations on places, hotels or events."""
    from core.i18n.services import overlay_translation

    return overlay_translation(objs)


def show_listings(services, *, products=None) -> list:
    """Show each listing in the page's language, from its Product's reviewed translation.

    One Product query for the list (none when `products` hands them over) and one
    translation query.
    """
    from core.i18n.services import active_language, default_language, overlay_translation

    services = [s for s in (services or []) if s is not None]
    language = active_language()
    if not services or language == default_language():
        return services
    if products is None:
        from plugins.installed.catalog.models import Product

        ids = {s.product_id for s in services if s.product_id}
        products = list(Product.objects.filter(pk__in=ids)) if ids else []
    overlay_translation(list(products), language)
    by_pk = {p.pk: p for p in products if p.__dict__.get('_morph_translated') == language}
    for service in services:
        product = by_pk.get(service.product_id)
        if product is not None:
            _copy_to_listing(product, service, language)
    return services


def show_listing(service):
    """The detail page's listing and its Product, both in the page's language."""
    product = service.product if service.product_id else None
    show_listings([service], products=[product] if product is not None else [])
    return service


def _copy_to_listing(product, service, language: str) -> None:
    """The Product's translated text onto the listing: only the fields it translated."""
    from core.i18n.services import overlay
    from plugins.installed.booking_marketplace.products import _listing_copy

    translated = product.__dict__.get('_morph_untranslated') or {}
    overlay(
        service,
        {
            field: _listing_copy(service, field, getattr(product, field))
            for field in _LISTING_FIELDS
            if field in translated
        },
        language,
    )
