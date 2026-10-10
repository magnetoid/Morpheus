"""SEO plugin manifest — deep extension."""

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin, SettingsPanel, StorefrontBlock
from morpheus.core import events

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

    # catalog is the one HARD dependency: products, categories and collections
    # are the entities this app describes. Everything else it used to import
    # (cms, book_product, markets, metafields, …) now answers a filter instead.
    requires = ['catalog']

    def ready(self) -> None:
        # The storefront head. Core seeds a fallback title, fires the filter, and
        # this handler produces the real document — so ANY theme that calls
        # `{% storefront_head %}` gets complete, correct SEO, and a store with
        # this app disabled still renders a valid head from the seed.
        self.register_hook(events.STOREFRONT_HEAD, self.on_storefront_head, priority=50)
        # The JSON-LD for one object, for callers with no request (GraphQL's
        # `structuredData` fields) — catalog used to import seo's private
        # helpers for this.
        self.register_hook(
            events.SEO_STRUCTURED_DATA_FOR_OBJECT, self.on_structured_data_for_object, priority=50
        )
        self.register_graphql_extension('plugins.installed.seo.graphql.queries')
        self.register_graphql_extension('plugins.installed.seo.graphql.mutations')
        # surface='chrome': sitemaps, robots.txt, llms.txt and the feeds are
        # machine endpoints, not pages — they must never be language-prefixed
        # (a store with /fr/ was serving /fr/robots.txt as well).
        self.register_urls(
            'plugins.installed.seo.urls', prefix='', namespace='seo', surface='chrome'
        )
        self.register_urls(
            'plugins.installed.seo.urls_dashboard',
            prefix='dashboard/seo/',
            namespace='seo_dashboard',
        )
        # ONE SEO editor, contributed into all four entity forms. Before this,
        # a product had thirteen native SEO columns edited through a bespoke
        # block hardcoded in admin_dashboard while pages used the shared panel —
        # two editors, two storages, and SeoMeta silently outranking the product
        # form's own fields. Disabling this app now removes the card everywhere
        # at once, which is what the disable litmus test asks for.
        for cards_event, saved_event, kind in (
            (events.PRODUCT_FORM_CARDS, events.PRODUCT_FORM_SAVED, 'product'),
            (events.CATEGORY_FORM_CARDS, events.CATEGORY_FORM_SAVED, 'category'),
            (events.COLLECTION_FORM_CARDS, events.COLLECTION_FORM_SAVED, 'collection'),
            (events.PAGE_FORM_CARDS, events.PAGE_FORM_SAVED, 'page'),
        ):
            self.register_hook(cards_event, self._form_card_handler(kind), priority=60)
            self.register_hook(saved_event, self._form_saved_handler(kind), priority=60)
        # The SEO score as a column in the product list, so a merchant can see
        # which products need attention without opening each one.
        self.register_hook(events.PRODUCT_LIST_COLUMNS, self.on_product_list_columns, priority=60)
        self.register_hook(events.PRODUCT_CREATED, self.on_product_created, priority=85)
        self.register_hook(events.PRODUCT_UPDATED, self.on_product_updated, priority=85)
        # Categories + Collections — fired from catalog/signals.py post_save.
        self.register_hook(events.CATEGORY_UPDATED, self.on_category_updated, priority=85)
        self.register_hook('collection.updated', self.on_collection_updated, priority=85)
        # Morpheus Brain — contribute the SEO/content-audit + Core Web Vitals
        # slices to the read-only signal snapshot (disable-gated by the bus).
        self.register_hook(events.BRAIN_SIGNALS, self.on_brain_signals, priority=50)
        # Nightly site-wide crawl. It renders every URL in the sitemap, so it
        # runs here and never in a request — the dashboard reads the cached
        # report. 3:10am keeps it clear of the 4:00/4:30 jobs.
        from celery.schedules import crontab  # noqa: PLC0415

        self.register_celery_tasks('plugins.installed.seo.tasks')
        self.register_celery_beat(
            'seo:site_audit',
            {'task': 'seo.site_audit', 'schedule': crontab(hour=3, minute=10)},
        )
        # CMS pages — wire the post_save signal directly so we don't need
        # a new cms/signals.py + apps.py wiring.
        self._wire_cms_page_signal()
        # Redirect-cache invalidation + automatic slug history. Both have to run
        # on every write path (dashboard, CSV import, an assistant, the admin),
        # so they hang off model signals rather than any one view.
        from plugins.installed.seo import signals  # noqa: PLC0415

        signals.wire()

    # Each shell names its object with its own kwarg (product=, category=,
    # collection=, page=), so the handler has to know which one to look for.
    # A closure per kind keeps that one fact in one place instead of four
    # near-identical methods.
    def _form_card_handler(self, kind: str):
        def handler(value, request=None, **kwargs):
            from plugins.installed.seo.cards import seo_form_card  # noqa: PLC0415

            card = seo_form_card(kind, kwargs.get(kind), request)
            if card:
                value.append(card)
            return value

        handler.__name__ = f'on_{kind}_form_cards'
        return handler

    def _form_saved_handler(self, kind: str):
        def handler(post=None, **kwargs):
            from plugins.installed.seo.services.panel import save_object_seo  # noqa: PLC0415

            obj = kwargs.get(kind)
            if obj is not None and post is not None:
                save_object_seo(obj, post)

        handler.__name__ = f'on_{kind}_form_saved'
        return handler

    def on_product_list_columns(self, value, products=None, request=None, **kwargs):
        from plugins.installed.seo.cards import annotate_seo_scores  # noqa: PLC0415

        if not products:
            return value
        annotate_seo_scores(products)
        value.append(
            {
                'label': 'SEO',
                'cell_template': 'seo/cards/_score_cell.html',
                'order': 60,
            }
        )
        return value

    def on_storefront_head(self, value, request=None, context=None, **kwargs):
        from plugins.installed.seo.head import on_storefront_head  # noqa: PLC0415

        return on_storefront_head(value, request=request, context=context, **kwargs)

    def on_structured_data_for_object(self, value, obj=None, **kwargs):
        if value is not None or obj is None:
            return value
        from plugins.installed.seo.schema import graph_for_object  # noqa: PLC0415

        return graph_for_object(obj)

    def on_brain_signals(self, value, **kwargs):
        """Merge the SEO slice into the Brain snapshot: content-audit scores,
        top unresolved 404s (→ content.*) and Core Web Vitals + structured-data
        flags (→ storefront.*). Every read is defensive; a partial DB never
        breaks the aggregator."""
        from contextlib import suppress  # noqa: PLC0415

        content = value.setdefault('content', {})
        with suppress(Exception):
            from django.db.models import Avg  # noqa: PLC0415

            from plugins.installed.seo.models import SeoAuditResult  # noqa: PLC0415

            low = SeoAuditResult.objects.order_by('score')[:20]
            content['low_seo'] = [{'score': a.score, 'issues': (a.issues or [])[:4]} for a in low]
            content['seo_avg'] = round(
                SeoAuditResult.objects.aggregate(a=Avg('score'))['a'] or 0, 1
            )
            content['seo_low_count'] = SeoAuditResult.objects.filter(score__lt=50).count()
            content['seo_total'] = SeoAuditResult.objects.count()
        with suppress(Exception):
            from plugins.installed.seo.models import NotFoundLog  # noqa: PLC0415

            content['notfound'] = [
                {'path': n.path, 'hits': n.hit_count}
                for n in NotFoundLog.objects.order_by('-hit_count')[:10]
            ]
        store = value.setdefault('storefront', {})
        with suppress(Exception):
            from plugins.installed.seo.services import cwv_summary  # noqa: PLC0415

            store['cwv'] = cwv_summary()
        with suppress(Exception):
            from plugins.installed.seo.services import site_settings  # noqa: PLC0415

            s = site_settings()
            store['seo_flags'] = {
                'Organization JSON-LD': getattr(s, 'jsonld_organization', None),
                'Product JSON-LD': getattr(s, 'jsonld_product', None),
                'WebSite + search box': getattr(s, 'jsonld_website', None),
                'llms.txt': getattr(s, 'llms_txt_enabled', None),
                'AI answer block': getattr(s, 'ai_answer_block_enabled', None),
            }
        return value

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

            from plugins.installed.seo.services.indexnow import ping_in_background  # noqa: PLC0415

            ping_in_background([url])
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
            # Journal RSS/Atom autodiscovery in <head>. Contributed rather than
            # written into the theme so it vanishes with the plugin — the theme
            # once reversed `seo:journal_rss` directly, and with seo disabled
            # that NoReverseMatch took down every storefront page.
            StorefrontBlock(
                slot='global_head',
                template='seo/blocks/feed_links.html',
                priority=20,
            ),
        ]

    def contribute_agent_tools(self) -> list:
        from plugins.installed.seo.agent_tools import (  # noqa: PLC0415
            apply_external_links_tool,
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
            apply_external_links_tool,
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
            apply_external_links_tool,
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
                    apply_external_links_tool,
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
        # there anymore — bookmarks survive, the tabs use the canonical URL.
        return [
            DashboardPage(
                label='Overview',
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
            # Redirects had a URL and a full CRUD screen but no nav entry, so
            # the only way in was a button on another page. A surface nothing
            # links to is a surface nobody uses.
            DashboardPage(
                label='Redirects',
                slug='redirects',
                view='plugins.installed.seo.views.redirects_page',
                icon='corner-up-right',
                section='seo',
                order=45,
                url='/dashboard/seo/redirects/',
            ),
            DashboardPage(
                label='Index rules',
                slug='rules',
                view='plugins.installed.seo.views.index_rules_page',
                icon='filter',
                section='seo',
                order=47,
                url='/dashboard/seo/rules/',
            ),
            DashboardPage(
                label='Templates',
                slug='templates',
                view='plugins.installed.seo.views.templates_page',
                icon='braces',
                section='seo',
                order=48,
                url='/dashboard/seo/templates/',
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
                label='Settings',
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
                'hide_until_launch': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Hide the store from search engines until launch',
                    'description': (
                        'While the store is being set up: every page asks not '
                        'to be indexed or followed, the sitemaps list nothing, '
                        'the AI discovery files are switched off and nothing '
                        'pings IndexNow. Visitors still see the store. Turn it '
                        'off on launch day.'
                    ),
                },
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
