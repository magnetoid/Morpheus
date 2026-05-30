"""Consent endpoints: save a decision, render the preferences page."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from plugins.installed.consent.services import (
    read_consent_from_cookie,
    write_consent,
)


def _safe_referer(request: HttpRequest) -> str:
    """Return the referer iff it points back at our host, else '/'."""
    referer = request.META.get('HTTP_REFERER', '')
    allowed_hosts = {request.get_host()}
    if referer and url_has_allowed_host_and_scheme(
        url=referer,
        allowed_hosts=allowed_hosts,
        require_https=request.is_secure(),
    ):
        return referer
    return '/'


@require_http_methods(['POST'])
def save(request: HttpRequest) -> HttpResponse:
    """Record a consent decision + bounce back to the referer.

    Three submission modes share this endpoint:
      * accept_all=1   → all categories on.
      * reject_all=1   → only necessary.
      * (neither)      → per-checkbox values.
    """
    if request.POST.get('accept_all'):
        analytics = marketing = functional = True
    elif request.POST.get('reject_all'):
        analytics = marketing = functional = False
    else:
        analytics = request.POST.get('analytics') == 'on'
        marketing = request.POST.get('marketing') == 'on'
        functional = request.POST.get('functional') == 'on'

    customer = request.user if getattr(request.user, 'is_authenticated', False) else None
    response = HttpResponseRedirect(_safe_referer(request))
    write_consent(
        request,
        response,
        analytics=analytics,
        marketing=marketing,
        functional=functional,
        customer=customer,
    )
    return response


@require_http_methods(['GET'])
def preferences(request: HttpRequest) -> HttpResponse:
    """Standalone settings page (footer link) so customers can change
    their decision after the banner has been dismissed. Reuses the same
    block template — the banner *is* the preferences UI."""
    return render(
        request,
        'consent/preferences.html',
        {
            'decision': read_consent_from_cookie(request),
            'force_show': True,
        },
    )
