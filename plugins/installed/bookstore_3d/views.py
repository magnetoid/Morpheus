"""3D bookstore walkthrough — a public storefront page at /walkthrough/.

Pulls up to N active catalog products (N + source configurable via the
plugin's settings panel) and hands them to the template as a JSON array of
``{title, slug, image_url, price, currency}``. The three.js scene reads that
array, textures a book per product, and on click navigates to
``/products/<slug>/``.

Catalog access is plain ORM (catalog.Product + .primary_image) — the
simplest reliable path to title/slug/image/price. No GraphQL round-trip
needed for a read-only page.
"""

# ruff: noqa: PLC0415
# Inline imports keep the module import-light + avoid load-order coupling
# (catalog models / registry resolve lazily at request time).

from __future__ import annotations

from morpheus.plugin.views import render

# Hard ceiling regardless of config — keeps the scene performant even if a
# merchant types a huge number into the settings form.
_MAX_BOOKS_CAP = 120

# Mirrors get_config_schema() defaults so the view is correct even before
# the merchant ever opens the settings panel (config is empty until saved).
_DEFAULTS = {
    'enabled': True,
    'book_source': 'featured',
    'source_category': '',
    'max_books': 40,
    'wall_color': '#efe7d6',
    'floor_color': '#6b5436',
    'accent_color': '#b08442',
    'ambient_intensity': 0.6,
}


def _config() -> dict:
    """Read this plugin's saved config, falling back to schema defaults.

    Never raises — a config-read failure must not break a public page.
    """
    cfg = dict(_DEFAULTS)
    try:
        from plugins.registry import plugin_registry

        plugin = plugin_registry.get('bookstore_3d')
        if plugin is not None:
            for key, default in _DEFAULTS.items():
                cfg[key] = plugin.get_config_value(key, default)
    except Exception:  # noqa: BLE001 — config is optional; never break the page
        import logging

        logging.getLogger('morpheus.bookstore_3d').debug('config read failed', exc_info=True)
    return cfg


def _image_url(request, product) -> str:
    """Absolute URL for the product's primary cover image, or '' if none.

    Absolute (request.build_absolute_uri) so three.js' TextureLoader — which
    fetches by URL, not via the page's relative base — always resolves it.
    Prefers the WebP variant (smaller download → faster texture upload).
    """
    img = product.primary_image
    if img is None:
        return ''
    f = getattr(img, 'webp_image', None) or img.image
    if not f:
        return ''
    try:
        return request.build_absolute_uri(f.url)
    except Exception:  # noqa: BLE001 — a broken file ref shouldn't drop the book
        return ''


def _books(request, cfg: dict) -> list[dict]:
    """Up to ``max_books`` active products as plain dicts for the template."""
    from plugins.installed.catalog.models import Product

    try:
        limit = int(cfg.get('max_books') or _DEFAULTS['max_books'])
    except (TypeError, ValueError):
        limit = _DEFAULTS['max_books']
    limit = max(1, min(limit, _MAX_BOOKS_CAP))

    qs = Product.objects.filter(status='active')

    source = cfg.get('book_source') or 'featured'
    if source == 'featured':
        # Featured first, newest as tiebreaker / filler so the shelves are
        # never empty on a store with few featured products.
        qs = qs.order_by('-is_featured', '-created_at')
    elif source == 'category':
        slug = (cfg.get('source_category') or '').strip()
        if slug:
            qs = qs.filter(category__slug=slug).order_by('-created_at')
        else:
            qs = qs.order_by('-created_at')
    else:  # 'recent' (and any unknown value falls back to recent)
        qs = qs.order_by('-created_at')

    # prefetch images so primary_image doesn't fire a query per product.
    qs = qs.prefetch_related('images')[:limit]

    books = []
    for p in qs:
        price = p.display_price
        books.append(
            {
                'title': p.name,
                'slug': p.slug,
                'image_url': _image_url(request, p),
                'price': str(price.amount) if price is not None else '',
                'currency': str(price.currency) if price is not None else '',
            }
        )
    return books


def walkthrough(request):
    """Render the 3D walkthrough within the active storefront theme.

    Public page — anyone can view it (no staff/customer scope). When the
    merchant has toggled the scene off in settings, we render the same page
    shell with an ``enabled=False`` flag so the template shows a short notice
    instead of booting three.js.
    """
    cfg = _config()
    enabled = bool(cfg.get('enabled', True))
    books = _books(request, cfg) if enabled else []

    scene = {
        'wallColor': cfg.get('wall_color') or _DEFAULTS['wall_color'],
        'floorColor': cfg.get('floor_color') or _DEFAULTS['floor_color'],
        'accentColor': cfg.get('accent_color') or _DEFAULTS['accent_color'],
        'ambientIntensity': cfg.get('ambient_intensity', _DEFAULTS['ambient_intensity']),
    }

    return render(
        request,
        'bookstore_3d/walkthrough.html',
        {
            'active_nav': 'bookstore_3d',
            'bookstore_enabled': enabled,
            'bookstore_books': books,
            'bookstore_scene': scene,
        },
    )
