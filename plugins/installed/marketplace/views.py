"""Storefront-side vendor flows, rendered in the shared partner-portal shell
(``plugins.partner_portal``; the numbers live in ``portal.py``).

Views:
  - `apply`              /vendor/apply/                         — submit application.
  - `dashboard`          /vendor/me/                            — period KPIs, orders to send, stock.
  - `vendor_orders`      /vendor/me/orders/                     — every order slice + CSV.
  - `vendor_order_detail`/vendor/me/orders/<vendor_order_id>/   — update status + tracking.
  - `vendor_products`    /vendor/me/products/                   — catalogue with stock.
  - `vendor_product_edit`/vendor/me/products/<id>/              — edit one product.
  - `vendor_payouts`     /vendor/me/payouts/                    — balance + request payout.
  - `vendor_settings`    /vendor/me/settings/                   — profile + payout method.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext
from django.views.decorators.http import require_http_methods
from djmoney.money import Money

from morpheus.app.views import HttpRequest, HttpResponse
from plugins import partner_portal as pp
from plugins.dropshipping.countries import country_name
from plugins.installed.catalog.models import Product, Vendor
from plugins.installed.marketplace import portal, services
from plugins.installed.marketplace.models import (
    VendorApplication,
    VendorOrder,
    VendorPayout,
    VendorPayoutAccount,
)


@login_required(login_url='/auth/login/')
@require_http_methods(['GET', 'POST'])
def apply(request: HttpRequest) -> HttpResponse:
    """Vendor application form. Creates a `submitted` VendorApplication."""
    existing = VendorApplication.objects.filter(user=request.user).order_by('-submitted_at').first()
    noun, plural = portal.vendor_noun()
    context = {
        'existing': existing,
        'vendor_noun': noun,
        'vendor_noun_plural': plural,
        'payout_methods': portal.PAYOUT_METHODS,
        'seo_title': gettext('Sell with us'),
        'seo_description': gettext(
            'Apply to sell your products through this store. We read every application.'
        ),
    }

    if request.method == 'POST' and (existing is None or existing.status == 'rejected'):
        business_name = (request.POST.get('business_name') or '').strip()[:200]
        contact_email = (request.POST.get('contact_email') or request.user.email).strip()[:254]
        description = (request.POST.get('description') or '').strip()[:5000]
        tax_id = (request.POST.get('tax_id') or '').strip()[:50]
        payout_method = (request.POST.get('payout_method') or '').strip()[:40]

        if not business_name:
            context['error'] = gettext('Business name is required.')
            return render(request, 'marketplace/vendor_apply.html', context)

        VendorApplication.objects.create(
            user=request.user,
            business_name=business_name,
            contact_email=contact_email,
            description=description,
            tax_id=tax_id,
            payout_method=payout_method,
        )
        return redirect('/vendor/me/')

    return render(request, 'marketplace/vendor_apply.html', context)


def _resolve_vendor(user):
    """Return the active catalog.Vendor owned by `user`, or None.

    Used by every self-service view to gate access — vendors can only
    see/edit their own data. The link is via catalog.Vendor.owner
    (FK to Customer), which the dashboard sets when it approves an
    application or switches a customer on as a vendor.
    """
    return Vendor.objects.filter(owner=user, is_active=True).first()


def _shell(request, vendor, active: str, title: str, application=None, **extra) -> dict:
    if application is None:
        application = (
            VendorApplication.objects.filter(user=request.user).order_by('-submitted_at').first()
        )
    context = portal.shell(request.user, vendor, application, active=active, title=title)
    context.update(extra)
    return context


def _account(vendor):
    acct, _created = VendorPayoutAccount.objects.get_or_create(
        vendor=vendor,
        defaults={'method': 'unset'},
    )
    return acct


@login_required(login_url='/auth/login/')
def dashboard(request: HttpRequest) -> HttpResponse:
    """The vendor's overview — or, before there is a shop, where the
    application stands. A vendor the merchant switched on from the customer
    page has no application, so the shop is found by owner, never by an
    approved application."""
    vendor, application = portal.resolve(request.user)
    noun = portal.vendor_noun()[0]
    title = gettext('%(noun)s dashboard') % {'noun': noun}
    if vendor is None or not vendor.is_active:
        return render(
            request,
            'marketplace/vendor_dashboard.html',
            _shell(request, vendor, 'overview', title, application=application),
        )

    period = pp.period_from(request)
    acct = _account(vendor)
    open_qs = portal.open_orders(vendor)
    context = _shell(
        request,
        vendor,
        'overview',
        title,
        application=application,
        period=period,
        periods=pp.period_links(period),
        to_fulfil=portal.decorate(open_qs[:6]),
        to_fulfil_count=open_qs.count(),
        recent=portal.decorate(
            VendorOrder.objects.filter(vendor=vendor)
            .select_related('parent_order')
            .order_by('-created_at')[:6]
        ),
        best_sellers=portal.best_sellers(vendor, period),
        stock=portal.stock_status(vendor),
        balance=portal.balance(vendor, acct),
        active_products=Product.objects.filter(vendor=vendor, status='active').count(),
    )
    context.update(portal.performance(vendor, period))
    return render(request, 'marketplace/vendor_dashboard.html', context)


_ORDER_TABS = {
    'open': ('pending', 'confirmed'),
    'shipped': ('shipped',),
    'delivered': ('delivered',),
    'closed': ('cancelled', 'refunded'),
}


@login_required(login_url='/auth/login/')
def vendor_orders(request: HttpRequest) -> HttpResponse:
    """Every slice of an order that is this vendor's to send, newest first, with
    the ones still to send one tab away; CSV of the money columns."""
    from django.core.paginator import Paginator
    from django.db.models import Q

    vendor = _resolve_vendor(request.user)
    if vendor is None:
        return redirect('/vendor/me/')

    tab = (request.GET.get('status') or '').strip()
    if tab not in _ORDER_TABS:
        tab = ''
    base = VendorOrder.objects.filter(vendor=vendor).select_related('parent_order')
    void = Q(parent_order__status__in=portal.VOID_PARENT)

    def in_tab(qs, key):
        if key == 'open':
            return qs.filter(status__in=_ORDER_TABS['open']).exclude(void)
        if key == 'closed':
            return qs.filter(Q(status__in=_ORDER_TABS['closed']) | void)
        if key:
            return qs.filter(status__in=_ORDER_TABS[key]).exclude(void)
        return qs

    # Orders to send read oldest first (the one waiting longest on top).
    qs = in_tab(base, tab).order_by('created_at' if tab == 'open' else '-created_at')

    if request.GET.get('export') == 'csv':
        import csv
        from io import StringIO

        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            ['date', 'order_number', 'status', 'gross', 'commission', 'net', 'tracking_number']
        )
        for vo in qs[:5000]:
            writer.writerow(
                [
                    vo.created_at.isoformat(),
                    vo.parent_order.order_number,
                    portal.display_state(vo),
                    str(vo.gross.amount),
                    str(vo.commission.amount),
                    str(vo.net.amount),
                    vo.tracking_number,
                ]
            )
        response = HttpResponse(buf.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="orders-{vendor.slug}.csv"'
        return response

    page = Paginator(qs, 40).get_page(request.GET.get('page'))
    counts = {key: in_tab(base, key).count() for key in _ORDER_TABS}
    counts['all'] = base.count()
    return render(
        request,
        'marketplace/vendor_orders.html',
        _shell(
            request,
            vendor,
            'orders',
            gettext('Your orders'),
            orders=portal.decorate(page.object_list),
            page_obj=page,
            tab=tab,
            counts=counts,
        ),
    )


@login_required(login_url='/auth/login/')
def vendor_products(request: HttpRequest) -> HttpResponse:
    """The signed-in vendor's products with status, price, stock and recent sales."""
    from django.db.models import Q

    vendor = _resolve_vendor(request.user)
    if vendor is None:
        return render(
            request,
            'marketplace/vendor_products.html',
            _shell(request, None, 'products', gettext('Your products'), products=[]),
        )

    q = (request.GET.get('q') or '').strip()
    view = (request.GET.get('view') or '').strip()
    base = Product.objects.filter(vendor=vendor)
    qs = base.prefetch_related('images')
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q))
    if view in ('active', 'draft', 'archived'):
        qs = qs.filter(status=view)
    rows = portal.decorate_products(vendor, qs.order_by('-updated_at')[:200])
    stock = portal.stock_status(vendor)
    if view == 'attention':
        flagged = {p.pk for p in stock['attention']}
        rows = [p for p in rows if p.pk in flagged]
    counts = {
        'all': base.count(),
        'active': base.filter(status='active').count(),
        'draft': base.filter(status='draft').count(),
        'archived': base.filter(status='archived').count(),
        'attention': len(stock['attention']),
    }
    return render(
        request,
        'marketplace/vendor_products.html',
        _shell(
            request,
            vendor,
            'products',
            gettext('Your products'),
            products=rows,
            q=q,
            view=view,
            counts=counts,
            stock_known=stock['tracked'] > 0,
        ),
    )


@login_required(login_url='/auth/login/')
@require_http_methods(['GET', 'POST'])
def vendor_product_edit(request: HttpRequest, product_id) -> HttpResponse:
    """Edit one of the signed-in vendor's products. The product must
    belong to the resolved vendor — we don't trust the URL; we double-
    check ownership server-side.

    Minimal field set (name / short / long / price / status). Vendors
    don't get to set vendor_id (they ARE the vendor), digital_file
    (security boundary), or featured (the platform's choice).
    """
    vendor = _resolve_vendor(request.user)
    if vendor is None:
        return HttpResponse(status=403, content='Not an approved vendor.')

    product = Product.objects.filter(pk=product_id, vendor=vendor).first()
    if product is None:
        return HttpResponse(status=404, content='Product not found.')

    error = ''
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()[:300]
        short = (request.POST.get('short_description') or '').strip()
        long_desc = (request.POST.get('description') or '').strip()
        status = (request.POST.get('status') or '').strip()
        raw_price = (request.POST.get('price') or '').strip()

        if not name:
            error = 'A name is required.'
        if status not in ('draft', 'active', 'archived'):
            status = product.status

        if not error and raw_price:
            try:
                amt = Decimal(raw_price)
                if amt < 0:
                    raise InvalidOperation()
                currency = product.price.currency if product.price else 'USD'
                product.price = Money(amt, currency)
            except (InvalidOperation, TypeError):
                error = 'Price must be a non-negative number.'

        if not error:
            product.name = name
            product.short_description = short
            product.description = long_desc
            product.status = status
            product.save(
                update_fields=[
                    'name',
                    'short_description',
                    'description',
                    'status',
                    'price',
                    'price_currency',
                    'updated_at',
                ]
            )
            messages.success(request, gettext('Saved.'))
            return redirect('marketplace:vendor_products')

    stock = portal.stock_for([product.pk]).get(str(product.pk))
    return render(
        request,
        'marketplace/vendor_product_edit.html',
        _shell(
            request,
            vendor,
            'products',
            gettext('Edit %(name)s') % {'name': product.name},
            product=product,
            stock=stock,
            error=error,
        ),
    )


# --------------------------------------------------------------------------
# Vendor self-service: order detail + tracking
# --------------------------------------------------------------------------


def _safe_next(request, default: str) -> str:
    nxt = request.POST.get('next') or ''
    if nxt.startswith('/vendor/me/') and '//' not in nxt:
        return nxt
    return default


def _update_vendor_order(request, vendor_order) -> str:
    """Apply a vendor's status/tracking update; return an error message or ''."""
    mapped = portal.VENDOR_STATUSES.get((request.POST.get('status') or '').strip().lower())
    if mapped is None:
        # "refunded" and "pending" are the store's to set, never the vendor's.
        return gettext('Unknown status.')
    if vendor_order.status == 'refunded':
        return gettext('This order was refunded by the store.')

    tracking_number = (request.POST.get('tracking_number') or '').strip()[:200]
    tracking_url = (request.POST.get('tracking_url') or '').strip()[:500]
    if tracking_url:
        # Rendered as a link on the portal: a javascript: URL would be a script.
        try:
            URLValidator(schemes=['http', 'https'])(tracking_url)
        except ValidationError:
            return gettext('The tracking link must be a web address starting with https://')

    vendor_order.status = mapped
    vendor_order.tracking_number = tracking_number
    vendor_order.tracking_url = tracking_url
    if mapped in ('shipped', 'delivered') and vendor_order.fulfilled_at is None:
        vendor_order.fulfilled_at = timezone.now()
    vendor_order.save(
        update_fields=['status', 'tracking_number', 'tracking_url', 'fulfilled_at', 'updated_at']
    )
    return ''


def _order_lines(vendor_order) -> list[dict]:
    """The slice's items with unit and line totals, from the order snapshot."""
    items = vendor_order.items_snapshot if isinstance(vendor_order.items_snapshot, list) else []
    lines = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            unit = Decimal(str(item.get('unit_price') or 0))
        except (InvalidOperation, TypeError):
            unit = Decimal('0')
        quantity = portal._int(item.get('quantity'))
        currency = item.get('currency') or str(vendor_order.gross.currency)
        lines.append(
            {
                'name': item.get('name') or '—',
                'sku': item.get('sku') or '',
                'quantity': quantity,
                'unit': Money(unit, currency),
                'total': Money(unit * quantity, currency),
            }
        )
    return lines


@login_required(login_url='/auth/login/')
@require_http_methods(['GET', 'POST'])
def vendor_order_detail(request: HttpRequest, vendor_order_id) -> HttpResponse:
    """Per-vendor order detail. Update status + tracking from one screen."""
    vendor = _resolve_vendor(request.user)
    if vendor is None:
        return HttpResponse(status=404, content='Not found.')

    vendor_order = (
        VendorOrder.objects.select_related('parent_order', 'vendor')
        .filter(pk=vendor_order_id, vendor=vendor)
        .first()
    )
    if vendor_order is None:
        return HttpResponse(status=404, content='Not found.')

    if request.method == 'POST':
        error = _update_vendor_order(request, vendor_order)
        if error:
            messages.error(request, error)
        else:
            messages.success(
                request,
                gettext('Order %(number)s updated.')
                % {'number': vendor_order.parent_order.order_number},
            )
        return redirect(_safe_next(request, f'/vendor/me/orders/{vendor_order.pk}/'))

    parent = vendor_order.parent_order
    row = portal.decorate([vendor_order])[0]
    return render(
        request,
        'marketplace/vendor_order_detail.html',
        _shell(
            request,
            vendor,
            'orders',
            gettext('Order %(number)s') % {'number': parent.order_number},
            vendor_order=row,
            parent_order_number=parent.order_number,
            shipping_address=parent.shipping_address or {},
            ship_country=country_name((parent.shipping_address or {}).get('country')),
            lines=_order_lines(vendor_order),
            status_choices=[
                ('confirmed', gettext('Preparing')),
                ('shipped', gettext('Shipped')),
                ('delivered', gettext('Delivered')),
                ('cancelled', gettext('Cancelled')),
            ],
        ),
    )


# --------------------------------------------------------------------------
# Vendor self-service: payouts
# --------------------------------------------------------------------------


@login_required(login_url='/auth/login/')
@require_http_methods(['GET', 'POST'])
def vendor_payouts(request: HttpRequest) -> HttpResponse:
    """Balance, progress to the payout minimum, the request button and history."""
    vendor = _resolve_vendor(request.user)
    if vendor is None:
        return redirect('/vendor/me/')

    acct = _account(vendor)
    state = portal.balance(vendor, acct)

    if request.method == 'POST':
        if state['blocker'] == 'method':
            messages.error(request, gettext('Set a payout method in settings first.'))
        elif state['blocker'] == 'open':
            messages.error(request, gettext('A payout request is already being processed.'))
        elif state['blocker'] == 'threshold':
            messages.error(
                request,
                gettext('Your balance is below the %(threshold)s minimum.')
                % {'threshold': portal.money_text(state['threshold'])},
            )
        else:
            try:
                services.request_vendor_payout(
                    vendor=vendor,
                    amount=acct.accrued_balance,
                    method=acct.method,
                )
                messages.success(
                    request,
                    gettext(
                        'Payout requested. The store team processes it and marks it paid here.'
                    ),
                )
            except ValueError as exc:
                messages.error(request, str(exc))
        return redirect('marketplace:vendor_payouts')

    history = list(VendorPayout.objects.filter(vendor=vendor).order_by('-requested_at')[:50])
    labels = dict(portal.PAYOUT_METHODS)
    for p in history:
        p.method_label = labels.get(p.method, p.method)

    return render(
        request,
        'marketplace/vendor_payouts.html',
        _shell(
            request,
            vendor,
            'payouts',
            gettext('Payouts'),
            account=acct,
            balance=state,
            history=history,
        ),
    )


# --------------------------------------------------------------------------
# Vendor self-service: settings
# --------------------------------------------------------------------------


@login_required(login_url='/auth/login/')
@require_http_methods(['GET', 'POST'])
def vendor_settings(request: HttpRequest) -> HttpResponse:
    """Edit vendor profile + payout account from the storefront."""
    vendor = _resolve_vendor(request.user)
    if vendor is None:
        return redirect('/vendor/me/')

    acct = _account(vendor)
    application = (
        VendorApplication.objects.filter(user=request.user).order_by('-submitted_at').first()
    )

    error = ''
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()[:200]
        description = (request.POST.get('description') or '').strip()[:5000]
        contact_email = (request.POST.get('contact_email') or '').strip()[:254]
        method = (request.POST.get('payout_method') or '').strip()[:40]
        external_account = (request.POST.get('external_account') or '').strip()[:200]

        if not name:
            error = gettext('A name is required.')
        elif method and method not in dict(portal.PAYOUT_METHODS):
            error = gettext('Pick a payout method from the list.')

        if not error:
            vendor.name = name
            vendor.description = description
            vendor.save(update_fields=['name', 'description'])

            # catalog.Vendor has no email field of its own: the contact
            # address lives on the latest application, when there is one.
            if application and contact_email:
                application.contact_email = contact_email
                application.save(update_fields=['contact_email'])

            acct.method = method or acct.method
            acct.external_account = external_account
            acct.save(update_fields=['method', 'external_account', 'updated_at'])

            messages.success(request, gettext('Settings saved.'))
            return redirect('marketplace:vendor_settings')

    return render(
        request,
        'marketplace/vendor_settings.html',
        _shell(
            request,
            vendor,
            'settings',
            gettext('Settings'),
            application=application,
            account=acct,
            contact_email=application.contact_email if application else '',
            error=error,
            payout_methods=portal.PAYOUT_METHODS,
        ),
    )
