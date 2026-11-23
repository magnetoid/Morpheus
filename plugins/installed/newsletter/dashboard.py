"""Merchant dashboard — newsletter subscribers + signup popups. Mounted under
/dashboard/newsletter/ and surfaced in the Marketing section.
"""

from __future__ import annotations

import contextlib
import csv

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.authz import require_capability


@staff_member_required
@require_capability('marketing.read')
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
        },
    )


@staff_member_required
@require_capability('marketing.write')
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
        },
    )


@staff_member_required
@require_capability('marketing.write')
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
        },
    )


@staff_member_required
@require_capability('marketing.read')
def campaigns_view(request):
    """Marketing's EmailCampaigns, sent to the confirmed list newsletter owns."""
    from plugins.installed.marketing.models import EmailCampaign
    from plugins.installed.newsletter import campaigns as rules
    from plugins.installed.newsletter.models import NewsletterSubscriber

    rows = [
        {
            'c': c,
            'audience': rules.audience_label(c.audience),
            'missed': rules.is_missed(c),
            'scheduled_local': rules.local_input_value(c.scheduled_at).replace('T', ' '),
        }
        for c in EmailCampaign.objects.all()[:100]
    ]
    return render(
        request,
        'newsletter/dashboard/campaigns.html',
        {
            'rows': rows,
            'audience': NewsletterSubscriber.objects.filter(status='confirmed').count(),
            'active_nav': 'marketing',
        },
    )


def _edit_context(campaign, data: dict) -> dict:
    from plugins.installed.newsletter import campaigns as rules
    from plugins.installed.newsletter.models import NewsletterSubscriber

    return {
        'campaign': campaign,
        'form': data,
        'AUDIENCES': rules.AUDIENCES,
        'confirmed': NewsletterSubscriber.objects.filter(status='confirmed').count(),
        'editable': campaign is None or campaign.status == 'draft',
        'active_nav': 'marketing',
    }


@staff_member_required
@require_capability('marketing.write')
def campaign_edit_view(request, campaign_id=None):
    """Write a campaign: save it as a draft, schedule it, or send it now."""
    from plugins.installed.marketing.models import EmailCampaign
    from plugins.installed.newsletter import campaigns as rules

    campaign = get_object_or_404(EmailCampaign, id=campaign_id) if campaign_id else None
    if request.method != 'POST':
        data = {
            'name': campaign.name if campaign else '',
            'subject': campaign.subject if campaign else '',
            'preview_text': campaign.preview_text if campaign else '',
            'html_body': campaign.html_body if campaign else '',
            'audience': campaign.audience if campaign else '',
            'send_at': rules.local_input_value(campaign.scheduled_at) if campaign else '',
        }
        return render(
            request, 'newsletter/dashboard/campaign_edit.html', _edit_context(campaign, data)
        )

    fields = ('name', 'subject', 'preview_text', 'html_body', 'audience', 'send_at')
    data = {k: request.POST.get(k, '') for k in fields}
    action = request.POST.get('action') or 'save'
    try:
        # Save and schedule together: a refused time leaves nothing half-saved.
        with transaction.atomic():
            campaign = rules.save_campaign(
                campaign=campaign,
                name=data['name'],
                subject=data['subject'],
                preview_text=data['preview_text'],
                html_body=data['html_body'],
                audience=data['audience'],
            )
            if action == 'schedule':
                rules.schedule_campaign(campaign, rules.parse_local_datetime(data['send_at']))
        # The send is queued after the commit, so the worker reads the saved draft.
        if action == 'send':
            rules.send_campaign_now(campaign)
    except rules.CampaignError as e:
        messages.error(request, str(e))
        # Show the row as the database has it: a rolled-back new one is gone, a
        # draft saved before a refused send is kept.
        shown = EmailCampaign.objects.filter(pk=getattr(campaign, 'pk', None)).first()
        return render(
            request, 'newsletter/dashboard/campaign_edit.html', _edit_context(shown, data)
        )
    done = {'schedule': 'scheduled', 'send': 'queued for sending'}.get(action, 'saved as a draft')
    messages.success(request, f'"{campaign.name}" {done}.')
    return redirect('/dashboard/newsletter/campaigns/')


def _campaign_action(request, campaign_id, act, success: str):
    if request.method != 'POST':
        return redirect('/dashboard/newsletter/campaigns/')
    from plugins.installed.marketing.models import EmailCampaign
    from plugins.installed.newsletter.campaigns import CampaignError

    campaign = get_object_or_404(EmailCampaign, id=campaign_id)
    try:
        act(campaign)
    except CampaignError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, f'"{campaign.name}" {success}.')
    return redirect('/dashboard/newsletter/campaigns/')


@staff_member_required
@require_capability('marketing.write')
def campaign_send_view(request, campaign_id: str):
    """POST — queue a full send of one draft to its audience."""
    from plugins.installed.newsletter.campaigns import send_campaign_now

    return _campaign_action(request, campaign_id, send_campaign_now, 'queued for sending')


@staff_member_required
@require_capability('marketing.write')
def campaign_schedule_view(request, campaign_id: str):
    """POST ``send_at`` (store time) — schedule a draft."""
    from plugins.installed.newsletter import campaigns as rules

    when = rules.parse_local_datetime(request.POST.get('send_at', ''))
    return _campaign_action(
        request, campaign_id, lambda c: rules.schedule_campaign(c, when), 'scheduled'
    )


@staff_member_required
@require_capability('marketing.write')
def campaign_cancel_view(request, campaign_id: str):
    """POST — take a scheduled campaign back to an editable draft."""
    from plugins.installed.newsletter.campaigns import cancel_campaign

    return _campaign_action(request, campaign_id, cancel_campaign, 'is a draft again')


@staff_member_required
@require_capability('marketing.write')
def campaign_test_view(request, campaign_id: str):
    """POST — send one test copy to the given (or the staff member's) address."""
    if request.method != 'POST':
        return redirect('/dashboard/newsletter/campaigns/')
    from plugins.installed.marketing.models import EmailCampaign
    from plugins.installed.newsletter.tasks import send_campaign_test

    campaign = get_object_or_404(EmailCampaign, id=campaign_id)
    to = (request.POST.get('to') or request.user.email or '').strip()
    if to:
        send_campaign_test.delay(str(campaign.id), to)
        messages.success(request, f'Test copy of "{campaign.name}" sent to {to}.')
    else:
        messages.error(request, 'No email address for the test send.')
    return redirect('/dashboard/newsletter/campaigns/')
