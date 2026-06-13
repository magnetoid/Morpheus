"""Storefront-side affiliate flows.

Affiliate self-service surface (``/affiliates/me/...``):

  - ``affiliate_redirect``  /r/<code>             — anonymous click → cookie + 302
  - ``apply``               /affiliates/apply/    — signed-in customer applies
  - ``dashboard``           /affiliates/me/       — KPI overview + recent activity
  - ``links``               /affiliates/me/links/ — full link inventory + edit
  - ``edit_link``           /affiliates/me/links/<id>/edit/
  - ``create_link``         /affiliates/me/links/new/
  - ``conversions``         /affiliates/me/conversions/   — log + CSV export
  - ``payouts``             /affiliates/me/payouts/       — request + history
  - ``settings``            /affiliates/me/settings/      — profile + payout prefs
"""
# ruff: noqa: PLC0415  — inline imports are the established style here.
# ruff: noqa: S110     — best-effort fallback when reading djmoney attributes.

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from morpheus.views import HttpRequest, HttpResponse, HttpResponseRedirect

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
    landing = link.landing_url if link else '/'

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

    response = HttpResponseRedirect(landing)
    response.set_cookie(
        _AFFILIATE_COOKIE,
        code,
        max_age=_COOKIE_TTL,
        httponly=True,
        samesite='Lax',
    )
    return response


@login_required(login_url='/auth/login/')
@require_http_methods(['GET', 'POST'])
def apply(request: HttpRequest) -> HttpResponse:
    """Affiliate application form. Creates a `pending` Affiliate row that an
    admin must approve before tracked links can be generated."""
    from plugins.installed.affiliates.models import Affiliate, AffiliateProgram

    existing = Affiliate.objects.filter(user=request.user).first()

    if request.method == 'POST' and existing is None:
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
            'seo_description': 'Earn a commission for every reader you send our way.',
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
        .first()
    )
    if aff is not None:
        return aff, None
    # No approved row → bounce to apply or dashboard (which surfaces
    # the pending/suspended banner).
    if Affiliate.objects.filter(user=request.user).exists():
        return None, redirect('/affiliates/me/')
    return None, redirect('/affiliates/apply/')


@login_required(login_url='/auth/login/')
def dashboard(request: HttpRequest) -> HttpResponse:
    """Affiliate dashboard overview.

    Refreshed layout — Rewardful/Tapfiliate-style:
      * KPI row (lifetime): clicks · conversions · earned · pending · CR
      * 7-day activity strip
      * Quick actions
      * Recent conversions (last 10)
      * Top performing links (top 5 by clicks)
    """
    from datetime import timedelta

    from django.db.models import Sum
    from django.utils import timezone

    from plugins.installed.affiliates.models import (
        Affiliate,
        AffiliateClick,
        AffiliateConversion,
        AffiliateLink,
    )
    from plugins.installed.affiliates.services import pending_payout_amount

    accounts = list(Affiliate.objects.filter(user=request.user).select_related('program'))
    now = timezone.now()

    for a in accounts:
        if a.status != 'approved':
            a.tracked_links = []
            a.stats = None
            a.recent_conversions = []
            a.top_links = []
            a.spark = []
            a.pending_earnings = None
            continue

        link_qs = AffiliateLink.objects.filter(affiliate=a)
        click_qs = AffiliateClick.objects.filter(link__affiliate=a)
        conv_qs = AffiliateConversion.objects.filter(affiliate=a)

        clicks_total = click_qs.count()
        convs_total = conv_qs.count()
        approved_conv_total = conv_qs.filter(status='approved').count()
        cr = round((convs_total / clicks_total * 100), 1) if clicks_total else 0.0

        # Pending earnings = approved-but-unpaid commission.
        try:
            pending = pending_payout_amount(a)
        except Exception:  # noqa: BLE001
            pending = None

        # 7-day activity bins (per-day counts for clicks/conversions).
        spark = []
        for i in range(6, -1, -1):
            day_start = (now - timedelta(days=i)).replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            day_end = day_start + timedelta(days=1)
            spark.append(
                {
                    'date': day_start,
                    'clicks': click_qs.filter(
                        occurred_at__gte=day_start,
                        occurred_at__lt=day_end,
                    ).count(),
                    'conversions': conv_qs.filter(
                        created_at__gte=day_start,
                        created_at__lt=day_end,
                    ).count(),
                }
            )

        clicks_7d = sum(b['clicks'] for b in spark)
        convs_7d = sum(b['conversions'] for b in spark)

        a.stats = {
            'clicks_total': clicks_total,
            'convs_total': convs_total,
            'approved_conv_total': approved_conv_total,
            'cr': cr,
            'clicks_7d': clicks_7d,
            'convs_7d': convs_7d,
        }
        a.pending_earnings = pending
        a.recent_conversions = list(
            conv_qs.select_related('order').order_by('-created_at')[:10],
        )
        # Top performing links by click_count.
        top = list(link_qs.order_by('-click_count', '-conversion_count')[:5])
        for tl in top:
            tl.cr = (
                round((tl.conversion_count / tl.click_count * 100), 1) if tl.click_count else 0.0
            )
        a.top_links = top
        a.spark = spark
        # Keep a small tracked_links slice for the dashboard sidebar (if any
        # template needs it). The full inventory lives on /links/.
        a.tracked_links = list(link_qs.order_by('-created_at')[:8])
        # Aggregate lifetime commission across all conversions (approved
        # contributes to accrued_balance; this is a display total).
        agg = conv_qs.exclude(status='rejected').aggregate(total=Sum('commission'))
        a.lifetime_earned_amount = agg['total']

    return render(
        request,
        'affiliates/dashboard.html',
        {
            'accounts': accounts,
            'site_base': request.build_absolute_uri('/').rstrip('/'),
            'seo_title': 'Your affiliate dashboard',
        },
    )


@login_required(login_url='/auth/login/')
@require_http_methods(['POST'])
def create_link(request: HttpRequest) -> HttpResponseRedirect:
    """Create a tracked affiliate link from the dashboard's inline form."""
    from plugins.installed.affiliates.models import Affiliate, AffiliateLink

    affiliate_id = request.POST.get('affiliate_id') or ''
    landing_url = (request.POST.get('landing_url') or '/')[:500]
    label = (request.POST.get('label') or '').strip()[:100]
    return_to = request.POST.get('return_to') or '/affiliates/me/'
    if not return_to.startswith('/affiliates/'):
        return_to = '/affiliates/me/'

    try:
        affiliate = Affiliate.objects.get(pk=affiliate_id, user=request.user)
    except Affiliate.DoesNotExist:
        return HttpResponseRedirect('/affiliates/me/')

    if affiliate.status == 'approved':
        AffiliateLink.objects.create(
            affiliate=affiliate,
            landing_url=landing_url or '/',
            label=label,
        )
    return HttpResponseRedirect(return_to)


# ─── Links inventory ──────────────────────────────────────────────────


@login_required(login_url='/auth/login/')
def links(request: HttpRequest) -> HttpResponse:
    """Full inventory of an affiliate's tracked links + search/filter."""
    from plugins.installed.affiliates.models import AffiliateLink

    affiliate, bounce = _affiliate_or_redirect(request)
    if bounce is not None:
        return bounce

    q = (request.GET.get('q') or '').strip()
    status = (request.GET.get('status') or '').strip()

    qs = AffiliateLink.objects.filter(affiliate=affiliate)
    if q:
        from django.db.models import Q

        qs = qs.filter(Q(code__icontains=q) | Q(label__icontains=q))
    if status == 'active':
        qs = qs.filter(is_active=True)
    elif status == 'inactive':
        qs = qs.filter(is_active=False)
    qs = qs.order_by('-created_at')

    return render(
        request,
        'affiliates/links.html',
        {
            'affiliate': affiliate,
            'links': list(qs[:200]),
            'q': q,
            'status': status,
            'site_base': request.build_absolute_uri('/').rstrip('/'),
            'share_text': 'Books worth your shelf — take a look:',
            'share_subject': 'A book recommendation',
            'seo_title': 'Your tracked links',
        },
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


# ─── Conversions log ──────────────────────────────────────────────────


@login_required(login_url='/auth/login/')
def conversions(request: HttpRequest) -> HttpResponse:
    """Conversion log + optional CSV export."""
    from plugins.installed.affiliates.models import AffiliateConversion

    affiliate, bounce = _affiliate_or_redirect(request)
    if bounce is not None:
        return bounce

    status = (request.GET.get('status') or '').strip()
    qs = (
        AffiliateConversion.objects.filter(affiliate=affiliate)
        .select_related('order')
        .order_by('-created_at')
    )
    if status in ('approved', 'pending', 'rejected', 'refunded', 'paid'):
        qs = qs.filter(status=status)

    if request.GET.get('export') == 'csv':
        import csv
        from io import StringIO

        buf = StringIO()
        w = csv.writer(buf)
        w.writerow(['date', 'order_number', 'gross', 'commission', 'status'])
        for c in qs[:1000]:
            order_number = getattr(c.order, 'order_number', str(c.order_id))
            gross = getattr(c.order, 'total', '')
            w.writerow(
                [
                    c.created_at.isoformat(),
                    order_number,
                    str(gross),
                    str(c.commission),
                    c.status,
                ]
            )
        response = HttpResponse(buf.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = (
            f'attachment; filename="conversions-{affiliate.handle}.csv"'
        )
        return response

    return render(
        request,
        'affiliates/conversions.html',
        {
            'affiliate': affiliate,
            'conversions': list(qs[:100]),
            'status': status,
            'seo_title': 'Conversions',
        },
    )


# ─── Payouts ──────────────────────────────────────────────────────────


def _min_payout_threshold(affiliate):
    """Read the program's minimum_payout, falling back to $25."""
    from djmoney.money import Money

    try:
        program_min = affiliate.program.minimum_payout
        if program_min and program_min.amount > 0:
            return program_min
    except Exception:  # noqa: BLE001
        pass
    return Money(25, str(affiliate.accrued_balance.currency))


@login_required(login_url='/auth/login/')
@require_http_methods(['GET', 'POST'])
def payouts(request: HttpRequest) -> HttpResponse:
    """Pending earnings card + request-payout form + past payouts table."""
    from plugins.installed.affiliates.models import AffiliatePayout
    from plugins.installed.affiliates.services import (
        has_pending_payout,
        pending_payout_amount,
        request_affiliate_payout,
    )

    affiliate, bounce = _affiliate_or_redirect(request)
    if bounce is not None:
        return bounce

    error = ''
    success = ''

    if request.method == 'POST':
        method = (request.POST.get('method') or '').strip()[:40]
        try:
            payout = request_affiliate_payout(affiliate, method=method)
            success = (
                f'Payout request for {payout.amount} submitted. '
                'We process requests on the 1st of the following month.'
            )
        except ValueError as exc:
            error = str(exc)

    pending = pending_payout_amount(affiliate)
    threshold = _min_payout_threshold(affiliate)
    pending_exists = has_pending_payout(affiliate)

    can_request = not pending_exists and pending.amount >= threshold.amount and pending.amount > 0

    history = list(
        AffiliatePayout.objects.filter(affiliate=affiliate).order_by('-requested_at')[:50]
    )

    return render(
        request,
        'affiliates/payouts.html',
        {
            'affiliate': affiliate,
            'pending_earnings': pending,
            'threshold': threshold,
            'pending_exists': pending_exists,
            'can_request': can_request,
            'history': history,
            'error': error,
            'success': success,
            'seo_title': 'Payouts',
        },
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
    site_base = request.build_absolute_uri('/').rstrip('/')
    for w in rows:
        w.iframe_src = f'{site_base}/affiliates/embed/{w.key}/'
        w.js_src = f'{site_base}/affiliates/embed/{w.key}.js'
        w.json_src = f'{site_base}/api/affiliates/widget/{w.key}.json'

    return render(
        request,
        'affiliates/widgets.html',
        {
            'affiliate': affiliate,
            'widgets': rows,
            'categories': _widget_categories(),
            'site_base': site_base,
            'seo_title': 'Embeddable widgets',
        },
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

        valid_methods = {k for k, _ in method_choices}
        if method not in valid_methods:
            error = 'Pick a valid payout method.'
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
        {
            'affiliate': affiliate,
            'method_choices': method_choices,
            'saved': saved,
            'error': error,
            'seo_title': 'Affiliate settings',
        },
    )


@login_required(login_url='/auth/login/')
def leaderboard(request: HttpRequest) -> HttpResponse:
    """Top affiliates by sales driven — a motivational leaderboard. Shows
    pseudonymous @handles + sales counts (never others' earnings) and
    highlights the viewer's own position."""
    from django.db.models import Count, Q

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
    for i, a in enumerate(ranked, start=1):
        is_me = a.id == affiliate.id
        if is_me:
            my_rank = i
        rows.append({'rank': i, 'name': f'@{a.handle}', 'sales': a.sales, 'is_me': is_me})
    my_sales = AffiliateConversion.objects.filter(
        affiliate=affiliate, status__in=['approved', 'paid']
    ).count()
    return render(
        request,
        'affiliates/leaderboard.html',
        {
            'affiliate': affiliate,
            'rows': rows,
            'my_rank': my_rank,
            'my_sales': my_sales,
            'seo_title': 'Affiliate leaderboard',
        },
    )


@login_required(login_url='/auth/login/')
def creatives(request: HttpRequest) -> HttpResponse:
    """Affiliate-facing marketing creatives library — grab a banner/cover +
    swipe copy, then spin a tracked link to its target in one click."""
    from plugins.installed.affiliates.models import AffiliateCreative

    affiliate, bounce = _affiliate_or_redirect(request)
    if bounce is not None:
        return bounce

    return render(
        request,
        'affiliates/creatives.html',
        {
            'affiliate': affiliate,
            'creatives': list(AffiliateCreative.objects.filter(is_active=True)),
            'seo_title': 'Marketing creatives',
        },
    )
