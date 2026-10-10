"""Storefront-side affiliate flows.

Affiliate self-service surface (``/affiliates/me/...``), rendered in the shared
partner-portal shell (``plugins.partner_portal``; the numbers in ``portal.py``):

  - ``affiliate_redirect``  /r/<code>             — anonymous click → cookie + 302
  - ``apply``               /affiliates/apply/    — signed-in customer applies
  - ``dashboard``           /affiliates/me/       — period KPIs, balance, link builder
  - ``links``               /affiliates/me/links/ — link builder + inventory + edit
  - ``edit_link``           /affiliates/me/links/<id>/edit/
  - ``create_link``         /affiliates/me/links/new/
  - ``conversions``         /affiliates/me/conversions/   — referred orders + CSV export
  - ``analytics``           /affiliates/me/analytics/     — traffic, funnel, products
  - ``payouts``             /affiliates/me/payouts/       — request + history
  - ``settings``            /affiliates/me/settings/      — profile + payout prefs
"""
# ruff: noqa: PLC0415  — inline imports are the established style here.
# ruff: noqa: S110     — best-effort fallback when reading djmoney attributes.

from __future__ import annotations

import contextlib

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from morpheus.app.views import HttpRequest, HttpResponse, HttpResponseRedirect

_AFFILIATE_COOKIE = 'morph_aff'
_COOKIE_TTL = 60 * 60 * 24 * 30  # 30 days; programs may override via cookie_window_days


def affiliate_redirect(request: HttpRequest, code: str) -> HttpResponseRedirect:
    from plugins.installed.affiliates.services import record_click

    referer = request.headers.get('Referer', '')
    user_agent = request.headers.get('User-Agent', '')
    ip = (
        request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        .split(',')[0]
        .strip()
    )

    link = record_click(code=code, referer=referer, user_agent=user_agent, ip=ip)
    # Only ever a page of this store: the landing URL is partner-written, and a
    # redirect to another host would make /r/ a phishing hop (services.store_path).
    from plugins.installed.affiliates.services import redirect_target

    landing = redirect_target(link.landing_url, request.get_host()) if link else '/'

    # Embeddable widgets link to /r/<code>?next=<pdp> so a click on an
    # external site still flows through record_click + the cookie set below.
    # `next` is honoured ONLY when it's a safe same-site path — never an
    # absolute/cross-host URL — so this can't be turned into an open redirect.
    from django.utils.http import url_has_allowed_host_and_scheme

    nxt = request.GET.get('next') or ''
    if (
        nxt
        and nxt.startswith('/')
        and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()})
    ):
        landing = nxt

    # The window the program advertises ("{days} days after a click"), not a
    # constant: programs allow 1–365 and the public terms print theirs.
    ttl = _COOKIE_TTL
    if link is not None:
        with contextlib.suppress(Exception):  # an odd row keeps the default window
            ttl = max(1, int(link.affiliate.program.cookie_window_days)) * 86400
    response = HttpResponseRedirect(landing)
    response.set_cookie(
        _AFFILIATE_COOKIE,
        code,
        max_age=ttl,
        httponly=True,
        samesite='Lax',
    )
    return response


@require_http_methods(['GET'])
def program_page(request: HttpRequest) -> HttpResponse:
    """The public affiliate program page: what each open program pays, how it
    works, and the next step for whoever is looking.

    Applying needs an account, so the call to action depends on the visitor:
    sign in, apply, or open the dashboard of an existing affiliate.
    """
    from django.utils.translation import gettext as _

    from plugins.installed.affiliates.models import Affiliate, AffiliateProgram

    programs = list(AffiliateProgram.objects.filter(is_active=True).order_by('created_at'))
    existing = None
    if request.user.is_authenticated:
        existing = Affiliate.objects.filter(user=request.user).first()
    if existing is not None:
        cta = {'url': '/affiliates/me/', 'label': _('Open your affiliate dashboard')}
    elif not programs:
        cta = None
    elif request.user.is_authenticated:
        cta = {'url': '/affiliates/apply/', 'label': _('Apply now')}
    else:
        cta = {'url': '/auth/login/?next=/affiliates/apply/', 'label': _('Sign in to apply')}
    return render(
        request,
        'affiliates/program.html',
        {
            'programs': programs,
            'cta': cta,
            'seo_title': _('Affiliate program'),
            'seo_description': _(
                'Earn a commission on every order that arrives through your links. '
                'See what each program pays and how to join.'
            ),
            'breadcrumb_items': [
                {'name': _('Home'), 'url': request.build_absolute_uri('/')},
                {'name': _('Affiliate program'), 'url': request.build_absolute_uri(request.path)},
            ],
        },
    )


@login_required(login_url='/auth/login/')
@require_http_methods(['GET', 'POST'])
def apply(request: HttpRequest) -> HttpResponse:
    """Affiliate application form. Creates a `pending` Affiliate row that an
    admin must approve before tracked links can be generated."""
    from plugins.installed.affiliates.models import Affiliate, AffiliateProgram

    existing = Affiliate.objects.filter(user=request.user).first()

    if request.method == 'POST' and existing is None:
        # Cloudflare Turnstile bot check (fail-soft: no-op when Turnstile/cloudflare off).
        try:
            from plugins.installed.cloudflare.services import verify_turnstile

            turnstile_ok = verify_turnstile(request)
        except Exception:  # noqa: BLE001 — cloudflare plugin may be disabled
            turnstile_ok = True
        if not turnstile_ok:
            return render(
                request,
                'affiliates/apply.html',
                {
                    'error': 'Bot check failed — please try again.',
                    'existing': None,
                    'programs': list(AffiliateProgram.objects.filter(is_active=True)),
                    'seo_title': 'Become an affiliate',
                },
            )
        handle_raw = (request.POST.get('handle') or '').strip()
        program_slug = (request.POST.get('program_slug') or '').strip()
        payout_email = (request.POST.get('payout_email') or request.user.email).strip()[:254]
        company = (request.POST.get('company') or '').strip()[:200]
        notes = (request.POST.get('notes') or '').strip()[:2000]

        program = None
        if program_slug:
            program = AffiliateProgram.objects.filter(slug=program_slug, is_active=True).first()
        if program is None:
            program = AffiliateProgram.objects.filter(is_active=True).order_by('created_at').first()

        if program is None:
            return render(
                request,
                'affiliates/apply.html',
                {
                    'error': 'No active affiliate program is currently accepting applications.',
                    'existing': None,
                    'programs': [],
                    'seo_title': 'Become an affiliate',
                },
            )

        # Generate a unique handle. Helper safely handles SSO users with
        # empty email + raises HandleUnavailable on collision exhaustion,
        # which we surface as a 200-with-form-error (not 403).
        from plugins.installed.affiliates.services import (
            HandleUnavailable,
            generate_unique_handle,
        )

        try:
            handle = generate_unique_handle(request.user, suggested=handle_raw)
        except HandleUnavailable:
            return render(
                request,
                'affiliates/apply.html',
                {
                    'error': "Couldn't pick a unique handle — try a different one.",
                    'existing': None,
                    'programs': list(AffiliateProgram.objects.filter(is_active=True)),
                    'seo_title': 'Become an affiliate',
                },
            )

        Affiliate.objects.create(
            program=program,
            user=request.user,
            handle=handle,
            status='pending',
            company=company,
            payout_email=payout_email,
            notes=notes,
        )
        return redirect('/affiliates/me/')

    return render(
        request,
        'affiliates/apply.html',
        {
            'existing': existing,
            'programs': list(AffiliateProgram.objects.filter(is_active=True).order_by('name')),
            'seo_title': 'Become an affiliate',
            'seo_description': 'Earn a commission on every order that arrives through your links.',
        },
    )


def _affiliate_or_redirect(request):
    """Return ``(affiliate, redirect_response)``. Exactly one is non-None.

    Self-service pages all need a single approved Affiliate row. If the
    user has none, we redirect to /affiliates/apply/. If they have only
    a pending/suspended row, we redirect them back to the dashboard
    where the appropriate status banner renders.
    """
    from plugins.installed.affiliates.models import Affiliate

    aff = (
        Affiliate.objects.filter(user=request.user, status='approved')
        .select_related('program')
        .order_by('created_at')
        .first()
    )
    if aff is not None:
        return aff, None
    # No approved row → bounce to apply or dashboard (which surfaces
    # the pending/suspended banner).
    if Affiliate.objects.filter(user=request.user).exists():
        return None, redirect('/affiliates/me/')
    return None, redirect('/affiliates/apply/')


def _shell(affiliate, active: str, title: str, **extra) -> dict:
    from plugins.installed.affiliates import portal

    context = portal.shell(affiliate, active=active, title=title)
    context['affiliate'] = affiliate
    context.update(extra)
    return context


def _site_base(request) -> str:
    return request.build_absolute_uri('/').rstrip('/')


def _highlighted_link(request, affiliate):
    """The link named by ``?new=<code>`` — the one the builder just made."""
    from plugins.installed.affiliates.models import AffiliateLink

    code = (request.GET.get('new') or '').strip()
    if not code:
        return None
    return AffiliateLink.objects.filter(affiliate=affiliate, code=code).first()


def _product_choices(limit: int = 300) -> list[dict]:
    """Active products for the link builder's suggestions: name → page path."""
    from plugins.installed.affiliates.widgets import product_pdp_path
    from plugins.installed.catalog.models import Product

    products = Product.objects.filter(status='active').only('id', 'name', 'slug').order_by('name')
    return [{'name': p.name, 'path': product_pdp_path(p)} for p in products[:limit]]


@login_required(login_url='/auth/login/')
def dashboard(request: HttpRequest) -> HttpResponse:
    """The affiliate's overview: period KPIs against the period before, the
    commission chart, balance and payout progress, the link builder, the rate
    they earn, their best links and products, and the latest orders."""
    from django.utils.translation import gettext as _

    from plugins import partner_portal as pp
    from plugins.installed.affiliates import portal
    from plugins.installed.affiliates.models import Affiliate, AffiliateConversion
    from plugins.installed.affiliates.services import affiliate_coupon, commission_summary

    accounts = list(
        Affiliate.objects.filter(user=request.user).select_related('program').order_by('created_at')
    )
    affiliate = next((a for a in accounts if a.status == 'approved'), None) or (
        accounts[0] if accounts else None
    )
    title = _('Affiliate dashboard')
    if affiliate is None:
        name = getattr(request.user, 'full_name', '') or request.user.get_username()
        context = pp.portal_context(
            kind='affiliate', kicker=_('Affiliate portal'), name=name, title=title
        )
        return render(request, 'affiliates/dashboard.html', context)
    if affiliate.status != 'approved':
        return render(request, 'affiliates/dashboard.html', _shell(affiliate, 'overview', title))

    period = pp.period_from(request)
    recent = list(
        AffiliateConversion.objects.filter(affiliate=affiliate)
        .select_related('order', 'link', 'payout')
        .order_by('-created_at')[:8]
    )
    for conversion in recent:
        conversion.state = portal.payout_state(conversion)
    context = _shell(
        affiliate,
        'overview',
        title,
        period=period,
        periods=pp.period_links(period),
        balance=portal.balances(affiliate),
        terms=commission_summary(affiliate),
        top_links=portal.top_links(affiliate, period),
        top_products=portal.top_products(affiliate, period),
        recent=recent,
        coupon=affiliate_coupon(affiliate),
        site_base=_site_base(request),
        new_link=_highlighted_link(request, affiliate),
        product_choices=_product_choices(),
        other_accounts=[a for a in accounts if a.pk != affiliate.pk],
    )
    context.update(portal.performance(affiliate, period))
    return render(request, 'affiliates/dashboard.html', context)


@login_required(login_url='/auth/login/')
@require_http_methods(['POST'])
def create_link(request: HttpRequest) -> HttpResponseRedirect:
    """The link builder: turn a page of the store into a tracked link.

    The landing page must be on this store (``services.store_path``). Making
    the same untitled link twice returns the first one instead of a duplicate.
    """
    from django.contrib import messages
    from django.utils.translation import gettext as _

    from plugins.installed.affiliates.models import Affiliate, AffiliateLink
    from plugins.installed.affiliates.services import store_path

    affiliate_id = (request.POST.get('affiliate_id') or '').strip()
    label = (request.POST.get('label') or '').strip()[:100]
    return_to = request.POST.get('return_to') or '/affiliates/me/links/'
    if not return_to.startswith('/affiliates/me/') or '//' in return_to:
        return_to = '/affiliates/me/links/'

    mine = Affiliate.objects.filter(user=request.user, status='approved')
    affiliate = None
    if affiliate_id:
        with contextlib.suppress(Exception):  # a malformed id is simply "not yours"
            affiliate = mine.filter(pk=affiliate_id).first()
    if affiliate is None:
        affiliate = mine.order_by('created_at').first()
    if affiliate is None:
        return HttpResponseRedirect('/affiliates/me/')

    try:
        landing = store_path(request.POST.get('landing_url') or '', request.get_host())
    except ValueError as exc:
        messages.error(request, str(exc))
        return HttpResponseRedirect(return_to)

    link = None
    if not label:
        link = (
            AffiliateLink.objects.filter(
                affiliate=affiliate, landing_url=landing, is_active=True, coupon_code=''
            )
            .order_by('created_at')
            .first()
        )
    if link is None:
        link = AffiliateLink.objects.create(affiliate=affiliate, landing_url=landing, label=label)
        messages.success(request, _('Your tracked link is ready.'))
    else:
        messages.info(request, _('You already had a link to that page — here it is.'))
    joiner = '&' if '?' in return_to else '?'
    return HttpResponseRedirect(f'{return_to}{joiner}new={link.code}')


# ─── Links inventory ──────────────────────────────────────────────────


@login_required(login_url='/auth/login/')
def links(request: HttpRequest) -> HttpResponse:
    """The link builder and every tracked link, with what each one earned."""
    from django.db.models import Q
    from django.utils.translation import gettext as _

    from plugins.installed.affiliates import portal
    from plugins.installed.affiliates.models import AffiliateLink
    from plugins.installed.affiliates.services import store_path

    affiliate, bounce = _affiliate_or_redirect(request)
    if bounce is not None:
        return bounce

    q = (request.GET.get('q') or '').strip()
    status = (request.GET.get('status') or '').strip()
    base = AffiliateLink.objects.filter(affiliate=affiliate)
    qs = base
    if q:
        qs = qs.filter(Q(code__icontains=q) | Q(label__icontains=q) | Q(landing_url__icontains=q))
    if status == 'active':
        qs = qs.filter(is_active=True)
    elif status == 'inactive':
        qs = qs.filter(is_active=False)
    rows = list(qs.order_by('-created_at')[:200])
    portal.link_stats(affiliate, rows)

    # ?url= prefills the builder ("share this product again" from the overview).
    prefill = ''
    if request.GET.get('url'):
        with contextlib.suppress(ValueError):
            prefill = store_path(request.GET['url'], request.get_host())

    return render(
        request,
        'affiliates/links.html',
        _shell(
            affiliate,
            'links',
            _('Your tracked links'),
            links=rows,
            q=q,
            status=status,
            counts={
                'all': base.count(),
                'active': base.filter(is_active=True).count(),
                'inactive': base.filter(is_active=False).count(),
            },
            site_base=_site_base(request),
            new_link=_highlighted_link(request, affiliate),
            prefill=prefill,
            product_choices=_product_choices(),
        ),
    )


@login_required(login_url='/auth/login/')
@require_http_methods(['POST'])
def edit_link(request: HttpRequest, link_id) -> HttpResponseRedirect:
    """Inline edit: label + active toggle."""
    from plugins.installed.affiliates.models import AffiliateLink

    try:
        link = AffiliateLink.objects.select_related('affiliate').get(
            pk=link_id,
            affiliate__user=request.user,
        )
    except AffiliateLink.DoesNotExist:
        return HttpResponseRedirect('/affiliates/me/links/')

    fields = []
    if 'label' in request.POST:
        link.label = (request.POST.get('label') or '').strip()[:100]
        fields.append('label')
    if 'is_active' in request.POST:
        link.is_active = request.POST.get('is_active') in ('1', 'true', 'on', 'yes')
        fields.append('is_active')
    if fields:
        link.save(update_fields=fields)
    return HttpResponseRedirect('/affiliates/me/links/')


# ─── Referred orders ──────────────────────────────────────────────────

_ORDER_FILTERS = ('pending', 'approved', 'paid', 'rejected')


def _filter_orders(qs, status: str):
    """Filter conversions by where their commission stands. "Paid" includes an
    approved conversion whose bundling payout has been paid."""
    from django.db.models import Q

    paid = Q(status='paid') | Q(status='approved', payout__status='paid')
    if status == 'paid':
        return qs.filter(paid)
    if status == 'approved':
        return qs.filter(status='approved').exclude(paid)
    if status in ('pending', 'rejected'):
        return qs.filter(status=status)
    return qs


@login_required(login_url='/auth/login/')
def conversions(request: HttpRequest) -> HttpResponse:
    """Every referred order, filterable by where its commission stands, + CSV export."""
    from django.core.paginator import Paginator
    from django.utils.translation import gettext as _

    from plugins.installed.affiliates import portal
    from plugins.installed.affiliates.models import AffiliateConversion

    affiliate, bounce = _affiliate_or_redirect(request)
    if bounce is not None:
        return bounce

    status = (request.GET.get('status') or '').strip()
    if status not in _ORDER_FILTERS:
        status = ''
    base = AffiliateConversion.objects.filter(affiliate=affiliate).select_related(
        'order', 'link', 'payout'
    )
    qs = _filter_orders(base, status).order_by('-created_at')

    if request.GET.get('export') == 'csv':
        import csv
        from io import StringIO

        buf = StringIO()
        w = csv.writer(buf)
        w.writerow(['date', 'order_number', 'order_total', 'commission', 'status', 'link'])
        for c in qs[:5000]:
            w.writerow(
                [
                    c.created_at.isoformat(),
                    getattr(c.order, 'order_number', str(c.order_id)),
                    str(getattr(c.order, 'total', '')),
                    str(c.commission),
                    portal.payout_state(c),
                    c.link.code if c.link_id and c.link else '',
                ]
            )
        response = HttpResponse(buf.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="orders-{affiliate.handle}.csv"'
        return response

    page = Paginator(qs, 50).get_page(request.GET.get('page'))
    for c in page.object_list:
        c.state = portal.payout_state(c)
    counts = {key: _filter_orders(base, key).count() for key in _ORDER_FILTERS}
    counts['all'] = base.count()
    return render(
        request,
        'affiliates/conversions.html',
        _shell(
            affiliate,
            'orders',
            _('Referred orders'),
            conversions=page.object_list,
            page_obj=page,
            status=status,
            counts=counts,
        ),
    )


# ─── Payouts ──────────────────────────────────────────────────────────


@login_required(login_url='/auth/login/')
@require_http_methods(['GET', 'POST'])
def payouts(request: HttpRequest) -> HttpResponse:
    """Balance, progress to the minimum payout, the request form and the history."""
    from django.db.models import Count
    from django.utils.translation import gettext as _

    from plugins.installed.affiliates import portal
    from plugins.installed.affiliates.models import Affiliate, AffiliatePayout
    from plugins.installed.affiliates.services import request_affiliate_payout

    affiliate, bounce = _affiliate_or_redirect(request)
    if bounce is not None:
        return bounce

    error = ''
    success = ''
    methods = dict(Affiliate.PAYOUT_METHOD_CHOICES)

    if request.method == 'POST':
        method = (request.POST.get('method') or '').strip()[:40]
        if method and method not in methods:
            error = _('Pick a payout method from the list.')
        else:
            try:
                payout = request_affiliate_payout(affiliate, method=method)
                success = _(
                    'Payout request for %(amount)s sent. The store team processes it '
                    'and marks it paid here.'
                ) % {'amount': portal.money_text(payout.amount)}
            except ValueError as exc:
                error = str(exc)

    history = list(
        AffiliatePayout.objects.filter(affiliate=affiliate)
        .annotate(orders=Count('bundled_conversions'))
        .order_by('-requested_at')[:50]
    )
    for p in history:
        p.method_label = methods.get(p.method, p.method)

    return render(
        request,
        'affiliates/payouts.html',
        _shell(
            affiliate,
            'payouts',
            _('Payouts'),
            balance=portal.balances(affiliate),
            history=history,
            method_choices=list(Affiliate.PAYOUT_METHOD_CHOICES),
            error=error,
            success=success,
        ),
    )


# ─── Embeddable widgets (affiliate self-service) ──────────────────────


def _widget_categories():
    """Active categories for the widget create form's category picker."""
    from plugins.installed.catalog.models import Category

    return list(Category.objects.filter(is_active=True).order_by('name').values('slug', 'name'))


def _resolve_product_ids(raw: str) -> list[str]:
    """Map a comma/newline list of product slugs to active product UUIDs.

    Bounded to 24 ids. Unknown / inactive slugs are silently dropped — the
    widget renders whatever resolves.
    """
    from plugins.installed.catalog.models import Product

    slugs = [s.strip() for s in raw.replace('\n', ',').split(',') if s.strip()][:24]
    if not slugs:
        return []
    found = Product.objects.filter(status='active', slug__in=slugs).values_list('slug', 'id')
    by_slug = {s: str(pid) for s, pid in found}
    return [by_slug[s] for s in slugs if s in by_slug]


def _apply_widget_form(widget, request) -> None:
    """Mutate ``widget`` in place from POST data (shared by create + edit)."""
    from plugins.installed.affiliates.models import AffiliateWidget

    title = (request.POST.get('title') or '').strip()[:120]
    source = request.POST.get('source') or 'featured'
    if source not in dict(AffiliateWidget.SOURCE_CHOICES):
        source = 'featured'
    theme = request.POST.get('theme') or 'auto'
    if theme not in dict(AffiliateWidget.THEME_CHOICES):
        theme = 'auto'
    layout = request.POST.get('layout') or 'grid'
    if layout not in dict(AffiliateWidget.LAYOUT_CHOICES):
        layout = 'grid'
    try:
        limit = int(request.POST.get('limit') or 6)
    except (TypeError, ValueError):
        limit = 6

    widget.title = title
    widget.source = source
    widget.theme = theme
    widget.layout = layout
    widget.limit = max(1, min(limit, 24))
    widget.category_slug = (request.POST.get('category_slug') or '').strip()[:200]
    widget.product_ids = (
        _resolve_product_ids(request.POST.get('product_slugs') or '')
        if source == 'products'
        else []
    )


@login_required(login_url='/auth/login/')
@require_http_methods(['GET', 'POST'])
def widgets(request: HttpRequest) -> HttpResponse:
    """Affiliate-owned embeddable widgets: list + create + copy embed codes.

    Owner-scoped — operates only on the requesting user's approved Affiliate
    (via ``_affiliate_or_redirect``). Anonymous users hit ``@login_required``;
    a signed-in user with no approved affiliate is bounced to apply/dashboard.
    """
    from django.utils.translation import gettext as _

    from plugins.installed.affiliates.models import AffiliateWidget

    affiliate, bounce = _affiliate_or_redirect(request)
    if bounce is not None:
        return bounce

    if request.method == 'POST' and request.POST.get('action') == 'create':
        widget = AffiliateWidget(affiliate=affiliate)
        _apply_widget_form(widget, request)
        widget.save()
        return HttpResponseRedirect('/affiliates/me/widgets/')

    rows = list(AffiliateWidget.objects.filter(affiliate=affiliate).order_by('-created_at')[:100])
    site_base = _site_base(request)
    for w in rows:
        w.iframe_src = f'{site_base}/affiliates/embed/{w.key}/'
        w.js_src = f'{site_base}/affiliates/embed/{w.key}.js'
        w.json_src = f'{site_base}/api/affiliates/widget/{w.key}.json'

    return render(
        request,
        'affiliates/widgets.html',
        _shell(
            affiliate,
            'widgets',
            _('Embeddable widgets'),
            widgets=rows,
            categories=_widget_categories(),
            site_base=site_base,
        ),
    )


@login_required(login_url='/auth/login/')
@require_http_methods(['POST'])
def edit_widget(request: HttpRequest, widget_id) -> HttpResponseRedirect:
    """Update / toggle / delete an owned widget. Owner-scoped: the queryset is
    filtered by ``affiliate__user=request.user`` so one affiliate can never
    mutate another's widget (404 otherwise)."""
    from plugins.installed.affiliates.models import AffiliateWidget

    try:
        widget = AffiliateWidget.objects.select_related('affiliate').get(
            pk=widget_id,
            affiliate__user=request.user,
        )
    except AffiliateWidget.DoesNotExist:
        return HttpResponseRedirect('/affiliates/me/widgets/')

    action = request.POST.get('action') or 'save'
    if action == 'delete':
        widget.delete()
    elif action == 'toggle':
        widget.is_active = not widget.is_active
        widget.save(update_fields=['is_active'])
    else:
        _apply_widget_form(widget, request)
        widget.save()
    return HttpResponseRedirect('/affiliates/me/widgets/')


# ─── Settings ─────────────────────────────────────────────────────────


@login_required(login_url='/auth/login/')
@require_http_methods(['GET', 'POST'])
def settings(request: HttpRequest) -> HttpResponse:
    """Editable affiliate profile: display name, payout email, method, bio."""
    from django.utils.translation import gettext as _

    from plugins.installed.affiliates.models import Affiliate

    affiliate, bounce = _affiliate_or_redirect(request)
    if bounce is not None:
        return bounce

    saved = False
    error = ''
    method_choices = list(Affiliate.PAYOUT_METHOD_CHOICES)

    if request.method == 'POST':
        display_name = (request.POST.get('display_name') or '').strip()[:200]
        company = (request.POST.get('company') or '').strip()[:200]
        payout_email = (request.POST.get('payout_email') or '').strip()[:254]
        method = (request.POST.get('preferred_payout_method') or 'paypal').strip()
        notes = (request.POST.get('notes') or '').strip()[:2000]

        valid_methods = {k for k, _label in method_choices}
        if method not in valid_methods:
            error = _('Pick a valid payout method.')
        else:
            affiliate.display_name = display_name
            affiliate.company = company
            affiliate.payout_email = payout_email
            affiliate.preferred_payout_method = method
            affiliate.notes = notes
            affiliate.save(
                update_fields=[
                    'display_name',
                    'company',
                    'payout_email',
                    'preferred_payout_method',
                    'notes',
                ]
            )
            saved = True

    return render(
        request,
        'affiliates/settings.html',
        _shell(
            affiliate,
            'settings',
            _('Affiliate settings'),
            method_choices=method_choices,
            saved=saved,
            error=error,
            site_base=_site_base(request),
        ),
    )


@login_required(login_url='/auth/login/')
def leaderboard(request: HttpRequest) -> HttpResponse:
    """Top affiliates by sales driven — a motivational leaderboard. Shows
    pseudonymous @handles + sales counts (never others' earnings) and
    highlights the viewer's own position."""
    from django.db.models import Count, Q
    from django.utils.translation import gettext as _

    from plugins.installed.affiliates.models import Affiliate, AffiliateConversion

    affiliate, bounce = _affiliate_or_redirect(request)
    if bounce is not None:
        return bounce

    counted = Q(conversions__status__in=['approved', 'paid'])
    ranked = list(
        Affiliate.objects.filter(status='approved')
        .annotate(sales=Count('conversions', filter=counted))
        .filter(sales__gt=0)
        .order_by('-sales', 'created_at')[:20]
    )
    rows = []
    my_rank = None
    leader = ranked[0].sales if ranked else 0
    for i, a in enumerate(ranked, start=1):
        is_me = a.id == affiliate.id
        if is_me:
            my_rank = i
        rows.append(
            {
                'rank': i,
                'name': f'@{a.handle}',
                'sales': a.sales,
                'is_me': is_me,
                'share': f'{a.sales * 100 / leader:.0f}' if leader else '0',
            }
        )
    my_sales = AffiliateConversion.objects.filter(
        affiliate=affiliate, status__in=['approved', 'paid']
    ).count()
    return render(
        request,
        'affiliates/leaderboard.html',
        _shell(
            affiliate,
            'leaderboard',
            _('Affiliate leaderboard'),
            rows=rows,
            my_rank=my_rank,
            my_sales=my_sales,
        ),
    )


@login_required(login_url='/auth/login/')
def creatives(request: HttpRequest) -> HttpResponse:
    """Affiliate-facing marketing creatives library — grab a banner/cover +
    swipe copy, then spin a tracked link to its target in one click."""
    from django.utils.translation import gettext as _

    from plugins.installed.affiliates.models import AffiliateCreative

    affiliate, bounce = _affiliate_or_redirect(request)
    if bounce is not None:
        return bounce

    return render(
        request,
        'affiliates/creatives.html',
        _shell(
            affiliate,
            'creatives',
            _('Marketing creatives'),
            creatives=list(AffiliateCreative.objects.filter(is_active=True)),
        ),
    )


@login_required(login_url='/auth/login/')
def analytics(request: HttpRequest) -> HttpResponse:
    """The affiliate's own performance over 7, 30 or 90 days: clicks per day,
    the click → order → confirmed funnel, where clicks come from, what
    customers bought and how every link did. Read-only."""
    from django.utils.translation import gettext as _

    from plugins import partner_portal as pp
    from plugins.installed.affiliates import portal
    from plugins.installed.affiliates.models import AffiliateLink

    affiliate, bounce = _affiliate_or_redirect(request)
    if bounce is not None:
        return bounce

    period = pp.period_from(request)
    perf = portal.performance(affiliate, period)
    link_rows = list(AffiliateLink.objects.filter(affiliate=affiliate))
    portal.link_stats(affiliate, link_rows, since=period.start)
    link_rows = [lk for lk in link_rows if lk.period_clicks or lk.period_orders]
    link_rows.sort(key=lambda lk: (lk.commission.amount, lk.period_clicks), reverse=True)
    for lk in link_rows:
        lk.epc = lk.commission / lk.period_clicks if lk.period_clicks else None
    kpis = perf['kpis'][:3]
    kpis.append(
        {
            'key': 'epc',
            'label': _('Earnings per click'),
            'value': portal.money_text(perf['epc']),
            'foot': _('Commission ÷ clicks, %(period)s') % {'period': period.label},
        }
    )
    clicks_chart = perf['clicks_chart']
    return render(
        request,
        'affiliates/analytics.html',
        _shell(
            affiliate,
            'analytics',
            _('Your analytics'),
            period=period,
            periods=pp.period_links(period),
            kpis=kpis,
            chart=clicks_chart,
            chart_label=_('Clicks per day, %(period)s. Total %(total)s.')
            % {'period': period.label, 'total': clicks_chart['total']},
            funnel=perf['funnel'],
            aov=perf['aov'],
            sources=portal.traffic_sources(affiliate, period),
            top_products=portal.top_products(affiliate, period, limit=8),
            link_rows=link_rows[:25],
        ),
    )


@login_required(login_url='/auth/login/')
def coupon(request: HttpRequest) -> HttpResponse:
    """The affiliate's personal coupon code — claim a handle-derived code, then
    share it. Customers who use it at checkout are attributed to the affiliate
    (via the existing coupon path); the store pairs it with a discount."""
    from django.utils.translation import gettext as _

    from plugins.installed.affiliates import portal
    from plugins.installed.affiliates.models import AffiliateLink
    from plugins.installed.affiliates.services import affiliate_coupon

    affiliate, bounce = _affiliate_or_redirect(request)
    if bounce is not None:
        return bounce

    if request.method == 'POST':
        affiliate_coupon(affiliate, claim=True)
        return redirect('/affiliates/me/coupon/')

    code = affiliate_coupon(affiliate)
    coupon_link = None
    if code:
        coupon_link = (
            AffiliateLink.objects.filter(affiliate=affiliate, coupon_code__iexact=code)
            .order_by('created_at')
            .first()
        )
        if coupon_link is not None:
            portal.link_stats(affiliate, [coupon_link])
    return render(
        request,
        'affiliates/coupon.html',
        _shell(
            affiliate,
            'coupon',
            _('Your coupon'),
            code=code,
            coupon_link=coupon_link,
            site_base=_site_base(request),
        ),
    )
