"""Merchant dashboard — newsletter subscribers + signup popups. Mounted under
/dashboard/newsletter/ and surfaced in the Marketing section.
"""

from __future__ import annotations

import contextlib
import csv

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

_TRAIL = [
    {'label': 'Dashboard', 'url': '/dashboard/'},
    {'label': 'Marketing', 'url': '/dashboard/marketing/'},
    {'label': 'Newsletter'},
]


@staff_member_required
def subscribers_view(request):
    from plugins.installed.newsletter.models import NewsletterSubscriber

    qs = NewsletterSubscriber.objects.all()
    status = (request.GET.get('status') or '').strip()
    if status in {'pending', 'confirmed', 'unsubscribed'}:
        qs = qs.filter(status=status)

    if request.GET.get('export') == 'csv':
        resp = HttpResponse(content_type='text/csv')
        resp['Content-Disposition'] = 'attachment; filename="newsletter-subscribers.csv"'
        w = csv.writer(resp)
        w.writerow(['email', 'status', 'source', 'created_at', 'confirmed_at'])
        for s in qs.iterator():
            w.writerow([s.email, s.status, s.source, s.created_at, s.confirmed_at or ''])
        return resp

    counts = {
        row['status']: row['n']
        for row in NewsletterSubscriber.objects.values('status').annotate(n=Count('id'))
    }
    return render(
        request,
        'newsletter/dashboard/subscribers.html',
        {
            'subscribers': qs.select_related('customer')[:200],
            'counts': counts,
            'total': sum(counts.values()),
            'status': status,
            'active_nav': 'marketing',
            'breadcrumb_trail': _TRAIL,
        },
    )


@staff_member_required
def popups_view(request):
    from plugins.installed.newsletter.models import SignupPopup

    if request.method == 'POST':
        action = request.POST.get('action') or 'create'
        if action == 'create':
            name = (request.POST.get('name') or '').strip()
            if name:
                SignupPopup.objects.create(name=name[:120])
                messages.success(request, f'Popup “{name}” created — edit it to go live.')
            return redirect('/dashboard/newsletter/popups/')
        pid = request.POST.get('popup_id')
        popup = get_object_or_404(SignupPopup, id=pid) if pid else None
        if popup and action == 'toggle':
            popup.enabled = not popup.enabled
            popup.save(update_fields=['enabled', 'updated_at'])
        elif popup and action == 'delete':
            popup.delete()
        return redirect('/dashboard/newsletter/popups/')

    return render(
        request,
        'newsletter/dashboard/popups.html',
        {
            'popups': SignupPopup.objects.all(),
            'active_nav': 'marketing',
            'breadcrumb_trail': _TRAIL,
        },
    )


@staff_member_required
def popup_edit_view(request, popup_id: str):
    from plugins.installed.newsletter.models import SignupPopup

    popup = get_object_or_404(SignupPopup, id=popup_id)
    fields = (
        'name',
        'headline',
        'body',
        'button_label',
        'success_message',
        'trigger',
        'frequency',
        'audience',
        'incentive',
        'coupon_code',
    )
    if request.method == 'POST':
        for f in fields:
            if f in request.POST:
                setattr(popup, f, request.POST[f].strip())
        with contextlib.suppress(TypeError, ValueError):
            popup.trigger_value = max(
                0, int(request.POST.get('trigger_value') or popup.trigger_value)
            )
        popup.enabled = request.POST.get('enabled') == 'on'
        popup.save()
        messages.success(request, 'Popup saved.')
        return redirect('/dashboard/newsletter/popups/')

    return render(
        request,
        'newsletter/dashboard/popup_edit.html',
        {
            'popup': popup,
            'TRIGGERS': SignupPopup.TRIGGER_CHOICES,
            'FREQUENCIES': SignupPopup.FREQUENCY_CHOICES,
            'AUDIENCES': SignupPopup.AUDIENCE_CHOICES,
            'active_nav': 'marketing',
            'breadcrumb_trail': _TRAIL,
        },
    )
