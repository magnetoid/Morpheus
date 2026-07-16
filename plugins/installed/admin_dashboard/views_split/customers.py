"""Auto-split from the legacy admin_dashboard/views.py monolith."""

# ruff: noqa: PLC0415, S110, SIM105
# PLC0415: inline imports are used throughout these views to avoid
# app-registry-not-ready issues + keep optional-plugin imports lazy.
# S110/SIM105: the bare try/except/pass guards are deliberate fail-soft
# enrichment — the page must render even when an optional model is absent.
from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Sum

from morpheus.views import (
    HttpRequest,
    HttpResponse,
    get_object_or_404,
    messages,
    redirect,
    render,
    staff_member_required,
)
from plugins.installed.admin_dashboard.forms import AddressForm, CustomerForm
from plugins.installed.admin_dashboard.views_split._shared import (
    _bulk_ids,
    ajax_form_errors,
    ajax_or_redirect,
    paginate_and_sort,
)

CUSTOMER_SOURCE_CHOICES = (
    ('', 'All'),
    ('order', 'Customers'),
    ('lead_form', 'Leads'),
    ('signup', 'Signups'),
    ('newsletter', 'Newsletter'),
)


@staff_member_required
def customers_list(request: HttpRequest) -> HttpResponse:
    """Unified Contacts list — customers, leads, signups in one table.

    `source` filter narrows by where the contact arrived from (orders,
    lead form, signup, newsletter, …). The view name + URL stay
    `customers` for stability; the page label is "Contacts".
    """
    search = request.GET.get('q', '').strip()[:80]
    source_filter = request.GET.get('source', '').strip()[:20]
    admin_filter = request.GET.get('admin') == '1'
    customers: list[Any] = []
    source_counts: dict[str, int] = {}
    admin_count = 0
    paging_ctx: dict[str, Any] = {}
    try:
        from django.contrib.auth import get_user_model
        from django.db.models import Count, Q

        from plugins.installed.orders.models import Order

        User = get_user_model()
        unfiltered = User.objects.all()
        if search:
            unfiltered = unfiltered.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        source_counts = {
            (row['source'] or ''): row['c']
            for row in unfiltered.values('source').annotate(c=Count('id'))
        }
        admin_count = unfiltered.filter(is_staff=True).count()
        qs = User.objects.all()
        if search:
            qs = qs.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        if source_filter:
            qs = qs.filter(source=source_filter)
        if admin_filter:
            qs = qs.filter(is_staff=True)
        # Paginate first, then enrich the page's rows. This keeps the
        # Python loop over a bounded slice no matter how many users exist.
        page_obj, paging_ctx = paginate_and_sort(
            request,
            qs,
            default_sort='-date_joined',
            allowed_sorts=(
                'email',
                'date_joined',
                'last_order_at',
                'lifetime_value',
                'purchase_count',
            ),
        )
        rows = []
        for user in page_obj.object_list:
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
            rows.append(
                {
                    'id': user.pk,
                    'email': getattr(user, 'email', ''),
                    'name': (
                        (
                            getattr(user, 'first_name', '') + ' ' + getattr(user, 'last_name', '')
                        ).strip()
                        or '—'
                    ),
                    'source': source,
                    'source_display': (
                        user.get_source_display()
                        if hasattr(user, 'get_source_display') and source
                        else ''
                    ),
                    'order_count': order_count,
                    'spent': spent,
                    'last_order_at': getattr(user, 'last_order_at', None),
                    'date_joined': getattr(user, 'date_joined', None),
                }
            )
        customers = rows
    except Exception:  # noqa: BLE001
        customers = []
    source_tabs = [
        {
            'value': value,
            'label': label,
            'count': (source_counts.get(value, 0) if value else sum(source_counts.values())),
            'active': not admin_filter and source_filter == value,
        }
        for value, label in CUSTOMER_SOURCE_CHOICES
    ]
    return render(
        request,
        'admin_dashboard/customers.html',
        {
            'customers': customers,
            'search': search,
            'source_filter': source_filter,
            'source_choices': CUSTOMER_SOURCE_CHOICES,
            'source_counts': source_counts,
            'source_tabs': source_tabs,
            'admin_filter': admin_filter,
            'admin_count': admin_count,
            'active_nav': 'admins' if admin_filter else 'customers',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Users'},
            ],
            **paging_ctx,
        },
    )


@staff_member_required
def customer_new(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f'Customer "{customer.email}" created.')
            return ajax_or_redirect(
                request, 'admin_dashboard:customer_edit', customer_id=customer.id, follow=True
            )
        if (error_response := ajax_form_errors(request, form)) is not None:
            return error_response
    else:
        form = CustomerForm()
    return render(
        request,
        'admin_dashboard/customer_form.html',
        {
            'form': form,
            'customer': None,
            'active_nav': 'customers',
        },
    )


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
            return ajax_or_redirect(
                request, 'admin_dashboard:customer_edit', customer_id=customer.id
            )
        if (error_response := ajax_form_errors(request, form)) is not None:
            return error_response
    else:
        form = CustomerForm(instance=customer)
    # Quick stats so the edit page also works as a customer profile.
    order_summary: dict[str, Any] = {'count': 0, 'spent': Decimal('0'), 'recent': []}
    try:
        from plugins.installed.orders.models import Order

        orders_qs = Order.objects.filter(customer=customer)
        order_summary['count'] = orders_qs.count()
        order_summary['spent'] = orders_qs.aggregate(t=Sum('total'))['t'] or Decimal('0')
        order_summary['recent'] = list(orders_qs.order_by('-placed_at')[:5])
    except Exception:  # noqa: BLE001
        pass
    addresses: list[Any] = []
    try:
        addresses = list(customer.addresses.all())
    except Exception:  # noqa: BLE001 — customer model may not have addresses
        pass
    # Plugin-contributed panels (CUSTOMER_DETAIL_PANELS filter). Each
    # subscriber appends a {'label', 'html', 'priority'} dict; a disabled
    # plugin contributes nothing, so its panel vanishes. admin_dashboard
    # exposes the slot only — it has zero vendor/affiliate-specific logic.
    # The hook bus isolates a broken handler so one bad panel can't break
    # this page.
    detail_panels: list[dict[str, Any]] = []
    try:
        from core.hooks import MorpheusEvents, hook_registry

        panels = hook_registry.filter(
            MorpheusEvents.CUSTOMER_DETAIL_PANELS, [], customer=customer, request=request
        )
        detail_panels = sorted(
            (p for p in panels if isinstance(p, dict)),
            key=lambda p: p.get('priority', 50),
        )
    except Exception:  # noqa: BLE001 — never break the customer page over a panel
        detail_panels = []
    return render(
        request,
        'admin_dashboard/customer_form.html',
        {
            'form': form,
            'customer': customer,
            'order_summary': order_summary,
            'addresses': addresses,
            'customer_detail_panels': detail_panels,
            'active_nav': 'customers',
        },
    )


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
            return ajax_or_redirect(
                request, 'admin_dashboard:customer_edit', customer_id=customer.id
            )
        if (error_response := ajax_form_errors(request, form)) is not None:
            return error_response
    else:
        form = AddressForm(customer=customer)
    return render(
        request,
        'admin_dashboard/address_form.html',
        {
            'form': form,
            'customer': customer,
            'address': None,
            'active_nav': 'customers',
        },
    )


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
            return ajax_or_redirect(
                request, 'admin_dashboard:customer_edit', customer_id=customer.id
            )
        if (error_response := ajax_form_errors(request, form)) is not None:
            return error_response
    else:
        form = AddressForm(instance=address, customer=customer)
    return render(
        request,
        'admin_dashboard/address_form.html',
        {
            'form': form,
            'customer': customer,
            'address': address,
            'active_nav': 'customers',
        },
    )


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


# ─── Cmd+K command palette ────────────────────────────────────────────────────
