"""
Admin dashboard views — Shopify-inspired merchant UI.

Notes
-----
- Every view is `@staff_member_required` and uses the Django ORM directly
  for performance + reliability. (LAW 3 prohibits ORM access from the
  *storefront* — the staff dashboard is fine.)
- Each view returns a single context dict with:
    * `metrics`         — small KPI tiles
    * `rows` / `items`  — table data
    * `active_nav`      — sidebar highlight
    * `period`          — current selection ("today" | "7d" | "30d" | "90d")
- Views are deliberately resilient: a missing plugin model raises an
  `ImportError`, caught and rendered as an empty section so the dashboard
  never crashes on optional plugins.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

from morpheus.views import messages
from morpheus.views import staff_member_required
from django.db.models import Sum
from morpheus.views import HttpRequest, HttpResponse
from morpheus.views import get_object_or_404, redirect, render
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

logger = logging.getLogger('morpheus.admin')

_PERIODS = {
    'today': 1,
    '7d': 7,
    '30d': 30,
    '90d': 90,
}


def _period(request: HttpRequest) -> tuple[str, int]:
    period = request.GET.get('period', '7d')
    if period not in _PERIODS:
        period = '7d'
    return period, _PERIODS[period]


def _since(days: int):
    return timezone.now() - timedelta(days=days)


@dataclass(slots=True)
class Metric:
    label: str
    value: str
    delta: str = ''
    trend: str = 'flat'  # 'up' | 'down' | 'flat'
    icon: str = 'activity'


def _trend(now, before) -> str:
    if not before:
        return 'flat'
    if now > before:
        return 'up'
    if now < before:
        return 'down'
    return 'flat'


def _pct_delta(now, before) -> str:
    if not before:
        return '—'
    diff = (Decimal(now) - Decimal(before)) / Decimal(before) * Decimal('100')
    sign = '+' if diff >= 0 else ''
    return f'{sign}{diff:.1f}%'


# ── Dashboard home ────────────────────────────────────────────────────────────


@staff_member_required
def dashboard_home(request: HttpRequest) -> HttpResponse:
    period, days = _period(request)
    since = _since(days)

    metrics: list[Metric] = []
    recent_orders: list[Any] = []
    top_products: list[Any] = []
    insights: list[Any] = []

    try:
        from plugins.installed.orders.models import Order

        orders_qs = Order.objects.filter(placed_at__gte=since)
        order_count = orders_qs.count()
        revenue = orders_qs.aggregate(total=Sum('total'))['total'] or Decimal('0')
        avg_order = (revenue / order_count) if order_count else Decimal('0')

        prev_orders = Order.objects.filter(
            placed_at__gte=_since(days * 2),
            placed_at__lt=since,
        )
        prev_count = prev_orders.count()
        prev_revenue = prev_orders.aggregate(total=Sum('total'))['total'] or Decimal('0')

        metrics.extend([
            Metric(
                label='Total sales',
                value=f'${revenue:,.2f}',
                delta=_pct_delta(revenue, prev_revenue),
                trend=_trend(revenue, prev_revenue),
                icon='dollar-sign',
            ),
            Metric(
                label='Orders',
                value=f'{order_count:,}',
                delta=_pct_delta(order_count, prev_count),
                trend=_trend(order_count, prev_count),
                icon='shopping-bag',
            ),
            Metric(
                label='Average order',
                value=f'${avg_order:,.2f}' if order_count else '—',
                icon='trending-up',
            ),
        ])

        recent_orders = list(
            Order.objects
            .select_related('customer', 'channel')
            .order_by('-placed_at')[:6]
        )
    except Exception as e:  # noqa: BLE001 — plugin optional / fail soft
        logger.warning('admin_dashboard: orders panel error: %s', e, exc_info=True)

    try:
        from plugins.installed.catalog.models import Product

        active_count = Product.objects.filter(status='active').count()
        metrics.append(Metric(
            label='Active products',
            value=f'{active_count:,}',
            icon='package',
        ))
        top_products = list(
            Product.objects.filter(status='active')
            .order_by('-created_at')[:5]
        )
    except Exception as e:  # noqa: BLE001
        logger.warning('admin_dashboard: catalog panel error: %s', e, exc_info=True)

    try:
        from plugins.installed.ai_assistant.models import MerchantInsight
        insights = list(
            MerchantInsight.objects
            .filter(is_read=False)
            .order_by('-created_at')[:4]
        )
    except Exception as e:  # noqa: BLE001
        logger.debug('admin_dashboard: insights panel skipped: %s', e)

    # AI summary block: counts of active agents + recent runs + provider in
    # use. Fail-soft if agent_core / ai_assistant aren't installed.
    ai_summary: dict[str, Any] = {
        'agent_count': 0,
        'recent_runs': 0,
        'unread_insights': len(insights),
        'provider': '',
        'has_keys': False,
    }
    try:
        from plugins.registry import plugin_registry
        ai_plugin = plugin_registry.get('ai_assistant')
        if ai_plugin is not None:
            cfg = ai_plugin.get_config()
            ai_summary['provider'] = cfg.get('ai_provider') or 'openai'
            ai_summary['has_keys'] = any(
                cfg.get(k) for k in (
                    'openai_api_key', 'anthropic_api_key', 'gemini_api_key',
                    'openrouter_api_key', 'ollama_api_key',
                )
            )
    except Exception:  # noqa: BLE001
        pass
    try:
        from plugins.installed.agent_core.models import Agent, AgentRun
        ai_summary['agent_count'] = Agent.objects.filter(is_active=True).count()
        ai_summary['recent_runs'] = AgentRun.objects.filter(
            created_at__gte=_since(7),
        ).count()
    except Exception:  # noqa: BLE001
        pass

    # Stock alerts — surface on home only when at least one variant is
    # below threshold. Inventory + advanced_ecommerce both optional.
    low_stock: list[Any] = []
    low_stock_threshold = 0
    try:
        from plugins.installed.inventory.models import StockLevel
        from plugins.registry import plugin_registry
        ae_plugin = plugin_registry.get('advanced_ecommerce')
        low_stock_threshold = (
            int(ae_plugin.get_config_value('low_stock_threshold', 5))
            if ae_plugin else 5
        )
        # available_quantity is a Python property; pull a small page and
        # filter in-memory so we don't need a denormalised column.
        candidates = list(
            StockLevel.objects
            .select_related('variant', 'variant__product', 'warehouse')
            .filter(quantity__lte=low_stock_threshold + 50)[:200]
        )
        low_stock = sorted(
            (sl for sl in candidates if sl.available_quantity <= low_stock_threshold),
            key=lambda sl: sl.available_quantity,
        )[:6]
    except Exception:  # noqa: BLE001
        pass

    return render(request, 'admin_dashboard/home.html', {
        'metrics': metrics,
        'recent_orders': recent_orders,
        'top_products': top_products,
        'insights': insights,
        'ai_summary': ai_summary,
        'low_stock': low_stock,
        'low_stock_threshold': low_stock_threshold,
        'active_nav': 'home',
        'period': period,
    })


# ── Orders ────────────────────────────────────────────────────────────────────


@staff_member_required
def orders_list(request: HttpRequest) -> HttpResponse:
    status_filter = request.GET.get('status', '')
    search = request.GET.get('q', '').strip()[:80]
    orders: list[Any] = []
    try:
        from plugins.installed.orders.models import Order
        qs = (
            Order.objects
            .select_related('customer', 'channel')
            .order_by('-placed_at')
        )
        if status_filter:
            qs = qs.filter(status=status_filter)
        if search:
            qs = qs.filter(order_number__icontains=search) | qs.filter(email__icontains=search)
        orders = list(qs[:100])
    except Exception:  # noqa: BLE001
        orders = []
    # Drafts surface inside the Orders page rather than as a separate
    # sidebar entry — staff sees drafts and real orders side by side.
    draft_count = 0
    drafts_url = ''
    try:
        from plugins.installed.draft_orders.models import DraftOrder
        draft_count = DraftOrder.objects.exclude(status='converted').count()
        drafts_url = '/dashboard/draft-orders/'
    except Exception:  # noqa: BLE001 — draft_orders may be disabled
        pass

    return render(request, 'admin_dashboard/orders.html', {
        'orders': orders,
        'status_filter': status_filter,
        'search': search,
        'draft_count': draft_count,
        'drafts_url': drafts_url,
        'active_nav': 'orders',
    })


@staff_member_required
def order_detail(request: HttpRequest, order_number: str) -> HttpResponse:
    order = None
    try:
        from plugins.installed.orders.models import Order
        order = (
            Order.objects
            .select_related('customer', 'channel')
            .prefetch_related('items', 'items__product', 'events', 'fulfillments')
            .get(order_number=order_number)
        )
    except Exception:  # noqa: BLE001
        order = None
    refunds: list[Any] = []
    refunded_total = Decimal('0')
    fulfillments: list[Any] = []
    if order is not None:
        try:
            refunds = list(order.refunds.all().order_by('-created_at'))
            refunded_total = sum(
                (Decimal(str(r.amount.amount)) for r in refunds), Decimal('0'),
            )
        except Exception:  # noqa: BLE001
            pass
        try:
            fulfillments = list(
                order.fulfillments.all()
                .prefetch_related('items', 'items__order_item')
                .order_by('-created_at')
            )
        except Exception:  # noqa: BLE001
            pass
    return render(request, 'admin_dashboard/order_detail.html', {
        'order': order,
        'refunds': refunds,
        'refunded_total': refunded_total,
        'fulfillments': fulfillments,
        'active_nav': 'orders',
    })


# ── Products ──────────────────────────────────────────────────────────────────


@staff_member_required
def products_list(request: HttpRequest) -> HttpResponse:
    status = request.GET.get('status', '')
    search = request.GET.get('q', '').strip()[:80]
    products: list[Any] = []
    try:
        from plugins.installed.catalog.models import Product
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


@staff_member_required
def customers_list(request: HttpRequest) -> HttpResponse:
    """Unified Contacts list — customers, leads, signups in one table.

    `source` filter narrows by where the contact arrived from (orders,
    lead form, signup, newsletter, …). The view name + URL stay
    `customers` for stability; the page label is "Contacts".
    """
    search = request.GET.get('q', '').strip()[:80]
    source_filter = request.GET.get('source', '').strip()[:20]
    customers: list[Any] = []
    try:
        from django.contrib.auth import get_user_model
        from django.db.models import Q
        from plugins.installed.orders.models import Order
        User = get_user_model()
        qs = User.objects.order_by('-date_joined')
        if search:
            qs = qs.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        if source_filter:
            qs = qs.filter(source=source_filter)
        rows = []
        for user in qs[:100]:
            order_qs = Order.objects.filter(customer=user)
            source = getattr(user, 'source', '') or ''
            # Prefer the CDP denormalized fields (cheap), fall back to live
            # aggregation when they aren't populated yet (pre-backfill row).
            denormalized_count = getattr(user, 'purchase_count', 0) or 0
            denormalized_ltv = getattr(user, 'lifetime_value', None) or Decimal('0')
            if denormalized_count:
                order_count = denormalized_count
                spent = denormalized_ltv
            else:
                order_count = order_qs.count()
                spent = order_qs.aggregate(total=Sum('total'))['total'] or Decimal('0')
            rows.append({
                'id': user.pk,
                'email': getattr(user, 'email', ''),
                'name': (
                    (getattr(user, 'first_name', '') + ' ' +
                     getattr(user, 'last_name', '')).strip() or '—'
                ),
                'source': source,
                'source_display': (
                    user.get_source_display() if hasattr(user, 'get_source_display') and source else ''
                ),
                'order_count': order_count,
                'spent': spent,
                'last_order_at': getattr(user, 'last_order_at', None),
                'date_joined': getattr(user, 'date_joined', None),
            })
        customers = rows
    except Exception:  # noqa: BLE001
        customers = []
    return render(request, 'admin_dashboard/customers.html', {
        'customers': customers,
        'search': search,
        'source_filter': source_filter,
        'active_nav': 'customers',
    })


@staff_member_required
def customer_new(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f'Customer "{customer.email}" created.')
            return redirect('admin_dashboard:customer_edit', customer_id=customer.id)
    else:
        form = CustomerForm()
    return render(request, 'admin_dashboard/customer_form.html', {
        'form': form,
        'customer': None,
        'active_nav': 'customers',
    })


@staff_member_required
def customer_edit(request: HttpRequest, customer_id: str) -> HttpResponse:
    from django.contrib.auth import get_user_model
    User = get_user_model()
    customer = get_object_or_404(User, pk=customer_id)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, 'Customer saved.')
            return redirect('admin_dashboard:customer_edit', customer_id=customer.id)
    else:
        form = CustomerForm(instance=customer)
    # Quick stats so the edit page also works as a customer profile.
    order_summary: dict[str, Any] = {'count': 0, 'spent': Decimal('0'), 'recent': []}
    try:
        from plugins.installed.orders.models import Order
        orders_qs = Order.objects.filter(customer=customer)
        order_summary['count'] = orders_qs.count()
        order_summary['spent'] = (
            orders_qs.aggregate(t=Sum('total'))['t'] or Decimal('0')
        )
        order_summary['recent'] = list(orders_qs.order_by('-placed_at')[:5])
    except Exception:  # noqa: BLE001
        pass
    addresses: list[Any] = []
    try:
        addresses = list(customer.addresses.all())
    except Exception:  # noqa: BLE001 — customer model may not have addresses
        pass
    return render(request, 'admin_dashboard/customer_form.html', {
        'form': form,
        'customer': customer,
        'order_summary': order_summary,
        'addresses': addresses,
        'active_nav': 'customers',
    })


@staff_member_required
def customer_delete(request: HttpRequest, customer_id: str) -> HttpResponse:
    from django.contrib.auth import get_user_model
    User = get_user_model()
    customer = get_object_or_404(User, pk=customer_id)
    if request.method == 'POST':
        # Refuse to nuke staff/superuser accounts from the merchant UI.
        if customer.is_staff or customer.is_superuser:
            messages.error(request, 'Staff accounts cannot be deleted from here.')
            return redirect('admin_dashboard:customer_edit', customer_id=customer.id)
        email = customer.email
        customer.delete()
        messages.success(request, f'Deleted customer "{email}".')
        return redirect('admin_dashboard:customers')
    return redirect('admin_dashboard:customer_edit', customer_id=customer.id)


# ── Customer addresses ────────────────────────────────────────────────────────


def _get_customer(customer_id: str):
    from django.contrib.auth import get_user_model
    return get_object_or_404(get_user_model(), pk=customer_id)


@staff_member_required
def address_new(request: HttpRequest, customer_id: str) -> HttpResponse:
    customer = _get_customer(customer_id)
    if request.method == 'POST':
        form = AddressForm(request.POST, customer=customer)
        if form.is_valid():
            form.save()
            messages.success(request, 'Address added.')
            return redirect('admin_dashboard:customer_edit', customer_id=customer.id)
    else:
        form = AddressForm(customer=customer)
    return render(request, 'admin_dashboard/address_form.html', {
        'form': form,
        'customer': customer,
        'address': None,
        'active_nav': 'customers',
    })


@staff_member_required
def address_edit(request: HttpRequest, customer_id: str, address_id: str) -> HttpResponse:
    from plugins.installed.customers.models import Address
    customer = _get_customer(customer_id)
    address = get_object_or_404(Address, pk=address_id, customer=customer)
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address, customer=customer)
        if form.is_valid():
            form.save()
            messages.success(request, 'Address saved.')
            return redirect('admin_dashboard:customer_edit', customer_id=customer.id)
    else:
        form = AddressForm(instance=address, customer=customer)
    return render(request, 'admin_dashboard/address_form.html', {
        'form': form,
        'customer': customer,
        'address': address,
        'active_nav': 'customers',
    })


@staff_member_required
def address_delete(request: HttpRequest, customer_id: str, address_id: str) -> HttpResponse:
    from plugins.installed.customers.models import Address
    customer = _get_customer(customer_id)
    address = get_object_or_404(Address, pk=address_id, customer=customer)
    if request.method == 'POST':
        address.delete()
        messages.success(request, 'Address deleted.')
    return redirect('admin_dashboard:customer_edit', customer_id=customer.id)


# ── Order actions ─────────────────────────────────────────────────────────────


@staff_member_required
def order_new(request: HttpRequest) -> HttpResponse:
    """Create a draft order from the dashboard.

    Real `orders.Order` rows are produced by the storefront checkout or by
    converting a draft — staff don't hand-craft FSM-managed orders.
    """
    customers: list[Any] = []
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        customers = list(User.objects.order_by('-date_joined')[:200])
    except Exception:  # noqa: BLE001
        pass

    if request.method == 'POST':
        form = DraftOrderForm(request.POST)
        if form.is_valid():
            draft = form.save()
            messages.success(request, f'Draft order #{draft.number} created.')
            return redirect(f'/dashboard/draft-orders/{draft.number}/')
    else:
        form = DraftOrderForm()
    return render(request, 'admin_dashboard/order_new.html', {
        'form': form,
        'customers': customers,
        'active_nav': 'orders',
    })


@staff_member_required
def order_action(request: HttpRequest, order_number: str) -> HttpResponse:
    """POST-only side-effects on an existing order (cancel, mark paid, …)."""
    if request.method != 'POST':
        return redirect('admin_dashboard:order_detail', order_number=order_number)

    from plugins.installed.orders.models import Order
    order = get_object_or_404(Order, order_number=order_number)
    action = request.POST.get('action', '')

    try:
        if action == 'cancel':
            order.cancel(reason=request.POST.get('reason', '') or 'Cancelled from dashboard')
            order.save()
            messages.success(request, f'Order #{order.order_number} cancelled.')
        elif action == 'confirm':
            order.confirm()
            order.save()
            messages.success(request, f'Order #{order.order_number} confirmed.')
        elif action == 'process':
            order.process()
            order.save()
            messages.success(request, f'Order #{order.order_number} marked as processing.')
        elif action == 'fulfill':
            order.fulfill()
            order.save()
            messages.success(request, f'Order #{order.order_number} marked as fulfilled.')
        elif action == 'ship':
            tracking = (request.POST.get('tracking_number') or '').strip()[:200]
            order.ship(tracking_number=tracking)
            order.save()
            messages.success(request, f'Order #{order.order_number} marked as shipped.')
        elif action == 'deliver':
            order.deliver()
            order.save()
            messages.success(request, f'Order #{order.order_number} marked as delivered.')
        elif action == 'mark_paid':
            order.payment_status = 'paid'
            order.save(update_fields=['payment_status', 'updated_at'])
            order.log_event('PAYMENT_MARKED_PAID', message='Marked paid via dashboard')
            messages.success(request, f'Order #{order.order_number} marked paid.')
        elif action == 'add_tracking':
            tracking = (request.POST.get('tracking_number') or '').strip()[:200]
            method = (request.POST.get('shipping_method') or '').strip()[:100]
            order.tracking_number = tracking
            if method:
                order.shipping_method = method
            order.save(update_fields=['tracking_number', 'shipping_method', 'updated_at'])
            order.log_event('TRACKING_UPDATED', message=tracking)
            messages.success(request, 'Tracking updated.')
        else:
            messages.error(request, f'Unknown action "{action}".')
    except Exception as e:  # noqa: BLE001 — FSM rejects illegal transitions
        logger.warning('order_action %s on %s failed: %s', action, order_number, e)
        messages.error(request, f'Action failed: {e}')

    return redirect('admin_dashboard:order_detail', order_number=order_number)


@staff_member_required
def order_fulfill(request: HttpRequest, order_number: str) -> HttpResponse:
    """Create a Fulfillment record for an order; optionally also flip the
    order's status to 'shipped' via the FSM."""
    from plugins.installed.orders.models import Order
    order = get_object_or_404(Order, order_number=order_number)
    if request.method == 'POST':
        form = FulfillmentForm(request.POST, order=order)
        if form.is_valid():
            f = form.save()
            if form.cleaned_data.get('mark_shipped') and order.status not in ('shipped', 'delivered', 'cancelled'):
                try:
                    order.ship(tracking_number=f.tracking_number)
                    order.save()
                except Exception as e:  # noqa: BLE001 — FSM rejects illegal moves
                    logger.warning('order_fulfill: ship transition failed: %s', e)
            messages.success(request, f'Fulfillment created for order #{order.order_number}.')
            return redirect('admin_dashboard:order_detail', order_number=order.order_number)
    else:
        form = FulfillmentForm(order=order)
    return render(request, 'admin_dashboard/order_fulfill.html', {
        'form': form,
        'order': order,
        'active_nav': 'orders',
    })


@staff_member_required
def order_refund(request: HttpRequest, order_number: str) -> HttpResponse:
    from plugins.installed.orders.models import Order
    order = get_object_or_404(Order, order_number=order_number)
    if request.method == 'POST':
        form = RefundForm(request.POST, order=order)
        if form.is_valid():
            refund = form.save()
            messages.success(request, f'Refund of {refund.amount} recorded.')
            return redirect('admin_dashboard:order_detail', order_number=order.order_number)
    else:
        form = RefundForm(order=order)
    return render(request, 'admin_dashboard/order_refund.html', {
        'form': form,
        'order': order,
        'active_nav': 'orders',
    })


# ── Product variants ──────────────────────────────────────────────────────────


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
def analytics_view(request: HttpRequest) -> HttpResponse:
    period, days = _period(request)
    since = _since(days)
    series: list[dict] = []
    try:
        from plugins.installed.observability.models import MerchantMetric
        rows = (
            MerchantMetric.objects
            .filter(granularity='hour', bucket__gte=since, metric='orders_placed')
            .order_by('bucket')
        )
        series = [{'bucket': r.bucket.isoformat(), 'value': r.value} for r in rows]
    except Exception as e:  # noqa: BLE001
        logger.debug('admin_dashboard: analytics empty: %s', e)
    return render(request, 'admin_dashboard/analytics.html', {
        'series': series,
        'active_nav': 'analytics',
        'period': period,
    })


# ── Marketing ─────────────────────────────────────────────────────────────────


@staff_member_required
def marketing_view(request: HttpRequest) -> HttpResponse:
    coupons: list[Any] = []
    try:
        from plugins.installed.marketing.models import Coupon
        coupons = list(Coupon.objects.order_by('-created_at')[:50])
    except Exception as e:  # noqa: BLE001
        logger.debug('admin_dashboard: marketing empty: %s', e)
    return render(request, 'admin_dashboard/marketing.html', {
        'coupons': coupons,
        'active_nav': 'marketing',
    })


# ── Coupons ──────────────────────────────────────────────────────────────────


@staff_member_required
def coupon_new(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = CouponForm(request.POST)
        if form.is_valid():
            coupon = form.save()
            messages.success(request, f'Coupon "{coupon.code}" created.')
            return redirect('admin_dashboard:coupon_edit', coupon_id=coupon.id)
    else:
        form = CouponForm()
    return render(request, 'admin_dashboard/coupon_form.html', {
        'form': form, 'coupon': None, 'active_nav': 'marketing',
    })


@staff_member_required
def coupon_edit(request: HttpRequest, coupon_id: str) -> HttpResponse:
    from plugins.installed.marketing.models import Coupon
    coupon = get_object_or_404(Coupon, pk=coupon_id)
    if request.method == 'POST':
        form = CouponForm(request.POST, instance=coupon)
        if form.is_valid():
            form.save()
            messages.success(request, 'Coupon saved.')
            return redirect('admin_dashboard:coupon_edit', coupon_id=coupon.id)
    else:
        form = CouponForm(instance=coupon)
    return render(request, 'admin_dashboard/coupon_form.html', {
        'form': form, 'coupon': coupon, 'active_nav': 'marketing',
    })


@staff_member_required
def coupon_delete(request: HttpRequest, coupon_id: str) -> HttpResponse:
    from plugins.installed.marketing.models import Coupon
    coupon = get_object_or_404(Coupon, pk=coupon_id)
    if request.method == 'POST':
        code = coupon.code
        coupon.delete()
        messages.success(request, f'Deleted coupon "{code}".')
        return redirect('admin_dashboard:marketing')
    return redirect('admin_dashboard:coupon_edit', coupon_id=coupon.id)


# ── Apps ──────────────────────────────────────────────────────────────────────


@staff_member_required
def apps_view(request: HttpRequest) -> HttpResponse:
    from plugins.registry import plugin_registry

    if request.method == 'POST':
        return _toggle_plugin(request)

    plugins = []
    for name, cls in sorted(plugin_registry._classes.items()):
        instance = plugin_registry.get(name)
        plugins.append({
            'name': name,
            'label': getattr(cls, 'label', name),
            'description': getattr(cls, 'description', ''),
            'version': getattr(cls, 'version', ''),
            'active': plugin_registry.is_active(name),
            'pages': [p for p in plugin_registry.dashboard_pages() if p.plugin == name],
            'has_settings': plugin_registry.settings_panel(name) is not None,
        })
    return render(request, 'admin_dashboard/apps.html', {
        'plugins': plugins,
        'active_nav': 'apps',
    })


def _toggle_plugin(request: HttpRequest):
    """POST handler on the apps page: flip a plugin's enabled state in DB."""
    from morpheus.views import redirect

    name = request.POST.get('plugin', '').strip()
    desired = request.POST.get('enabled') == '1'
    try:
        from plugins.models import PluginConfig
        row, _ = PluginConfig.objects.get_or_create(plugin_name=name)
        row.is_enabled = desired
        row.save(update_fields=['is_enabled', 'updated_at'])
    except Exception as e:  # noqa: BLE001 — DB outage shouldn't crash the page
        logger.warning('admin_dashboard: toggle %s failed: %s', name, e, exc_info=True)
    return redirect('admin_dashboard:apps')


# ── Settings ──────────────────────────────────────────────────────────────────


def _panels_by_category() -> dict:
    """Index every active plugin's SettingsPanel by its category slug."""
    from plugins.registry import plugin_registry

    by_cat: dict[str, list] = {}
    for plugin in plugin_registry.active_plugins():
        panel = plugin_registry.settings_panel(plugin.name)
        if panel is None:
            continue
        cat = getattr(panel, 'category', '') or 'apps'
        by_cat.setdefault(cat, []).append({
            'plugin': plugin.name,
            'plugin_label': plugin.label,
            'plugin_description': plugin.description,
            'panel': panel,
        })
    for entries in by_cat.values():
        entries.sort(key=lambda e: (e['panel'].label or e['plugin_label']).lower())
    return by_cat


def _build_panel_fields(plugin_instance, schema: dict) -> list[dict]:
    """Schema → list of form-field dicts (matches plugin_settings.html shape)."""
    config = plugin_instance.get_config()
    fields = []
    for key, prop in (schema.get('properties') or {}).items():
        ptype = prop.get('type', 'string')
        kind = 'enum' if 'enum' in prop else ptype
        value = config.get(key, prop.get('default', ''))
        if kind == 'boolean':
            value = bool(value)
        fields.append({
            'key': key,
            'title': prop.get('title') or key.replace('_', ' ').title(),
            'description': prop.get('description', ''),
            'kind': kind,
            'enum': prop.get('enum') or [],
            'value': value,
        })
    return fields


@staff_member_required
def settings_view(request: HttpRequest) -> HttpResponse:
    """Settings hub — Shopify-style category index.

    Renders one card per ``SettingsCategory`` showing how many plugin
    panels live under it. Each card links to
    ``/dashboard/settings/<slug>/`` where the actual editable forms are
    grouped together. The legacy
    ``/dashboard/apps/<plugin>/settings/`` URL still works as a deep
    link for backward compat.
    """
    from django.conf import settings as dj_settings
    from plugins.installed.admin_dashboard.settings_categories import (
        SETTINGS_CATEGORIES,
    )

    by_cat = _panels_by_category()
    cards = []
    for cat in SETTINGS_CATEGORIES:
        entries = by_cat.get(cat.slug, [])
        cards.append({
            'category': cat,
            'count': len(entries),
            # Show up to 3 plugin labels as a hint of what's inside.
            'plugins': [e['panel'].label or e['plugin_label'] for e in entries[:3]],
        })

    store_summary = {
        'name': getattr(dj_settings, 'STORE_NAME', '—'),
        'currency': getattr(dj_settings, 'STORE_CURRENCY', '—'),
        'country': getattr(dj_settings, 'STORE_COUNTRY', '—'),
        'theme': getattr(dj_settings, 'MORPHEUS_ACTIVE_THEME', '—'),
    }
    return render(request, 'admin_dashboard/settings.html', {
        'cards': cards,
        'store_summary': store_summary,
        'active_nav': 'settings',
    })


_CORE_FORMS_BY_CATEGORY = {
    'general': ('StoreGeneralForm', 'Store details', 'Name, description, currency, locale.'),
    'notifications': ('StoreNotificationsForm', 'Email sender + SMTP', 'Outbound email used for transactional notifications.'),
}


def _core_form_for(category: str):
    """Return (form_class, title, description) for a category, or None."""
    entry = _CORE_FORMS_BY_CATEGORY.get(category)
    if entry is None:
        return None
    from plugins.installed.admin_dashboard import forms as dashboard_forms
    cls = getattr(dashboard_forms, entry[0])
    return cls, entry[1], entry[2]


@staff_member_required
def settings_ai_probe(request: HttpRequest) -> HttpResponse:
    """JSON endpoint backing the "Fetch models" + "Test connection" buttons.

    POST body fields:
        provider — openai | anthropic | gemini | openrouter | ollama
        api_key  — optional override; falls back to saved plugin config
        base_url — optional override

    Returns ``{"ok": bool, "models": [{"id", "label"}], "error": str}``.
    """
    from morpheus.views import JsonResponse

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    provider = (request.POST.get('provider') or '').strip()
    if not provider:
        return JsonResponse({'ok': False, 'error': 'provider is required'}, status=400)

    api_key = (request.POST.get('api_key') or '').strip()
    base_url = (request.POST.get('base_url') or '').strip()
    try:
        from plugins.registry import plugin_registry
        ai_plugin = plugin_registry.get('ai_assistant')
        if ai_plugin is not None:
            cfg = ai_plugin.get_config()
            if not api_key:
                api_key = cfg.get(f'{provider}_api_key') or ''
            if not base_url:
                base_url = cfg.get(f'{provider}_base_url') or ''
    except Exception:  # noqa: BLE001
        pass

    from plugins.installed.ai_assistant.services.probe import probe
    result = probe(provider, api_key=api_key, base_url=base_url)
    return JsonResponse(result)


_AI_PROVIDERS = [
    {
        'slug': 'openai',
        'label': 'OpenAI',
        'icon': 'sparkle',
        'fields': ('api_key', 'base_url', 'model'),
        'help_url': 'https://platform.openai.com/api-keys',
        'placeholder_model': 'gpt-4o-mini',
    },
    {
        'slug': 'anthropic',
        'label': 'Anthropic',
        'icon': 'sparkle',
        'fields': ('api_key', 'model'),
        'help_url': 'https://console.anthropic.com/settings/keys',
        'placeholder_model': 'claude-3-5-sonnet-latest',
    },
    {
        'slug': 'gemini',
        'label': 'Google Gemini',
        'icon': 'sparkle',
        'fields': ('api_key', 'model'),
        'help_url': 'https://aistudio.google.com/app/apikey',
        'placeholder_model': 'gemini-2.0-flash',
    },
    {
        'slug': 'openrouter',
        'label': 'OpenRouter',
        'icon': 'route',
        'fields': ('api_key', 'base_url', 'model'),
        'help_url': 'https://openrouter.ai/keys',
        'placeholder_model': 'anthropic/claude-3.5-sonnet',
    },
    {
        'slug': 'ollama',
        'label': 'Ollama',
        'icon': 'cpu',
        'fields': ('base_url', 'api_key', 'model'),
        'help_url': 'https://ollama.com',
        'placeholder_model': 'llama3.2',
        'api_key_optional': True,
    },
]


@staff_member_required
def settings_ai(request: HttpRequest) -> HttpResponse:
    """Custom AI providers settings page — card per provider.

    Replaces the schema-driven render path for the 'ai' category. Each
    provider gets its own form/card with Fetch / Test buttons and a
    per-provider Save. The agent_core 'Agents' panel still renders below
    as a regular schema-driven panel for runtime config.
    """
    from plugins.registry import plugin_registry
    from plugins.installed.admin_dashboard.settings_categories import get_category

    cat = get_category('ai')
    ai_plugin = plugin_registry.get('ai_assistant')
    cfg = ai_plugin.get_config() if ai_plugin else {}
    active = cfg.get('ai_provider') or 'openai'

    # Per-provider card data with current values + status.
    cards = []
    for p in _AI_PROVIDERS:
        api_key = cfg.get(f'{p["slug"]}_api_key', '') or ''
        base_url = cfg.get(f'{p["slug"]}_base_url', '') or ''
        model = cfg.get(f'{p["slug"]}_model', '') or p.get('placeholder_model', '')
        configured = bool(api_key) or p.get('api_key_optional')
        cards.append({
            **p,
            'api_key': api_key,
            'base_url': base_url,
            'model': model,
            'configured': configured,
            'is_active': p['slug'] == active,
        })

    # The agent_core panel — render it as a secondary schema-driven card
    # below the providers (existing template fields helper handles it).
    agent_core_card = None
    ac_plugin = plugin_registry.get('agent_core')
    if ac_plugin is not None and plugin_registry.settings_panel('agent_core') is not None:
        panel = plugin_registry.settings_panel('agent_core')
        agent_core_card = {
            'plugin_name': 'agent_core',
            'plugin': ac_plugin,
            'panel': panel,
            'fields': _build_panel_fields(ac_plugin, panel.schema),
            'submit_url': '/dashboard/apps/agent_core/settings/',
        }

    feature_flags = [
        ('enable_intent_engine', 'Intent engine'),
        ('enable_semantic_search', 'Semantic search'),
        ('enable_dynamic_pricing', 'Dynamic pricing'),
        ('enable_zero_shot_catalog', 'Zero-shot catalog'),
        ('enable_autonomous_operator', 'Autonomous operator'),
        ('enable_synthetic_testing', 'Synthetic testing'),
        ('agent_purchase_requires_approval', 'Agent purchases require approval'),
    ]
    features = [
        {'key': k, 'label': lbl, 'value': bool(cfg.get(k))}
        for k, lbl in feature_flags
    ]

    return render(request, 'admin_dashboard/settings_ai.html', {
        'category': cat,
        'cards': cards,
        'active_provider': active,
        'features': features,
        'agent_core_card': agent_core_card,
        'active_nav': 'settings',
    })


@staff_member_required
def settings_category(request: HttpRequest, category: str) -> HttpResponse:
    """Render every plugin SettingsPanel that belongs to one category.

    The 'ai' category is handled by a dedicated rich view (per-provider
    cards). Everything else falls through to the schema-driven render.

    For categories that map to core ``StoreSettings`` fields ('general',
    'notifications') we additionally render an editable core form at the
    top of the page. POSTs land in this same view and are dispatched by
    the hidden ``_form`` field so we can host both core and plugin
    submissions on one URL.

    Each plugin panel becomes a card with an inline form posting to the
    existing plugin-settings handler at
    ``/dashboard/apps/<plugin>/settings/``.
    """
    from plugins.installed.admin_dashboard.settings_categories import get_category
    from plugins.registry import plugin_registry

    # AI gets a custom render — per-provider cards with Fetch / Test
    # buttons rather than a single schema-driven form.
    if category == 'ai':
        return settings_ai(request)

    cat = get_category(category)
    if cat is None:
        from morpheus.views import Http404
        raise Http404('Unknown settings category')

    core_card = None
    core_entry = _core_form_for(category)
    if core_entry is not None:
        FormCls, core_title, core_description = core_entry
        from core.models import StoreSettings
        instance = StoreSettings.objects.first()

        if request.method == 'POST' and request.POST.get('_form') == 'core':
            form = FormCls(request.POST, instance=instance)
            if form.is_valid():
                form.save()
                messages.success(request, f'{core_title} saved.')
                return redirect('admin_dashboard:settings_category', category=category)
        else:
            form = FormCls(instance=instance)

        core_card = {
            'title': core_title,
            'description': core_description,
            'form': form,
        }

    by_cat = _panels_by_category()
    entries = by_cat.get(category, [])
    cards = []
    for entry in entries:
        instance = plugin_registry.get(entry['plugin'])
        if instance is None:
            continue
        cards.append({
            'plugin': instance,
            'plugin_name': entry['plugin'],
            'panel': entry['panel'],
            'fields': _build_panel_fields(instance, entry['panel'].schema),
            'submit_url': f'/dashboard/apps/{entry["plugin"]}/settings/',
        })

    return render(request, 'admin_dashboard/settings_category.html', {
        'category': cat,
        'core_card': core_card,
        'cards': cards,
        'active_nav': 'settings',
    })


# ── AI insights (kept for back-compat with old URL) ──────────────────────────


@staff_member_required
def ai_insights(request: HttpRequest) -> HttpResponse:
    insights: list[Any] = []
    try:
        from plugins.installed.ai_assistant.models import MerchantInsight
        insights = list(MerchantInsight.objects.order_by('-created_at')[:50])
    except Exception:  # noqa: BLE001
        insights = []
    return render(request, 'admin_dashboard/ai_insights.html', {
        'insights': insights,
        'active_nav': 'ai_insights',
    })


# ─── Editable transactional email templates ──────────────────────────────────


_EMAIL_TEMPLATE_KEYS = [
    ('order_placed', 'Order placed', 'Order #{{ order.order_number }} received'),
    ('order_paid', 'Order paid', 'Payment confirmed for order #{{ order.order_number }}'),
    ('order_fulfilled', 'Order fulfilled', 'Order #{{ order.order_number }} is on its way'),
    ('order_cancelled', 'Order cancelled', 'Order #{{ order.order_number }} cancelled'),
    ('refund_issued', 'Refund issued', 'Refund issued for order #{{ order.order_number }}'),
    ('digital_download', 'Digital downloads', 'Your downloads — order #{{ order.order_number }}'),
    ('cart_abandoned', 'Cart abandoned', 'You left items in your cart'),
    ('welcome', 'Welcome', 'Welcome'),
]


def _filesystem_default(key: str) -> str:
    """Read the shipped default body so the editor can show / restore it."""
    from pathlib import Path
    base = Path(__file__).resolve().parent.parent.parent.parent / 'core' / 'emails' / 'templates' / 'emails'
    fp = base / f'{key}.txt'
    try:
        return fp.read_text(encoding='utf-8')
    except OSError:
        return ''


@staff_member_required
def email_templates_list(request: HttpRequest) -> HttpResponse:
    """Show every transactional email template, edited or not."""
    from plugins.installed.cms.models import EmailTemplate

    existing = {t.key: t for t in EmailTemplate.objects.all()}
    rows = []
    for key, label, default_subject in _EMAIL_TEMPLATE_KEYS:
        tpl = existing.get(key)
        rows.append({
            'key': key,
            'label': label,
            'subject': tpl.subject if tpl else default_subject,
            'is_active': tpl.is_active if tpl else False,
            'updated_at': tpl.updated_at if tpl else None,
            'is_customised': tpl is not None,
        })
    return render(request, 'admin_dashboard/email_templates_list.html', {
        'rows': rows,
        'active_nav': 'settings',
    })


@staff_member_required
def email_template_edit(request: HttpRequest, key: str) -> HttpResponse:
    """Edit one template. Reset = delete the row → falls back to filesystem default."""
    from morpheus.views import HttpResponseRedirect

    from plugins.installed.cms.models import EmailTemplate

    label_map = {k: lbl for k, lbl, _ in _EMAIL_TEMPLATE_KEYS}
    default_subject_map = {k: subj for k, _, subj in _EMAIL_TEMPLATE_KEYS}
    if key not in label_map:
        from django.http import Http404
        raise Http404('Unknown template.')

    tpl = EmailTemplate.objects.filter(key=key).first()

    if request.method == 'POST':
        action = request.POST.get('action') or 'save'
        if action == 'reset':
            if tpl:
                tpl.delete()
            return HttpResponseRedirect(request.path)
        subject = (request.POST.get('subject') or '').strip()
        body_text = request.POST.get('body_text') or ''
        body_html = request.POST.get('body_html') or ''
        is_active = request.POST.get('is_active') == 'on'
        EmailTemplate.objects.update_or_create(
            key=key,
            defaults={
                'label': label_map[key],
                'subject': subject or default_subject_map[key],
                'body_text': body_text,
                'body_html': body_html,
                'is_active': is_active,
                'updated_by': request.user if request.user.is_authenticated else None,
            },
        )
        return HttpResponseRedirect('/dashboard/settings/email-templates/')

    return render(request, 'admin_dashboard/email_template_edit.html', {
        'key': key,
        'label': label_map[key],
        'subject': tpl.subject if tpl else default_subject_map[key],
        'body_text': tpl.body_text if tpl else _filesystem_default(key),
        'body_html': tpl.body_html if tpl else '',
        'is_active': tpl.is_active if tpl else True,
        'is_customised': tpl is not None,
        'default_subject': default_subject_map[key],
        'default_body_text': _filesystem_default(key),
        'active_nav': 'settings',
    })


# ─── Returns / RMA ────────────────────────────────────────────────────────────


@staff_member_required
def returns_list(request: HttpRequest) -> HttpResponse:
    from plugins.installed.orders.refunds import ReturnRequest

    state = (request.GET.get('state') or '').strip()
    qs = ReturnRequest.objects.select_related('order', 'order__customer').order_by('-created_at')
    if state:
        qs = qs.filter(state=state)
    rows = list(qs[:200])
    counts = {
        s[0]: ReturnRequest.objects.filter(state=s[0]).count()
        for s in ReturnRequest.STATE_CHOICES
    }
    return render(request, 'admin_dashboard/returns_list.html', {
        'rows': rows,
        'counts': counts,
        'state': state,
        'state_choices': ReturnRequest.STATE_CHOICES,
        'active_nav': 'orders',
    })


@staff_member_required
def return_detail(request: HttpRequest, rma_id) -> HttpResponse:
    from morpheus.views import HttpResponseRedirect

    from plugins.installed.orders.models import OrderItem
    from plugins.installed.orders.refunds import ReturnRequest, ReturnService

    rr = get_object_or_404(
        ReturnRequest.objects.select_related('order', 'order__customer'),
        pk=rma_id,
    )
    error = ''
    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        try:
            if action == 'approve':
                ReturnService.approve(rr, decided_by=request.user)
            elif action == 'reject':
                ReturnService.reject(
                    rr,
                    decided_by=request.user,
                    staff_note=(request.POST.get('staff_note') or '')[:2000],
                )
            elif action == 'refund_money':
                ReturnService.mark_received_and_refund(rr, actor=request.user, as_store_credit=False)
            elif action == 'refund_credit':
                ReturnService.mark_received_and_refund(rr, actor=request.user, as_store_credit=True)
            else:
                error = 'Unknown action.'
        except Exception as e:  # noqa: BLE001
            error = str(e)
        if not error:
            return HttpResponseRedirect(request.path)
        rr.refresh_from_db()

    line_items = []
    items_by_id = {str(oi.id): oi for oi in OrderItem.objects.filter(order=rr.order)}
    for entry in (rr.items or []):
        oi = items_by_id.get(str(entry.get('order_item_id', '')))
        if oi:
            line_items.append({
                'order_item': oi,
                'qty': int(entry.get('quantity', 0) or 0),
            })
    return render(request, 'admin_dashboard/return_detail.html', {
        'rr': rr,
        'line_items': line_items,
        'error': error,
        'active_nav': 'orders',
    })


# ─── Bulk actions on list pages ───────────────────────────────────────────────


def _bulk_ids(request: HttpRequest, field: str = 'ids') -> list[str]:
    """Extract a sanitised list of UUID-like ids from POST.

    Caps at 500 so a runaway script can't ask us to delete 50k rows in
    one shot. Filters empty entries.
    """
    raw = request.POST.getlist(field)
    out = [s.strip() for s in raw if s and s.strip()]
    return out[:500]


@staff_member_required
def orders_bulk(request: HttpRequest) -> HttpResponse:
    """Bulk action endpoint for the orders list page.

    Supported actions: ``mark_paid`` (flip payment_status to paid),
    ``cancel`` (transition to cancelled, fires the cancel hook),
    ``export`` (redirect to the importers/csv export with a pre-filtered
    set — placeholder; falls back to the full export).
    """
    if request.method != 'POST':
        return redirect('admin_dashboard:orders')
    from plugins.installed.orders.models import Order

    action = (request.POST.get('action') or '').strip()
    ids = _bulk_ids(request)
    if not ids:
        messages.warning(request, 'No orders selected.')
        return redirect('admin_dashboard:orders')

    qs = Order.objects.filter(pk__in=ids)
    count = qs.count()
    if count == 0:
        messages.warning(request, 'No matching orders found.')
        return redirect('admin_dashboard:orders')

    if action == 'mark_paid':
        qs.update(payment_status='paid')
        messages.success(request, f'Marked {count} order(s) as paid.')
    elif action == 'cancel':
        # Transition each order — FSM is per-instance so we loop.
        ok = 0
        for o in qs:
            try:
                o.status = 'cancelled'
                o.save(update_fields=['status'])
                ok += 1
            except Exception:  # noqa: BLE001
                continue
        messages.success(request, f'Cancelled {ok} order(s).')
    elif action == 'export':
        return redirect('/dashboard/apps/importers/csv/')
    else:
        messages.warning(request, f'Unknown action: {action!r}.')
    return redirect('admin_dashboard:orders')


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


@staff_member_required
def customers_bulk(request: HttpRequest) -> HttpResponse:
    """Bulk action endpoint for the customers list page.

    Supported: ``mark_marketing_yes`` / ``mark_marketing_no`` (toggle
    accepts_marketing), ``delete`` (hard delete — guarded by the modal).
    """
    if request.method != 'POST':
        return redirect('admin_dashboard:customers')
    from django.contrib.auth import get_user_model

    User = get_user_model()
    action = (request.POST.get('action') or '').strip()
    ids = _bulk_ids(request)
    if not ids:
        messages.warning(request, 'No customers selected.')
        return redirect('admin_dashboard:customers')

    qs = User.objects.filter(pk__in=ids)
    count = qs.count()
    if count == 0:
        messages.warning(request, 'No matching customers found.')
        return redirect('admin_dashboard:customers')

    if action == 'mark_marketing_yes':
        qs.update(accepts_marketing=True)
        messages.success(request, f'{count} customer(s) opted in to marketing.')
    elif action == 'mark_marketing_no':
        qs.update(accepts_marketing=False)
        messages.success(request, f'{count} customer(s) opted out of marketing.')
    elif action == 'delete':
        qs.delete()
        messages.success(request, f'Deleted {count} customer(s).')
    else:
        messages.warning(request, f'Unknown action: {action!r}.')
    return redirect('admin_dashboard:customers')
