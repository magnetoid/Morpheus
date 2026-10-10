"""What the vendor portal shows, computed from the rows that record it.

Sales and earnings are summed from ``VendorOrder`` rows (gross, net) that still
count — not cancelled or refunded, and not part of an order the store
cancelled. Stock comes from the inventory app through the
``PRODUCT_STOCK_SUMMARY`` filter (marketplace does not import inventory); with
inventory off the portal simply shows no stock.

The shell (identity header + tabs) comes from ``plugins.partner_portal``; this
module supplies the vendor's navigation and numbers. What the store calls its
vendors is the theme's word (``MorpheusTheme.vendor_noun``): a supplier on one
store, a maker on another — the portal never hardcodes one.
"""
# ruff: noqa: PLC0415  — inline imports keep cross-plugin reads lazy (house style).

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils.dateformat import format as date_format
from django.utils.formats import number_format
from django.utils.translation import gettext as _
from djmoney.money import Money

from plugins import partner_portal as pp
from plugins.dropshipping.countries import country_name

# A vendor slice still to be sent, and the slices that count as a sale.
OPEN = ('pending', 'confirmed')
SOLD = ('pending', 'confirmed', 'shipped', 'delivered')
# A parent order in one of these states voids every slice of it.
VOID_PARENT = ('cancelled', 'refunded')

# Statuses a vendor may set from the portal, with the legacy form words. Refunds
# and the initial "pending" belong to the store, not the vendor.
VENDOR_STATUSES = {
    'confirmed': 'confirmed',
    'preparing': 'confirmed',
    'packed': 'confirmed',
    'shipped': 'shipped',
    'delivered': 'delivered',
    'cancelled': 'cancelled',
}

PAYOUT_METHODS = [
    ('stripe', 'Stripe Connect'),
    ('bank_transfer', 'Bank transfer (SEPA / wire)'),
    ('paypal', 'PayPal'),
    ('other', 'Other'),
]


def vendor_noun() -> tuple[str, str]:
    """``(singular, plural)``: what this store calls its vendors, from the theme
    (read the same way as storefront's ``vendor_nouns``)."""
    from themes.registry import theme_registry

    theme = theme_registry.active
    single = getattr(theme, 'vendor_noun', '') or 'Seller'
    plural = getattr(theme, 'vendor_noun_plural', '') or 'Sellers'
    return _(single), _(plural)


def resolve(user):
    """``(vendor, application)`` for ``user``: the vendor they own (an active one
    first) and their latest application — either may be ``None``. A vendor the
    merchant switched on from the customer page has no application at all."""
    from plugins.installed.catalog.models import Vendor
    from plugins.installed.marketplace.models import VendorApplication

    vendor = Vendor.objects.filter(owner=user).order_by('-is_active', 'created_at').first()
    application = VendorApplication.objects.filter(user=user).order_by('-submitted_at').first()
    return vendor, application


def status_of(vendor, application) -> dict | None:
    if vendor is not None:
        if vendor.is_active:
            return {'key': 'active', 'label': _('Active'), 'tone': 'ok'}
        return {'key': 'paused', 'label': _('Paused'), 'tone': 'bad'}
    if application is None:
        return None
    return {
        'submitted': {'key': 'submitted', 'label': _('Application received'), 'tone': 'wait'},
        'reviewing': {'key': 'reviewing', 'label': _('In review'), 'tone': 'wait'},
        'approved': {'key': 'approved', 'label': _('Being set up'), 'tone': 'wait'},
        'rejected': {'key': 'rejected', 'label': _('Not approved'), 'tone': 'bad'},
    }.get(
        application.status,
        {'key': application.status, 'label': application.status, 'tone': 'neutral'},
    )


# ── Orders ───────────────────────────────────────────────────────────────


def sold_orders(vendor):
    from plugins.installed.marketplace.models import VendorOrder

    return VendorOrder.objects.filter(vendor=vendor, status__in=SOLD).exclude(
        parent_order__status__in=VOID_PARENT
    )


def open_orders(vendor):
    """Slices still to be sent, oldest first."""
    from plugins.installed.marketplace.models import VendorOrder

    return (
        VendorOrder.objects.filter(vendor=vendor, status__in=OPEN)
        .exclude(parent_order__status__in=VOID_PARENT)
        .select_related('parent_order')
        .order_by('created_at')
    )


def payment_state(order) -> str:
    """paid · cod (paid to the courier on delivery, so ship it) · awaiting."""
    if order.payment_status == 'paid':
        return 'paid'
    if order.payment_gateway == 'cod':
        return 'cod'
    return 'awaiting'


def display_state(vendor_order) -> str:
    """The slice's status as the vendor should read it: a store-cancelled order
    reads cancelled whatever the slice says."""
    if vendor_order.parent_order.status in VOID_PARENT and vendor_order.status in SOLD:
        return 'cancelled'
    return vendor_order.status


def decorate(vendor_orders) -> list:
    """Attach what a row needs: payment state, display state, item count, ship-to."""
    from django.utils import timezone

    now = timezone.now()
    rows = list(vendor_orders)
    for vo in rows:
        parent = vo.parent_order
        vo.payment = payment_state(parent)
        vo.state = display_state(vo)
        items = vo.items_snapshot if isinstance(vo.items_snapshot, list) else []
        vo.units = sum(_int(i.get('quantity')) for i in items if isinstance(i, dict))
        vo.first_item = next((i.get('name') for i in items if isinstance(i, dict)), '')
        vo.extra_items = max(0, len(items) - 1)
        address = parent.shipping_address if isinstance(parent.shipping_address, dict) else {}
        place = (address.get('city'), country_name(address.get('country')))
        vo.ship_to = ', '.join(p for p in place if p)
        vo.waiting_days = (now - vo.created_at).days
        vo.ready = vo.payment in ('paid', 'cod')
    return rows


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


# ── Money ────────────────────────────────────────────────────────────────


def _amount(value) -> Decimal:
    return Decimal(str(getattr(value, 'amount', value) or 0))


def _sum(qs, field: str) -> Decimal:
    return _amount(qs.aggregate(t=Sum(field))['t'])


def currency_of(vendor) -> str:
    from plugins.installed.marketplace.models import VendorOrder, VendorPayoutAccount

    latest = (
        VendorOrder.objects.filter(vendor=vendor)
        .order_by('-created_at')
        .values_list('gross_currency', flat=True)
        .first()
    )
    if latest:
        return str(latest)
    acct = VendorPayoutAccount.objects.filter(vendor=vendor).first()
    return str(acct.accrued_balance.currency) if acct else 'USD'


def money_text(value) -> str:
    from core.templatetags.morph import money_filter

    return money_filter(value)


def payout_threshold() -> Decimal:
    from plugins.registry import app_registry

    plugin = app_registry.get('marketplace')
    raw = plugin.get_config_value('min_payout_threshold', 50) if plugin else 50
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError):
        return Decimal('50')


def balance(vendor, account) -> dict:
    """The vendor's balance with the store and whether a payout can be asked for."""
    from plugins.installed.marketplace.models import VendorPayout
    from plugins.installed.marketplace.services import OPEN_PAYOUT_STATUSES

    currency = str(account.accrued_balance.currency)
    available = _amount(account.accrued_balance)
    threshold = payout_threshold()
    payouts = VendorPayout.objects.filter(vendor=vendor)
    open_qs = payouts.filter(status__in=OPEN_PAYOUT_STATUSES)
    open_payout = open_qs.order_by('-requested_at').first()
    method_set = account.method not in ('', 'unset')
    if threshold > 0:
        progress = min(Decimal('100'), max(available, Decimal('0')) * 100 / threshold)
    else:
        progress = Decimal('100') if available > 0 else Decimal('0')
    reached = available > 0 and available >= threshold
    if open_payout is not None:
        blocker = 'open'
    elif not method_set:
        blocker = 'method'
    elif not reached:
        blocker = 'threshold'
    else:
        blocker = ''
    return {
        'available': Money(available, currency),
        'threshold': Money(threshold, currency),
        'remaining': Money(max(threshold - available, Decimal('0')), currency),
        'progress': f'{progress:.0f}',
        'reached': reached,
        'in_flight': Money(_sum(open_qs, 'amount'), currency),
        'paid': Money(_sum(payouts.filter(status='paid'), 'amount'), currency),
        'open_payout': open_payout,
        'method_set': method_set,
        'method_label': dict(PAYOUT_METHODS).get(account.method, ''),
        'blocker': blocker,
        'can_request': not blocker,
    }


# ── Period figures ───────────────────────────────────────────────────────


def _daily(qs, value) -> list[tuple]:
    return list(
        qs.annotate(d=TruncDate('created_at')).values('d').annotate(v=value).values_list('d', 'v')
    )


def performance(vendor, period: pp.Period) -> dict:
    """KPI tiles and the sales chart for ``period``."""
    currency = currency_of(vendor)
    sold = sold_orders(vendor)
    now = sold.filter(created_at__gte=period.start)
    prev = sold.filter(created_at__gte=period.prev_start, created_at__lt=period.start)

    g_now, g_prev = _sum(now, 'gross'), _sum(prev, 'gross')
    n_now, n_prev = _sum(now, 'net'), _sum(prev, 'net')
    c_now, c_prev = now.count(), prev.count()
    a_now = g_now / c_now if c_now else Decimal('0')
    a_prev = g_prev / c_prev if c_prev else Decimal('0')

    daily_gross = [_amount(v) for v in pp.daily(_daily(now, Sum('gross')), period)]
    daily_net = [_amount(v) for v in pp.daily(_daily(now, Sum('net')), period)]
    daily_count = pp.daily(_daily(now, Count('id')), period)
    compare = _('vs previous %(days)s days') % {'days': period.days}

    def fmt(v):
        return money_text(Money(v, currency))

    kpis = [
        {
            'key': 'sales',
            'label': _('Sales'),
            'value': fmt(g_now),
            'delta': pp.change(g_now, g_prev),
            'compare': compare,
            'spark': pp.sparkline(daily_gross),
        },
        {
            'key': 'earnings',
            'label': _('Your earnings'),
            'value': fmt(n_now),
            'delta': pp.change(n_now, n_prev),
            'compare': compare,
            'spark': pp.sparkline(daily_net),
        },
        {
            'key': 'orders',
            'label': _('Orders'),
            'value': number_format(c_now, force_grouping=True),
            'delta': pp.change(c_now, c_prev),
            'compare': compare,
            'spark': pp.sparkline(daily_count),
        },
        {
            'key': 'aov',
            'label': _('Average order'),
            'value': fmt(a_now),
            'delta': pp.change(a_now, a_prev),
            'compare': compare,
            'spark': {},
        },
    ]
    chart = pp.bar_chart(daily_gross, period, fmt=fmt)
    return {
        'kpis': kpis,
        'chart': chart,
        'chart_label': _('Sales per day, %(period)s. Total %(total)s.')
        % {'period': period.label, 'total': chart['total']},
        'commission': Money(g_now - n_now, currency),
    }


def units_by_sku(vendor, since=None) -> dict:
    """``{sku or name: {'name', 'sku', 'units', 'revenue'}}`` from the order snapshots."""
    qs = sold_orders(vendor)
    if since is not None:
        qs = qs.filter(created_at__gte=since)
    out: dict[str, dict] = {}
    for snapshot in qs.values_list('items_snapshot', flat=True):
        for item in snapshot if isinstance(snapshot, list) else []:
            if not isinstance(item, dict):
                continue
            key = item.get('sku') or item.get('name') or ''
            if not key:
                continue
            qty = _int(item.get('quantity'))
            try:
                unit = Decimal(str(item.get('unit_price') or 0))
            except (InvalidOperation, TypeError):
                unit = Decimal('0')
            row = out.setdefault(
                key,
                {
                    'name': item.get('name') or key,
                    'sku': item.get('sku') or '',
                    'units': 0,
                    'revenue': Decimal('0'),
                    'currency': item.get('currency') or 'USD',
                },
            )
            row['units'] += qty
            row['revenue'] += unit * qty
    return out


def best_sellers(vendor, period: pp.Period, limit: int = 5) -> list[dict]:
    from plugins.installed.catalog.models import Product

    rows = sorted(
        units_by_sku(vendor, period.start).values(), key=lambda r: (-r['units'], r['name'])
    )
    rows = rows[:limit]
    by_sku = {
        p.sku: p
        for p in Product.objects.filter(vendor=vendor, sku__in=[r['sku'] for r in rows if r['sku']])
    }
    peak = max((r['units'] for r in rows), default=0)
    for r in rows:
        product = by_sku.get(r['sku'])
        r['product_id'] = product.pk if product else None
        r['revenue'] = Money(r['revenue'], r['currency'])
        r['share'] = f'{r["units"] * 100 / peak:.0f}' if peak else '0'
    return rows


# ── Products ─────────────────────────────────────────────────────────────


def stock_for(product_ids) -> dict:
    """The inventory app's stock answer, or ``{}`` when nothing answers."""
    from morpheus.core import events, hook_registry

    ids = [str(pk) for pk in product_ids]
    if not ids:
        return {}
    answer = hook_registry.filter(events.PRODUCT_STOCK_SUMMARY, value={}, product_ids=ids)
    return answer if isinstance(answer, dict) else {}


def image_url(product) -> str:
    img = product.primary_image
    if not img:
        return ''
    try:
        if getattr(img, 'webp_image', None):
            return img.webp_image.url
        if getattr(img, 'image', None):
            return img.image.url
    except ValueError:  # an empty file field has no url
        return ''
    return ''


def decorate_products(vendor, products) -> list:
    """Attach stock, units sold in the last 30 days and a thumbnail to each product."""
    from datetime import timedelta

    from django.utils import timezone

    rows = list(products)
    stock = stock_for([p.pk for p in rows])
    sold = units_by_sku(vendor, timezone.now() - timedelta(days=30))
    for p in rows:
        p.stock = stock.get(str(p.pk))
        p.sold_30 = sold.get(p.sku, {}).get('units', 0) if p.sku else 0
        p.thumb = image_url(p)
    return rows


def stock_status(vendor) -> dict:
    """``{'attention': [...], 'tracked': n}`` — the vendor's live products that
    are low on stock or sold out (lowest first), and how many have tracked stock
    at all (0 when inventory is off or tracks none of them)."""
    from plugins.installed.catalog.models import Product

    products = list(
        Product.objects.filter(vendor=vendor).exclude(status='archived').only('id', 'name', 'sku')
    )
    stock = stock_for([p.pk for p in products])
    flagged = []
    for p in products:
        entry = stock.get(str(p.pk))
        if entry and (entry['low'] or entry['out']):
            p.stock = entry
            flagged.append(p)
    flagged.sort(key=lambda p: p.stock['available'])
    return {'attention': flagged, 'tracked': len(stock)}


def attention_products(vendor) -> list:
    return stock_status(vendor)['attention']


# ── Shell ────────────────────────────────────────────────────────────────


def nav(vendor) -> list[tuple]:
    to_fulfil = open_orders(vendor).count()
    attention = len(attention_products(vendor))
    return [
        ('overview', _('Overview'), '/vendor/me/'),
        ('orders', _('Orders'), '/vendor/me/orders/', to_fulfil or None),
        ('products', _('Products'), '/vendor/me/products/', attention or None, 'warn'),
        ('payouts', _('Payouts'), '/vendor/me/payouts/'),
        ('settings', _('Settings'), '/vendor/me/settings/'),
    ]


def shell(user, vendor, application, *, active: str, title: str) -> dict:
    """The portal context for one of the vendor's pages."""
    noun, _plural = vendor_noun()
    live = vendor is not None and vendor.is_active
    if vendor is not None:
        name = vendor.name
    elif application is not None:
        name = application.business_name
    else:
        name = getattr(user, 'full_name', '') or user.get_username()
    sub = ''
    if vendor is not None and vendor.created_at:
        sub = _('Selling here since %(date)s') % {'date': date_format(vendor.created_at, 'F Y')}
    actions = []
    if live:
        actions.append({'label': _('Your public page'), 'url': _public_page(vendor)})
    context = pp.portal_context(
        kind='vendor',
        kicker=_('%(noun)s portal') % {'noun': noun},
        name=name,
        sub=sub,
        title=title,
        status=status_of(vendor, application),
        nav=nav(vendor) if live else (),
        active=active,
        nav_label=_('%(noun)s portal') % {'noun': noun},
        actions=actions,
        avatar_url=_logo_url(vendor),
    )
    context.update({'vendor': vendor, 'application': application, 'vendor_noun': noun})
    return context


def _public_page(vendor) -> str:
    from django.urls import NoReverseMatch, reverse

    try:
        return reverse('storefront:vendor_detail', args=[vendor.slug])
    except NoReverseMatch:
        return f'/vendor/{vendor.slug}/'


def _logo_url(vendor) -> str:
    if vendor is None or not vendor.logo:
        return ''
    try:
        return vendor.logo.url
    except ValueError:
        return ''
