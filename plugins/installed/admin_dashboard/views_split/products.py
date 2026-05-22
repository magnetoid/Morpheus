"""Auto-split from the legacy admin_dashboard/views.py monolith."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from morpheus.views import HttpRequest, HttpResponse, messages, staff_member_required
from morpheus.views import get_object_or_404, redirect, render
from django.db.models import Sum
from django.utils import timezone

from plugins.installed.admin_dashboard.views_split._shared import ajax_or_redirect

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
    Metric, _bulk_ids, _period, _pct_delta, _since, _sparkline_points,
    _trend, logger, paginate_and_sort,
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
            unfiltered = unfiltered.filter(name__icontains=search) | unfiltered.filter(sku__icontains=search)
        status_counts = {
            row['status']: row['c']
            for row in unfiltered.values('status').annotate(c=Count('id'))
        }
        qs = (
            Product.objects
            .select_related('category', 'vendor')
            .prefetch_related('images')
        )
        if status:
            qs = qs.filter(status=status)
        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(sku__icontains=search)
        page_obj, paging_ctx = paginate_and_sort(
            request, qs,
            default_sort='-created_at',
            allowed_sorts=('name', 'created_at', 'status', 'price'),
        )
        products = list(page_obj.object_list)
    except Exception:  # noqa: BLE001
        products = []
    return render(request, 'admin_dashboard/products.html', {
        'products': products,
        'status_filter': status,
        'status_choices': PRODUCT_STATUS_CHOICES,
        'status_counts': status_counts,
        'search': search,
        'active_nav': 'products',
        **paging_ctx,
    })


def _product_form_choices():
    """Categories + vendors for the product form selects."""
    categories: list[Any] = []
    vendors: list[Any] = []
    try:
        from plugins.installed.catalog.models import Category, Vendor
        categories = list(Category.objects.filter(is_active=True).order_by('name'))
        vendors = list(Vendor.objects.filter(is_active=True).order_by('name'))
    except Exception:  # noqa: BLE001
        pass
    return categories, vendors


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
    return render(request, 'admin_dashboard/product_form.html', {
        'form': form,
        'product': None,
        'categories': categories,
        'vendors': vendors,
        'active_nav': 'products',
    })


@staff_member_required
def product_edit(request: HttpRequest, product_id: str) -> HttpResponse:
    from plugins.installed.catalog.models import Product
    product = get_object_or_404(Product, pk=product_id)
    if request.method == 'POST':
        form = ProductForm(request.POST, files=request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product saved.')
            return ajax_or_redirect(request, 'admin_dashboard:product_edit', product_id=product.id)
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
    return render(request, 'admin_dashboard/product_form.html', {
        'form': form,
        'product': product,
        'categories': categories,
        'vendors': vendors,
        'variants': variants,
        'images': images,
        'videos': videos,
        'front_image': front_image,
        'back_image': back_image,
        'active_nav': 'products',
    })


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


# ── Customers ─────────────────────────────────────────────────────────────────



def _get_product(product_id: str):
    from plugins.installed.catalog.models import Product
    return get_object_or_404(Product, pk=product_id)


@staff_member_required
def variant_new(request: HttpRequest, product_id: str) -> HttpResponse:
    product = _get_product(product_id)
    if request.method == 'POST':
        form = VariantForm(request.POST, product=product)
        if form.is_valid():
            form.save()
            # First variant flips the product to 'variable' as a convenience.
            if product.product_type == 'simple':
                product.product_type = 'variable'
                product.save(update_fields=['product_type', 'updated_at'])
            messages.success(request, 'Variant added.')
            return ajax_or_redirect(request, 'admin_dashboard:product_edit', product_id=product.id)
    else:
        form = VariantForm(product=product)
    return render(request, 'admin_dashboard/variant_form.html', {
        'form': form,
        'product': product,
        'variant': None,
        'active_nav': 'products',
    })


@staff_member_required
def variant_edit(request: HttpRequest, product_id: str, variant_id: str) -> HttpResponse:
    from plugins.installed.catalog.models import ProductVariant
    product = _get_product(product_id)
    variant = get_object_or_404(ProductVariant, pk=variant_id, product=product)
    if request.method == 'POST':
        form = VariantForm(request.POST, instance=variant, product=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Variant saved.')
            return ajax_or_redirect(request, 'admin_dashboard:product_edit', product_id=product.id)
    else:
        form = VariantForm(instance=variant, product=product)
    return render(request, 'admin_dashboard/variant_form.html', {
        'form': form,
        'product': product,
        'variant': variant,
        'active_nav': 'products',
    })


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
def image_upload(request: HttpRequest, product_id: str) -> HttpResponse:
    """POST-only: accept a multipart upload, attach to product."""
    if request.method != 'POST':
        return redirect('admin_dashboard:product_edit', product_id=product_id)
    from plugins.installed.catalog.models import ProductImage
    product = _get_product(product_id)
    upload = request.FILES.get('image')
    if not upload:
        messages.error(request, 'Choose an image to upload.')
        return redirect('admin_dashboard:product_edit', product_id=product.id)
    # Cheap MIME guard — ImageField does its own validation but we want a
    # clearer error if someone uploads a PDF or .txt by accident.
    if not (upload.content_type or '').startswith('image/'):
        messages.error(request, 'That file is not an image.')
        return redirect('admin_dashboard:product_edit', product_id=product.id)
    alt = (request.POST.get('alt_text') or '').strip()[:255]

    # 15-image cap (Phase 1 of docs/plans/product-slider.md).
    # Slider only renders 15 anyway; refuse to accept more so the DB
    # doesn't accumulate orphan rows the merchant can't see.
    image_count = ProductImage.objects.filter(product=product).count()
    if image_count >= 15:
        messages.error(
            request,
            'You can have up to 15 images per product. Delete one before uploading another.',
        )
        return redirect('admin_dashboard:product_edit', product_id=product.id)

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
        .order_by('-sort_order').values_list('sort_order', flat=True).first()
    )
    if max_sort is None:
        sort_order = 0
        is_primary = True
    else:
        sort_order = int(max_sort) + 1
        is_primary = False

    ProductImage.objects.create(
        product=product,
        image=upload,
        alt_text=alt,
        is_primary=is_primary,
        sort_order=sort_order,
    )
    messages.success(request, 'Image uploaded.')
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
        should_primary = (idx == 0)
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
        .order_by('-sort_order').values_list('sort_order', flat=True).first()
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
            product=product, is_primary=True, sort_order=target_sort,
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



