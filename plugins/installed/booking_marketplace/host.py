"""Booking marketplace — host self-serve views.

A host (a catalog.Vendor owner) manages their own experiences, availability
and bookings/enquiries under /bookings/host/. Ownership is always re-checked
server-side (never trust the URL). Pages are storefront-themed so non-staff
host users get the montenegro look without the admin dashboard.
"""

from __future__ import annotations

import datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import (
    REGIONS,
    AddOn,
    AvailabilityWindow,
    BookableService,
    Booking,
    Enquiry,
    PricingTier,
    ServiceImage,
)

_ACTIONS = {'confirm': 'confirmed', 'cancel': 'cancelled', 'complete': 'completed'}


def _host_vendor(user):
    """The active vendor owned by this user, or None (same rule as marketplace)."""
    from plugins.installed.catalog.models import Vendor

    return Vendor.objects.filter(owner=user, is_active=True).first()


def _not_host(request):
    return render(request, 'booking_marketplace/host/not_host.html', {'seo_title': 'Become a host'})


def _int(value, default):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _unique_slug(name, exclude_pk=None):
    base = slugify(name) or 'experience'
    slug, i = base, 2
    qs = BookableService.objects.all()
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    while qs.filter(slug=slug).exists():
        slug, i = f'{base}-{i}', i + 1
    return slug


@login_required(login_url='/auth/login/')
def host_services(request):
    vendor = _host_vendor(request.user)
    if vendor is None:
        return _not_host(request)
    services = BookableService.objects.filter(vendor=vendor).select_related('category')
    return render(
        request,
        'booking_marketplace/host/services.html',
        {
            'vendor': vendor,
            'services': services,
            'pending_bookings': Booking.objects.filter(
                service__vendor=vendor, status='pending'
            ).count(),
            'new_enquiries': Enquiry.objects.filter(service__vendor=vendor, status='new').count(),
            'seo_title': 'Your experiences',
        },
    )


def _dec_or_none(value):
    try:
        return Decimal(value) if (value or '').strip() else None
    except (InvalidOperation, TypeError):
        return None


def _apply_service_fields(svc, vendor, request, name):
    """Set every scalar field off the POST onto `svc` (created if None) and save."""
    from plugins.installed.catalog.models import Category

    if svc is None:
        svc = BookableService(vendor=vendor, slug=_unique_slug(name))
    svc.name = name
    svc.short_description = (request.POST.get('short_description') or '').strip()
    svc.description = (request.POST.get('description') or '').strip()
    region = (request.POST.get('region') or '').strip()
    svc.region = region if region in dict(REGIONS) else ''
    cat_id = request.POST.get('category') or ''
    svc.category = Category.objects.filter(pk=cat_id).first() if cat_id else None
    try:
        amount = Decimal(request.POST.get('price') or '0')
    except (InvalidOperation, TypeError):
        amount = Decimal('0')
    svc.price = Money(amount, 'EUR')
    svc.duration_minutes = _int(request.POST.get('duration_minutes'), 60)
    svc.daily_capacity = _int(request.POST.get('daily_capacity'), 10)
    svc.max_guests_per_booking = _int(request.POST.get('max_guests_per_booking'), 10)
    svc.cancellation_policy = (request.POST.get('cancellation_policy') or '').strip()
    svc.is_active = request.POST.get('is_active') == 'on'
    img = request.FILES.get('image')
    if img:
        svc.image = img
    kind = (request.POST.get('listing_kind') or 'experience').strip()
    svc.listing_kind = kind if kind in dict(BookableService.LISTING_KINDS) else 'experience'
    svc.meeting_point = (request.POST.get('meeting_point') or '').strip()
    svc.languages = [
        s.strip() for s in (request.POST.get('languages') or '').split(',') if s.strip()
    ]
    svc.what_to_bring = [
        s.strip() for s in (request.POST.get('what_to_bring') or '').splitlines() if s.strip()
    ]
    svc.latitude = _dec_or_none(request.POST.get('latitude'))
    svc.longitude = _dec_or_none(request.POST.get('longitude'))
    svc.save()
    return svc


def _save_availability(svc, post):
    """Replace availability weekdays (with optional per-weekday start times)."""
    AvailabilityWindow.objects.filter(service=svc).delete()
    for wd in post.getlist('weekdays'):
        try:
            wd_i = int(wd)
        except (TypeError, ValueError):
            continue
        raw = (post.get(f'start_time_{wd}') or '').strip()
        for part in [p.strip() for p in raw.split(',') if p.strip()] or [None]:
            st = None
            if part:
                try:
                    st = datetime.time.fromisoformat(part)
                except ValueError:
                    st = None
            AvailabilityWindow.objects.create(service=svc, weekday=wd_i, start_time=st)


def _save_pricing(svc, post):
    """Replace pricing tiers + add-ons from the repeated form rows."""
    PricingTier.objects.filter(service=svc).delete()
    names = post.getlist('tier_name')
    prices = post.getlist('tier_price')
    for i, (raw_name, pr) in enumerate(zip(names, prices, strict=False)):
        tier_name = (raw_name or '').strip()
        if not tier_name:
            continue
        try:
            amt = Decimal(pr or '0')
        except (InvalidOperation, TypeError):
            amt = Decimal('0')
        PricingTier.objects.create(
            service=svc, name=tier_name, price=Money(amt, 'EUR'), sort_order=i
        )

    AddOn.objects.filter(service=svc).delete()
    anames = post.getlist('addon_name')
    aprices = post.getlist('addon_price')
    atypes = post.getlist('addon_type')
    for i, raw_name in enumerate(anames):
        addon_name = (raw_name or '').strip()
        if not addon_name:
            continue
        try:
            amt = Decimal(aprices[i] if i < len(aprices) else '0')
        except (InvalidOperation, TypeError):
            amt = Decimal('0')
        ptype = atypes[i] if i < len(atypes) else 'per_person'
        AddOn.objects.create(
            service=svc,
            name=addon_name,
            price=Money(amt, 'EUR'),
            price_type=ptype if ptype in ('per_person', 'per_booking') else 'per_person',
            sort_order=i,
        )


@login_required(login_url='/auth/login/')
@require_http_methods(['GET', 'POST'])
def host_service_form(request, slug=None):
    vendor = _host_vendor(request.user)
    if vendor is None:
        return _not_host(request)

    svc = get_object_or_404(BookableService, slug=slug, vendor=vendor) if slug else None

    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        if not name:
            messages.error(request, 'A name is required.')
        else:
            svc = _apply_service_fields(svc, vendor, request, name)
            _save_availability(svc, request.POST)
            _save_pricing(svc, request.POST)
            for f in request.FILES.getlist('gallery'):
                ServiceImage.objects.create(service=svc, image=f)

            messages.success(request, f'Saved “{svc.name}”.')
            return redirect('/bookings/host/')

    from plugins.installed.catalog.models import Category

    selected = (
        set(AvailabilityWindow.objects.filter(service=svc).values_list('weekday', flat=True))
        if svc
        else set()
    )

    from collections import defaultdict

    st_map = defaultdict(list)
    if svc:
        for w in AvailabilityWindow.objects.filter(service=svc):
            if w.start_time:
                st_map[w.weekday].append(w.start_time.strftime('%H:%M'))
    start_times = {k: ', '.join(v) for k, v in st_map.items()}

    return render(
        request,
        'booking_marketplace/host/service_form.html',
        {
            'vendor': vendor,
            'svc': svc,
            'categories': Category.objects.filter(is_active=True).order_by('name'),
            'regions': REGIONS,
            'weekdays': AvailabilityWindow.WEEKDAYS,
            'selected_wd': selected,
            'start_times': start_times,
            'listing_kinds': BookableService.LISTING_KINDS,
            'seo_title': 'Edit experience' if svc else 'New experience',
        },
    )


@login_required(login_url='/auth/login/')
@require_http_methods(['GET', 'POST'])
def host_bookings(request):
    vendor = _host_vendor(request.user)
    if vendor is None:
        return _not_host(request)

    if request.method == 'POST':
        b = Booking.objects.filter(
            pk=request.POST.get('booking_id'), service__vendor=vendor
        ).first()
        new_status = _ACTIONS.get(request.POST.get('action'))
        if b and new_status:
            b.status = new_status
            b.save(update_fields=['status'])
            messages.success(request, f'Booking marked {new_status}.')
        else:
            messages.error(request, 'Could not update that booking.')
        return redirect('/bookings/host/bookings/')

    bookings = (
        Booking.objects.filter(service__vendor=vendor)
        .select_related('service')
        .order_by('-booking_date', '-created_at')[:200]
    )
    return render(
        request,
        'booking_marketplace/host/bookings.html',
        {'vendor': vendor, 'bookings': bookings, 'seo_title': 'Your bookings'},
    )


@login_required(login_url='/auth/login/')
def host_enquiries(request):
    vendor = _host_vendor(request.user)
    if vendor is None:
        return _not_host(request)
    enquiries = (
        Enquiry.objects.filter(service__vendor=vendor)
        .select_related('service')
        .order_by('-created_at')[:200]
    )
    return render(
        request,
        'booking_marketplace/host/enquiries.html',
        {'vendor': vendor, 'enquiries': enquiries, 'seo_title': 'Your enquiries'},
    )


@login_required(login_url='/auth/login/')
def host_earnings(request):
    """Host payout summary from confirmed/completed bookings (EUR).

    gross = what guests paid · fees = 12% platform fee · net = host take-home
    (the per-guest price subtotal). All booking money is already stored in EUR.
    """
    vendor = _host_vendor(request.user)
    if vendor is None:
        return _not_host(request)

    paid = Booking.objects.filter(service__vendor=vendor, status__in=('confirmed', 'completed'))
    gross = fees = net = Decimal('0')
    for b in paid:
        gross += b.total_price.amount
        fees += b.service_fee.amount
        net += b.subtotal.amount

    return render(
        request,
        'booking_marketplace/host/earnings.html',
        {
            'vendor': vendor,
            'gross': gross,
            'fees': fees,
            'net': net,
            'count': paid.count(),
            'recent': paid.select_related('service').order_by('-booking_date')[:50],
            'seo_title': 'Earnings',
        },
    )
