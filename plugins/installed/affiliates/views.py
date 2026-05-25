"""Storefront-side affiliate flows.

Three views:
  - `affiliate_redirect`  /r/<code>           — anonymous click → cookie + 302
  - `apply`               /affiliates/apply/  — signed-in customer submits an
                                                application; a pending row is
                                                created for admin review.
  - `dashboard`           /affiliates/me/     — signed-in approved affiliate sees
                                                their links + accrued balance,
                                                and can create new tracked links.
"""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

from morpheus.views import HttpRequest, HttpResponse, HttpResponseRedirect


_AFFILIATE_COOKIE = 'morph_aff'
_COOKIE_TTL = 60 * 60 * 24 * 30  # 30 days; programs may override via cookie_window_days


def affiliate_redirect(request: HttpRequest, code: str) -> HttpResponseRedirect:
    from plugins.installed.affiliates.services import record_click

    referer = request.headers.get('Referer', '')
    user_agent = request.headers.get('User-Agent', '')
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()

    link = record_click(code=code, referer=referer, user_agent=user_agent, ip=ip)
    landing = link.landing_url if link else '/'

    response = HttpResponseRedirect(landing)
    response.set_cookie(
        _AFFILIATE_COOKIE, code,
        max_age=_COOKIE_TTL, httponly=True, samesite='Lax',
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
            return render(request, 'affiliates/apply.html', {
                'error': 'No active affiliate program is currently accepting applications.',
                'existing': None, 'programs': [], 'seo_title': 'Become an affiliate',
            })

        # Generate a unique handle. Helper safely handles SSO users with
        # empty email + raises HandleUnavailable on collision exhaustion,
        # which we surface as a 200-with-form-error (not 403).
        from plugins.installed.affiliates.services import (
            HandleUnavailable, generate_unique_handle,
        )
        try:
            handle = generate_unique_handle(request.user, suggested=handle_raw)
        except HandleUnavailable:
            return render(request, 'affiliates/apply.html', {
                'error': "Couldn't pick a unique handle — try a different one.",
                'existing': None,
                'programs': list(AffiliateProgram.objects.filter(is_active=True)),
                'seo_title': 'Become an affiliate',
            })

        Affiliate.objects.create(
            program=program, user=request.user, handle=handle, status='pending',
            company=company, payout_email=payout_email, notes=notes,
        )
        return redirect('/affiliates/me/')

    return render(request, 'affiliates/apply.html', {
        'existing': existing,
        'programs': list(AffiliateProgram.objects.filter(is_active=True).order_by('name')),
        'seo_title': 'Become an affiliate',
        'seo_description': 'Earn a commission for every reader you send our way.',
    })


@login_required(login_url='/auth/login/')
def dashboard(request: HttpRequest) -> HttpResponse:
    """Affiliate dashboard for the signed-in customer.

    Surfaces (matching the 2026 Rewardful / Tapfiliate UX baseline):
      * KPI strip: clicks 30d, conversions 30d, commission accrued, EPC.
      * Tracked links list with copy-to-clipboard + per-link CR.
      * Recent conversions (last 10) so the affiliate sees the funnel
        working in close to real-time.
      * Metric definitions surfaced inline — research is unambiguous
        that affiliates trust dashboards that explain their math.
    """
    from datetime import timedelta
    from django.utils import timezone
    from plugins.installed.affiliates.models import (
        Affiliate, AffiliateClick, AffiliateConversion, AffiliateLink,
    )

    accounts = list(Affiliate.objects.filter(user=request.user).select_related('program'))
    since = timezone.now() - timedelta(days=30)

    # Per-account stats (cheap: 4 small COUNT/SUM queries each).
    for a in accounts:
        if a.status == 'approved':
            link_qs = AffiliateLink.objects.filter(affiliate=a)
            a.tracked_links = list(link_qs.order_by('-created_at')[:50])

            clicks_30d = AffiliateClick.objects.filter(
                link__affiliate=a, created_at__gte=since,
            ).count()
            conv_30d_qs = AffiliateConversion.objects.filter(
                affiliate=a, created_at__gte=since,
            )
            conversions_30d = conv_30d_qs.count()
            approved_conv_30d = conv_30d_qs.filter(status='approved').count()

            # Earnings per click (EPC) and conversion rate (CR).
            epc = (
                (float(a.accrued_balance.amount) / clicks_30d) if clicks_30d else 0
            )
            cr = ((conversions_30d / clicks_30d * 100) if clicks_30d else 0)

            a.stats = {
                'clicks_30d': clicks_30d,
                'conversions_30d': conversions_30d,
                'approved_conv_30d': approved_conv_30d,
                'epc': round(epc, 2),
                'cr': round(cr, 1),
            }
            a.recent_conversions = list(
                conv_30d_qs.order_by('-created_at')[:8]
            )
        else:
            a.tracked_links = []
            a.stats = None
            a.recent_conversions = []

    return render(request, 'affiliates/dashboard.html', {
        'accounts': accounts,
        'site_base': request.build_absolute_uri('/').rstrip('/'),
        'seo_title': 'Your affiliate dashboard',
    })


@login_required(login_url='/auth/login/')
@require_http_methods(['POST'])
def create_link(request: HttpRequest) -> HttpResponseRedirect:
    """Create a tracked affiliate link from the dashboard's inline form."""
    from plugins.installed.affiliates.models import Affiliate, AffiliateLink

    affiliate_id = request.POST.get('affiliate_id') or ''
    landing_url = (request.POST.get('landing_url') or '/')[:500]
    label = (request.POST.get('label') or '').strip()[:100]

    try:
        affiliate = Affiliate.objects.get(pk=affiliate_id, user=request.user)
    except Affiliate.DoesNotExist:
        return HttpResponseRedirect('/affiliates/me/')

    if affiliate.status == 'approved':
        AffiliateLink.objects.create(
            affiliate=affiliate, landing_url=landing_url or '/', label=label,
        )
    return HttpResponseRedirect('/affiliates/me/')
