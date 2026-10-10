"""What the affiliate portal shows, computed from the rows that record it.

Every money figure is summed from conversions and payouts, never read from
``Affiliate.accrued_balance`` / ``lifetime_paid``: the merchant dashboard
approves a conversion by setting its status without touching that balance, so
the column under-reports — a denormalised display column is not a source.

The shell (identity header + tabs) comes from ``plugins.partner_portal``; this
module supplies the affiliate's navigation and numbers.
"""
# ruff: noqa: PLC0415  — inline imports keep cross-plugin reads lazy (house style).

from __future__ import annotations

from decimal import Decimal
from urllib.parse import urlsplit

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils.formats import number_format
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from djmoney.money import Money

from plugins import partner_portal as pp

# A referred order that still counts: not reversed by a refund or a reviewer.
COUNTED = ('pending', 'approved', 'paid')
# Commission the store has confirmed.
EARNED = ('approved', 'paid')

_STATUS = {
    'approved': ('ok', gettext_lazy('Approved')),
    'pending': ('wait', gettext_lazy('Pending review')),
    'suspended': ('bad', gettext_lazy('Suspended')),
    'rejected': ('bad', gettext_lazy('Not approved')),
}


def nav() -> list[tuple]:
    return [
        ('overview', _('Overview'), '/affiliates/me/'),
        ('links', _('Links'), '/affiliates/me/links/'),
        ('coupon', _('Coupon'), '/affiliates/me/coupon/'),
        ('orders', _('Orders'), '/affiliates/me/conversions/'),
        ('analytics', _('Analytics'), '/affiliates/me/analytics/'),
        ('payouts', _('Payouts'), '/affiliates/me/payouts/'),
        ('creatives', _('Creatives'), '/affiliates/me/creatives/'),
        ('widgets', _('Widgets'), '/affiliates/me/widgets/'),
        ('leaderboard', _('Leaderboard'), '/affiliates/me/leaderboard/'),
        ('settings', _('Settings'), '/affiliates/me/settings/'),
    ]


def shell(affiliate, *, active: str, title: str) -> dict:
    """The portal context for one of ``affiliate``'s pages."""
    tone, label = _STATUS.get(affiliate.status, ('neutral', affiliate.get_status_display()))
    name = affiliate.display_name or affiliate.company or f'@{affiliate.handle}'
    sub = f'@{affiliate.handle} · {affiliate.program.name}'
    approved = affiliate.status == 'approved'
    return pp.portal_context(
        kind='affiliate',
        kicker=_('Affiliate portal'),
        name=name,
        sub=sub,
        title=title,
        status={'key': affiliate.status, 'label': label, 'tone': tone},
        nav=nav() if approved else (),
        active=active,
        nav_label=_('Affiliate portal'),
        actions=[{'label': _('Program terms'), 'url': '/affiliates/'}],
    )


def currency_of(affiliate) -> str:
    """The currency the affiliate is paid in: their latest commission's, else
    the programme's payout currency."""
    from plugins.installed.affiliates.models import AffiliateConversion

    latest = (
        AffiliateConversion.objects.filter(affiliate=affiliate)
        .order_by('-created_at')
        .values_list('commission_currency', flat=True)
        .first()
    )
    return str(latest or affiliate.program.minimum_payout.currency or 'USD')


def _amount(value) -> Decimal:
    return Decimal(str(getattr(value, 'amount', value) or 0))


def _sum(qs, field: str) -> Decimal:
    return _amount(qs.aggregate(t=Sum(field))['t'])


def money_text(value) -> str:
    from core.templatetags.morph import money_filter

    return money_filter(value)


def count_text(value) -> str:
    return number_format(value, force_grouping=True)


# ── Balances ─────────────────────────────────────────────────────────────


def balances(affiliate) -> dict:
    """Where the affiliate's commission stands, and whether a payout can be asked for."""
    from plugins.installed.affiliates.models import AffiliateConversion, AffiliatePayout
    from plugins.installed.affiliates.services import min_payout_threshold, pending_payout_amount

    currency = currency_of(affiliate)
    conversions = AffiliateConversion.objects.filter(affiliate=affiliate)
    payouts = AffiliatePayout.objects.filter(affiliate=affiliate)
    open_qs = payouts.filter(status__in=('pending', 'processing'))

    ready = pending_payout_amount(affiliate).amount
    threshold = min_payout_threshold(affiliate)
    floor = threshold.amount
    if floor > 0:
        progress = min(Decimal('100'), ready * 100 / floor)
    else:
        progress = Decimal('100') if ready > 0 else Decimal('0')
    open_payout = open_qs.order_by('-requested_at').first()
    return {
        'currency': currency,
        'in_review': Money(_sum(conversions.filter(status='pending'), 'commission'), currency),
        'earned': Money(_sum(conversions.filter(status__in=EARNED), 'commission'), currency),
        'ready': Money(ready, currency),
        'in_flight': Money(_sum(open_qs, 'amount'), currency),
        'paid': Money(_sum(payouts.filter(status='paid'), 'amount'), currency),
        'threshold': threshold,
        'remaining': Money(max(floor - ready, Decimal('0')), currency),
        'progress': f'{progress:.0f}',
        'reached': ready > 0 and ready >= floor,
        'open_payout': open_payout,
        'can_request': open_payout is None and ready > 0 and ready >= floor,
    }


# ── Period figures ───────────────────────────────────────────────────────


def _daily(qs, field: str, value=None) -> list[tuple]:
    agg = value if value is not None else Count('id')
    return list(qs.annotate(d=TruncDate(field)).values('d').annotate(v=agg).values_list('d', 'v'))


def performance(affiliate, period: pp.Period) -> dict:
    """KPI tiles, the commission chart and the funnel for ``period``."""
    from plugins.installed.affiliates.models import AffiliateClick, AffiliateConversion

    currency = currency_of(affiliate)
    clicks = AffiliateClick.objects.filter(link__affiliate=affiliate)
    orders = AffiliateConversion.objects.filter(affiliate=affiliate, status__in=COUNTED)
    now_clicks = clicks.filter(occurred_at__gte=period.start)
    now_orders = orders.filter(created_at__gte=period.start)
    prev_clicks = clicks.filter(occurred_at__gte=period.prev_start, occurred_at__lt=period.start)
    prev_orders = orders.filter(created_at__gte=period.prev_start, created_at__lt=period.start)

    n_clicks, p_clicks = now_clicks.count(), prev_clicks.count()
    n_orders, p_orders = now_orders.count(), prev_orders.count()
    n_comm, p_comm = _sum(now_orders, 'commission'), _sum(prev_orders, 'commission')
    n_rate, p_rate = pp.rate(n_orders, n_clicks), pp.rate(p_orders, p_clicks)
    confirmed = now_orders.filter(status__in=EARNED).count()

    daily_clicks = pp.daily(_daily(now_clicks, 'occurred_at'), period)
    daily_orders = pp.daily(_daily(now_orders, 'created_at'), period)
    daily_comm = [
        _amount(v) for v in pp.daily(_daily(now_orders, 'created_at', Sum('commission')), period)
    ]
    compare = _('vs previous %(days)s days') % {'days': period.days}

    def fmt_money(v):
        return money_text(Money(v, currency))

    kpis = [
        {
            'key': 'clicks',
            'label': _('Clicks'),
            'value': count_text(n_clicks),
            'delta': pp.change(n_clicks, p_clicks),
            'compare': compare,
            'spark': pp.sparkline(daily_clicks),
        },
        {
            'key': 'orders',
            'label': _('Orders'),
            'value': count_text(n_orders),
            'delta': pp.change(n_orders, p_orders),
            'compare': compare,
            'spark': pp.sparkline(daily_orders),
        },
        {
            'key': 'conversion',
            'label': _('Conversion rate'),
            'value': f'{number_format(n_rate, decimal_pos=1)}%',
            'delta': pp.change_points(n_rate, p_rate),
            'compare': compare,
            'spark': {},
        },
        {
            'key': 'commission',
            'label': _('Commission'),
            'value': fmt_money(n_comm),
            'delta': pp.change(n_comm, p_comm),
            'compare': compare,
            'spark': pp.sparkline(daily_comm),
        },
    ]
    chart = pp.bar_chart(daily_comm, period, fmt=fmt_money)
    return {
        'kpis': kpis,
        'chart': chart,
        'chart_label': _('Commission per day, %(period)s. Total %(total)s.')
        % {'period': period.label, 'total': chart['total']},
        'clicks_chart': pp.bar_chart(
            daily_clicks, period, fmt=count_text, highlight=[n > 0 for n in daily_orders]
        ),
        'funnel': {
            'clicks': count_text(n_clicks),
            'orders': count_text(n_orders),
            'confirmed': count_text(confirmed),
            'click_rate': pp.rate(n_orders, n_clicks),
            'confirm_rate': pp.rate(confirmed, n_orders),
        },
        'epc': Money(n_comm / n_clicks if n_clicks else 0, currency),
        'aov': _average_order(now_orders, currency),
    }


def _average_order(conversions, currency: str) -> Money:
    """Average total of the referred orders."""
    from plugins.installed.orders.models import Order

    totals = Order.objects.filter(pk__in=conversions.values('order_id')).aggregate(
        t=Sum('total'), n=Count('id')
    )
    n = totals['n'] or 0
    return Money(_amount(totals['t']) / n if n else 0, currency)


def link_stats(affiliate, links, *, since=None) -> None:
    """Annotate each link with its orders and commission (``since`` or lifetime)
    and its clicks over the same span."""
    from plugins.installed.affiliates.models import AffiliateClick, AffiliateConversion

    currency = currency_of(affiliate)
    conv = AffiliateConversion.objects.filter(affiliate=affiliate, status__in=COUNTED)
    clicks = AffiliateClick.objects.filter(link__affiliate=affiliate)
    if since is not None:
        conv = conv.filter(created_at__gte=since)
        clicks = clicks.filter(occurred_at__gte=since)
    by_link = {
        row['link_id']: row
        for row in conv.values('link_id').annotate(n=Count('id'), t=Sum('commission'))
    }
    click_counts = dict(clicks.values_list('link_id').annotate(n=Count('id')))
    for link in links:
        row = by_link.get(link.pk, {})
        link.period_clicks = click_counts.get(link.pk, 0)
        link.period_orders = row.get('n', 0)
        link.commission = Money(_amount(row.get('t')), currency)
        link.cr = pp.rate(link.period_orders, link.period_clicks)


def top_links(affiliate, period: pp.Period, limit: int = 5) -> list:
    from plugins.installed.affiliates.models import AffiliateLink

    links = list(AffiliateLink.objects.filter(affiliate=affiliate))
    link_stats(affiliate, links, since=period.start)
    active = [lk for lk in links if lk.period_clicks or lk.period_orders]
    active.sort(
        key=lambda lk: (lk.commission.amount, lk.period_orders, lk.period_clicks), reverse=True
    )
    return active[:limit]


def top_products(affiliate, period: pp.Period | None, limit: int = 5) -> list[dict]:
    """What customers bought in the orders this affiliate referred."""
    from plugins.installed.affiliates.models import AffiliateConversion
    from plugins.installed.affiliates.widgets import product_pdp_path
    from plugins.installed.catalog.models import Product
    from plugins.installed.orders.models import OrderItem

    conv = AffiliateConversion.objects.filter(affiliate=affiliate, status__in=COUNTED)
    if period is not None:
        conv = conv.filter(created_at__gte=period.start)
    rows = list(
        OrderItem.objects.filter(order_id__in=conv.values('order_id'))
        .values('product_id', 'product_name', 'total_price_currency')
        .annotate(units=Sum('quantity'), revenue=Sum('total_price'))
        .order_by('-units', '-revenue')[:limit]
    )
    products = Product.objects.filter(
        pk__in=[r['product_id'] for r in rows if r['product_id']], status='active'
    ).only('id', 'slug')
    paths = {p.pk: product_pdp_path(p) for p in products}
    peak = max((r['units'] or 0 for r in rows), default=0)
    return [
        {
            'name': r['product_name'],
            'units': r['units'] or 0,
            'revenue': Money(_amount(r['revenue']), r['total_price_currency'] or 'USD'),
            'path': paths.get(r['product_id'], ''),
            'share': f'{(r["units"] or 0) * 100 / peak:.0f}' if peak else '0',
        }
        for r in rows
    ]


def traffic_sources(affiliate, period: pp.Period, limit: int = 8) -> list[dict]:
    """Where this period's clicks came from, by referring site."""
    from plugins.installed.affiliates.models import AffiliateClick

    counts: dict[str, int] = {}
    rows = (
        AffiliateClick.objects.filter(link__affiliate=affiliate, occurred_at__gte=period.start)
        .values_list('referer')
        .annotate(n=Count('id'))
    )
    for referer, n in rows:
        host = (urlsplit(referer).hostname or '') if referer else ''
        host = host[4:] if host.startswith('www.') else host
        counts[host] = counts.get(host, 0) + n
    total = sum(counts.values())
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [
        {
            'source': host or _('Direct or unknown'),
            'clicks': n,
            'share': f'{n * 100 / total:.0f}' if total else '0',
        }
        for host, n in ranked
    ]


def payout_state(conversion) -> str:
    """Where one conversion's commission is: in review, approved, in a payout, paid, reversed."""
    if conversion.status == 'rejected':
        return 'reversed'
    if conversion.status == 'pending':
        return 'review'
    if conversion.status == 'paid' or (conversion.payout_id and conversion.payout.status == 'paid'):
        return 'paid'
    if conversion.payout_id:
        return 'requested'
    return 'approved'
