"""SEO service layer — meta resolution, JSON-LD, sitemaps, AI-crawler files,
IndexNow, image variants, audit, and 404 monitoring.

This package replaces the original 1907-LOC ``services.py`` monolith.
External callers keep importing from
``plugins.installed.seo.services`` unchanged — the re-exports below
are shape-identical (including the four leading-underscore symbols
that views.py / catalog.graphql / templatetags depend on).

Layout:
  * _helpers.py     — ResolvedMeta dataclass, logger,
                      _site_base_url, site_settings,
                      _seo_plugin_cfg, _jsonld_dump, _seo_plugin.
  * meta.py         — resolve_meta, _structured_data_for,
                      autofill_meta_for.
  * jsonld.py       — organization / website / breadcrumb / product /
                      speakable / collection_page / qa_page /
                      article / faq JSON-LD generators.
  * sitemaps.py     — iter_sitemap_entries + sitemap_counts +
                      render_sitemap_xml (main + index + news +
                      image) + render_opensearch_xml.
  * crawler_files.py — AI_CRAWLERS catalogue, get_ai_crawler_policy,
                      render_robots_txt, render_llms_txt.
  * indexnow.py     — get_or_create_indexnow_key, ping_indexnow.
  * redirects.py    — resolve_redirect, record_404, suggest_redirect,
                      refresh_404_suggestions.
  * images.py       — ALLOWED_IMAGE_WIDTHS/FORMATS,
                      parse_image_variant_path, generate_image_variant.
  * ai_feeds.py     — render_product_markdown, render_ai_products_feed.
  * audit.py        — audit_product, store_audit, audit_all_products,
                      suggest_internal_links_for.
"""

from __future__ import annotations

# Helpers / settings / serialization.
from ._helpers import (
    ResolvedMeta,
    _jsonld_dump,
    _seo_plugin_cfg,
    _site_base_url,
    logger,
    site_settings,
)

# Meta resolution.
from .meta import (
    _structured_data_for,
    autofill_meta_for,
    resolve_meta,
)

# JSON-LD generators.
from .jsonld import (
    aggregate_offer,
    article_jsonld,
    book_jsonld,
    breadcrumb_jsonld,
    collection_page_jsonld,
    faq_jsonld,
    organization_jsonld,
    product_jsonld,
    qa_page_jsonld,
    speakable_jsonld,
    video_jsonld,
    website_jsonld,
)

# Sitemaps + OpenSearch.
from .sitemaps import (
    _sitemap_max_urls,
    iter_sitemap_entries,
    regenerate_sitemap,
    render_image_sitemap_xml,
    render_news_sitemap_xml,
    render_opensearch_xml,
    render_sitemap_index_xml,
    render_sitemap_xml,
    sitemap_counts,
)

# Crawler-facing files.
from .crawler_files import (
    AI_CRAWLERS,
    get_ai_crawler_policy,
    render_llms_txt,
    render_robots_txt,
)

# IndexNow.
from .indexnow import (
    get_or_create_indexnow_key,
    ping_indexnow,
)

# Redirects + 404 monitor.
from .redirects import (
    record_404,
    refresh_404_suggestions,
    resolve_redirect,
    suggest_redirect,
)

# Image variants.
from .images import (
    ALLOWED_IMAGE_FORMATS,
    ALLOWED_IMAGE_WIDTHS,
    generate_image_variant,
    parse_image_variant_path,
)

# AI feeds.
from .ai_feeds import (
    render_ai_products_feed,
    render_product_markdown,
)

# Audit + internal-link suggester.
from .audit import (
    audit_all_products,
    audit_product,
    score_aeo,
    store_audit,
    suggest_internal_links_for,
)

# Core Web Vitals (field data).
from .cwv import cwv_summary

# Backwards-compat re-export. The old monolith did
# `from plugins.installed.seo.models import SeoMeta` at module level
# (line 22 of services.py with a noqa) so that `services.SeoMeta`
# resolved; keeping it here for any caller that grew to rely on it.
from plugins.installed.seo.models import SeoMeta  # noqa: F401

__all__ = [
    # helpers
    'ResolvedMeta',
    '_jsonld_dump',
    'aggregate_offer',
    '_seo_plugin_cfg',
    '_site_base_url',
    'logger',
    'site_settings',
    # meta
    '_structured_data_for',
    'autofill_meta_for',
    'resolve_meta',
    # jsonld
    'article_jsonld',
    'book_jsonld',
    'breadcrumb_jsonld',
    'collection_page_jsonld',
    'faq_jsonld',
    'organization_jsonld',
    'product_jsonld',
    'qa_page_jsonld',
    'speakable_jsonld',
    'video_jsonld',
    'website_jsonld',
    # sitemaps
    '_sitemap_max_urls',
    'iter_sitemap_entries',
    'render_image_sitemap_xml',
    'render_news_sitemap_xml',
    'render_opensearch_xml',
    'render_sitemap_index_xml',
    'render_sitemap_xml',
    'sitemap_counts',
    'regenerate_sitemap',
    # crawler files
    'AI_CRAWLERS',
    'get_ai_crawler_policy',
    'render_llms_txt',
    'render_robots_txt',
    # indexnow
    'get_or_create_indexnow_key',
    'ping_indexnow',
    # redirects
    'record_404',
    'refresh_404_suggestions',
    'resolve_redirect',
    'suggest_redirect',
    # images
    'ALLOWED_IMAGE_FORMATS',
    'ALLOWED_IMAGE_WIDTHS',
    'generate_image_variant',
    'parse_image_variant_path',
    # ai feeds
    'render_ai_products_feed',
    'render_product_markdown',
    # audit
    'audit_all_products',
    'audit_product',
    'score_aeo',
    'store_audit',
    'suggest_internal_links_for',
    # core web vitals
    'cwv_summary',
    # legacy re-export
    'SeoMeta',
]

# ruff: noqa: I001
# Imports are intentionally grouped by service layer (helpers → meta →
# jsonld → sitemaps → … → audit) with section comments, not alphabetised
# by module — that ordering documents the package structure.
