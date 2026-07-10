"""Auto-split from the legacy admin_dashboard/views.py monolith."""

# ruff: noqa: PLC0415, I001, F401, S110, PLR0912, PLR0915
# Inline imports throughout: every view imports only what it needs to
# stay fast at startup + avoid circular deps with catalog / product_videos
# / bookvault / seo / core.agents. The `_shared` re-exports cover legacy
# import paths that other modules still reach for. S110 on optional
# integrations + PLR0912 on the hot-path catalog editing flows.
from __future__ import annotations

from decimal import Decimal
from typing import Any

from morpheus.views import HttpRequest, HttpResponse, messages, staff_member_required
from morpheus.views import get_object_or_404, redirect, render
from django.db.models import Sum
from django.utils import timezone

from plugins.installed.admin_dashboard.views_split._shared import (
    ajax_form_errors,
    ajax_or_redirect,
)

from plugins.installed.admin_dashboard.forms import (
    AddressForm,
    CouponForm,
    CustomerForm,
    DraftOrderForm,
    FulfillmentForm,
    ProductForm,
    RefundForm,
    VariantForm,
)
from plugins.installed.admin_dashboard.views_split._shared import (
    Metric,
    _bulk_ids,
    _period,
    _pct_delta,
    _since,
    _sparkline_points,
    _trend,
    logger,
    paginate_and_sort,
)

PRODUCT_STATUS_CHOICES = (
    ('', 'All'),
    ('active', 'Active'),
    ('draft', 'Drafts'),
    ('archived', 'Archived'),
)


@staff_member_required
def products_list(request: HttpRequest) -> HttpResponse:
    status = request.GET.get('status', '')
    search = request.GET.get('q', '').strip()[:80]
    products: list[Any] = []
    status_counts: dict[str, int] = {}
    paging_ctx: dict[str, Any] = {}
    try:
        from django.db.models import Count
        from plugins.installed.catalog.models import Product

        unfiltered = Product.objects.all()
        if search:
            unfiltered = unfiltered.filter(name__icontains=search) | unfiltered.filter(
                sku__icontains=search
            )
        status_counts = {
            row['status']: row['c'] for row in unfiltered.values('status').annotate(c=Count('id'))
        }
        qs = Product.objects.select_related('category', 'vendor').prefetch_related('images')
        if status:
            qs = qs.filter(status=status)
        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(sku__icontains=search)
        page_obj, paging_ctx = paginate_and_sort(
            request,
            qs,
            default_sort='-created_at',
            allowed_sorts=('name', 'created_at', 'status', 'price'),
        )
        products = list(page_obj.object_list)
        load_error = False
    except Exception:  # noqa: BLE001
        # An honest failure state — NOT the first-run empty state. A DB
        # outage on a 500-product store must never render "Add your first
        # product".
        logger.exception('products_list: query failed')
        products = []
        load_error = True

    # Bookvault is an optional plugin. Surface the per-row link status
    # column only when BV is configured + authed; otherwise the column
    # is hidden so non-BV stores don't see noise.
    bv_authed = False
    try:
        from plugins.installed.bookvault import services as bv_services

        bv_authed = bv_services.is_authenticated()
        if bv_authed and products:
            bv_status = bv_services.bulk_link_status_for([p.id for p in products])
            # Annotate each product so the template can read it without
            # needing a dict-lookup filter. (Django templates reject
            # attrs that start with an underscore, hence the public name.)
            for p in products:
                p.bv_link_status = bv_status.get(p.id, 'Unlinked')
    except Exception:  # noqa: BLE001 — never break the product list if BV is wedged
        bv_authed = False

    return render(
        request,
        'admin_dashboard/products.html',
        {
            'products': products,
            'load_error': load_error,
            'status_filter': status,
            'status_choices': PRODUCT_STATUS_CHOICES,
            'status_counts': status_counts,
            'search': search,
            'bv_authed': bv_authed,
            'active_nav': 'products',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Products'},
            ],
            **paging_ctx,
        },
    )


def _product_form_choices():
    """Categories (tree-ordered) + vendors for the product form selects."""
    categories: list[Any] = []
    vendors: list[Any] = []
    try:
        from plugins.installed.catalog.models import Category, Vendor

        categories = _ordered_categories()
        vendors = list(Vendor.objects.filter(is_active=True).order_by('name'))
    except Exception:  # noqa: BLE001
        pass
    return categories, vendors


def _ordered_categories() -> list:
    """Return active categories in parent→child tree order, each tagged
    with a ``tree_prefix`` ("— " per depth level) so the flat <select>
    renders the hierarchy. Categories can be nested arbitrarily deep
    via Category.parent."""
    from plugins.installed.catalog.models import Category

    cats = list(Category.objects.filter(is_active=True).select_related('parent'))
    by_parent: dict = {}
    for c in cats:
        by_parent.setdefault(c.parent_id, []).append(c)
    for siblings in by_parent.values():
        siblings.sort(key=lambda c: (c.name or '').lower())

    ordered: list = []

    def _walk(parent_id, depth):
        for c in by_parent.get(parent_id, []):
            c.tree_prefix = '— ' * depth
            c.tree_depth = depth
            ordered.append(c)
            _walk(c.id, depth + 1)

    _walk(None, 0)
    # Orphans whose parent is inactive / filtered out — surface flat so
    # they're still selectable rather than silently dropped.
    seen = {c.id for c in ordered}
    for c in cats:
        if c.id not in seen:
            c.tree_prefix = ''
            c.tree_depth = 0
            ordered.append(c)
    return ordered


def _seo_field_defaults(product) -> dict:
    """Resolved SEO values the storefront would render for this product
    when each field is left blank — surfaced as gray placeholders in
    the product form so the merchant sees the effective value before
    deciding to override it.

    Computed from the same fallback chain `seo.services.resolve_meta`
    uses (product name + store name suffix for the title, stripped
    short/long description for the meta description), so the placeholder
    matches what actually ships."""
    if product is None:
        return {}
    import re as _re

    try:
        from django.conf import settings as _settings
        from plugins.installed.seo.services import _site_base_url, site_settings

        s = site_settings()
        store_name = (
            getattr(s, 'organization_name', '') or getattr(_settings, 'STORE_NAME', '') or ''
        )
        name = product.name or ''
        title_default = (f'{name} — {store_name}'.strip(' —')) if name else ''
        desc_src = product.short_description or product.description or ''
        desc_default = _re.sub(r'<[^>]+>', '', desc_src).strip()[:160]
        base = _site_base_url().rstrip('/')
        canonical_default = f'{base}/products/{product.slug}/' if product.slug else ''
        return {
            'meta_title': title_default,
            'meta_description': desc_default,
            'og_title': title_default,
            'og_description': desc_default,
            'twitter_title': title_default,
            'twitter_description': desc_default,
            'canonical_url': canonical_default,
            'twitter_card': getattr(s, 'twitter_card_default', '') or 'summary_large_image',
        }
    except Exception:  # noqa: BLE001 — seo plugin optional; fall back to static placeholders
        return {}


@staff_member_required
def product_new(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = ProductForm(request.POST, files=request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product "{product.name}" created.')
            return redirect('admin_dashboard:product_edit', product_id=product.id)
    else:
        form = ProductForm()
    categories, vendors = _product_form_choices()
    return render(
        request,
        'admin_dashboard/product_form.html',
        {
            'form': form,
            'product': None,
            'categories': categories,
            'vendors': vendors,
            'seo_defaults': {},
            'active_nav': 'products',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Products', 'url': '/dashboard/products/'},
                {'label': 'New product'},
            ],
        },
    )


def _save_product_identifiers(product, post) -> None:
    """Persist the product-identifier codes (ISBN/EAN/GTIN/UPC/MPN/ASIN) from
    the edit form into the ``identifiers`` metafield namespace. Gated on the
    card's hidden marker so a POST without the card never wipes codes.
    Fail-soft: a missing metafields plugin must not break product save."""
    if not post.get('identifiers_present'):
        return
    try:
        from plugins.installed.metafields.identifiers import (  # noqa: PLC0415
            IDENTIFIERS_NAMESPACE,
            PRODUCT_IDENTIFIERS,
        )
        from plugins.installed.metafields.models import Metafield  # noqa: PLC0415

        for key, _label, _jsonld, _ph in PRODUCT_IDENTIFIERS:
            raw = (post.get(f'identifier_{key}') or '').strip()
            if raw:
                Metafield.objects.set(
                    product,
                    namespace=IDENTIFIERS_NAMESPACE,
                    key=key,
                    value=raw,
                    value_type='string',
                )
            else:
                Metafield.objects.delete_for(
                    product,
                    namespace=IDENTIFIERS_NAMESPACE,
                    key=key,
                )
    except Exception:  # noqa: BLE001 — codes are best-effort, never block save
        pass


def _identifier_fields(product) -> list[dict]:
    """``[{key, label, placeholder, value}]`` for the editor's codes card."""
    try:
        from plugins.installed.metafields.identifiers import (  # noqa: PLC0415
            PRODUCT_IDENTIFIERS,
            identifier_values,
        )

        vals = identifier_values(product)
        return [
            {'key': k, 'label': label, 'placeholder': ph, 'value': vals.get(k, '')}
            for k, label, _jsonld, ph in PRODUCT_IDENTIFIERS
        ]
    except Exception:  # noqa: BLE001
        return []


def _seo_tokens(product) -> list[dict]:
    """``[{token, label}]`` for the SEO title/description "Insert field" menu."""
    try:
        from plugins.installed.seo.services.tokens import available_tokens  # noqa: PLC0415

        return available_tokens(product)
    except Exception:  # noqa: BLE001
        return []


def _collect_product_form_cards(product, request) -> list:
    """Render plugin-contributed product-form cards (PRODUCT_FORM_CARDS filter).

    The modular extension point: a plugin appends {'template', 'context', 'order'}
    and we render it here, so admin_dashboard never imports the plugin. Fail-soft
    per card — one broken card can't break the product form.
    """
    from django.template.loader import render_to_string

    from core.hooks import MorpheusEvents, hook_registry

    out: list = []
    cards = hook_registry.filter(MorpheusEvents.PRODUCT_FORM_CARDS, value=[], product=product)
    for card in sorted(cards or [], key=lambda c: c.get('order', 100)):
        tpl = card.get('template')
        if not tpl:
            continue
        try:
            out.append(
                render_to_string(
                    tpl, {**card.get('context', {}), 'product': product}, request=request
                )
            )
        except Exception as e:  # noqa: BLE001 — one bad card can't break the form
            logger.warning('product_form_card render failed (%s): %s', tpl, e, exc_info=True)
    return out


@staff_member_required
def product_edit(request: HttpRequest, product_id: str) -> HttpResponse:
    from plugins.installed.catalog.models import Product

    product = get_object_or_404(Product, pk=product_id)
    if request.method == 'POST':
        form = ProductForm(request.POST, files=request.FILES, instance=product)
        if form.is_valid():
            form.save()
            _save_product_identifiers(product, request.POST)
            # Let plugins persist their own product-form fields (their contributed
            # cards, incl. book_product's Book details) — the modular path; the
            # hook bus isolates a broken handler and a disabled plugin's handler
            # simply isn't registered.
            from core.hooks import MorpheusEvents, hook_registry

            hook_registry.fire(
                MorpheusEvents.PRODUCT_FORM_SAVED,
                product=product,
                post=request.POST,
                files=request.FILES,
            )
            messages.success(request, 'Product saved.')
            return ajax_or_redirect(request, 'admin_dashboard:product_edit', product_id=product.id)
        if (error_response := ajax_form_errors(request, form)) is not None:
            return error_response
    else:
        form = ProductForm(instance=product)
    categories, vendors = _product_form_choices()
    variants = list(product.variants.all().order_by('sort_order', 'name'))
    images = list(product.images.all().order_by('sort_order', '-is_primary'))
    # Pre-resolve the front + back slot occupants so the _cover_slot.html
    # partial doesn't have to re-iterate the image list 3× per slot.
    # Convention: sort_order=0 is the front cover, 1 is the back.
    front_image = next((i for i in images if i.is_primary and i.sort_order == 0), None)
    back_image = next((i for i in images if i.is_primary and i.sort_order == 1), None)
    # Load attached videos for the dashboard video CRUD card. The
    # plugin may be disabled — fall through to an empty list.
    videos: list = []
    try:
        from plugins.installed.product_videos.models import ProductVideo

        videos = list(
            ProductVideo.objects.filter(product=product).order_by('sort_order', 'created_at')
        )
    except Exception:  # noqa: BLE001
        pass

    # Bookvault per-product panel — same gate as the product list.
    # Pulls every BookvaultProductLink row for this product (one per
    # variant + one for the parent) so the template can render the
    # fulfilment-locations + linked-status block the WP plugin's
    # `bvlt_product_meta` showed.
    bv_authed = False
    bv_links: list = []
    bv_locations: list = []
    bv_bulk_link_url = ''
    try:
        from plugins.installed.bookvault import services as bv_services
        from plugins.installed.bookvault.models import (
            BookvaultProductLink,
            BV_LOCATION_CHOICES,
        )

        bv_authed = bv_services.is_authenticated()
        if bv_authed:
            bv_locations = [{'id': lid, 'name': name} for lid, name in BV_LOCATION_CHOICES]
            bv_links = list(
                BookvaultProductLink.objects.filter(product=product)
                .select_related('variant')
                .order_by('variant__sort_order', 'variant__name')
            )
            bv_bulk_link_url = bv_services.bulk_products_link([str(product.id)])
    except Exception:  # noqa: BLE001 — never break the product page if BV is wedged
        bv_authed = False

    # Plugin-contributed product-form cards (modular extension point) — includes
    # book_product's Book details card, contributed via PRODUCT_FORM_CARDS so it
    # disappears when the plugin is disabled.
    extra_product_cards = _collect_product_form_cards(product, request)

    return render(
        request,
        'admin_dashboard/product_form.html',
        {
            'extra_product_cards': extra_product_cards,
            'form': form,
            'product': product,
            'categories': categories,
            'vendors': vendors,
            'variants': variants,
            'images': images,
            'videos': videos,
            'front_image': front_image,
            'back_image': back_image,
            'bv_authed': bv_authed,
            'bv_links': bv_links,
            'bv_locations': bv_locations,
            'bv_bulk_link_url': bv_bulk_link_url,
            'seo_defaults': _seo_field_defaults(product),
            'identifier_fields': _identifier_fields(product),
            'seo_tokens': _seo_tokens(product),
            'active_nav': 'products',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Products', 'url': '/dashboard/products/'},
                {'label': product.name[:60]},
            ],
        },
    )


@staff_member_required
def product_delete(request: HttpRequest, product_id: str) -> HttpResponse:
    from plugins.installed.catalog.models import Product

    product = get_object_or_404(Product, pk=product_id)
    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f'Deleted product "{name}".')
        return redirect('admin_dashboard:products')
    return redirect('admin_dashboard:product_edit', product_id=product.id)


@staff_member_required
def product_archive(request: HttpRequest, product_id: str) -> HttpResponse:
    """Soft-archive (or restore) a product — flips status between
    'active' and 'archived'. Confirmed via modal on the product list.
    """
    from plugins.installed.catalog.models import Product

    product = get_object_or_404(Product, pk=product_id)
    if request.method == 'POST':
        if product.status == 'archived':
            product.status = 'active'
            product.save(update_fields=['status'])
            messages.success(request, f'Restored "{product.name}".')
        else:
            product.status = 'archived'
            product.save(update_fields=['status'])
            messages.success(request, f'Archived "{product.name}".')
        return redirect('admin_dashboard:products')
    return redirect('admin_dashboard:product_edit', product_id=product.id)


# ── Customers ─────────────────────────────────────────────────────────────────


def _get_product(product_id: str):
    from plugins.installed.catalog.models import Product

    return get_object_or_404(Product, pk=product_id)


@staff_member_required
def variant_new(request: HttpRequest, product_id: str) -> HttpResponse:
    product = _get_product(product_id)
    if request.method == 'POST':
        form = VariantForm(request.POST, files=request.FILES, product=product)
        if form.is_valid():
            form.save()
            # First variant flips the product to 'variable' as a convenience.
            if product.product_type == 'simple':
                product.product_type = 'variable'
                product.save(update_fields=['product_type', 'updated_at'])
            messages.success(request, 'Variant added.')
            return ajax_or_redirect(request, 'admin_dashboard:product_edit', product_id=product.id)
        if (error_response := ajax_form_errors(request, form)) is not None:
            return error_response
    else:
        form = VariantForm(product=product)
    return render(
        request,
        'admin_dashboard/variant_form.html',
        {
            'form': form,
            'product': product,
            'variant': None,
            'active_nav': 'products',
        },
    )


@staff_member_required
def variant_edit(request: HttpRequest, product_id: str, variant_id: str) -> HttpResponse:
    from plugins.installed.catalog.models import ProductVariant

    product = _get_product(product_id)
    variant = get_object_or_404(ProductVariant, pk=variant_id, product=product)
    if request.method == 'POST':
        form = VariantForm(request.POST, files=request.FILES, instance=variant, product=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Variant saved.')
            return ajax_or_redirect(request, 'admin_dashboard:product_edit', product_id=product.id)
        if (error_response := ajax_form_errors(request, form)) is not None:
            return error_response
    else:
        form = VariantForm(instance=variant, product=product)
    return render(
        request,
        'admin_dashboard/variant_form.html',
        {
            'form': form,
            'product': product,
            'variant': variant,
            'active_nav': 'products',
        },
    )


@staff_member_required
def variant_delete(request: HttpRequest, product_id: str, variant_id: str) -> HttpResponse:
    from plugins.installed.catalog.models import ProductVariant

    product = _get_product(product_id)
    variant = get_object_or_404(ProductVariant, pk=variant_id, product=product)
    if request.method == 'POST':
        variant.delete()
        messages.success(request, 'Variant deleted.')
    return redirect('admin_dashboard:product_edit', product_id=product.id)


# ── Product images ────────────────────────────────────────────────────────────


@staff_member_required
def image_upload(request: HttpRequest, product_id: str) -> HttpResponse:  # noqa: PLR0911
    """POST-only: accept a multipart upload, attach to product.

    Answers JSON for AJAX callers (the media uploader sends
    ``X-Requested-With``). A plain redirect is opaque to ``fetch()`` — it
    follows the 302 and reads EVERY outcome (including "no file" / "too big" /
    a storage error) as a 200, so failures looked like silent successes.
    """
    from django.http import JsonResponse

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def _fail(msg, status=400):
        if is_ajax:
            return JsonResponse({'ok': False, 'error': msg}, status=status)
        messages.error(request, msg)
        return redirect('admin_dashboard:product_edit', product_id=product_id)

    if request.method != 'POST':
        return _fail('POST required.', status=405)
    from plugins.installed.catalog.models import ProductImage

    product = _get_product(product_id)
    upload = request.FILES.get('image')
    if not upload:
        return _fail('Choose an image to upload.')
    # Cheap MIME guard — ImageField does its own validation but we want a
    # clearer error if someone uploads a PDF or .txt by accident.
    if not (upload.content_type or '').startswith('image/'):
        return _fail('That file is not an image.')
    alt = (request.POST.get('alt_text') or '').strip()[:255]

    # 15-image cap (Phase 1 of docs/plans/product-slider.md).
    # Slider only renders 15 anyway; refuse to accept more so the DB
    # doesn't accumulate orphan rows the merchant can't see.
    image_count = ProductImage.objects.filter(product=product).count()
    if image_count >= 15:
        return _fail(
            'You can have up to 15 images per product. Delete one before uploading another.'
        )

    # Unified 15-slot model (Phase 1 of docs/plans/product-slider.md):
    # new uploads append at the end of the slider. The merchant drags
    # tiles to reorder; slot 0 is the cover.
    #
    # First image for a product auto-becomes the cover (is_primary=True,
    # sort_order=0). Subsequent uploads append with is_primary=False;
    # the reorder endpoint reconciles primary state when the merchant
    # drags slots around.
    max_sort = (
        ProductImage.objects.filter(product=product)
        .order_by('-sort_order')
        .values_list('sort_order', flat=True)
        .first()
    )
    if max_sort is None:
        sort_order = 0
        is_primary = True
    else:
        sort_order = int(max_sort) + 1
        is_primary = False

    try:
        image = ProductImage.objects.create(
            product=product,
            image=upload,
            alt_text=alt,
            is_primary=is_primary,
            sort_order=sort_order,
        )
    except Exception as exc:  # noqa: BLE001 — surface storage/processing errors instead of a silent redirect
        import logging

        logging.getLogger('morpheus.admin').exception('image_upload failed for %s', product_id)
        return _fail(f'Could not save the image: {exc}', status=500)

    messages.success(request, 'Image uploaded.')
    if is_ajax:
        try:
            url = image.image.url
        except Exception:  # noqa: BLE001
            url = ''
        return JsonResponse({'ok': True, 'id': str(image.id), 'url': url})
    return redirect('admin_dashboard:product_edit', product_id=product.id)


@staff_member_required
def image_delete(request: HttpRequest, product_id: str, image_id: str) -> HttpResponse:
    from plugins.installed.catalog.models import ProductImage

    product = _get_product(product_id)
    image = get_object_or_404(ProductImage, pk=image_id, product=product)
    if request.method == 'POST':
        image.delete()
        messages.success(request, 'Image deleted.')
    return redirect('admin_dashboard:product_edit', product_id=product.id)


@staff_member_required
def image_reorder(request: HttpRequest, product_id: str) -> HttpResponse:
    """Persist new sort_order for a product's images.

    POST body: ``order=<image_id_1>,<image_id_2>,...`` — comma-joined
    list of image UUIDs in their new visual order. Indices map 1:1
    to ``sort_order`` so slot 0 → sort_order 0, slot 1 → sort_order 1.

    AJAX-only via the slider grid drag handler in product_form.html.
    Returns JSON ``{"ok": true, "count": N}``.
    """
    from django.http import JsonResponse
    from plugins.installed.catalog.models import ProductImage

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    product = _get_product(product_id)
    raw = (request.POST.get('order') or '').strip()
    ids = [s.strip() for s in raw.split(',') if s.strip()]
    if not ids:
        return JsonResponse({'ok': False, 'error': 'no ids'}, status=400)
    # Update in a single round-trip per image; the set is small (≤ 15).
    # Slot 0 is the cover — auto-promote to is_primary so the OG /
    # JSON-LD / storefront grid thumbnail all surface the right one
    # without merchant intervention.
    existing = {str(i.pk): i for i in ProductImage.objects.filter(product=product, pk__in=ids)}
    updated = 0
    for idx, image_id in enumerate(ids):
        img = existing.get(image_id)
        if img is None:
            continue
        should_primary = idx == 0
        fields = []
        if img.sort_order != idx:
            img.sort_order = idx
            fields.append('sort_order')
        if img.is_primary != should_primary:
            img.is_primary = should_primary
            fields.append('is_primary')
        if fields:
            img.save(update_fields=fields)
            updated += 1
    return JsonResponse({'ok': True, 'count': updated})


@staff_member_required
def video_add(request: HttpRequest, product_id: str) -> HttpResponse:
    """Attach a video (YouTube/Vimeo URL, direct mp4, or raw iframe)
    to a product. Phase 2 of docs/plans/product-slider.md — moves
    video CRUD off the Django admin and onto the product edit page.
    """
    if request.method != 'POST':
        return redirect('admin_dashboard:product_edit', product_id=product_id)
    product = _get_product(product_id)
    try:
        from plugins.installed.product_videos.models import ProductVideo
    except ImportError:
        messages.error(request, 'Product videos plugin is not installed.')
        return redirect('admin_dashboard:product_edit', product_id=product.id)

    title = (request.POST.get('title') or '').strip()[:200]
    url = (request.POST.get('url') or '').strip()[:500]
    poster_url = (request.POST.get('poster_url') or '').strip()[:500]
    embed_html = (request.POST.get('embed_html') or '').strip()
    if not (url or embed_html):
        messages.error(request, 'Provide a video URL or raw embed HTML.')
        return redirect('admin_dashboard:product_edit', product_id=product.id)
    # Append at the end — the storefront renders videos AFTER images.
    max_sort = (
        ProductVideo.objects.filter(product=product)
        .order_by('-sort_order')
        .values_list('sort_order', flat=True)
        .first()
    )
    sort_order = (int(max_sort) + 1) if max_sort is not None else 0
    ProductVideo.objects.create(
        product=product,
        title=title,
        url=url,
        embed_html=embed_html,
        poster_url=poster_url,
        sort_order=sort_order,
        is_active=True,
    )
    messages.success(request, 'Video added.')
    return redirect('admin_dashboard:product_edit', product_id=product.id)


@staff_member_required
def video_delete(request: HttpRequest, product_id: str, video_id: str) -> HttpResponse:
    if request.method != 'POST':
        return redirect('admin_dashboard:product_edit', product_id=product_id)
    product = _get_product(product_id)
    try:
        from plugins.installed.product_videos.models import ProductVideo
    except ImportError:
        return redirect('admin_dashboard:product_edit', product_id=product.id)
    video = ProductVideo.objects.filter(pk=video_id, product=product).first()
    if video is not None:
        video.delete()
        messages.success(request, 'Video removed.')
    return redirect('admin_dashboard:product_edit', product_id=product.id)


@staff_member_required
def image_edit(request: HttpRequest, product_id: str, image_id: str) -> HttpResponse:
    """Inline metadata edit for a ProductImage — alt_text + description.

    Called by the Morph.MediaUploader modal. AJAX-only (returns JSON).
    """
    from django.http import JsonResponse
    from plugins.installed.catalog.models import ProductImage

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    product = _get_product(product_id)
    image = ProductImage.objects.filter(pk=image_id, product=product).first()
    if image is None:
        return JsonResponse({'ok': False, 'error': 'image not found'}, status=404)
    alt = (request.POST.get('alt_text') or '').strip()[:255]
    image.alt_text = alt
    image.save(update_fields=['alt_text'])
    return JsonResponse({'ok': True, 'alt_text': alt})


@staff_member_required
def video_edit(request: HttpRequest, product_id: str, video_id: str) -> HttpResponse:
    """Inline metadata edit for a ProductVideo — title + poster_url.

    Called by the Morph.MediaUploader modal. AJAX-only (returns JSON).
    """
    from django.http import JsonResponse

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    product = _get_product(product_id)
    try:
        from plugins.installed.product_videos.models import ProductVideo
    except ImportError:
        return JsonResponse({'ok': False, 'error': 'product_videos plugin disabled'}, status=400)
    video = ProductVideo.objects.filter(pk=video_id, product=product).first()
    if video is None:
        return JsonResponse({'ok': False, 'error': 'video not found'}, status=404)
    title = (request.POST.get('title') or '').strip()[:200]
    poster_url = (request.POST.get('poster_url') or '').strip()[:500]
    video.title = title
    video.poster_url = poster_url
    video.save(update_fields=['title', 'poster_url', 'updated_at'])
    return JsonResponse({'ok': True, 'title': title, 'poster_url': poster_url})


@staff_member_required
def image_set_primary(request: HttpRequest, product_id: str, image_id: str) -> HttpResponse:
    from plugins.installed.catalog.models import ProductImage

    product = _get_product(product_id)
    image = get_object_or_404(ProductImage, pk=image_id, product=product)
    # Optional `slot` POST param ('front' | 'back') lets the admin form
    # promote directly into a specific cover slot. Default: front slot.
    slot = (request.POST.get('slot') or 'front').strip().lower()
    if slot not in ('front', 'back'):
        slot = 'front'
    if request.method == 'POST':
        target_sort = 0 if slot == 'front' else 1
        # Demote whatever currently sits at the target slot so the slot
        # stays unique. The demoted image goes back to the slider with a
        # high sort_order (so it doesn't fight the back slot).
        ProductImage.objects.filter(
            product=product,
            is_primary=True,
            sort_order=target_sort,
        ).exclude(pk=image.pk).update(is_primary=False, sort_order=99)
        image.is_primary = True
        image.sort_order = target_sort
        image.save(update_fields=['is_primary', 'sort_order'])
        messages.success(request, f'Image set as {slot} cover.')
    return redirect('admin_dashboard:product_edit', product_id=product.id)


# ── Analytics ─────────────────────────────────────────────────────────────────


@staff_member_required
def products_bulk(request: HttpRequest) -> HttpResponse:
    """Bulk action endpoint for the products list page.

    Supported: ``activate`` / ``draft`` / ``archive`` (status switches),
    ``delete`` (hard delete).
    """
    if request.method != 'POST':
        return redirect('admin_dashboard:products')
    from plugins.installed.catalog.models import Product

    action = (request.POST.get('action') or '').strip()
    ids = _bulk_ids(request)
    if not ids:
        messages.warning(request, 'No products selected.')
        return redirect('admin_dashboard:products')

    qs = Product.objects.filter(pk__in=ids)
    count = qs.count()
    if count == 0:
        messages.warning(request, 'No matching products found.')
        return redirect('admin_dashboard:products')

    status_map = {'activate': 'active', 'draft': 'draft', 'archive': 'archived'}
    if action in status_map:
        qs.update(status=status_map[action])
        messages.success(request, f'Updated {count} product(s) to {status_map[action]}.')
    elif action == 'delete':
        qs.delete()
        messages.success(request, f'Deleted {count} product(s).')
    else:
        messages.warning(request, f'Unknown action: {action!r}.')
    return redirect('admin_dashboard:products')


# ── Content Audit — fill missing short/long descriptions + categorization ─────


def _content_audit_queryset():
    """Return products missing any of: short_description, description, category.

    The query is intentionally not paginated — the merchant wants a clear
    picture of how much copy work is outstanding. Cap at 500 to stay safe.
    """
    from plugins.installed.catalog.models import Product
    from django.db.models import Q

    return (
        Product.objects.filter(
            Q(short_description='') | Q(description='') | Q(category__isnull=True),
        )
        .select_related('category')
        .order_by('status', 'name')
    )


@staff_member_required
def content_audit(request: HttpRequest) -> HttpResponse:
    """List every product missing copy or categorization."""
    from plugins.installed.catalog.models import Category, Product

    qs = _content_audit_queryset()
    rows = []
    for p in qs[:500]:
        rows.append(
            {
                'product': p,
                'missing_short': not (p.short_description or '').strip(),
                'missing_long': not (p.description or '').strip(),
                'missing_category': p.category_id is None,
            }
        )
    summary = {
        'total': qs.count(),
        'missing_short': qs.filter(short_description='').count(),
        'missing_long': qs.filter(description='').count(),
        'missing_category': qs.filter(category__isnull=True).count(),
        'product_total': Product.objects.count(),
    }
    categories = list(Category.objects.values('id', 'name').order_by('name')[:200])
    return render(
        request,
        'admin_dashboard/content_audit.html',
        {
            'rows': rows,
            'summary': summary,
            'categories': categories,
            'active_nav': 'products',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Products', 'url': '/dashboard/products/'},
                {'label': 'Content audit'},
            ],
        },
    )


@staff_member_required
def content_fill_one(request: HttpRequest, product_id: str) -> HttpResponse:
    """Generate missing short + long descriptions for ONE product via the LLM.

    Idempotent on fields already populated — only fills what's empty.
    Category suggestion is best-effort: the LLM returns a name, we map
    it to an existing Category row (no auto-create — merchants resent
    category sprawl).
    """
    from django.http import JsonResponse
    from plugins.installed.catalog.models import Category, Product

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    p = get_object_or_404(Product, pk=product_id)
    fields_updated: list[str] = []

    try:
        from core.agents.llm import LLMMessage, get_llm_provider

        provider = get_llm_provider()
    except Exception as e:  # noqa: BLE001
        return JsonResponse({'ok': False, 'error': f'llm unavailable: {e}'}, status=502)

    if not (p.short_description or '').strip():
        try:
            resp = provider.respond(
                messages=[
                    LLMMessage(
                        role='system',
                        content=(
                            'You are a bookstore copywriter. Write a single '
                            'sentence (12–25 words) summarising the book. No '
                            'hype, no spoilers, no marketing adjectives.'
                        ),
                    ),
                    LLMMessage(
                        role='user',
                        content=(
                            f'Title: {p.name}\n'
                            f'Existing long description: {(p.description or "")[:600]}'
                        ),
                    ),
                ],
                tools=None,
                temperature=0.5,
                max_tokens=120,
            )
            short = (resp.text or '').strip().strip('"').strip()
            if short:
                p.short_description = short[:600]
                fields_updated.append('short_description')
        except Exception as e:  # noqa: BLE001
            logger.warning('content_fill: short failed for %s: %s', p.pk, e)

    if not (p.description or '').strip():
        try:
            resp = provider.respond(
                messages=[
                    LLMMessage(
                        role='system',
                        content=(
                            'You are a literary but unfussy bookstore copywriter. '
                            'Write an 80–140 word product description. Avoid spoilers, '
                            'hype, and generic adjectives. Plain prose, short sentences.'
                        ),
                    ),
                    LLMMessage(
                        role='user',
                        content=(
                            f'Title: {p.name}\n'
                            f'Category: {p.category.name if p.category_id else "—"}\n'
                            f'Existing short: {p.short_description or ""}'
                        ),
                    ),
                ],
                tools=None,
                temperature=0.6,
                max_tokens=400,
            )
            long_desc = (resp.text or '').strip()
            if long_desc:
                p.description = long_desc[:5000]
                fields_updated.append('description')
        except Exception as e:  # noqa: BLE001
            logger.warning('content_fill: long failed for %s: %s', p.pk, e)

    if p.category_id is None:
        try:
            cat_names = list(Category.objects.values_list('name', flat=True)[:200])
            if cat_names:
                resp = provider.respond(
                    messages=[
                        LLMMessage(
                            role='system',
                            content=(
                                'Pick the SINGLE best-fit category for this book '
                                'from the list provided. Reply with EXACTLY the '
                                'category name and nothing else. If none fit well, '
                                'reply with the word NONE.'
                            ),
                        ),
                        LLMMessage(
                            role='user',
                            content=(
                                f'Title: {p.name}\n'
                                f'Description: {(p.description or p.short_description or "")[:600]}\n\n'
                                f'Categories:\n- ' + '\n- '.join(cat_names)
                            ),
                        ),
                    ],
                    tools=None,
                    temperature=0.1,
                    max_tokens=40,
                )
                guess = (resp.text or '').strip().strip('"').strip()
                if guess and guess.upper() != 'NONE':
                    cat = Category.objects.filter(name__iexact=guess).first()
                    if cat:
                        p.category = cat
                        fields_updated.append('category')
        except Exception as e:  # noqa: BLE001
            logger.warning('content_fill: category failed for %s: %s', p.pk, e)

    if fields_updated:
        fields_updated.append('updated_at')
        p.save(update_fields=fields_updated)

    return JsonResponse(
        {
            'ok': True,
            'product_id': str(p.pk),
            'updated': [f for f in fields_updated if f != 'updated_at'],
            'short_description': p.short_description,
            'description': p.description,
            'category': p.category.name if p.category_id else '',
        }
    )
