"""Booking marketplace — dashboard page (bookings overview)."""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from plugins.installed.booking_marketplace.models import BookableService, Booking


@staff_member_required
def bookings_list(request):
    bookings = Booking.objects.select_related('service', 'service__vendor').order_by('-start_at')[
        :100
    ]
    return render(
        request,
        'booking_marketplace/dashboard/bookings.html',
        {
            'bookings': bookings,
            'service_count': BookableService.objects.count(),
            'pending_count': Booking.objects.filter(status='pending').count(),
        },
    )
