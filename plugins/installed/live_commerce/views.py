"""Dashboard CRUD for live events (staff-only)."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from plugins.installed.live_commerce import services
from plugins.installed.live_commerce.models import LiveEvent, LiveEventProduct

_LIST_URL = '/dashboard/live/'


@staff_member_required
def index(request: HttpRequest) -> HttpResponse:
    events = LiveEvent.objects.all()
    return render(
        request,
        'live_commerce/dashboard/index.html',
        {'events': events, 'active_nav': 'apps'},
    )


@staff_member_required
def edit_event(request: HttpRequest, event_id=None) -> HttpResponse:
    event = get_object_or_404(LiveEvent, pk=event_id) if event_id else None
    if request.method == 'POST' and _save_from_post(request, event):
        return HttpResponseRedirect(_LIST_URL)
    return render(
        request,
        'live_commerce/dashboard/form.html',
        {
            'event': event,
            'pinned_slugs': _pinned_slugs(event),
            'status_choices': LiveEvent.STATUS_CHOICES,
            'active_nav': 'apps',
        },
    )


@require_POST
@staff_member_required
def delete_event(request: HttpRequest, event_id) -> HttpResponse:
    get_object_or_404(LiveEvent, pk=event_id).delete()
    messages.success(request, 'Live event deleted.')
    return HttpResponseRedirect(_LIST_URL)


@require_POST
@staff_member_required
def set_status(request: HttpRequest, event_id) -> HttpResponse:
    event = get_object_or_404(LiveEvent, pk=event_id)
    status = (request.POST.get('status') or '').strip()
    if services.set_status(event, status):
        messages.success(request, f'Event is now {status}.')
    return HttpResponseRedirect(_LIST_URL)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pinned_slugs(event) -> str:
    if not event:
        return ''
    return ', '.join(ep.product.slug for ep in event.products.select_related('product'))


def _save_from_post(request: HttpRequest, event) -> bool:
    """Create/update the event and rebuild its pinned-product rows. Returns True on save."""
    from plugins.installed.catalog.models import Product

    title = (request.POST.get('title') or '').strip()
    if not title:
        messages.error(request, 'Title is required.')
        return False
    slug = (request.POST.get('slug') or '').strip() or slugify(title)
    start = (request.POST.get('scheduled_start') or '').strip()
    end = (request.POST.get('scheduled_end') or '').strip()
    if not start or not end:
        messages.error(request, 'Scheduled start and end are required.')
        return False

    if event is None:
        event = LiveEvent(slug=slug)
    event.title = title
    event.slug = slug
    event.description = (request.POST.get('description') or '').strip()
    event.scheduled_start = start
    event.scheduled_end = end
    event.embed_url = (request.POST.get('embed_url') or '').strip()
    event.recording_url = (request.POST.get('recording_url') or '').strip()
    status = (request.POST.get('status') or '').strip()
    if status in dict(LiveEvent.STATUS_CHOICES):
        event.status = status
    try:
        event.save()
    except Exception as exc:  # noqa: BLE001 — surface a clean form error, never a 500
        messages.error(request, f'Could not save: {exc}')
        return False

    # Rebuild pinned products from the comma/space-separated slug list.
    raw = request.POST.get('pinned_slugs') or ''
    slugs = [s.strip() for s in raw.replace('\n', ',').split(',') if s.strip()]
    event.products.all().delete()
    products = {p.slug: p for p in Product.objects.filter(slug__in=slugs)}
    for order, s in enumerate(slugs):
        product = products.get(s)
        if product:
            LiveEventProduct.objects.create(event=event, product=product, sort_order=order)
    messages.success(request, 'Live event saved.')
    return True
