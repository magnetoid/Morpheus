"""Section bundle for the dot_books theme.

Importing this package registers six starter sections in
`themes.sections.section_registry`. The dot_books theme registers
them on import via the bottom of this file; theme load follows the
plugin registry's discovery so the registry is populated before any
page render attempts to look up a section_id.

Add a section: subclass `Section`, set the four class attributes,
@section_registry.register it, and ship a matching
`templates/storefront/sections/_<id>.html`.
"""

from themes.sections import Section, section_registry


@section_registry.register
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


@section_registry.register
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


@section_registry.register
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


@section_registry.register
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


@section_registry.register
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


@section_registry.register
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
