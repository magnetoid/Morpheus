"""Security response headers that Django's SecurityMiddleware doesn't set.

Permissions-Policy disables browser capabilities the storefront never
needs (camera, microphone, geolocation, etc.), shrinking the
client-side attack surface and opting out of FLoC/Topics tracking.

Content-Security-Policy ships in report-only mode on the storefront
(per the 2026 architecture audit P2-E). Report-only lets us learn the
actual violation surface from production traffic before turning on
enforcement — the live storefront pulls TipTap, Stripe.js, Lucide
icons, PDF.js, StPageFlip from a handful of CDNs, plus inline styles
+ scripts on most pages. Switching straight to enforcing CSP would
break the storefront; report-only gives us the violation data without
the breakage.

The /dashboard/ surface, by contrast, ships an *enforcing* CSP. Staff
render untrusted input (metafields, vendor copy, product descriptions)
in the admin — a stored-XSS there has direct access to staff sessions.
The admin policy is narrower than the storefront's: no CDNs, no
unsafe-eval, frame-ancestors 'none'. Toggle off with
``CSP_DASHBOARD_ENFORCE = False`` in dev if a feature legitimately
needs it.
"""

from __future__ import annotations

from django.conf import settings
from django.utils.cache import patch_cache_control
from django.utils.csp import CSP
from django.utils.html import format_html
from django.views.decorators.csp import csp_override

_PERMISSIONS_POLICY_VALUE = ', '.join(
    [
        'camera=()',
        'microphone=()',
        'geolocation=()',
        'payment=(self)',
        'usb=()',
        'magnetometer=()',
        'accelerometer=()',
        'gyroscope=()',
        'interest-cohort=()',
        'browsing-topics=()',
    ]
)

# CSP — report-only for now. Allows the CDN hosts the storefront + admin
# currently use; inline styles + scripts are allowed (we have a lot of
# them today). After ~2 weeks of report data we can tighten this:
#   - swap unsafe-inline for nonce-based scripts (Django already supports
#     CSP nonces via django-csp middleware; we'd add it then).
#   - move from report-only to enforcing.
_CSP_REPORT_ONLY = '; '.join(
    [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
        'https://cdn.jsdelivr.net '
        'https://cdnjs.cloudflare.com '
        'https://unpkg.com '
        'https://js.stripe.com '
        'https://maps.googleapis.com '
        # Cloudflare Web Analytics — the edge injects this beacon when the
        # merchant turns it on in Cloudflare.
        'https://static.cloudflareinsights.com '
        # AMP story player (webstories plugin's <amp-story-player> PDP embed)
        # loads amp-story-player-v0.js / amp-loader / v0.js from Google's AMP CDN.
        'https://cdn.ampproject.org',
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com "
        # unpkg.com — Leaflet's stylesheet on the travel store's map pages
        # (its script already loads from unpkg under script-src).
        'https://cdn.jsdelivr.net https://cdn.ampproject.org https://unpkg.com',
        "img-src 'self' data: blob: https:",
        "font-src 'self' data: https://fonts.gstatic.com https://cdn.jsdelivr.net",
        "connect-src 'self' "
        # The service worker caches the storefront's Google Fonts stylesheet and
        # files; its fetches are connect-src, and each one filed a violation.
        'https://fonts.googleapis.com https://fonts.gstatic.com '
        'https://api.stripe.com '
        'https://api.cloudflare.com '
        'https://cdn.jsdelivr.net '
        'https://cdnjs.cloudflare.com '
        # AMP story runtime fetches its strings; the Cloudflare beacon reports.
        'https://cdn.ampproject.org '
        'https://cloudflareinsights.com',
        "frame-src 'self' https://js.stripe.com https://hooks.stripe.com",
        "worker-src 'self' blob:",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self' https://checkout.stripe.com",
        # The store frames itself (Theme builder preview); nobody else may.
        "frame-ancestors 'self'",
        'report-uri /api/csp-report/',
    ]
)

# Enforcing CSP for /dashboard/. Narrower than the storefront report-only
# policy: limited CDN allow-list (only what base.html actually loads),
# no unsafe-eval, frame-ancestors 'none'. Staff-rendered untrusted content
# (metafields, vendor copy) is the XSS surface this is designed to
# neutralize.
#
# CDN allow-list rationale (TODO: self-host these to remove the allow-list):
#   - unpkg.com — htmx + lucide-icons (admin behaviour + iconography)
# The rich-text editor is self-hosted (richtext plugin: an eval-free Lexical
# bundle served from 'self'), so esm.sh is gone (it used to load TipTap), and
# Tailwind is a stylesheet built ahead of time (admin_dashboard/frontend), so
# the Play CDN and the 'unsafe-eval' its in-browser compiler needed are gone
# too (v0.136.0).
_CSP_DASHBOARD_ENFORCE = '; '.join(
    [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' https://unpkg.com",
        "style-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net",
        "img-src 'self' data: blob: https:",
        # cdn.jsdelivr.net — Remix Icon webfont (remixicon.css + .woff2 glyphs).
        "font-src 'self' data: https://cdn.jsdelivr.net",
        # unpkg.com fetches: PDF.js module + worker for the book_product 3D
        # cover preview (three.js + pdf.js). connect-src covers the worker/wasm
        # fetch; worker-src allows the PDF.js web worker (blob: + unpkg).
        "connect-src 'self' https://unpkg.com",
        "worker-src 'self' blob: https://unpkg.com",
        "frame-ancestors 'none'",
        "object-src 'none'",
        "base-uri 'self'",
    ]
)


# The origins a payment page's own markup loads scripts from, or tells the
# browser to load them from (an inline tag snippet that inserts its loader).
# docs/CHECKOUT_SCRIPTS.md is the inventory PCI DSS 6.4.3 asks for: every
# script, its owner and why it is there (core/tests/test_payment_page_csp.py
# keeps the two in step). In the policy they matter only to a browser without
# 'strict-dynamic': every current one runs a script only when its tag carries
# the page's nonce, and then whatever that script loads.
PAYMENT_PAGE_SCRIPT_ORIGINS = (
    'https://js.stripe.com',
    'https://*.js.stripe.com',
    'https://maps.googleapis.com',
    'https://www.googletagmanager.com',
    'https://cdn.jsdelivr.net',
    # The ad pixels' loaders, each inserted by the app's inline snippet.
    'https://connect.facebook.net',
    'https://analytics.tiktok.com',
    'https://s.pinimg.com',
    'https://sc-static.net',
    'https://www.redditstatic.com',
    'https://bat.bing.com',
)

# Where a payment page's forms may send the shopper. The one-page checkout
# answers a PayPal order with a redirect to PayPal's approval page, and a
# browser applies form-action to that redirect too.
PAYMENT_PAGE_FORM_TARGETS = ('https://www.paypal.com', 'https://www.sandbox.paypal.com')

# Enforced on every page where a shopper types an address or a card: the
# cart (wallet buttons), the checkout steps, saved cards and the membership
# card form. A script runs only when its tag carries the response's nonce
# (`nonce="{{ csp_nonce }}"`), so markup injected into the page runs nothing,
# and there is no 'unsafe-eval'. The other directives stay unrestricted here:
# the storefront's report-only policy is still learning them.
_PAYMENT_PAGE_CSP = {
    'script-src': [CSP.NONCE, CSP.STRICT_DYNAMIC, CSP.SELF, *PAYMENT_PAGE_SCRIPT_ORIGINS],
    'object-src': [CSP.NONE],
    'base-uri': [CSP.SELF],
    'frame-ancestors': [CSP.SELF],
    'form-action': [CSP.SELF, *PAYMENT_PAGE_FORM_TARGETS],
    'report-uri': '/api/csp-report/',
}


def payment_page(view):
    """Enforce the payment-page policy on `view` (django.middleware.csp writes it)."""
    return csp_override(_PAYMENT_PAGE_CSP)(view)


def script_nonce(context) -> str:
    """` nonce="…"` for a <script> a template tag writes, from the page's context.

    Empty outside a request (an email, a test without the middleware). A tag
    that writes a script takes the context for this (takes_context=True).
    """
    nonce = context.get('csp_nonce')
    return format_html(' nonce="{}"', nonce) if nonce is not None else ''


def dashboard_csp(*, frame_src: tuple[str, ...] = ()) -> str:
    """The enforced dashboard policy, letting one response frame `frame_src`.

    A dashboard page that embeds another origin (Help and About show the
    project website) sets this on its own response — the middleware leaves a
    response's own policy alone — so every other page still frames nothing.
    """
    if not frame_src:
        return _CSP_DASHBOARD_ENFORCE
    return f"{_CSP_DASHBOARD_ENFORCE}; frame-src 'self' {' '.join(frame_src)}"


class SecurityHeadersMiddleware:
    """Adds headers Django doesn't ship by default."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not response.has_header('Permissions-Policy'):
            response['Permissions-Policy'] = _PERMISSIONS_POLICY_VALUE
        path = getattr(request, 'path', '') or ''
        # Enforcing CSP on /dashboard/ — staff-rendered untrusted content
        # (metafields, vendor copy) is the XSS surface we're hardening.
        # Toggleable via CSP_DASHBOARD_ENFORCE for dev workflows.
        dashboard_enforce = path.startswith('/dashboard/') and getattr(
            settings, 'CSP_DASHBOARD_ENFORCE', True
        )
        if dashboard_enforce and not response.has_header('Content-Security-Policy'):
            response['Content-Security-Policy'] = _CSP_DASHBOARD_ENFORCE
        elif (
            not dashboard_enforce
            # A payment page enforces its own policy (payment_page above).
            and not response.has_header('Content-Security-Policy')
            and not response.has_header('Content-Security-Policy-Report-Only')
            and not path.startswith('/admin/')
            and not path.startswith('/static/')
            and not path.startswith('/dashboard/')
        ):
            # Report-only — no enforcement, just collects violation reports.
            # Skip on /admin/ (Django Admin uses inline event handlers we
            # don't control), /static/, and /dashboard/ (the Morpheus admin
            # ships heavy inline styles/scripts that flood /api/csp-report/
            # into 429s; report telemetry is for hardening the public
            # storefront, not the authenticated staff area — which now gets
            # its own narrower *enforcing* CSP above).
            response['Content-Security-Policy-Report-Only'] = _CSP_REPORT_ONLY
        if path.startswith('/dashboard/'):
            # Cloudflare's Email Address Obfuscation rewrites every address in an
            # HTML page into "[email protected]" and decodes it with a script that
            # runs once per full page load. The dashboard body is hx-boost, so a
            # page reached by a link was never decoded; `no-transform` is the
            # header Cloudflare documents for leaving a response's body alone.
            patch_cache_control(response, no_transform=True)
        return response
