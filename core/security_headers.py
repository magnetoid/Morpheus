"""Security response headers that Django's SecurityMiddleware doesn't set.

Permissions-Policy disables browser capabilities the storefront never
needs (camera, microphone, geolocation, etc.), shrinking the
client-side attack surface and opting out of FLoC/Topics tracking.
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


class SecurityHeadersMiddleware:
    """Adds headers Django doesn't ship by default."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not response.has_header('Permissions-Policy'):
            response['Permissions-Policy'] = _PERMISSIONS_POLICY_VALUE
        return response
