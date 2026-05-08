"""Two views drive the passwordless flow.

  GET  /auth/otp/         — form: enter your email
  POST /auth/otp/         — issue + send code, redirect to /auth/otp/verify/
  GET  /auth/otp/verify/  — form: enter the 6-digit code
  POST /auth/otp/verify/  — consume + login + redirect to ?next= or /account/

The email is held in the session between the two POSTs so the verify
form doesn't have to ask for it again — better UX, and prevents code-
substitution attacks where a user pastes a code into a different
email's form.
"""
from __future__ import annotations

import logging

from django.contrib.auth import login
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from core.auth.services import consume_otp, issue_otp, send_otp_email

logger = logging.getLogger('morpheus.core.auth.views')


def _client_ip(request: HttpRequest) -> str | None:
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',', 1)[0].strip() or None
    return request.META.get('REMOTE_ADDR') or None


def _safe_next(request: HttpRequest) -> str:
    """Pick a redirect target. Only honour same-origin paths."""
    nxt = (request.POST.get('next') or request.GET.get('next') or '').strip()
    if nxt.startswith('/') and not nxt.startswith('//'):
        return nxt
    return '/account/'


@csrf_protect
@require_http_methods(['GET', 'POST'])
def otp_request(request: HttpRequest) -> HttpResponse:
    error = ''
    nxt = _safe_next(request)

    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip().lower()
        if not email or '@' not in email:
            error = 'Enter a valid email address.'
        else:
            code, obj = issue_otp(email, request_ip=_client_ip(request))
            if code:
                send_otp_email(to=email, code=code)
            # Even on rate-cap we proceed to the verify step + show a
            # generic message so we don't leak rate-cap state.
            request.session['morph_otp_email'] = email
            request.session['morph_otp_next'] = nxt
            return redirect(reverse('core_auth:otp_verify'))

    return render(request, 'account/otp_request.html', {
        'error': error,
        'next': nxt,
        'prefill_email': request.session.get('morph_otp_email', ''),
    })


@csrf_protect
@require_http_methods(['GET', 'POST'])
def otp_verify(request: HttpRequest) -> HttpResponse:
    email = request.session.get('morph_otp_email', '')
    nxt = request.session.get('morph_otp_next') or _safe_next(request)
    error = ''

    if not email:
        # Drop straight back to the email step if the session lost it
        # (cookies cleared, took >30 min, etc.).
        return redirect(reverse('core_auth:otp_request'))

    if request.method == 'POST':
        code = (request.POST.get('code') or '').strip()
        # Allow a 6-digit code with stray spaces / dashes.
        code = ''.join(ch for ch in code if ch.isdigit())
        user = consume_otp(email, code) if code else None
        if user is None:
            error = 'That code didn\'t work. Try again, or request a new one.'
        else:
            # Required when the project has multiple auth backends —
            # allauth registers more than one. Pin to the model backend.
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)
            request.session.pop('morph_otp_email', None)
            request.session.pop('morph_otp_next', None)
            return redirect(nxt)

    return render(request, 'account/otp_verify.html', {
        'email': email,
        'error': error,
        'next': nxt,
    })
