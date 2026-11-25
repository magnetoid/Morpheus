"""What of this app a shopper reads can be translated, and showing the translations.

Places, hotels and events are this app's own text (`TRANSLATABLE_CONTENT`). An
experience's name and descriptions are its catalog Product's (catalog registers
them), so a listing shows the Product's reviewed translation, copied onto the
in-memory listing the way `products.sync_from_product` copies the English text:
plain and clipped. The rest of an experience page is the listing's own (its
duration, meeting point, cancellation policy, highlights, what is and is not
included, what to bring, itinerary and guest questions), registered here as
"Experience details"; its page exists in a language only when both are
translated there (`with`). Nothing is shown on a default-language page, and an
object not fully translated keeps its own text
(`core.i18n.services.overlay_translation`).
"""

from __future__ import annotations

#: The Product fields a listing keeps a copy of.
_LISTING_FIELDS = ('name', 'short_description', 'description')

#: The listing's own text a guest reads on its page and card.
EXPERIENCE_FIELDS = {
    'duration_label': 'text',
    'meeting_point': 'text',
    'cancellation_policy': 'text',
    'highlights': 'lines',
    'included': 'lines',
    'not_included': 'lines',
    'what_to_bring': 'lines',
    'itinerary': 'pairs:title,detail',
    'faqs': 'pairs:q,a',
}


def on_translatable_content(value, **kwargs):
    """TRANSLATABLE_CONTENT — places, hotels and events."""
    from plugins.installed.booking_marketplace.models import (
        BookableService,
        Event,
        Place,
        Property,
    )

    return [
        *(value or []),
        {
            'key': 'booking_marketplace.experience',
            'model': BookableService,
            'label': 'Experience details',
            'title_field': 'name',
            'fields': dict(EXPERIENCE_FIELDS),
            'queryset': lambda: BookableService.objects.filter(
                is_active=True, vendor__is_active=True
            ),
            'url': lambda service: f'/bookings/{service.slug}/',
            # The page also shows the Product's name and descriptions.
            'with': lambda service: [service.product] if service.product_id else [],
        },
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
    """Show each listing in the page's language: its details' reviewed translation,
    and its name and descriptions from its Product's.

    One Product query for the list (none when `products` hands them over) and two
    translation queries.
    """
    from core.i18n.services import active_language, default_language, overlay_translation

    services = [s for s in (services or []) if s is not None]
    language = active_language()
    if not services or language == default_language():
        return services
    overlay_translation(services, language)
    _show_categories(services, language)
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


def _show_categories(services, language: str) -> None:
    """Each listing's category named in `language`: one query for the list."""
    from core.i18n.services import overlay_translation
    from plugins.installed.catalog.models import Category

    ids = {s.category_id for s in services if s.category_id}
    if not ids:
        return
    cached = {
        s.category_id: s._state.fields_cache['category']
        for s in services
        if s.category_id and s._state.fields_cache.get('category') is not None
    }
    missing = ids - set(cached)
    if missing:
        cached.update({c.pk: c for c in Category.objects.filter(pk__in=missing)})
    overlay_translation(list({id(c): c for c in cached.values()}.values()), language)
    for service in services:
        if service.category_id in cached:
            service._state.fields_cache['category'] = cached[service.category_id]


def show_listing(service):
    """The detail page's listing and its Product, both in the page's language."""
    product = service.product if service.product_id else None
    show_listings([service], products=[product] if product is not None else [])
    return service


def _copy_to_listing(product, service, language: str) -> None:
    """The Product's translated text onto the listing: only the fields it translated."""
    from core.i18n.services import ai_translated, overlay
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
        # The listing shows the Product's text, so it carries the Product's AI marks.
        ai_fields=ai_translated(product),
    )
