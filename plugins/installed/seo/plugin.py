"""SEO plugin manifest — deep extension."""

from __future__ import annotations

import logging

from morpheus import DashboardPage, Plugin, SettingsPanel, StorefrontBlock, events

logger = logging.getLogger('morpheus.seo')


class SeoPlugin(Plugin):
    name = 'seo'
    label = 'SEO'
    version = '2.0.0'
    description = (
        'Deep SEO + AEO/GEO: per-object meta + full JSON-LD (Product / '
        'Organization / BreadcrumbList / WebSite / Article / FAQ / Review), '
        'OpenGraph + Twitter Cards, sitemap.xml + robots.txt with a 2026 '
        'AI-crawler matrix, redirects + 404 monitor with auto-redirect '
        'suggester, per-product SEO audit + an answer-engine readiness '
        'scorer, a PDP AI-answer / key-facts block, bulk meta editor, '
        'keyword tracking, and LLM discovery surfaces (/llms.txt + '
        '/llms-full.txt + /ai/products.json + /md/products/<slug>).'
    )
    has_models = True

    # Storefront URL templates per model_label. Reverse-resolution via
    # django.urls.reverse() would be cleaner, but the namespace isn't
    # always loaded at signal-fire time (signals fire during apps.ready()
    # before URL conf finishes). String templating keeps it bulletproof.
    _URL_TEMPLATES = {
        'catalog.product': '/products/{slug}/',
        'catalog.category': '/category/{slug}/',
        'catalog.collection': '/collection/{slug}/',
        'cms.page': '/journal/{slug}/',
    }

    def ready(self) -> None:
        self.register_graphql_extension('plugins.installed.seo.graphql.queries')
        self.register_graphql_extension('plugins.installed.seo.graphql.mutations')
        self.register_urls('plugins.installed.seo.urls', prefix='', namespace='seo')
        self.register_urls(
            'plugins.installed.seo.urls_dashboard',
            prefix='dashboard/seo/',
            namespace='seo_dashboard',
        )
        self.register_hook(events.PRODUCT_CREATED, self.on_product_created, priority=85)
        self.register_hook(events.PRODUCT_UPDATED, self.on_product_updated, priority=85)
        # Categories + Collections — fired from catalog/signals.py post_save.
        self.register_hook(events.CATEGORY_UPDATED, self.on_category_updated, priority=85)
        self.register_hook('collection.updated', self.on_collection_updated, priority=85)
        # CMS pages — wire the post_save signal directly so we don't need
        # a new cms/signals.py + apps.py wiring.
        self._wire_cms_page_signal()

    def _wire_cms_page_signal(self) -> None:
        try:
            from django.db.models.signals import post_save  # noqa: PLC0415

            from plugins.installed.cms.models import Page  # noqa: PLC0415
        except Exception as e:  # noqa: BLE001 — cms plugin may be disabled
            logger.debug('seo: cms plugin unavailable, skipping page signal: %s', e)
            return
        post_save.connect(
            self._on_cms_page_saved,
            sender=Page,
            dispatch_uid='seo.indexnow.cms_page',
        )

    def _on_cms_page_saved(self, sender, instance, created, **kwargs):
        # Skip-if-not-published — only ping SERPs for live URLs.
        if getattr(instance, 'state', '') != 'published':
            return
        if not getattr(instance, 'is_live', True):
            return
        self._indexnow_push(model_label='cms.page', slug=instance.slug)

    def on_product_created(self, product, **kwargs):
        try:
            from plugins.installed.seo.services import (  # noqa: PLC0415
                audit_product,
                autofill_meta_for,
                store_audit,
            )

            autofill_meta_for(product)
            store_audit(product, audit_product(product))
        except Exception as e:  # noqa: BLE001 — autofill is best-effort
            logger.warning('seo: autofill/audit failed for %s: %s', product.id, e, exc_info=True)
        self._indexnow_push(model_label='catalog.product', slug=getattr(product, 'slug', ''))

    def on_product_updated(self, product, **kwargs):
        """Refresh the SEO score when a product changes."""
        try:
            from plugins.installed.seo.services import audit_product, store_audit  # noqa: PLC0415

            store_audit(product, audit_product(product))
        except Exception as e:  # noqa: BLE001
            logger.debug('seo: refresh-audit failed for %s: %s', product.id, e)
        self._indexnow_push(model_label='catalog.product', slug=getattr(product, 'slug', ''))

    def on_category_updated(self, category, **kwargs):
        self._indexnow_push(model_label='catalog.category', slug=getattr(category, 'slug', ''))

    def on_collection_updated(self, collection, **kwargs):
        self._indexnow_push(model_label='catalog.collection', slug=getattr(collection, 'slug', ''))

    def _indexnow_push(
        self,
        *,
        url: str | None = None,
        model_label: str | None = None,
        slug: str | None = None,
    ) -> None:
        """Notify Bing/Yandex/Naver/Seznam/Yep about a URL.

        Fire-and-forget — IndexNow failures must never block the
        save/update flow. Skipped when the merchant has disabled
        IndexNow in plugin config.

        Call with either an absolute ``url`` OR ``(model_label, slug)``
        for path-template resolution. Unknown model_labels are dropped
        silently — better to miss a ping than to ship a wrong URL.
        """
        try:
            cfg = self.get_config()
            if not cfg.get('indexnow_enabled', True):
                return

            if url is None:
                if not slug or not model_label:
                    return
                template = self._URL_TEMPLATES.get(model_label)
                if not template:
                    logger.debug('seo: no IndexNow URL template for %s', model_label)
                    return
                from plugins.installed.seo.services import _site_base_url  # noqa: PLC0415

                url = f'{_site_base_url().rstrip("/")}{template.format(slug=slug)}'

            import threading  # noqa: PLC0415

            from plugins.installed.seo.services import ping_indexnow  # noqa: PLC0415

            threading.Thread(target=ping_indexnow, args=([url],), daemon=True).start()
        except Exception as e:  # noqa: BLE001
            logger.debug('seo: IndexNow push failed for %s/%s: %s', model_label, slug, e)

    def contribute_storefront_blocks(self) -> list[StorefrontBlock]:
        """PDP "key facts / AI answer" block.

        Renders the merchant's quotable TL;DR + a labelled spec table on
        the product page itself — the highest-leverage AEO surface, since
        answer engines lift the on-page answer, not just the JSON-LD.
        Opt-in via SiteSeoSettings.ai_answer_block_enabled (default off);
        the block renders nothing until the merchant turns it on AND sets
        an answer / has book metafields. Modular — no theme edit.
        """
        return [
            StorefrontBlock(
                slot='pdp_below_price',
                template='seo/blocks/ai_answer.html',
                priority=40,  # after trust_strip (30); above the fold but below price
                context_keys=['product'],
            ),
        ]

    def contribute_agent_tools(self) -> list:
        from plugins.installed.seo.agent_tools import (  # noqa: PLC0415
            apply_internal_links_tool,
            audit_all_tool,
            audit_product_tool,
            bulk_set_meta_tool,
            create_redirect_tool,
            get_meta_tool,
            list_404s_tool,
            seo_regenerate_sitemap_tool,
            set_meta_tool,
            set_site_settings_tool,
        )

        return [
            get_meta_tool,
            set_meta_tool,
            audit_product_tool,
            audit_all_tool,
            list_404s_tool,
            create_redirect_tool,
            bulk_set_meta_tool,
            set_site_settings_tool,
            apply_internal_links_tool,
            seo_regenerate_sitemap_tool,
        ]

    def contribute_skills(self) -> list:
        """The SEO skill — Linda's Worker opts in via skills=['seo'] when
        the merchant asks about meta tags, redirects, 404s, or sitemap.
        The prelude tells the Worker the proper audit-then-propose-then-apply
        workflow, which would otherwise leak across every conversation.
        """
        from core.agents import Skill  # noqa: PLC0415
        from plugins.installed.seo.agent_tools import (  # noqa: PLC0415
            apply_internal_links_tool,
            audit_all_tool,
            audit_product_tool,
            bulk_set_meta_tool,
            create_redirect_tool,
            get_meta_tool,
            list_404s_tool,
            set_meta_tool,
            set_site_settings_tool,
        )

        return [
            Skill(
                name='seo',
                label='SEO Management',
                description='Audit + tune SEO across the catalog. Meta tags, redirects, 404 cleanup.',
                tools=(
                    get_meta_tool,
                    set_meta_tool,
                    audit_product_tool,
                    audit_all_tool,
                    list_404s_tool,
                    create_redirect_tool,
                    bulk_set_meta_tool,
                    set_site_settings_tool,
                    apply_internal_links_tool,
                ),
                system_prompt_prelude=(
                    'You are working on SEO for this store. Standard workflow:\n'
                    '  1. Audit first — call seo.audit_product or seo.audit_all to '
                    'find what is broken. Never assume.\n'
                    '  2. Propose specific edits with before/after values.\n'
                    '  3. Apply with confirmed=true only after the merchant agrees.\n'
                    'Avoid keyword stuffing; favour natural prose that matches the '
                    'store voice. For 404s, prefer a 301 redirect to a relevant '
                    'live URL over a generic homepage redirect.'
                ),
            )
        ]

    def contribute_dashboard_pages(self) -> list:
        # All URLs point at the canonical /dashboard/seo/<slug>/ route
        # registered via register_urls(prefix='dashboard/seo/'). The
        # legacy /dashboard/apps/seo/<slug>/ path still works (the
        # plugin_page_router resolves it) but nothing in the UI links
        # there anymore — bookmarks survive, sidebar uses canonical.
        return [
            DashboardPage(
                label='SEO',
                slug='overview',
                view='plugins.installed.seo.views.seo_overview',
                icon='search',
                section='seo',
                order=10,
                url='/dashboard/seo/',
            ),
            DashboardPage(
                label='Bulk meta',
                slug='bulk-meta',
                view='plugins.installed.seo.views.bulk_meta',
                icon='edit-3',
                section='seo',
                order=20,
                url='/dashboard/seo/bulk-meta/',
            ),
            DashboardPage(
                label='Audit',
                slug='audit',
                view='plugins.installed.seo.views.audit_page',
                icon='gauge',
                section='seo',
                order=30,
                url='/dashboard/seo/audit/',
            ),
            DashboardPage(
                label='404s',
                slug='not-found',
                view='plugins.installed.seo.views.not_found_log',
                icon='alert-triangle',
                section='seo',
                order=40,
                url='/dashboard/seo/not-found/',
            ),
            DashboardPage(
                label='Keywords',
                slug='keywords',
                view='plugins.installed.seo.views.keywords_page',
                icon='hash',
                section='seo',
                order=50,
                url='/dashboard/seo/keywords/',
            ),
            DashboardPage(
                label='Sitemap',
                slug='sitemap',
                view='plugins.installed.seo.views.sitemap_page',
                icon='map',
                section='seo',
                order=55,
                url='/dashboard/seo/sitemap/',
            ),
            DashboardPage(
                label='Structured data',
                slug='schema',
                view='plugins.installed.seo.views.schema_index',
                icon='braces',
                section='seo',
                order=57,
                url='/dashboard/seo/schema/',
            ),
            DashboardPage(
                label='Site SEO settings',
                slug='settings',
                view='plugins.installed.seo.views.seo_settings_page',
                icon='settings',
                section='seo',
                order=60,
                url='/dashboard/seo/settings/',
            ),
        ]

    def get_config_schema(self):
        """Site-wide SEO toggles stored on PluginConfig['seo'].

        These are the knobs that don't live on the SiteSeoSettings
        model (which carries the organization metadata, social URLs,
        verification codes, etc. and is edited via /dashboard/seo/
        settings/). Everything here is a boolean or simple scalar
        the merchant might want to tune from the unified settings
        panel without diving into the dedicated SEO dashboard.
        """
        return {
            'type': 'object',
            'properties': {
                # ── Search-engine ping fan-out ────────────────────────
                'indexnow_enabled': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Push updates via IndexNow',
                    'description': 'Notify Bing / Yandex / Naver / Seznam / Yep when a product is created or updated. Fire-and-forget; never blocks the save.',
                },
                'ping_google_on_sitemap_change': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Ping Google + Bing when the sitemap changes',
                    'description': 'Sends a sitemap-changed ping when SitemapEntry rows are added / removed in the dashboard.',
                },
                # ── Sitemap shapes ────────────────────────────────────
                'image_sitemap_enabled': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Image sitemap',
                    'description': 'Emit /sitemap-images.xml with product image URLs so Google Images can index them faster.',
                },
                'news_sitemap_enabled': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Google News sitemap',
                    'description': 'Emit /sitemap-news.xml for blog / press content. Only enable if you run editorial content under Google News guidelines.',
                },
                'news_sitemap_max_age_hours': {
                    'type': 'integer',
                    'default': 168,
                    'title': 'News sitemap max age (hours)',
                    'description': 'Google News wants only entries from the last 48 h, but a wider window helps re-indexing. Default 168 (one week).',
                },
                'sitemap_max_urls_per_file': {
                    'type': 'integer',
                    'default': 50000,
                    'title': 'Sitemap split size (URLs)',
                    'description': 'Hard cap is 50,000 per file (Google requirement). Lower this to chunk earlier if your sitemaps grow large.',
                },
                # ── AI discovery + LLM training control ───────────────
                'include_pricing_in_llms_txt': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Include pricing in /llms.txt',
                    'description': 'When on, LLM crawlers see live prices in /llms.txt — improves citation accuracy in ChatGPT / Perplexity / AI Overviews.',
                },
                'include_inventory_in_llms_txt': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Include stock status in /llms.txt',
                    'description': 'Surfaces in-stock / out-of-stock signals. Off by default because inventory can churn fast and stale LLM caches embarrass.',
                },
                'ai_crawler_default_allow': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Allow unknown AI crawlers by default',
                    'description': "When a new AI crawler hits us with a UA we don't recognise, default to allow. Tighten by listing specific UAs in /dashboard/seo/settings/.",
                },
                # ── Schema.org defaults ───────────────────────────────
                'organization_type': {
                    'type': 'string',
                    'enum': [
                        'Organization',
                        'LocalBusiness',
                        'Store',
                        'OnlineStore',
                        'BookStore',
                        'Publisher',
                    ],
                    'default': 'OnlineStore',
                    'title': 'Organization @type',
                    'description': 'JSON-LD @type emitted for the site-wide Organization schema. Use BookStore / Publisher for book-focused stores; LocalBusiness adds geo fields.',
                },
                'gtin_field_preference': {
                    'type': 'string',
                    'enum': ['isbn13', 'gtin13', 'gtin12', 'gtin8', 'auto'],
                    'default': 'auto',
                    'title': 'Preferred GTIN field',
                    'description': "Which barcode property to emit in Product JSON-LD. 'auto' picks the right one from the variant.barcode length.",
                },
                # ── Google Book structured data ───────────────────────
                # developers.google.com/search/docs/appearance/structured-data/book
                'book_structured_data': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Emit Book structured data',
                    'description': 'Add Google Book JSON-LD (Work → Edition → ReadAction) on book product pages, alongside the Product graph, so titles can qualify for Book rich results / Book Actions. Needs an author; an ISBN on the book makes it eligible to surface.',
                },
                'book_offer_category': {
                    'type': 'string',
                    'enum': ['purchase', 'rental', 'free', 'subscription', 'nologinrequired'],
                    'default': 'purchase',
                    'title': 'Book action type',
                    'description': "How a reader obtains the book through the Book ReadAction offer. 'purchase' for a normal store; price is only emitted for purchase/rental.",
                },
                'book_eligible_region': {
                    'type': 'string',
                    'default': 'US',
                    'title': 'Book offer region',
                    'description': 'ISO 3166-1 alpha-2 country the Book offer applies to (e.g. US, GB). Falls back to the shipping country.',
                },
                'book_action_platforms': {
                    'type': 'string',
                    'default': 'desktop,android,ios',
                    'title': 'Book action platforms',
                    'description': 'Comma-separated platforms the buy/read link works on: any of desktop, android, ios.',
                },
                # ── Organization contact + address (knowledge panel) ──
                'org_email': {
                    'type': 'string',
                    'default': '',
                    'title': 'Public contact email',
                    'description': 'Shown to Google as the Organization ContactPoint (customer service). Leave blank to omit.',
                },
                'org_phone': {
                    'type': 'string',
                    'default': '',
                    'title': 'Public contact phone',
                    'description': 'E.164 preferred (e.g. +1-800-555-0199). Emitted as the Organization ContactPoint telephone.',
                },
                'org_street': {
                    'type': 'string',
                    'default': '',
                    'title': 'Street address',
                    'description': 'Organization PostalAddress streetAddress. Fill the address fields for a richer brand/knowledge panel.',
                },
                'org_city': {
                    'type': 'string',
                    'default': '',
                    'title': 'City',
                    'description': 'Organization PostalAddress addressLocality.',
                },
                'org_region': {
                    'type': 'string',
                    'default': '',
                    'title': 'State / region',
                    'description': 'Organization PostalAddress addressRegion (e.g. CA).',
                },
                'org_postal': {
                    'type': 'string',
                    'default': '',
                    'title': 'Postal code',
                    'description': 'Organization PostalAddress postalCode.',
                },
                'org_country': {
                    'type': 'string',
                    'default': '',
                    'title': 'Country',
                    'description': 'Organization PostalAddress addressCountry (ISO 3166-1 alpha-2, e.g. US).',
                },
                # ── Crawl + indexability ──────────────────────────────
                'noindex_thin_pdp_below_words': {
                    'type': 'integer',
                    'default': 0,
                    'title': 'Auto-noindex PDPs with descriptions shorter than (words)',
                    'description': '0 disables. Setting 50 means any product page whose description has fewer than 50 words gets robots=noindex,follow until the merchant fills it in.',
                },
                'canonical_strip_query_params': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Strip query params from canonical URLs',
                    'description': 'Standard SEO hygiene — the canonical link should point to the clean URL even when the visitor arrived with utm_/fbclid/gclid params.',
                },
                # ── Performance + UX signals ──────────────────────────
                'lazy_load_below_fold_images': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Lazy-load below-the-fold images',
                    'description': 'Adds loading="lazy" to img tags below the first viewport. Faster LCP, lower bandwidth.',
                },
                'preconnect_to_cdn': {
                    'type': 'string',
                    'default': '',
                    'title': 'Preconnect <link> to CDN host',
                    'description': 'Optional host to preconnect to (e.g. cdn.example.com). Speeds first image load when you serve media from a separate CDN.',
                },
            },
        }

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='SEO',
            description='Site-wide SEO defaults, JSON-LD, AI discovery feeds, audits. Per-object meta lives on individual products / categories / pages; this panel is the global knobs.',
            schema=self.get_config_schema(),
            category='channels',
        )
