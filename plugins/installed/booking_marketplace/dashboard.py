"""Booking marketplace — dashboard page (bookings overview)."""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from plugins.installed.booking_marketplace.models import BookableService, Booking


@staff_member_required
def bookings_list(request):
    bookings = Booking.objects.select_related('service', 'service__vendor').order_by(
        '-booking_date', '-created_at'
    )[:100]
    return render(
        request,
        'booking_marketplace/dashboard/bookings.html',
        {
            'bookings': bookings,
            'service_count': BookableService.objects.count(),
            'pending_count': Booking.objects.filter(status='pending').count(),
        },
    )


# ── Enquiry inbox (experiences + stays) ──────────────────────────────────────
#
# While the marketplace is enquiry-only every lead is an Enquiry or a
# StayEnquiry, and listings have no owner accounts, so this page is the only
# place the operator sees them: 25 sat at 'new' for two months, seen by nobody.

ENQUIRY_STATUSES = ('new', 'contacted', 'closed')


def _enquiry_row(e) -> dict:
    when = ''
    if e.preferred_date:
        when = f'{e.preferred_date:%a %d %b %Y}' + (f' · {e.time_slot}' if e.time_slot else '')
    return {
        'kind': 'experience',
        'id': e.pk,
        'created_at': e.created_at,
        'listing': e.service.name if e.service_id else '—',
        'name': e.name,
        'email': e.email,
        'phone': e.phone,
        'when': when,
        'party': f'{e.guests} guest{"s" if e.guests != 1 else ""}' if e.guests else '',
        'message': e.message,
        'status': e.status,
        'reply_subject': f'Your enquiry about {e.service.name if e.service_id else "your booking"}',
    }


def _stay_enquiry_row(e) -> dict:
    when = ''
    if e.check_in:
        when = f'{e.check_in:%a %d %b}' + (f' → {e.check_out:%a %d %b %Y}' if e.check_out else '')
    listing = e.property.name if e.property_id else '—'
    if e.room_type_id:
        listing = f'{listing} · {e.room_type.name}'
    party = ' · '.join(
        p
        for p in (
            f'{e.rooms} room{"s" if e.rooms != 1 else ""}' if e.rooms else '',
            f'{e.adults} adult{"s" if e.adults != 1 else ""}' if e.adults else '',
            f'{e.children} child{"ren" if e.children != 1 else ""}' if e.children else '',
        )
        if p
    )
    return {
        'kind': 'stay',
        'id': e.pk,
        'created_at': e.created_at,
        'listing': listing,
        'name': e.name,
        'email': e.email,
        'phone': e.phone,
        'when': when,
        'party': party,
        'message': e.message,
        'status': e.status,
        'reply_subject': f'Your enquiry about {e.property.name if e.property_id else "your stay"}',
    }


@staff_member_required
def enquiries_list(request):
    from django.contrib import messages
    from django.shortcuts import redirect

    from plugins.installed.booking_marketplace.models import Enquiry, StayEnquiry

    if request.method == 'POST':
        model = StayEnquiry if request.POST.get('kind') == 'stay' else Enquiry
        new_status = request.POST.get('status', '')
        if new_status in ENQUIRY_STATUSES and model.objects.filter(
            pk=request.POST.get('id')
        ).update(status=new_status):
            messages.success(request, f'Enquiry marked {new_status}.')
        else:
            messages.error(request, 'That enquiry could not be updated.')
        return redirect(request.get_full_path())

    status = request.GET.get('status', 'new')
    if status not in (*ENQUIRY_STATUSES, 'all'):
        status = 'new'
    experiences = Enquiry.objects.select_related('service').order_by('-created_at')
    stays = StayEnquiry.objects.select_related('property', 'room_type').order_by('-created_at')
    if status != 'all':
        experiences = experiences.filter(status=status)
        stays = stays.filter(status=status)
    rows = sorted(
        [_enquiry_row(e) for e in experiences[:200]] + [_stay_enquiry_row(e) for e in stays[:200]],
        key=lambda row: row['created_at'],
        reverse=True,
    )
    counts = {
        s: Enquiry.objects.filter(status=s).count() + StayEnquiry.objects.filter(status=s).count()
        for s in ENQUIRY_STATUSES
    }
    return render(
        request,
        'booking_marketplace/dashboard/enquiries.html',
        {
            'rows': rows,
            'status': status,
            'tabs': [(s, counts[s]) for s in ENQUIRY_STATUSES],
            'statuses': ENQUIRY_STATUSES,
        },
    )


@staff_member_required
def stays_list(request):
    """Hotel and apartment bookings — which had no screen anywhere."""
    from django.utils import timezone

    from plugins.installed.booking_marketplace.models import StayBooking

    stays = StayBooking.objects.select_related('property', 'room_type').order_by('-check_in')[:200]
    upcoming = StayBooking.objects.filter(
        status='confirmed', check_out__gte=timezone.localdate()
    ).count()
    return render(
        request,
        'booking_marketplace/dashboard/stays.html',
        {'stays': stays, 'upcoming': upcoming},
    )
