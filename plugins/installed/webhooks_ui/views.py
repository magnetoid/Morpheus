"""Webhooks dashboard pages (admin-only)."""

from __future__ import annotations

import secrets

from morpheus.views import get_object_or_404, redirect, render, staff_member_required


@staff_member_required
def endpoints_list(request):
    from core.models import WebhookEndpoint

    endpoints = WebhookEndpoint.objects.all().order_by('-created_at')
    return render(
        request,
        'webhooks_ui/list.html',
        {
            'endpoints': endpoints,
            'active_nav': 'webhooks',
        },
    )


@staff_member_required
def endpoint_create(request):
    from core.models import WebhookEndpoint

    if request.method == 'POST':
        WebhookEndpoint.objects.create(
            name=request.POST.get('name', 'Webhook')[:100],
            url=request.POST.get('url', '')[:500],
            secret=secrets.token_urlsafe(32),
            events=[
                e.strip() for e in (request.POST.get('events', '') or '').split(',') if e.strip()
            ],
            is_active=True,
        )
        return redirect('webhooks_ui:endpoints_list')
    return render(request, 'webhooks_ui/edit.html', {'endpoint': None, 'active_nav': 'webhooks'})


@staff_member_required
def endpoint_edit(request, endpoint_id):
    from core.models import WebhookEndpoint

    endpoint = get_object_or_404(WebhookEndpoint, id=endpoint_id)
    if request.method == 'POST':
        endpoint.name = request.POST.get('name', endpoint.name)[:100]
        endpoint.url = request.POST.get('url', endpoint.url)[:500]
        endpoint.events = [
            e.strip() for e in (request.POST.get('events', '') or '').split(',') if e.strip()
        ]
        endpoint.is_active = bool(request.POST.get('is_active'))
        endpoint.save()
        return redirect('webhooks_ui:endpoints_list')
    return render(
        request, 'webhooks_ui/edit.html', {'endpoint': endpoint, 'active_nav': 'webhooks'}
    )


@staff_member_required
def endpoint_delete(request, endpoint_id):
    from core.models import WebhookEndpoint

    endpoint = get_object_or_404(WebhookEndpoint, id=endpoint_id)
    if request.method == 'POST':
        endpoint.delete()
    return redirect('webhooks_ui:endpoints_list')


@staff_member_required
def deliveries_list(request):
    from plugins.installed.webhooks_ui.models import WebhookDelivery

    deliveries = WebhookDelivery.objects.select_related('endpoint').order_by('-created_at')[:200]
    return render(
        request,
        'webhooks_ui/deliveries.html',
        {
            'deliveries': deliveries,
            'active_nav': 'webhooks',
        },
    )


@staff_member_required
def delivery_replay(request, delivery_id):
    """Re-enqueue a failed / DLQ'd delivery in-place — resets attempts to 0
    and re-runs through the retry chain. POST-only."""
    from plugins.installed.webhooks_ui.models import WebhookDelivery
    from plugins.installed.webhooks_ui.tasks import replay_delivery

    d = get_object_or_404(WebhookDelivery, id=delivery_id)
    if request.method == 'POST':
        replay_delivery.delay(str(d.id))
    return redirect('webhooks_ui:deliveries_list')
