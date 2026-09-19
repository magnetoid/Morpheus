"""Customer-facing "My bookings" account page.

Renders the signed-in customer's experience ``Booking``s and hotel
``StayBooking``s in one place. Lives here (not in ``storefront``) because it is
booking-specific: when this plugin is disabled the route disappears entirely
(ADR 0013), and the montenegro theme's ``storefront/base.html`` only links to
it while the theme — which ``requires_plugins = ['booking_marketplace']`` — is
active.

The template ``storefront/account_bookings.html`` is supplied by the theme,
not this plugin (it lives under ``themes/library/montenegro/templates/``), so
the page only renders on the store that owns the booking vertical.
"""

from __future__ import annotations

from morpheus.app.views import render


def _login_required(request, target):
    if not request.user.is_authenticated:
        from django.shortcuts import redirect

        return redirect(f'/auth/login/?next={target}')
    return None


def account_bookings(request):
    redirect_resp = _login_required(request, '/account/bookings/')
    if redirect_resp is not None:
        return redirect_resp

    from plugins.installed.booking_marketplace.models import Booking, StayBooking

    experience_bookings = list(
        Booking.objects.filter(customer=request.user)
        .select_related('service')
        .order_by('-booking_date', '-created_at')[:50]
    )
    stay_bookings = list(
        StayBooking.objects.filter(customer=request.user)
        .select_related('property', 'room_type')
        .order_by('-check_in', '-created_at')[:50]
    )
    return render(
        request,
        'storefront/account_bookings.html',
        {
            'experience_bookings': experience_bookings,
            'stay_bookings': stay_bookings,
            'has_bookings': bool(experience_bookings or stay_bookings),
        },
    )
