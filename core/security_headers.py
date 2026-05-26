"""Security response headers that Django's SecurityMiddleware doesn't set.

Permissions-Policy disables browser capabilities the storefront never
needs (camera, microphone, geolocation, etc.), shrinking the
client-side attack surface and opting out of FLoC/Topics tracking.

Content-Security-Policy ships in report-only mode (per the 2026
architecture audit P2-E). Report-only lets us learn the actual
violation surface from production traffic before turning on
enforcement — the live storefront pulls TipTap, Stripe.js, Lucide
icons, PDF.js, StPageFlip from a handful of CDNs, plus inline styles
+ scripts on most pages. Switching straight to enforcing CSP would
break the storefront; report-only gives us the violation data without
the breakage.
"""
from __future__ import annotations


_PERMISSIONS_POLICY_VALUE = ', '.join([
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
])

# CSP — report-only for now. Allows the CDN hosts the storefront + admin
# currently use; inline styles + scripts are allowed (we have a lot of
# them today). After ~2 weeks of report data we can tighten this:
#   - swap unsafe-inline for nonce-based scripts (Django already supports
#     CSP nonces via django-csp middleware; we'd add it then).
#   - move from report-only to enforcing.
_CSP_REPORT_ONLY = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
        "https://cdn.jsdelivr.net "
        "https://cdnjs.cloudflare.com "
        "https://unpkg.com "
        "https://js.stripe.com "
        "https://maps.googleapis.com",
    "style-src 'self' 'unsafe-inline' "
        "https://fonts.googleapis.com "
        "https://cdn.jsdelivr.net",
    "img-src 'self' data: blob: https:",
    "font-src 'self' data: https://fonts.gstatic.com https://cdn.jsdelivr.net",
    "connect-src 'self' "
        "https://api.stripe.com "
        "https://api.cloudflare.com "
        "https://cdn.jsdelivr.net "
        "https://cdnjs.cloudflare.com",
    "frame-src 'self' https://js.stripe.com https://hooks.stripe.com",
    "worker-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self' https://checkout.stripe.com",
    "frame-ancestors 'none'",
    "report-uri /api/csp-report/",
])


class SecurityHeadersMiddleware:
    """Adds headers Django doesn't ship by default."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not response.has_header('Permissions-Policy'):
            response['Permissions-Policy'] = _PERMISSIONS_POLICY_VALUE
        if not response.has_header('Content-Security-Policy-Report-Only'):
            # Report-only — no enforcement, just collects violation
            # reports. Skip on /admin/ (Django Admin uses inline event
            # handlers we don't control) and /static/.
            path = getattr(request, 'path', '') or ''
            if not (path.startswith('/admin/') or path.startswith('/static/')):
                response['Content-Security-Policy-Report-Only'] = _CSP_REPORT_ONLY
        return response
