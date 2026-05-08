"""Auto-split from the legacy admin_dashboard/views.py monolith."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from morpheus.views import HttpRequest, HttpResponse, messages, staff_member_required
from morpheus.views import get_object_or_404, redirect, render
from django.db.models import Sum
from django.utils import timezone

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
    Metric, _bulk_ids, _period, _pct_delta, _since, _sparkline_points, _trend, logger,
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
            .order_by('-created_at')
        )
        if status:
            qs = qs.filter(status=status)
        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(sku__icontains=search)
        products = list(qs[:100])
    except Exception:  # noqa: BLE001
        products = []
    return render(request, 'admin_dashboard/products.html', {
        'products': products,
        'status_filter': status,
        'status_choices': PRODUCT_STATUS_CHOICES,
        'status_counts': status_counts,
        'search': search,
        'active_nav': 'products',
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
            return redirect('admin_dashboard:product_edit', product_id=product.id)
    else:
        form = ProductForm(instance=product)
    categories, vendors = _product_form_choices()
    variants = list(product.variants.all().order_by('sort_order', 'name'))
    images = list(product.images.all().order_by('sort_order', '-is_primary'))
    return render(request, 'admin_dashboard/product_form.html', {
        'form': form,
        'product': product,
        'categories': categories,
        'vendors': vendors,
        'variants': variants,
        'images': images,
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
            return redirect('admin_dashboard:product_edit', product_id=product.id)
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
            return redirect('admin_dashboard:product_edit', product_id=product.id)
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
    is_primary = bool(request.POST.get('is_primary'))
    if is_primary:
        # Only one primary at a time.
        ProductImage.objects.filter(product=product, is_primary=True).update(is_primary=False)
    next_order = (
        ProductImage.objects.filter(product=product)
        .order_by('-sort_order').values_list('sort_order', flat=True).first()
    )
    ProductImage.objects.create(
        product=product,
        image=upload,
        alt_text=alt,
        is_primary=is_primary,
        sort_order=(next_order or 0) + 1,
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
def image_set_primary(request: HttpRequest, product_id: str, image_id: str) -> HttpResponse:
    from plugins.installed.catalog.models import ProductImage
    product = _get_product(product_id)
    image = get_object_or_404(ProductImage, pk=image_id, product=product)
    if request.method == 'POST':
        ProductImage.objects.filter(product=product, is_primary=True).update(is_primary=False)
        image.is_primary = True
        image.save(update_fields=['is_primary'])
        messages.success(request, 'Primary image updated.')
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



