"""Section bundle for the dawnchild theme.

Importing this package registers the six starter sections and Dawnchild's own
"Stock list" in `themes.sections.section_registry`. CMS imports the bundle of
the theme named in `MORPHEUS_ACTIVE_THEME` when it starts, so these are offered
only on a store that runs this theme.

Add a section: subclass `Section`, set its attributes, decorate it with
`@_register`, and ship a matching `templates/storefront/sections/_<id>.html`.
"""

from themes.sections import Section, section_registry

_FIELDS = ('id', 'label', 'description', 'template', 'icon', 'schema', 'defaults')


def _register(cls):
    """Register a section built from the attributes its class declares.

    `Section` is a dataclass, so `cls()` takes every field from the base class's
    defaults and a subclass that only sets `id = 'hero'` comes out with an empty
    id, which the registry refuses. Passing the class's own values in keeps the
    declarative shape the other themes' bundles use and gives an instance that
    actually carries them.
    """
    section_registry.register(cls(**{f: vars(cls)[f] for f in _FIELDS if f in vars(cls)}))
    return cls


@_register
class HeroSection(Section):
    id = 'hero'
    label = 'Hero'
    description = 'Big editorial header with optional eyebrow + CTA.'
    icon = 'image'
    template = 'storefront/sections/_hero.html'
    schema = {
        'fields': [
            {'name': 'eyebrow', 'type': 'string', 'label': 'Eyebrow text'},
            {'name': 'heading', 'type': 'string', 'label': 'Heading', 'required': True},
            {'name': 'subheading', 'type': 'text', 'label': 'Sub-heading'},
            {'name': 'cta_label', 'type': 'string', 'label': 'CTA label'},
            {'name': 'cta_url', 'type': 'url', 'label': 'CTA URL'},
            {'name': 'image_url', 'type': 'url', 'label': 'Background image URL'},
        ]
    }
    defaults = {
        'eyebrow': '',
        'heading': 'Welcome',
        'subheading': '',
        'cta_label': '',
        'cta_url': '',
        'image_url': '',
    }


@_register
class FeaturedProductsSection(Section):
    id = 'featured_products'
    label = 'Featured products'
    description = 'A grid of products you want to highlight.'
    icon = 'package'
    template = 'storefront/sections/_featured_products.html'
    schema = {
        'fields': [
            {'name': 'heading', 'type': 'string', 'label': 'Heading'},
            {'name': 'count', 'type': 'integer', 'label': 'How many to show', 'min': 1, 'max': 24},
            {'name': 'category_slug', 'type': 'string', 'label': 'Filter by category slug'},
            {
                'name': 'sort',
                'type': 'enum',
                'label': 'Sort',
                'options': ['newest', 'oldest', 'price_low', 'price_high'],
            },
        ]
    }
    defaults = {'heading': 'Featured', 'count': 6, 'category_slug': '', 'sort': 'newest'}

    def render_context(self, *, page, settings):
        ctx = super().render_context(page=page, settings=settings)
        merged = ctx['settings']
        try:
            from plugins.installed.catalog.models import Product

            qs = Product.objects.filter(status='active')
            if merged.get('category_slug'):
                qs = qs.filter(category__slug=merged['category_slug'])
            if merged.get('sort') == 'oldest':
                qs = qs.order_by('created_at')
            elif merged.get('sort') == 'price_low':
                qs = qs.order_by('price')
            elif merged.get('sort') == 'price_high':
                qs = qs.order_by('-price')
            else:
                qs = qs.order_by('-created_at')
            count = max(1, min(int(merged.get('count') or 6), 24))
            products = list(qs.prefetch_related('images')[:count])
            # Merchandising takeover (reorder-only): a dynamics surface block
            # bound to 'section_featured' may re-rank the section's picks.
            try:
                from core.hooks import MorpheusEvents, hook_registry

                products = (
                    hook_registry.filter(
                        MorpheusEvents.STOREFRONT_PRODUCTS,
                        value=products,
                        surface='section_featured',
                        request=None,
                        limit=count,
                    )
                    or products
                )
            except Exception:  # noqa: BLE001, S110 — merchandising never breaks a section
                pass
            ctx['products'] = products
        except Exception:  # noqa: BLE001
            ctx['products'] = []
        return ctx


@_register
class RichTextSection(Section):
    id = 'rich_text'
    label = 'Rich text'
    description = 'A block of editorial copy. HTML or Markdown welcome.'
    icon = 'pilcrow'
    template = 'storefront/sections/_rich_text.html'
    schema = {
        'fields': [
            {'name': 'heading', 'type': 'string', 'label': 'Heading'},
            {'name': 'body', 'type': 'text', 'label': 'Body (HTML allowed)'},
            {'name': 'align', 'type': 'enum', 'label': 'Alignment', 'options': ['left', 'center']},
        ]
    }
    defaults = {'heading': '', 'body': '', 'align': 'left'}


@_register
class ImageWithTextSection(Section):
    id = 'image_with_text'
    label = 'Image with text'
    description = 'Image on one side, copy on the other. Click to flip the layout.'
    icon = 'image'
    template = 'storefront/sections/_image_with_text.html'
    schema = {
        'fields': [
            {'name': 'image_url', 'type': 'url', 'label': 'Image URL', 'required': True},
            {'name': 'image_alt', 'type': 'string', 'label': 'Image alt text'},
            {'name': 'heading', 'type': 'string', 'label': 'Heading'},
            {'name': 'body', 'type': 'text', 'label': 'Body'},
            {'name': 'cta_label', 'type': 'string', 'label': 'CTA label'},
            {'name': 'cta_url', 'type': 'url', 'label': 'CTA URL'},
            {
                'name': 'image_position',
                'type': 'enum',
                'label': 'Image position',
                'options': ['left', 'right'],
            },
        ]
    }
    defaults = {
        'image_url': '',
        'image_alt': '',
        'heading': '',
        'body': '',
        'cta_label': '',
        'cta_url': '',
        'image_position': 'left',
    }


@_register
class FaqSection(Section):
    id = 'faq'
    label = 'FAQ'
    description = 'Accordion of question / answer pairs. Edit the JSON list of items.'
    icon = 'help-circle'
    template = 'storefront/sections/_faq.html'
    schema = {
        'fields': [
            {'name': 'heading', 'type': 'string', 'label': 'Heading'},
            {
                'name': 'items',
                'type': 'json',
                'label': 'Items',
                'help': 'List of {"q": "...", "a": "..."} objects.',
            },
        ]
    }
    defaults = {
        'heading': 'Frequently asked',
        'items': [
            {'q': 'How long does shipping take?', 'a': 'Usually 3-5 business days.'},
            {'q': 'Do you accept returns?', 'a': 'Yes — within 30 days, unworn.'},
        ],
    }


@_register
class NewsletterSignupSection(Section):
    id = 'newsletter_signup'
    label = 'Newsletter signup'
    description = 'Email capture with a heading and short pitch.'
    icon = 'mail'
    template = 'storefront/sections/_newsletter_signup.html'
    schema = {
        'fields': [
            {'name': 'heading', 'type': 'string', 'label': 'Heading'},
            {'name': 'subheading', 'type': 'text', 'label': 'Sub-heading'},
            {'name': 'cta_label', 'type': 'string', 'label': 'Submit button label'},
        ]
    }
    defaults = {
        'heading': 'Stay in touch',
        'subheading': 'Occasional updates. No spam, ever.',
        'cta_label': 'Subscribe',
    }


@_register
class StockListSection(Section):
    """The trade page's stock list: every book on sale with its editions.

    Dawnchild's own section (design "Dawnchild Trade - soft"). CMS imports only
    the active theme's bundle, so it is offered only while this theme is live.
    Everything in a row is the catalogue's: an edition is an active variant, its
    code is its SKU and its price is the one the shop charges.
    """

    id = 'stock_list'
    label = 'Stock list'
    description = 'Every book on sale, one row per edition, with its code and price.'
    icon = 'table'
    template = 'storefront/sections/_stock_list.html'
    schema = {
        'fields': [
            {'name': 'heading', 'type': 'string', 'label': 'Heading'},
            {'name': 'intro', 'type': 'string', 'label': 'Line under the heading'},
            {'name': 'category_slug', 'type': 'string', 'label': 'Only this category (slug)'},
        ]
    }
    defaults = {'heading': 'Stock list', 'intro': '', 'category_slug': ''}

    MAX_BOOKS = 200

    def render_context(self, *, page, settings):
        ctx = super().render_context(page=page, settings=settings)
        try:
            ctx['stock'] = self._stock(ctx['settings'].get('category_slug') or '')
        except Exception:  # noqa: BLE001 - a section never breaks its page
            ctx['stock'] = []
        return ctx

    def _stock(self, category_slug: str) -> list[dict]:
        from core.hooks import MorpheusEvents, hook_registry
        from core.pricing import apply_price_filter
        from plugins.installed.catalog.models import Product

        qs = Product.objects.shoppable()
        if category_slug:
            # A category lists its subtree (catalog/category_tree.py), never the
            # one slug alone.
            from plugins.installed.catalog.category_tree import in_categories
            from plugins.installed.catalog.models import Category

            qs = qs.filter(
                in_categories(Category.objects.filter(slug=category_slug, is_active=True))
            ).distinct()
        qs = qs.order_by('category__name', 'name').prefetch_related('images', 'variants')
        stock = []
        for product in qs[: self.MAX_BOOKS]:
            variants = [v for v in product.variants.all() if v.is_active]
            editions = [
                {
                    'name': v.name,
                    'sku': v.sku,
                    'price': apply_price_filter(v.price or product.price, product=product),
                }
                for v in variants
            ] or [
                {
                    'name': product.get_product_type_display(),
                    'sku': product.sku,
                    'price': apply_price_filter(product.price, product=product),
                }
            ]
            meta = hook_registry.filter(MorpheusEvents.PRODUCT_CARD_META, {}, product=product)
            image = product.primary_image
            stock.append(
                {
                    'name': product.name,
                    'slug': product.slug,
                    'author': meta.get('author', '') if isinstance(meta, dict) else '',
                    'image': image.image if image and image.image else None,
                    'editions': editions,
                }
            )
        return stock
