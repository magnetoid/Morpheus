"""Booking marketplace — storefront views (only wired while the plugin is on)."""

from __future__ import annotations

import datetime

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from plugins.installed.booking_marketplace.models import BookableService, Booking
from plugins.installed.booking_marketplace.services import upcoming_slots


def services_list(request):
    """Browse bookable services across all vendors."""
    services = BookableService.objects.filter(
        is_active=True, vendor__is_active=True
    ).select_related('vendor')
    return render(
        request,
        'booking_marketplace/list.html',
        {'services': services},
    )


def service_detail(request, slug):
    service = get_object_or_404(
        BookableService.objects.select_related('vendor'), slug=slug, is_active=True
    )
    slots = upcoming_slots(service)

    if request.method == 'POST':
        return _create_booking(request, service, slots)

    return render(
        request,
        'booking_marketplace/detail.html',
        {'service': service, 'slots': slots},
    )


def _create_booking(request, service, slots):
    raw = (request.POST.get('slot') or '').strip()
    name = (request.POST.get('name') or '').strip()
    email = (request.POST.get('email') or '').strip()
    notes = (request.POST.get('notes') or '').strip()

    if not (raw and name and email):
        messages.error(request, 'Please pick a slot and fill in your name and email.')
        return redirect(service_detail_url(service))

    # Parse the chosen slot and confirm it's still on offer (guards double-book).
    chosen = None
    for s in slots:
        if s.isoformat() == raw:
            chosen = s
            break
    if chosen is None:
        messages.error(request, 'That slot is no longer available — please pick another.')
        return redirect(service_detail_url(service))

    Booking.objects.create(
        service=service,
        customer=request.user if request.user.is_authenticated else None,
        customer_name=name,
        customer_email=email,
        start_at=chosen,
        end_at=chosen + datetime.timedelta(minutes=service.duration_minutes or 60),
        status='pending',
        notes=notes,
        price=service.price,
    )
    messages.success(
        request,
        f'Booked {service.name} for {timezone.localtime(chosen):%a %d %b, %H:%M}. '
        f'{service.vendor.name} will confirm shortly.',
    )
    return redirect(service_detail_url(service))


def service_detail_url(service) -> str:
    return f'/bookings/{service.slug}/'
