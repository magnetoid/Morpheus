"""JSON-LD generators for every storefront surface.

Each function returns a dict ready to be ``json.dumps``-ed into a
``<script type="application/ld+json">``. They never raise; the broad
``except`` blocks below are intentional — a malformed product or
missing metafield should not block a page render.
"""

# ruff: noqa: PLC0415, I001, SIM105, S110, PLR0912, PLR0915
# Inline imports avoid circular deps + keep optional plugins (inventory,
# metafields, reviews) soft; the broad try/except blocks are deliberate
# (a malformed product must never block a render). Same convention as
# views_split/products.py.

from __future__ import annotations

import contextlib

from ._helpers import (
    _seo_plugin,
    _seo_plugin_cfg,
    _site_base_url,
    ai_answer_for,
    site_settings,
    strip_html,
)


def organization_jsonld() -> dict | None:
    s = site_settings()
    if not getattr(s, 'jsonld_organization', True):
        return None
    if not s.organization_name:
        return None
    # @type comes from PluginConfig['seo']['organization_type'] —
    # merchant can pick Store / OnlineStore / BookStore / Publisher
    # to give Google a more accurate signal about what kind of
    # business this is. Default: 'OnlineStore'.
    org_type = 'OnlineStore'
    seo_plugin = _seo_plugin()
    if seo_plugin is not None:
        try:
            org_type = (
                seo_plugin.get_config_value(
                    'organization_type',
                    'OnlineStore',
                )
                or 'OnlineStore'
            ).strip() or 'OnlineStore'
        except Exception:  # noqa: BLE001
            pass

    same_as = [
        u
        for u in (s.facebook_url, s.instagram_url, s.linkedin_url, s.youtube_url, s.tiktok_url)
        if u
    ]
    out = {
        '@context': 'https://schema.org',
        '@type': org_type,
        'name': s.organization_name,
        'url': _site_base_url(),
    }
    if s.organization_logo_url:
        out['logo'] = s.organization_logo_url
    if same_as:
        out['sameAs'] = same_as
    return out


def website_jsonld() -> dict | None:
    s = site_settings()
    if not getattr(s, 'jsonld_website', True):
        return None
    base = _site_base_url()
    out = {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        'url': base,
    }
    if s.organization_name:
        out['name'] = s.organization_name
    if s.enable_sitelinks_search:
        out['potentialAction'] = {
            '@type': 'SearchAction',
            'target': f'{base.rstrip("/")}/search/?q={{search_term_string}}',
            'query-input': 'required name=search_term_string',
        }
    return out


def breadcrumb_jsonld(items: list[dict]) -> dict:
    """`items` = [{'name': str, 'url': str}, …] in order."""
    return {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': [
            {'@type': 'ListItem', 'position': i + 1, 'name': it['name'], 'item': it['url']}
            for i, it in enumerate(items)
        ],
    }


def product_jsonld(product, *, base_url: str = '') -> dict:
    """Rich Product structured data.

    `product` may be a Django model instance (SSR path) OR a dict (when
    fed by GraphQL via a template tag). Accessor helper normalises both.
    """
    base = base_url or _site_base_url()

    def _abs(u: str) -> str:
        # Google requires absolute image URLs; model .url is site-relative.
        u = u or ''
        if not u or u.startswith(('http://', 'https://')):
            return u
        return base.rstrip('/') + '/' + u.lstrip('/')

    def g(name, default=None):
        if isinstance(product, dict):
            return product.get(name, default)
        # getattr's default only catches AttributeError; a djmoney/deferred
        # field raises KeyError when the instance was loaded with .only()/
        # .defer() and that field wasn't selected — guard so JSON-LD never 500s.
        try:
            return getattr(product, name, default)
        except Exception:  # noqa: BLE001
            return default

    slug = g('slug') or ''
    if not slug:
        return {}
    if not getattr(site_settings(), 'jsonld_product', True):
        return {}

    url = f'{base.rstrip("/")}/products/{slug}/'
    description = strip_html(g('short_description') or g('description') or '')
    out: dict = {
        '@context': 'https://schema.org',
        '@type': 'Product',
        'name': g('name') or '',
        'sku': g('sku') or '',
        'url': url,
        'description': description[:500],
    }

    # AEO answer — the merchant's quotable TL;DR (seo.ai_answer metafield).
    # Emitted as schema.org `disambiguatingDescription`: a short, factual
    # restatement that AI answer engines (ChatGPT / Perplexity / AI
    # Overviews) can lift verbatim and attribute. ORM-only.
    if not isinstance(product, dict):
        answer = ai_answer_for(product)
        if answer:
            out['disambiguatingDescription'] = answer[:600]

    # Book subtype — if any namespace='book' metafields are attached to
    # this product, upgrade @type to ['Product', 'Book'] and surface the
    # Book-specific properties. Books-only storefront → AI engines + SERP
    # rich results want Book over generic Product. Guarded so a missing
    # metafields plugin doesn't break JSON-LD rendering.
    book_mf: dict = {}
    if not isinstance(product, dict):
        try:
            from plugins.installed.book_product.compat import book_attrs

            book_mf = book_attrs(product)
        except Exception:  # noqa: BLE001
            book_mf = {}
        if book_mf:
            out['@type'] = ['Product', 'Book']
            fmt_raw = str(book_mf.get('format') or '').strip().lower()
            fmt_map = {
                'hardcover': 'https://schema.org/Hardcover',
                'paperback': 'https://schema.org/Paperback',
                'ebook': 'https://schema.org/EBook',
                'audio': 'https://schema.org/AudiobookFormat',
                'audiobook': 'https://schema.org/AudiobookFormat',
            }
            if fmt_raw in fmt_map:
                out['bookFormat'] = fmt_map[fmt_raw]
            pages_raw = book_mf.get('pages')
            if pages_raw is not None and str(pages_raw).strip():
                with contextlib.suppress(TypeError, ValueError):
                    out['numberOfPages'] = int(str(pages_raw).strip())
            if book_mf.get('language'):
                out['inLanguage'] = str(book_mf['language'])
            if book_mf.get('published_year'):
                out['datePublished'] = str(book_mf['published_year'])
            if book_mf.get('author'):
                out['author'] = {
                    '@type': 'Person',
                    'name': str(book_mf['author']),
                }
    # dateModified — Perplexity decays citations after ~13 weeks and AI
    # Overviews favour ≤60-day content. updated_at is auto_now=True on
    # the Product model so it bumps on every save.
    updated = g('updated_at') or g('updatedAt')
    if updated:
        try:
            out['dateModified'] = (
                updated.isoformat() if hasattr(updated, 'isoformat') else str(updated)
            )
        except Exception:  # noqa: BLE001
            pass

    # Image — Google's Product guidance lists `image` as a *repeated*
    # property and recommends several photos per product (it also picks
    # the best aspect ratio per surface). Emit the whole gallery
    # (primary first, capped) for ORM products; the GraphQL/dict path
    # keeps its single primary URL. Falls back to the old single-image
    # behaviour when no gallery rows exist.
    images: list[str] = []
    if not isinstance(product, dict):
        try:
            for pi in product.images.order_by('-is_primary', 'sort_order')[:8]:
                u = _abs(getattr(getattr(pi, 'image', None), 'url', '') or '')
                if u and u not in images:
                    images.append(u)
        except Exception:  # noqa: BLE001
            images = []
    if images:
        out['image'] = images if len(images) > 1 else images[0]
    else:
        primary = g('primary_image')
        if primary:
            if isinstance(primary, dict):
                out['image'] = _abs(primary.get('url') or primary.get('image_url') or '')
            elif getattr(primary, 'image', None):
                out['image'] = _abs(primary.image.url)
        elif g('primary_image_url'):
            out['image'] = _abs(g('primary_image_url'))

    # Category: model has .category.name; dict has .category as nested.
    cat = g('category')
    if cat:
        out['category'] = cat.get('name') if isinstance(cat, dict) else getattr(cat, 'name', '')

    # Offer
    offer_price = ''
    offer_curr = 'USD'
    price = g('price')
    if price is not None:
        avail = 'https://schema.org/InStock'
        # Stock check is ORM-only; skip silently for dicts.
        try:
            if not isinstance(product, dict):
                from plugins.installed.inventory.models import StockLevel
                from django.db.models import Sum, F

                stock = (
                    StockLevel.objects.filter(variant__product=product).aggregate(
                        qty=Sum(F('quantity') - F('reserved_quantity'))
                    )['qty']
                    or 0
                )
                if stock <= 0:
                    avail = 'https://schema.org/OutOfStock'
        except Exception:  # noqa: BLE001
            pass
        if isinstance(price, dict):
            offer_price = str(price.get('amount', ''))
            offer_curr = str(price.get('currency', 'USD'))
        else:
            offer_price = str(getattr(price, 'amount', price))
            offer_curr = str(getattr(price, 'currency', 'USD'))
        out['offers'] = {
            '@type': 'Offer',
            'price': offer_price,
            'priceCurrency': offer_curr,
            'availability': avail,
            'url': url,
            # New goods; Google recommends itemCondition for merchant listings.
            'itemCondition': 'https://schema.org/NewCondition',
        }
        # priceValidUntil — Google emits a "missing field" warning without it.
        # Roll a year forward from today so the offer never reads as expired.
        try:
            from datetime import timedelta

            from django.utils import timezone

            out['offers']['priceValidUntil'] = (
                timezone.now().date() + timedelta(days=365)
            ).isoformat()
        except Exception:  # noqa: BLE001
            pass
        # MerchantReturnPolicy + OfferShippingDetails — 2026 Required
        # for Merchant free listings + AI shopping comparisons. Values
        # live in the SEO plugin's PluginConfig JSON so no migration.
        commerce_cfg = _seo_plugin_cfg()
        return_days = int(commerce_cfg.get('return_days') or 0)
        ship_fee = commerce_cfg.get('shipping_fee_amount') or '0'
        free_over = commerce_cfg.get('free_shipping_over') or '0'
        country = (commerce_cfg.get('shipping_country') or 'US').upper()
        # Handling + transit windows are merchant-tunable via the SEO
        # plugin config — defaults match the hard-coded values they
        # replaced (0-1d handling, 2-5d transit). Coerced to int so a
        # stray string in the config JSON doesn't break rendering.
        try:
            handling_min = int(commerce_cfg.get('handling_days_min', 0) or 0)
        except (TypeError, ValueError):
            handling_min = 0
        try:
            handling_max = int(commerce_cfg.get('handling_days_max', 1) or 0)
        except (TypeError, ValueError):
            handling_max = 1
        try:
            transit_min = int(commerce_cfg.get('transit_days_min', 2) or 0)
        except (TypeError, ValueError):
            transit_min = 2
        try:
            transit_max = int(commerce_cfg.get('transit_days_max', 5) or 0)
        except (TypeError, ValueError):
            transit_max = 5
        if return_days:
            out['offers']['hasMerchantReturnPolicy'] = {
                '@type': 'MerchantReturnPolicy',
                'applicableCountry': country,
                'returnPolicyCategory': 'https://schema.org/MerchantReturnFiniteReturnWindow',
                'merchantReturnDays': return_days,
                'returnMethod': 'https://schema.org/ReturnByMail',
                'returnFees': 'https://schema.org/FreeReturn',
            }
        out['offers']['shippingDetails'] = {
            '@type': 'OfferShippingDetails',
            'shippingDestination': {
                '@type': 'DefinedRegion',
                'addressCountry': country,
            },
            'shippingRate': {
                '@type': 'MonetaryAmount',
                'value': str(ship_fee),
                'currency': offer_curr,
            },
            'deliveryTime': {
                '@type': 'ShippingDeliveryTime',
                'handlingTime': {
                    '@type': 'QuantitativeValue',
                    'minValue': handling_min,
                    'maxValue': handling_max,
                    'unitCode': 'DAY',
                },
                'transitTime': {
                    '@type': 'QuantitativeValue',
                    'minValue': transit_min,
                    'maxValue': transit_max,
                    'unitCode': 'DAY',
                },
            },
        }
        if free_over:
            out['offers']['shippingDetails']['freeShippingThreshold'] = {
                '@type': 'MonetaryAmount',
                'value': str(free_over),
                'currency': offer_curr,
            }

    # Aggregate rating + Review nodes — ORM only, and only while the
    # merchant keeps "Product reviews" structured data switched on.
    if not isinstance(product, dict) and getattr(site_settings(), 'jsonld_reviews', True):
        try:
            from django.db.models import Avg, Count

            agg = product.reviews.aggregate(avg=Avg('rating'), n=Count('id'))
            if agg['n']:
                out['aggregateRating'] = {
                    '@type': 'AggregateRating',
                    'ratingValue': round(float(agg['avg'] or 0), 1),
                    'reviewCount': agg['n'],
                }
        except Exception:  # noqa: BLE001
            pass

        # Individual Review nodes — without these, SERP star-rating
        # rich results get stripped (Google requires the rated item to
        # have at least one Review with reviewBody alongside the
        # aggregate). AI engines also have nothing concrete to cite.
        # Cap at 5 to keep the JSON-LD payload bounded. Guarded so a
        # missing reviews plugin / model doesn't break rendering.
        try:
            review_nodes: list[dict] = []
            for r in product.reviews.filter(is_approved=True)[:5]:
                body = (getattr(r, 'body', None) or getattr(r, 'content', None) or '').strip()
                if not body:
                    continue
                author_name = getattr(r, 'author_name', None) or (
                    r.customer.full_name if getattr(r, 'customer', None) else 'Customer'
                )
                node: dict = {
                    '@type': 'Review',
                    'reviewBody': body,
                    'reviewRating': {
                        '@type': 'Rating',
                        'ratingValue': r.rating,
                        'bestRating': 5,
                    },
                    'author': {'@type': 'Person', 'name': author_name},
                }
                if getattr(r, 'created_at', None):
                    node['datePublished'] = r.created_at.date().isoformat()
                review_nodes.append(node)
            if review_nodes:
                out['review'] = review_nodes
        except Exception:  # noqa: BLE001
            pass

    # AI shopping hint — `agent_metadata` already structured for agents.
    am = g('agent_metadata')
    if am:
        out['additionalProperty'] = [
            {'@type': 'PropertyValue', 'name': k, 'value': str(v)[:200]}
            for k, v in (am if isinstance(am, dict) else {}).items()
        ][:25]

    # ProductGroup variants — schema.org's hasVariant unlocks variant
    # cards in Google AI Shopping. Only emit when variants exist.
    if not isinstance(product, dict):
        try:
            variants = (
                list(getattr(product, 'variants', None).filter(is_active=True)[:20])
                if getattr(product, 'variants', None)
                else []
            )
            if variants:
                # Preserve Book subtype if it was added above — emit
                # ['ProductGroup', 'Book'] so we don't lose the Book
                # signal AI engines + SERP rich results use.
                if isinstance(out.get('@type'), list) and 'Book' in out['@type']:
                    out['@type'] = ['ProductGroup', 'Book']
                else:
                    out['@type'] = 'ProductGroup'
                out['productGroupID'] = str(getattr(product, 'id', '') or slug)
                out['hasVariant'] = [
                    {
                        '@type': 'Product',
                        'sku': v.sku or '',
                        'name': v.name or '',
                        'offers': {
                            '@type': 'Offer',
                            'price': str(
                                getattr(v, 'price', None).amount
                                if getattr(v, 'price', None)
                                else (offer_price if price is not None else '')
                            ),
                            'priceCurrency': str(
                                getattr(v, 'price', None).currency
                                if getattr(v, 'price', None)
                                else (offer_curr if price is not None else 'USD')
                            ),
                            'availability': 'https://schema.org/InStock',
                        },
                    }
                    for v in variants
                ]
        except Exception:  # noqa: BLE001
            pass

    # Entity-graph sameAs links via metafield 'seo.same_as' (comma- or
    # newline-separated URLs). March-2026 core update made this the #1
    # leverage point for AI engines.
    if not isinstance(product, dict):
        try:
            from django.contrib.contenttypes.models import ContentType
            from plugins.installed.metafields.models import Metafield

            ct = ContentType.objects.get_for_model(type(product))
            m = Metafield.objects.filter(
                content_type=ct,
                object_id=product.pk,
                namespace='seo',
                key='same_as',
            ).first()
            if m and m.value:
                urls = [u.strip() for u in str(m.value).replace('\n', ',').split(',') if u.strip()]
                if urls:
                    out['sameAs'] = urls[:10]
        except Exception:  # noqa: BLE001
            pass

    # GTIN / brand via 'book' metafield namespace (used by dotbooks)
    # AND via ProductVariant.barcode (Phase 1 of variant Shopify
    # parity — every variant carries an optional UPC / EAN / ISBN).
    if not isinstance(product, dict):
        candidate_barcode = ''
        try:
            from plugins.installed.book_product.compat import book_attrs

            book_meta = book_attrs(product)
            if book_meta.get('isbn'):
                candidate_barcode = str(book_meta['isbn']).strip()
            if book_meta.get('publisher'):
                out['brand'] = {'@type': 'Brand', 'name': str(book_meta['publisher'])}
            if book_meta.get('author'):
                out['author'] = {'@type': 'Person', 'name': str(book_meta['author'])}
        except Exception:  # noqa: BLE001
            pass
        # Variant-level barcode wins when present — closer to source.
        try:
            first_variant_barcode = (
                product.variants.exclude(barcode='').values_list('barcode', flat=True).first()
            )
            if first_variant_barcode:
                candidate_barcode = str(first_variant_barcode).strip()
        except Exception:  # noqa: BLE001
            pass
        if candidate_barcode:
            # Emit the right schema.org GTIN property based on the
            # configured preference. 'auto' picks the variant by length:
            # 8 → gtin8, 12 → gtin12, 13 → gtin13 (also ISBN-13).
            pref = 'auto'
            seo_plugin = _seo_plugin()
            if seo_plugin is not None:
                try:
                    pref = (
                        seo_plugin.get_config_value(
                            'gtin_field_preference',
                            'auto',
                        )
                        or 'auto'
                    ).lower()
                except Exception:  # noqa: BLE001
                    pass
            digits = ''.join(c for c in candidate_barcode if c.isdigit())
            field_name = 'gtin13'
            if pref == 'auto':
                length = len(digits)
                if length == 8:
                    field_name = 'gtin8'
                elif length == 12:
                    field_name = 'gtin12'
                elif length == 13:
                    field_name = 'gtin13'
                else:
                    field_name = 'gtin'  # generic fallback
            elif pref == 'isbn13':
                field_name = 'gtin13'  # schema.org uses gtin13 for ISBN-13
                # ALSO emit it as ISBN so Google Books picks it up.
                out['isbn'] = (digits or candidate_barcode)[:13]
            elif pref in ('gtin8', 'gtin12', 'gtin13'):
                field_name = pref
            out[field_name] = (digits or candidate_barcode)[
                : int(''.join(c for c in field_name if c.isdigit()) or 14)
            ]
        # Explicit product-identifier metafields (ISBN-13→isbn, EAN→gtin13,
        # UPC→gtin12, GTIN-14→gtin14, MPN→mpn, ASIN→asin) — emitted for ANY
        # product and authoritative: a code the merchant set explicitly wins
        # over the isbn/barcode-derived value above. Same registry as the
        # PDP + editor (metafields.identifiers).
        try:
            from plugins.installed.metafields.identifiers import product_identifiers

            for code in product_identifiers(product):
                if code['jsonld']:
                    out[code['jsonld']] = code['value']
        except Exception:  # noqa: BLE001
            pass

    return out


def speakable_jsonld(selectors: list[str] | None = None) -> dict:
    """SpeakableSpecification — tells voice assistants which CSS selectors
    contain text suitable for spoken reading.

    Defaults target the page's headline + the lede paragraph, which work
    on every storefront template we ship.
    """
    css = selectors or ['h1', '.lede', '[itemprop="description"]']
    return {
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        'speakable': {
            '@type': 'SpeakableSpecification',
            'cssSelector': css,
        },
    }


def collection_page_jsonld(
    *,
    name: str,
    url: str,
    description: str,
    items: list[dict],
    kind: str = 'CollectionPage',
    total: int | None = None,
) -> dict:
    """CollectionPage + ItemList for PLP/category pages.

    Each `items[i]` is a dict with at least {name, url, image}. Tells AI
    engines that this URL is a list of products under a topic — Google
    AI Overviews use this to assemble "show me [topic] from X" answers.

    `total` lets callers pass the FULL queryset count so numberOfItems
    reflects the collection size, not just the sliced top-60. Falls back
    to len(items) when unset (backward-compatible). `kind` is the outer
    @type and defaults to 'CollectionPage'.
    """
    base = _site_base_url().rstrip('/')
    return {
        '@context': 'https://schema.org',
        '@type': kind,
        'name': name[:120],
        'url': url,
        'description': (description or '')[:400],
        'isPartOf': {'@type': 'WebSite', '@id': base},
        'mainEntity': {
            '@type': 'ItemList',
            'numberOfItems': total if total is not None else len(items),
            'itemListOrder': 'https://schema.org/ItemListOrderDescending',
            'itemListElement': [
                {
                    '@type': 'ListItem',
                    'position': idx + 1,
                    'url': it.get('url') or '',
                    'name': (it.get('name') or '')[:120],
                    **({'image': it['image']} if it.get('image') else {}),
                }
                for idx, it in enumerate(items[:60])
            ],
        },
    }


def qa_page_jsonld(*, name: str, url: str, qa: list[dict]) -> dict:
    """QAPage schema — ChatGPT cites QAPage ~58% more than FAQPage
    (per Searchless research, May 2026). Use for any "ask a question →
    answer" surface; FAQPage stays useful for static FAQs.
    """
    return {
        '@context': 'https://schema.org',
        '@type': 'QAPage',
        'name': name[:120],
        'url': url,
        'mainEntity': [
            {
                '@type': 'Question',
                'name': item.get('q', '')[:200],
                'answerCount': 1,
                'acceptedAnswer': {
                    '@type': 'Answer',
                    'text': item.get('a', '')[:2000],
                },
            }
            for item in qa
        ],
    }


def article_jsonld(
    *,
    headline: str,
    body: str,
    url: str,
    author: str = '',
    published_at=None,
    updated_at=None,
    image: str = '',
    image_url: str = '',
    citations: list[str] | None = None,
    author_same_as: list[str] | None = None,
) -> dict:
    """Article schema for journal posts.

    Beyond the bare-bones headline/body/url, we emit ``publisher`` (reusing
    ``organization_jsonld()`` minus the @context so it nests as a plain
    inner dict), ``mainEntityOfPage`` (Google's required pointer back to
    the canonical page), and ``dateModified`` — only when ``updated_at``
    actually differs from ``published_at``, so unchanged posts don't get
    spurious freshness signals.

    Both ``image`` and ``image_url`` are accepted for caller convenience;
    ``image_url`` wins when both are passed.
    """
    out = {
        '@context': 'https://schema.org',
        '@type': 'Article',
        'headline': headline[:110],
        'url': url,
        'articleBody': body[:5000],
        'mainEntityOfPage': {'@type': 'WebPage', '@id': url},
    }
    if author:
        author_node = {'@type': 'Person', 'name': author}
        # E-E-A-T: sameAs links prove the author entity (LinkedIn /
        # ORCID / Wikidata). AI engines weight authored, attributable
        # content far higher for citation.
        if author_same_as:
            links = [u for u in author_same_as if u]
            if links:
                author_node['sameAs'] = links[:6]
        out['author'] = author_node
    if published_at:
        out['datePublished'] = published_at.isoformat()
    if updated_at and updated_at != published_at:
        try:
            out['dateModified'] = updated_at.isoformat()
        except AttributeError:
            out['dateModified'] = str(updated_at)
    hero = image_url or image
    if hero:
        out['image'] = hero
    # GEO trust signal — sources the article cites/derives from. Emitted
    # as both `citation` (CreativeWork refs) and `isBasedOn` (the URLs
    # this content is grounded in), which AI engines read to gauge
    # factual provenance.
    if citations:
        urls = [u for u in citations if u]
        if urls:
            out['citation'] = [{'@type': 'CreativeWork', 'url': u} for u in urls[:10]]
            out['isBasedOn'] = urls[:10]
    publisher = organization_jsonld()
    if publisher:
        publisher.pop('@context', None)
        out['publisher'] = publisher
    return out


def faq_jsonld(qa: list[dict]) -> dict:
    return {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        'mainEntity': [
            {
                '@type': 'Question',
                'name': item['q'],
                'acceptedAnswer': {'@type': 'Answer', 'text': item['a']},
            }
            for item in qa
        ],
    }


# ── Google Book structured data ──────────────────────────────────────────
# https://developers.google.com/search/docs/appearance/structured-data/book
# Model: Book (Work) → workExample → Book (Edition) → potentialAction
# (ReadAction → EntryPoint + Offer). Distinct from the Product graph: Product
# drives shopping rich results; Book describes the *title* for Book knowledge
# results / Book Actions. Built from a plain dict the caller assembles, so it
# never touches a deferred ORM field (the price-KeyError landmine).

_BOOK_FORMAT_MAP = {
    'hardcover': 'https://schema.org/Hardcover',
    'board_book': 'https://schema.org/Hardcover',
    'leather': 'https://schema.org/Hardcover',
    'spiral': 'https://schema.org/Hardcover',
    'paperback': 'https://schema.org/Paperback',
    'mass_market': 'https://schema.org/Paperback',
    'ebook': 'https://schema.org/EBook',
    'audiobook': 'https://schema.org/AudiobookFormat',
    'audio': 'https://schema.org/AudiobookFormat',
}
_BOOK_PLATFORM_MAP = {
    'desktop': 'https://schema.org/DesktopWebPlatform',
    'android': 'https://schema.org/AndroidPlatform',
    'ios': 'https://schema.org/IOSPlatform',
}


def _book_platforms(raw) -> list[str]:
    """Parse the merchant's platform config → schema.org EntryPoint platforms."""
    if isinstance(raw, str):
        keys = [k.strip().lower() for k in raw.split(',') if k.strip()]
    elif isinstance(raw, (list, tuple)):
        keys = [str(k).strip().lower() for k in raw]
    else:
        keys = []
    out = [_BOOK_PLATFORM_MAP[k] for k in keys if k in _BOOK_PLATFORM_MAP]
    return out or list(_BOOK_PLATFORM_MAP.values())


def _to_isbn13(isbn13, isbn10) -> str | None:
    """Google requires ISBN-13 on the edition; convert ISBN-10 when needed."""
    import re

    if isbn13:
        digits = re.sub(r'[^0-9]', '', str(isbn13))
        if len(digits) == 13:
            return digits
    if isbn10:
        core = re.sub(r'[^0-9X]', '', str(isbn10).upper())
        if len(core) == 10:
            base = '978' + core[:9]
            s = sum((1 if i % 2 == 0 else 3) * int(d) for i, d in enumerate(base))
            check = (10 - (s % 10)) % 10
            return base + str(check)
    return None


def book_jsonld(data: dict, *, base_url: str = '') -> dict:
    """Google Book (Work → Edition → ReadAction) JSON-LD.

    `data` is a plain dict assembled by the caller (pure in/out — no ORM):
      name (required), path|url, authors (list[str], >=1 required),
      isbn13, isbn10, book_format, language, date_published, edition,
      same_as (list[str]), price, currency.
    Returns {} when disabled, or when there's no title/author to form a Work.
    """
    if not isinstance(data, dict):
        return {}
    cfg = _seo_plugin_cfg()
    if not cfg.get('book_structured_data', True):
        return {}
    name = (data.get('name') or '').strip()
    authors = [str(a).strip() for a in (data.get('authors') or []) if str(a).strip()]
    if not name or not authors:
        return {}

    base = base_url or _site_base_url()
    url = data.get('url') or ''
    if url and not url.startswith(('http://', 'https://')):
        url = base.rstrip('/') + '/' + url.lstrip('/')
    elif not url:
        path = data.get('path') or ''
        url = (base.rstrip('/') + '/' + path.lstrip('/')) if path else base.rstrip('/') + '/'

    def _person(n):
        return {'@type': 'Person', 'name': str(n)}

    work: dict = {
        '@context': 'https://schema.org',
        '@type': 'Book',
        '@id': f'{url}#work',
        'name': name,
        'author': _person(authors[0]) if len(authors) == 1 else [_person(a) for a in authors],
        'url': url,
    }
    same_as = [str(s).strip() for s in (data.get('same_as') or []) if str(s).strip()]
    if same_as:
        work['sameAs'] = same_as if len(same_as) > 1 else same_as[0]

    edition: dict = {'@type': 'Book', '@id': f'{url}#edition', 'url': url}
    isbn13 = _to_isbn13(data.get('isbn13'), data.get('isbn10'))
    if isbn13:
        edition['isbn'] = isbn13
    fmt = _BOOK_FORMAT_MAP.get(str(data.get('book_format') or '').strip().lower())
    if fmt:
        edition['bookFormat'] = fmt
    lang = str(data.get('language') or '').strip().lower()
    if lang:
        edition['inLanguage'] = lang[:2]
    if data.get('date_published'):
        edition['datePublished'] = str(data['date_published'])
    if data.get('edition'):
        edition['bookEdition'] = str(data['edition'])

    platforms = _book_platforms(cfg.get('book_action_platforms'))
    region = str(cfg.get('book_eligible_region') or cfg.get('shipping_country') or 'US').upper()
    category = str(cfg.get('book_offer_category') or 'purchase')
    offer: dict = {
        '@type': 'Offer',
        'category': category,
        'eligibleRegion': {'@type': 'Country', 'name': region},
    }
    price = data.get('price')
    if price not in (None, '') and category in ('purchase', 'rental'):
        offer['price'] = str(price)
        offer['priceCurrency'] = str(data.get('currency') or 'USD')
    edition['potentialAction'] = {
        '@type': 'ReadAction',
        'target': {
            '@type': 'EntryPoint',
            'urlTemplate': url,
            'actionPlatform': platforms,
        },
        'expectsAcceptanceOf': offer,
    }

    work['workExample'] = edition
    return work
