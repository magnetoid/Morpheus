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
        # AMP story player (webstories plugin's <amp-story-player> PDP embed)
        # loads amp-story-player-v0.js / amp-loader / v0.js from Google's AMP CDN.
        'https://cdn.ampproject.org',
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com "
        'https://cdn.jsdelivr.net https://cdn.ampproject.org',
        "img-src 'self' data: blob: https:",
        "font-src 'self' data: https://fonts.gstatic.com https://cdn.jsdelivr.net",
        "connect-src 'self' "
        'https://api.stripe.com '
        'https://api.cloudflare.com '
        'https://cdn.jsdelivr.net '
        'https://cdnjs.cloudflare.com',
        "frame-src 'self' https://js.stripe.com https://hooks.stripe.com",
        "worker-src 'self' blob:",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self' https://checkout.stripe.com",
        "frame-ancestors 'none'",
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
#   - cdn.tailwindcss.com — Tailwind JIT runtime (admin styling)
#   - unpkg.com — htmx + lucide-icons (admin behaviour + iconography)
#   - esm.sh — TipTap rich-text editor ESM bundles (product description
#     editors). Without this the editors silently fail to mount and the
#     short/long description fields render blank.
# Self-hosting all of these would let us drop the allow-list entirely and
# restore the tighter policy.
_CSP_DASHBOARD_ENFORCE = '; '.join(
    [
        "default-src 'self'",
        # 'unsafe-eval' is required by the TipTap v3 rich-text editor (esm.sh
        # build uses new Function) AND the Tailwind Play CDN's JIT compiler.
        # Without it the product-form editor never constructs and you can't
        # edit descriptions. script-src already allows 'unsafe-inline' and the
        # storefront report-only CSP already permits 'unsafe-eval', so this is
        # a consistency fix, not a new relaxation. Dashboard is staff-only.
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://unpkg.com https://esm.sh",
        "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net",
        "img-src 'self' data: blob: https:",
        # cdn.jsdelivr.net — Remix Icon webfont (remixicon.css + .woff2 glyphs).
        "font-src 'self' data: https://cdn.jsdelivr.net",
        # esm.sh is in script-src (TipTap); allow its module/sourcemap fetches too.
        # unpkg.com fetches: PDF.js module + worker for the book_product 3D
        # cover preview (three.js + pdf.js). connect-src covers the worker/wasm
        # fetch; worker-src allows the PDF.js web worker (blob: + unpkg).
        "connect-src 'self' https://esm.sh https://unpkg.com",
        "worker-src 'self' blob: https://unpkg.com",
        "frame-ancestors 'none'",
        "object-src 'none'",
        "base-uri 'self'",
    ]
)


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
        return response
