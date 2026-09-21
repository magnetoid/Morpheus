"""Book Product plugin manifest."""

# ruff: noqa: PLC0415
from __future__ import annotations

from morpheus.app import Plugin, SettingsPanel, StorefrontBlock
from morpheus.core import events


class BookProductPlugin(Plugin):
    name = 'book_product'
    label = 'Book Product'
    version = '0.3.0'
    description = (
        'Book product-type extension: author, print/paper type, page count, '
        'a cover-PDF 3D preview, and a dashboard book widget. Book attributes '
        'live on a real model instead of meta tags.'
    )
    has_models = True
    requires = ['catalog']

    def ready(self) -> None:
        # Contribute the "Book details" card into the dashboard product form via
        # the modular extension point (PRODUCT_FORM_CARDS) and persist it on save
        # (PRODUCT_FORM_SAVED) — so the card lives in this plugin and DISABLING
        # book_product removes it, with no hard-coded import in admin_dashboard
        # (ADR 0023). Was previously a try/except import in product_edit, which
        # only guarded ImportError and so survived a disable.
        self.register_hook(events.PRODUCT_FORM_CARDS, self.on_product_form_cards, priority=40)
        self.register_hook(events.PRODUCT_FORM_SAVED, self.on_product_form_saved, priority=40)
        # This app owns a whole family of storefront URLs (/genre/…, /topic/…,
        # /publisher/…, /series/…, /format/…, the taxonomy index pages) that the
        # SEO layer would otherwise see as anonymous static pages — no ItemList,
        # no author entity, no per-term meta. Answering SEO_RESOLVE_PAGE tells it
        # what they are, without seo importing this app.
        self.register_hook(events.SEO_RESOLVE_PAGE, self.on_seo_resolve_page, priority=40)
        # Full GraphQL control: bookProduct query + setBookProduct mutation.
        self.register_graphql_extension('plugins.installed.book_product.graphql.queries')
        self.register_graphql_extension('plugins.installed.book_product.graphql.mutations')
        # Storefront routes: taxonomy index pages (/authors/, /publishers/,
        # /series/, /imprints/) listing every term, plus per-value facet pages
        # (/publisher/<slug>/, /series/, /imprint/, /format/, /language/) — each
        # listing the books carrying that attribute value.
        self.register_urls(
            'plugins.installed.book_product.urls', prefix='', namespace='book_product'
        )
        # Dashboard: Book taxonomies (per-term SEO editing) under Products.
        self.register_urls(
            'plugins.installed.book_product.urls_dashboard',
            prefix='dashboard/book-taxonomies/',
            namespace='book_product_dashboard',
        )
        # Bulk taxonomy-copy backfill runs on the worker (one LLM call per term).
        self.register_celery_tasks('plugins.installed.book_product.tasks')
        # Storefront nav for Genres/Topics. Contributed (not listed in
        # settings.TEMPLATES) so it runs only while this app is active — a
        # non-book store that disables the vertical then executes none of it,
        # instead of querying unloaded Genre/Topic models every request.
        from plugins.installed.book_product.context_processors import nav_genres, nav_topics

        self.register_context_processor(nav_genres)
        self.register_context_processor(nav_topics)

    # Every route this app mounts, and what it is in SEO terms. Author landings
    # are entity pages (they get a Person node); the rest are listings of books
    # sharing an attribute. The index pages list terms rather than books, but
    # they are still listings.
    _SEO_KINDS = {
        'genre': 'genre',
        'topic': 'topic',
        'publisher': 'publisher',
        'series': 'series',
        'imprint': 'imprint',
        'format': 'format',
        'language': 'language',
        'author': 'author',
        'genres': 'genres',
        'topics': 'topics',
        'authors': 'authors',
        'publishers': 'publishers',
        'series_index': 'series',
        'imprints': 'imprints',
    }

    def on_seo_resolve_page(self, value, request=None, context=None, **kwargs):
        """Claim this app's storefront URLs for the SEO layer.

        Returns the incoming value untouched unless the URL is ours — the filter
        is first-answer-wins, so a handler that claims too much would silently
        take another app's pages.
        """
        if value is not None or request is None:
            return value
        url_name = getattr(getattr(request, 'resolver_match', None), 'url_name', '') or ''
        namespace = getattr(getattr(request, 'resolver_match', None), 'namespace', '') or ''
        if namespace != self.name or url_name not in self._SEO_KINDS:
            return value
        # From CORE, not from the seo app: this app does not depend on seo and
        # must still describe its own pages when seo is disabled (the filter
        # simply has no subscriber then).
        from core.seo_page import KIND_LISTING, SeoPage  # noqa: PLC0415

        ctx = context or {}
        return SeoPage(
            kind=KIND_LISTING,
            subtype=self._SEO_KINDS[url_name],
            path=request.get_full_path(),
            title=str(ctx.get('seo_title') or ''),
            description=str(ctx.get('seo_description') or ''),
            og_type='profile' if url_name == 'author' else 'website',
            context=ctx,
        )

    def on_product_form_cards(self, value, product=None, **kwargs):
        """Contribute the 'Book details' card. Shown for every product (any
        product can be made a book via this card's `book_submitted` marker)."""
        from plugins.installed.book_product.dashboard import book_widget_context

        value.append(
            {
                'template': 'book_product/_product_form_card.html',
                'context': {'book_widget': book_widget_context(product)},
                'order': 40,
            }
        )
        return value

    def on_product_form_saved(self, product=None, post=None, files=None, **kwargs):
        """Persist the book fields submitted with the product form."""
        if product is None or post is None:
            return
        from plugins.installed.book_product.dashboard import save_book_fields

        save_book_fields(product, post, files)

    def contribute_dashboard_pages(self) -> list:
        from morpheus.app import DashboardPage  # noqa: PLC0415

        return [
            DashboardPage(
                label='Book taxonomies',
                slug='book-taxonomies',
                view='plugins.installed.book_product.dashboard_taxonomies.taxonomies_list',
                icon='tags',
                # section='products' renders this as a child of the hardcoded
                # Products nav group (just below Collections, via order) — the
                # plugin owns its placement; no hardcoded link in base.html (ADR 0016).
                section='products',
                order=10,
                nav='main',
                url='/dashboard/book-taxonomies/',
            ),
        ]

    def contribute_storefront_blocks(self) -> list[StorefrontBlock]:
        # Book details + 3D cover preview on the PDP. Self-gates on a
        # BookProduct existing (the template renders nothing otherwise), so it
        # disappears with the plugin.
        return [
            StorefrontBlock(
                slot='pdp_below_form',
                template='storefront/blocks/_book_pdp.html',
                priority=40,
                context_keys=['product'],
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        # Lives under Settings → Product Types (the category is declared in
        # admin_dashboard.settings_categories). Disabling the plugin removes it.
        return SettingsPanel(
            label='Books',
            description='Defaults for the Book product type.',
            schema=self.get_config_schema(),
            category='general',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'default_print_type': {
                    'type': 'string',
                    'default': 'paperback',
                    'title': 'Default print type',
                    'description': 'Pre-selected when a book has no print type set.',
                },
                'default_paper_type': {
                    'type': 'string',
                    'default': '',
                    'title': 'Default paper type',
                },
                'enable_3d_preview': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Enable the 3D cover preview on product pages',
                },
            },
        }
