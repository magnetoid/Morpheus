"""Dashboard views for draft orders."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from morpheus.app.views import (
    get_object_or_404,
    messages,
    redirect,
    render,
    staff_member_required,
)
from plugins.installed.draft_orders import services
from plugins.installed.draft_orders.models import DraftOrder, DraftOrderLine


def _editable(draft) -> bool:
    return draft.status not in ('converted', 'cancelled')


@staff_member_required
def index(request):
    drafts = DraftOrder.objects.select_related('customer', 'channel').order_by('-created_at')[:200]
    return render(request, 'draft_orders/index.html', {'drafts': drafts})


@staff_member_required
def detail(request, number: str):
    draft = get_object_or_404(DraftOrder, number=number)
    # Variants for the "add line" picker. Limit to active products to avoid
    # a 1000-option select; a real autocomplete is the next step up.
    variants: list = []
    try:
        from plugins.installed.catalog.models import ProductVariant

        variants = list(
            ProductVariant.objects.select_related('product')
            .filter(is_active=True, product__status='active')
            .order_by('product__name', 'name')[:500]
        )
    except Exception:  # noqa: BLE001 — catalog is a plugin too
        variants = []
    return render(
        request,
        'draft_orders/detail.html',
        {
            'draft': draft,
            'variants': variants,
            'editable': _editable(draft),
        },
    )


@staff_member_required
def line_add(request, number: str):
    draft = get_object_or_404(DraftOrder, number=number)
    if request.method != 'POST':
        return redirect(f'/dashboard/draft-orders/{draft.number}/')
    if not _editable(draft):
        messages.error(request, 'This draft is locked and cannot be edited.')
        return redirect(f'/dashboard/draft-orders/{draft.number}/')

    from djmoney.money import Money

    variant = None
    variant_id = (request.POST.get('variant') or '').strip()
    if variant_id:
        try:
            from plugins.installed.catalog.models import ProductVariant

            variant = ProductVariant.objects.select_related('product').get(pk=variant_id)
        except Exception:  # noqa: BLE001 — bad UUID, missing variant, plugin off
            variant = None

    name = (request.POST.get('product_name') or '').strip()[:255]
    sku = (request.POST.get('sku') or '').strip()[:64]
    raw_price = (request.POST.get('unit_price') or '').strip()
    raw_qty = (request.POST.get('quantity') or '1').strip()

    # If a variant was picked, fall back to its product/price for any blank field.
    if variant is not None:
        if not name:
            name = variant.product.name + (f' — {variant.name}' if variant.name else '')
        if not sku:
            sku = variant.sku or ''
        if not raw_price:
            ep = variant.effective_price
            if ep is not None:
                raw_price = str(ep.amount)

    if not name:
        messages.error(request, 'Pick a variant or enter a product name.')
        return redirect(f'/dashboard/draft-orders/{draft.number}/')

    try:
        unit_price = Decimal(raw_price or '0')
        quantity = max(int(raw_qty), 1)
    except (InvalidOperation, ValueError):
        messages.error(request, 'Invalid price or quantity.')
        return redirect(f'/dashboard/draft-orders/{draft.number}/')

    currency = str(getattr(draft.subtotal, 'currency', 'USD'))
    DraftOrderLine.objects.create(
        draft=draft,
        variant=variant,
        product_name=name,
        sku=sku,
        unit_price=Money(unit_price, currency),
        quantity=quantity,
    )
    services.recalc(draft)
    messages.success(request, f'Added {quantity}× {name}.')
    return redirect(f'/dashboard/draft-orders/{draft.number}/')


@staff_member_required
def line_delete(request, number: str, line_id: str):
    draft = get_object_or_404(DraftOrder, number=number)
    if request.method != 'POST':
        return redirect(f'/dashboard/draft-orders/{draft.number}/')
    if not _editable(draft):
        messages.error(request, 'This draft is locked and cannot be edited.')
        return redirect(f'/dashboard/draft-orders/{draft.number}/')
    line = get_object_or_404(DraftOrderLine, pk=line_id, draft=draft)
    line.delete()
    services.recalc(draft)
    messages.success(request, 'Line removed.')
    return redirect(f'/dashboard/draft-orders/{draft.number}/')


@staff_member_required
def cancel(request, number: str):
    draft = get_object_or_404(DraftOrder, number=number)
    if request.method == 'POST' and _editable(draft):
        draft.status = 'cancelled'
        draft.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'Draft #{draft.number} cancelled.')
    return redirect(f'/dashboard/draft-orders/{draft.number}/')


@staff_member_required
def convert(request, number: str):
    draft = get_object_or_404(DraftOrder, number=number)
    if request.method == 'POST':
        if not draft.lines.exists():
            messages.error(request, 'Add at least one line before converting.')
            return redirect(f'/dashboard/draft-orders/{draft.number}/')
        services.recalc(draft)
        order = services.convert_to_order(draft)
        return redirect(f'/dashboard/orders/{order.order_number}/')
    return redirect(f'/dashboard/draft-orders/{draft.number}/')
