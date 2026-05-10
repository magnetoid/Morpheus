"""Dashboard moderation surface for catalog reviews.

The plugin already owns the storefront write endpoint (views.add_review).
This module owns the merchant-facing list + approve/hide/respond
actions so the whole reviews surface stays inside its own plugin.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST


_FILTER_CHOICES = (
    ('all', 'All'),
    ('approved', 'Approved'),
    ('hidden', 'Hidden'),
    ('low_star', '1-2 stars'),
)


@staff_member_required
def reviews_list(request):
    """List + filter reviews. Default to 'all' so newcomers see everything."""
    from plugins.installed.catalog.models import Review

    selected = (request.GET.get('filter') or 'all').lower()
    qs = (Review.objects
          .select_related('product', 'customer')
          .order_by('-created_at'))
    if selected == 'approved':
        qs = qs.filter(is_approved=True)
    elif selected == 'hidden':
        qs = qs.filter(is_approved=False)
    elif selected == 'low_star':
        qs = qs.filter(rating__lte=2)
    rows = list(qs[:200])

    counts = {
        'all':      Review.objects.count(),
        'approved': Review.objects.filter(is_approved=True).count(),
        'hidden':   Review.objects.filter(is_approved=False).count(),
        'low_star': Review.objects.filter(rating__lte=2).count(),
    }

    return render(request, 'reviews/dashboard/list.html', {
        'rows': rows,
        'filters': _FILTER_CHOICES,
        'counts': counts,
        'selected_filter': selected,
        'active_nav': 'reviews',
    })


@staff_member_required
@require_POST
def review_action(request, review_id):
    """Approve / hide / unhide a single review. POST-only."""
    from plugins.installed.catalog.models import Review
    review = get_object_or_404(Review, pk=review_id)
    action = (request.POST.get('action') or '').lower()
    if action == 'approve':
        review.is_approved = True
        review.save(update_fields=['is_approved', 'updated_at'])
        messages.success(request, f"Approved review on {review.product.name}.")
    elif action == 'hide':
        review.is_approved = False
        review.save(update_fields=['is_approved', 'updated_at'])
        messages.success(request, f"Hid review on {review.product.name}.")
    else:
        messages.error(request, f"Unknown action: {action}")
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') \
        or '/dashboard/reviews/'
    return redirect(next_url)


@staff_member_required
@require_POST
def review_respond(request, review_id):
    """Add a public merchant reply. Stored as a metafield on the Review
    so we don't need a schema migration. Renders on the PDP via the
    same `reviews` template once we surface it (TODO).
    """
    from plugins.installed.catalog.models import Review
    review = get_object_or_404(Review, pk=review_id)
    body = (request.POST.get('body') or '').strip()
    if not body:
        messages.error(request, "Response body is required.")
        return redirect('/dashboard/reviews/')
    try:
        from plugins.installed.metafields.models import Metafield
        Metafield.objects.set(review, namespace='reviews', key='merchant_reply',
                              value=body[:2000])
        Metafield.objects.set(review, namespace='reviews', key='merchant_reply_at',
                              value=timezone.now().isoformat())
        messages.success(request, f"Posted response on {review.product.name}.")
    except Exception as e:  # noqa: BLE001
        messages.error(request, f"Couldn't save response: {e}")
    return redirect('/dashboard/reviews/')
