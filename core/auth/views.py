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
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from core.auth.services import consume_otp, issue_otp, send_otp_email
from core.hooks import MorpheusEvents, hook_registry
from core.utils.rate_limit import RateLimitExceeded, check_and_consume

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

    return render(
        request,
        'account/otp_request.html',
        {
            'error': error,
            'next': nxt,
            'prefill_email': request.session.get('morph_otp_email', ''),
        },
    )


_OTP_VERIFY_MAX_ATTEMPTS = 5
_OTP_VERIFY_WINDOW_SECONDS = 15 * 60
_OTP_EMAIL_LOCK_TTL_SECONDS = 15 * 60
_OTP_EMAIL_FAIL_KEY = 'otp_verify_fails:{email}'
_OTP_EMAIL_LOCK_KEY = 'otp_verify_lock:{email}'


def _otp_locked_response(request: HttpRequest, email: str, nxt: str) -> HttpResponse:
    error = 'Too many attempts. Try again in 15 minutes.'
    resp = render(
        request,
        'account/otp_verify.html',
        {'email': email, 'error': error, 'next': nxt},
    )
    resp.status_code = 429
    return resp


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
        email_lower = email.strip().lower()
        ip = _client_ip(request) or 'unknown'

        # Per-email hard lock after 5 cumulative failures in 15 min —
        # blocks the whole email regardless of source IP so the attacker
        # can't IP-rotate around the per-(email,ip) limiter below.
        if cache.get(_OTP_EMAIL_LOCK_KEY.format(email=email_lower)):
            logger.warning('otp_verify: email locked %s', email_lower)
            return _otp_locked_response(request, email, nxt)

        # Per-(email, ip) sliding-window rate limit.
        try:
            check_and_consume(
                key=f'otp_verify:{email_lower}:{ip}',
                max_per_window=_OTP_VERIFY_MAX_ATTEMPTS,
                window_seconds=_OTP_VERIFY_WINDOW_SECONDS,
            )
        except RateLimitExceeded:
            logger.warning(
                'otp_verify: rate limit hit for %s ip=%s',
                email_lower,
                ip,
            )
            return _otp_locked_response(request, email, nxt)

        code = (request.POST.get('code') or '').strip()
        # Allow a 6-digit code with stray spaces / dashes.
        code = ''.join(ch for ch in code if ch.isdigit())
        user = consume_otp(email, code) if code else None
        if user is None:
            error = "That code didn't work. Try again, or request a new one."
            # Track cumulative failures per-email. When it hits 5, set a
            # 15-min lock — blocks all sources, not just this IP.
            fail_key = _OTP_EMAIL_FAIL_KEY.format(email=email_lower)
            try:
                fails = cache.incr(fail_key)
            except ValueError:
                cache.set(fail_key, 1, timeout=_OTP_EMAIL_LOCK_TTL_SECONDS)
                fails = 1
            if fails >= _OTP_VERIFY_MAX_ATTEMPTS:
                cache.set(
                    _OTP_EMAIL_LOCK_KEY.format(email=email_lower),
                    1,
                    timeout=_OTP_EMAIL_LOCK_TTL_SECONDS,
                )
                logger.warning(
                    'otp_verify: locking %s after %d cumulative failures',
                    email_lower,
                    fails,
                )
        else:
            # Successful verify clears any pending fail counter.
            cache.delete(_OTP_EMAIL_FAIL_KEY.format(email=email_lower))
            # Required when the project has multiple auth backends —
            # allauth registers more than one. Pin to the model backend.
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            # Second-factor extension point. Email-OTP is factor one; a
            # plugin (staff_mfa) may interpose a second factor here by
            # returning an HttpResponse (a redirect to its challenge view).
            # With no subscriber the value stays None and login proceeds
            # exactly as before — single-factor email-OTP.
            # Fail CLOSED: if a second-factor subscriber raises, do NOT log the
            # user in single-factor — the whole point of the gate is that an
            # enrolled staffer can't slip through on the first factor alone.
            try:
                second_factor = hook_registry.filter(
                    MorpheusEvents.AUTH_SECOND_FACTOR,
                    value=None,
                    request=request,
                    user=user,
                    next=nxt,
                    raise_errors=True,
                )
            except Exception:
                logger.exception(
                    'otp_verify: second-factor resolution failed for %s; refusing login',
                    email_lower,
                )
                error = 'We could not verify your second factor. Please try again.'
            else:
                if second_factor is not None:
                    return second_factor
                login(request, user)
                request.session.pop('morph_otp_email', None)
                request.session.pop('morph_otp_next', None)
                return redirect(nxt)

    return render(
        request,
        'account/otp_verify.html',
        {
            'email': email,
            'error': error,
            'next': nxt,
        },
    )
